# SPDX-License-Identifier: Apache-2.0
"""Check the `ci-gate` check, the one check that a merge rule can require (docs/ci.md#merge-gate).

The gate passes only when every CI job of the run concluded `success`. It is safe as the only
required check while these rules hold:

- the decision (scripts/ci/ci_gate.py) fails on a failed, cancelled or skipped job and on a run
  with no job results;
- `.github/workflows/ci.yml` is the only workflow that pull requests start, it calls every
  reusable workflow, and the gate needs every other job of it and runs whatever they concluded;
- the called workflows skip no job by a condition, so a job that a path rule leaves without checks
  still runs and concludes `success`;
- a fast run reports the gate under another name, so a draft's result never stands in for the
  full tier on the same commit.

Only the standard library is used.
"""
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/ci"))
import ci_gate  # noqa: E402
import tiers  # noqa: E402

WORKFLOWS = REPO / ".github/workflows"
CI = WORKFLOWS / "ci.yml"
NO_GITHUB = "this copy has no .github/workflows; see docs/ci.md#copies-without-github"
GATE = "ci-gate"
FAST_GATE = "ci-gate (fast)"


def needs(**results):
    return {job: {"result": result, "outputs": {}} for job, result in results.items()}


def run(env):
    out = io.StringIO()
    return ci_gate.main(env, out), out.getvalue()


class DecisionTest(unittest.TestCase):
    def test_every_job_succeeded_passes(self):
        self.assertEqual([], ci_gate.decide(needs(docs="success", host="success", zephyr="success")))

    def test_a_failed_cancelled_or_skipped_job_fails_and_is_named(self):
        for result in ("failure", "cancelled", "skipped"):
            with self.subTest(result=result):
                problems = ci_gate.decide(needs(docs="success", zephyr=result))
                self.assertEqual(1, len(problems))
                self.assertIn("zephyr", problems[0])
                self.assertIn(result, problems[0])

    def test_an_unknown_or_missing_result_fails(self):
        self.assertTrue(ci_gate.decide(needs(host="neutral")))
        self.assertTrue(ci_gate.decide({"host": {}}))
        self.assertTrue(ci_gate.decide({"host": "success"}))

    def test_no_job_results_fail(self):
        self.assertTrue(ci_gate.decide({}))
        self.assertTrue(ci_gate.decide([]))
        self.assertTrue(ci_gate.decide(None))

    def test_the_exit_status_follows_the_decision(self):
        status, out = run({"CI_GATE_NEEDS": json.dumps(needs(docs="success", web="success"))})
        self.assertEqual(0, status)
        self.assertIn("web: success", out)
        status, out = run({"CI_GATE_NEEDS": json.dumps(needs(docs="success", web="cancelled"))})
        self.assertEqual(1, status)
        self.assertIn("::error", out)
        self.assertIn("web: cancelled", out)

    def test_missing_or_malformed_input_is_a_usage_error(self):
        self.assertEqual(2, run({})[0])
        self.assertEqual(2, run({"CI_GATE_NEEDS": "{not json"})[0])


# --- the workflow text ----------------------------------------------------------------------------

def top_level_block(text, key):
    """Return the lines of a top-level key's block, without the key line."""
    lines = text.splitlines()
    if f"{key}:" not in lines:
        return []
    start = lines.index(f"{key}:")
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"\S", lines[i])), len(lines))
    return lines[start + 1:end]


def triggers(text):
    return {line.strip().rstrip(":") for line in top_level_block(text, "on") if re.match(r"  [a-z_]+:", line)}


def jobs(text):
    """Return {job id: its lines}."""
    block = top_level_block(text, "jobs")
    result, current = {}, None
    for line in block:
        match = re.match(r"  ([A-Za-z0-9_-]+):\s*$", line)
        if match:
            current = match.group(1)
            result[current] = []
        elif current:
            result[current].append(line)
    return result


def job_key(lines, key):
    """Return the value of a job-level key (four spaces in), or None."""
    for line in lines:
        match = re.match(rf"    {key}: (.+)$", line)
        if match:
            return match.group(1).strip()
    return None


def called_workflows():
    return sorted(p for p in WORKFLOWS.glob("*.yml") if "workflow_call" in triggers(p.read_text()))


