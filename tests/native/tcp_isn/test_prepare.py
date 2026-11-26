#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The fail-closed TCP initial sequence number refuses a drifted tcp.c and output inside Zephyr.

The good run needs the pinned Zephyr checkout, named by ZEPHYR_BASE. scripts/test-tcp-isn.sh runs it.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
if not os.environ.get("ZEPHYR_BASE"):
    raise RuntimeError("ZEPHYR_BASE is unset: set it to the pinned Zephyr checkout to run test_prepare.py")
ZEPHYR = Path(os.environ["ZEPHYR_BASE"])
SCRIPT = ROOT / "scripts/prepare-tcp-isn.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREPARE = load("prepare_tcp_isn", SCRIPT)


def fake_zephyr(root, source):
    """A Zephyr tree holding only the given tcp.c bytes."""
    zephyr = root / "zephyr"
    (zephyr / PREPARE.RELATIVE_SOURCE).parent.mkdir(parents=True)
    (zephyr / PREPARE.RELATIVE_SOURCE).write_bytes(source)
    return zephyr


class Preparation(unittest.TestCase):
    def setUp(self):
        self.pinned = (ZEPHYR / PREPARE.RELATIVE_SOURCE).read_bytes()

    def test_the_patch_is_the_one_in_patches(self):
        self.assertEqual(PREPARE.PATCH, ROOT / "patches/zephyr/tcp-isn-fail-closed.patch")
        self.assertTrue(PREPARE.PATCH.is_file())

    def test_source_with_one_changed_byte_is_rejected(self):
        changed = bytearray(self.pinned)
        changed[len(changed) // 2] ^= 0x01
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            zephyr = fake_zephyr(root, bytes(changed))
            output = root / "out/tcp.c"
            with self.assertRaises(ValueError):
                PREPARE.prepare(zephyr, output)
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix(".json").exists())

    def test_a_changed_patch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            zephyr = fake_zephyr(root, self.pinned)
            patch = root / "changed.patch"
            patch.write_bytes(PREPARE.PATCH.read_bytes().replace(b"connect refused", b"connect refused!"))
            output = root / "out/tcp.c"
            with self.assertRaises(ValueError):
                PREPARE.prepare(zephyr, output, patch)
            self.assertFalse(output.exists())

    def test_output_inside_zephyr_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            zephyr = fake_zephyr(Path(directory), self.pinned)
            output = zephyr / "subsys/net/ip/generated/tcp.c"
            with self.assertRaises(ValueError):
                PREPARE.prepare(zephyr, output)
            self.assertFalse(output.exists())

    def test_good_run_writes_the_source_and_its_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            zephyr = fake_zephyr(root, self.pinned)
            output = root / "out/tcp.c"
            metadata = PREPARE.prepare(zephyr, output)
            generated = output.read_bytes()
            self.assertNotEqual(generated, self.pinned)
            self.assertNotIn(b"using random ISN", generated)
            self.assertIn(b"static int tcp_init_isn(", generated)
            self.assertIn(b"connect refused", generated)
            self.assertEqual(json.loads(output.with_suffix(".json").read_text()), metadata)
            self.assertEqual(metadata["generated_sha256"], PREPARE.PATCHED_SHA256)
            self.assertEqual(metadata["upstream_sha256"], PREPARE.BASE_SHA256)
            self.assertTrue(metadata["patch_applied"])
            self.assertEqual((zephyr / PREPARE.RELATIVE_SOURCE).read_bytes(), self.pinned)

    def test_a_tree_that_already_fails_closed_is_copied_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first/tcp.c"
            PREPARE.prepare(fake_zephyr(root / "a", self.pinned), first)
            zephyr = fake_zephyr(root / "b", first.read_bytes())
            output = root / "out/tcp.c"
            metadata = PREPARE.prepare(zephyr, output)
            self.assertEqual(output.read_bytes(), first.read_bytes())
            self.assertFalse(metadata["patch_applied"])
            self.assertEqual(metadata["generated_sha256"], PREPARE.PATCHED_SHA256)

    def test_the_wolfssl_bench_copy_of_v4_4_2_is_known_as_fail_closed(self):
        # That copy carries patches/zephyr/zephyr-isn-fail-closed.patch, applied by its own script; the two scripts
        # must name the same result.
        wolf = load("prepare_isn_fail_closed", ROOT / "scripts/prepare-isn-fail-closed.py")
        self.assertIn(wolf.PATCHED_SHA256, PREPARE.ALREADY_FAIL_CLOSED)
        self.assertNotIn(wolf.BASE_SHA256, PREPARE.ALREADY_FAIL_CLOSED)
        self.assertNotIn(PREPARE.BASE_SHA256, PREPARE.ALREADY_FAIL_CLOSED)

    def test_the_command_line_names_the_failure_and_writes_nothing(self):
        changed = bytearray(self.pinned)
        changed[0] ^= 0x01
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            zephyr = fake_zephyr(root, bytes(changed))
            output = root / "out/tcp.c"
            result = subprocess.run([sys.executable, str(SCRIPT), str(zephyr), str(output)],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("FAIL:", result.stderr)
            self.assertIn("patches/zephyr/README.md", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
