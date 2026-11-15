"""Check the board files of the RT1170-EVK boot composition and the build check that uses them.

The composition is MCUboot RAM load with revert on the RT1170-EVK (`mimxrt1170_evk@A//cm7`),
build only. It mirrors the RT1060-EVK Rev B composition (`test_boot_composition.py`). Its values
are PROPOSED STARTING VALUES from the RT1170 design note, "RT1170-EVK boot composition:
memory-map choices", which the owner has not accepted yet. They are corrected by the first CI
build. These rules read files only and use the standard library, because `host.yml` runs this
directory without west or PyYAML. No build ran for this board.
"""
from pathlib import Path
import os
import re
import unittest

REPO = Path(__file__).resolve().parents[2]
BOARD = "mimxrt1170_evk_mimxrt1176_cm7_A"
BOARD_DIR = REPO / "zephyr/boot/boards" / BOARD
PAGE = REPO / "docs/boot-composition-rt1170.md"
SCRIPT = REPO / "scripts/test-boot-composition-rt1170.sh"
ZEPHYR_WORKFLOW = REPO / ".github/workflows/zephyr.yml"
FILES = ("mcuboot.conf", "mcuboot.overlay", "app.conf", "app.overlay")

# Starting values of the design note. ocram2 is `ocram@202c0000`, 512 KiB, in nxp_rt1170.dtsi.
OCRAM2_START = 0x202C0000
OCRAM2_SIZE = 512 * 1024
RETAINED_SIZE = 0x100
RETAINED_START = OCRAM2_START + OCRAM2_SIZE - RETAINED_SIZE
TRIMMED_OCRAM2_SIZE = OCRAM2_SIZE - RETAINED_SIZE
SDRAM_START = 0x80000000
SDRAM_SIZE = 64 * 1024 * 1024


def read(path):
    return path.read_text(encoding="utf-8")


def reg_cells(text):
    """Return every `reg = <a b>;` of a devicetree text as a tuple of integers."""
    return [tuple(int(v, 16) for v in m.split()) for m in re.findall(r"reg = <([^>]+)>;", text)]


class ArithmeticTest(unittest.TestCase):
    def test_the_starting_values_agree_with_each_other(self):
        self.assertEqual(0x2033FF00, RETAINED_START)
        self.assertEqual(0x7FF00, TRIMMED_OCRAM2_SIZE)
        self.assertEqual(67108864, SDRAM_SIZE)


class BoardFilesTest(unittest.TestCase):
    def test_the_four_files_exist(self):
        for name in FILES:
            self.assertTrue((BOARD_DIR / name).is_file(), f"{BOARD_DIR / name} is missing")

    def test_the_files_say_that_the_values_are_starting_values(self):
        for name in FILES:
            text = read(BOARD_DIR / name)
            self.assertIn("starting value", text.lower(), name)
            self.assertIn("first CI build", text, name)

    def test_mcuboot_executes_from_sdram_and_shares_boot_information(self):
        lines = read(BOARD_DIR / "mcuboot.conf").splitlines()
        for line in (
            f"CONFIG_BOOT_IMAGE_EXECUTABLE_RAM_START={SDRAM_START:#x}",
            f"CONFIG_BOOT_IMAGE_EXECUTABLE_RAM_SIZE={SDRAM_SIZE}",
            "CONFIG_RETAINED_MEM=y",
            "CONFIG_RETENTION=y",
            "CONFIG_BOOT_SHARE_DATA=y",
            "CONFIG_BOOT_SHARE_DATA_BOOTINFO=y",
            "CONFIG_BOOT_SHARE_BACKEND_RETENTION=y",
        ):
            self.assertIn(line, lines)

    def test_both_overlays_declare_the_same_retained_region(self):
        regions = []
        for name in ("mcuboot.overlay", "app.overlay"):
            text = read(BOARD_DIR / name)
            cells = reg_cells(text)
            # The retained node and its boot-information child, then the trimmed ocram2.
            self.assertIn((RETAINED_START, RETAINED_SIZE), cells, name)
            self.assertIn((0x0, RETAINED_SIZE), cells, name)
            self.assertIn(f"sram@{RETAINED_START:x}", text, name)
            self.assertIn(f"ranges = <0x0 {RETAINED_START:#x} {RETAINED_SIZE:#x}>;", text, name)
            regions.append(cells)
        self.assertEqual(regions[0], regions[1])

    def test_both_overlays_trim_ocram2_by_exactly_the_retained_region(self):
        for name in ("mcuboot.overlay", "app.overlay"):
            text = read(BOARD_DIR / name)
            match = re.search(r"&ocram2\s*\{\s*reg = <([^>]+)>;", text)
            self.assertIsNotNone(match, f"{name} does not trim &ocram2")
            start, size = (int(v, 16) for v in match.group(1).split())
            self.assertEqual(OCRAM2_START, start, name)
            self.assertEqual(TRIMMED_OCRAM2_SIZE, size, name)
            # The trimmed region ends where the retained region begins, with no gap or overlap.
            self.assertEqual(RETAINED_START, start + size, name)

    def test_mcuboot_runs_from_the_trimmed_ocram2(self):
        text = read(BOARD_DIR / "mcuboot.overlay")
        self.assertRegex(text, r"zephyr,sram = &ocram2;")

    def test_the_application_keeps_its_own_ram_and_asks_for_the_bootloader_information(self):
        self.assertNotIn("zephyr,sram", read(BOARD_DIR / "app.overlay"))
        config = read(BOARD_DIR / "app.conf").splitlines()
        for line in (
            "CONFIG_RETAINED_MEM=y",
            "CONFIG_RETENTION=y",
            "CONFIG_RETENTION_BOOTLOADER_INFO=y",
            "CONFIG_RETENTION_BOOTLOADER_INFO_TYPE_MCUBOOT=y",
        ):
            self.assertIn(line, config)

    def test_the_retained_region_lies_outside_the_load_window(self):
        # The image is loaded into the SDRAM, and the retained region must survive the load.
        self.assertFalse(SDRAM_START <= RETAINED_START < SDRAM_START + SDRAM_SIZE)

    def test_no_key_or_certificate_file_is_stored_under_zephyr_boot(self):
        suffixes = {".pem", ".key", ".der", ".crt", ".p12", ".pfx"}
        stored = [p for p in (REPO / "zephyr/boot").rglob("*") if p.suffix.lower() in suffixes]
        self.assertEqual([], stored)
        for path in (REPO / "zephyr/boot").rglob("*"):
            if path.is_file():
                self.assertNotIn("PRIVATE KEY", read(path), str(path))


