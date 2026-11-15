#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check tests/target/compare_boot_builds.py on fake build trees of synthetic images.

The tool compares two builds of the composition of docs/boot-composition.md. What "reproducible" means
here is the definition of Stage 8 of the boot and update investigation (docs/evidence/boot-update/
stage8-reproducibility-and-signing.md): the unsigned binaries are byte-identical, and the signed
images are identical in header, payload, protected TLVs, digest and key hash, while the ECDSA
signature may differ, because the signature of this toolchain is randomised. These tests build the
trees by hand from the helpers of test_boot_image_inspect.py. They show what the tool decides on such
inputs; no real build output is compared, and nothing says that two real builds reproduce. Standard
library only.
"""
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SCRIPT = REPO / "tests/target/compare_boot_builds.py"
SLOT = 3 * 1024 * 1024


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = load_module(HERE / "test_boot_image_inspect.py", "test_boot_image_inspect_for_compare_tests")
compare = load_module(SCRIPT, "compare_boot_builds_under_test") if SCRIPT.is_file() else None

SIG_A = bytes(range(72))
SIG_B = bytes(range(100, 171))  # one byte shorter: DER length varies
PAYLOAD = bytes((i * 11 + 5) & 0xFF for i in range(0x800))
MCUBOOT_BIN = bytes(range(256)) * 64
APP_BIN = PAYLOAD


def signed(signature=SIG_A, payload=PAYLOAD, **kwargs):
    return base.build_image(payload=payload, signature=signature, **kwargs)


def confirmed(image, align=8, slot=SLOT):
    data = bytearray(base.trailer_bytes(slot, align, magic="good", image_ok=1))
    data[:len(image)] = image
    return bytes(data)


def write_build(root, image="zephyr", mcuboot=MCUBOOT_BIN, app=APP_BIN, signed_bin=None,
                confirmed_bin=None, with_confirmed=True):
    root = Path(root)
    (root / "mcuboot/zephyr").mkdir(parents=True, exist_ok=True)
    (root / image / "zephyr").mkdir(parents=True, exist_ok=True)
    (root / "mcuboot/zephyr/zephyr.bin").write_bytes(mcuboot)
    app_dir = root / image / "zephyr"
    (app_dir / "zephyr.bin").write_bytes(app)
    signed_bin = signed() if signed_bin is None else signed_bin
    (app_dir / "zephyr.signed.bin").write_bytes(signed_bin)
    if with_confirmed:
        (app_dir / "zephyr.signed.confirmed.bin").write_bytes(
            confirmed(signed_bin) if confirmed_bin is None else confirmed_bin)
    return root


class CompareBase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.root = Path(self._dir.name)
        self.a = self.root / "a"
        self.b = self.root / "b"

    def rows(self, report):
        return {row["artifact"]: row for row in report["rows"]}

    def status(self, report, artifact):
        return self.rows(report)[artifact]["status"]


APP_SIGNED = "zephyr/zephyr/zephyr.signed.bin"
APP_CONFIRMED = "zephyr/zephyr/zephyr.signed.confirmed.bin"
APP_BIN_NAME = "zephyr/zephyr/zephyr.bin"
MCUBOOT_NAME = "mcuboot/zephyr/zephyr.bin"


class IdenticalBuildsTest(CompareBase):
    def test_identical_builds_are_reproducible_and_every_row_is_identical(self):
        write_build(self.a)
        write_build(self.b)
        report = compare.compare_builds(self.a, self.b)
        self.assertTrue(report["ok"], report)
        self.assertEqual("reproducible", report["result"])
        self.assertEqual({MCUBOOT_NAME, APP_BIN_NAME, APP_SIGNED, APP_CONFIRMED},
                         set(self.rows(report)))
        for row in report["rows"]:
            self.assertEqual("identical", row["status"], row)

    def test_a_different_image_name_is_read_from_its_own_directory(self):
        write_build(self.a, image="app")
        write_build(self.b, image="app")
        report = compare.compare_builds(self.a, self.b, image="app")
        self.assertTrue(report["ok"], report)
        self.assertIn("app/zephyr/zephyr.signed.bin", self.rows(report))

    def test_the_tool_does_not_claim_a_signature_check_or_a_boot_result(self):
        write_build(self.a)
        write_build(self.b)
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["signature_verified"])
        self.assertIn("NOT a signature verification", report["signature_note"])


class UnsignedBinaryTest(CompareBase):
    def test_a_changed_mcuboot_binary_is_not_reproducible(self):
        write_build(self.a)
        changed = bytearray(MCUBOOT_BIN)
        changed[1000] ^= 0xFF
        write_build(self.b, mcuboot=bytes(changed))
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        self.assertEqual("not reproducible", report["result"])
        row = self.rows(report)[MCUBOOT_NAME]
        self.assertEqual("differs", row["status"])
        self.assertIn("1000", row["detail"])

    def test_a_changed_application_binary_is_not_reproducible(self):
        write_build(self.a)
        write_build(self.b, app=APP_BIN + b"\x00")
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        self.assertEqual("differs", self.status(report, APP_BIN_NAME))
        self.assertIn("sizes", self.rows(report)[APP_BIN_NAME]["detail"])

    def test_a_missing_unsigned_binary_in_one_build_fails(self):
        write_build(self.a)
        write_build(self.b)
        (self.b / "mcuboot/zephyr/zephyr.bin").unlink()
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        self.assertEqual("missing", self.status(report, MCUBOOT_NAME))
        self.assertIn("build B", self.rows(report)[MCUBOOT_NAME]["detail"])


class SignedImageTest(CompareBase):
    def test_a_different_signature_alone_is_equivalent_and_passes(self):
        write_build(self.a, signed_bin=signed(SIG_A))
        write_build(self.b, signed_bin=signed(SIG_B))
        report = compare.compare_builds(self.a, self.b)
        self.assertTrue(report["ok"], report)
        row = self.rows(report)[APP_SIGNED]
        self.assertEqual("equivalent", row["status"])
        self.assertIn("ECDSA_SIG", row["detail"])
        self.assertIn("randomised", row["detail"])

    def test_the_size_difference_of_one_byte_is_named(self):
        write_build(self.a, signed_bin=signed(SIG_A))
        write_build(self.b, signed_bin=signed(SIG_B))
        row = self.rows(compare.compare_builds(self.a, self.b))[APP_SIGNED]
        self.assertIn(str(len(signed(SIG_A))), row["detail"])
        self.assertIn(str(len(signed(SIG_B))), row["detail"])

    def test_the_strict_option_fails_a_different_signature(self):
        write_build(self.a, signed_bin=signed(SIG_A))
        write_build(self.b, signed_bin=signed(SIG_B))
        report = compare.compare_builds(self.a, self.b, strict_signature=True)
        self.assertFalse(report["ok"])
        self.assertEqual("equivalent", self.status(report, APP_SIGNED))
        self.assertIn("strict", self.rows(report)[APP_SIGNED]["detail"])

    def test_a_changed_payload_is_not_reproducible_even_with_a_valid_digest(self):
        write_build(self.a, signed_bin=signed(SIG_A))
        other = bytearray(PAYLOAD)
        other[0x40] ^= 0xFF
        write_build(self.b, signed_bin=signed(SIG_A, payload=bytes(other)))
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        row = self.rows(report)[APP_SIGNED]
        self.assertEqual("differs", row["status"])
        self.assertIn("payload", row["detail"])

    def test_a_changed_header_field_is_named(self):
        write_build(self.a, signed_bin=signed(SIG_A, version=(1, 2, 3, 4)))
        write_build(self.b, signed_bin=signed(SIG_A, version=(1, 2, 3, 5)))
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        self.assertIn("header", self.rows(report)[APP_SIGNED]["detail"])

    def test_a_changed_key_hash_is_named(self):
        write_build(self.a, signed_bin=signed(SIG_A, key=b"fake public key bytes, not a key"))
        write_build(self.b, signed_bin=signed(SIG_A, key=b"another fake key, also not a key!!"))
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        self.assertIn("TLVs other than the signature", self.rows(report)[APP_SIGNED]["detail"])

    def test_a_signed_image_that_does_not_parse_fails(self):
        write_build(self.a)
        broken = bytearray(signed())
        broken[0x500] ^= 0xFF  # the digest no longer matches
        write_build(self.b, signed_bin=bytes(broken), confirmed_bin=confirmed(signed()))
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        row = self.rows(report)[APP_SIGNED]
        self.assertEqual("differs", row["status"])
        self.assertIn("build B", row["detail"])

    def test_a_missing_signed_image_fails(self):
        write_build(self.a)
        write_build(self.b)
        (self.a / "zephyr/zephyr/zephyr.signed.bin").unlink()
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        self.assertEqual("missing", self.status(report, APP_SIGNED))


class ConfirmedImageTest(CompareBase):
    def test_confirmed_images_with_only_a_different_signature_are_equivalent(self):
        write_build(self.a, signed_bin=signed(SIG_A))
        write_build(self.b, signed_bin=signed(SIG_B))
        report = compare.compare_builds(self.a, self.b)
        self.assertEqual("equivalent", self.status(report, APP_CONFIRMED))

    def test_a_different_trailer_is_not_reproducible(self):
        image = signed()
        write_build(self.a, signed_bin=image, confirmed_bin=confirmed(image, align=8))
        write_build(self.b, signed_bin=image, confirmed_bin=confirmed(image, align=16))
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        row = self.rows(report)[APP_CONFIRMED]
        self.assertEqual("differs", row["status"])
        self.assertIn("trailer", row["detail"])

    def test_a_confirmed_flag_that_differs_is_not_reproducible(self):
        image = signed()
        a = confirmed(image)
        b = bytearray(a)
        layout_flag = len(b) - inspector_distance(8, "image_ok")
        b[layout_flag] = 0xFF
        write_build(self.a, signed_bin=image, confirmed_bin=a)
        write_build(self.b, signed_bin=image, confirmed_bin=bytes(b))
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        self.assertEqual("differs", self.status(report, APP_CONFIRMED))

    def test_confirmed_images_of_different_lengths_fail(self):
        image = signed()
        write_build(self.a, signed_bin=image, confirmed_bin=confirmed(image, slot=SLOT))
        write_build(self.b, signed_bin=image, confirmed_bin=confirmed(image, slot=SLOT - 4096))
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        self.assertEqual("differs", self.status(report, APP_CONFIRMED))

    def test_a_confirmed_image_absent_from_both_builds_is_reported_and_passes(self):
        write_build(self.a, with_confirmed=False)
        write_build(self.b, with_confirmed=False)
        report = compare.compare_builds(self.a, self.b)
        self.assertTrue(report["ok"], report)
        self.assertEqual("absent", self.status(report, APP_CONFIRMED))

    def test_a_confirmed_image_in_only_one_build_fails(self):
        write_build(self.a)
        write_build(self.b, with_confirmed=False)
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        self.assertEqual("missing", self.status(report, APP_CONFIRMED))


def inspector_distance(align, field):
    return base.inspector.trailer_distances(align)[field]


def signed_with(tlvs, payload=PAYLOAD):
    """A signed-looking image whose unprotected TLVs are exactly `tlvs` (list of (type, value))."""
    prot = b""
    header = base.HEADER.pack(base.IMAGE_MAGIC, 0x80000000, 0x400, 0, len(payload), 0, 1, 2, 3, 4, 0)
    header += bytes(0x400 - len(header))
    import hashlib
    digest = hashlib.sha256(header + payload + prot).digest()
    entries = [(kind, digest if value == "digest" else value) for kind, value in tlvs]
    return header + payload + prot + base.tlv_area(base.UNPROT_MAGIC, entries)




def standard_tlvs(signature):
    import hashlib
    return [(base.KEYHASH, hashlib.sha256(base.FAKE_KEY).digest()), (base.SHA256_TLV, "digest"),
            (base.ECDSA_SIG, signature)]


class UncomparedBytesTest(CompareBase):
    """Bytes outside the parsed parts must not slip through as an equivalent signature difference."""

    def padded_pair(self, change):
        image = signed(SIG_A)
        a = confirmed(image)
        b = bytearray(a)
        change(b, len(image))
        write_build(self.a, signed_bin=image, confirmed_bin=a)
        write_build(self.b, signed_bin=image, confirmed_bin=bytes(b))
        return compare.compare_builds(self.a, self.b)

    def test_a_changed_padding_byte_before_the_trailer_is_not_reproducible(self):
        def change(data, image_len):
            data[image_len + 100] = 0x00
        report = self.padded_pair(change)
        self.assertFalse(report["ok"])
        row = self.rows(report)[APP_CONFIRMED]
        self.assertEqual("differs", row["status"])
        self.assertIn("tail", row["detail"])
        self.assertNotIn("only the ECDSA_SIG TLV differs", row["detail"])

    def test_a_changed_tail_without_a_trailer_magic_is_not_reproducible(self):
        image = signed(SIG_A)
        a = bytearray(b"\xff" * SLOT)
        a[:len(image)] = image
        b = bytearray(a)
        b[SLOT - 40] = 0x01  # where a trailer field would sit
        write_build(self.a, signed_bin=image, confirmed_bin=bytes(a))
        write_build(self.b, signed_bin=image, confirmed_bin=bytes(b))
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        self.assertEqual("differs", self.status(report, APP_CONFIRMED))

    def test_unpadded_images_with_different_extra_trailing_bytes_are_not_reproducible(self):
        image = signed(SIG_A)
        write_build(self.a, signed_bin=image + b"\x01\x02\x03", confirmed_bin=confirmed(image))
        write_build(self.b, signed_bin=image + b"\x01\x02\x04", confirmed_bin=confirmed(image))
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        self.assertEqual("differs", self.status(report, APP_SIGNED))

    def test_the_extra_bytes_of_the_longer_signature_in_a_padded_image_must_be_erased(self):
        # The shorter signature leaves two more padding bytes in build B. They must be 0xFF.
        a = confirmed(signed(SIG_A))
        b = bytearray(confirmed(signed(SIG_B)))
        end = len(signed(SIG_B))
        b[end] = 0x00
        write_build(self.a, signed_bin=signed(SIG_A), confirmed_bin=a)
        write_build(self.b, signed_bin=signed(SIG_B), confirmed_bin=bytes(b))
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        self.assertEqual("differs", self.status(report, APP_CONFIRMED))

    def test_a_pure_signature_difference_in_a_padded_image_is_still_equivalent(self):
        a = confirmed(signed(SIG_A))
        b = confirmed(signed(SIG_B))
        write_build(self.a, signed_bin=signed(SIG_A), confirmed_bin=a)
        write_build(self.b, signed_bin=signed(SIG_B), confirmed_bin=b)
        report = compare.compare_builds(self.a, self.b)
        self.assertTrue(report["ok"], report)
        self.assertEqual("equivalent", self.status(report, APP_CONFIRMED))


class SignatureConstraintTest(CompareBase):
    def build_pair(self, tlvs_a, tlvs_b):
        write_build(self.a, signed_bin=signed_with(tlvs_a))
        write_build(self.b, signed_bin=signed_with(tlvs_b))
        return compare.compare_builds(self.a, self.b)

    def test_an_image_without_a_signature_tlv_is_not_reproducible(self):
        report = self.build_pair(standard_tlvs(SIG_A), standard_tlvs(SIG_A)[:2])
        self.assertFalse(report["ok"])
        row = self.rows(report)[APP_SIGNED]
        self.assertEqual("differs", row["status"])
        self.assertIn("signature TLV count", row["detail"])

    def test_an_image_with_two_signature_tlvs_is_not_reproducible(self):
        report = self.build_pair(standard_tlvs(SIG_A), standard_tlvs(SIG_A) + [(base.ECDSA_SIG, SIG_B)])
        self.assertFalse(report["ok"])
        self.assertIn("signature TLV count", self.rows(report)[APP_SIGNED]["detail"])

    def test_a_signature_of_a_very_different_length_is_not_reproducible(self):
        report = self.build_pair(standard_tlvs(SIG_A), standard_tlvs(bytes(range(200)) + bytes(100)))
        self.assertFalse(report["ok"])
        self.assertIn("signature length", self.rows(report)[APP_SIGNED]["detail"])

    def test_an_empty_signature_is_not_reproducible(self):
        report = self.build_pair(standard_tlvs(SIG_A), standard_tlvs(b""))
        self.assertFalse(report["ok"])
        self.assertIn("signature length", self.rows(report)[APP_SIGNED]["detail"])

    def test_a_signature_tlv_at_another_position_is_not_reproducible(self):
        tlvs = standard_tlvs(SIG_A)
        moved = [tlvs[2], tlvs[0], tlvs[1]]
        report = self.build_pair(tlvs, moved)
        self.assertFalse(report["ok"])
        self.assertIn("signature position", self.rows(report)[APP_SIGNED]["detail"])

    def test_signature_lengths_within_two_bytes_are_accepted(self):
        report = self.build_pair(standard_tlvs(SIG_A), standard_tlvs(SIG_A[:-2] + b"\x01\x02"[:0]))
        self.assertTrue(report["ok"], report)
        self.assertEqual("equivalent", self.status(report, APP_SIGNED))

    def test_a_changed_reserved_byte_of_another_tlv_entry_is_not_reproducible(self):
        # The reserved byte of a TLV entry is in no parsed value. With a different signature as well,
        # an equivalent row would be a false claim.
        a, b = signed(SIG_A), bytearray(signed(SIG_B))
        keyhash_entry = len(b) - len(base.tlv_area(base.UNPROT_MAGIC, [
            (base.KEYHASH, bytes(32)), (base.SHA256_TLV, bytes(32)), (base.ECDSA_SIG, SIG_B)]))
        b[keyhash_entry + 4 + 1] = 0x01  # the reserved byte of the first entry
        write_build(self.a, signed_bin=a)
        write_build(self.b, signed_bin=bytes(b))
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        row = self.rows(report)[APP_SIGNED]
        self.assertEqual("differs", row["status"])
        self.assertIn("unprotected TLV area", row["detail"])
        self.assertNotIn("only the ECDSA_SIG TLV differs", row["detail"])

    def test_a_changed_reserved_byte_of_the_signature_entry_is_not_reproducible(self):
        a, b = signed(SIG_A), bytearray(signed(SIG_B))
        sig_entry = len(b) - len(SIG_B) - 4
        b[sig_entry + 1] = 0x01
        write_build(self.a, signed_bin=a)
        write_build(self.b, signed_bin=bytes(b))
        report = compare.compare_builds(self.a, self.b)
        self.assertFalse(report["ok"])
        self.assertIn("signature entry", self.rows(report)[APP_SIGNED]["detail"])


class ToolFailureTest(CompareBase):
    def test_an_unexpected_exception_is_a_usage_error_not_a_verdict(self):
        write_build(self.a)
        write_build(self.b)
        original = compare.compare_builds

        def boom(*args, **kwargs):
            raise RuntimeError("boom")
        compare.compare_builds = boom
        self.addCleanup(setattr, compare, "compare_builds", original)
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = compare.main([str(self.a), str(self.b)])
        self.assertEqual(2, status)
        self.assertIn("boom", err.getvalue())
        self.assertNotIn("Result:", out.getvalue())


class CommandTest(CompareBase):
    def run_main(self, *args):
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = compare.main([str(a) for a in args])
        return status, out.getvalue(), err.getvalue()

    def test_reproducible_builds_exit_0_and_print_the_result(self):
        write_build(self.a, signed_bin=signed(SIG_A))
        write_build(self.b, signed_bin=signed(SIG_B))
        status, out, err = self.run_main(self.a, self.b)
        self.assertEqual(0, status, err)
        self.assertIn("Result: reproducible", out)
        self.assertIn("equivalent", out)

    def test_a_difference_exits_1_and_says_not_reproducible(self):
        write_build(self.a)
        write_build(self.b, mcuboot=MCUBOOT_BIN[:-1])
        status, out, _ = self.run_main(self.a, self.b)
        self.assertEqual(1, status)
        self.assertIn("Result: not reproducible", out)

    def test_the_strict_option_exits_1_for_a_different_signature(self):
        write_build(self.a, signed_bin=signed(SIG_A))
        write_build(self.b, signed_bin=signed(SIG_B))
        status, _, _ = self.run_main(self.a, self.b, "--strict-signature")
        self.assertEqual(1, status)

    def test_json_output_carries_the_rows(self):
        write_build(self.a)
        write_build(self.b)
        status, out, _ = self.run_main(self.a, self.b, "--json")
        self.assertEqual(0, status)
        report = json.loads(out)
        self.assertEqual("build comparison", report["kind"])
        self.assertEqual(4, len(report["rows"]))

    def test_a_missing_build_directory_is_a_usage_error(self):
        write_build(self.a)
        status, _, err = self.run_main(self.a, self.root / "no-such-build")
        self.assertEqual(2, status)
        self.assertIn("no-such-build", err)

    def test_the_same_directory_twice_is_refused_as_not_a_comparison(self):
        write_build(self.a)
        status, _, err = self.run_main(self.a, self.a)
        self.assertEqual(2, status)
        self.assertIn("same", err)

    def test_the_image_name_is_an_option(self):
        write_build(self.a, image="app")
        write_build(self.b, image="app")
        status, out, err = self.run_main(self.a, self.b, "--image", "app")
        self.assertEqual(0, status, err)
        self.assertIn("app/zephyr/zephyr.signed.bin", out)


class ToolShapeTest(unittest.TestCase):
    def test_the_tool_exists_is_executable_and_uses_only_the_standard_library(self):
        import ast
        self.assertTrue(SCRIPT.is_file(), f"{SCRIPT} is missing")
        self.assertTrue(SCRIPT.stat().st_mode & 0o111)
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("#!/usr/bin/env python3"))
        names = set()
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names.add(node.module.split(".")[0])
        self.assertEqual(set(), names - set(sys.stdlib_module_names))

    def test_the_tool_is_not_under_scripts(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertFalse((REPO / "scripts" / SCRIPT.name).exists())
        self.assertFalse(list((REPO / "scripts").glob("*compare*boot*")))


if __name__ == "__main__":
    unittest.main()
