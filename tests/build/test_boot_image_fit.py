#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the `fit` command of tests/target/inspect_boot_image.py on synthetic images.

`fit` answers whether a signed image fits a slot: the image plus the trailer region must not pass the
slot size (oversized), the slot size and offset must sit on an erase unit, a padded image must be
exactly the slot size, and the trailer alignment of a padded image must be the requested one
(misaligned). The inputs are built in memory with the helpers of test_boot_image_inspect.py, so they
carry the same limits: the TLV layout is the author's reading, the trailer reach comes from the
repository's trailer model, and nothing here is an image from a build or a board. These tests show
what the tool decides on such inputs, not what imgtool or MCUboot accept. The standard library only.
"""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = load_module(HERE / "test_boot_image_inspect.py", "test_boot_image_inspect_for_fit_tests")
inspector = base.inspector
KIB = 1024
SLOT = 3 * 1024 * KIB  # the slot size of the composition
FIELD_NAMES = {"image", "layout", "size", "padding", "trailer alignment"}


def padded_slot(image, slot_size, align, magic="good"):
    """The image at the start of a slot-sized buffer whose end carries the trailer magic."""
    assert len(image) <= slot_size - 16, "the image must leave room for the trailer magic"
    slot = bytearray(base.trailer_bytes(slot_size, align, magic=magic))
    slot[:len(image)] = image
    return bytes(slot)


def check(data, **kwargs):
    kwargs.setdefault("erase_unit", 1)
    return inspector.check_fit(data, **kwargs)


def statuses(report):
    return {entry["name"]: entry["status"] for entry in report["checks"]}


class FitSizeTest(unittest.TestCase):
    def setUp(self):
        self.image = base.build_image()
        self.reach = inspector.trailer_distances(8)["swap_info"]

    def test_an_image_in_a_large_slot_fits(self):
        report = check(self.image, slot_size=64 * KIB, align=8)
        self.assertTrue(report["ok"], report)
        self.assertEqual("fits", report["result"])
        self.assertEqual(len(self.image), report["image_bytes"])
        self.assertEqual(self.reach, report["trailer_bytes"])

    def test_an_image_that_just_leaves_room_for_the_trailer_fits(self):
        report = check(self.image, slot_size=len(self.image) + self.reach, align=8)
        self.assertTrue(report["ok"], report)
        self.assertEqual(0, report["over_by"])

    def test_one_byte_less_than_image_and_trailer_is_oversized(self):
        report = check(self.image, slot_size=len(self.image) + self.reach - 1, align=8)
        self.assertFalse(report["ok"])
        self.assertEqual("does not fit", report["result"])
        self.assertEqual(1, report["over_by"])
        self.assertEqual("fail", statuses(report)["size"])
        self.assertIn("oversized", " ".join(e["detail"] for e in report["checks"]))

    def test_the_trailer_reach_depends_on_the_alignment(self):
        slot = len(self.image) + inspector.trailer_distances(8)["swap_info"]
        self.assertTrue(check(self.image, slot_size=slot, align=8)["ok"])
        self.assertFalse(check(self.image, slot_size=slot, align=512)["ok"])

    def test_an_image_larger_than_the_slot_is_oversized_without_an_alignment(self):
        report = check(self.image, slot_size=len(self.image) - 1)
        self.assertFalse(report["ok"])
        self.assertEqual("fail", statuses(report)["size"])

    def test_without_an_alignment_the_trailer_is_not_counted_and_says_so(self):
        report = check(self.image, slot_size=len(self.image))
        self.assertTrue(report["ok"], report)
        self.assertIsNone(report["trailer_bytes"])
        self.assertEqual("info", statuses(report)["size"])

    def test_a_file_longer_than_the_slot_is_oversized(self):
        data = self.image + b"\xff" * (64 * KIB)
        report = check(data, slot_size=64 * KIB, align=8)
        self.assertFalse(report["ok"])
        self.assertEqual("fail", statuses(report)["size"])


class FitLayoutTest(unittest.TestCase):
    def setUp(self):
        self.image = base.build_image()

    def test_a_slot_size_on_the_erase_unit_passes(self):
        report = inspector.check_fit(self.image, slot_size=SLOT, align=8, slot_offset=0x20000)
        self.assertTrue(report["ok"], report)
        self.assertEqual("ok", statuses(report)["layout"])

    def test_the_default_erase_unit_is_64_kib(self):
        report = inspector.check_fit(self.image, slot_size=SLOT + 4 * KIB, align=8)
        self.assertFalse(report["ok"])
        self.assertEqual("fail", statuses(report)["layout"])
        self.assertIn("misaligned", " ".join(e["detail"] for e in report["checks"]))

    def test_a_slot_offset_off_the_erase_unit_fails(self):
        report = inspector.check_fit(self.image, slot_size=SLOT, align=8, slot_offset=0x21000)
        self.assertFalse(report["ok"])
        self.assertEqual("fail", statuses(report)["layout"])

    def test_a_smaller_erase_unit_accepts_what_the_default_refuses(self):
        report = inspector.check_fit(self.image, slot_size=SLOT + 4 * KIB, align=8, erase_unit=4 * KIB)
        self.assertTrue(report["ok"], report)

    def test_without_an_offset_the_offset_is_not_judged(self):
        report = inspector.check_fit(self.image, slot_size=SLOT, align=8)
        self.assertNotIn("offset", " ".join(e["detail"] for e in report["checks"] if e["name"] == "layout"))


class FitPaddedImageTest(unittest.TestCase):
    def setUp(self):
        self.image = base.build_image()

    def test_an_image_padded_to_the_slot_with_the_right_trailer_fits(self):
        report = check(padded_slot(self.image, 64 * KIB, 8), slot_size=64 * KIB, align=8)
        self.assertTrue(report["ok"], report)
        self.assertEqual("ok", statuses(report)["padding"])
        self.assertEqual("ok", statuses(report)["trailer alignment"])

    def test_a_padded_image_of_another_length_than_the_slot_fails(self):
        data = padded_slot(self.image, 64 * KIB, 8)
        report = check(data, slot_size=128 * KIB, align=8)
        self.assertFalse(report["ok"])
        self.assertEqual("fail", statuses(report)["padding"])

    def test_a_trailer_of_another_alignment_is_misaligned(self):
        data = padded_slot(self.image, 64 * KIB, 16)
        report = check(data, slot_size=64 * KIB, align=8)
        self.assertFalse(report["ok"])
        self.assertEqual("fail", statuses(report)["trailer alignment"])
        self.assertIn("misaligned", " ".join(e["detail"] for e in report["checks"]))

    def test_the_trailer_alignment_is_not_judged_without_a_requested_alignment(self):
        data = padded_slot(self.image, 64 * KIB, 16)
        report = check(data, slot_size=64 * KIB)
        self.assertTrue(report["ok"], report)
        self.assertEqual("info", statuses(report)["trailer alignment"])

    def test_a_padded_image_without_a_trailer_magic_is_reported_not_failed_for_alignment(self):
        data = padded_slot(self.image, 64 * KIB, 8, magic="unset")
        report = check(data, slot_size=64 * KIB, align=8)
        self.assertEqual("info", statuses(report)["trailer alignment"])

    def test_an_unpadded_image_has_no_padding_or_trailer_judgement(self):
        report = check(self.image, slot_size=64 * KIB, align=8)
        self.assertEqual("ok", statuses(report)["padding"])
        self.assertEqual("info", statuses(report)["trailer alignment"])

    def test_the_trailer_overlapping_the_image_is_oversized(self):
        # About 3.2 KiB of image in a 4 KiB slot leaves room for the 16-byte magic, but not for the
        # 2048 bytes that the trailer fields of alignment 512 reach below the end.
        image = base.build_image(payload=bytes(range(256)) * 8)
        size = 4 * KIB
        data = padded_slot(image, size, 512)
        self.assertEqual(size, len(data))
        report = check(data, slot_size=size, align=512)
        self.assertFalse(report["ok"])
        self.assertEqual("fail", statuses(report)["size"])
        self.assertEqual("ok", statuses(report)["padding"])
        detail = next(e["detail"] for e in report["checks"] if e["name"] == "size")
        self.assertIn("trailer region", detail)
        self.assertGreater(report["over_by"], 0)


class FitImageValidityTest(unittest.TestCase):
    def test_an_image_whose_digest_does_not_match_fails_the_image_check(self):
        data = bytearray(base.build_image())
        data[0x500] ^= 0xFF
        report = check(bytes(data), slot_size=64 * KIB, align=8)
        self.assertFalse(report["ok"])
        self.assertEqual("fail", statuses(report)["image"])

    def test_garbage_is_not_an_image(self):
        report = check(b"\x00" * 100, slot_size=64 * KIB, align=8)
        self.assertFalse(report["ok"])
        self.assertEqual("fail", statuses(report)["image"])

    def test_every_check_is_named_and_has_a_status_and_detail(self):
        report = check(base.build_image(), slot_size=64 * KIB, align=8)
        self.assertEqual(FIELD_NAMES, {e["name"] for e in report["checks"]})
        for entry in report["checks"]:
            self.assertIn(entry["status"], {"ok", "fail", "info"})
            self.assertTrue(entry["detail"])

    def test_it_does_not_claim_a_signature_check_or_boot_behaviour(self):
        report = check(base.build_image(), slot_size=64 * KIB, align=8)
        self.assertFalse(report["signature_verified"])
        self.assertIn("NOT a signature verification", report["signature_note"])


class FitCommandTest(base.TempFiles):
    def test_a_fitting_image_exits_0_and_prints_the_result(self):
        path = self.write(base.build_image(), "ok.bin")
        status, out, err = base.run_main(["fit", path, "--slot-size", str(64 * KIB), "--align", "8",
                                          "--erase-unit", "1"])
        self.assertEqual(0, status, err)
        self.assertIn("Result: fits", out)

    def test_an_oversized_image_exits_1_and_says_by_how_much(self):
        image = base.build_image()
        path = self.write(image, "big.bin")
        status, out, _ = base.run_main(["fit", path, "--slot-size", str(len(image)), "--align", "8",
                                        "--erase-unit", "1"])
        self.assertEqual(1, status)
        self.assertIn("Result: does not fit", out)
        self.assertIn("over by", out)

    def test_json_output_carries_the_checks(self):
        path = self.write(base.build_image(), "ok.bin")
        status, out, _ = base.run_main(["fit", path, "--slot-size", str(SLOT), "--align", "8", "--json",
                                        "--slot-offset", "0x20000"])
        self.assertEqual(0, status)
        report = json.loads(out)
        self.assertEqual("fit", report["kind"])
        self.assertTrue(report["ok"])
        self.assertEqual(FIELD_NAMES, {e["name"] for e in report["checks"]})

    def test_the_slot_size_is_required(self):
        path = self.write(base.build_image(), "ok.bin")
        status, _, _ = base.run_main(["fit", path])
        self.assertEqual(2, status)

    def test_an_unreadable_file_is_a_usage_error(self):
        status, _, err = base.run_main(["fit", "/nonexistent/image.bin", "--slot-size", "65536"])
        self.assertEqual(2, status)
        self.assertIn("cannot read", err)

    def test_a_zero_erase_unit_is_a_usage_error(self):
        path = self.write(base.build_image(), "ok.bin")
        status, _, _ = base.run_main(["fit", path, "--slot-size", "65536", "--erase-unit", "0"])
        self.assertEqual(2, status)


if __name__ == "__main__":
    unittest.main()