class PageTest(unittest.TestCase):
    def test_the_page_exists_and_is_marked_proposed(self):
        text = read(PAGE)
        self.assertIn("> **Status:**", text)
        self.assertIn("proposed", text.lower())

    def test_the_argument_set_names_files_that_exist(self):
        named = set(re.findall(r"zephyr/boot/boards/%s/([\w.]+)" % re.escape(BOARD), read(PAGE)))
        self.assertEqual(set(FILES), named)
        for name in named:
            self.assertTrue((BOARD_DIR / name).is_file(), name)


class BuildCheckTest(unittest.TestCase):
    def setUp(self):
        self.script = read(SCRIPT)
        # Comments may name what the script avoids, so the rules that forbid a word read code only.
        self.code = "\n".join(l for l in self.script.splitlines() if not l.lstrip().startswith("#"))

    def test_the_script_is_executable(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_the_script_targets_the_rt1170_files_and_build_directory(self):
        self.assertIn("'mimxrt1170_evk@A//cm7'", self.code)
        self.assertIn("zephyr/boot/boards/mimxrt1170_evk_mimxrt1176_cm7_A", self.code)
        self.assertIn("build/zephyr/boot-composition-rt1170", self.code)

    def test_the_script_builds_the_published_argument_set(self):
        for argument in (
            "--sysbuild",
            "SB_CONFIG_BOOTLOADER_MCUBOOT=y",
            "SB_CONFIG_MCUBOOT_MODE_RAM_LOAD_WITH_REVERT=y",
            "SB_CONFIG_BOOT_SIGNATURE_TYPE_ECDSA_P256=y",
            "mcuboot_EXTRA_CONF_FILE=",
            "mcuboot_EXTRA_DTC_OVERLAY_FILE=",
            "_EXTRA_CONF_FILE=",
            "_EXTRA_DTC_OVERLAY_FILE=",
        ):
            self.assertIn(argument, self.code)

    def test_the_script_checks_the_window_it_configures(self):
        self.assertIn(f"CONFIG_BOOT_IMAGE_EXECUTABLE_RAM_START={SDRAM_START:#x}", self.code)
        self.assertIn(f"CONFIG_BOOT_IMAGE_EXECUTABLE_RAM_SIZE={SDRAM_SIZE}", self.code)

    def test_the_script_has_no_key_argument_and_no_module_argument(self):
        # No key argument and no -DEXTRA_ZEPHYR_MODULES, as in the RT1060 recipe.
        self.assertNotIn("SB_CONFIG_BOOT_SIGNATURE_KEY_FILE", self.code)
        self.assertNotIn("-DEXTRA_ZEPHYR_MODULES", self.code)
        self.assertIn("+crux-boot", self.code)

    def test_the_script_never_programs_or_generates_a_key(self):
        for forbidden in ("imgtool.py keygen", " keygen", "west flash", "west debug", "openocd", "pyocd", "JLink"):
            self.assertNotIn(forbidden, self.code)

    def test_the_script_signs_and_verifies_with_the_public_test_key(self):
        self.assertIn("root-ec-p256.pem", self.code)
        self.assertIn("verify", self.code)
        self.assertIn("Traceback", self.code)
        self.assertIn("root-rsa-2048.pem", self.code)

    def test_the_script_checks_that_modified_images_are_refused(self):
        self.assertIn("expect_refused", self.code)
        self.assertIn("0x300 0x500", self.code)

    def test_the_application_configuration_is_read_from_its_own_build_directory(self):
        self.assertIn('app_config="$build/$image/zephyr/.config"', self.code)
        self.assertNotIn("-name .config", self.code)

    def test_the_application_directory_comes_from_the_environment_with_the_controller_sample_as_default(self):
        # Open point D2: the controller sample has no RT1170 board configuration.
        self.assertIn("CRUX_BOOT_RT1170_APP:-$repo/samples/controller/zephyr", self.code)
        self.assertIn("CRUX_BOOT_RT1170_APP", self.script.split("set -euo pipefail")[0])

    def test_the_script_is_linux_only(self):
        self.assertIn('uname -s', self.code)
        self.assertIn("exit 2", self.code)


class WorkflowTest(unittest.TestCase):
    def test_the_workflow_does_not_run_the_rt1170_check_yet(self):
        # The CI step is open point D3 and `.github/workflows/zephyr.yml` is a protected path.
        # THIS TEST MUST BE CHANGED, to require the step, when the owner approves the CI step.
        text = read(ZEPHYR_WORKFLOW)
        self.assertNotIn("test-boot-composition-rt1170", text)


if __name__ == "__main__":
    unittest.main()
