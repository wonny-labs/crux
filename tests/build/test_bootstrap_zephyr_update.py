"""Checks for how `scripts/bootstrap-zephyr.sh` calls `west update`.

The script runs against a stub `west` and a stub Python in a temporary workspace. Nothing is
downloaded. They prove nothing about the real fetch.
"""
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "bootstrap-zephyr.sh"


class BootstrapZephyrUpdateTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="crux-zephyr-update-test-")
        root = Path(self.temporary.name).resolve()  # macOS: /var is a symlink to /private/var
        self.workspace = root / "workspace"
        self.repo = self.workspace / "crux"
        self.repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.workspace / ".west").mkdir()
        (self.workspace / ".west" / "config").write_text("")
        (self.workspace / "zephyr" / "scripts").mkdir(parents=True)
        for name in ("requirements-base.txt", "requirements-build-test.txt", "requirements-run-test.txt"):
            (self.workspace / "zephyr" / "scripts" / name).write_text("")
        self.log = root / "west.log"
        self.bin = root / "bin"
        self.bin.mkdir()
        self.stub(self.bin / "west", f"""
echo "west $*" >> "{self.log}"
if [ "$1" = topdir ]; then echo "{self.workspace}"; fi
exit 0
""")
        self.stub(self.bin / "python3", 'exit 0\n')

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def stub(path, body):
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def run_script(self, **environment):
        env = {
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "HOME": self.temporary.name,
            "CRUX_WORKSPACE": str(self.workspace),
            "CRUX_CACHE_DIR": str(Path(self.temporary.name) / "cache"),
            "CRUX_PYTHON": str(self.bin / "python3"),
            **environment,
        }
        return subprocess.run(["bash", str(SCRIPT)], cwd=self.repo, env=env,
                              capture_output=True, text=True, check=False)

    def update_call(self):
        calls = [line for line in self.log.read_text().splitlines() if line.startswith("west update")]
        self.assertEqual(len(calls), 1, calls)
        return calls[0]

    def test_update_fetches_only_the_pinned_revisions(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("--narrow", self.update_call().split())

    def test_update_shows_git_progress_outside_ci(self):
        # Git prints no progress when its output is not a terminal, so the fetch looks stuck.
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("-o=--progress", self.update_call().split())

    def test_update_keeps_ci_logs_free_of_progress_lines(self):
        result = self.run_script(CI="true")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        call = self.update_call().split()
        self.assertIn("--narrow", call)
        self.assertNotIn("-o=--progress", call)

    def move_repo(self, name):
        self.repo = self.repo.rename(self.workspace / name)

    def test_the_older_folder_name_is_still_accepted(self):
        self.move_repo("crux-pilot")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.update_call()

    def test_another_folder_name_is_refused_before_west_runs(self):
        self.move_repo("crux-main")
        result = self.run_script()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(f"Expected repo at {self.workspace}/crux;", result.stderr)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
