"""Check the board files of the boot composition and the build check that uses them.

The composition is MCUboot RAM load with revert on the RT1060-EVK Rev B (build only). Its four
board-level files live in `zephyr/boot/boards/<board>/` (owner decision of 9 November 2026,
option B; docs/boot-composition.md). These rules read files only and use the standard library,
because `host.yml` runs this directory without west or PyYAML. The build itself runs in
`scripts/test-boot-composition.sh`, wired into the `runtime` shard of `zephyr.yml`.
"""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[2]
BOARD = "mimxrt1060_evk_mimxrt1062_qspi_B"
BOARD_DIR = REPO / "zephyr/boot/boards" / BOARD
TRIAL = REPO / "docs/evidence/boot-update/trial-inputs"
PAGE = REPO / "docs/boot-composition.md"
SCRIPT = REPO / "scripts/test-boot-composition.sh"
ZEPHYR_WORKFLOW = REPO / ".github/workflows/zephyr.yml"
# The files of the argument set and the trial inputs of #141 build A that they were taken from.
FILES = {
    "mcuboot.conf": "build-a-mcuboot.conf",
    "mcuboot.overlay": "build-a-mcuboot.overlay",
    "app.conf": "build-a-app.conf",
    "app.overlay": "build-a-app.overlay",
}


def read(path):
    return path.read_text(encoding="utf-8")


class BoardFilesTest(unittest.TestCase):
    def test_the_four_files_exist(self):
        for name in FILES:
            self.assertTrue((BOARD_DIR / name).is_file(), f"{BOARD_DIR / name} is missing")

    def test_the_files_are_the_trial_inputs_the_evidence_built(self):
        # The #141 trial and the WP1a build used these contents. Changing one needs a new build
        # result, so a difference must be a deliberate edit of this test as well.
        for name, trial in FILES.items():
            self.assertEqual(read(TRIAL / trial), read(BOARD_DIR / name), f"{name} differs from {trial}")

    def test_mcuboot_executes_from_sdram_and_shares_boot_information(self):
        config = read(BOARD_DIR / "mcuboot.conf")
        for line in (
            "CONFIG_BOOT_IMAGE_EXECUTABLE_RAM_START=0x80000000",
            "CONFIG_BOOT_IMAGE_EXECUTABLE_RAM_SIZE=33554432",
            "CONFIG_BOOT_SHARE_DATA=y",
            "CONFIG_BOOT_SHARE_BACKEND_RETENTION=y",
        ):
            self.assertIn(line, config.splitlines())

    def test_both_images_reserve_the_same_retained_region(self):
        regions = []
        for name in ("mcuboot.overlay", "app.overlay"):
            text = read(BOARD_DIR / name)
            self.assertIn("reg = <0x2027ff00 0x100>;", text, name)
            self.assertIn("reg = <0x20200000 0x7ff00>;", text, name)
            regions.append(re.findall(r"reg = <[^>]+>;", text))
        self.assertEqual(regions[0], regions[1])

    def test_the_application_asks_for_the_bootloader_information(self):
        config = read(BOARD_DIR / "app.conf").splitlines()
        self.assertIn("CONFIG_RETENTION_BOOTLOADER_INFO_TYPE_MCUBOOT=y", config)

    def test_no_key_or_certificate_file_is_stored_beside_the_files(self):
        suffixes = {".pem", ".key", ".der", ".crt", ".p12", ".pfx"}
        stored = [p for p in (REPO / "zephyr/boot").rglob("*") if p.suffix.lower() in suffixes]
        self.assertEqual([], stored)
        for path in (REPO / "zephyr/boot").rglob("*"):
            if path.is_file():
                self.assertNotIn("PRIVATE KEY", read(path), str(path))


class PageTest(unittest.TestCase):
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
            self.assertIn(argument, self.script)

    def test_the_script_keeps_to_the_public_test_key_and_the_group(self):
        # The page publishes the argument set without a key argument and without
        # -DEXTRA_ZEPHYR_MODULES, so the check must not add either.
        self.assertNotIn("SB_CONFIG_BOOT_SIGNATURE_KEY_FILE", self.code)
        self.assertNotIn("-DEXTRA_ZEPHYR_MODULES", self.code)
        self.assertIn("+crux-boot", self.code)

    def test_the_script_never_programs_or_generates_a_key(self):
        for forbidden in ("imgtool.py keygen", " keygen", "west flash", "west debug", "openocd", "pyocd", "JLink"):
            self.assertNotIn(forbidden, self.code)

    def test_the_script_signs_and_verifies_with_the_public_test_key(self):
        self.assertIn("root-ec-p256.pem", self.script)
        self.assertIn("verify", self.script)

    def test_the_runtime_shard_runs_the_script(self):
        text = read(ZEPHYR_WORKFLOW)
        match = re.search(r"- name: [^\n]*\n(?:(?!      - ).*\n)*?.*scripts/test-boot-composition\.sh", text)
        self.assertIsNotNone(match, "zephyr.yml does not run scripts/test-boot-composition.sh")
        step = match.group(0)
        self.assertIn("if: matrix.shard == 'runtime'", step)


if __name__ == "__main__":
    unittest.main()
