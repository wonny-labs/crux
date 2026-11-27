"""CMake Tools shows a preset's displayName, or its name when it has none.

The configure, build and test presets of one host build must read the same in the CMake side
bar, so each of them carries the same displayName.
"""
import json
from pathlib import Path
import unittest

PRESETS = Path(__file__).resolve().parents[2] / "CMakePresets.json"
KINDS = ("configurePresets", "buildPresets", "testPresets")


class CMakePresetNamesTest(unittest.TestCase):
    def setUp(self):
        self.presets = json.loads(PRESETS.read_text())

    def test_every_preset_has_a_display_name(self):
        for kind in KINDS:
            for preset in self.presets[kind]:
                with self.subTest(kind=kind, preset=preset["name"]):
                    self.assertTrue(preset.get("displayName"))

    def test_a_host_build_reads_the_same_in_every_kind(self):
        names = {}
        for kind in KINDS:
            for preset in self.presets[kind]:
                names.setdefault(preset["name"], set()).add(preset.get("displayName"))
        for name, display_names in names.items():
            with self.subTest(preset=name):
                self.assertEqual(len(display_names), 1, display_names)

    def test_display_names_carry_no_language_standard(self):
        for kind in KINDS:
            for preset in self.presets[kind]:
                with self.subTest(kind=kind, preset=preset["name"]):
                    self.assertNotRegex(preset.get("displayName", ""), r"C\+*\d\d|C17|C\+\+")


if __name__ == "__main__":
    unittest.main()
