"""Check scripts/crux-pin-bot.py end to end: a fake Crux remote, a product remote and a fake gh."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from test_open_pin_pr import FAKE_GH, git

try:
    import yaml
except ImportError:  # west installs PyYAML; skip where it is missing.
    yaml = None

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/crux-pin-bot.py"
GIT = shutil.which("git")
BRANCH = "bot/crux-pin"

MANIFEST = """\
manifest:
  projects:
    - name: crux
      url: {url}
      revision: {revision}
  self:
    path: product-x
"""


@unittest.skipUnless(GIT, "git is required")
@unittest.skipUnless(yaml, "PyYAML is required; west installs it")
class CruxPinBotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.crux = self.tmp / "crux"
        self.crux.mkdir()
        git("init", "-q", "-b", "main", cwd=self.crux)
        self.old = self.commit_crux("feat: old")
        self.new = self.commit_crux("feat: new")
        self.origin = self.tmp / "product.git"
        git("init", "-q", "--bare", "-b", "main", str(self.origin))
        self.work = self.tmp / "product-x"
        git("clone", "-q", str(self.origin), str(self.work))
        (self.work / "west.yml").write_text(MANIFEST.format(url=self.crux.as_uri(), revision=self.old))
        git("add", ".", cwd=self.work)
        git("commit", "-q", "-m", "feat: start", cwd=self.work)
        git("push", "-q", "origin", "HEAD:main", cwd=self.work)
        bindir = self.tmp / "bin"
        bindir.mkdir()
        gh = bindir / "gh"
        gh.write_text(FAKE_GH.replace("/usr/bin/env python3", sys.executable, 1))
        gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
        self.state = self.tmp / "gh.json"
        self.env = dict(os.environ, PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}",
                        FAKE_GH_STATE=str(self.state))

    def commit_crux(self, subject):
        (self.crux / "f.txt").write_text(subject)
        git("add", ".", cwd=self.crux)
        git("commit", "-q", "-m", subject, cwd=self.crux)
        return git("rev-parse", "HEAD", cwd=self.crux)

    def run_bot(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--host", "github", *args], cwd=self.work,
                              text=True, capture_output=True, env=self.env)

    def test_opens_one_pr_with_the_log_and_appended_evidence_then_stops_when_current(self):
        evidence = self.tmp / "evidence.md"
        evidence.write_text("## Evidence\n\nimage sha256: 00ff\n")
        result = self.run_bot("--append-body", str(evidence))
        self.assertEqual(0, result.returncode, result.stderr)
        prs = json.loads(self.state.read_text())["prs"]
        self.assertEqual(1, len(prs))
        self.assertIn(self.new[:12], prs[0]["title"])
        self.assertIn("feat: new", prs[0]["body"])
        self.assertTrue(prs[0]["body"].rstrip().endswith("image sha256: 00ff"))
        message = git("log", "-1", "--format=%B", BRANCH, cwd=self.origin)
        self.assertIn("feat: new", message)
        self.assertNotIn("image sha256", message)  # Evidence goes to the pull request only.
        pinned = git("show", f"{BRANCH}:west.yml", cwd=self.origin)
        self.assertIn(f"revision: {self.new}", pinned)

        # The product merges; the next run finds the pin current and changes nothing.
        git("update-ref", "refs/heads/main", f"refs/heads/{BRANCH}", cwd=self.origin)
        git("fetch", "-q", "origin", cwd=self.work)
        git("checkout", "-q", "-f", "-B", "main", "origin/main", cwd=self.work)
        result = self.run_bot()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("already pinned", result.stdout)
        self.assertEqual(1, len(json.loads(self.state.read_text())["prs"]))

    def test_no_git_process_and_no_product_hook_sees_the_token(self):
        # A probe in front of git records each call's arguments and whether the secrets are set.
        real = shutil.which("git", path=os.environ["PATH"])
        probe_log = self.tmp / "git-calls.log"
        bindir = self.tmp / "bin"
        probe = bindir / "git"
        probe.write_text(f"""#!/bin/sh
printf '%s|%s|%s\\n' "${{CRUX_PIN_TOKEN:+token}}" "${{PIN_USER:+user}}" "$*" >> "{probe_log}"
exec "{real}" "$@"
""")
        probe.chmod(probe.stat().st_mode | stat.S_IXUSR)
        hook = self.work / "scripts/crux-pin-hook"
        hook.parent.mkdir()
        hook.write_text(f'#!/bin/sh\necho "[$CRUX_PIN_TOKEN][$PIN_USER]" > "{self.tmp / "hook.out"}"\n')
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
        git("add", ".", cwd=self.work)
        git("commit", "-q", "-m", "feat: hook", cwd=self.work)
        git("push", "-q", "origin", "HEAD:main", cwd=self.work)
        self.env.update(CRUX_PIN_TOKEN="s3cret", PIN_USER="bot@example.invalid")
        result = self.run_bot("--user-env", "PIN_USER")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("[][]", (self.tmp / "hook.out").read_text().strip())
        calls = probe_log.read_text().splitlines()
        self.assertTrue(calls)
        for call in calls:
            self.assertTrue(call.startswith("||"), call)
            self.assertIn("core.hooksPath=/dev/null", call, call)

    def test_an_error_in_the_updater_fails_the_run(self):
        result = self.run_bot("--to", "no-such-ref")
        self.assertEqual(1, result.returncode)
        self.assertFalse(self.state.exists())


if __name__ == "__main__":
    unittest.main()
