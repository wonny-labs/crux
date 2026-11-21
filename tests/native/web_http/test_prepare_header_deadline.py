#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The header-phase deadline correction refuses a drifted source and output inside Zephyr.

The good run needs the pinned Zephyr checkout, named by ZEPHYR_BASE. scripts/test-web.sh runs it.
"""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
if not os.environ.get("ZEPHYR_BASE"):
    raise RuntimeError("ZEPHYR_BASE is unset: set it to the pinned Zephyr checkout")
ZEPHYR = Path(os.environ["ZEPHYR_BASE"])
SPEC = importlib.util.spec_from_file_location(
    "prepare_header_deadline", ROOT / "components/web/ports/zephyr/prepare_header_deadline.py")
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


def fake_zephyr(root, source):
    """A Zephyr tree holding only the given http_server_core.c bytes."""
    zephyr = root / "zephyr"
    (zephyr / PREPARE.RELATIVE_SOURCE).parent.mkdir(parents=True)
    (zephyr / PREPARE.RELATIVE_SOURCE).write_bytes(source)
    return zephyr


class Preparation(unittest.TestCase):
    def setUp(self):
        self.pinned = (ZEPHYR / PREPARE.RELATIVE_SOURCE).read_bytes()

    def test_the_patch_is_the_one_in_patches(self):
        self.assertEqual(PREPARE.PATCH, ROOT / "patches/zephyr/http-header-deadline.patch")
        self.assertTrue(PREPARE.PATCH.is_file())

    def test_source_with_one_changed_byte_is_rejected(self):
        changed = bytearray(self.pinned)
        changed[len(changed) // 2] ^= 0x01
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            zephyr = fake_zephyr(root, bytes(changed))
            output = root / "out/http_server_core.c"
            with self.assertRaises(ValueError):
                PREPARE.prepare(zephyr, output)
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix(".json").exists())

    def test_output_inside_zephyr_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            zephyr = fake_zephyr(Path(directory), self.pinned)
            output = zephyr / "subsys/net/lib/http/generated/http_server_core.c"
            with self.assertRaises(ValueError):
                PREPARE.prepare(zephyr, output)
            self.assertFalse(output.exists())

    def test_good_run_writes_the_source_and_its_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            zephyr = fake_zephyr(root, self.pinned)
            output = root / "out/http_server_core.c"
            metadata = PREPARE.prepare(zephyr, output)
            generated = output.read_bytes()
            self.assertNotEqual(generated, self.pinned)
            self.assertIn(b"header_deadline_check", generated)
            self.assertIn(b"CONFIG_CRUX_WEB_HEADER_DEADLINE_MS", generated)
            self.assertEqual(json.loads(output.with_suffix(".json").read_text()), metadata)
            self.assertEqual(metadata["generated_sha256"], PREPARE.PATCHED_SHA256)
            self.assertEqual(metadata["upstream_sha256"], PREPARE.BASE_SHA256)
            self.assertEqual((zephyr / PREPARE.RELATIVE_SOURCE).read_bytes(), self.pinned)


if __name__ == "__main__":
    unittest.main()
