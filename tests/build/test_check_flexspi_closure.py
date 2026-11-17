"""The FlexSPI write-path closure check (#165) must find a NOR reference reachable from the write path.

The NOR literal in the first fixture is synthetic: the real edge of Stage 6 is a load through the device record
(`ldr r3, [r0, #4]`), which the device-record check covers, not a pool literal.

HOST-TESTED ONLY. These rules run the check on small fixtures: `nm` and `objdump -d` text and a tiny ELF
that the test builds. They show that the check finds the edges it is written to find and passes a
fixture that has none. They show nothing about a real MCUboot image, and a pass of the check on a real
image shows the absence of those edges only, not closure of the #22 matrix.
"""
import hashlib
import runpy
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/check-flexspi-closure.py"
CHECK = runpy.run_path(str(SCRIPT))

NM_BAD = """\
00000e00 T flash_flexspi_nor_wait_bus_busy
00000f00 T memc_flexspi_transfer
00001000 T flash_flexspi_nor_write
00001100 T flash_flexspi_nor_erase
60008000 T crux_log_in_nor
6000bfd8 R memc_flexspi_config_0
6000c000 R __device_dts_ord_546
60002000 T _vector_table
60005fb0 T z_arm_fault
"""

DISASM_BAD = """\
00000e00 <flash_flexspi_nor_wait_bus_busy>:
 e00:\tb510      \tpush\t{r4, lr}
 e02:\tf000 f87d \tbl\tf00 <memc_flexspi_transfer>
 e06:\t4770      \tbx\tlr

00000f00 <memc_flexspi_transfer>:
 f00:\tb570      \tpush\t{r4, r5, r6, lr}
 f02:\t4b05      \tldr\tr3, [pc, #20]\t@ (f18 <memc_flexspi_transfer+0x18>)
 f04:\t685b      \tldr\tr3, [r3, #4]
 f06:\t4798      \tblx\tr3
 f08:\tbd70      \tpop\t{r4, r5, r6, pc}
 f18:\t6000bfd8 \t.word\t0x6000bfd8

00001000 <flash_flexspi_nor_write>:
 1000:\tf7ff fefe \tbl\te00 <flash_flexspi_nor_wait_bus_busy>
 1004:\tf000 f800 \tbl\t8000 <crux_log_in_nor>
 1008:\t4770      \tbx\tlr

00001100 <flash_flexspi_nor_erase>:
 1100:\tf7ff fe7e \tbl\te00 <flash_flexspi_nor_wait_bus_busy>
 1104:\tb480      \tpush\t{r7}
 1106:\t4770      \tbx\tlr
"""

NM_GOOD = NM_BAD.replace("6000bfd8 R memc_flexspi_config_0", "00002160 D memc_flexspi_config_0").replace(
    "60008000 T crux_log_in_nor\n", ""
)
DISASM_GOOD = (
    DISASM_BAD.replace("6000bfd8", "00002160")
    .replace(" 1004:\tf000 f800 \tbl\t8000 <crux_log_in_nor>\n", "")
    .replace(" f06:\t4798      \tblx\tr3\n", "")
)


def elf_with_words(base, words):
    """A minimal 32-bit little-endian ARM ELF with one loadable segment at `base` holding `words`."""
    payload = b"".join(struct.pack("<I", w) for w in words)
    header = struct.pack(
        "<16sHHIIIIIHHHHHH", b"\x7fELF\x01\x01\x01" + b"\0" * 9, 2, 40, 1, 0, 52, 0, 0, 52, 32, 1, 40, 0, 0
    )
    phdr = struct.pack("<IIIIIIII", 1, 84, base, base, len(payload), len(payload), 5, 4)
    return header + phdr + payload


class ParseTest(unittest.TestCase):
    def test_nm_symbols(self):
        symbols = CHECK["parse_nm"](NM_BAD)
        self.assertEqual(0x6000BFD8, symbols["memc_flexspi_config_0"])
        self.assertEqual(0xE00, symbols["flash_flexspi_nor_wait_bus_busy"])

    def test_disassembly_edges_literals_and_indirect_branches(self):
        functions = CHECK["parse_objdump"](DISASM_BAD)
        busy = functions["flash_flexspi_nor_wait_bus_busy"]
        self.assertEqual({"memc_flexspi_transfer"}, busy.calls)
        transfer = functions["memc_flexspi_transfer"]
        self.assertEqual([0x6000BFD8], transfer.literals)
        self.assertEqual(1, transfer.indirect)
        self.assertEqual(0, busy.indirect, "bx lr is a return")

    def test_region_names(self):
        region = CHECK["region"]
        self.assertEqual("NOR", region(0x6000BFD8))
        self.assertEqual("ITCM", region(0x2160))
        self.assertEqual("SDRAM", region(0x80000100))
        self.assertEqual("OCRAM", region(0x20200010))
        self.assertEqual("PERIPHERAL", region(0x402A8000))


