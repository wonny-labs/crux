#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the shape of tests/target/compare-mcuboot-crypto-backends.sh and of its variant files.

The script builds the RT1060-EVK Rev B RAM load composition of docs/boot-composition.md once for each
ECDSA P-256 backend of MCUboot and reports the sizes. It needs the Linux Dev Container (west, the Zephyr
SDK, network access), so a Host test cannot run it; these rules read files only, like the neighbouring
tests of the boot scripts. They keep the script to what its record promises: the same argument set as the
composition check, one variant file per backend, no hardware, no key generation and no change of the
manifest. What the builds show is in docs/plans/mcuboot-crypto-backend-comparison.md and comes from a CI
run, not from these tests. The standard library only.
"""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "tests/target/compare-mcuboot-crypto-backends.sh"
VARIANTS = REPO / "tests/target/mcuboot-crypto"
COMPOSITION = REPO / "scripts/test-boot-composition.sh"
WEST = REPO / "west.yml"


class ScriptShape(unittest.TestCase):
    def setUp(self):
        self.script = SCRIPT.read_text(encoding="utf-8") if SCRIPT.is_file() else ""
        self.code = "\n".join(l for l in self.script.splitlines() if not l.lstrip().startswith("#"))
        self.header = "\n".join(l for l in self.script.splitlines() if l.startswith("#"))

    def test_the_script_exists_is_executable_and_not_under_scripts(self):
        self.assertTrue(SCRIPT.is_file(), f"{SCRIPT} is missing")
        self.assertTrue(SCRIPT.stat().st_mode & 0o111)
        self.assertTrue(self.script.startswith("#!/usr/bin/env bash\n"))
        self.assertFalse((REPO / "scripts" / SCRIPT.name).exists())

    def test_the_script_uses_strict_mode_and_needs_the_linux_environment(self):
        self.assertIn("set -euo pipefail", self.code.splitlines())
        self.assertIn('uname -s', self.code)
        self.assertIn("exit 2", self.code)

    def test_the_script_builds_the_argument_set_of_the_composition_check(self):
        for argument in (
            "--sysbuild",
            "SB_CONFIG_BOOTLOADER_MCUBOOT=y",
            "SB_CONFIG_MCUBOOT_MODE_RAM_LOAD_WITH_REVERT=y",
            "SB_CONFIG_BOOT_SIGNATURE_TYPE_ECDSA_P256=y",
            "mcuboot_EXTRA_DTC_OVERLAY_FILE=",
            "_EXTRA_CONF_FILE=",
            "_EXTRA_DTC_OVERLAY_FILE=",
            "mimxrt1060_evk@B//qspi",
        ):
            self.assertIn(argument, self.code)
            self.assertIn(argument, COMPOSITION.read_text(encoding="utf-8"), argument)
        # The same four board files as the composition check.
        self.assertIn("zephyr/boot/boards/mimxrt1060_evk_mimxrt1062_qspi_B", self.code)

    def test_the_script_never_programs_a_board_generates_a_key_or_edits_the_manifest(self):
        for word in ("keygen", "flash", "debug", "openocd", "pyocd", "JLink", "probe", "reset", "docker"):
            self.assertIsNone(re.search(rf"\b{word}\b", self.code), word)
        self.assertNotIn("west.yml", self.code)
        self.assertNotIn("west manifest", self.code)
        self.assertNotIn("SB_CONFIG_BOOT_SIGNATURE_KEY_FILE", self.code)

    def test_the_script_fetches_only_the_two_crypto_projects_and_enables_their_group(self):
        # The group is off by default because it also holds GPL stacks; the script names the two Apache-2.0
        # projects and must never run a plain `west update` after enabling the group.
        self.assertIn("+crux-secure-management", self.code)
        self.assertIn("west update mbedtls tf-psa-crypto", self.code)
        for line in self.code.splitlines():
            if "west update" in line:
                self.assertRegex(line, r"west update (mcuboot|mbedtls tf-psa-crypto)\b", line)
        for stack in ("wolfssl", "wolfssh", "wolfpsa"):
            self.assertNotIn(stack, self.code)
        west = WEST.read_text(encoding="utf-8")
        self.assertIn("name: mbedtls", west)
        self.assertIn("name: tf-psa-crypto", west)

    def test_the_baseline_is_built_before_the_crypto_modules_are_fetched(self):
        baseline = self.code.index("run_variant tinycrypt-modules-absent")
        fetch = self.code.index("west update mbedtls tf-psa-crypto")
        later = self.code.index("run_variant tinycrypt-modules-present")
        self.assertLess(baseline, fetch)
        self.assertLess(fetch, later)

    def test_the_script_does_not_estimate_boot_time(self):
        self.assertRegex(self.header, r"not measured")
        self.assertIn("not measured", self.script)
        self.assertNotRegex(self.code, r"\bms\b|milliseconds|seconds")

    def test_the_header_says_it_is_unwired_and_not_a_check(self):
        self.assertRegex(self.header, r"NOT wired")
        self.assertRegex(self.header, r"one-off|decision input|not a regression check")

    def test_a_failed_variant_does_not_stop_the_comparison(self):
        self.assertIn("status=failed", self.code)
        self.assertRegex(self.code, r"run_variant\(\)")


class VariantFiles(unittest.TestCase):
    def test_each_backend_has_a_variant_file_that_selects_it_by_the_pinned_kconfig_choice(self):
        # The choice BOOT_ECDSA_IMPLEMENTATION of boot/zephyr/Kconfig at MCUboot 6d3b3d2c (read on
        # 15 November 2026): tinycrypt is the default, the other options are these symbols.
        expected = {
            "mbedtls-legacy.conf": "CONFIG_BOOT_ECDSA_MBEDTLS=y",
            "psa.conf": "CONFIG_BOOT_ECDSA_PSA=y",
            "psa-mbedtls.conf": "CONFIG_BOOT_ECDSA_PSA=y",
            "psa-mbedtls-entropy.conf": "CONFIG_BOOT_ECDSA_PSA=y",
        }
        for name, line in expected.items():
            path = VARIANTS / name
            self.assertTrue(path.is_file(), f"{path} is missing")
            self.assertIn(line, path.read_text(encoding="utf-8").splitlines())

    def test_the_psa_variants_add_the_zephyr_module_symbol_that_the_first_build_showed_missing(self):
        # The first CI run of psa.conf failed with "psa/crypto.h: No such file or directory": Zephyr's
        # modules/mbedtls/CMakeLists.txt (v4.4.2) adds the TF-PSA-Crypto include directories only when
        # CONFIG_MBEDTLS is set, and BOOT_ECDSA_PSA does not select it.
        for name in ("psa-mbedtls.conf", "psa-mbedtls-entropy.conf"):
            self.assertIn("CONFIG_MBEDTLS=y", (VARIANTS / name).read_text(encoding="utf-8").splitlines())
        self.assertIn("CONFIG_ENTROPY_GENERATOR=y",
                      (VARIANTS / "psa-mbedtls-entropy.conf").read_text(encoding="utf-8").splitlines())
        self.assertNotIn("CONFIG_MBEDTLS=y", (VARIANTS / "psa.conf").read_text(encoding="utf-8").splitlines())

    def test_the_variant_files_hold_only_configuration_lines_and_comments(self):
        for path in sorted(VARIANTS.glob("*.conf")):
            for line in path.read_text(encoding="utf-8").splitlines():
                self.assertTrue(not line.strip() or line.startswith("#") or re.fullmatch(r"CONFIG_\w+=\S+", line),
                                f"{path.name}: {line!r}")

    def test_no_variant_file_changes_the_signature_type_or_the_key(self):
        for path in sorted(VARIANTS.glob("*.conf")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("BOOT_SIGNATURE_TYPE", text)
            self.assertNotIn("KEY_FILE", text)

    def test_the_script_names_every_variant_file(self):
        script = SCRIPT.read_text(encoding="utf-8") if SCRIPT.is_file() else ""
        for path in sorted(VARIANTS.glob("*.conf")):
            self.assertIn(path.name, script, path.name)


if __name__ == "__main__":
    unittest.main()
