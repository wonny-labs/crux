#!/usr/bin/env python3
"""Pin the onboarding structure that docs/documentation-guidelines.md sets.

Getting started sets up the environment, the tutorial is one path (A Linux Host,
B native_sim, C your board) with one table of supported boards, and every board
detail lives on one page under docs/boards/. Adding a board is one new page and
one row in docs/boards/README.md and in the tutorial's board table.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
BOARDS = DOCS / "boards"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "docs_page_types.json"

# Commands and settings of a board procedure. They belong on a board page only.
BOARD_PROCEDURE = (
    "start-jlink-gdbserver",
    "JLinkGDBServer",
    "-localhostonly",
)


def read(path):
    return path.read_text(encoding="utf-8")


def board_pages():
    return sorted(p for p in BOARDS.glob("*.md") if p.name != "README.md")


def section(text, heading):
    """Return the text under a heading, up to the next heading of the same or a higher level."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.*)", line)
        if match and match.group(2).strip() == heading:
            level = len(match.group(1))
            body = []
            for rest in lines[index + 1:]:
                other = re.match(r"^(#{1,6})\s", rest)
                if other and len(other.group(1)) <= level:
                    break
                body.append(rest)
            return "\n".join(body)
    raise AssertionError(f"no heading {heading!r}")


class BoardPages(unittest.TestCase):
    def test_there_is_a_board_index_and_at_least_one_board_page(self):
        self.assertTrue((BOARDS / "README.md").is_file())
        self.assertIn(BOARDS / "mimxrt1060_evkb.md", board_pages())

    def test_the_index_has_one_row_per_board_page(self):
        index = read(BOARDS / "README.md")
        for page in board_pages():
            rows = [line for line in index.splitlines()
                    if line.startswith("|") and f"]({page.name})" in line]
            self.assertEqual(1, len(rows), page.name)

    def test_each_board_page_has_the_standard_sections(self):
        for page in board_pages():
            text = read(page)
            for heading in ("Board target", "Switches and jumpers", "Probe and connection",
                            "Flash and debug", "Recovery", "Board image profiles",
                            "Known limits"):
                self.assertRegex(text, rf"(?m)^## {heading}$", f"{page.name}: {heading}")

    def test_board_pages_have_page_types(self):
        types = json.loads(read(FIXTURE))["types"]
        self.assertEqual("reference", types.get("docs/boards/README.md"))
        for page in board_pages():
            self.assertEqual("how-to", types.get(page.relative_to(ROOT).as_posix()), page.name)


class Tutorial(unittest.TestCase):
    def setUp(self):
        self.text = read(DOCS / "tutorial.md")

    def test_one_path_in_three_parts(self):
        headings = re.findall(r"(?m)^## (Part [A-Z]\. .*)$", self.text)
        self.assertEqual(["Part A. Linux Host", "Part B. Zephyr", "Part C. Run on your board"],
                         headings)

    def test_part_c_opens_with_the_no_board_line(self):
        body = section(self.text, "Part C. Run on your board").strip()
        self.assertTrue(body.startswith("No board? Parts A and B run every sample and test."), body[:80])

    def test_the_board_table_has_one_row_per_board_page(self):
        body = section(self.text, "Part C. Run on your board")
        self.assertIn("| Board | `-b` target | Probe | Board guide |", body)
        for page in board_pages():
            rows = [line for line in body.splitlines()
                    if line.startswith("|") and f"](boards/{page.name})" in line]
            self.assertEqual(1, len(rows), page.name)
        self.assertIn("component-readiness.md", body)

    def test_part_c_links_the_board_page_that_owns_its_commands(self):
        # A tutorial may repeat the commands it runs; the board page owns them.
        body = section(self.text, "Part C. Run on your board")
        self.assertIn("](boards/mimxrt1060_evkb.md#flash-and-debug)", body)


class RunFromRepositoryRoot(unittest.TestCase):
    """Repository commands run from the repository root, where the VS Code terminal opens."""

    PAGES = (
        DOCS / "tutorial.md",
        DOCS / "rt1060-mbed-management-image.md",
        DOCS / "emmc-reliance-physical-gate.md",
        ROOT / "samples" / "README.md",
        ROOT / "samples" / "hello_crux" / "README.md",
        ROOT / "samples" / "file" / "basic" / "README.md",
        ROOT / "samples" / "time" / "shell" / "README.md",
        ROOT / "samples" / "networking" / "echo_client" / "README.md",
        ROOT / "tests" / "time_periodic" / "README.md",
    )

    def test_no_command_reaches_the_repository_from_the_workspace_root(self):
        for page in self.PAGES:
            text = read(page)
            for path in ("crux-pilot/samples", "crux-pilot/tests"):
                self.assertNotIn(path, text, page.relative_to(ROOT))
            self.assertNotIn("west workspace root", text, page.relative_to(ROOT))

    def test_the_tutorial_names_one_folder(self):
        text = read(DOCS / "tutorial.md")
        self.assertIn("All commands in this tutorial run from `/workspace/crux-pilot`, where the VS Code terminal"
                      " opens.", " ".join(text.split()))
        self.assertIsNone(re.search(r"from `/workspace`", text))
        self.assertNotIn("| Folder | What it is | Run from here |", text)


class GettingStarted(unittest.TestCase):
    def test_holds_no_board_procedure_and_links_the_board_pages(self):
        text = read(DOCS / "getting-started.md")
        for marker in BOARD_PROCEDURE:
            self.assertNotIn(marker, text)
        body = section(text, "7. If you use a board")
        self.assertIn("boards/README.md", body)


class BuildGuide(unittest.TestCase):
    def test_the_evkb_procedure_lives_on_the_board_page(self):
        text = read(DOCS / "build.md")
        for marker in BOARD_PROCEDURE:
            self.assertNotIn(marker, text)
        self.assertIn("boards/mimxrt1060_evkb.md", section(text, "RT1060-EVKB debugging"))
        board = read(BOARDS / "mimxrt1060_evkb.md")
        self.assertIn("scripts/macos/start-jlink-gdbserver.command", board)
        for marker in BOARD_PROCEDURE:
            self.assertIn(marker, board)


class Guidelines(unittest.TestCase):
    def test_the_rule_is_recorded(self):
        text = read(DOCS / "documentation-guidelines.md")
        body = section(text, "6. Onboarding and board pages")
        for needle in ("getting-started.md", "tutorial.md", "docs/boards/", "crux-controller",
                       "crux-codesys"):
            self.assertIn(needle, body)

    def test_the_map_links_the_board_pages(self):
        self.assertIn("boards/README.md", read(DOCS / "README.md"))


if __name__ == "__main__":
    unittest.main()
