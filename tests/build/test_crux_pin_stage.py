"""Check scripts/crux-pin-stage.py: the token stage that builds the pin change from fresh clones.

A fake Crux remote, a product remote and a local fake Bitbucket API stand in for the real ones.
"""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

from test_open_pin_pr import FakeBitbucket, LocalServer, TOKEN, git

try:
    import yaml  # noqa: F401
except ImportError:  # west installs PyYAML; skip where it is missing.
    yaml = None

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
STAGE = SCRIPTS / "crux-pin-stage.py"
GIT = shutil.which("git")
BRANCH = "bot/crux-pin"
READY, ERROR, NOTHING = 0, 1, 3

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
class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.crux = self.tmp / "crux.git"
        seed = self.tmp / "crux-seed"
        git("init", "-q", "-b", "main", str(seed))
        (seed / "scripts").mkdir()
        for name in ("crux-pin-stage.py", "update-crux-pin.py", "open-pin-pr.py"):
            if (SCRIPTS / name).exists():
                shutil.copy2(SCRIPTS / name, seed / "scripts" / name)
        self.seed = seed
        self.old = self.commit_crux("feat: old")
        self.new = self.commit_crux("feat: new")
        git("clone", "-q", "--bare", str(seed), str(self.crux))
        self.product = self.tmp / "product.git"
        git("init", "-q", "--bare", "-b", "main", str(self.product))
        work = self.tmp / "product-seed"
        git("clone", "-q", str(self.product), str(work))
        (work / "west.yml").write_text(MANIFEST.format(url=self.crux.as_uri(), revision=self.old))
        git("add", ".", cwd=work)
        git("commit", "-q", "-m", "feat: start", cwd=work)
        git("push", "-q", "origin", "HEAD:main", cwd=work)
        self.product_head = git("rev-parse", "HEAD", cwd=work)
        self.work = self.tmp / "stage"
        self.home = self.tmp / "home"
        self.home.mkdir()

    def commit_crux(self, subject, files=None):
        (self.seed / "f.txt").write_text(subject)
        for name, text in (files or {}).items():
            (self.seed / name).write_text(text)
        git("add", ".", cwd=self.seed)
        git("commit", "-q", "-m", subject, cwd=self.seed)
        return git("rev-parse", "HEAD", cwd=self.seed)

    def publish_crux(self):
        git("push", "-q", "--force", str(self.crux), "main:main", cwd=self.seed)

    def stage_copy(self, rev=None):
        """The stage script as the wrapper takes it: from Crux at one revision."""
        target = self.tmp / "stage-copy.py"
        target.write_text(self.show(rev or self.old, "scripts/crux-pin-stage.py"))
        return target

    def show(self, rev, path):
        """A file at a revision, byte for byte (the git helper strips the last newline)."""
        return subprocess.run(["git", "show", f"{rev}:{path}"], cwd=self.seed, text=True, check=True,
                              capture_output=True).stdout

    def env(self, **extra):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home)}
        env.update(extra)
        return env

    def run_stage(self, mode, *args, script=None, env=None):
        return subprocess.run([sys.executable, "-I", str(script or self.stage_copy()), mode,
                               "--workdir", str(self.work), *args],
                              text=True, capture_output=True, env=env or self.env())

    def prepare(self, target=None, product_commit=None, **kwargs):
        return self.run_stage("prepare", "--product-remote", self.product.as_uri(),
                              "--crux-remote", self.crux.as_uri(),
                              "--product-commit", product_commit or self.product_head,
                              "--target", target or self.new, **kwargs)


@unittest.skipUnless(GIT, "git is required")
@unittest.skipUnless(yaml, "PyYAML is required; west installs it")
class PrepareTest(Base):
    def test_prepare_moves_the_pin_in_a_fresh_clone_and_writes_the_text(self):
        result = self.prepare()
        self.assertEqual(READY, result.returncode, result.stderr)
        self.assertIn(self.new, (self.work / "product/west.yml").read_text())
        message = (self.work / "message.txt").read_text()
        self.assertIn(self.new[:12], message.splitlines()[0])
        self.assertIn("feat: new", message)

    def test_the_bot_scripts_come_from_the_pinned_revision_not_the_target(self):
        poisoned = self.commit_crux("feat: poisoned", {"scripts/open-pin-pr.py": "raise SystemExit('target')\n"})
        self.publish_crux()
        result = self.prepare(target=poisoned)
        self.assertEqual(READY, result.returncode, result.stderr)
        pinned = self.show(self.old, "scripts/open-pin-pr.py")
        self.assertEqual(pinned, (self.work / "bot/open-pin-pr.py").read_text())

    def test_a_stage_script_that_is_not_the_pinned_one_is_refused(self):
        copy = self.stage_copy()
        copy.write_text(copy.read_text() + "\n# local edit\n")
        result = self.prepare(script=copy)
        self.assertEqual(ERROR, result.returncode)
        self.assertIn("pinned", result.stderr)

    def test_a_product_that_moved_since_the_build_proposes_nothing(self):
        result = self.prepare(product_commit="0" * 40)
        self.assertEqual(NOTHING, result.returncode, result.stderr)

    def test_a_current_pin_proposes_nothing(self):
        result = self.prepare(target=self.old)
        self.assertEqual(NOTHING, result.returncode, result.stderr)

    def test_an_older_target_is_refused(self):
        # The pin is on the newer commit; a build may not pick the older one.
        work = self.tmp / "product-seed"
        (work / "west.yml").write_text(MANIFEST.format(url=self.crux.as_uri(), revision=self.new))
        git("commit", "-q", "-am", "feat: pin new", cwd=work)
        git("push", "-q", "origin", "HEAD:main", cwd=work)
        head = git("rev-parse", "HEAD", cwd=work)
        result = self.prepare(target=self.old, product_commit=head, script=self.stage_copy(self.new))
        self.assertEqual(ERROR, result.returncode)
        self.assertIn("forward", result.stderr)

    def test_a_target_that_is_not_on_crux_main_is_refused(self):
        git("checkout", "-q", "-b", "side", cwd=self.seed)
        side = self.commit_crux("feat: side")
        git("push", "-q", str(self.crux), "side:side", cwd=self.seed)
        git("checkout", "-q", "main", cwd=self.seed)
        result = self.prepare(target=side)
        self.assertEqual(ERROR, result.returncode)
        self.assertIn("main", result.stderr)

    def test_a_malformed_target_is_refused(self):
        result = self.prepare(target="main")
        self.assertEqual(ERROR, result.returncode)

    def test_git_ignores_the_global_and_system_configuration(self):
        # The user's configuration would redirect the product remote to an empty repository.
        empty = self.tmp / "empty.git"
        git("init", "-q", "--bare", str(empty))
        (self.home / ".gitconfig").write_text(f'[url "{empty.as_uri()}"]\n\tinsteadOf = {self.product.as_uri()}\n')
        result = self.prepare()
        self.assertEqual(READY, result.returncode, result.stderr)


