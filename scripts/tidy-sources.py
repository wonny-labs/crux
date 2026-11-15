#!/usr/bin/env python3
"""Derive the clang-tidy source list from the compile databases of the host builds.

Nobody maintains a path list. The sources to analyse are the C and C++ sources under components/,
samples/, tests/ and web/ that the listed builds compile, minus a short list of exclusions that each
carry a reason (scripts/tidy-sources.conf). A new source is analysed as soon as a listed build compiles it.

    tidy-sources.py list   print `<build>\\t<source>` for every source to analyse
    tidy-sources.py check  validate the configuration against the databases, run no clang-tidy
    tidy-sources.py run    check, then run clang-tidy once per source (-p <its build>)

The check fails when a build directory holds a compile database that is neither listed as analysed
nor ignored with a reason (its sources would be in no list), when an exclusion has no reason or names
a file that does not exist, and, with --strict, when a listed build is missing or an exclusion names a
source that no listed build compiles. Without --strict those are warnings, so a developer who built
only some consumers can still run the analysis. CI passes --strict.

Configuration lines (`;` separates fields, `#` starts a comment):

    build ; build/linux/debug                      analyse this build's database (order is priority)
    ignore-build ; build/*-boundary ; <reason>     a database that is deliberately not analysed
    exclude ; tests/x/probe.c ; <reason>           one compiled source that is not analysed

When a source is in several databases, the first listed build wins; it is analysed once.

Exit status: 0 success, 1 a check or clang-tidy failed, 2 usage or environment error.
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import fnmatch
import json
import os
import re
import subprocess
import sys

OWNED_ROOTS = ("components", "samples", "tests", "web")
SOURCE_SUFFIXES = (".c", ".cc", ".cpp", ".cxx")
DIAGNOSTIC = re.compile(r"^(?P<file>\S.*?):(?P<line>\d+):(?P<col>\d+): (?P<level>warning|error): "
                        r"(?P<message>.*?)(?: \[(?P<check>[^\]]+)\])?$")
KINDS = ("build", "ignore-build", "exclude")


class Usage(Exception):
    """An environment or usage problem (exit status 2)."""


class Config:
    def __init__(self):
        self.builds = []          # [relative build directory]
        self.ignored = []         # [(glob, reason)]
        self.excluded = {}        # {relative source: reason}
        self.problems = []


def parse_config(path):
    config = Config()
    name = os.path.basename(path)
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
    except OSError as error:
        raise Usage(f"cannot read the configuration {path}: {error}")
    for number, line in enumerate(lines, 1):
        text = line.split("#", 1)[0].strip()
        if not text:
            continue
        where = f"{name}:{number}"
        fields = [field.strip() for field in text.split(";")]
        kind = fields[0]
        if kind not in KINDS:
            config.problems.append(f"{where}: unknown kind '{kind}' (expected one of {', '.join(KINDS)})")
            continue
        if len(fields) < 2 or not fields[1]:
            config.problems.append(f"{where}: '{kind}' needs a path")
            continue
        target = fields[1].rstrip("/")
        if os.path.isabs(target) or ".." in target.split("/"):
            config.problems.append(f"{where}: '{target}' must be a relative path inside the repository")
            continue
        reason = ";".join(fields[2:]).strip()
        if kind == "build":
            if not target.startswith("build/"):
                config.problems.append(f"{where}: a build directory must be below build/, not '{target}'")
            elif target in config.builds:
                config.problems.append(f"{where}: build '{target}' is listed twice")
            else:
                config.builds.append(target)
        elif kind == "ignore-build":
            if not reason:
                config.problems.append(f"{where}: ignore-build '{target}' needs a reason")
            else:
                config.ignored.append((target, reason))
        else:
            if any(ch in target for ch in "*?["):
                config.problems.append(f"{where}: an exclusion is one explicit path, not a pattern: '{target}'")
            elif not reason:
                config.problems.append(f"{where}: exclusion '{target}' needs a reason")
            elif target in config.excluded:
                config.problems.append(f"{where}: '{target}' is excluded twice")
            else:
                config.excluded[target] = reason
    return config


def read_database(db_path, repo):
    """Return the set of owned C-family sources (relative to repo) that a database compiles, sorted."""
    with open(db_path, encoding="utf-8") as handle:
        records = json.load(handle)
    found = set()
    for record in records:
        file = record.get("file", "")
        directory = record.get("directory", "")
        path = file if os.path.isabs(file) else os.path.join(directory, file)
        path = os.path.normpath(path)
        rel = os.path.relpath(path, repo).replace(os.sep, "/")
        if rel.startswith("../") or rel == "..":
            continue
        if rel.split("/", 1)[0] not in OWNED_ROOTS or rel.startswith("build/"):
            continue
        if rel.endswith(SOURCE_SUFFIXES):
            found.add(rel)
    return sorted(found)


def discover_databases(build_root, repo):
    """Directories (relative to repo) below build_root that hold a compile database, not descending into them."""
    found = []
    if not os.path.isdir(build_root):
        return found
    for current, dirs, files in os.walk(build_root):
        if "compile_commands.json" in files:
            found.append(os.path.relpath(current, repo).replace(os.sep, "/"))
            dirs[:] = []
        else:
            dirs.sort()
    return sorted(found)


class Plan:
    def __init__(self):
        self.items = []           # [(build, source)]
        self.problems = []        # failures
        self.warnings = []        # failures in --strict mode
        self.databases = []       # [(build, sources)]


def build_plan(repo, config, strict, primary=None, build_root=None):
    plan = Plan()
    problems = plan.problems
    problems.extend(config.problems)
    warn = problems if strict else plan.warnings

    builds = list(config.builds)
    if primary:
        primary = primary.rstrip("/")
        if primary not in builds:
            problems.append(f"--primary '{primary}' is not a listed build")
        else:
            builds.remove(primary)
            builds.insert(0, primary)

    seen = {}
    for build in builds:
        db = os.path.join(repo, build, "compile_commands.json")
        if not os.path.isfile(db):
            warn.append(f"listed build {build} has no compile_commands.json (build it first)")
            continue
        try:
            sources = read_database(db, repo)
        except (OSError, ValueError) as error:
            problems.append(f"cannot read {build}/compile_commands.json: {error}")
            continue
        plan.databases.append((build, sources))
        for source in sources:
            if not os.path.isfile(os.path.join(repo, source)):
                problems.append(f"{build} compiles {source}, which does not exist in the tree (stale database)")
            elif source not in seen:
                seen[source] = build

    for source, reason in config.excluded.items():
        if not os.path.isfile(os.path.join(repo, source)):
            problems.append(f"exclusion {source} names a file that does not exist; remove the line")
        elif source not in seen:
            warn.append(f"exclusion {source} is compiled by no listed build; remove the line ({reason})")
    plan.items = [(build, source) for source, build in seen.items() if source not in config.excluded]
    order = {build: index for index, build in enumerate(builds)}
    plan.items.sort(key=lambda item: (order[item[0]], item[1]))

    root = build_root if build_root else os.path.join(repo, "build")
    for build in discover_databases(root, repo):
        if build in config.builds or any(fnmatch.fnmatch(build, pattern) for pattern, _r in config.ignored):
            continue
        db = os.path.join(repo, build, "compile_commands.json")
        try:
            sources = read_database(db, repo)
        except (OSError, ValueError):
            sources = []
        shown = ", ".join(sources[:3]) + (f" and {len(sources) - 3} more" if len(sources) > 3 else "")
        warn.append(f"{build} holds a compile database that is neither listed as 'build' nor 'ignore-build'"
                    f" in the configuration; its {len(sources)} owned sources would be in no list"
                    + (f" ({shown})" if sources else ""))
    return plan


def parse_diagnostics(text, repo):
    found = []
    for line in text.splitlines():
        match = DIAGNOSTIC.match(line)
        if not match:
            continue
        path = match.group("file")
        if os.path.isabs(path):
            rel = os.path.relpath(os.path.normpath(path), repo).replace(os.sep, "/")
            if rel.startswith("../"):
                rel = path
        else:
            rel = path
        found.append({"file": rel, "line": int(match.group("line")), "col": int(match.group("col")),
                      "level": match.group("level"), "check": match.group("check") or "(no check)",
                      "message": match.group("message")})
    return found


def directory_of(rel):
    parts = rel.split("/")
    if rel.startswith("/") or parts[0] not in OWNED_ROOTS:
        return "(outside the repository)"
    return "/".join(parts[:2]) if len(parts) > 2 else parts[0]


def analyse_one(tidy, repo, build, source, extra):
    command = [tidy, "-p", os.path.join(repo, build), "--quiet", *extra, os.path.join(repo, source)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, cwd=repo)
    except OSError as error:
        return {"build": build, "source": source, "status": -1, "output": f"cannot start {tidy}: {error}",
                "diagnostics": []}
    output = result.stdout + result.stderr
    return {"build": build, "source": source, "status": result.returncode, "output": output,
            "diagnostics": parse_diagnostics(result.stdout, repo)}


def run_tidy(plan, repo, tidy, jobs, extra, report_only, json_path, out):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(analyse_one, tidy, repo, b, s, extra) for b, s in plan.items]
        for future in futures:
            results.append(future.result())

    unique = collections.OrderedDict()
    for result in results:
        for diagnostic in result["diagnostics"]:
            key = (diagnostic["file"], diagnostic["line"], diagnostic["col"], diagnostic["check"])
            unique.setdefault(key, diagnostic)
    diagnostics = list(unique.values())
    failed = [r for r in results if r["status"] != 0]
    unreadable = [r for r in failed if r["status"] == -1]

    by_directory = collections.Counter(directory_of(d["file"]) for d in diagnostics)
    by_check = collections.Counter(d["check"] for d in diagnostics)
    files = {d["file"] for d in diagnostics}

    print(f"tidy-sources: {len(results)} sources analysed in {len(plan.databases)} builds; "
          f"{len(failed)} failed; {len(diagnostics)} diagnostics in {len(files)} files", file=out)
    if by_directory:
        print("\ndiagnostics by directory of the reported file:", file=out)
        print(f"  {'directory':<40} {'count':>5}", file=out)
        for directory, count in sorted(by_directory.items()):
            print(f"  {directory:<40} {count:>5}", file=out)
        print("\ndiagnostics by check:", file=out)
        for check, count in by_check.most_common():
            print(f"  {count:>5}  {check}", file=out)
        print("\ndiagnostics:", file=out)
        for diagnostic in sorted(diagnostics, key=lambda d: (d["file"], d["line"], d["col"])):
            print(f"  {diagnostic['file']}:{diagnostic['line']}:{diagnostic['col']}: "
                  f"{diagnostic['message']} [{diagnostic['check']}]", file=out)
    failed_without_diagnostic = [r for r in failed if not r["diagnostics"]]
    for result in failed_without_diagnostic:
        print(f"\nclang-tidy failed on {result['source']} (exit {result['status']}) without a parsed diagnostic:\n"
              f"{result['output'].strip()}", file=out)
    for result in failed:
        if result["diagnostics"] and not report_only:
            print(f"\nclang-tidy failed on {result['source']}:\n{result['output'].strip()}", file=out)

    if json_path:
        report = {"sources": len(results), "builds": [b for b, _s in plan.databases],
                  "failed_sources": sorted(r["source"] for r in failed), "diagnostics": diagnostics}
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
    if unreadable:
        return 1
    return 0 if (report_only or not failed) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("list", "check", "run"))
    here = os.path.dirname(os.path.abspath(__file__))
    parser.add_argument("--repo", default=os.path.dirname(here))
    parser.add_argument("--config", default=os.path.join(here, "tidy-sources.conf"))
    parser.add_argument("--primary", help="listed build directory to put first (its compile commands win)")
    parser.add_argument("--build-root", help="directory searched for unlisted compile databases (default <repo>/build)")
    parser.add_argument("--strict", action="store_true",
                        help="a missing listed build, an unlisted database and a stale exclusion fail")
    parser.add_argument("--tidy", default=os.environ.get("CLANG_TIDY", "clang-tidy-18"))
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--report-only", action="store_true",
                        help="print the diagnostics and the problems found, exit 0 unless clang-tidy cannot run")
    parser.add_argument("--json", help="write the run result as JSON")
    parser.add_argument("extra", nargs="*", help="arguments after -- go to clang-tidy")
    args = parser.parse_args(argv)

    repo = os.path.realpath(args.repo)
    try:
        config = parse_config(args.config)
        build_root = os.path.realpath(args.build_root) if args.build_root else None
        plan = build_plan(repo, config, args.strict, args.primary, build_root)
    except Usage as error:
        print(f"tidy-sources: {error}", file=sys.stderr)
        return 2

    for warning in plan.warnings:
        print(f"tidy-sources: warning: {warning}", file=sys.stderr)
    for problem in plan.problems:
        print(f"tidy-sources: {problem}", file=sys.stderr)

    if args.command == "list":
        if plan.problems:
            return 1
        for build, source in plan.items:
            print(f"{build}\t{source}")
        return 0
    if args.command == "check":
        if plan.problems:
            return 1
        print(f"tidy-sources: {len(plan.items)} sources in {len(plan.databases)} builds, "
              f"{len(config.excluded)} excluded", file=sys.stderr)
        return 0
    if plan.problems and not args.report_only:
        return 1
    if not plan.items:
        print("tidy-sources: no source to analyse", file=sys.stderr)
        return 1
    return run_tidy(plan, repo, args.tidy, max(1, args.jobs), args.extra, args.report_only, args.json, sys.stdout)


if __name__ == "__main__":
    sys.exit(main())
