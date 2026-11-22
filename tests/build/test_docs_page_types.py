#!/usr/bin/env python3
"""Stop new drift from the documentation guidelines.

docs/documentation-guidelines.md gives every page one type. Current-state pages
(entry, tutorial, how-to, reference and explanation) describe what is true now:
change history, pull request provenance and component status have their own
homes. This test looks for the usual lexical markers of those topics, per page
type, and fails only when a page has more of them than the recorded allowlist.

The allowlist and the page types live in fixtures/docs_page_types.json. The
audit in docs/plans/documentation-audit-2026-11.md recorded the current
offenders; fixing a page lowers its count. The top-level README.md has its own
guard (test_readme_scope.py) and is not scanned here.
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "docs_page_types.json"

# Page types from docs/documentation-guidelines.md.
CURRENT_TYPES = {"entry", "tutorial", "how-to", "reference", "explanation"}
OTHER_TYPES = {"record", "decision", "plan", "history", "evidence", "template"}

# Folders whose pages have their own type and are not scanned.
TYPED_FOLDERS = {
    "docs/history/": "history",
    "docs/plans/": "plan",
    "docs/superpowers/plans/": "plan",
    "docs/evidence/": "evidence",
    "docs/decisions/": "decision",
    "docs/research/": "record",
}

# Governance files and test fixtures are out of scope; README.md has its own test.
UNSCANNED = {"README.md", "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", "docs/baseline.md"}
UNSCANNED_PREFIXES = (".claude/", "tests/build/fixtures/")

MONTHS = ("January|February|March|April|May|June|July|August|September|"
          "October|November|December")

# rule name -> (pattern, flags, where the topic belongs)
RULES = {
    "history": (
        r"\b(?:was|were|has been|have been|is now|are now) "
        r"(?:removed|renamed|replaced|dropped|deleted)\b"
        r"|\b(?:moved|renamed) from\b|\bpreviously\b|\bno longer\b|\bformerly\b"
        r"|\bwill be (?:frozen|removed|deprecated)\b",
        re.IGNORECASE,
        "change history: CHANGELOG, the contract's migration notes or docs/history/",
    ),
    "provenance": (
        r"\bmerged in \[?(?:PR|pull request)\b|\bfor review in a Draft PR\b"
        rf"|\b(?:on|since|until) \d{{1,2}} (?:{MONTHS}) 20\d\d\b",
        re.IGNORECASE,
        "provenance and dates: the pull request, the issue or docs/history/",
    ),
    "status": (
        r"\bExperimental\b|\bUnstable\b|\bto be removed\b|\bdeprecated\b"
        # "frozen manifest", "frozen lock" and the like are release terms, not status.
        r"|\bfrozen\b(?![ -](?:manifest|lock|inputs?|evidence|copy|tree|workspace|revision|patched|Zephyr))"
        r"|\b(?:ran|run|been run|executed) on (?:a|the|any) (?:real |physical )?board\b",
        0,
        "lifecycle and verification status: docs/component-readiness.md",
    ),
}
# Rules waived on one page because that page is the topic's home.
HOMES = {"status": {"docs/component-readiness.md"}}

FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^(#{1,6})\s+(.*)")
CODE_SPAN = re.compile(r"`[^`]*`")


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def page_type(path, types):
    for folder, kind in TYPED_FOLDERS.items():
        if path.startswith(folder):
            return kind
    # A page nobody has classified yet gets the strictest treatment.
    return types.get(path, "reference")


def scanned_pages():
    raw = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z", "--", "*.md"])
    for entry in raw.split(b"\0"):
        path = entry.decode()
        if (not path or path in UNSCANNED or path.startswith(UNSCANNED_PREFIXES)
                or not (ROOT / path).is_file()):
            continue
        if path.startswith("docs/") or path.endswith("README.md") or path.startswith("templates/"):
            yield path


def findings(path, text, kind):
    """Return (rule, line number, matched text) for a page of the given type."""
    if kind not in CURRENT_TYPES:
        return []
    found = []
    in_fence = False
    migration_section = 0  # heading level of an open "Migration notes" section
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            if migration_section and level <= migration_section:
                migration_section = 0
            if kind == "reference" and re.search(r"migration", heading.group(2), re.IGNORECASE):
                migration_section = level
        # Text in a code span is quoted, such as a symbol or a marker being described.
        prose = CODE_SPAN.sub("", line)
        for rule, (pattern, flags, _) in RULES.items():
            if path in HOMES.get(rule, ()):
                continue
            if rule == "history" and migration_section:
                continue
            for match in re.finditer(pattern, prose, flags):
                found.append((rule, number, match.group(0)))
    return found


def counts(path, text, kind):
    result = {}
    for rule, _, _ in findings(path, text, kind):
        result[rule] = result.get(rule, 0) + 1
    return result


class DocsPageTypesTest(unittest.TestCase):
    def test_no_page_has_more_markers_than_its_allowlist(self):
        fixture = load_fixture()
        allow = fixture["allowlist"]
        problems = []
        for path in scanned_pages():
            kind = page_type(path, fixture["types"])
            text = (ROOT / path).read_text(encoding="utf-8")
            limit = allow.get(path, {})
            got = counts(path, text, kind)
            for rule, number in sorted(got.items()):
                if number > limit.get(rule, 0):
                    lines = [f"{n}: '{m}'" for r, n, m in findings(path, text, kind) if r == rule]
                    problems.append(
                        f"{path} ({kind}): {number} '{rule}' markers, allowlist "
                        f"{limit.get(rule, 0)} ({RULES[rule][2]}); lines {', '.join(lines)}")
        self.assertEqual([], problems, "\n" + "\n".join(problems))

    def test_fixture_uses_known_types_and_rules(self):
        fixture = load_fixture()
        for path, kind in fixture["types"].items():
            with self.subTest(path=path):
                self.assertIn(kind, CURRENT_TYPES | OTHER_TYPES)
        for path, limits in fixture["allowlist"].items():
            for rule, number in limits.items():
                with self.subTest(path=path, rule=rule):
                    self.assertIn(rule, RULES)
                    self.assertGreater(number, 0)

    def test_each_rule_finds_its_marker(self):
        samples = {
            "history": ["Crux Queue was removed on purpose", "It previously used NVS",
                        "The option is no longer read", "Serial will be removed in v0.2",
                        "This template moved from samples/product_template"],
            "provenance": ["Status: merged in [PR #210](x)", "for review in a Draft PR",
                           "approved on 23 October 2026"],
            "status": ["`image_state` is Experimental", "GPIO is frozen",
                       "Device I/O, to be removed", "Nothing here ran on a board"],
        }
        for rule, lines in samples.items():
            for line in lines:
                with self.subTest(line=line):
                    self.assertEqual([rule], [r for r, _, _ in findings("x.md", line, "how-to")])

    def test_current_text_and_other_types_pass(self):
        text = ("Build the sample with west.\n"
                "The handle is invalid after close.\n"
                "Release from a frozen manifest and a frozen lock.\n"
                "The marker `was removed` is quoted in a code span.\n"
                "```\nthis was removed in a code block\n```\n")
        self.assertEqual([], findings("x.md", text, "tutorial"))
        self.assertEqual([], findings("x.md", "Crux Queue was removed", "record"))

    def test_migration_section_of_a_reference_page_allows_history(self):
        text = ("# Queue\n## Migration notes\nQueue was removed; use k_msgq.\n"
                "## Limits\nIt previously blocked.\n")
        self.assertEqual([("history", 5, "previously")], findings("x.md", text, "reference"))
        self.assertEqual(2, len(findings("x.md", text, "how-to")))

    def test_the_status_home_may_state_status(self):
        self.assertEqual([], findings("docs/component-readiness.md", "GPIO is frozen", "reference"))

    def test_unclassified_pages_and_typed_folders(self):
        self.assertEqual("reference", page_type("docs/new-page.md", {}))
        self.assertEqual("history", page_type("docs/history/x.md", {}))
        self.assertEqual("evidence", page_type("docs/evidence/a/b.md", {"docs/evidence/a/b.md": "how-to"}))


if __name__ == "__main__":
    unittest.main()
