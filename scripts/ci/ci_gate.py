#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Decide the `ci-gate` check from the results of the CI jobs it needs (docs/ci.md#merge-gate).

The `ci-gate` job of .github/workflows/ci.yml passes its `needs` context as JSON in the variable
CI_GATE_NEEDS. The gate passes only when at least one job is listed and every listed job concluded
`success`. A failed, cancelled or skipped job fails it. A job that the tier selected no check for
still runs and concludes `success`, so a path rule never fails the gate.

Exit status: 0 pass, 1 fail, 2 missing or malformed input.
"""
import json
import os
import sys


def decide(needs):
    """Return the problems with these job results; an empty list means the gate passes."""
    if not isinstance(needs, dict) or not needs:
        return ["no job results: the gate must need every CI job"]
    problems = []
    for job in sorted(needs):
        entry = needs[job]
        result = entry.get("result") if isinstance(entry, dict) else None
        if result != "success":
            problems.append(f"{job}: {result or 'no result'}")
    return problems


def main(env=os.environ, out=sys.stdout):
    text = env.get("CI_GATE_NEEDS")
    if text is None:
        print("ci_gate.py: set CI_GATE_NEEDS to the JSON of the needs context", file=out)
        return 2
    try:
        needs = json.loads(text)
    except ValueError as error:
        print(f"ci_gate.py: CI_GATE_NEEDS is not JSON: {error}", file=out)
        return 2
    if isinstance(needs, dict):
        for job in sorted(needs):
            entry = needs[job]
            print(f"{job}: {entry.get('result') if isinstance(entry, dict) else entry}", file=out)
    problems = decide(needs)
    if problems:
        print(f"::error title=ci-gate::Not every CI job succeeded: {'; '.join(problems)}", file=out)
        return 1
    print("Every CI job succeeded.", file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
