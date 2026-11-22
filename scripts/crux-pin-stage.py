#!/usr/bin/env python3
"""Build and propose a Crux pin change in a stage that holds the token and trusts no workspace.

CI runs this in its own, freshly started container, apart from any build. It takes
nothing from a shared workspace: it clones the product and Crux itself, and runs
the bot scripts it takes from the Crux revision that the clean product manifest
pins, never from the new Crux revision and never from a build's checkout.

  prepare   (no token) clone the product and Crux into an empty --workdir, check
            the target, take the scripts from the pinned revision, write the new
            manifest and the pull request text.
  propose   (token) run open-pin-pr.py from the pinned revision against that
            clone, with a fixed PATH and Git ignoring user and system settings.

Run this script from a copy that the wrapper took from Crux at the pinned
revision. prepare refuses a copy that differs from the pinned one.

Exit status of prepare: 0 ready, 3 nothing to propose (the pin is current, or the
product moved since the build), 1 an error. propose: 0 done, 1 an error.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

READY = DONE = 0
ERROR = 1
NOTHING = 3
FOREIGN = 4
CRUX_NAMES = ("crux", "crux-pilot")
SHA = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
BOT_SCRIPTS = ("update-crux-pin.py", "open-pin-pr.py")
STAGE_SCRIPT = "scripts/crux-pin-stage.py"
# Git reads no system or user configuration and ssh no user configuration.
ISOLATION = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_ATTR_NOSYSTEM": "1",
             "GIT_SSH_COMMAND": "ssh -F /dev/null", "GIT_TERMINAL_PROMPT": "0", "GIT_NO_REPLACE_OBJECTS": "1"}
PASS_THROUGH = ("HOME", "SSH_AUTH_SOCK", "LANG", "LC_ALL", "TMPDIR")


class StageError(Exception):
    pass


def env_for(path, extra=None):
    """A small environment: no PYTHON*, no GIT_* from the caller, then the isolation."""
    env = {key: os.environ[key] for key in PASS_THROUGH if key in os.environ}
    env["PATH"] = path
    env.update(ISOLATION)
    env.update(extra or {})
    return env


def scrub(text):
    """Drop user names and tokens from every URL in a message."""
    return re.sub(r"(://)[^/@\s]+@", r"\1", text)


def run(cmd, env, cwd=None, check=True):
    result = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise StageError(f"{cmd[0]} {cmd[1] if len(cmd) > 1 else ''} failed: "
                         + scrub(result.stderr.strip()))
    return result


def pinned_revision(manifest_path, project_name):
    try:
        import yaml  # Only prepare needs it, so the token-holding propose mode does not import it.
    except ImportError:
        raise StageError("PyYAML is required (west installs it)") from None
    manifest = yaml.safe_load(manifest_path.read_text()) or {}
    projects = (manifest.get("manifest") or {}).get("projects") or []
    matches = [p for p in projects if p.get("name") == project_name] if project_name else \
        [p for p in projects if p.get("name") in CRUX_NAMES]
    if len(matches) != 1:
        raise StageError("cannot tell which project is Crux; name it with --project")
    revision = str(matches[0].get("revision", "")).lower()
    if not SHA.match(revision):
        raise StageError("the manifest does not pin Crux to a full commit SHA")
    return revision


def prepare(args):
    work = Path(args.workdir)
    if work.exists() and any(work.iterdir()):
        raise StageError(f"{work} is not empty: this stage starts from nothing")
    if not SHA.match(args.target.lower()) or not SHA.match(args.product_commit.lower()):
        raise StageError("--target and --product-commit must be full commit SHAs")
    work.mkdir(parents=True, exist_ok=True)
    env = env_for(os.environ.get("PATH", "/usr/bin:/bin"))
    product, crux, bot = work / "product", work / "crux", work / "bot"

    run(["git", "clone", "-q", "--", args.product_remote, str(product)], env)
    head = run(["git", "rev-parse", "HEAD"], env, cwd=product).stdout.strip()
    if head != args.product_commit.lower():
        print(f"the product moved since the build ({head[:12]}, built {args.product_commit[:12]}): "
              "nothing proposed")
        return NOTHING
    pinned = pinned_revision(product / args.manifest, args.project)
    target = args.target.lower()

    run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout", "--", args.crux_remote, str(crux)], env)
    for sha in (pinned, target):
        if run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], env, cwd=crux, check=False).returncode != 0:
            raise StageError(f"{sha} is not a commit of {scrub(args.crux_remote)}")
    own = Path(__file__).resolve().read_text()
    if own != run(["git", "show", f"{pinned}:{STAGE_SCRIPT}"], env, cwd=crux).stdout:
        raise StageError("this script is not the one at the pinned Crux revision; "
                         "the wrapper must take it from there")
    if target == pinned:
        print(f"Crux is already pinned to {pinned}")
        return NOTHING
    branch = f"refs/remotes/origin/{args.crux_branch}"
    if run(["git", "merge-base", "--is-ancestor", target, branch], env, cwd=crux, check=False).returncode != 0:
        raise StageError(f"the target {target} is not on Crux {args.crux_branch}")
    if run(["git", "merge-base", "--is-ancestor", pinned, target], env, cwd=crux, check=False).returncode != 0:
        raise StageError(f"the target {target} does not contain the pinned {pinned}: only forward moves")

    bot.mkdir()
    for name in BOT_SCRIPTS:
        (bot / name).write_text(run(["git", "show", f"{pinned}:scripts/{name}"], env, cwd=crux).stdout)
    update = [sys.executable, "-I", str(bot / "update-crux-pin.py"), "--manifest", args.manifest,
              "--to", target, "--remote-url", args.crux_remote, "--checkout", str(crux), "--no-hook",
              "--summary", str(work / "message.txt")]
    if args.project:
        update += ["--project", args.project]
    result = subprocess.run(update, cwd=product, env=env, text=True)
    if result.returncode == NOTHING:
        return NOTHING
    if result.returncode != 0:
        raise StageError(f"update-crux-pin.py failed with status {result.returncode}")
    (work / "state.json").write_text(json.dumps({"product_remote": args.product_remote}))
    return READY


def propose(args):
    work = Path(args.workdir)
    try:
        remote = json.loads((work / "state.json").read_text())["product_remote"]
    except (OSError, ValueError, KeyError):
        raise StageError("run prepare first: there is no prepared change in the workdir") from None
    secrets = {name: os.environ[name] for name in (args.token_env, args.user_env)
               if name and name in os.environ}
    cmd = [sys.executable, "-I", "-S", str(work / "bot/open-pin-pr.py"), "--host", args.host,
           "--message-file", str(work / "message.txt"), "--base", args.base, "--branch", args.branch,
           "--remote", "origin", "--push-url", remote, "--token-env", args.token_env]
    for flag, value in (("--repo", args.repo), ("--user-env", args.user_env), ("--api-url", args.api_url)):
        if value:
            cmd += [flag, value]
    for path in args.allow_path or [args.manifest]:
        cmd += ["--allow-path", path]
    for extra in args.append_body:
        cmd += ["--append-body", extra]
    status = subprocess.run(cmd, cwd=work / "product", env=env_for(args.path, secrets)).returncode
    if status == FOREIGN:
        print(f"warning: {args.branch} was not refreshed because a person pushed to it", file=sys.stderr)
        return DONE
    return DONE if status in (0, NOTHING) else ERROR


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    for name in ("prepare", "propose"):
        p = sub.add_parser(name)
        p.add_argument("--workdir", required=True, help="a directory outside any workspace; empty for prepare")
        p.add_argument("--manifest", default="west.yml", help="the product manifest (default: west.yml)")
        p.add_argument("--project", help="the Crux project (default: the project named crux or crux-pilot)")
        if name == "prepare":
            p.add_argument("--product-remote", required=True, help="the product's URL, cloned and pushed to")
            p.add_argument("--crux-remote", required=True, help="Crux's URL")
            p.add_argument("--product-commit", required=True,
                           help="the product commit the build used; main moving past it proposes nothing")
            p.add_argument("--target", required=True, help="the full SHA of the Crux commit the build verified")
            p.add_argument("--crux-branch", default="main", help="the Crux branch the target must be on")
        else:
            p.add_argument("--host", required=True, choices=("github", "bitbucket-cloud"))
            p.add_argument("--repo")
            p.add_argument("--api-url")
            p.add_argument("--base", default="main")
            p.add_argument("--branch", default="bot/crux-pin")
            p.add_argument("--token-env", default="CRUX_PIN_TOKEN", metavar="NAME")
            p.add_argument("--user-env", metavar="NAME")
            p.add_argument("--allow-path", action="append", metavar="PATH")
            p.add_argument("--append-body", action="append", default=[], metavar="FILE")
            p.add_argument("--path", default="/usr/bin:/bin", help="PATH for the push (default: /usr/bin:/bin)")
    args = parser.parse_args(argv)
    try:
        return {"prepare": prepare, "propose": propose}[args.mode](args)
    except (StageError, OSError) as error:
        print(f"crux-pin-stage: {error}", file=sys.stderr)
        return ERROR


if __name__ == "__main__":
    sys.exit(main())
