#!/usr/bin/env python3
"""Move a product's Crux pin and keep one pull request open for it, in one command.

Run it from the product repository, in CI. It runs update-crux-pin.py, adds any
--append-body files to the pull request text, and runs open-pin-pr.py when the
pin moved. Both scripts sit next to this one.

Exit status: 0 the pull request is open and current, the pin is already
current, or a person's commit on the bot branch kept it from being refreshed
(a warning says so); 1 an error; 2 a usage error.
"""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CURRENT, NOTHING, FOREIGN = 3, 3, 4


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
    parser.add_argument("--token-env", default="CRUX_PIN_TOKEN", metavar="NAME",
                        help="the variable that holds the token (default: CRUX_PIN_TOKEN)")
    parser.add_argument("--user-env", metavar="NAME", help="as for open-pin-pr.py")
    parser.add_argument("--api-url", help="as for open-pin-pr.py")
    args = parser.parse_args(argv)

    temp = tempfile.mkdtemp(prefix="crux-pin-")  # Outside the repository, so it is not committed.
    try:
        message = Path(temp) / "message.txt"
        update = [sys.executable, str(HERE / "update-crux-pin.py"), "--manifest", args.manifest,
                  "--branch", args.crux_branch, "--summary", str(message)]
        for flag, value in (("--project", args.project), ("--to", args.to), ("--remote-url", args.remote_url)):
            if value:
                update += [flag, value]
        if args.no_hook:
            update.append("--no-hook")
        status = subprocess.run(update).returncode
        if status == CURRENT:
            return 0
        if status != 0:
            return 1
        with message.open("a") as out:
            for extra in args.append_body:
                out.write("\n" + Path(extra).read_text().rstrip("\n") + "\n")

        open_pr = [sys.executable, str(HERE / "open-pin-pr.py"), "--host", args.host,
                   "--message-file", str(message), "--base", args.base, "--branch", args.branch,
                   "--remote", args.remote, "--token-env", args.token_env]
        for flag, value in (("--repo", args.repo), ("--user-env", args.user_env), ("--api-url", args.api_url)):
            if value:
                open_pr += [flag, value]
        status = subprocess.run(open_pr).returncode
        if status == FOREIGN:
            print(f"warning: {args.branch} was not refreshed because a person pushed to it", file=sys.stderr)
            return 0
        return 0 if status in (0, NOTHING) else 1
    except OSError as error:
        print(f"crux-pin-bot: {error}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
