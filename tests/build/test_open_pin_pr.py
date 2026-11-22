"""Check scripts/open-pin-pr.py with throwaway Git remotes, a fake gh and a local fake Bitbucket API."""
import http.server
import json
import os
from pathlib import Path
import shutil
import socketserver
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/open-pin-pr.py"
GIT = shutil.which("git")

DONE, NOTHING, FOREIGN = 0, 3, 4
TOKEN = "s3cret-token-value"
BRANCH = "bot/crux-pin"

FAKE_GH = r'''#!/usr/bin/env python3
"""Enough of gh pr list/create/edit for the tests, with state in a JSON file."""
import json, os, sys
state_path = os.environ["FAKE_GH_STATE"]
state = json.load(open(state_path)) if os.path.exists(state_path) else {"prs": [], "calls": []}
args = sys.argv[1:]
state["calls"].append(args)
def opt(name):
    return args[args.index(name) + 1] if name in args else None
if args[:2] == ["pr", "list"]:
    prs = [p for p in state["prs"] if p["head"] == opt("--head") and p["base"] == opt("--base")
           and p["state"] == "OPEN"]
    print(json.dumps([{"number": p["number"], "url": p["url"]} for p in prs]))
elif args[:2] == ["pr", "create"]:
    number = len(state["prs"]) + 1
    url = f"https://github.example/o/r/pull/{number}"
    state["prs"].append({"number": number, "url": url, "head": opt("--head"), "base": opt("--base"),
                         "title": opt("--title"), "body": open(opt("--body-file")).read(),
                         "state": "OPEN"})
    print(url)
elif args[:2] == ["pr", "edit"]:
    pr = next(p for p in state["prs"] if p["number"] == int(args[2]))
    pr["title"] = opt("--title")
    pr["body"] = open(opt("--body-file")).read()
    print(pr["url"])
else:
    sys.exit(f"fake gh: unsupported {args}")
json.dump(state, open(state_path, "w"))
'''


def git(*args, cwd=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, text=True,
                          capture_output=True).stdout.strip()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.origin = self.tmp / "origin.git"
        git("init", "-q", "--bare", "-b", "main", str(self.origin))
        seed = self.tmp / "seed"
        git("clone", "-q", str(self.origin), str(seed))
        (seed / "west.yml").write_text("revision: aaaa\n")
        git("add", ".", cwd=seed)
        git("commit", "-q", "-m", "feat: start", cwd=seed)
        git("push", "-q", "origin", "HEAD:main", cwd=seed)
        self.main = git("rev-parse", "HEAD", cwd=seed)
        self.work = self.tmp / "work"
        git("clone", "-q", str(self.origin), str(self.work))
        self.message = self.tmp / "message.txt"

    def change(self, revision):
        # Each CI run starts from a fresh checkout of the base branch.
        git("fetch", "-q", "origin", cwd=self.work)
        git("checkout", "-q", "-f", "-B", "main", "origin/main", cwd=self.work)
        (self.work / "west.yml").write_text(f"revision: {revision}\n")
        self.message.write_text(f"build(deps): move the Crux pin to {revision}\n\nLog for {revision}.\n")

    def run_script(self, *args, env=None):
        full_env = dict(os.environ, **(env or {}))
        return subprocess.run([sys.executable, str(SCRIPT), "--message-file", str(self.message), *args],
                              cwd=self.work, text=True, capture_output=True, env=full_env)

    def remote_ref(self, ref):
        result = subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=self.origin,
                                text=True, capture_output=True)
        return result.stdout.strip() or None

    def remote_file(self, ref, path="west.yml"):
        return git("show", f"{ref}:{path}", cwd=self.origin)