class _Null:
    """GitHub's null: false, equal only to null, and every property of it is null too."""

    def __getattr__(self, name):
        return self

    def __bool__(self):
        return False

    def __eq__(self, other):
        return other is None or isinstance(other, _Null)

    def __ne__(self, other):
        return not self == other


class _Context:
    """Attribute access for the contexts of a job name expression; a missing property is null."""

    def __init__(self, values=None):
        self._values = values or {}

    def __getattr__(self, name):
        value = self._values.get(name)
        if value is None:
            return _Null()
        return _Context(value) if isinstance(value, dict) else value


def gate_name(expression, github, inputs):
    """Evaluate the gate's name expression: literals, properties, ==, !=, !, && and ||.

    GitHub's && and || return an operand, as Python's `and` and `or` do, and treat null, false,
    0 and '' as false, as Python does.
    """
    match = re.fullmatch(r"\$\{\{(.+)\}\}", expression.strip("\"'"))
    if not match:
        return expression
    code = match.group(1)
    if re.search(r"[^\w\s.'()!=&|-]|\w\(", code.replace("(fast)", "")):
        raise AssertionError(f"the gate name uses more than this evaluator knows: {code}")
    code = code.replace("&&", " and ").replace("||", " or ")
    code = re.sub(r"!(?!=)", " not ", code)
    return eval(code, {"__builtins__": {}}, {"github": _Context(github), "inputs": _Context(inputs)})


def selected_tier(event_name, payload, inputs, ref="refs/heads/feature"):
    """The tier that `scripts/ci/run-tier.sh` runs for this event, as the workflows call it."""
    if inputs.get("tier"):
        return inputs["tier"]
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "event.json"
        path.write_text(json.dumps(payload))
        env = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": event_name,
               "GITHUB_EVENT_PATH": str(path), "GITHUB_REF": ref, "GITHUB_BASE_REF": "main"}
        return tiers.ci_context(env)[0]


