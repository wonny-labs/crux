#!/usr/bin/env python3
"""Commit the working tree's changes to one bot branch and keep one pull request open for it.

Run it in a product repository after scripts/update-crux-pin.py has changed the
manifest. It commits the changes, which must lie in --allow-path, on top of HEAD, pushes them to the bot branch
(replacing the bot's earlier commit there) and creates the pull request, or
updates the open one. It never merges and never pushes any other branch. If a
person has pushed a commit to the bot branch, it changes nothing.

Exit status: 0 the pull request is open and current, 3 nothing to propose, 4 the
bot branch holds a commit the bot did not make, 1 an error, 2 a usage error.
"""

import argparse
import base64
import hashlib
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


# Set from --token-env and --user-env in main(); kept out of every Git process.
SECRET_ENV = {"CRUX_PIN_TOKEN"}


# A build that ran as the same user may have written hooks or settings that run a program.
# These keep Git from running any: no hooks, no fsmonitor and no credential helper.
SAFE_GIT = ["-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "credential.helper="]


def git(*args, check=True):
    env = {k: v for k, v in os.environ.items() if k not in SECRET_ENV}  # Git never sees the token.
    result = subprocess.run(["git", *SAFE_GIT, *args], text=True, capture_output=True, env=env)
    if check and result.returncode != 0:
        raise PinPrError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result


def git_config_sha256():
    """SHA-256 of the repository's .git/config, followed by config.worktree when there is one."""
    digest = hashlib.sha256()
    common = Path(git("rev-parse", "--git-common-dir").stdout.strip())
    digest.update((common / "config").read_bytes())
    worktree = Path(git("rev-parse", "--git-dir").stdout.strip()) / "config.worktree"
    if worktree.is_file():
        digest.update(worktree.read_bytes())
    return digest.hexdigest()


def check_git_config(expected):
    if expected and git_config_sha256() != expected.lower():
        raise PinPrError("the repository's Git configuration changed after it was recorded, "
                         "perhaps by the hook or a build; refusing to push")


def push_target(remote, push_url):
    """The URL to push to: --push-url, or the remote's url setting, never its pushurl."""
    if push_url:
        return push_url
    url = git("config", "--get", f"remote.{remote}.url", check=False).stdout.strip()
    if not url:
        raise PinPrError(f"the remote {remote} has no url; give --push-url")
    return url


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
    if git("rev-parse", "--is-shallow-repository").stdout.strip() == "true":
        # A shallow clone cannot tell an older base commit from a person's commit.
        git("fetch", "-q", "--unshallow", remote)
    git("fetch", "-q", remote, f"+refs/heads/{branch}:{tracking}", f"+refs/heads/{base}:refs/pin-bot/base")
    shas = git("rev-list", f"refs/pin-bot/base..{tracking}").stdout.split()
    return [sha for sha in shas
            if TRAILER not in git("log", "-1", "--format=%B", sha).stdout.splitlines()]


def changed_paths():
    """Every tracked change against HEAD and every untracked file, as repository paths."""
    tracked = git("diff", "--name-only", "--no-renames", "-z", "HEAD").stdout.split("\0")
    untracked = git("ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")
    return sorted({path for path in tracked + untracked if path})


def allowed(path, allow):
    entries = [os.path.normpath(entry) for entry in allow]
    return any(path == entry or path.startswith(entry + "/") for entry in entries)


def commit(message, paths):
    git("add", "--all", "--", *paths)
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
    """Pull requests through the gh command line, given the token as GH_TOKEN."""

    def __init__(self, repo, token):
        self.repo = ["--repo", repo] if repo else []
        self.env = dict(os.environ, GH_TOKEN=token) if token else None

    def gh(self, *args):
        result = subprocess.run(["gh", *args, *self.repo], text=True, capture_output=True, env=self.env)
        if result.returncode != 0:
            raise PinPrError(f"gh {' '.join(args[:2])} failed: {result.stderr.strip()}")
        return result.stdout

    def upsert(self, base, branch, title, body, refresh=True):
        found = json.loads(self.gh("pr", "list", "--head", branch, "--base", base, "--state", "open",
                                   "--json", "number,url") or "[]")
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
            handle.write(body)
        try:
            if found and not refresh:
                return "unchanged", found[0]["url"]
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
        # Never sent again to the target of a redirect.
        request.add_unredirected_header("Authorization", self.auth)
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

    def upsert(self, base, branch, title, body, refresh=True):
        query = (f'source.branch.name="{branch}" AND destination.branch.name="{base}" '
                 f'AND state="OPEN"')
        found = self.call("GET", f"{self.base_url}?{urllib.parse.urlencode({'q': query})}").get("values", [])
        if found and not refresh:
            return "unchanged", found[0]["links"]["html"]["href"]
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
    token = os.environ.get(args.token_env, "")
    if args.host == "github":
        return GitHub(args.repo, token)  # Without a token, gh uses its own login.
    parts = urllib.parse.urlsplit(args.api_url)
    if parts.scheme != "https" and parts.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise PinPrError("--api-url must use https")
    if not token:
        raise PinPrError(f"set the token in the environment variable {args.token_env}")
    user = os.environ.get(args.user_env, "") if args.user_env else ""
    return BitbucketCloud(args.repo, args.api_url, token, user)


def main(argv=None):
    # prog is fixed: crux-pin-bot.py runs this script from its source on standard input.
    parser = argparse.ArgumentParser(prog="open-pin-pr.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", required=True, choices=("github", "bitbucket-cloud"))
    parser.add_argument("--message-file", required=True, type=Path,
                        help="commit message: the pull request title, a blank line and its text")
    parser.add_argument("--base", default="main", help="the branch the pull request targets (default: main)")
    parser.add_argument("--branch", default="bot/crux-pin", help="the bot branch (default: bot/crux-pin)")
    parser.add_argument("--remote", default="origin",
                        help="the Git remote whose url setting is pushed to (default: origin); its pushurl is ignored")
    parser.add_argument("--push-url", metavar="URL", help="push to this URL instead of the --remote's url")
    parser.add_argument("--git-config-sha256", metavar="HEX",
                        help="refuse to push unless .git/config still has this SHA-256, "
                             "recorded before the hook or a build ran")
    parser.add_argument("--repo", help="OWNER/REPO for github (default: what gh infers), "
                                       "WORKSPACE/REPOSITORY for bitbucket-cloud (required)")
    parser.add_argument("--api-url", default="https://api.bitbucket.org/2.0",
                        help="the Bitbucket Cloud API root (default: https://api.bitbucket.org/2.0)")
    parser.add_argument("--token-env", default="CRUX_PIN_TOKEN", metavar="NAME",
                        help="the variable that holds the token (default: CRUX_PIN_TOKEN); "
                             "required for bitbucket-cloud, optional for github")
    parser.add_argument("--user-env", metavar="NAME",
                        help="a variable with a user name or e-mail; when set, use Basic instead of Bearer")
    parser.add_argument("--allow-path", action="append", metavar="PATH",
                        help="a file or directory, from the repository root, that the commit may change; "
                             "may repeat (default: west.yml)")
    parser.add_argument("--append-body", action="append", default=[], metavar="FILE",
                        help="add this file to the pull request text, not the commit; may repeat")
    args = parser.parse_args(argv)
    args.allow_path = args.allow_path or ["west.yml"]
    SECRET_ENV.update(name for name in (args.token_env, args.user_env) if name)

    try:
        if args.branch in (args.base, "main", "master") or args.branch.startswith("release"):
            raise PinPrError(f"refusing to use {args.branch} as the bot branch")
        top = Path(git("rev-parse", "--show-toplevel").stdout.strip()).resolve()
        if top == args.message_file.resolve().parent or top in args.message_file.resolve().parents:
            raise PinPrError("keep --message-file outside the repository, or it is committed")
        title, body, message = read_message(args.message_file)
        for extra in args.append_body:
            body = body.rstrip("\n") + "\n\n" + Path(extra).read_text().rstrip("\n") + "\n"
        os.chdir(top)  # Git paths and --allow-path are relative to the repository root.
        check_git_config(args.git_config_sha256)  # Before any Git call that could obey a changed setting.
        target = push_target(args.remote, args.push_url)
        host = make_host(args)  # Checks the token before anything is pushed.
        paths = changed_paths()
        if not paths:
            print("nothing to propose: the working tree is clean")
            return EXIT_NOTHING
        unexpected = [path for path in paths if not allowed(path, args.allow_path)]
        if unexpected:
            raise PinPrError("changes outside --allow-path, nothing committed: " + ", ".join(unexpected))
        old_head = remote_branch_head(target, args.branch)
        if old_head:
            foreign = foreign_commits(target, args.base, args.branch)
            if foreign:
                print(f"open-pin-pr: {args.branch} holds commits the bot did not make "
                      f"({', '.join(sha[:12] for sha in foreign)}); merge or delete that branch first",
                      file=sys.stderr)
                return EXIT_FOREIGN
        new_head = commit(message, paths)
        refresh = not same_change(old_head, new_head)
        if not refresh:
            print(f"{args.branch} already holds this change")
        else:
            check_git_config(args.git_config_sha256)
            lease = f"--force-with-lease=refs/heads/{args.branch}:{old_head or ''}"
            git("push", "-q", lease, target, f"{new_head}:refs/heads/{args.branch}")
            print(f"pushed {new_head[:12]} to {args.branch}")
        action, url = host.upsert(args.base, args.branch, title, body, refresh)
        print(f"{action} {url}")
        return EXIT_DONE
    except (PinPrError, OSError) as error:
        print(f"open-pin-pr: {error}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
