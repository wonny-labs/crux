#!/usr/bin/env python3
"""Commit the working tree's changes to one bot branch and keep one pull request open for it.

Run it in a product repository after scripts/update-crux-pin.py has changed the
manifest. It commits the changes on top of HEAD, pushes them to the bot branch
(replacing the bot's earlier commit there) and creates the pull request, or
updates the open one. It never merges and never pushes any other branch. If a
person has pushed a commit to the bot branch, it changes nothing.

Exit status: 0 the pull request is open and current, 3 nothing to propose, 4 the
bot branch holds a commit the bot did not make, 1 an error, 2 a usage error.
"""

import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

EXIT_DONE = 0
EXIT_ERROR = 1
EXIT_NOTHING = 3
EXIT_FOREIGN = 4
TRAILER = "Pin-Bot: open-pin-pr"
BOT_NAME = "Crux pin bot"
BOT_EMAIL = "crux-pin-bot@users.noreply.invalid"


class PinPrError(Exception):
    pass


def git(*args, check=True):
    result = subprocess.run(["git", *args], text=True, capture_output=True)
    if check and result.returncode != 0:
        raise PinPrError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result


def read_message(path):
    text = Path(path).read_text()
    title, _, body = text.partition("\n")
    title = title.strip()
    if not title:
        raise PinPrError(f"{path} has no title line")
    return title, body.lstrip("\n"), text.rstrip("\n")


def remote_branch_head(remote, branch):
    result = git("ls-remote", "--heads", remote, f"refs/heads/{branch}")
    line = result.stdout.strip()
    return line.split("\t", 1)[0] if line else None


def foreign_commits(remote, base, branch):
    """Commits on the bot branch, past the base, that lack the bot's trailer."""
    tracking = f"refs/pin-bot/{branch}"
    git("fetch", "-q", remote, f"+refs/heads/{branch}:{tracking}", f"+refs/heads/{base}:refs/pin-bot/base")
    shas = git("rev-list", f"refs/pin-bot/base..{tracking}").stdout.split()
    return [sha for sha in shas
            if TRAILER not in git("log", "-1", "--format=%B", sha).stdout.splitlines()]


def commit(message):
    git("add", "--all")
    identity = []
    if not git("config", "user.email", check=False).stdout.strip():
        identity = ["-c", f"user.name={BOT_NAME}", "-c", f"user.email={BOT_EMAIL}"]
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
        handle.write(f"{message}\n\n{TRAILER}\n")
    try:
        git(*identity, "commit", "-q", "--no-verify", "-F", handle.name)
    finally:
        os.unlink(handle.name)
    return git("rev-parse", "HEAD").stdout.strip()


def same_change(old_head, new_head):
    """True when the bot branch already holds this tree on this parent."""
    if old_head is None:
        return False
    old_tree = git("rev-parse", f"{old_head}^{{tree}}", check=False).stdout.strip()
    old_parent = git("rev-parse", f"{old_head}^", check=False).stdout.strip()
    return (old_tree == git("rev-parse", f"{new_head}^{{tree}}").stdout.strip()
            and old_parent == git("rev-parse", f"{new_head}^").stdout.strip())


class GitHub:
    """Pull requests through the gh command line, which reads GH_TOKEN itself."""

    def __init__(self, repo):
        self.repo = ["--repo", repo] if repo else []

    def gh(self, *args):
        result = subprocess.run(["gh", *args, *self.repo], text=True, capture_output=True)
        if result.returncode != 0:
            raise PinPrError(f"gh {' '.join(args[:2])} failed: {result.stderr.strip()}")
        return result.stdout

    def upsert(self, base, branch, title, body):
        found = json.loads(self.gh("pr", "list", "--head", branch, "--base", base, "--state", "open",
                                   "--json", "number,url") or "[]")
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
            handle.write(body)
        try:
            if found:
                number = str(found[0]["number"])
                self.gh("pr", "edit", number, "--title", title, "--body-file", handle.name)
                return "updated", found[0]["url"]
            out = self.gh("pr", "create", "--base", base, "--head", branch, "--title", title,
                          "--body-file", handle.name)
            return "created", out.strip().splitlines()[-1]
        finally:
            os.unlink(handle.name)


