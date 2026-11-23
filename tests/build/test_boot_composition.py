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
            self.assertEqual((TRIAL / trial).read_bytes(), (BOARD_DIR / name).read_bytes(), f"{name} differs from {trial}")

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
            self.assertIn(argument, self.code)

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
        self.assertIn("root-ec-p256.pem", self.code)
        self.assertIn("verify", self.code)
        self.assertIn("Traceback", self.code)

    def test_the_application_configuration_is_read_from_its_own_build_directory(self):
        # The sysbuild directory also holds a zephyr/.config of its own, so a search by name can
        # return the wrong file (it did in the first CI run). The path must be explicit.
        self.assertIn('app_config="$build/$image/zephyr/.config"', self.code)
        self.assertNotIn("-name .config", self.code)

    def test_the_runtime_shard_runs_the_script(self):
        text = read(ZEPHYR_WORKFLOW)
        match = re.search(r"- name: [^\n]*\n(?:(?!      - ).*\n)*?.*scripts/test-boot-composition\.sh", text)
        self.assertIsNotNone(match, "zephyr.yml does not run scripts/test-boot-composition.sh")
        step = match.group(0)
        self.assertIn("if: matrix.shard == 'runtime'", step)

class BuildCheckWiringTest(unittest.TestCase):
    """The board-free checks that read the build output are called by the composition script.

    They were merged as separate tools (scripts/check-boot-config.py, tests/target/check_boot_images.sh) and
    did nothing in CI until this script called them. The script itself needs Linux, west and a build, so
    these rules read it as text, like the rules of BuildCheckTest.
    """

    def setUp(self):
        self.script = read(SCRIPT)
        self.code = "\n".join(l for l in self.script.splitlines() if not l.lstrip().startswith("#"))

    def position(self, text):
        index = self.code.find(text)
        self.assertNotEqual(-1, index, f"the script does not contain: {text}")
        return index

    def test_the_script_runs_the_build_configuration_check_on_its_own_build(self):
        self.assertIn(
            '"$python" "$repo/scripts/check-boot-config.py" "$build" --image "$image" ||', self.code)
        self.assertIn("the boot build configuration check failed", self.code)

    def test_the_configuration_check_runs_after_the_configurations_it_reads_exist(self):
        # It reads both .config files, so it follows the lines that already insist on them.
        call = self.position("check-boot-config.py")
        self.assertLess(self.position('[[ -f "$config" ]]'), call)
        self.assertLess(self.position('[[ -f "$app_config" ]]'), call)

    def test_the_script_requires_the_padded_confirmed_image_of_the_slot_size(self):
        # docs/secure-boot-board-test-procedure.md section 4 step 4 hands this file to the bench. The
        # explicit path avoids the search by name that returned a wrong file once (see above).
        self.assertIn('confirmed="$build/$image/zephyr/zephyr.signed.confirmed.bin"', self.code)
        self.assertIn("slot_size=3145728", self.code)
        self.assertIn('[[ -f "$confirmed" ]]', self.code)
        self.assertIn('"$(stat -c %s "$confirmed")" -eq "$slot_size"', self.code)

    def test_the_slot_size_is_the_one_the_image_check_and_the_procedure_use(self):
        images = read(REPO / "tests/target/check_boot_images.sh")
        self.assertIn("slot_size=3145728", images)
        procedure = read(REPO / "docs/secure-boot-board-test-procedure.md")
        self.assertIn("`<app-out>/zephyr.signed.confirmed.bin` | 3,145,728 B, the slot size", procedure)

    def test_the_script_runs_the_image_check_on_its_own_build_with_its_own_tools(self):
        self.assertIn(
            'CRUX_PYTHON="$python" CRUX_WORKSPACE="$workspace" "$repo/tests/target/check_boot_images.sh" "$build" ||',
            self.code)
        self.assertIn("the boot image check failed", self.code)
        self.assertTrue((REPO / "tests/target/check_boot_images.sh").stat().st_mode & 0o111)

    def test_the_image_check_runs_after_the_images_are_signed_verified_and_confirmed(self):
        call = self.position("check_boot_images.sh")
        self.assertLess(self.position("imgtool.py\" verify"), call)
        self.assertLess(self.position("zephyr.signed.confirmed.bin"), call)
        self.assertLess(self.position("check-boot-config.py"), call)

    def test_the_new_checks_come_before_the_final_report(self):
        report = self.position("Boot composition: MCUboot")
        self.assertLess(self.position("check_boot_images.sh"), report)
        self.assertLess(self.position("check-boot-config.py"), report)

    def test_the_config_check_header_says_who_calls_it_and_that_the_edit_is_approved(self):
        header = read(REPO / "scripts/check-boot-config.py").split('"""')[1]
        self.assertIn("scripts/test-boot-composition.sh calls it", header)
        self.assertIn("approved by the project owner on 2026-11-16", header)
        self.assertNotIn("pending", header)

    def test_the_tests_readme_does_not_call_the_wiring_pending(self):
        readme = read(REPO / "tests/README.md")
        self.assertNotIn("pending the owner's approval", readme)
        self.assertIn("check_boot_images.sh", readme)
        self.assertIn("check-boot-config.py", readme)
        self.assertIn("recorded in the header of each of those two scripts", readme)

    def test_no_existing_check_of_the_script_was_dropped(self):
        # The wiring is additive (belt and braces with the inline greps, as the proposal recommends).
        for line in (
            "CONFIG_BOOT_RAM_LOAD=y",
            "CONFIG_BOOT_RAM_LOAD_REVERT=y",
            "CONFIG_RETENTION_BOOTLOADER_INFO_TYPE_MCUBOOT=y",
            "expect_refused",
        ):
            self.assertIn(line, self.code)

    def test_the_script_still_builds_nothing_extra_and_never_touches_a_board(self):
        for forbidden in ("west flash", "west debug", "openocd", "pyocd", "JLink", " keygen"):
            self.assertNotIn(forbidden, self.code)

    def test_the_procedure_no_longer_says_the_ci_check_ignores_the_confirmed_image(self):
        procedure = read(REPO / "docs/secure-boot-board-test-procedure.md")
        self.assertNotIn("The CI check does not test for this file", procedure)
        self.assertIn("zephyr.signed.confirmed.bin", procedure)

    def test_the_documents_say_that_the_composition_script_calls_the_image_check(self):
        for name in ("docs/boot-image-inspection.md", "docs/boot-overview.md", "docs/boot-composition.md",
                     "docs/secure-boot-and-update-review.md"):
            text = read(REPO / name)
            # The owner approved the protected-path edits on 2026-11-16 (#489); the pages say so and no
            # longer say that the approval is pending.
            self.assertIn("approved by the owner on 2026-11-16", text, name)
            self.assertNotIn("pending the owner's approval", text, name)
            # The reproducibility check is still unwired, so only the image check's statements are refused.
            self.assertNotIn("check against the real build output is prepared there and not wired into CI", text, name)
            self.assertNotIn("`imgtool sign` is prepared and not wired", text, name)
            self.assertNotIn("**not wired into CI** and has never run on a real build (#467)", text, name)


if __name__ == "__main__":
    unittest.main()