class ClosureTest(unittest.TestCase):
    ROOTS = ["flash_flexspi_nor_write", "flash_flexspi_nor_erase"]

    def run_check(self, nm, disasm, roots=None):
        return CHECK["check_closure"](
            CHECK["parse_nm"](nm), CHECK["parse_objdump"](disasm), roots or self.ROOTS, allow=set()
        )

    def test_the_bad_fixture_reports_the_nor_literal_the_nor_call_and_the_indirect_branch(self):
        errors = self.run_check(NM_BAD, DISASM_BAD)
        text = "\n".join(errors)
        self.assertIn("0x6000bfd8", text)
        self.assertIn("memc_flexspi_config_0", text)
        self.assertIn("crux_log_in_nor", text)
        self.assertIn("indirect", text)

    def test_the_good_fixture_has_no_finding(self):
        self.assertEqual([], self.run_check(NM_GOOD, DISASM_GOOD))

    def test_an_allowed_symbol_is_not_a_finding(self):
        errors = CHECK["check_closure"](
            CHECK["parse_nm"](NM_BAD),
            CHECK["parse_objdump"](DISASM_BAD),
            self.ROOTS,
            allow={"memc_flexspi_config_0", "crux_log_in_nor"},
        )
        self.assertFalse([e for e in errors if "memc_flexspi_config_0" in e or "crux_log_in_nor" in e])

    def test_a_function_outside_the_itcm_run_range_is_a_finding(self):
        nm = NM_GOOD.replace("00000f00 T memc_flexspi_transfer", "20000f00 T memc_flexspi_transfer")
        errors = self.run_check(nm, DISASM_GOOD)
        self.assertTrue(any("memc_flexspi_transfer" in e and "ITCM" in e for e in errors), errors)

    def test_a_missing_root_is_a_finding_not_a_silent_pass(self):
        errors = self.run_check(NM_GOOD, DISASM_GOOD, roots=["flash_flexspi_nor_missing"])
        self.assertTrue(any("flash_flexspi_nor_missing" in e for e in errors), errors)

    def test_the_configuration_object_must_not_run_in_nor(self):
        errors = CHECK["check_placement"](CHECK["parse_nm"](NM_BAD))
        self.assertTrue(any("memc_flexspi_config_0" in e and "NOR" in e for e in errors), errors)
        self.assertEqual([], CHECK["check_placement"](CHECK["parse_nm"](NM_GOOD)))


class DeviceRecordTest(unittest.TestCase):
    def test_a_record_whose_config_pointer_is_in_nor_is_a_finding(self):
        # struct device: name, config, api, ... so the config pointer is the second word.
        elf = elf_with_words(0x6000C000, [0x60009000, 0x6000BFD8, 0x6000A000])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.elf"
            path.write_bytes(elf)
            errors = CHECK["check_device_records"](CHECK["parse_nm"](NM_BAD), str(path))
        self.assertTrue(any("__device_dts_ord_546" in e and "NOR" in e for e in errors), errors)

    def test_a_record_pointing_at_a_relocated_object_passes(self):
        nm = NM_BAD.replace("6000bfd8 R memc_flexspi_config_0", "00002160 D memc_flexspi_config_0")
        elf = elf_with_words(0x6000C000, [0x60009000, 0x00002160, 0x6000A000])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.elf"
            path.write_bytes(elf)
            self.assertEqual([], CHECK["check_device_records"](CHECK["parse_nm"](nm), str(path)))

    def test_no_controller_record_is_a_finding(self):
        nm = "6000bfd8 R memc_flexspi_config_0\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.elf"
            path.write_bytes(elf_with_words(0x6000C000, [0, 0, 0]))
            errors = CHECK["check_device_records"](CHECK["parse_nm"](nm), str(path))
        self.assertTrue(errors)