@unittest.skipUnless(GIT, "git is required")
@unittest.skipUnless(yaml, "PyYAML is required; west installs it")
class ProposeTest(Base):
    def setUp(self):
        super().setUp()
        self.server = LocalServer(("127.0.0.1", 0), FakeBitbucket)
        self.server.calls, self.server.prs = [], []
        self.server.accepted = {f"Bearer {TOKEN}"}
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.api = f"http://127.0.0.1:{self.server.server_port}/2.0"

    def propose(self, *extra, env=None):
        return self.run_stage("propose", "--host", "bitbucket-cloud", "--repo", "ws/repo",
                              "--api-url", self.api, *extra,
                              env=env or self.env(CRUX_PIN_TOKEN=TOKEN))

    def remote_head(self, ref):
        return subprocess.run(["git", "rev-parse", "--verify", "-q", ref], cwd=self.product,
                              text=True, capture_output=True).stdout.strip()

    def test_it_pushes_one_commit_with_only_the_manifest_and_opens_the_pr(self):
        self.assertEqual(READY, self.prepare().returncode)
        result = self.propose()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        files = git("diff", "--name-only", "--no-renames", f"main..{BRANCH}", cwd=self.product).split()
        self.assertEqual(["west.yml"], files)
        self.assertEqual(self.product_head, git("rev-parse", f"{BRANCH}^", cwd=self.product))
        self.assertEqual(1, len(self.server.prs))
        self.assertIn(self.new[:12], self.server.prs[0]["title"])

    def test_the_push_ignores_user_configuration_that_redirects_the_product_url(self):
        # A clone's origin url is the one pushed to, whatever the user's configuration says.
        empty = self.tmp / "empty.git"
        git("init", "-q", "--bare", str(empty))
        self.assertEqual(READY, self.prepare().returncode)
        (self.home / ".gitconfig").write_text(f'[url "{empty.as_uri()}"]\n\tinsteadOf = {self.product.as_uri()}\n')
        result = self.propose()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(self.remote_head(BRANCH))
        self.assertFalse(subprocess.run(["git", "rev-parse", "--verify", "-q", BRANCH], cwd=empty).returncode == 0)

    def test_only_open_pin_pr_sees_the_token_and_it_runs_isolated(self):
        self.assertEqual(READY, self.prepare().returncode)
        seen = self.tmp / "seen.json"
        (self.work / "bot/open-pin-pr.py").write_text(
            "import json, os, sys\n"
            f"json.dump({{'argv': sys.argv, 'env': dict(os.environ), 'flags': sys.flags.isolated, "
            f"'nosite': sys.flags.no_site}}, open({str(seen)!r}, 'w'))\n")
        result = self.propose(env=self.env(CRUX_PIN_TOKEN=TOKEN, PYTHONPATH=str(self.tmp), GIT_SSH_COMMAND="evil"))
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads(seen.read_text())
        self.assertEqual(1, data["flags"])
        self.assertEqual(1, data["nosite"])
        self.assertEqual(TOKEN, data["env"]["CRUX_PIN_TOKEN"])
        self.assertEqual("/usr/bin:/bin", data["env"]["PATH"])
        self.assertNotIn("PYTHONPATH", data["env"])
        self.assertEqual("1", data["env"]["GIT_CONFIG_NOSYSTEM"])
        self.assertEqual("/dev/null", data["env"]["GIT_CONFIG_GLOBAL"])
        self.assertEqual("ssh -F /dev/null", data["env"]["GIT_SSH_COMMAND"])
        self.assertEqual(self.product.as_uri(), data["argv"][data["argv"].index("--push-url") + 1])
        self.assertIn("--message-file", data["argv"])

    def test_propose_without_prepare_fails(self):
        result = self.propose()
        self.assertEqual(ERROR, result.returncode)
        self.assertEqual([], self.server.prs)

    def test_a_workdir_that_is_not_empty_is_refused(self):
        # A workdir that already holds files is refused: the stage starts from nothing.
        self.work.mkdir()
        (self.work / "leftover").write_text("x")
        result = self.prepare()
        self.assertEqual(ERROR, result.returncode)
        self.assertIn("empty", result.stderr)


if __name__ == "__main__":
    unittest.main()