@unittest.skipUnless(GIT, "git is required")
class GitHubTest(Base):
    def setUp(self):
        super().setUp()
        bindir = self.tmp / "bin"
        bindir.mkdir()
        gh = bindir / "gh"
        gh.write_text(FAKE_GH.replace("/usr/bin/env python3", sys.executable, 1))
        gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
        self.state = self.tmp / "gh.json"
        self.env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "FAKE_GH_STATE": str(self.state)}

    def gh(self):
        return json.loads(self.state.read_text())

    def test_first_run_pushes_the_bot_branch_and_opens_one_pr(self):
        self.change("bbbb")
        result = self.run_script("--host", "github", env=self.env)
        self.assertEqual(DONE, result.returncode, result.stderr)
        prs = self.gh()["prs"]
        self.assertEqual(1, len(prs))
        self.assertEqual((BRANCH, "main"), (prs[0]["head"], prs[0]["base"]))
        self.assertEqual("build(deps): move the Crux pin to bbbb", prs[0]["title"])
        self.assertEqual("Log for bbbb.\n", prs[0]["body"])
        self.assertIn(prs[0]["url"], result.stdout)
        self.assertEqual("revision: bbbb", self.remote_file(BRANCH))
        self.assertEqual(self.main, self.remote_ref("main"))
        message = git("log", "-1", "--format=%B", BRANCH, cwd=self.origin)
        self.assertIn("Pin-Bot: open-pin-pr", message)

    def test_a_later_run_updates_the_same_pr_and_rebuilds_the_branch(self):
        self.change("bbbb")
        self.assertEqual(DONE, self.run_script("--host", "github", env=self.env).returncode)
        self.change("cccc")
        result = self.run_script("--host", "github", env=self.env)
        self.assertEqual(DONE, result.returncode, result.stderr)
        prs = self.gh()["prs"]
        self.assertEqual(1, len(prs))
        self.assertEqual("build(deps): move the Crux pin to cccc", prs[0]["title"])
        self.assertEqual("revision: cccc", self.remote_file(BRANCH))
        # One bot commit on top of main, not a growing stack.
        self.assertEqual(self.main, self.remote_ref(f"{BRANCH}~1"))
        self.assertEqual(self.main, self.remote_ref("main"))

    def test_the_same_change_again_pushes_nothing(self):
        self.change("bbbb")
        self.assertEqual(DONE, self.run_script("--host", "github", env=self.env).returncode)
        head = self.remote_ref(BRANCH)
        self.change("bbbb")
        result = self.run_script("--host", "github", env=self.env)
        self.assertEqual(DONE, result.returncode, result.stderr)
        self.assertEqual(head, self.remote_ref(BRANCH))
        self.assertEqual(1, len(self.gh()["prs"]))

    def test_a_clean_tree_proposes_nothing(self):
        self.change("aaaa")
        result = self.run_script("--host", "github", env=self.env)
        self.assertEqual(NOTHING, result.returncode, result.stderr)
        self.assertIsNone(self.remote_ref(BRANCH))
        self.assertFalse(self.state.exists())

    def test_a_bot_branch_with_a_persons_commit_is_left_alone(self):
        self.change("bbbb")
        self.assertEqual(DONE, self.run_script("--host", "github", env=self.env).returncode)
        person = self.tmp / "person"
        git("clone", "-q", "-b", BRANCH, str(self.origin), str(person))
        (person / "fix.txt").write_text("hand fix\n")
        git("add", ".", cwd=person)
        git("commit", "-q", "-m", "fix: adapt the product", cwd=person)
        git("push", "-q", "origin", BRANCH, cwd=person)
        head = self.remote_ref(BRANCH)
        self.change("cccc")
        result = self.run_script("--host", "github", env=self.env)
        self.assertEqual(FOREIGN, result.returncode, result.stderr)
        self.assertEqual(head, self.remote_ref(BRANCH))

    def test_a_message_file_inside_the_repository_is_refused(self):
        self.change("bbbb")
        self.message = self.work / "pin.txt"
        self.message.write_text("build(deps): move\n\nbody\n")
        result = self.run_script("--host", "github", env=self.env)
        self.assertNotIn(result.returncode, (DONE, NOTHING, FOREIGN))
        self.assertIn("outside", result.stderr)
        self.assertIsNone(self.remote_ref(BRANCH))

    def test_the_branch_may_not_be_the_base(self):
        self.change("bbbb")
        result = self.run_script("--host", "github", "--branch", "main", env=self.env)
        self.assertNotIn(result.returncode, (DONE, NOTHING, FOREIGN))
        self.assertEqual(self.main, self.remote_ref("main"))


