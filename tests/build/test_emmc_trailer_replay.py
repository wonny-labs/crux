#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Runs the MCUboot trailer replay tests of tests/native/emmc_trailer in this discovery.

The Host workflow discovers tests/build, so these Python-only tests run on every pull request
without a change to a workflow or a check script. They need no build and no MCUboot checkout.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'native',
                                'emmc_trailer'))

from test_trailer_model import BootOnceTest, LayoutTest, SwapStateTest  # noqa: E402,F401
from test_write_path import (LayoutCheckTest, RebuildTest, RecorderTest,  # noqa: E402,F401
                             RunnerTest, ScenarioTest, StagedTest)

if __name__ == '__main__':
    import unittest
    unittest.main()
