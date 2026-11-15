#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check scripts/check-boot-config.py, the build-configuration check of the boot composition.

The check reads the resolved `.config` of the two images that scripts/test-boot-composition.sh builds
(`$build/mcuboot/zephyr/.config` and `$build/<application>/zephyr/.config`) and fails unless

* the bootloader is built for RAM load with revert: CONFIG_BOOT_RAM_LOAD=y and CONFIG_BOOT_RAM_LOAD_REVERT=y,
* the application is built for the same mode: CONFIG_MCUBOOT_BOOTLOADER_MODE_RAM_LOAD_WITH_REVERT=y, and
* CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER is not enabled in either image.

Why: the application's BLINFO_MODE reports RAM load for a bootloader built without revert too, so the
application cannot catch it at run time, and a bootloader that compares the build number disagrees with an
application that does not (docs/plans/image-state-contract-proposal.md, I5 and Q9).

Where the option names come from (labels: Verified = read in the pinned source in this change; the sources
were fetched from the upstream repositories at these revisions, outside this repository):

* Verified, Zephyr v4.4.2 `dccb09599635` `share/sysbuild/image_configurations/BOOTLOADER_image_default.cmake`:
  SB_CONFIG_MCUBOOT_MODE_RAM_LOAD_WITH_REVERT sets CONFIG_BOOT_RAM_LOAD=y and CONFIG_BOOT_RAM_LOAD_REVERT=y
  on the MCUboot image.
* Verified, Zephyr v4.4.2 `dccb09599635` `share/sysbuild/image_configurations/MAIN_image_default.cmake`:
  the same sysbuild option sets CONFIG_MCUBOOT_BOOTLOADER_MODE_RAM_LOAD_WITH_REVERT=y on the application.
  `modules/Kconfig.mcuboot` declares it in the choice MCUBOOT_BOOTLOADER_MODE, so the plain
  MCUBOOT_BOOTLOADER_MODE_RAM_LOAD and the other modes exclude it.
* Verified, MCUboot `6d3b3d2c38ab` `boot/zephyr/Kconfig`: BOOT_RAM_LOAD, BOOT_RAM_LOAD_REVERT (which depends
  on BOOT_RAM_LOAD) and BOOT_VERSION_CMP_USE_BUILD_NUMBER, the last defined only in the MCUboot image.
* Verified, MCUboot `6d3b3d2c38ab` `boot/zephyr/include/mcuboot_config/mcuboot_config.h`:
  CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER defines MCUBOOT_VERSION_CMP_USE_BUILD_NUMBER, and
  CONFIG_BOOT_RAM_LOAD_REVERT defines MCUBOOT_RAM_LOAD_REVERT.
* Not verified: that a build of this repository's composition resolves to these values. That is what the
  script settles on a real build, which CI runs; the fixtures here are hand-written subsets.

