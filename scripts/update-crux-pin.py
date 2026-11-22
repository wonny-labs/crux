#!/usr/bin/env python3
"""Move the Crux pin in a product's west manifest to a commit SHA.

Run it in a product repository. It resolves the target revision (by default the
Crux remote's main branch) to a full commit SHA, rewrites only the revision value
of the Crux project in the manifest, runs the product's optional hook and writes
a summary that can serve as a commit message and pull request text.

Exit status: 0 the pin moved (or would move, with --dry-run), 3 the pin is
already current, 1 an error, 2 a usage error.
"""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

try:
    import yaml
except ImportError:  # pragma: no cover - west installs PyYAML
    sys.exit("update-crux-pin: PyYAML is required (west installs it)")

EXIT_CHANGED = 0
EXIT_ERROR = 1
EXIT_CURRENT = 3
CRUX_NAMES = ("crux", "crux-pilot")
HOOK = Path("scripts/crux-pin-hook")
SHA = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


class PinError(Exception):
    pass


def git(*args, cwd=None):
    result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise PinError(f"git {args[0]} failed: {scrub(result.stderr.strip())}")
    return result.stdout


def scrub(text):
    """Drop user names and tokens from every URL in a message."""
    return re.sub(r"(://)[^/@\s]+@", r"\1", text)


def redact(url):
    """Drop any user name or token from a URL before it is printed."""
    parts = urllib.parse.urlsplit(url)
    if parts.username or parts.password:
        host = parts.hostname or ""
        if parts.port:
            host += f":{parts.port}"
        return urllib.parse.urlunsplit(parts._replace(netloc=host))
    return url


def find_project(manifest, name):
    projects = (manifest.get("manifest") or {}).get("projects") or []
    if name:
        matches = [p for p in projects if p.get("name") == name]
        if not matches:
            raise PinError(f"no project named {name} in the manifest")
        return matches[0]
    matches = [p for p in projects if p.get("name") in CRUX_NAMES]
    if len(matches) != 1:
        raise PinError("cannot tell which project is Crux; name it with --project")
    return matches[0]


def project_url(manifest, project):
    if project.get("url"):
        return project["url"]
    body = manifest["manifest"]
    remote_name = project.get("remote") or (body.get("defaults") or {}).get("remote")
    remotes = {r.get("name"): r for r in body.get("remotes") or []}
    if remote_name not in remotes:
        raise PinError(f"project {project['name']} has no url and no known remote; pass --remote-url")
    base = str(remotes[remote_name]["url-base"]).rstrip("/")
    return f"{base}/{project.get('repo-path') or project['name']}"


def resolve(url, to, branch):
    """Return (SHA, ref) for --to, or for the branch on the remote."""
    if to and SHA.match(to.lower()):
        return to.lower(), to.lower()
    wanted = [f"refs/heads/{branch}"] if not to else [f"refs/heads/{to}", f"refs/tags/{to}"]
    refs = {}
    for line in git("ls-remote", "--", url, *wanted).splitlines():
        sha, ref = line.split("\t", 1)
        refs[ref] = sha
    found = {}
    for ref in wanted:
        if ref + "^{}" in refs:  # The commit an annotated tag points to.
            found[ref] = refs[ref + "^{}"]
        elif ref in refs:
            found[ref] = refs[ref]
    if not found:
        raise PinError(f"{to or branch} is not a branch or tag of {redact(url)}, and not a full SHA")
    if len(found) > 1:
        raise PinError(f"{to} names both a branch and a tag; pass the full ref's SHA")
    ref, sha = next(iter(found.items()))
    sha = sha.lower()
    if not SHA.match(sha):
        raise PinError(f"the remote returned {sha}, which is not a full SHA")
    return sha, ref


def revision_node(text, name):
    """Return the scalar node of the named project's revision, with its position."""
    root = yaml.compose(text)
    body = mapping_get(root, "manifest")
    projects = mapping_get(body, "projects")
    for item in getattr(projects, "value", []):
        node_name = mapping_get(item, "name")
        if node_name is not None and node_name.value == name:
            node = mapping_get(item, "revision")
            if node is None:
                raise PinError(f"project {name} has no revision line; add one first")
            if not isinstance(node, yaml.ScalarNode):
                raise PinError(f"the revision of project {name} is not a plain value")
            return node
    raise PinError(f"no project named {name} in the manifest")


def mapping_get(node, key):
    if not isinstance(node, yaml.MappingNode):
        return None
    for k, v in node.value:
        if k.value == key:
            return v
    return None


def rewrite(text, name, new):
    """Replace only the revision value of one project and drop that line's comment."""
    node = revision_node(text, name)
    start, end = node.start_mark, node.end_mark
    if start.line != end.line:
        raise PinError(f"the revision of project {name} spans several lines")
    lines = text.splitlines(keepends=True)
    line = lines[start.line]
    ending = line[len(line.rstrip("\r\n")):]
    rest = line[end.column:].rstrip("\r\n")
    if rest.strip() and not rest.lstrip().startswith("#"):
        raise PinError(f"unexpected text after the revision of project {name}")
    # A comment on that line described the old revision, so it goes with it.
    lines[start.line] = line[:start.column] + new + ending
    result = "".join(lines)
    check(text, result, name, new)
    return result


def check(before, after, name, new):
    """Fail unless the only parsed difference is the new revision."""
    old_doc, new_doc = yaml.safe_load(before), yaml.safe_load(after)
    for doc, value in ((old_doc, None), (new_doc, new)):
        project = find_project(doc, name)
        if value is not None and str(project.get("revision")) != value:
            raise PinError("the rewritten manifest does not hold the new revision")
        project["revision"] = new
    if old_doc != new_doc:
        raise PinError("the rewrite changed more than the revision; nothing was written")


