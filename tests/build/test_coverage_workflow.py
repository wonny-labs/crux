"""Check that the advisory coverage workflow stays advisory.

The workflow measures how much of the component sources the Host and `native_sim` tests
execute. It must never gate a change, send data out of the repository, or change the CI time
of a pull request. These rules read the workflow text and the scripts it runs. Only the
standard library is used because `host.yml` runs this directory without PyYAML.
"""
from pathlib import Path
import re
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github/workflows/coverage.yml"
HOST = REPO / ".github/workflows/host.yml"
SCRIPTS = [REPO / "scripts/coverage-host.sh", REPO / "scripts/coverage-native-sim.sh"]
JOBS = ("host", "native-sim")
# Only GitHub's own actions may run; nothing here can upload to another service.
ALLOWED_ACTION_OWNERS = {"actions"}
FORBIDDEN_WORDS = re.compile(
    r"fail[-_]under|fail[-_]below|--fail|codecov|coveralls|sonar|curl |wget |secrets\.",
    re.IGNORECASE,
)


def job_text(workflow, job):
    """Return the lines of one job, from its key to the next job or end of file."""
    lines = workflow.splitlines()
    start = lines.index(f"  {job}:")
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"  \S", lines[i])), len(lines))
    return lines[start:end]


def steps(job_lines):
    """Split a job into steps: {'title', 'text'}, in workflow order."""
    result = []
    for line in job_lines:
        if line.startswith("      - "):
            result.append({"title": line[8:].strip(), "text": line + "\n"})
        elif result and line.startswith("      "):
            result[-1]["text"] += line + "\n"
    return result


def pinned_use(workflow, action):
    match = re.search(rf"uses: ({re.escape(action)}@\S+)", workflow)
    return match.group(1) if match else None


def trigger_block(workflow):
    """Return the lines of the top-level `on:` block."""
    lines = workflow.splitlines()
    start = lines.index("on:")
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"\S", lines[i])), len(lines))
    return lines[start + 1:end]


class CoverageWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text()
        cls.triggers = trigger_block(cls.workflow)

    def test_triggers_are_manual_weekly_and_main_push(self):
        events = [line.strip().rstrip(":") for line in self.triggers if re.match(r"  \S", line)]
        self.assertEqual({"workflow_dispatch", "schedule", "push"}, set(events))
        cron = re.findall(r"- cron: \"([^\"]+)\"", "\n".join(self.triggers))
        self.assertEqual(1, len(cron), "one weekly schedule")
        fields = cron[0].split()
        self.assertEqual(5, len(fields))
        self.assertNotEqual("*", fields[4], "the schedule names a weekday, so it runs weekly")
        self.assertEqual(["*", "*"], fields[2:4], "day of month and month stay open: weekly, not monthly")
        self.assertIn("    branches: [main]", self.triggers)

    def test_pull_requests_do_not_start_it(self):
        self.assertNotIn("pull_request", "\n".join(self.triggers))
        self.assertNotRegex(self.workflow, r"github\.event_name == 'pull_request'")

    def test_token_is_read_only(self):
        self.assertIn("\npermissions:\n  contents: read\n", self.workflow)
        self.assertNotRegex(self.workflow, r"(?m)^\s*[a-z-]+:\s*write\b")
        self.assertNotIn("persist-credentials: true", self.workflow)

    def test_nothing_gates_or_leaves_the_repository(self):
        self.assertIsNone(FORBIDDEN_WORDS.search(self.workflow))
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                self.assertIsNone(FORBIDDEN_WORDS.search(script.read_text()))

    def test_only_github_actions_run_and_pins_match_the_other_workflows(self):
        uses = re.findall(r"uses: ([^@\s]+)@(\S+)", self.workflow)
        self.assertTrue(uses)
        for action, ref in uses:
            with self.subTest(action=action):
                self.assertIn(action.split("/")[0], ALLOWED_ACTION_OWNERS)
                self.assertRegex(ref, r"^v\d+$", "pinned by major tag like the other workflows")
        zephyr = (REPO / ".github/workflows/zephyr.yml").read_text()
        for action in ("actions/checkout", "actions/upload-artifact"):
            with self.subTest(pin=action):
                self.assertEqual(pinned_use(HOST.read_text(), action), pinned_use(self.workflow, action))
        for action in ("actions/setup-python", "actions/cache/restore", "actions/cache/save"):
            with self.subTest(pin=action):
                self.assertEqual(pinned_use(zephyr, action), pinned_use(self.workflow, action))

    def test_both_jobs_exist_and_upload_their_report(self):
        for job in JOBS:
            with self.subTest(job=job):
                text = "\n".join(job_text(self.workflow, job))
                self.assertIn("uses: actions/upload-artifact@", text)
                self.assertIn("if: always()", text)
                self.assertIn("retention-days:", text)
                self.assertIn('>> "$GITHUB_STEP_SUMMARY"', text)

    def test_the_two_artifacts_have_distinct_names(self):
        names = re.findall(r"name: (coverage-[a-z-]+)-\$\{\{ github\.run_id \}\}", self.workflow)
        self.assertEqual(sorted(JOBS), sorted(n.removeprefix("coverage-") for n in names))

    def test_build_and_test_failures_stay_visible(self):
        # Only the report steps may continue on error: a failed build or test must show as
        # failed, or the report would be empty without anyone noticing.
        for job in JOBS:
            for step in steps(job_text(self.workflow, job)):
                with self.subTest(job=job, step=step["title"]):
                    continues = "continue-on-error: true" in step["text"]
                    self.assertEqual("id: report" in step["text"], continues)

    def test_a_failed_report_leaves_a_visible_warning(self):
        for job in JOBS:
            with self.subTest(job=job):
                text = "\n".join(job_text(self.workflow, job))
                self.assertIn("steps.report.outcome == 'failure'", text)
                self.assertIn("::warning::", text)

    def test_report_steps_run_after_a_failed_test_step(self):
        for job in JOBS:
            with self.subTest(job=job):
                report = [s for s in steps(job_text(self.workflow, job)) if "id: report" in s["text"]]
                self.assertEqual(1, len(report))
                self.assertIn("if: ${{ !cancelled() }}", report[0]["text"])

    def test_jobs_have_a_time_limit(self):
        for job in JOBS:
            with self.subTest(job=job):
                self.assertIn("timeout-minutes:", "\n".join(job_text(self.workflow, job)))

    def test_scripts_the_workflow_runs_exist_and_parse(self):
        named = set(re.findall(r"scripts/(coverage-[a-z-]+\.(?:sh|py))", self.workflow))
        self.assertTrue({"coverage-host.sh", "coverage-native-sim.sh", "coverage-summary.py"} <= named)
        for name in named:
            with self.subTest(script=name):
                self.assertTrue((REPO / "scripts" / name).is_file())
        for script in SCRIPTS:
            with self.subTest(syntax=script.name):
                subprocess.run(["bash", "-n", str(script)], check=True)

    def test_the_host_build_does_not_edit_the_presets(self):
        script = (REPO / "scripts/coverage-host.sh").read_text()
        for flag in ("-DCMAKE_C_FLAGS=--coverage", "-DCMAKE_CXX_FLAGS=--coverage",
                     "-DCMAKE_EXE_LINKER_FLAGS=--coverage"):
            with self.subTest(flag=flag):
                self.assertIn(flag, script)
        self.assertNotIn("--coverage", (REPO / "CMakePresets.json").read_text())

    def test_native_sim_measures_a_named_set_and_keeps_repository_sources_only(self):
        script = (REPO / "scripts/coverage-native-sim.sh").read_text()
        for suite in ("tests/time/zephyr", "tests/logging/zephyr", "tests/system/zephyr",
                      "tests/native/file_fatfs"):
            with self.subTest(suite=suite):
                self.assertIn(suite, script)
        self.assertIn("--enable-coverage", script)
        self.assertIn('-r "$repo"', script, "report paths are relative to this repository")


if __name__ == "__main__":
    unittest.main()
