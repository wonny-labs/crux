#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check tests/target/check_boot_reproducibility.sh, the reproducibility check of the composition.

The script compares two builds of the composition and runs `imgtool verify` on both signed images. The
real builds and the real imgtool are exercised only where the composition check runs (the Linux Dev
Container and CI), and the script has not run there. Here it runs end to end against

* FAKE build trees of synthetic images (the helpers of test_compare_boot_builds.py),
* a FAKE imgtool.py (named as such inside, not MCUboot's tool) in a fake MCUboot checkout at the path
  that the script derives from CRUX_WORKSPACE, whose `verify` answers as the test chooses, and
* in --build mode a FAKE composition command (CRUX_COMPOSITION_COMMAND) that writes a build tree.

So these tests show that the script's logic does what it says. They say nothing about whether two real
builds reproduce. The standard library only.
"""
import hashlib
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCRIPT = REPO / "tests/target/check_boot_reproducibility.sh"
PAGE = REPO / "docs/boot-reproducibility.md"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


helpers = load_module(HERE / "test_compare_boot_builds.py", "compare_boot_builds_helpers")

FAKE_IMGTOOL = '''#!/usr/bin/env python3
"""FAKE imgtool for tests/build/test_check_boot_reproducibility.py. This is NOT MCUboot's imgtool.

verify -k KEY FILE  exits as fake-mode.txt says: honest (0 only for a file listed in
                    fake-good-sha256.txt), accept-all (0), refuse-all (1), crash (traceback)
--help              exits 0, as the real tool does when its requirements are installed
mode no-requirements raises ModuleNotFoundError for every command
"""
import hashlib
from pathlib import Path
import sys

here = Path(__file__).resolve().parent
mode = (here / "fake-mode.txt").read_text().strip()
command = sys.argv[1]
if mode == "no-requirements":
    raise ModuleNotFoundError("No module named 'cryptography' (FAKE imgtool)")
if command == "--help":
    print("FAKE imgtool help")
    sys.exit(0)
if command == "verify":
    data = Path(sys.argv[-1]).read_bytes()
    good = (here / "fake-good-sha256.txt").read_text().split()
    if mode == "crash":
        raise RuntimeError("FAKE imgtool crash")
    accepted = mode == "accept-all" or (mode == "honest" and hashlib.sha256(data).hexdigest() in good)
    print("FAKE imgtool verify: " + ("Image was correctly validated" if accepted else "Image is not valid"))
    sys.exit(0 if accepted else 1)
sys.exit(2)
'''

# A fake composition command: copies the tree named in fake-tree-N (N = the run number) into the build
# directory, so that two runs can produce two different builds, as a real command might.
FAKE_COMPOSITION = '''#!/usr/bin/env bash
set -euo pipefail
dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pwd >>"$dir/cwds"
count_file="$dir/runs"
count="$(cat "$count_file" 2>/dev/null || echo 0)"
count=$((count + 1))
printf '%s' "$count" >"$count_file"
build="$(cat "$dir/build-dir")"
rm -rf "$build"
mkdir -p "$(dirname "$build")"
cp -R "$dir/tree-$count" "$build"
'''


class ScriptShape(unittest.TestCase):
    def setUp(self):
        self.script = SCRIPT.read_text(encoding="utf-8") if SCRIPT.is_file() else ""
        self.code = "\n".join(l for l in self.script.splitlines() if not l.lstrip().startswith("#"))

    def test_the_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT.is_file(), f"{SCRIPT} is missing")
        self.assertTrue(SCRIPT.stat().st_mode & 0o111, "the script is not executable")
        self.assertTrue(self.script.startswith("#!/usr/bin/env bash\n"))

    def test_the_script_is_not_under_scripts_and_has_its_comparison_tool_beside_it(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertFalse((REPO / "scripts" / SCRIPT.name).exists())
        self.assertTrue((SCRIPT.parent / "compare_boot_builds.py").is_file())
        self.assertFalse(list((REPO / "scripts").glob("*reproduc*")))

    def test_the_script_uses_strict_mode_and_derives_the_root_from_its_depth(self):
        self.assertIn("set -euo pipefail", self.code.splitlines())
        self.assertIn('repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"', self.code)
        self.assertIn('python="${CRUX_PYTHON:-python3}"', self.code)
        self.assertIn('workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"', self.code)

    def test_the_script_never_generates_a_key_programs_a_board_or_changes_the_manifest(self):
        for word in ("keygen", "flash", "debug", "openocd", "pyocd", "JLink", "probe", "reset", "west", "pip",
                     "git", "ninja", "cmake", "docker"):
            self.assertIsNone(re.search(rf"\b{word}\b", self.code), word)

    def test_the_script_says_it_is_not_wired_and_has_not_run_on_real_builds(self):
        header = "\n".join(l for l in self.script.splitlines() if l.startswith("#"))
        self.assertRegex(header, r"NOT wired")
        self.assertRegex(header, r"never run on a real build")
        self.assertIn("scripts/test-boot-composition.sh", self.code)
        self.assertIn("compare_boot_builds.py", self.code)

    def test_the_page_exists_and_names_the_limits(self):
        page = PAGE.read_text(encoding="utf-8")
        for text in ("Not verified", "tests/target/check_boot_reproducibility.sh", "NOT wired",
                     "same path", "stage8-reproducibility-and-signing.md", "issues/296",
                     "directory that the composition command writes"):
            self.assertIn(text, page)


class BehaviourTest(unittest.TestCase):
    """Run the script against fake build trees and a fake imgtool."""

    @classmethod
    def setUpClass(cls):
        cls.sig_a = helpers.signed(helpers.SIG_A)
        cls.sig_b = helpers.signed(helpers.SIG_B)

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.root = Path(self._dir.name)
        self.workspace = self.root / "workspace"
        self.tool_dir = self.workspace / "bootloader/mcuboot/scripts"
        self.tool_dir.mkdir(parents=True)
        (self.workspace / "bootloader/mcuboot/root-ec-p256.pem").write_text("FAKE KEY FILE\n")
        (self.tool_dir / "imgtool.py").write_text(FAKE_IMGTOOL)
        self.a = helpers.write_build(self.root / "a", signed_bin=self.sig_a)
        self.b = helpers.write_build(self.root / "b", signed_bin=self.sig_b)
        self.set_fake("honest", good=[self.sig_a, self.sig_b, helpers.confirmed(self.sig_a),
                                      helpers.confirmed(self.sig_b)])

    def set_fake(self, mode, good=()):
        (self.tool_dir / "fake-mode.txt").write_text(mode)
        (self.tool_dir / "fake-good-sha256.txt").write_text(
            "\n".join(hashlib.sha256(g).hexdigest() for g in good) + "\n")

    def run_script(self, *args, expect=None, env_extra=None, python=None):
        env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "CRUX_WORKSPACE": str(self.workspace),
               "CRUX_PYTHON": python or sys.executable}
        env.update(env_extra or {})
        done = subprocess.run(["bash", str(SCRIPT), *[str(a) for a in args]], capture_output=True, text=True, env=env)
        if expect is not None:
            self.assertEqual(expect, done.returncode, f"stdout:\n{done.stdout}\nstderr:\n{done.stderr}")
        return done

    # ---- comparing two existing builds ----

    def test_two_builds_that_differ_only_in_the_signature_pass_and_say_what_was_not_compared(self):
        done = self.run_script(self.a, self.b, expect=0)
        for text in ("Reproducibility check passed", "equivalent", "Result: reproducible",
                     "imgtool verify", "not a boot result"):
            self.assertIn(text, done.stdout)
        self.assertIn("same container", done.stdout)

    def test_identical_builds_pass(self):
        helpers.write_build(self.root / "c", signed_bin=self.sig_a)
        self.run_script(self.a, self.root / "c", expect=0)

    def test_a_different_unsigned_binary_fails_and_names_the_artifact(self):
        helpers.write_build(self.root / "c", signed_bin=self.sig_a, mcuboot=helpers.MCUBOOT_BIN[:-1])
        done = self.run_script(self.a, self.root / "c", expect=1)
        self.assertIn("not reproducible", done.stdout + done.stderr)
        self.assertIn("mcuboot/zephyr/zephyr.bin", done.stdout)

    def test_a_signed_image_that_imgtool_refuses_fails_even_when_the_builds_agree(self):
        self.set_fake("refuse-all")
        done = self.run_script(self.a, self.b, expect=1)
        self.assertIn("imgtool verify", done.stderr)
        self.assertIn("build A", done.stderr)

    def test_a_crash_of_imgtool_is_not_a_refusal_and_not_a_pass(self):
        self.set_fake("crash")
        done = self.run_script(self.a, self.b, expect=1)
        self.assertIn("imgtool crashed", done.stderr)

    def test_the_second_build_is_verified_too(self):
        # Only the first signed image is listed as good: the second is refused by the honest fake.
        self.set_fake("honest", good=[self.sig_a])
        done = self.run_script(self.a, self.b, expect=1)
        self.assertIn("build B", done.stderr)

    def test_the_strict_option_fails_a_different_signature(self):
        done = self.run_script("--strict-signature", self.a, self.b, expect=1)
        self.assertIn("not reproducible", done.stdout)

    # ---- missing inputs: exit 2 ----

    def test_a_missing_build_directory_exits_2_and_names_the_ways_to_get_two_builds(self):
        done = self.run_script(self.a, self.root / "no-such", expect=2)
        self.assertIn("no-such", done.stderr)
        self.assertIn("--build", done.stderr)

    def test_the_same_directory_twice_exits_2(self):
        self.run_script(self.a, self.a, expect=2)

    def test_no_arguments_exit_2_with_the_usage(self):
        done = self.run_script(expect=2)
        self.assertIn("Usage", done.stderr)

    def test_a_missing_imgtool_exits_2(self):
        (self.tool_dir / "imgtool.py").unlink()
        done = self.run_script(self.a, self.b, expect=2)
        self.assertIn("imgtool", done.stderr)

    def test_a_missing_key_exits_2(self):
        (self.workspace / "bootloader/mcuboot/root-ec-p256.pem").unlink()
        self.run_script(self.a, self.b, expect=2)

    def test_imgtool_without_its_requirements_exits_2_and_names_them(self):
        self.set_fake("no-requirements")
        done = self.run_script(self.a, self.b, expect=2)
        self.assertIn("requirements", done.stderr)

    def test_a_missing_python_exits_2(self):
        done = self.run_script(self.a, self.b, python="/no/such/python", expect=2)
        self.assertIn("python", done.stderr)

    # ---- --build: two runs of the composition command ----

    def fake_command(self, trees):
        command_dir = self.root / "command"
        command_dir.mkdir()
        build = self.root / "build/zephyr/boot-composition"
        (command_dir / "build-dir").write_text(str(build))
        for number, tree in enumerate(trees, start=1):
            shutil.copytree(tree, command_dir / f"tree-{number}")
        command = command_dir / "compose.sh"
        command.write_text(FAKE_COMPOSITION)
        command.chmod(0o755)
        return command, build

    def test_build_runs_the_command_twice_and_compares_the_two_builds(self):
        command, build = self.fake_command([self.a, self.b])
        done = self.run_script("--build", build, env_extra={"CRUX_COMPOSITION_COMMAND": str(command)}, expect=0)
        self.assertEqual("2", (command.parent / "runs").read_text())
        self.assertIn("Result: reproducible", done.stdout)
        self.assertTrue(Path(str(build) + ".first").is_dir())

    def test_build_runs_the_command_from_the_repository_root(self):
        # The real composition command finds the repository with git rev-parse, which depends on the
        # current directory.
        command, build = self.fake_command([self.a, self.b])
        self.run_script("--build", build, env_extra={"CRUX_COMPOSITION_COMMAND": str(command)}, expect=0)
        cwds = (command.parent / "cwds").read_text().split()
        self.assertEqual([str(REPO.resolve())] * 2, [str(Path(c).resolve()) for c in cwds])

    def test_build_fails_when_the_two_runs_differ_in_an_unsigned_binary(self):
        different = helpers.write_build(self.root / "d", signed_bin=self.sig_a, app=helpers.APP_BIN + b"\0")
        command, build = self.fake_command([self.a, different])
        done = self.run_script("--build", build, env_extra={"CRUX_COMPOSITION_COMMAND": str(command)}, expect=1)
        self.assertIn("not reproducible", done.stdout + done.stderr)

    def test_build_stops_with_exit_2_when_the_command_fails(self):
        command_dir = self.root / "command"
        command_dir.mkdir()
        command = command_dir / "compose.sh"
        command.write_text("#!/usr/bin/env bash\nexit 7\n")
        command.chmod(0o755)
        build = self.root / "build/zephyr/boot-composition"
        done = self.run_script("--build", build, env_extra={"CRUX_COMPOSITION_COMMAND": str(command)}, expect=2)
        self.assertIn("composition command", done.stderr)
        self.assertIn("7", done.stderr)

    def test_build_refuses_to_overwrite_an_existing_first_copy(self):
        command, build = self.fake_command([self.a, self.b])
        Path(str(build) + ".first").mkdir(parents=True)
        done = self.run_script("--build", build, env_extra={"CRUX_COMPOSITION_COMMAND": str(command)}, expect=2)
        self.assertIn(".first", done.stderr)
        self.assertFalse((command.parent / "runs").exists())


class CiProposalTest(unittest.TestCase):
    """The page proposes where two real builds could be compared in CI; nothing is wired."""

    def setUp(self):
        self.page = PAGE.read_text(encoding="utf-8")
        start = self.page.index("## Proposal: comparing two real builds in CI")
        self.section = self.page[start:]

    def test_the_proposal_is_labelled_inference_and_states_cost_and_what_it_shows(self):
        self.assertIn("**Inference**", self.section)
        self.assertRegex(self.section, r"(?i)cost")
        self.assertRegex(self.section, r"(?i)what it (would )?show")
        self.assertRegex(self.section, r"(?i)does not show|would not show|will not show")

    def test_the_measured_step_time_is_given_with_its_source(self):
        self.assertIn("43898428480", self.section)
        self.assertRegex(self.section, r"62 s")

    def test_the_proposal_names_the_options_and_the_approval_it_needs(self):
        self.assertIn("check_boot_reproducibility.sh --build", self.section)
        self.assertRegex(self.section, r"(?i)owner")
        self.assertRegex(self.section, r"(?i)protected")

    def test_the_page_gives_one_recommendation_for_the_placement(self):
        # The older section advised a job of its own; the proposal recommends the runtime shard. The page
        # must not hold both.
        self.assertNotIn("better placed in its own job or shard", self.page)
        self.assertEqual(1, self.page.count("tests/target/check_boot_reproducibility.sh --build\n"))

    def test_the_claims_that_are_not_read_from_a_record_are_not_labelled_verified(self):
        paragraph = next(l for l in self.section.splitlines() if l.startswith("**Cost, measured.**"))
        verified, _, rest = paragraph.partition("**Inference:**")
        self.assertIn("43898428480", verified)
        self.assertNotIn("separate job probably costs more", verified)
        self.assertIn("separate job probably costs more", rest)

    def test_no_workflow_runs_the_reproducibility_check(self):
        # The task is a proposal, not a heavy job: the check stays out of every workflow.
        for workflow in (REPO / ".github/workflows").glob("*.yml"):
            self.assertNotIn("check_boot_reproducibility", workflow.read_text(encoding="utf-8"), workflow.name)
        for script in (REPO / "scripts").glob("*"):
            if script.is_file():
                self.assertNotIn("check_boot_reproducibility", script.read_text(encoding="utf-8", errors="replace"), script.name)


if __name__ == "__main__":
    unittest.main()