def workspace_checkout(manifest_path, project):
    """The Crux checkout in the west workspace, if there is one."""
    for parent in manifest_path.resolve().parents:
        if (parent / ".west").is_dir():
            checkout = parent / str(project.get("path") or project["name"])
            return checkout if (checkout / ".git").exists() else None
    return None


def has_commit(repo, sha):
    return subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=repo,
                          capture_output=True).returncode == 0


def commit_log(checkout, url, ref, old, new, limit):
    """Return (lines, note) for old..new, fetching into a temporary clone if needed."""
    temp = None
    try:
        repo = checkout
        if repo is not None and not has_commit(repo, new):
            # A fetch only adds objects and FETCH_HEAD; west's refs stay as they are.
            subprocess.run(["git", "fetch", "-q", url, ref], cwd=repo, capture_output=True)
        if repo is None or not has_commit(repo, new):
            temp = tempfile.mkdtemp(prefix="crux-pin-")
            repo = Path(temp) / "crux.git"
            git("clone", "-q", "--bare", "--filter=blob:none", "--", url, str(repo))
            if not has_commit(repo, new):
                return [], "The new revision was not found on the remote, so no log is shown."
        if not SHA.match(old.lower()) or not has_commit(repo, old):
            return [], f"The previous revision `{old}` is not a commit SHA here, so no log is shown."
        note = None
        if subprocess.run(["git", "merge-base", "--is-ancestor", old, new], cwd=repo,
                          capture_output=True).returncode != 0:
            note = "**The new revision does not contain the previous one.** Check that this move is intended."
        out = git("log", "--format=%h %s", "--abbrev=12", f"{old}..{new}", cwd=repo).splitlines()
        if len(out) > limit:
            out = out[:limit] + [f"... and {len(out) - limit} more"]
        return out, note
    except PinError as error:
        return [], f"No log: {error}"
    finally:
        if temp:
            shutil.rmtree(temp, ignore_errors=True)


def summary(name, manifest_rel, old, new, source, lines, note):
    text = [f"build(deps): move the Crux pin to {new[:12]}", "",
            f"Moves `{name}` in `{manifest_rel}` from `{old}` to `{new}` ({source}).", ""]
    if note:
        text += [note, ""]
    if lines:
        text += [f"Commits in Crux since the previous pin ({len(lines)}):", ""]
        text += [f"- {line}" for line in lines]
        text.append("")
    return "\n".join(text)


def product_root(manifest_path):
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=manifest_path.parent,
                            text=True, capture_output=True)
    return Path(result.stdout.strip()) if result.returncode == 0 else manifest_path.parent


def run_hook(root, env):
    hook = root / HOOK
    if not hook.exists():
        return
    if not os.access(hook, os.X_OK):
        raise PinError(f"{HOOK} exists but is not executable")
    result = subprocess.run([str(hook)], cwd=root, env=dict(os.environ, **env))
    if result.returncode != 0:
        raise PinError(f"{HOOK} failed with status {result.returncode}; the manifest is already updated")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--manifest", default="west.yml", type=Path,
                        help="the product's west manifest (default: west.yml)")
    parser.add_argument("--project", help="the Crux project's name (default: the project named crux or crux-pilot)")
    parser.add_argument("--to", metavar="REV",
                        help="a full SHA, branch or tag of the Crux remote (default: the head of --branch)")
    parser.add_argument("--branch", default="main", help="the Crux branch to follow (default: main)")
    parser.add_argument("--remote-url", help="fetch from this URL instead of the manifest's, such as a mirror")
    parser.add_argument("--checkout", type=Path,
                        help="the Crux checkout passed to the hook (default: found in the west workspace)")
    parser.add_argument("--summary", type=Path, metavar="FILE",
                        help="write a commit message: a title line, a blank line and the old..new log")
    parser.add_argument("--log-limit", type=int, default=100, help="the most commits to list (default: 100)")
    parser.add_argument("--no-hook", action="store_true", help=f"do not run {HOOK}")
    parser.add_argument("--dry-run", action="store_true",
                        help="leave the manifest alone and run no hook; --summary is still written")
    args = parser.parse_args(argv)

    try:
        with args.manifest.open(newline="") as handle:  # Keeps CRLF line endings.
            text = handle.read()
        manifest = yaml.safe_load(text)
        project = find_project(manifest, args.project)
        name = project["name"]
        url = args.remote_url or project_url(manifest, project)
        old = str(project.get("revision", ""))
        new, ref = resolve(url, args.to, args.branch)
        if old.lower() == new:
            print(f"{name} is already pinned to {new}")
            return EXIT_CURRENT
        updated = rewrite(text, name, new)
        print(f"{name}: {old} -> {new}")
        checkout = args.checkout or workspace_checkout(args.manifest, project)
        if args.summary:
            lines, note = commit_log(checkout, url, ref, old, new, args.log_limit)
            source = f"`{ref}` of {redact(url)}"
            args.summary.write_text(summary(name, args.manifest.name, old, new, source, lines, note))
        if args.dry_run:
            return EXIT_CHANGED
        with args.manifest.open("w", newline="") as handle:
            handle.write(updated)
        if not args.no_hook:
            run_hook(product_root(args.manifest), {
                "CRUX_PIN_OLD": old, "CRUX_PIN_NEW": new, "CRUX_PIN_PROJECT": name,
                "CRUX_PIN_MANIFEST": str(args.manifest.resolve()),
                "CRUX_PIN_CHECKOUT": str(checkout) if checkout else ""})
        return EXIT_CHANGED
    except (PinError, OSError, yaml.YAMLError) as error:
        print(f"update-crux-pin: {error}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
