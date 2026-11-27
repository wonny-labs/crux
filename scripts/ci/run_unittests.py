#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run a unittest discovery with a listed set of cases left out, or only that set.

    run_unittests.py -s tests/build --exclude-from scripts/ci/large-tests.txt
    run_unittests.py -s tests/build --only-from scripts/ci/large-tests.txt

The two runs together are exactly `python3 -m unittest discover -s tests/build -v`. A listed id
that discovery does not find is an error (exit 2), so a renamed case cannot drop out unnoticed.
The list holds one id per line (module.Class.method); # starts a comment.
"""
import argparse
from pathlib import Path
import sys
import unittest


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def read_ids(path):
    lines = Path(path).read_text().splitlines()
    return [line.split("#", 1)[0].strip() for line in lines if line.split("#", 1)[0].strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-s", "--start", required=True, help="the folder to discover")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--exclude-from", help="leave out the ids listed in this file")
    group.add_argument("--only-from", help="run only the ids listed in this file")
    args = parser.parse_args(argv)

    listed = read_ids(args.exclude_from or args.only_from)
    start = str(Path(args.start).resolve())
    suite = unittest.defaultTestLoader.discover(start, top_level_dir=start)
    cases = list(flatten(suite))
    found = {case.id() for case in cases}
    missing = [test_id for test_id in listed if test_id not in found]
    if missing:
        print(f"error: {missing[0]} is listed in {args.exclude_from or args.only_from} but discovery "
              f"of {args.start} does not find it. Fix the list. See docs/ci.md.", file=sys.stderr)
        return 2
    keep = set(listed)
    chosen = [c for c in cases if (c.id() in keep) == bool(args.only_from)]
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(chosen))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
