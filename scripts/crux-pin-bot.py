#!/usr/bin/env python3
"""Move a product's Crux pin and keep one pull request open for it, in one command.

Run it from the product repository, in CI. It runs update-crux-pin.py, adds any
--append-body files to the pull request text, and runs open-pin-pr.py when the
pin moved. Both scripts sit next to this one.

Only open-pin-pr.py gets the token's variable. The updater and the product hook
run without it and without the --user-env variable. open-pin-pr.py runs from the
copy read before the hook, and refuses to push if .git/config changed. This
process and the CI step still hold the token while the hook runs, so a hook that
builds or runs anything from the new Crux belongs in a job without the token:
see "Keeping the Crux pin current" in docs/product-composition.md.

Exit status: 0 the pull request is open and current, the pin is already
current, or a person's commit on the bot branch kept it from being refreshed
(a warning says so); 1 an error; 2 a usage error.
"""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CURRENT, NOTHING, FOREIGN = 3, 3, 4
SAFE_GIT = ["-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "credential.helper="]


def git_config_sha256(env):
    """As open-pin-pr.py computes it: .git/config, then config.worktree when there is one."""
    def rev_parse(flag):
        return Path(subprocess.run(["git", *SAFE_GIT, "rev-parse", flag], text=True, capture_output=True,
                                   env=env, check=True).stdout.strip())
    digest = hashlib.sha256((rev_parse("--git-common-dir") / "config").read_bytes())
    worktree = rev_parse("--git-dir") / "config.worktree"
    if worktree.is_file():
        digest.update(worktree.read_bytes())
    return digest.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", required=True, choices=("github", "bitbucket-cloud"))
    parser.add_argument("--repo", help="OWNER/REPO or WORKSPACE/REPOSITORY, as for open-pin-pr.py")
    parser.add_argument("--manifest", default="west.yml", help="the product manifest (default: west.yml)")
    parser.add_argument("--project", help="the Crux project (default: the project named crux or crux-pilot)")
    parser.add_argument("--to", metavar="REV", help="a full SHA, branch or tag of Crux (default: head of main)")
    parser.add_argument("--crux-branch", default="main", help="the Crux branch to follow (default: main)")
    parser.add_argument("--remote-url", help="fetch Crux from this URL, such as a mirror")
    parser.add_argument("--append-body", action="append", default=[], metavar="FILE",
                        help="add this file to the pull request text, such as evidence; may repeat")
    parser.add_argument("--no-hook", action="store_true", help="do not run scripts/crux-pin-hook")
    parser.add_argument("--base", default="main", help="the product branch to target (default: main)")
    parser.add_argument("--branch", default="bot/crux-pin", help="the bot branch (default: bot/crux-pin)")
    parser.add_argument("--remote", default="origin", help="the product remote (default: origin)")
    parser.add_argument("--push-url", metavar="URL", help="as for open-pin-pr.py")
    parser.add_argument("--token-env", default="CRUX_PIN_TOKEN", metavar="NAME",
                        help="the variable that holds the token (default: CRUX_PIN_TOKEN)")
    parser.add_argument("--user-env", metavar="NAME", help="as for open-pin-pr.py")
    parser.add_argument("--api-url", help="as for open-pin-pr.py")
    parser.add_argument("--allow-path", action="append", metavar="PATH",
                        help="a file or directory the commit may change; may repeat (default: --manifest)")
    args = parser.parse_args(argv)

    secrets = {name for name in (args.token_env, args.user_env) if name}
    clean = {k: v for k, v in os.environ.items() if k not in secrets}
    temp = tempfile.mkdtemp(prefix="crux-pin-")  # Outside the repository, so it is not committed.
    try:
        # Read now: a hook that runs west update moves this checkout, these scripts included.
        open_pr_source = (HERE / "open-pin-pr.py").read_text()
        config_sha256 = git_config_sha256(clean)
        message = Path(temp) / "message.txt"
        update = [sys.executable, str(HERE / "update-crux-pin.py"), "--manifest", args.manifest,
                  "--branch", args.crux_branch, "--summary", str(message)]
        for flag, value in (("--project", args.project), ("--to", args.to), ("--remote-url", args.remote_url)):
            if value:
                update += [flag, value]
        if args.no_hook:
            update.append("--no-hook")
        update += ["--token-env", args.token_env] + (["--user-env", args.user_env] if args.user_env else [])
        status = subprocess.run(update, env=clean).returncode
        if status == CURRENT:
            return 0
        if status != 0:
            return 1
        # -I: no PYTHON* variables, user site or current directory on the path.
        open_pr = [sys.executable, "-I", "-", "--host", args.host,
                   "--message-file", str(message), "--base", args.base, "--branch", args.branch,
                   "--remote", args.remote, "--token-env", args.token_env,
                   "--git-config-sha256", config_sha256]
        for flag, value in (("--repo", args.repo), ("--user-env", args.user_env), ("--api-url", args.api_url),
                            ("--push-url", args.push_url)):
            if value:
                open_pr += [flag, value]
        for extra in args.append_body:
            open_pr += ["--append-body", extra]
        for path in args.allow_path or [args.manifest]:
            open_pr += ["--allow-path", path]
        status = subprocess.run(open_pr, input=open_pr_source, text=True).returncode
        if status == FOREIGN:
            print(f"warning: {args.branch} was not refreshed because a person pushed to it", file=sys.stderr)
            return 0
        return 0 if status in (0, NOTHING) else 1
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"crux-pin-bot: {error}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