The tests use the standard library only and run on fixture files, as host.yml runs this directory without
west.
"""
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/check-boot-config.py"
FIXTURES = REPO / "tests/build/fixtures/boot-config"
IMAGE = "zephyr"  # basename of samples/controller/zephyr, the application of scripts/test-boot-composition.sh

CHECK = runpy.run_path(str(SCRIPT)) if SCRIPT.is_file() else {}


def good(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def without(text, option):
    return "".join(line for line in text.splitlines(keepends=True) if option not in line)


def replaced(text, old, new):
    assert old in text, old
    return text.replace(old, new)


class ParseTest(unittest.TestCase):
    def test_reads_the_kconfig_output_forms(self):
        text = (
            "# comment\n\nCONFIG_A=y\nCONFIG_B=0x80000000\nCONFIG_C=\"a=b\"\n"
            "# CONFIG_D is not set\nCONFIG_E=n\n"
        )
        config = CHECK["parse_config"](text)
        self.assertEqual("y", config["CONFIG_A"])
        self.assertEqual("0x80000000", config["CONFIG_B"])
        self.assertEqual('"a=b"', config["CONFIG_C"])
        self.assertEqual("n", config["CONFIG_D"])
        self.assertEqual("n", config["CONFIG_E"])

    def test_the_last_assignment_wins(self):
        config = CHECK["parse_config"]("CONFIG_A=y\n# CONFIG_A is not set\n")
        self.assertEqual("n", config["CONFIG_A"])

    def test_an_option_that_only_contains_a_name_is_not_that_name(self):
        config = CHECK["parse_config"]("CONFIG_BOOT_RAM_LOAD_REVERT=y\n")
        self.assertNotIn("CONFIG_BOOT_RAM_LOAD", config)


class BootloaderTest(unittest.TestCase):
    def errors(self, text):
        return CHECK["bootloader_errors"](CHECK["parse_config"](text))

    def test_good_fixture_passes(self):
        self.assertEqual([], self.errors(good("good-mcuboot.config")))

    def test_ram_load_without_revert_fails(self):
        for text in (
            without(good("good-mcuboot.config"), "CONFIG_BOOT_RAM_LOAD_REVERT"),
            replaced(good("good-mcuboot.config"), "CONFIG_BOOT_RAM_LOAD_REVERT=y",
                     "# CONFIG_BOOT_RAM_LOAD_REVERT is not set"),
        ):
            errors = self.errors(text)
            self.assertEqual(1, len(errors), errors)
            self.assertIn("CONFIG_BOOT_RAM_LOAD_REVERT", errors[0])

    def test_no_ram_load_fails(self):
        text = replaced(good("good-mcuboot.config"), "CONFIG_BOOT_RAM_LOAD=y", "# CONFIG_BOOT_RAM_LOAD is not set")
        self.assertTrue(any("CONFIG_BOOT_RAM_LOAD" in error for error in self.errors(text)))

    def test_another_boot_mode_fails(self):
        text = (without(good("good-mcuboot.config"), "CONFIG_BOOT_RAM_LOAD")
                + "CONFIG_BOOT_SWAP_USING_MOVE=y\n")
        self.assertTrue(self.errors(text))

    def test_build_number_comparison_fails(self):
        text = replaced(good("good-mcuboot.config"), "# CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER is not set",
                        "CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER=y")
        errors = self.errors(text)
        self.assertEqual(1, len(errors), errors)
        self.assertIn("CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER", errors[0])

    def test_build_number_comparison_absent_or_n_passes(self):
        base = without(good("good-mcuboot.config"), "CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER")
        self.assertEqual([], self.errors(base))
        self.assertEqual([], self.errors(base + "CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER=n\n"))

    def test_build_number_comparison_with_any_other_value_fails(self):
        for value in ("1", '"y"', "m"):
            text = without(good("good-mcuboot.config"), "CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER")
            text += f"CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER={value}\n"
            self.assertTrue(self.errors(text), value)

    def test_every_failure_is_reported(self):
        text = without(good("good-mcuboot.config"), "CONFIG_BOOT_RAM_LOAD_REVERT") \
            + "CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER=y\n"
        self.assertEqual(2, len(self.errors(text)))


class ApplicationTest(unittest.TestCase):
    def errors(self, text):
        return CHECK["application_errors"](CHECK["parse_config"](text))

    def test_good_fixture_passes(self):
        self.assertEqual([], self.errors(good("good-app.config")))

    def test_plain_ram_load_fails(self):
        text = (without(good("good-app.config"), "MODE_RAM_LOAD")
                + "CONFIG_MCUBOOT_BOOTLOADER_MODE_RAM_LOAD=y\n")
        errors = self.errors(text)
        self.assertEqual(1, len(errors), errors)
        self.assertIn("CONFIG_MCUBOOT_BOOTLOADER_MODE_RAM_LOAD_WITH_REVERT", errors[0])

    def test_a_swap_mode_fails(self):
        text = (without(good("good-app.config"), "MODE_RAM_LOAD")
                + "CONFIG_MCUBOOT_BOOTLOADER_MODE_SWAP_USING_OFFSET=y\n")
        self.assertTrue(self.errors(text))

    def test_no_mode_fails(self):
        self.assertTrue(self.errors(without(good("good-app.config"), "MODE_RAM_LOAD")))

    def test_build_number_comparison_fails(self):
        text = good("good-app.config") + "CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER=y\n"
        errors = self.errors(text)
        self.assertEqual(1, len(errors), errors)
        self.assertIn("CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER", errors[0])


class CommandLineTest(unittest.TestCase):
    """Run the script as scripts/test-boot-composition.sh's caller would: on a build directory."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.build = self.tmp / "boot-composition"

    def write(self, mcuboot=None, app=None):
        for directory, text in (("mcuboot", mcuboot), (IMAGE, app)):
            if text is not None:
                path = self.build / directory / "zephyr/.config"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")

    def run_check(self, *arguments):
        return subprocess.run([sys.executable, "-I", str(SCRIPT), *arguments], capture_output=True, text=True)

    def test_good_build_passes(self):
        self.write(good("good-mcuboot.config"), good("good-app.config"))
        result = self.run_check(str(self.build))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("build only", result.stdout)

    def test_a_bad_bootloader_fails_and_names_the_file(self):
        self.write(without(good("good-mcuboot.config"), "CONFIG_BOOT_RAM_LOAD_REVERT"), good("good-app.config"))
        result = self.run_check(str(self.build))
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("CONFIG_BOOT_RAM_LOAD_REVERT", result.stderr)
        self.assertIn(str(self.build / "mcuboot/zephyr/.config"), result.stderr)

    def test_a_bad_application_fails_and_names_the_file(self):
        self.write(good("good-mcuboot.config"),
                   replaced(good("good-app.config"), "MODE_RAM_LOAD_WITH_REVERT=y", "MODE_RAM_LOAD=y"))
        result = self.run_check(str(self.build))
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn(str(self.build / IMAGE / "zephyr/.config"), result.stderr)

    def test_a_failure_in_each_image_is_reported_together(self):
        self.write(good("good-mcuboot.config") + "CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER=y\n",
                   without(good("good-app.config"), "MODE_RAM_LOAD"))
        result = self.run_check(str(self.build))
        self.assertEqual(1, result.returncode)
        self.assertIn("CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER", result.stderr)
        self.assertIn("CONFIG_MCUBOOT_BOOTLOADER_MODE_RAM_LOAD_WITH_REVERT", result.stderr)

    def test_a_missing_build_directory_is_not_a_verdict(self):
        result = self.run_check(str(self.tmp / "absent"))
        self.assertEqual(2, result.returncode)
        self.assertNotIn("Traceback", result.stderr)

    def test_a_missing_configuration_is_not_a_verdict(self):
        for mcuboot, app in ((None, good("good-app.config")), (good("good-mcuboot.config"), None)):
            shutil.rmtree(self.build, ignore_errors=True)
            self.write(mcuboot, app)
            result = self.run_check(str(self.build))
            self.assertEqual(2, result.returncode, result.stdout)
            self.assertNotIn("Traceback", result.stderr)

    def test_a_file_without_options_is_not_a_configuration(self):
        self.write("# nothing here\n", good("good-app.config"))
        result = self.run_check(str(self.build))
        self.assertEqual(2, result.returncode)

    def test_the_application_directory_can_be_named(self):
        for directory, text in (("mcuboot", good("good-mcuboot.config")), ("controller", good("good-app.config"))):
            path = self.build / directory / "zephyr/.config"
            path.parent.mkdir(parents=True)
            path.write_text(text, encoding="utf-8")
        self.assertEqual(0, self.run_check(str(self.build), "--image", "controller").returncode)
        self.assertEqual(2, self.run_check(str(self.build)).returncode)

    def test_the_script_reads_only(self):
        self.write(good("good-mcuboot.config"), good("good-app.config"))
        before = sorted(str(path) for path in self.tmp.rglob("*"))
        self.run_check(str(self.build))
        self.assertEqual(before, sorted(str(path) for path in self.tmp.rglob("*")))