@unittest.skipUnless(WORKFLOWS.is_dir(), NO_GITHUB)
class WiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ci = CI.read_text()
        cls.jobs = jobs(cls.ci)

    def test_only_the_ci_workflow_runs_for_pull_requests_and_merges(self):
        # coverage.yml is advisory and never runs for a pull request (test_coverage_workflow.py).
        for workflow in WORKFLOWS.glob("*.yml"):
            names = triggers(workflow.read_text())
            with self.subTest(workflow=workflow.name):
                if workflow == CI:
                    self.assertEqual({"push", "pull_request", "schedule", "workflow_dispatch"}, names)
                elif workflow.name != "coverage.yml":
                    self.assertEqual({"workflow_call", "workflow_dispatch"}, names)
                self.assertNotIn("pull_request_target", names)

    def test_pull_requests_run_again_when_marked_ready_for_review(self):
        self.assertIn("    types: [opened, synchronize, reopened, ready_for_review]\n", self.ci)

    def test_only_merges_to_main_start_a_push_run(self):
        # A push to another branch runs the fast tier, which the gate name below does not cover.
        block = top_level_block(self.ci, "on")
        start = block.index("  push:")
        self.assertEqual("    branches: [main]", block[start + 1])
        self.assertFalse(block[start + 2].startswith("    "))

    def test_no_path_filter_can_leave_the_gate_unreported(self):
        # A workflow that a path filter skips leaves its checks pending; the map file's scopes
        # select the checks of a change instead (test_zephyr_ci_shards.py).
        for line in top_level_block(self.ci, "on"):
            self.assertNotRegex(line, r"^\s+(paths|paths-ignore|branches-ignore):")

    def test_the_ci_workflow_calls_every_reusable_workflow(self):
        called = {job_key(lines, "uses") for lines in self.jobs.values()} - {None}
        expected = {f"./.github/workflows/{p.name}" for p in called_workflows()}
        self.assertEqual(expected, called)
        self.assertGreaterEqual(len(expected), 5)

    def test_the_gate_needs_every_other_job_and_runs_whatever_they_concluded(self):
        gate = self.jobs["ci-gate"]
        listed = set(re.findall(r"[a-z][a-z0-9-]*", job_key(gate, "needs") or ""))
        self.assertEqual(set(self.jobs) - {"ci-gate"}, listed)
        # `!cancelled()` would skip the gate in a cancelled run, and a skipped job counts as success.
        self.assertEqual("always()", job_key(gate, "if"))
        text = "\n".join(gate)
        self.assertIn("CI_GATE_NEEDS: ${{ toJSON(needs) }}", text)
        self.assertIn("python3 scripts/ci/ci_gate.py", text)
        self.assertIsNotNone(job_key(gate, "timeout-minutes"))

    def test_the_called_workflows_skip_no_job_by_a_condition(self):
        # A job skipped by a condition concludes `skipped`, and a calling job whose jobs were all
        # skipped could look like a pass. Only the Zephyr summary job has a condition, `always()`.
        for workflow in called_workflows():
            for job, lines in jobs(workflow.read_text()).items():
                with self.subTest(workflow=workflow.name, job=job):
                    condition = job_key(lines, "if")
                    if (workflow.name, job) == ("zephyr.yml", "zephyr"):
                        self.assertEqual("always()", condition)
                    else:
                        self.assertIsNone(condition)

    def test_a_web_job_without_checks_skips_its_steps_after_the_plan(self):
        # The web jobs now run for every change; without checks they must not set up Node.js or
        # require the SBOM that only a check writes.
        for job, lines in jobs((WORKFLOWS / "web.yml").read_text()).items():
            steps = re.split(r"\n(?=      - )", "\n".join(lines))
            titles = [s.strip().splitlines()[0] for s in steps if s.startswith("      - ")]
            plan = next(i for i, t in enumerate(titles) if t == "- name: Plan the checks of this tier")
            with self.subTest(job=job):
                self.assertEqual(1, plan, "the plan follows the checkout")
                for step in [s for s in steps if s.startswith("      - ")][plan + 1:]:
                    self.assertIn("steps.plan.outputs.checks != '0'", step)

    def test_only_the_caller_cancels_superseded_runs(self):
        # A called workflow sees the caller's `github.workflow`: its own concurrency group would
        # collide with the caller's and the other called workflows'.
        for workflow in called_workflows():
            with self.subTest(workflow=workflow.name):
                self.assertEqual([], top_level_block(workflow.read_text(), "concurrency"))
        concurrency = "\n".join(top_level_block(self.ci, "concurrency"))
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}", concurrency)

    def test_every_call_passes_the_manual_tier_and_base(self):
        for job, lines in self.jobs.items():
            if job_key(lines, "uses"):
                with self.subTest(job=job):
                    text = "\n".join(lines)
                    self.assertIn("tier: ${{ inputs.tier }}", text)
                    self.assertIn("base: ${{ inputs.base }}", text)

    def test_the_workflow_names_no_repository(self):
        # Local references keep working when the repository is renamed or copied.
        self.assertNotRegex(self.ci, r"uses: (?!\./)[\w.-]+/[\w.-]+/\.github/workflows/")
        self.assertNotIn("github.com/", self.ci)

    def test_only_a_run_of_the_full_or_nightly_tier_reports_the_gate_name(self):
        expression = job_key(self.jobs["ci-gate"], "name")
        main = "refs/heads/main"
        cases = [
            ("pull_request", {"pull_request": {"draft": True}}, {}, "refs/pull/1/merge"),
            ("pull_request", {"pull_request": {"draft": False}}, {}, "refs/pull/1/merge"),
            ("push", {"before": "a" * 40, "repository": {"default_branch": "main"}}, {}, main),
            ("schedule", {}, {}, main),
            ("workflow_dispatch", {}, {"tier": "fast"}, "refs/heads/feature"),
            ("workflow_dispatch", {}, {"tier": "full"}, "refs/heads/feature"),
            ("workflow_dispatch", {}, {"tier": "nightly"}, main),
        ]
        names = set()
        for event, payload, inputs, ref in cases:
            with self.subTest(event=event, payload=payload, inputs=inputs):
                github = {"event_name": event, "event": payload, "ref": ref}
                name = gate_name(expression, github, inputs)
                names.add(name)
                tier = selected_tier(event, payload, inputs, ref)
                self.assertEqual(FAST_GATE if tier == "fast" else GATE, name)
        self.assertEqual({GATE, FAST_GATE}, names)


if __name__ == "__main__":
    unittest.main()