class PinGuardTest(unittest.TestCase):
    def test_a_changed_upstream_file_is_a_finding_and_the_digests_are_the_poc_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in CHECK["PINNED_FILES"]:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("changed\n")
            errors = CHECK["check_pins"](str(root), str(root))
            self.assertEqual(len(CHECK["PINNED_FILES"]), len(errors), errors)
            # The expected digests are the ones of scripts/prepare-flash-poc.py.
            poc = (REPO / "scripts/prepare-flash-poc.py").read_text()
            for digest in CHECK["PINNED_FILES"].values():
                self.assertIn(digest, poc)

    def test_a_file_that_matches_its_pin_passes(self):
        original = dict(CHECK["PINNED_FILES"])
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for relative in original:
                    target = root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("pinned\n")
                    CHECK["PINNED_FILES"][relative] = hashlib.sha256(b"pinned\n").hexdigest()
                self.assertEqual([], CHECK["check_pins"](str(root), str(root)))
        finally:
            CHECK["PINNED_FILES"].clear()
            CHECK["PINNED_FILES"].update(original)

    def test_a_missing_tree_is_reported_as_not_checked_not_as_a_pass(self):
        errors, notes = CHECK["check_pins"](None, None, with_notes=True)
        self.assertEqual([], errors)
        self.assertTrue(any("not checked" in n for n in notes), notes)


class SilentPassTest(unittest.TestCase):
    """A parse miss must be a finding, not a pass (review of #165, B1-2 and B1-3)."""

    ROOTS = ["flash_flexspi_nor_write"]

    def findings(self, nm, disasm, read=None):
        return CHECK["check_closure"](
            CHECK["parse_nm"](nm), CHECK["parse_objdump"](disasm), self.ROOTS, allow=set(), read=read
        )

    def test_a_disassembly_that_parses_to_nothing_is_a_finding(self):
        unreadable = "00001000 <flash_flexspi_nor_write>:\n (no instruction in a form this check reads)\n"
        errors = self.findings("00001000 T flash_flexspi_nor_write\n", unreadable)
        self.assertTrue(any("no parsed instruction" in e for e in errors), errors)

    def test_the_llvm_form_of_a_call_and_a_pool_literal_is_read(self):
        text = (
            "00001000 <flash_flexspi_nor_write>:\n"
            "    1000: 4b01         \tldr\tr3, [pc, #4]\t@ 0x1008 <flash_flexspi_nor_write+0x8>\n"
            "    1002: f000 f800    \tbl\t0x1100 <helper>\n"
            "    1008: 6000bfd8     \t.word\t0x6000bfd8\n"
            "00001100 <helper>:\n"
            "    1100: 4770         \tbx\tlr\n"
        )
        functions = CHECK["parse_objdump"](text)
        self.assertEqual({"helper"}, functions["flash_flexspi_nor_write"].calls)
        self.assertEqual([0x6000BFD8], functions["flash_flexspi_nor_write"].literals)

    def test_the_semicolon_comment_form_of_an_older_binutils_is_read(self):
        text = (
            "00001000 <flash_flexspi_nor_write>:\n"
            " 1000:\t4b05      \tldr\tr3, [pc, #20]\t; (1018 <flash_flexspi_nor_write+0x18>)\n"
            " 1018:\t6000bfd8 \t.word\t0x6000bfd8\n"
        )
        self.assertEqual([0x6000BFD8], CHECK["parse_objdump"](text)["flash_flexspi_nor_write"].literals)

    def test_a_pool_word_the_text_does_not_show_is_read_from_the_elf_or_reported(self):
        text = (
            "00001000 <flash_flexspi_nor_write>:\n"
            " 1000:\t4b05      \tldr\tr3, [pc, #20]\t@ (1018 <flash_flexspi_nor_write+0x18>)\n"
            " 1002:\t4770      \tbx\tlr\n"
        )
        nm = "00001000 T flash_flexspi_nor_write\n"
        errors = self.findings(nm, text)
        self.assertTrue(any("no resolvable value" in e for e in errors), errors)
        errors = self.findings(nm, text, read=lambda address: 0x6000BFD8 if address == 0x1018 else None)
        self.assertTrue(any("0x6000bfd8" in e and "NOR" in e for e in errors), errors)
        self.assertEqual([], self.findings(nm, text, read=lambda address: 0x2160))

    def test_a_pc_relative_load_with_no_comment_is_reported(self):
        text = "00001000 <flash_flexspi_nor_write>:\n 1000:\tf85f f000 \tldr.w\tpc, [pc, #-0]\n"
        errors = self.findings("00001000 T flash_flexspi_nor_write\n", text)
        self.assertTrue(any("no resolvable value" in e for e in errors), errors)

    def test_a_long_branch_veneer_into_nor_is_found(self):
        # ITCM to NOR is beyond the range of bl, so the linker routes the call through a veneer whose
        # pool word is the only sign of the NOR target.
        text = (
            "00001000 <flash_flexspi_nor_write>:\n"
            " 1000:\tf000 f800 \tbl\t1100 <__flash_driver_veneer>\n"
            " 1004:\t4770      \tbx\tlr\n"
            "00001100 <__flash_driver_veneer>:\n"
            " 1100:\tf85f f004 \tldr.w\tpc, [pc, #-4]\t@ (1104 <__flash_driver_veneer+0x4>)\n"
        )
        errors = self.findings(
            "00001000 T flash_flexspi_nor_write\n00001100 t __flash_driver_veneer\n",
            text,
            read=lambda address: 0x60008001 if address == 0x1104 else None,
        )
        self.assertTrue(any("NOR" in e and "0x60008001" in e for e in errors), errors)


