"""Check scripts/update-crux-pin.py on throwaway Git repositories, with no network."""
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest

try:
    import yaml
except ImportError:  # west installs PyYAML; skip where it is missing.
    yaml = None

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/update-crux-pin.py"
GIT = shutil.which("git")

CHANGED, CURRENT = 0, 3


def git(*args, cwd=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, text=True,
                          capture_output=True).stdout.strip()


def commit(repo, name, subject):
    (repo / name).write_text(subject + "\n")
    git("add", name, cwd=repo)
    git("commit", "-q", "-m", subject, cwd=repo)
    return git("rev-parse", "HEAD", cwd=repo)


MANIFEST = """\
# Product manifest.
manifest:
  version: "1.2"
  remotes:
    - name: crux
      url-base: {base}
  projects:
    - name: vendor-runtime
      url: https://git.example/vendor-runtime
      revision: 0123456789abcdef0123456789abcdef01234567 # v1.0.0
    # Crux, kept current by the pin bot.
    - name: crux-pilot
      remote: crux
      # A comment that must stay.
      revision: {revision}   # trailing note
      import: true
  self:
    path: product-x
"""


@unittest.skipUnless(GIT, "git is required")
@unittest.skipUnless(yaml, "PyYAML is required; west installs it")
class UpdateCruxPinTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        # The remote: <base>/crux-pilot, as west builds it from url-base and the name.
        self.base = self.tmp / "remotes"
        self.crux = self.base / "crux-pilot"
        self.crux.mkdir(parents=True)
        git("init", "-q", "-b", "main", cwd=self.crux)
        self.first = commit(self.crux, "a.txt", "feat: first")
        self.second = commit(self.crux, "b.txt", "fix: second")
        self.third = commit(self.crux, "c.txt", "docs: third")
        git("tag", "v0.1.0", self.second, cwd=self.crux)
        self.product = self.tmp / "product-x"
        self.product.mkdir()
        self.manifest = self.product / "west.yml"
        self.write_manifest(self.first)

    def write_manifest(self, revision, text=MANIFEST):
        self.manifest.write_text(text.format(base=self.base.as_uri(), revision=revision))

    def run_script(self, *args, env=None):
        return subprocess.run([sys.executable, str(SCRIPT), "--manifest", str(self.manifest), *args],
                              cwd=self.product, text=True, capture_output=True,
                              env=dict(os.environ, **(env or {})))

    def revision(self):
        projects = yaml.safe_load(self.manifest.read_text())["manifest"]["projects"]
        return next(p for p in projects if p["name"] == "crux-pilot")["revision"]

    def test_moves_the_pin_to_the_remote_main_and_changes_only_that_line(self):
        before = self.manifest.read_text().splitlines()
        result = self.run_script()
        self.assertEqual(CHANGED, result.returncode, result.stderr)
        after = self.manifest.read_text().splitlines()
        self.assertEqual(self.third, self.revision())
        changed = [(a, b) for a, b in zip(before, after) if a != b]
        self.assertEqual(len(before), len(after))
        self.assertEqual(1, len(changed))
        self.assertEqual(f"      revision: {self.third}", changed[0][1])

    def test_exit_three_when_the_pin_is_already_current(self):
        self.write_manifest(self.third)
        text = self.manifest.read_text()
        result = self.run_script()
        self.assertEqual(CURRENT, result.returncode, result.stderr)
        self.assertEqual(text, self.manifest.read_text())

    def test_to_resolves_a_tag_or_takes_a_full_sha(self):
        self.assertEqual(CHANGED, self.run_script("--to", "v0.1.0").returncode)
        self.assertEqual(self.second, self.revision())
        self.assertEqual(CHANGED, self.run_script("--to", self.third).returncode)
        self.assertEqual(self.third, self.revision())

    def test_a_short_or_unknown_revision_is_refused(self):
        for rev in (self.third[:12], "no-such-branch"):
            with self.subTest(rev=rev):
                result = self.run_script("--to", rev)
                self.assertNotIn(result.returncode, (CHANGED, CURRENT))
                self.assertEqual(self.first, self.revision())

    def test_a_branch_pin_becomes_a_sha_pin(self):
        self.write_manifest("main")
        self.assertEqual(CHANGED, self.run_script().returncode)
        self.assertEqual(self.third, self.revision())

    def test_summary_names_both_revisions_and_lists_the_new_commits(self):
        summary = self.tmp / "summary.md"
        result = self.run_script("--summary", str(summary))
        self.assertEqual(CHANGED, result.returncode, result.stderr)
        text = summary.read_text()
        title, _, body = text.partition("\n\n")
        self.assertIn(self.third[:12], title)
        self.assertNotIn("\n", title)
        self.assertIn(self.first, body)
        self.assertIn(self.third, body)
        self.assertIn("fix: second", body)
        self.assertIn("docs: third", body)
        self.assertNotIn("feat: first", body)

    def test_remote_url_overrides_the_manifest_location(self):
        mirror = self.tmp / "mirror.git"
        git("clone", "-q", "--bare", str(self.crux), str(mirror))
        newest = commit(self.crux, "d.txt", "feat: only upstream")
        result = self.run_script("--remote-url", str(mirror))
        self.assertEqual(CHANGED, result.returncode, result.stderr)
        self.assertEqual(self.third, self.revision())
        self.assertNotEqual(newest, self.revision())

    def test_branch_selects_another_branch(self):
        git("branch", "release-1", self.second, cwd=self.crux)
        self.assertEqual(CHANGED, self.run_script("--branch", "release-1").returncode)
        self.assertEqual(self.second, self.revision())

    def test_project_is_detected_or_named(self):
        text = MANIFEST.replace("name: crux-pilot", "name: platform")
        self.write_manifest(self.first, text)
        result = self.run_script("--remote-url", str(self.crux))
        self.assertNotEqual(CHANGED, result.returncode)
        self.assertIn("--project", result.stderr)
        result = self.run_script("--project", "platform", "--remote-url", str(self.crux))
        self.assertEqual(CHANGED, result.returncode, result.stderr)

    def test_a_project_named_crux_is_detected(self):
        self.write_manifest(self.first, MANIFEST.replace("name: crux-pilot", "name: crux\n      repo-path: crux-pilot"))
        result = self.run_script()
        self.assertEqual(CHANGED, result.returncode, result.stderr)

    def test_a_missing_revision_line_is_an_error(self):
        text = MANIFEST.replace("      revision: {revision}   # trailing note\n", "")
        self.write_manifest(self.first, text)
        result = self.run_script()
        self.assertNotIn(result.returncode, (CHANGED, CURRENT))
        self.assertIn("revision", result.stderr)

    def test_dry_run_changes_nothing(self):
        text = self.manifest.read_text()
        result = self.run_script("--dry-run")
        self.assertEqual(CHANGED, result.returncode, result.stderr)
        self.assertEqual(text, self.manifest.read_text())

    def write_hook(self, body):
        hook = self.product / "scripts/crux-pin-hook"
        hook.parent.mkdir(exist_ok=True)
        hook.write_text("#!/bin/sh\n" + body)
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
        return hook

    def test_the_product_hook_runs_with_old_new_and_the_checkout(self):
        self.write_hook(textwrap.dedent("""\
            echo "$CRUX_PIN_OLD $CRUX_PIN_NEW $CRUX_PIN_PROJECT" > hook.out
            echo "$CRUX_PIN_CHECKOUT" >> hook.out
            """))
        checkout = self.tmp / "crux-pilot"
        git("clone", "-q", str(self.crux), str(checkout))
        (self.tmp / ".west").mkdir()  # The workspace top directory.
        result = self.run_script()
        self.assertEqual(CHANGED, result.returncode, result.stderr)
        lines = (self.product / "hook.out").read_text().splitlines()
        self.assertEqual(f"{self.first} {self.third} crux-pilot", lines[0])
        self.assertEqual(checkout.resolve(), Path(lines[1]).resolve())

    def test_the_hook_does_not_run_when_nothing_changes_and_a_failing_hook_fails(self):
        self.write_hook("touch ran\nexit 7\n")
        self.write_manifest(self.third)
        self.assertEqual(CURRENT, self.run_script().returncode)
        self.assertFalse((self.product / "ran").exists())
        self.write_manifest(self.first)
        result = self.run_script()
        self.assertNotIn(result.returncode, (CHANGED, CURRENT))
        self.assertIn("crux-pin-hook", result.stderr)

    def test_no_hook_skips_it(self):
        self.write_hook("touch ran\n")
        self.assertEqual(CHANGED, self.run_script("--no-hook").returncode)
        self.assertFalse((self.product / "ran").exists())


if __name__ == "__main__":
    unittest.main()