class AgreementTest(unittest.TestCase):
    """The names the check reads are the names the existing build check and the page already use."""

    def test_the_build_check_greps_the_same_bootloader_options(self):
        build_check = (REPO / "scripts/test-boot-composition.sh").read_text(encoding="utf-8")
        for option in ("CONFIG_BOOT_RAM_LOAD=y", "CONFIG_BOOT_RAM_LOAD_REVERT=y"):
            self.assertIn(option, build_check)
        self.assertEqual(
            {"CONFIG_BOOT_RAM_LOAD": "y", "CONFIG_BOOT_RAM_LOAD_REVERT": "y"},
            dict(CHECK["BOOTLOADER_REQUIRED"]),
        )

    def test_the_build_check_passes_the_sysbuild_mode_the_check_assumes(self):
        build_check = (REPO / "scripts/test-boot-composition.sh").read_text(encoding="utf-8")
        self.assertIn("-DSB_CONFIG_MCUBOOT_MODE_RAM_LOAD_WITH_REVERT=y", build_check)
        self.assertEqual(
            {"CONFIG_MCUBOOT_BOOTLOADER_MODE_RAM_LOAD_WITH_REVERT": "y"},
            dict(CHECK["APPLICATION_REQUIRED"]),
        )

    def test_the_forbidden_option_is_the_one_the_proposal_names(self):
        proposal = (REPO / "docs/plans/image-state-contract-proposal.md").read_text(encoding="utf-8")
        self.assertIn("MCUBOOT_VERSION_CMP_USE_BUILD_NUMBER", proposal)
        self.assertEqual(("CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER",), tuple(CHECK["FORBIDDEN"]))


if __name__ == "__main__":
    unittest.main()
