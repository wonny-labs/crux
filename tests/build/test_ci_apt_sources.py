# SPDX-License-Identifier: Apache-2.0
"""Check that CI index updates read only the apt sources the jobs use.

The hosted Ubuntu runner image adds a packages.microsoft.com source that no job here installs
from. When that server refuses the index, `apt-get update` exits with an error and the job fails
before any check runs. Each step that updates the index therefore first removes the source files
that name that server, and logs each file it removes. The update itself stays strict: no step
may ignore its exit status.

Only the standard library is used.
"""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[2]
# The tests skip only in a copy without the workflow folder.
WORKFLOWS = REPO / ".github/workflows"
NO_GITHUB = "this copy has no .github/workflows; see docs/ci.md#copies-without-github"
# Removes only the files that name the Microsoft server, prints each one, and fails the step if
# the folder cannot be read or a file cannot be removed. A missing source is not an error.
REMOVE = ("sudo find /etc/apt/sources.list.d -maxdepth 1 -type f"
          " -exec grep -q 'packages\\.microsoft\\.com' {} \\;"
          " -printf 'Removing unused apt source %p\\n' -delete")
UPDATE = re.compile(r"\bapt-get\b.*\bupdate\b")
IGNORED_STATUS = re.compile(r"\|\|\s*(true\b|:(\s|$))|continue-on-error:\s*true|\bset \+e\b", re.MULTILINE)


def steps(workflow):
    """Split a workflow into its steps: {'title', 'lines'}, in file order.

    Every workflow here lists its steps at an indentation of six spaces.
    """
    result = []
    current = None
    for line in workflow.splitlines():
        if line.startswith("      - "):
            current = {"title": line.strip(), "lines": [line]}
            result.append(current)
        elif current is not None and (line.startswith("       ") or not line.strip()):
            current["lines"].append(line)
        else:
            current = None
    return result


def unguarded_updates(workflow):
    """Return the titles of the steps that update the index without first removing the source."""
    result = []
    for step in steps(workflow):
        commands = [line.strip() for line in step["lines"]]
        for index, command in enumerate(commands):
            if UPDATE.search(command) and REMOVE not in commands[:index]:
                result.append(step["title"])
    return result


def ignored_statuses(workflow):
    """Return the titles of the steps that update the index and may ignore a failure."""
    return [s["title"] for s in steps(workflow)
            if any(UPDATE.search(line) for line in s["lines"])
            and IGNORED_STATUS.search("\n".join(s["lines"]))]


def job(*commands, title="Install host packages"):
    lines = ["jobs:", "  build:", "    steps:", f"      - name: {title}", "        run: |"]
    return "\n".join(lines + [f"          {c}" for c in commands]) + "\n"


class AptSourceRuleTest(unittest.TestCase):
    """The rules must report the cases they exist for."""

    def test_an_update_without_the_removal_is_reported(self):
        workflow = job("sudo apt-get update", "sudo apt-get install -y gperf")
        self.assertEqual(["- name: Install host packages"], unguarded_updates(workflow))

    def test_the_removal_after_the_update_is_reported(self):
        workflow = job("sudo apt-get update", REMOVE)
        self.assertEqual(["- name: Install host packages"], unguarded_updates(workflow))

    def test_the_removal_in_an_earlier_step_is_reported(self):
        workflow = job(REMOVE) + "\n".join(["      - name: Update", "        run: sudo apt-get update"]) + "\n"
        self.assertEqual(["- name: Update"], unguarded_updates(workflow))

    def test_the_removal_before_the_update_is_accepted(self):
        self.assertEqual([], unguarded_updates(job(REMOVE, "sudo apt-get update")))

    def test_an_ignored_update_failure_is_reported(self):
        for command in ("sudo apt-get update || true", "sudo apt-get update || :", "set +e"):
            with self.subTest(command=command):
                workflow = job(REMOVE, command, "sudo apt-get update")
                self.assertEqual(["- name: Install host packages"], ignored_statuses(workflow))


@unittest.skipUnless(WORKFLOWS.is_dir(), NO_GITHUB)
class WorkflowAptSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflows = {p.name: p.read_text() for p in sorted(WORKFLOWS.glob("*.yml"))}

    def test_every_index_update_first_removes_the_unused_source(self):
        updates = 0
        for name, text in self.workflows.items():
            updates += len(UPDATE.findall(text))
            with self.subTest(workflow=name):
                self.assertEqual([], unguarded_updates(text))
        # host (2), zephyr (1), coverage (2) and psa-crypto (1): a rule that sees none checks nothing.
        self.assertEqual(6, updates)

    def test_no_index_update_ignores_a_failure(self):
        for name, text in self.workflows.items():
            with self.subTest(workflow=name):
                self.assertEqual([], ignored_statuses(text))

    def test_the_removal_names_only_the_microsoft_server(self):
        for name, text in self.workflows.items():
            for line in text.splitlines():
                if "/etc/apt/sources.list.d" in line:
                    with self.subTest(workflow=name, line=line.strip()):
                        self.assertEqual(REMOVE, line.strip())


if __name__ == "__main__":
    unittest.main()