class FakeBitbucket(http.server.BaseHTTPRequestHandler):
    """A small part of the Bitbucket Cloud 2.0 pull request API."""
    server_version = "fake"

    def log_message(self, *args):
        pass

    def reply(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def record(self):
        """Record the call; answer 401 and return False for a wrong token."""
        length = int(self.headers.get("Content-Length") or 0)
        self.body = json.loads(self.rfile.read(length)) if length else None
        self.server.calls.append({"method": self.command, "path": self.path,
                                  "auth": self.headers.get("Authorization"), "body": self.body})
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self.reply(401, {"type": "error", "error": {"message": "Unauthorized"}})
            return False
        return True

    def do_GET(self):
        if not self.record():
            return
        url = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(url.query).get("q", [""])[0]
        prs = [p for p in self.server.prs
               if f'source.branch.name="{p["source"]["branch"]["name"]}"' in query
               and f'destination.branch.name="{p["destination"]["branch"]["name"]}"' in query
               and 'state="OPEN"' in query]
        self.reply(200, {"values": prs})

    def do_POST(self):
        if not self.record():
            return
        body = self.body
        number = len(self.server.prs) + 1
        pr = dict(body, id=number, state="OPEN",
                  links={"html": {"href": f"https://bitbucket.example/ws/repo/pull-requests/{number}"}})
        self.server.prs.append(pr)
        self.reply(201, pr)

    def do_PUT(self):
        if not self.record():
            return
        body = self.body
        number = int(self.path.rstrip("/").rsplit("/", 1)[1])
        pr = self.server.prs[number - 1]
        pr.update(body)
        self.reply(200, pr)


class LocalServer(http.server.HTTPServer):
    def server_bind(self):
        # HTTPServer looks up the host's full name, which can take seconds; it is not needed.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


@unittest.skipUnless(GIT, "git is required")
class BitbucketCloudTest(Base):
    def setUp(self):
        super().setUp()
        self.server = LocalServer(("127.0.0.1", 0), FakeBitbucket)
        self.server.calls, self.server.prs = [], []
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.api = f"http://127.0.0.1:{self.server.server_port}/2.0"

    def run_bitbucket(self, env=None):
        return self.run_script("--host", "bitbucket-cloud", "--repo", "ws/repo", "--api-url", self.api,
                               env=env if env is not None else {"BITBUCKET_TOKEN": TOKEN})

    def test_creates_then_updates_one_pr_and_never_prints_the_token(self):
        self.change("bbbb")
        first = self.run_bitbucket()
        self.assertEqual(DONE, first.returncode, first.stderr)
        self.change("cccc")
        second = self.run_bitbucket()
        self.assertEqual(DONE, second.returncode, second.stderr)
        self.assertEqual(1, len(self.server.prs))
        pr = self.server.prs[0]
        self.assertEqual(BRANCH, pr["source"]["branch"]["name"])
        self.assertEqual("main", pr["destination"]["branch"]["name"])
        self.assertEqual("build(deps): move the Crux pin to cccc", pr["title"])
        self.assertEqual("Log for cccc.\n", pr["description"])
        methods = [c["method"] for c in self.server.calls]
        self.assertEqual(["GET", "POST", "GET", "PUT"], methods)
        self.assertTrue(all(c["path"].startswith("/2.0/repositories/ws/repo/pullrequests")
                            for c in self.server.calls))
        for result in (first, second):
            self.assertNotIn(TOKEN, result.stdout + result.stderr)
        self.assertIn("pull-requests/1", second.stdout)
        self.assertEqual("revision: cccc", self.remote_file(BRANCH))

    def test_a_missing_token_fails_before_any_push_or_request(self):
        self.change("bbbb")
        result = self.run_bitbucket(env={"BITBUCKET_TOKEN": ""})
        self.assertNotIn(result.returncode, (DONE, NOTHING, FOREIGN))
        self.assertIn("BITBUCKET_TOKEN", result.stderr)
        self.assertEqual([], self.server.calls)
        self.assertIsNone(self.remote_ref(BRANCH))

    def test_a_rejected_token_is_reported_without_the_token(self):
        self.change("bbbb")
        result = self.run_bitbucket(env={"BITBUCKET_TOKEN": "wrong-" + TOKEN})
        self.assertNotIn(result.returncode, (DONE, NOTHING, FOREIGN))
        self.assertIn("401", result.stderr)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
