#!/usr/bin/env python3
"""Keep the repository README an entry point.

The README holds what a newcomer needs to decide and to start. Change history,
migration notes and per-component lifecycle belong on the pages that own them
(docs/README.md, "Keep the README an entry point"). This test looks only for
the usual markers of those topics, so it stays narrow and lexical.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"

# Each marker names a topic that has its own home outside the README.
MARKERS = {
    r"\bwas removed\b|\bis removed\b": "change history: use the contract page",
    r"\bmigrat(e|ed|es|ing|ion)\b": "migration note: use the contract page",
    r"\bfrozen\b": "lifecycle: use docs/component-readiness.md",
    r"\bto be removed\b": "lifecycle: use docs/component-readiness.md",
    r"\bdeprecat(e|ed|es|ion)\b": "lifecycle: use docs/component-readiness.md",
    r"\bexperimental\b": "stability tier: use docs/component-readiness.md",
}


def findings(text):
    found = []
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern, reason in MARKERS.items():
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                found.append(f"README.md:{number}: '{match.group(0)}' ({reason})")
    return found


class ReadmeScopeTest(unittest.TestCase):
    def test_the_readme_has_no_history_or_lifecycle_markers(self):
        self.assertEqual([], findings(README.read_text(encoding="utf-8")))

    def test_each_marker_is_found(self):
        samples = [
            "Crux Queue was removed; use Zephyr k_msgq",
            "see the migration note",
            "Execution (frozen for new product code)",
            "Device I/O (to be removed)",
            "The API is deprecated",
            "`image_state` (Experimental)",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(1, len(findings(sample)))

    def test_the_intro_names_zephyr_today_and_embedded_linux_as_expected(self):
        intro = README.read_text(encoding="utf-8").split("\n## ", 1)[0]
        self.assertNotIn("Zephyr firmware products", intro)
        self.assertIn("runs on Zephyr today", intro)
        self.assertRegex(intro, r"Embedded Linux integration is expected, with no date set")
        self.assertIn("docs/decisions/0003-", intro)
        self.assertNotRegex(intro, r"(?i)supports? (embedded )?linux products")

    def test_the_status_is_one_sentence_under_the_intro(self):
        text = README.read_text(encoding="utf-8")
        intro = text.split("\n## ", 1)[0]
        self.assertNotIn("\n## Status and limits", text)
        self.assertIn("not production-qualified", intro)
        self.assertIn("](docs/component-readiness.md)", intro)

    def test_the_documentation_map_holds_the_status_details_once(self):
        docs = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        section = docs.split("\n## Status and limits\n", 1)[1].split("\n## ", 1)[0]
        self.assertNotIn("README.md#status-and-limits", section)
        self.assertIn("pin a source revision", section)

    def test_ordinary_entry_point_text_passes(self):
        text = ("Crux is a reusable embedded software platform.\n"
                "Clone the repository and open it in the Dev Container.\n"
                "Products pin a source revision.\n")
        self.assertEqual([], findings(text))


if __name__ == "__main__":
    unittest.main()