class BitbucketCloud:
    """Pull requests through the Bitbucket Cloud REST API 2.0."""

    def __init__(self, repo, api_url, token, user):
        if not repo or repo.count("/") != 1:
            raise PinPrError("--repo WORKSPACE/REPOSITORY is required for bitbucket-cloud")
        workspace, slug = (urllib.parse.quote(part, safe="") for part in repo.split("/"))
        self.base_url = f"{api_url.rstrip('/')}/repositories/{workspace}/{slug}/pullrequests"
        if user:
            pair = base64.b64encode(f"{user}:{token}".encode()).decode()
            self.auth = f"Basic {pair}"
        else:
            self.auth = f"Bearer {token}"

    def call(self, method, url, data=None):
        request = urllib.request.Request(url, method=method,
                                         data=json.dumps(data).encode() if data is not None else None)
        request.add_header("Authorization", self.auth)
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as error:
            try:
                detail = json.loads(error.read()).get("error", {}).get("message", "")
            except (ValueError, AttributeError):
                detail = ""
            raise PinPrError(f"Bitbucket {method} returned {error.code} {detail}".rstrip()) from None
        except urllib.error.URLError as error:
            raise PinPrError(f"Bitbucket {method} failed: {error.reason}") from None

    def upsert(self, base, branch, title, body):
        query = (f'source.branch.name="{branch}" AND destination.branch.name="{base}" '
                 f'AND state="OPEN"')
        found = self.call("GET", f"{self.base_url}?{urllib.parse.urlencode({'q': query})}").get("values", [])
        if found:
            pr = self.call("PUT", f"{self.base_url}/{found[0]['id']}",
                           {"title": title, "description": body})
            return "updated", pr["links"]["html"]["href"]
        pr = self.call("POST", self.base_url, {
            "title": title, "description": body,
            "source": {"branch": {"name": branch}},
            "destination": {"branch": {"name": base}},
            "close_source_branch": True})
        return "created", pr["links"]["html"]["href"]


def make_host(args):
    if args.host == "github":
        return GitHub(args.repo)
    token = os.environ.get(args.token_env, "")
    if not token:
        raise PinPrError(f"set the token in the environment variable {args.token_env}")
    user = os.environ.get(args.user_env, "") if args.user_env else ""
    return BitbucketCloud(args.repo, args.api_url, token, user)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", required=True, choices=("github", "bitbucket-cloud"))
    parser.add_argument("--message-file", required=True, type=Path,
                        help="commit message: the pull request title, a blank line and its text")
    parser.add_argument("--base", default="main", help="the branch the pull request targets (default: main)")
    parser.add_argument("--branch", default="bot/crux-pin", help="the bot branch (default: bot/crux-pin)")
    parser.add_argument("--remote", default="origin", help="the Git remote to push to (default: origin)")
    parser.add_argument("--repo", help="OWNER/REPO for github (default: what gh infers), "
                                       "WORKSPACE/REPOSITORY for bitbucket-cloud (required)")
    parser.add_argument("--api-url", default="https://api.bitbucket.org/2.0",
                        help="the Bitbucket Cloud API root (default: https://api.bitbucket.org/2.0)")
    parser.add_argument("--token-env", default="BITBUCKET_TOKEN", metavar="NAME",
                        help="the variable that holds the Bitbucket token (default: BITBUCKET_TOKEN)")
    parser.add_argument("--user-env", metavar="NAME",
                        help="a variable with a user name or e-mail; when set, use Basic instead of Bearer")
    args = parser.parse_args(argv)

    try:
        if args.branch in (args.base, "main", "master") or args.branch.startswith("release"):
            raise PinPrError(f"refusing to use {args.branch} as the bot branch")
        top = Path(git("rev-parse", "--show-toplevel").stdout.strip()).resolve()
        if top == args.message_file.resolve().parent or top in args.message_file.resolve().parents:
            raise PinPrError("keep --message-file outside the repository, or it is committed")
        title, body, message = read_message(args.message_file)
        host = make_host(args)  # Checks the token before anything is pushed.
        if not git("status", "--porcelain").stdout.strip():
            print("nothing to propose: the working tree is clean")
            return EXIT_NOTHING
        old_head = remote_branch_head(args.remote, args.branch)
        if old_head:
            foreign = foreign_commits(args.remote, args.base, args.branch)
            if foreign:
                print(f"open-pin-pr: {args.branch} holds commits the bot did not make "
                      f"({', '.join(sha[:12] for sha in foreign)}); merge or delete that branch first",
                      file=sys.stderr)
                return EXIT_FOREIGN
        new_head = commit(message)
        if same_change(old_head, new_head):
            print(f"{args.branch} already holds this change")
        else:
            lease = f"--force-with-lease=refs/heads/{args.branch}:{old_head or ''}"
            git("push", "-q", lease, args.remote, f"{new_head}:refs/heads/{args.branch}")
            print(f"pushed {new_head[:12]} to {args.branch}")
        action, url = host.upsert(args.base, args.branch, title, body)
        print(f"{action} {url}")
        return EXIT_DONE
    except (PinPrError, OSError) as error:
        print(f"open-pin-pr: {error}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
