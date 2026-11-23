"""Argument handling of scripts/build-debug-target.sh, with a stand-in west."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
FRAGMENT = REPO / "scripts/debug-optimizations.conf"

# Records its arguments, then makes the ELF that the script expects, or fails when told to.
FAKE_WEST = """#!/bin/sh
printf '%s\\n' "$@" > "$FAKE_WEST_LOG"
if [ -n "${FAKE_WEST_FAIL:-}" ]; then exit 37; fi
while [ $# -gt 0 ]; do
    if [ "$1" = "-d" ]; then mkdir -p "$2/zephyr" && : > "$2/zephyr/zephyr.elf" && : > "$2/compile_commands.json"; fi
    shift
done
"""


class DebugTargetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.workspace = root / "workspace"
        self.repo = self.workspace / "repo"
        (self.workspace / ".west").mkdir(parents=True)
        (self.workspace / ".west/config").write_text("")
        (self.workspace / "zephyr").mkdir()
        (self.workspace / "zephyr/zephyr-env.sh").write_text("")
        for application in ("samples/time/shell", "samples/hello_crux",
                            "samples/boards/nxp/mimxrt1060_evk/sd_card_file"):
            (self.repo / application).mkdir(parents=True)
            (self.repo / application / "CMakeLists.txt").write_text("")
        (self.repo / "scripts").mkdir()
        for name in ("build-debug-target.sh", "select-clangd-database.sh", "debug-optimizations.conf"):
            (self.repo / "scripts" / name).write_text((REPO / "scripts" / name).read_text())
            (self.repo / "scripts" / name).chmod(0o755)
        subprocess.check_call(["git", "-C", str(self.repo), "init", "-q"])
        self.bin = root / "bin"
        self.bin.mkdir()
        west = self.bin / "west"
        west.write_text(FAKE_WEST)
        west.chmod(0o755)
        self.log = root / "west.log"

    def run_script(self, *arguments, **extra_environment):
        environment = dict(os.environ, CRUX_WORKSPACE=str(self.workspace),
                           PATH=f"{self.bin}:{os.environ['PATH']}", FAKE_WEST_LOG=str(self.log),
                           **extra_environment)
        return subprocess.run(["bash", str(self.repo / "scripts/build-debug-target.sh"), *arguments],
                              cwd=self.repo, env=environment, capture_output=True, text=True)

    def west_arguments(self):
        return self.log.read_text().splitlines()

    def test_default_is_the_time_sample_in_the_unchanged_build_directory(self):
        result = self.run_script("mimxrt1060_evk@B//qspi")
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = self.west_arguments()
        self.assertEqual(arguments[arguments.index("-d") + 1],
                         str(self.repo / "build/zephyr/mimxrt1060_evk_B_qspi"))
        self.assertIn(str(self.repo / "samples/time/shell"), arguments)
        self.assertFalse(any("EXTRA_CONF_FILE" in argument for argument in arguments))

    def test_application_path_selects_the_application_and_its_own_directory(self):
        result = self.run_script("mimxrt1060_evk@B//qspi", "--app",
                                 "samples/boards/nxp/mimxrt1060_evk/sd_card_file")
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = self.west_arguments()
        self.assertEqual(arguments[arguments.index("-d") + 1],
                         str(self.repo / "build/zephyr"
                             / "mimxrt1060_evk_B_qspi--samples_boards_nxp_mimxrt1060_evk_sd_card_file"))
        self.assertIn(str(self.repo / "samples/boards/nxp/mimxrt1060_evk/sd_card_file"), arguments)
        self.assertNotIn(str(self.repo / "samples/time/shell"), arguments)

    def test_debug_optimizations_adds_the_fragment_and_a_separate_directory(self):
        result = self.run_script("mimxrt1060_evk@B//qspi", "--debug-optimizations")
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = self.west_arguments()
        self.assertEqual(arguments[arguments.index("-d") + 1],
                         str(self.repo / "build/zephyr/mimxrt1060_evk_B_qspi--og"))
        self.assertIn(f"-DEXTRA_CONF_FILE={self.repo / 'scripts/debug-optimizations.conf'}", arguments)

    def test_application_and_debug_optimizations_combine(self):
        result = self.run_script("mimxrt1060_evk@B//qspi", "--app", "samples/time/shell",
                                 "--debug-optimizations")
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = self.west_arguments()
        self.assertEqual(arguments[arguments.index("-d") + 1],
                         str(self.repo / "build/zephyr/mimxrt1060_evk_B_qspi--samples_time_shell--og"))

    def test_an_existing_build_directory_is_not_reconfigured(self):
        directory = self.repo / "build/zephyr/mimxrt1060_evk_B_qspi--og"
        directory.mkdir(parents=True)
        (directory / "build.ninja").write_text("")
        result = self.run_script("mimxrt1060_evk@B//qspi", "--debug-optimizations")
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = self.west_arguments()
        self.assertNotIn("--", arguments)
        self.assertFalse(any("EXTRA_CONF_FILE" in argument for argument in arguments))

    def test_rejects_bad_arguments_without_building(self):
        for arguments in ((), ("--app", "samples/time/shell"), ("board", "--unknown"),
                          ("board", "--app"), ("board", "--app", "samples/missing")):
            with self.subTest(arguments=arguments):
                result = self.run_script(*arguments)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(self.log.exists())

    def current_link(self):
        return self.repo / "build/zephyr/mimxrt1060_evk_B_qspi--current"

    def test_each_successful_build_points_the_current_link_at_its_directory(self):
        # The VS Code profiles debug the ELF behind this link, so they follow the last build.
        link = self.current_link()
        result = self.run_script("mimxrt1060_evk@B//qspi")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), "mimxrt1060_evk_B_qspi")
        self.assertIn(f"Current build link:   {link}", result.stdout)

        result = self.run_script("mimxrt1060_evk@B//qspi", "--app", "samples/hello_crux")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.readlink(link), "mimxrt1060_evk_B_qspi--samples_hello_crux")
        self.assertTrue((link / "zephyr/zephyr.elf").is_file())
        self.assertEqual(sorted(path.name for path in link.parent.iterdir()),
                         ["mimxrt1060_evk_B_qspi", "mimxrt1060_evk_B_qspi--current",
                          "mimxrt1060_evk_B_qspi--samples_hello_crux"])

    def test_a_failed_build_leaves_the_previous_link(self):
        link = self.current_link()
        self.assertEqual(self.run_script("mimxrt1060_evk@B//qspi").returncode, 0)
        result = self.run_script("mimxrt1060_evk@B//qspi", "--app", "samples/hello_crux",
                                 FAKE_WEST_FAIL="1")
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertEqual(os.readlink(link), "mimxrt1060_evk_B_qspi")
        self.assertNotIn("Current build link", result.stdout)

    def test_a_build_without_an_elf_leaves_the_previous_link(self):
        link = self.current_link()
        self.assertEqual(self.run_script("mimxrt1060_evk@B//qspi").returncode, 0)
        # This west makes the compilation database but no ELF.
        (self.bin / "west").write_text(FAKE_WEST.replace(' && : > "$2/zephyr/zephyr.elf"', ""))
        result = self.run_script("mimxrt1060_evk@B//qspi", "--debug-optimizations")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(os.readlink(link), "mimxrt1060_evk_B_qspi")

    def test_vs_code_profiles_debug_the_elf_behind_the_printed_link(self):
        result = self.run_script("mimxrt1060_evk@B//qspi")
        self.assertEqual(result.returncode, 0, result.stderr)
        printed = next(line.split(":", 1)[1].strip() for line in result.stdout.splitlines()
                       if line.startswith("Current build link:"))
        relative = Path(printed).relative_to(self.repo).as_posix()
        expected = f"${{workspaceFolder}}/{relative}/zephyr/zephyr.elf"
        configurations = json.loads((REPO / ".vscode/launch.json").read_text())["configurations"]
        labels = {task["label"] for task in json.loads((REPO / ".vscode/tasks.json").read_text())["tasks"]}
        self.assertEqual(len(configurations), 3)
        for configuration in configurations:
            with self.subTest(profile=configuration["name"]):
                self.assertEqual(configuration["executable"], expected)
                if "preLaunchTask" in configuration:
                    self.assertIn(configuration["preLaunchTask"], labels)

    def test_fragment_sets_only_the_optimisation_level(self):
        lines = [line for line in FRAGMENT.read_text().splitlines() if line and not line.startswith("#")]
        self.assertEqual(lines, ["CONFIG_DEBUG_OPTIMIZATIONS=y"])


if __name__ == "__main__":
    unittest.main()