class CommandLineTest(unittest.TestCase):
    def run_cli(self, nm, disasm, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "nm.txt").write_text(nm)
            (root / "dis.txt").write_text(disasm)
            for name in ("nm", "objdump"):
                tool = root / name
                tool.write_text("#!/bin/sh\ncat '%s'\n" % (root / ("nm.txt" if name == "nm" else "dis.txt")))
                tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
            (root / "x.elf").write_bytes(elf_with_words(0x6000C000, [0x60009000, 0x00002160, 0x6000A000]))
            return subprocess.run(
                [sys.executable, "-I", str(SCRIPT), "--elf", str(root / "x.elf"),
                 "--nm", str(root / "nm"), "--objdump", str(root / "objdump"), *extra],
                capture_output=True, text=True,
            )

    def test_report_mode_prints_findings_and_exits_zero(self):
        result = self.run_cli(NM_BAD, DISASM_BAD)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("finding", result.stdout)
        self.assertIn("0x6000bfd8", result.stdout)

    def test_strict_mode_fails_on_findings_and_passes_on_the_good_fixture(self):
        self.assertNotEqual(0, self.run_cli(NM_BAD, DISASM_BAD, "--strict").returncode)
        good = self.run_cli(NM_GOOD, DISASM_GOOD, "--strict")
        self.assertEqual(0, good.returncode, good.stdout + good.stderr)

    def test_the_output_says_what_a_pass_does_not_show(self):
        result = self.run_cli(NM_GOOD, DISASM_GOOD, "--strict")
        self.assertIn("not closure", result.stdout)


class WiringTest(unittest.TestCase):
    """The composition script runs the check in report mode after its other checks (owner approval of 2026-11-16)."""

    def setUp(self):
        text = (REPO / "scripts/test-boot-composition.sh").read_text()
        self.code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))

    def position(self, text):
        index = self.code.find(text)
        self.assertNotEqual(-1, index, text)
        return index

    def test_the_composition_script_runs_the_check_in_report_mode_only(self):
        self.assertIn("check-flexspi-closure.py", self.code)
        self.assertNotIn("--strict", self.code)

    def test_the_report_cannot_fail_the_composition_check(self):
        call = self.code[self.position("check-flexspi-closure.py") :]
        line_end = call.index("fi\n")
        block = call[:line_end]
        self.assertIn("||", block)
        self.assertNotIn("fail ", block)
        self.assertNotIn("exit", block)

    def test_the_report_runs_after_the_existing_checks_and_before_the_final_line(self):
        call = self.position("check-flexspi-closure.py")
        self.assertGreater(call, self.position("check_boot_images.sh"))
        self.assertGreater(call, self.position("check-boot-config.py"))
        self.assertGreater(call, self.position("expect_refused"))
        self.assertLess(call, self.position("Boot composition: MCUboot"))

    def test_the_existing_checks_are_all_still_there(self):
        for needle in (
            "check-boot-config.py",
            "check_boot_images.sh",
            "the boot image check failed",
            "the boot build configuration check failed",
            "slot_size=3145728",
            "expect_refused",
            "CONFIG_BOOT_RAM_LOAD_REVERT=y",
        ):
            self.assertIn(needle, self.code)

    def test_the_script_has_no_forbidden_word_of_the_composition_check(self):
        code = (SCRIPT).read_text()
        for forbidden in ("west flash", "openocd", "pyocd", "JLink", "keygen"):
            self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
