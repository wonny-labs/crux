#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check tests/target/inspect_boot_image.py on synthetic MCUboot images and slot trailers.

Every input is built in memory. The image header, the trailer offsets and the trailer magic come
from the repository's own model in `tests/native/emmc_trailer/trailer_model.py` (ModelImage, Layout),
the slot states from `docs/plans/image-state-contract-proposal.md` (Slot states), and the offsets
0x300 (header padding) and 0x500 (payload) from `scripts/test-boot-composition.sh`. The TLV info
magics, the TLV entry layout and the hashed range have no repository record: they are the author's
reading of MCUboot's image format, and these tests only repeat that reading. Nothing here is an image
from a board or from a build, and nothing is compared with MCUboot's source: an error that the
records or the author's reading share with these tests would pass.
The tests use the standard library only, like the tool.
"""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "tests/target/inspect_boot_image.py"
MODEL = REPO / "tests/native/emmc_trailer/trailer_model.py"

IMAGE_MAGIC = 0x96F3B83D
HEADER = struct.Struct("<IIHHIIBBHII")  # the 32 bytes of ModelImage._HEADER
TLV_INFO = struct.Struct("<HH")
TLV_ENTRY = struct.Struct("<BBH")
PROT_MAGIC, UNPROT_MAGIC = 0x6908, 0x6907
KEYHASH, SHA256_TLV, ECDSA_SIG = 0x01, 0x10, 0x22
FAKE_KEY = b"fake public key bytes, not a key"
FAKE_SIG = bytes(range(72))
# The repository's record for BOOT_MAX_ALIGN 8 (trailer_model.py _MAGIC_ALIGN_8).
MAGIC_ALIGN_8 = bytes.fromhex("77c295f360d2ef7f3552500f2cb67980")
STATE_NAMES = {
    "STAGED", "PENDING_TEST", "PENDING_PERMANENT", "TRIED", "STANDBY_CONFIRMED",
    "RUNNING_CONFIRMED", "RUNNING_TESTING", "EMPTY", "INVALID", "ERR_BOOT_STATE",
}


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


model = load_module(MODEL, "emmc_trailer_model_for_inspect_tests")
inspector = load_module(SCRIPT, "inspect_boot_image_under_test") if SCRIPT.is_file() else None


def tlv_area(magic, entries):
    body = b"".join(TLV_ENTRY.pack(kind, 0, len(value)) + value for kind, value in entries)
    return TLV_INFO.pack(magic, TLV_INFO.size + len(body)) + body


def build_image(payload=None, hdr_size=0x400, protected=None, key=FAKE_KEY, signature=FAKE_SIG,
                version=(1, 2, 3, 4), load_addr=0x80000000, flags=0, magic=IMAGE_MAGIC):
    """A signed-looking image: header with padding, payload, optional protected TLVs, then
    KEYHASH, SHA256 and ECDSA_SIG TLVs. The digest covers the header (with its padding up to
    hdr_size), the payload and the protected TLV area, which is how MCUboot hashes an image."""
    if payload is None:
        payload = bytes((i * 7 + 3) & 0xFF for i in range(0x600))
    prot_area = tlv_area(PROT_MAGIC, protected) if protected else b""
    major, minor, revision, build = version
    header = HEADER.pack(magic, load_addr, hdr_size, len(prot_area), len(payload), flags,
                         major, minor, revision, build, 0)
    header += bytes(hdr_size - len(header))
    digest = hashlib.sha256(header + payload + prot_area).digest()
    unprot = tlv_area(UNPROT_MAGIC, [
        (KEYHASH, hashlib.sha256(key).digest()),
        (SHA256_TLV, digest),
        (ECDSA_SIG, signature),
    ])
    return header + payload + prot_area + unprot


def trailer_bytes(size, align, magic="good", image_ok=None, copy_done=None, swap_info=None):
    """A slot-sized buffer of erased bytes with the trailer fields at the offsets of the
    repository's Layout. None leaves a field erased."""
    layout = model.Layout(size, align, 1)
    data = bytearray(b"\xff" * size)
    if magic == "good":
        data[layout.magic_off:layout.magic_off + 16] = layout.magic
    elif magic == "bad":
        data[layout.magic_off:layout.magic_off + 16] = bytes(range(16))
    for offset, value in ((layout.image_ok_off, image_ok), (layout.copy_done_off, copy_done),
                          (layout.swap_info_off, swap_info)):
        if value is not None:
            data[offset] = value
    return bytes(data)


def run_main(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = inspector.main(args)
    return status, out.getvalue(), err.getvalue()


class TempFiles(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)

    def write(self, data, name="input.bin"):
        path = Path(self._dir.name) / name
        path.write_bytes(data)
        return str(path)

    def cli(self, *args):
        """The real command line, in a child process, so the exit status is the process's."""
        done = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)
        return done.returncode, done.stdout, done.stderr


