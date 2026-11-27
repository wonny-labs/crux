#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Staging refuses drifted sources and output inside the pinned checkout; fake inputs only."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

# The module's staging script (zephyr/settings_file.cmake runs it).
SCRIPT = Path(__file__).resolve().parents[3] / 'zephyr/prepare_settings_file.py'
SPEC = importlib.util.spec_from_file_location('prepare_settings_file', SCRIPT)
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)


class StagingSafety(unittest.TestCase):
    def test_output_inside_pinned_checkout_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            zephyr = Path(directory) / 'zephyr'
            zephyr.mkdir()
            with self.assertRaises(RuntimeError):
                prepare.prepare(zephyr, zephyr / 'generated')
            self.assertFalse((zephyr / 'generated').exists())

    def test_source_that_differs_from_the_pin_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            zephyr, output = root / 'zephyr', root / 'output'
            source = zephyr / 'subsys/settings/src'
            source.mkdir(parents=True)
            (source / 'settings_file.c').write_bytes(b'locally modified\n')
            with patch.object(prepare.subprocess, 'check_output', return_value=b'pinned\n'):
                with self.assertRaises(RuntimeError):
                    prepare.prepare(zephyr, output)
            self.assertFalse((output / 'manifest.json').exists())
            self.assertFalse((output / 'settings_file.c').exists())


if __name__ == '__main__':
    unittest.main()
