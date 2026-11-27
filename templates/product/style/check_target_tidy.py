#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run clang-tidy, as an advisory check, on the product's own sources of a Zephyr build.

The input is the compile_commands.json of a build directory. Only the sources that lie inside the
Git top level of the product, and outside the build directory, are analysed: Zephyr, Crux, the SDK
and generated sources are not. Findings are printed and counted and never fail the run. A file that
clang-tidy could not compile makes the run exit 1, because its result is missing. The script changes
no file: it never passes --fix.

This is a product-side developer tool. It is not a Crux interface, no Crux CI runs it, and it has
not been run on Zephyr driver sources. See "Static analysis of target code" in Crux's
docs/coding-guidelines.md.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
DEFAULT_PROFILE = os.path.join(HERE, "target.clang-tidy")
DEFAULT_TOOL = "clang-tidy-18"
# The product directories whose headers are reported. Same list as style/.clang-tidy.
HEADER_DIRECTORIES = "app|domain|drivers|include|tests"
SOURCE_SUFFIXES = (".c", ".cc", ".cpp", ".cxx")
FINDING = re.compile(r"^.+:\d+:\d+: warning: ")


def fail(message):
    print(message, file=sys.stderr)
    return 2


def plural(count, noun):
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def regex_escape(text):
    """Escape the characters that are special in a POSIX extended regular expression."""
    return re.sub(r"([.^$*+?()\[\]{}|\\])", r"\\\1", text)


def git_top_level():
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    except OSError:
        return None
    return os.path.realpath(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None


def product_sources(database, root, build, excludes):
    """Return the sorted absolute paths of the C and C++ sources of the product in the database."""
    found = set()
    for entry in database:
        path = os.path.realpath(os.path.join(entry.get("directory", ""), entry["file"]))
        if not path.lower().endswith(SOURCE_SUFFIXES):
            continue
        if not path.startswith(root + os.sep) or path.startswith(build + os.sep):
            continue
        relative = os.path.relpath(path, root).replace(os.sep, "/")
        if any(pattern.search(relative) for pattern in excludes):
            continue
        found.add(path)
    return sorted(found)


def parse(argv):
    if "--" in argv:
        split = argv.index("--")
        argv, extra = argv[:split], argv[split + 1:]
    else:
        extra = []
    parser = argparse.ArgumentParser(
        prog="check_target_tidy.py",
        description="Advisory clang-tidy run on the product's own sources of a Zephyr build. "
                    "Findings are reported and never fail the run.",
        epilog="Arguments after a lone -- go to clang-tidy, for example: "
               "-- --extra-arg=-Wno-unknown-warning-option. Environment: CLANG_TIDY names the tool "
               f"(default {DEFAULT_TOOL}). Exit status: 0 analysed, 1 a file did not compile, "
               "2 usage or missing input.")
    parser.add_argument("build_dir", help="build directory that holds compile_commands.json")
    parser.add_argument("--profile", default=DEFAULT_PROFILE,
                        help="clang-tidy configuration file (default: target.clang-tidy beside this script)")
    parser.add_argument("--exclude", action="append", default=[], metavar="REGEX",
                        help="skip sources whose path relative to the product root matches REGEX "
                             "(Python regular expression, repeatable)")
    parser.add_argument("--header-filter", metavar="REGEX",
                        help=f"headers to report (default: {HEADER_DIRECTORIES} directories of the product)")
    parser.add_argument("--root", help="product root (default: the Git top level of the current directory)")
    return parser.parse_args(argv), extra


def main(argv):
    args, extra = parse(argv)
    tool = os.environ.get("CLANG_TIDY", DEFAULT_TOOL)
    root = os.path.realpath(args.root) if args.root else git_top_level()
    if not root:
        return fail("Not inside a Git repository. Run from the product, or pass --root.")
    build = os.path.realpath(args.build_dir)
    database_path = os.path.join(build, "compile_commands.json")
    if not os.path.isfile(database_path):
        return fail(f"No compile_commands.json in {build}. Configure the build with "
                    "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON first.")
    if not os.path.isfile(args.profile):
        return fail(f"The clang-tidy profile {args.profile} does not exist.")
    if not (shutil.which(tool) or os.path.isfile(tool)):
        return fail(f"Tool not found: {tool}. Install clang-tidy 18 or set CLANG_TIDY.")
    try:
        excludes = [re.compile(pattern) for pattern in args.exclude]
    except re.error as error:
        return fail(f"Bad --exclude pattern: {error}")
    with open(database_path) as stream:
        database = json.load(stream)

    sources = product_sources(database, root, build, excludes)
    if not sources:
        print(f"No product source files in {database_path}: nothing to analyse.")
        return 0
    header_filter = args.header_filter or f"^{regex_escape(root)}/({HEADER_DIRECTORIES})/"

    findings = 0
    broken = []
    for source in sources:
        command = [tool, "-p", build, f"--config-file={args.profile}", f"--header-filter={header_filter}",
                   "--quiet", *extra, source]
        result = subprocess.run(command, capture_output=True, text=True)
        output = result.stdout + result.stderr
        if output.strip():
            print(output.rstrip())
        findings += sum(1 for line in result.stdout.splitlines() if FINDING.match(line))
        if result.returncode != 0:
            broken.append(os.path.relpath(source, root))

    print(f"\n{plural(len(sources), 'source file')} analysed, {plural(findings, 'finding')}, "
          f"{plural(len(broken), 'file')} that did not compile. Advisory: findings do not fail this run.")
    if broken:
        print("clang-tidy could not analyse: " + ", ".join(broken), file=sys.stderr)
        print("A Zephyr database holds the build's own compiler options. Options that clang does not know "
              "can be passed after --, for example --extra-arg=-Wno-unknown-warning-option.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
