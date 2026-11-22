#!/usr/bin/env python3
"""Keep the classification table of samples/README.md in step with the samples/ tree."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "samples"


def listed_folders(text):
    """Folders named in the first column of the table under "## Classification"."""
    folders = set()
    body = text.split("\n## Classification\n", 1)[1]
    table = body.lstrip("\n").split("\n\n", 1)[0]  # the table right after the heading
    for line in table.splitlines():
        cells = line.split("|")
        if len(cells) < 3 or not line.startswith("| `"):
            continue
        for name in re.findall(r"`([^`]+/)`", cells[1]):
            folders.add(name.rstrip("/"))
    return folders


def application_folders():
    """Every folder under samples/ with its own sample.yaml or testcase.yaml."""
    found = set()
    for pattern in ("sample.yaml", "testcase.yaml"):
        for path in SAMPLES.rglob(pattern):
            found.add(path.parent.relative_to(SAMPLES).as_posix())
    return found


class SamplesReadme(unittest.TestCase):
    def setUp(self):
        self.listed = listed_folders((SAMPLES / "README.md").read_text(encoding="utf-8"))

    def test_every_listed_folder_exists(self):
        missing = sorted(f for f in self.listed if not (SAMPLES / f).is_dir())
        self.assertEqual([], missing)

    def test_every_application_is_listed(self):
        unlisted = sorted(f for f in application_folders()
                          if f not in self.listed and f.split("/")[0] not in self.listed)
        self.assertEqual([], unlisted)


if __name__ == "__main__":
    unittest.main()