class ScriptExists(unittest.TestCase):
    def test_the_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT.is_file(), f"{SCRIPT} is missing")
        self.assertTrue(SCRIPT.stat().st_mode & 0o111, "the script is not executable")
        self.assertTrue(SCRIPT.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3"))

    def test_the_script_imports_only_the_standard_library(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(0, node.level, "a relative import")
                names.add(node.module.split(".")[0])
        self.assertTrue(names, "no imports found")
        self.assertEqual(set(), names - set(sys.stdlib_module_names))


class ImageTest(unittest.TestCase):
    def test_a_well_formed_image_has_a_matching_digest(self):
        report = inspector.inspect_image(build_image())
        self.assertEqual("digest ok", report["result"])
        self.assertTrue(report["ok"])
        self.assertEqual("ok", report["digest"]["status"])
        self.assertEqual(report["digest"]["computed"], report["digest"]["expected"])
        self.assertEqual([], report["errors"])

    def test_the_header_fields_are_reported(self):
        image = build_image(hdr_size=0x400, version=(1, 2, 3, 4), load_addr=0x80000000, flags=0x04)
        header = inspector.inspect_image(image)["header"]
        self.assertEqual(IMAGE_MAGIC, header["magic"])
        self.assertTrue(header["magic_ok"])
        self.assertEqual(0x80000000, header["load_addr"])
        self.assertEqual(0x400, header["hdr_size"])
        self.assertEqual(0, header["protect_tlv_size"])
        self.assertEqual(0x600, header["img_size"])
        self.assertEqual(0x04, header["flags"])
        self.assertEqual({"major": 1, "minor": 2, "revision": 3, "build_num": 4}, header["version"])
        self.assertEqual("1.2.3+4", header["version_string"])

    def test_the_tlvs_are_listed_with_names_where_known(self):
        report = inspector.inspect_image(build_image())
        area = report["unprotected_tlv"]
        self.assertTrue(area["present"])
        self.assertEqual(UNPROT_MAGIC, area["magic"])
        self.assertEqual(0x400 + 0x600, area["offset"])
        self.assertEqual([KEYHASH, SHA256_TLV, ECDSA_SIG], [t["type"] for t in area["tlvs"]])
        self.assertEqual(["KEYHASH", "SHA256", "ECDSA_SIG"], [t["type_name"] for t in area["tlvs"]])
        self.assertEqual(["0x01", "0x10", "0x22"], [t["type_hex"] for t in area["tlvs"]])
        self.assertEqual([32, 32, 72], [t["length"] for t in area["tlvs"]])
        self.assertEqual(FAKE_SIG.hex(), area["tlvs"][2]["value_hex"])
        self.assertEqual(len(tlv_area(UNPROT_MAGIC, [(1, bytes(32)), (0x10, bytes(32)), (0x22, FAKE_SIG)])),
                         area["total_length"])

    def test_an_unknown_tlv_type_is_shown_as_hex(self):
        image = build_image(protected=[(0x50, b"\x01\x00\x00\x00")])
        report = inspector.inspect_image(image)
        tlv = report["protected_tlv"]["tlvs"][0]
        self.assertEqual(0x50, tlv["type"])
        self.assertIsNone(tlv["type_name"])
        self.assertEqual("0x50", tlv["type_hex"])
        self.assertEqual("01000000", tlv["value_hex"])

    def test_the_key_hash_is_the_sha256_of_the_public_key(self):
        key = b"another fake public key"
        report = inspector.inspect_image(build_image(key=key))
        self.assertEqual(hashlib.sha256(key).hexdigest(), report["key_hash"])

    def test_a_payload_change_at_0x500_is_a_mismatch(self):
        # scripts/test-boot-composition.sh changes the byte at 0x500, inside the payload.
        image = bytearray(build_image())
        image[0x500] ^= 0xFF
        report = inspector.inspect_image(bytes(image))
        self.assertEqual("digest MISMATCH", report["result"])
        self.assertFalse(report["ok"])
        self.assertEqual("MISMATCH", report["digest"]["status"])
        self.assertNotEqual(report["digest"]["computed"], report["digest"]["expected"])

    def test_a_header_padding_change_at_0x300_is_a_mismatch(self):
        # 0x300 is inside the header padding (hdr_size 0x400). MCUboot hashes the header up to
        # hdr_size, so the padding is covered, which is why test-boot-composition.sh uses it.
        image = bytearray(build_image())
        self.assertEqual(0, image[0x300])
        image[0x300] ^= 0xFF
        self.assertEqual("digest MISMATCH", inspector.inspect_image(bytes(image))["result"])

    def test_a_signature_change_is_not_noticed_because_this_is_not_a_signature_check(self):
        image = bytearray(build_image())
        image[-1] ^= 0xFF  # the last byte of the ECDSA_SIG value
        report = inspector.inspect_image(bytes(image))
        self.assertEqual("digest ok", report["result"])
        self.assertFalse(report["signature_verified"])

    def test_the_protected_tlv_area_is_hashed_when_present(self):
        protected = [(0x50, b"\x07\x00\x00\x00")]
        image = build_image(protected=protected)
        report = inspector.inspect_image(image)
        self.assertEqual("digest ok", report["result"])
        area = report["protected_tlv"]
        self.assertTrue(area["present"])
        self.assertEqual(PROT_MAGIC, area["magic"])
        self.assertEqual(0x400 + 0x600, area["offset"])
        self.assertEqual(report["header"]["protect_tlv_size"], area["total_length"])
        self.assertEqual(0x400 + 0x600 + area["total_length"], report["unprotected_tlv"]["offset"])
        changed = bytearray(image)
        changed[0x400 + 0x600 + 4 + 4] ^= 0xFF  # the first value byte of the protected TLV
        self.assertEqual("digest MISMATCH", inspector.inspect_image(bytes(changed))["result"])

    def test_the_protected_tlv_area_is_absent_when_the_header_says_zero(self):
        report = inspector.inspect_image(build_image())
        area = report["protected_tlv"]
        self.assertFalse(area["present"])
        self.assertEqual([], area["tlvs"])

    def test_a_bad_image_magic_is_inconsistent(self):
        report = inspector.inspect_image(build_image(magic=0x12345678))
        self.assertEqual("structure inconsistent", report["result"])
        self.assertFalse(report["ok"])
        self.assertFalse(report["header"]["magic_ok"])
        self.assertTrue(any("magic" in e for e in report["errors"]))

    def test_an_image_size_beyond_the_file_is_inconsistent(self):
        image = bytearray(build_image())
        struct.pack_into("<I", image, 12, 0x10000000)  # img_size
        report = inspector.inspect_image(bytes(image))
        self.assertEqual("structure inconsistent", report["result"])
        self.assertTrue(any("beyond" in e for e in report["errors"]))

    def test_a_truncated_tlv_area_is_inconsistent(self):
        report = inspector.inspect_image(build_image()[:-10])
        self.assertEqual("structure inconsistent", report["result"])
        self.assertTrue(any("beyond" in e for e in report["errors"]))

    def test_a_file_shorter_than_the_header_is_inconsistent(self):
        report = inspector.inspect_image(b"\x3d\xb8\xf3\x96" + bytes(10))
        self.assertEqual("structure inconsistent", report["result"])
        self.assertFalse(report["ok"])

    def test_a_missing_tlv_info_magic_is_inconsistent(self):
        image = bytearray(build_image())
        struct.pack_into("<H", image, 0x400 + 0x600, 0x1234)
        report = inspector.inspect_image(bytes(image))
        self.assertEqual("structure inconsistent", report["result"])

    def test_a_protected_area_without_its_magic_is_inconsistent(self):
        image = bytearray(build_image(protected=[(0x50, bytes(4))]))
        struct.pack_into("<H", image, 0x400 + 0x600, UNPROT_MAGIC)
        self.assertEqual("structure inconsistent", inspector.inspect_image(bytes(image))["result"])

    def test_a_hdr_size_smaller_than_the_header_is_inconsistent(self):
        image = bytearray(build_image())
        struct.pack_into("<H", image, 8, 16)
        report = inspector.inspect_image(bytes(image))
        self.assertEqual("structure inconsistent", report["result"])
        self.assertTrue(any("hdr_size" in e for e in report["errors"]))

    def test_a_protect_tlv_size_that_differs_from_the_area_length_is_inconsistent(self):
        image = bytearray(build_image(protected=[(0x50, bytes(4))]))
        struct.pack_into("<H", image, 10, 16)  # protect_tlv_size, the area says 12
        report = inspector.inspect_image(bytes(image))
        self.assertEqual("structure inconsistent", report["result"])
        self.assertTrue(any("protect_tlv_size" in e for e in report["errors"]))

    def test_a_protected_magic_with_protect_tlv_size_zero_is_inconsistent(self):
        image = bytearray(build_image())
        struct.pack_into("<H", image, 0x400 + 0x600, PROT_MAGIC)
        report = inspector.inspect_image(bytes(image))
        self.assertEqual("structure inconsistent", report["result"])
        self.assertTrue(any("protect_tlv_size is 0" in e for e in report["errors"]))

    def test_a_protected_tlv_running_past_its_area_is_inconsistent(self):
        image = bytearray(build_image(protected=[(0x50, bytes(4))]))
        struct.pack_into("<H", image, 0x400 + 0x600 + 4 + 2, 200)  # the entry length
        report = inspector.inspect_image(bytes(image))
        self.assertEqual("structure inconsistent", report["result"])
        self.assertTrue(any("beyond" in e for e in report["errors"]))

    def test_an_unpadded_image_has_no_trailing_bytes(self):
        padding = inspector.inspect_image(build_image())["padding"]
        self.assertFalse(padding["padded"])
        self.assertEqual(0, padding["trailing_bytes"])
        self.assertEqual("none", padding["trailer_magic"])
        self.assertIsNone(padding["trailer"])

    def test_a_padded_image_without_trailer_magic_is_reported(self):
        image = build_image()
        padded = image + b"\xff" * (0x4000 - len(image))
        report = inspector.inspect_image(padded)
        self.assertEqual("digest ok", report["result"])
        padding = report["padding"]
        self.assertTrue(padding["padded"])
        self.assertEqual(0x4000 - len(image), padding["trailing_bytes"])
        self.assertEqual("none", padding["trailer_magic"])

    def test_a_padded_image_with_trailer_magic_is_reported_and_its_trailer_decoded(self):
        image = build_image()
        trailer = trailer_bytes(0x4000, 8, image_ok=1)
        padded = image + trailer[len(image):]
        report = inspector.inspect_image(padded)
        self.assertEqual("digest ok", report["result"])
        padding = report["padding"]
        self.assertTrue(padding["padded"])
        self.assertEqual("good", padding["trailer_magic"])
        self.assertEqual(8, padding["trailer_alignment"])
        self.assertEqual("set", padding["trailer"]["image_ok"]["state"])
        self.assertEqual("PENDING_PERMANENT", padding["trailer"]["slot_state"])

    def test_trailing_bytes_that_are_not_erased_are_noted(self):
        image = build_image()
        padded = image + b"\xff" * 100 + b"\x00" + b"\xff" * 100
        report = inspector.inspect_image(padded)
        self.assertEqual("digest ok", report["result"])
        self.assertTrue(any("not erased" in n for n in report["notes"]))

    def test_the_digest_status_is_not_computed_when_the_sha256_tlv_is_missing(self):
        image = build_image()
        payload_end = 0x400 + 0x600
        area = tlv_area(UNPROT_MAGIC, [(KEYHASH, hashlib.sha256(FAKE_KEY).digest())])
        report = inspector.inspect_image(image[:payload_end] + area)
        self.assertEqual("structure inconsistent", report["result"])
        self.assertEqual("not computed", report["digest"]["status"])

    def test_the_json_keys_are_stable(self):
        report = inspector.inspect_image(build_image(protected=[(0x50, bytes(4))]))
        self.assertEqual(
            {"kind", "file_size", "result", "ok", "signature_verified", "signature_note", "header",
             "protected_tlv", "unprotected_tlv", "digest", "key_hash", "padding", "errors", "notes"},
            set(report))
        self.assertEqual("image", report["kind"])
        self.assertEqual({"magic", "magic_ok", "load_addr", "hdr_size", "protect_tlv_size", "img_size",
                          "flags", "version", "version_string"}, set(report["header"]))
        self.assertEqual({"present", "offset", "magic", "total_length", "tlvs"},
                         set(report["protected_tlv"]))
        self.assertEqual({"type", "type_name", "type_hex", "offset", "length", "value_hex"},
                         set(report["unprotected_tlv"]["tlvs"][0]))
        self.assertEqual({"covers", "computed", "expected", "status"}, set(report["digest"]))
        self.assertEqual({"padded", "trailing_bytes", "trailer_magic", "trailer_alignment", "trailer"},
                         set(report["padding"]))
        json.dumps(report)


class HeaderOnlyTest(unittest.TestCase):
    def test_an_erased_32_byte_read_is_no_image(self):
        report = inspector.inspect_header_only(b"\xff" * 32)
        self.assertFalse(report["image_magic_present"])
        self.assertEqual("no image", report["classification"])
        self.assertTrue(report["erased"])
        self.assertTrue(report["ok"])

    def test_bytes_3d_b8_f3_96_are_the_image_magic(self):
        report = inspector.inspect_header_only(bytes.fromhex("3db8f396") + b"\xff" * 28)
        self.assertTrue(report["image_magic_present"])
        self.assertEqual("image magic present", report["classification"])
        self.assertFalse(report["erased"])

    def test_other_bytes_are_no_image_and_not_erased(self):
        report = inspector.inspect_header_only(bytes(32))
        self.assertEqual("no image", report["classification"])
        self.assertFalse(report["erased"])

    def test_four_bytes_are_enough(self):
        self.assertTrue(inspector.inspect_header_only(bytes.fromhex("3db8f396"))["image_magic_present"])

    def test_fewer_than_four_bytes_are_refused(self):
        with self.assertRaises(ValueError):
            inspector.inspect_header_only(b"\x3d\xb8\xf3")

    def test_the_json_keys_are_stable(self):
        report = inspector.inspect_header_only(b"\xff" * 32)
        self.assertEqual({"kind", "file_size", "bytes_read_hex", "image_magic_present", "classification",
                          "erased", "ok", "note"}, set(report))
        self.assertEqual("image-header", report["kind"])


class TrailerTest(unittest.TestCase):
    SLOT = 0x300000  # 3145728, the slot size of the boot investigation's trial builds
    ALIGNS = (1, 8, 512, 4096)

    def decode(self, align, **kwargs):
        decode_args = {key: kwargs.pop(key) for key in ("slot_size", "running", "check_header")
                       if key in kwargs}
        return inspector.decode_trailer(trailer_bytes(self.SLOT, align, **kwargs), align, **decode_args)

    def test_the_offsets_match_the_repository_layout_for_every_alignment(self):
        for align in self.ALIGNS:
            with self.subTest(align=align):
                layout = model.Layout(self.SLOT, align, 1)
                offsets = self.decode(align, image_ok=1)["offsets"]
                self.assertEqual(layout.magic_off, offsets["magic"])
                self.assertEqual(layout.image_ok_off, offsets["image_ok"])
                self.assertEqual(layout.copy_done_off, offsets["copy_done"])
                self.assertEqual(layout.swap_info_off, offsets["swap_info"])

    def test_the_offsets_below_the_slot_end_are_the_documented_distances(self):
        # Fixed numbers, so that a mistake shared with trailer_model.py does not pass.
        expected = {
            1: (16, 17, 18, 19),
            8: (16, 24, 32, 40),
            512: (16, 1024, 1536, 2048),
            4096: (16, 8192, 12288, 16384),
        }
        for align, (magic, image_ok, copy_done, swap_info) in expected.items():
            with self.subTest(align=align):
                offsets = self.decode(align)["offsets"]
                self.assertEqual(self.SLOT - magic, offsets["magic"])
                self.assertEqual(self.SLOT - image_ok, offsets["image_ok"])
                self.assertEqual(self.SLOT - copy_done, offsets["copy_done"])
                self.assertEqual(self.SLOT - swap_info, offsets["swap_info"])

    def test_the_magic_for_alignment_8_is_the_repository_value(self):
        self.assertEqual(MAGIC_ALIGN_8, model.Layout(self.SLOT, 8, 1).magic)
        report = self.decode(8, image_ok=None)
        self.assertEqual(MAGIC_ALIGN_8.hex(), report["magic"]["bytes_hex"])
        self.assertEqual("good", report["magic"]["state"])

    def test_every_alignment_decodes_every_state(self):
        # (magic, image_ok, copy_done, swap_info) -> state name, not the running slot
        cases = [
            ("unset", None, None, None, "STAGED"),
            ("good", None, None, 2, "PENDING_TEST"),
            ("good", 1, None, 3, "PENDING_PERMANENT"),
            ("good", None, 1, None, "TRIED"),
            ("good", 1, 1, None, "STANDBY_CONFIRMED"),
        ]
        for align in self.ALIGNS:
            for magic, image_ok, copy_done, swap_info, state in cases:
                with self.subTest(align=align, state=state):
                    report = self.decode(align, magic=magic, image_ok=image_ok, copy_done=copy_done,
                                         swap_info=swap_info)
                    self.assertEqual(state, report["slot_state"])
                    self.assertTrue(report["ok"], report["errors"])
                    self.assertEqual([], report["errors"])
                    self.assertIn(report["slot_state"], STATE_NAMES)

    def test_the_running_slot_states(self):
        cases = [
            (1, None, "RUNNING_CONFIRMED"),
            (1, 1, "RUNNING_CONFIRMED"),
            (None, 1, "RUNNING_TESTING"),
            (None, None, "RUNNING_TESTING"),
        ]
        for align in (8, 512):
            for image_ok, copy_done, state in cases:
                with self.subTest(align=align, state=state, image_ok=image_ok, copy_done=copy_done):
                    report = self.decode(align, image_ok=image_ok, copy_done=copy_done, running=True)
                    self.assertEqual(state, report["slot_state"])
                    self.assertTrue(report["ok"])
                    self.assertTrue(report["running"])

    def test_a_running_slot_without_a_good_magic_is_err_boot_state(self):
        for magic in ("unset", "bad"):
            with self.subTest(magic=magic):
                report = self.decode(8, magic=magic, running=True)
                self.assertEqual("ERR_BOOT_STATE", report["slot_state"])
                self.assertFalse(report["ok"])

    def test_an_unset_trailer_is_reported_as_all_unset(self):
        report = self.decode(8, magic="unset")
        self.assertEqual("unset", report["magic"]["state"])
        for field in ("image_ok", "copy_done", "swap_info"):
            self.assertEqual("unset", report[field]["state"])
            self.assertIsNone(report[field]["value"])
        self.assertEqual("unset", report["trailer_state"])
        self.assertEqual("STAGED", report["slot_state"])
        self.assertTrue(report["ok"])

    def test_a_bad_magic_with_set_fields_is_inconsistent(self):
        for align in self.ALIGNS:
            with self.subTest(align=align):
                report = self.decode(align, magic="bad", image_ok=1, copy_done=1)
                self.assertEqual("bad", report["magic"]["state"])
                self.assertFalse(report["ok"])
                self.assertEqual("INVALID", report["slot_state"])
                self.assertTrue(any("magic" in e for e in report["errors"]))

    def test_a_bad_magic_with_unset_fields_is_still_inconsistent(self):
        report = self.decode(8, magic="bad")
        self.assertFalse(report["ok"])
        self.assertEqual("INVALID", report["slot_state"])

    def test_fields_set_under_an_unset_magic_are_inconsistent(self):
        for field in ("image_ok", "copy_done"):
            with self.subTest(field=field):
                report = self.decode(8, magic="unset", **{field: 1})
                self.assertFalse(report["ok"])
                self.assertTrue(any("unset magic" in e for e in report["errors"]))

    def test_a_flag_value_that_is_neither_set_nor_unset_is_bad(self):
        report = self.decode(8, image_ok=0x05)
        self.assertEqual("bad", report["image_ok"]["state"])
        self.assertEqual(0x05, report["image_ok"]["value"])
        self.assertFalse(report["ok"])
        self.assertEqual("INVALID", report["slot_state"])

    def test_the_swap_info_fields_are_decoded(self):
        report = self.decode(8, swap_info=0x12)
        info = report["swap_info"]
        self.assertEqual(0x12, info["value"])
        self.assertEqual(2, info["swap_type"])
        self.assertEqual(1, info["image_num"])
        self.assertEqual("test", info["swap_type_name"])
        self.assertEqual(3, self.decode(8, image_ok=1, swap_info=3)["swap_info"]["swap_type"])
        self.assertEqual("perm", self.decode(8, image_ok=1, swap_info=3)["swap_info"]["swap_type_name"])

    def test_a_swap_info_that_disagrees_with_image_ok_is_a_warning_not_an_error(self):
        report = self.decode(8, image_ok=1, swap_info=2)  # test request with image_ok set
        self.assertTrue(report["ok"])
        self.assertTrue(any("swap_info" in w for w in report["warnings"]))
        report = self.decode(8, swap_info=3)  # permanent request without image_ok
        self.assertTrue(any("swap_info" in w for w in report["warnings"]))
        self.assertEqual([], self.decode(8, image_ok=1, swap_info=3)["warnings"])

    def test_the_trailer_state_words_come_from_the_flags(self):
        self.assertEqual("test request pending", self.decode(8, swap_info=2)["state_description"])
        self.assertIn("confirmed", self.decode(8, image_ok=1, copy_done=1)["state_description"])

    def test_the_magic_of_another_alignment_is_recognised(self):
        data = trailer_bytes(self.SLOT, 512, image_ok=1)
        report = inspector.decode_trailer(data, 8)
        self.assertEqual("bad", report["magic"]["state"])
        self.assertEqual(512, report["magic"]["alignment_hint"])
        self.assertFalse(report["ok"])

    def test_a_magic_that_only_shares_the_tail_is_not_called_the_magic_of_that_alignment(self):
        # '08 00' + the shared tail is not the good magic for alignment 8, which is the old one.
        self.assertIsNone(inspector.identify_magic(struct.pack("<H", 8) + inspector.MAGIC_TAIL))
        self.assertEqual(8, inspector.identify_magic(MAGIC_ALIGN_8))
        self.assertEqual(512, inspector.identify_magic(inspector.magic_for(512)))
        data = bytearray(trailer_bytes(self.SLOT, 8))
        data[-16:] = struct.pack("<H", 8) + inspector.MAGIC_TAIL
        report = inspector.decode_trailer(bytes(data), 8)
        self.assertEqual("bad", report["magic"]["state"])
        self.assertIsNone(report["magic"]["alignment_hint"])

    def test_a_running_slot_with_a_bad_image_ok_is_invalid(self):
        report = self.decode(8, image_ok=0x05, running=True)
        self.assertEqual("INVALID", report["slot_state"])
        self.assertFalse(report["ok"])

    def test_a_not_running_slot_with_unset_magic_and_a_bad_flag_is_invalid_not_staged(self):
        report = self.decode(8, magic="unset", copy_done=0x05)
        self.assertEqual("INVALID", report["slot_state"])
        self.assertFalse(report["ok"])

    def test_the_old_magic_is_recognised_as_alignment_8(self):
        data = trailer_bytes(self.SLOT, 8)
        report = inspector.decode_trailer(data, 512)
        self.assertEqual("bad", report["magic"]["state"])
        self.assertEqual(8, report["magic"]["alignment_hint"])

    def test_a_file_that_is_exactly_the_trailer_region_decodes(self):
        for align in (1, 8, 512):
            with self.subTest(align=align):
                layout = model.Layout(self.SLOT, align, 1)
                slot = trailer_bytes(self.SLOT, align, image_ok=1, copy_done=1, swap_info=3)
                region = slot[self.SLOT - layout.trailer_size:]
                report = inspector.decode_trailer(region, align)
                self.assertEqual("STANDBY_CONFIRMED", report["slot_state"])
                self.assertEqual("not examined", report["header"])

    def test_a_file_too_short_for_the_trailer_is_inconsistent(self):
        report = inspector.decode_trailer(b"\xff" * 20, 512)
        self.assertFalse(report["ok"])
        self.assertTrue(any("too short" in e for e in report["errors"]))

    def test_the_slot_size_comparison_is_reported(self):
        data = trailer_bytes(self.SLOT, 8)
        self.assertEqual("equal", inspector.decode_trailer(data, 8, slot_size=self.SLOT)["slot_size_check"])
        self.assertEqual("not given", inspector.decode_trailer(data, 8)["slot_size_check"])
        longer = inspector.decode_trailer(b"\xff" * 4096 + data, 8, slot_size=self.SLOT)
        self.assertEqual("longer", longer["slot_size_check"])
        self.assertTrue(any("longer" in n for n in longer["notes"]))
        shorter = inspector.decode_trailer(data[-4096:], 8, slot_size=self.SLOT)
        self.assertEqual("shorter", shorter["slot_size_check"])
        self.assertTrue(any("shorter" in n for n in shorter["notes"]))

    def test_the_header_is_examined_for_a_whole_slot(self):
        slot = bytearray(trailer_bytes(self.SLOT, 8, image_ok=1, copy_done=1))
        report = inspector.decode_trailer(bytes(slot), 8, slot_size=self.SLOT)
        self.assertEqual("no image magic", report["header"])
        self.assertEqual("EMPTY", report["slot_state"])
        slot[0:4] = struct.pack("<I", IMAGE_MAGIC)
        report = inspector.decode_trailer(bytes(slot), 8, slot_size=self.SLOT)
        self.assertEqual("image magic present", report["header"])
        self.assertEqual("STANDBY_CONFIRMED", report["slot_state"])

    def test_the_header_can_be_requested_for_an_image_file(self):
        image = build_image()
        padded = image + trailer_bytes(0x4000, 8, image_ok=1)[len(image):]
        report = inspector.decode_trailer(padded, 8, check_header=True)
        self.assertEqual("image magic present", report["header"])
        self.assertEqual("PENDING_PERMANENT", report["slot_state"])

    def test_the_json_keys_are_stable(self):
        report = self.decode(8, image_ok=1, swap_info=3)
        self.assertEqual(
            {"kind", "file_size", "alignment", "slot_size", "slot_size_check", "offsets", "magic",
             "image_ok", "copy_done", "swap_info", "header", "running", "trailer_state", "slot_state",
             "state_description", "ok", "errors", "warnings", "notes"}, set(report))
        self.assertEqual("trailer", report["kind"])
        self.assertEqual({"magic", "image_ok", "copy_done", "swap_info"}, set(report["offsets"]))
        self.assertEqual({"offset", "bytes_hex", "state", "alignment_hint"}, set(report["magic"]))
        self.assertEqual({"offset", "value", "state"}, set(report["image_ok"]))
        self.assertEqual({"offset", "value", "state", "swap_type", "swap_type_name", "image_num"},
                         set(report["swap_info"]))
        json.dumps(report)


class CliTest(TempFiles):
    def test_a_good_image_exits_0_and_says_digest_ok_and_not_a_signature_check(self):
        status, out, _ = self.cli("image", self.write(build_image()))
        self.assertEqual(0, status)
        self.assertIn("digest ok", out)
        self.assertIn("NOT a signature verification", out)
        self.assertIn("imgtool verify", out)

    def test_a_changed_image_exits_1_for_the_offsets_of_the_composition_check(self):
        for offset in (0x300, 0x500):
            with self.subTest(offset=hex(offset)):
                image = bytearray(build_image())
                image[offset] ^= 0xFF
                status, out, _ = self.cli("image", self.write(bytes(image)))
                self.assertEqual(1, status)
                self.assertIn("digest MISMATCH", out)

    def test_a_bad_magic_exits_1(self):
        status, out, _ = self.cli("image", self.write(build_image(magic=0xDEADBEEF)))
        self.assertEqual(1, status)
        self.assertIn("structure inconsistent", out)

    def test_the_image_text_surfaces_the_errors_and_warnings_of_the_decoded_trailer(self):
        image = build_image()
        trailer = trailer_bytes(0x4000, 8, image_ok=1, swap_info=2)  # test request with image_ok set
        status, out, _ = self.cli("image", self.write(image + trailer[len(image):]))
        self.assertEqual(0, status)
        self.assertIn("Warning: swap_info says test request but image_ok is set", out)
        trailer = trailer_bytes(0x4000, 8, image_ok=0x05)
        status, out, _ = self.cli("image", self.write(image + trailer[len(image):]))
        self.assertIn("ERROR: image_ok is bad", out)

    def test_the_text_output_shows_the_key_hash_and_a_shortened_signature(self):
        status, out, _ = self.cli("image", self.write(build_image()))
        self.assertEqual(0, status)
        self.assertIn(hashlib.sha256(FAKE_KEY).hexdigest(), out)
        self.assertIn("KEYHASH", out)
        self.assertIn("ECDSA_SIG", out)
        self.assertNotIn(FAKE_SIG.hex(), out)
        self.assertIn("...", out)
        self.assertIn("1.2.3+4", out)

    def test_the_json_output_parses_and_has_the_report_keys(self):
        status, out, _ = self.cli("image", self.write(build_image()), "--json")
        self.assertEqual(0, status)
        report = json.loads(out)
        self.assertEqual("digest ok", report["result"])
        self.assertEqual(hashlib.sha256(FAKE_KEY).hexdigest(), report["key_hash"])
        self.assertIs(False, report["signature_verified"])

    def test_the_json_exit_status_follows_the_result(self):
        image = bytearray(build_image())
        image[0x500] ^= 0xFF
        status, out, _ = self.cli("image", self.write(bytes(image)), "--json")
        self.assertEqual(1, status)
        self.assertEqual("digest MISMATCH", json.loads(out)["result"])

    def test_the_slot_1_header_check_of_an_erased_read(self):
        path = self.write(b"\xff" * 32)
        status, out, _ = self.cli("image", path, "--header-only")
        self.assertEqual(0, status)
        self.assertIn("no image", out)
        status, out, _ = self.cli("image", path, "--header-only", "--json")
        self.assertEqual(0, status)
        self.assertEqual("no image", json.loads(out)["classification"])

    def test_the_slot_1_header_check_of_a_read_with_the_image_magic(self):
        path = self.write(bytes.fromhex("3db8f396") + b"\xff" * 28)
        status, out, _ = self.cli("image", path, "--header-only")
        self.assertEqual(0, status)
        self.assertIn("image magic present", out)

    def test_the_header_check_accepts_a_whole_image_too(self):
        status, out, _ = self.cli("image", self.write(build_image()), "--header-only")
        self.assertEqual(0, status)
        self.assertIn("image magic present", out)

    def test_a_read_of_fewer_than_four_bytes_is_a_usage_error_for_the_header_check(self):
        status, _, err = self.cli("image", self.write(b"\x3d\xb8"), "--header-only")
        self.assertEqual(2, status)
        self.assertIn("4 bytes", err)

    def test_a_short_file_is_not_an_image_without_the_header_flag(self):
        status, out, _ = self.cli("image", self.write(b"\xff" * 32))
        self.assertEqual(1, status)
        self.assertIn("structure inconsistent", out)

    def test_a_trailer_exits_0_and_names_the_state(self):
        data = trailer_bytes(0x10000, 8, swap_info=2)
        status, out, _ = self.cli("trailer", self.write(data), "--align", "8")
        self.assertEqual(0, status)
        self.assertIn("PENDING_TEST", out)
        self.assertIn("test request pending", out)
        self.assertIn("good", out)

    def test_a_trailer_json_with_a_slot_size(self):
        # A file as long as the slot is a whole slot, so its first bytes are checked for the image magic.
        data = struct.pack("<I", IMAGE_MAGIC) + trailer_bytes(0x10000, 512, image_ok=1, copy_done=1)[4:]
        status, out, _ = self.cli("trailer", self.write(data), "--align", "512", "--slot-size", "65536",
                                  "--json")
        self.assertEqual(0, status)
        report = json.loads(out)
        self.assertEqual("STANDBY_CONFIRMED", report["slot_state"])
        self.assertEqual("equal", report["slot_size_check"])
        self.assertEqual(512, report["alignment"])

    def test_the_running_flag_changes_the_state_name(self):
        data = trailer_bytes(0x10000, 8, image_ok=1)
        status, out, _ = self.cli("trailer", self.write(data), "--align", "8", "--running")
        self.assertEqual(0, status)
        self.assertIn("RUNNING_CONFIRMED", out)

    def test_an_inconsistent_trailer_exits_1(self):
        data = trailer_bytes(0x10000, 8, magic="bad", image_ok=1)
        status, out, _ = self.cli("trailer", self.write(data), "--align", "8")
        self.assertEqual(1, status)
        self.assertIn("INVALID", out)

    def test_usage_errors_exit_2(self):
        path = self.write(b"\xff" * 64)
        missing = str(Path(self._dir.name) / "missing.bin")
        # (arguments, text that only the script can print on stderr)
        cases = [
            ((), "usage: inspect_boot_image.py"),
            (("image",), "usage: inspect_boot_image.py"),
            (("trailer", path), "usage: inspect_boot_image.py"),
            (("trailer", path, "--align", "0"), "usage: inspect_boot_image.py"),
            (("trailer", path, "--align", "eight"), "usage: inspect_boot_image.py"),
            (("trailer", path, "--align", "8", "--slot-size", "-1"), "usage: inspect_boot_image.py"),
            (("unknown", path), "usage: inspect_boot_image.py"),
            (("image", missing), "error: cannot read"),
            (("trailer", missing, "--align", "8"), "error: cannot read"),
        ]
        for args, text in cases:
            with self.subTest(args=args):
                status, _, err = self.cli(*args)
                self.assertEqual(2, status)
                self.assertIn(text, err)

    def test_help_states_the_limits(self):
        for args in (("--help",), ("image", "--help"), ("trailer", "--help")):
            with self.subTest(args=args):
                status, out, _ = self.cli(*args)
                self.assertEqual(0, status)
                self.assertIn("digest check only and NOT a signature verification", out)
                self.assertIn("imgtool verify", out)
                self.assertIn("not checked against upstream", out)
                self.assertIn("author's reading of MCUboot's image format", out)

    def test_main_returns_the_status_in_process(self):
        status, out, _ = run_main(["image", self.write(build_image())])
        self.assertEqual(0, status)
        self.assertIn("digest ok", out)
        status, _, _ = run_main(["trailer", self.write(b"\xff" * 64)])
        self.assertEqual(2, status)


if __name__ == "__main__":
    unittest.main()
