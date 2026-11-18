"""Check scripts/coverage-summary.py, which turns gcovr JSON reports into a per-component table.

The script is advisory output only: it must group by component directory, merge several
reports of the same file, ignore non-code lines, and never fail on a coverage figure.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/coverage-summary.py"


def load():
    spec = importlib.util.spec_from_file_location("coverage_summary", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def line(number, count, branches=(), **extra):
    entry = {"line_number": number, "count": count,
             "branches": [{"count": c} for c in branches]}
    entry.update(extra)
    return entry


def report(*files):
    return {"gcovr/format_version": "0.6", "files": [{"file": name, "lines": lines}
                                                      for name, lines in files]}


class SummaryTest(unittest.TestCase):
    def setUp(self):
        self.module = load()

    def test_groups_by_component_directory(self):
        data = report(
            ("components/file/a.c", [line(1, 1), line(2, 0)]),
            ("components/file/b.c", [line(1, 3)]),
            ("components/time/t.c", [line(1, 0)]),
            ("samples/x/main.c", [line(1, 1)]),
        )
        table = self.module.summarise([data])
        self.assertEqual((2, 3), table["file"]["lines"])
        self.assertEqual((0, 1), table["time"]["lines"])
        self.assertEqual((1, 1), table["samples"]["lines"])

    def test_counts_branches_taken(self):
        data = report(("components/file/a.c", [line(1, 2, branches=[1, 0, 4]), line(2, 1)]))
        table = self.module.summarise([data])
        self.assertEqual((2, 3), table["file"]["branches"])

    def test_ignores_non_code_and_excluded_lines(self):
        data = report(("components/file/a.c", [
            line(1, 1),
            line(2, 0, **{"gcovr/noncode": True}),
            line(3, 0, **{"gcovr/excluded": True}),
        ]))
        self.assertEqual((1, 1), self.module.summarise([data])["file"]["lines"])

    def test_merging_reports_counts_a_line_once_and_covered_if_any_run_hit_it(self):
        first = report(("components/file/a.c", [line(1, 1, branches=[1, 0]), line(2, 0)]))
        second = report(("components/file/a.c", [line(1, 0, branches=[0, 2]), line(2, 5)]))
        table = self.module.summarise([first, second])
        self.assertEqual((2, 2), table["file"]["lines"])
        self.assertEqual((2, 2), table["file"]["branches"])

    def test_percentage_of_nothing_is_a_dash_not_an_error(self):
        self.assertEqual("-", self.module.percent(0, 0))
        self.assertEqual("50.0%", self.module.percent(1, 2))

    def test_markdown_has_one_row_per_component_and_a_total(self):
        data = report(("components/file/a.c", [line(1, 1), line(2, 0)]),
                      ("components/time/t.c", [line(1, 1)]))
        text = self.module.markdown("Host", self.module.summarise([data]))
        self.assertIn("### Host", text)
        self.assertIn("| file | 1 / 2 (50.0%) | - |", text)
        self.assertIn("| time | 1 / 1 (100.0%) | - |", text)
        self.assertIn("| **total** | 2 / 3 (66.7%) | - |", text)
        self.assertIn("advisory", text.lower())

    def test_command_line_reads_files_and_exits_zero_even_at_zero_percent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "coverage.json"
            path.write_text(json.dumps(report(("components/file/a.c", [line(1, 0)]))))
            result = subprocess.run([sys.executable, "-I", str(SCRIPT), "--title", "Host", str(path)],
                                    capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("| file | 0 / 1 (0.0%) | - |", result.stdout)

    def test_command_line_reports_a_missing_or_broken_input_as_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / "broken.json"
            broken.write_text("{")
            for argument in (str(Path(directory) / "absent.json"), str(broken)):
                with self.subTest(argument=argument):
                    result = subprocess.run([sys.executable, "-I", str(SCRIPT), argument],
                                            capture_output=True, text=True)
                    self.assertNotEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
