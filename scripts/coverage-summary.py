#!/usr/bin/env python3
"""Summarise gcovr JSON reports as a per-component Markdown table (advisory output).

Usage: coverage-summary.py [--title TITLE] REPORT.json [REPORT.json ...]

Several reports of the same file are merged: a line or branch counts once and is covered
when any report covers it. Paths are grouped by the directory under `components/`, or by
their first directory otherwise. The script prints figures and never fails on their value.
It exits non-zero only when an input is missing or is not a gcovr JSON report.
"""
import argparse
import json
import sys
from pathlib import PurePosixPath


def component(path):
    parts = PurePosixPath(path).parts
    if len(parts) >= 3 and parts[0] == "components":
        return parts[1]
    return parts[0] if len(parts) > 1 else "(root)"


def summarise(reports):
    """Return {component: {'lines': (covered, total), 'branches': (covered, total)}}."""
    lines = {}
    branches = {}
    for data in reports:
        for entry in data["files"]:
            name = entry["file"]
            for item in entry.get("lines", []):
                if item.get("gcovr/noncode") or item.get("gcovr/excluded"):
                    continue
                key = (name, item["line_number"])
                lines[key] = lines.get(key, False) or item.get("count", 0) > 0
                for index, branch in enumerate(item.get("branches", [])):
                    bkey = (name, item["line_number"], index)
                    branches[bkey] = branches.get(bkey, False) or branch.get("count", 0) > 0
    table = {}
    for source, slot in ((lines, "lines"), (branches, "branches")):
        for key, covered in source.items():
            cell = table.setdefault(component(key[0]), {"lines": (0, 0), "branches": (0, 0)})
            hit, total = cell[slot]
            cell[slot] = (hit + int(covered), total + 1)
    return table


def percent(hit, total):
    return "-" if total == 0 else f"{100.0 * hit / total:.1f}%"


def cell(value):
    hit, total = value
    return "-" if total == 0 else f"{hit} / {total} ({percent(hit, total)})"


def markdown(title, table):
    rows = [f"### {title}", "",
            "Advisory measurement only: no threshold applies and nothing is gated on these figures.",
            "", "| Component | Lines | Branches |", "| --- | --- | --- |"]
    totals = {"lines": (0, 0), "branches": (0, 0)}
    for name in sorted(table):
        rows.append(f"| {name} | {cell(table[name]['lines'])} | {cell(table[name]['branches'])} |")
        for slot in totals:
            totals[slot] = (totals[slot][0] + table[name][slot][0],
                            totals[slot][1] + table[name][slot][1])
    rows.append(f"| **total** | {cell(totals['lines'])} | {cell(totals['branches'])} |")
    return "\n".join(rows) + "\n"


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--title", default="Coverage")
    parser.add_argument("reports", nargs="+")
    args = parser.parse_args(argv)
    loaded = []
    for path in args.reports:
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            if "files" not in data:
                raise ValueError("no 'files' list")
        except (OSError, ValueError) as error:
            print(f"coverage-summary: cannot read {path}: {error}", file=sys.stderr)
            return 1
        loaded.append(data)
    sys.stdout.write(markdown(args.title, summarise(loaded)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
