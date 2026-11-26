"""Check that the CI workflows cannot silently drop a check.

Each Zephyr shard runs the checks of its job `zephyr-<shard>` in scripts/ci/checks.toml through
scripts/ci/run-tier.sh. A shard that names no job, a job that no shard runs, or a check step
outside the entry point would leave a check out or run it twice while the run stays green, so
these rules read the workflow text and the map file. tests/build/test_ci_tiers.py holds the
checks of each job. Only the standard library is used.
"""
from fnmatch import fnmatchcase
from pathlib import Path
import re
import tomllib
import unittest

REPO = Path(__file__).resolve().parents[2]
ZEPHYR = REPO / ".github/workflows/zephyr.yml"
PSA_CRYPTO = REPO / ".github/workflows/psa-crypto.yml"
HOST = REPO / ".github/workflows/host.yml"
WEB = REPO / ".github/workflows/web.yml"
DOCS = REPO / ".github/workflows/docs.yml"
MANIFEST = REPO / "scripts/ci/checks.toml"
TIER_WORKFLOWS = [HOST, ZEPHYR, PSA_CRYPTO, WEB, DOCS]
DOCS_ONLY = ["docs/**", "**.md"]
PSA_SCRIPT = REPO / "scripts" / "test-psa-crypto.sh"
# Later patterns win: everything but documentation, plus the records that the pin check reads.
PSA_PATHS = ["**", "!docs/**", "!**.md", "docs/dependency-review-*.md"]
# Steps that run in every shard: they prepare the runner or collect what the shard produced.
SET_UP_STEPS = {
    "name: List host packages from the signed index",
    "name: Install Zephyr host packages",
    "name: Install pinned Python tools",
    "name: Fetch pinned Zephyr workspace and install SDK",
    "name: Collect Twister evidence",
}
SET_UP_SCRIPTS = re.compile(r"scripts/(bootstrap-zephyr\.sh|verify-apt-cache\.py)")
# The steps that plan and run the shard's checks: they may run nothing but the tier entry point.
TIER_STEPS = {"name: Plan the checks of this tier", "name: Run the checks of this tier"}
TIER_COMMAND = re.compile(r'scripts/ci/run-tier\.sh "\$TIER" --job "zephyr-\$\{\{ matrix\.shard \}\}"')
PLANNED = "steps.plan.outputs.checks != '0'"


def job_text(workflow, job):
    """Return the lines of one job, from its key to the next job or end of file."""
    lines = workflow.splitlines()
    start = lines.index(f"  {job}:")
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"  \S", lines[i])), len(lines))
    return lines[start:end]


def steps(job_lines):
    """Split a job into steps: {'title', 'condition', 'text'}, in workflow order."""
    result = []
    for line in job_lines:
        if line.startswith("      - "):
            result.append({"title": line[8:].strip(), "condition": None, "text": line + "\n"})
        elif result and line.startswith("      "):
            result[-1]["text"] += line + "\n"
            match = re.match(r"\s+if: (.+)$", line)
            if match and line.startswith("        if:"):
                result[-1]["condition"] = match.group(1).strip()
    return result


def paths_ignore(workflow, event, key="paths-ignore"):
    """Return the patterns of a trigger event's path filter, or None without that filter."""
    lines = workflow.splitlines()
    start = lines.index(f"  {event}:")
    patterns = None
    for line in lines[start + 1:]:
        if not line.startswith("    "):
            break
        if line.strip() == f"{key}:":
            patterns = []
        elif patterns is not None and line.strip().startswith("- "):
            patterns.append(line.strip()[2:].strip("\"'"))
    return patterns


def runs_a_command(step):
    """True for a step with a `run:` key, whether it comes first or after `name:`."""
    return re.search(r"^ {6}- run:|^ {8}run:", step["text"], re.MULTILINE) is not None


def mentions_repository_code(step):
    return "scripts/" in step["text"] or "python3 " in step["text"] or "west " in step["text"]


def misplaced_steps(job_steps):
    """Return the steps that run a check outside the tier entry point.

    A check is any step with a `run:` and any step that mentions repository code, whatever
    command it runs. A named set-up step is exempt while it mentions no repository code, and one
    that runs a set-up script is exempt whatever else it runs. The plan and run steps are exempt
    while the tier entry point for the shard's job is the only repository code they mention.
    """
    result = []
    for step in job_steps:
        if not (runs_a_command(step) or mentions_repository_code(step)):
            continue
        if step["title"] in SET_UP_STEPS and (SET_UP_SCRIPTS.search(step["text"])
                                              or not mentions_repository_code(step)):
            continue
        if step["title"] in TIER_STEPS and TIER_COMMAND.search(step["text"]):
            if not mentions_repository_code({"text": TIER_COMMAND.sub("", step["text"])}):
                continue
        result.append(step)
    return result


def load_manifest():
    return tomllib.loads(MANIFEST.read_text())


class ZephyrShardsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = ZEPHYR.read_text()
        cls.job = job_text(cls.workflow, "shard")
        cls.steps = steps(cls.job)
        matrix = next(line for line in cls.job if line.strip().startswith("shard: ["))
        cls.shards = re.findall(r"[a-z-]+", matrix.split("[", 1)[1])
        cls.manifest = load_manifest()

    def test_no_step_runs_a_check_outside_the_tier_entry_point(self):
        for step in misplaced_steps(self.steps):
            with self.subTest(step=step["title"]):
                self.fail("step runs a command that is neither set-up nor scripts/ci/run-tier.sh")

    def test_the_shards_are_exactly_the_zephyr_jobs_of_the_map_file(self):
        jobs = {name[len("zephyr-"):] for name in self.manifest["jobs"] if name.startswith("zephyr-")}
        self.assertEqual(jobs, set(self.shards))
        used = {check["job"] for check in self.manifest["check"]}
        self.assertLessEqual({f"zephyr-{shard}" for shard in self.shards}, used)

    def test_the_shard_runs_its_job_once_after_the_set_up(self):
        titles = [s["title"] for s in self.steps]
        run = [s for s in self.steps if s["title"] == "name: Run the checks of this tier"]
        self.assertEqual(1, len(run))
        self.assertRegex(run[0]["text"], r'run: scripts/ci/run-tier\.sh "\$TIER" --job "zephyr-\$\{\{ matrix\.shard \}\}"\n')
        self.assertEqual(PLANNED, run[0]["condition"])
        self.assertLess(titles.index("name: Fetch pinned Zephyr workspace and install SDK"),
                        titles.index("name: Run the checks of this tier"))

    def test_set_up_is_skipped_only_when_the_plan_is_empty(self):
        for step in self.steps:
            if step["title"] in SET_UP_STEPS - {"name: Collect Twister evidence"}:
                with self.subTest(step=step["title"]):
                    self.assertEqual(PLANNED, step["condition"])

    def test_networking_checks_share_their_test_library(self):
        # The fixture check reads the Picolibc checkout that the networking check fetches.
        jobs = {c["id"]: c["job"] for c in self.manifest["check"]}
        fetch = next(c["id"] for c in self.manifest["check"]
                     if "scripts/bootstrap-networking-tests.sh" in c["run"])
        fixture = next(c["id"] for c in self.manifest["check"]
                       if "scripts/test-networking-physical.sh" in c["run"])
        self.assertEqual(jobs[fetch], jobs[fixture])

    def test_one_shard_failing_does_not_cancel_the_others(self):
        self.assertIn("      fail-fast: false", self.job)

    def test_each_shard_uploads_under_its_own_name(self):
        # upload-artifact@v4 refuses a name that another job in the run already used.
        self.assertIn("name: zephyr-${{ matrix.shard }}-${{ github.run_id }}", self.workflow)

    def test_summary_job_keeps_the_zephyr_check_and_needs_every_shard(self):
        summary = "\n".join(job_text(self.workflow, "zephyr"))
        self.assertIn("needs: shard", summary)
        self.assertIn("if: always()", summary)
        self.assertIn("needs.shard.result", summary)
        # Only "success" may pass: failed, cancelled and skipped shards must all fail it.
        self.assertIn('test "$SHARD_RESULT" = success', summary)

    def test_only_documentation_skips_the_workflow(self):
        self.assertEqual(DOCS_ONLY, paths_ignore(self.workflow, "push"))
        self.assertEqual(DOCS_ONLY, paths_ignore(self.workflow, "pull_request"))
        # The map file applies the same rule to the Zephyr checks on every CI system.
        self.assertEqual(DOCS_ONLY, self.manifest["selection"]["docs"])
        for check in self.manifest["check"]:
            if check["job"].startswith("zephyr-"):
                with self.subTest(check=check["id"]):
                    self.assertEqual("code", check.get("scope", "code"))

    def step_using(self, action):
        matches = [s for s in self.steps if f"uses: {action}" in s["text"]]
        self.assertEqual(1, len(matches), f"{action} must be used by exactly one step")
        return matches[0]

    def test_host_packages_are_restored_before_they_are_installed(self):
        # Slow mirrors cost one job in six up to ten minutes, which sets a run's length.
        titles = [s["title"] for s in self.steps]
        install = self.install_step()
        self.assertIn("Dir::Cache::archives=", install["text"])
        restore = self.step_using("actions/cache/restore@")
        save = self.step_using("actions/cache/save@")
        self.assertLess(titles.index(restore["title"]), titles.index(install["title"]))
        self.assertLess(titles.index(install["title"]), titles.index(save["title"]))

    def install_step(self):
        matches = [s for s in self.steps if re.search(r"apt-get install -y -o", s["text"])]
        self.assertEqual(1, len(matches), "one step must install from the package cache")
        return matches[0]

    def test_restored_packages_are_verified_before_apt_reads_them(self):
        # apt accepts a cached file by name and size alone, so a poisoned cache would install.
        text = self.install_step()["text"]
        self.assertIn("scripts/verify-apt-cache.py", text)
        self.assertLess(text.index("scripts/verify-apt-cache.py"), text.index("apt-get install"))

    def test_package_list_comes_from_the_index_with_a_strong_hash(self):
        # --print-uris reports MD5 unless a hash is forced.
        listing = next(s for s in self.steps if "--print-uris" in s["text"])
        self.assertIn("Acquire::ForceHash=SHA256", listing["text"])
        self.assertIn("apt-get update", listing["text"])
        self.assertIn("$CI_HOST_PACKAGES", listing["text"])
        self.assertIn("$CI_HOST_PACKAGES", self.install_step()["text"])

    def test_restored_and_saved_packages_use_one_path_and_key(self):
        field = re.compile(r"^\s+(path|key): (.+)$", re.MULTILINE)
        self.assertEqual(field.findall(self.step_using("actions/cache/restore@")["text"]),
                         field.findall(self.step_using("actions/cache/save@")["text"]))

    def test_cache_paths_are_accepted_by_the_cache_action(self):
        # actions/cache only warns about a path with "..", then stores nothing: every run
        # stays cold while the workflow stays green.
        for step in (s for s in self.steps if "actions/cache" in s["text"]):
            with self.subTest(step=step["title"]):
                path = re.search(r"^\s+path: (.+)$", step["text"], re.MULTILINE).group(1)
                self.assertNotIn("..", path)

    def test_psa_crypto_workflow_skips_documentation_but_not_its_review_records(self):
        psa = PSA_CRYPTO.read_text()
        for event in ("push", "pull_request"):
            with self.subTest(event=event):
                self.assertIsNone(paths_ignore(psa, event))
                self.assertEqual(PSA_PATHS, paths_ignore(psa, event, "paths"))
        self.assertEqual(PSA_PATHS, self.manifest["scopes"]["psa-crypto"])
        for check in self.manifest["check"]:
            if check["job"] == "psa-crypto":
                with self.subTest(check=check["id"]):
                    self.assertEqual("psa-crypto", check.get("scope"))

    def test_the_review_records_that_the_pin_check_reads_start_the_psa_crypto_workflow(self):
        records = re.findall(r"'(docs/[^']+)'", PSA_SCRIPT.read_text())
        self.assertTrue(records)
        for record in records:
            with self.subTest(record=record):
                self.assertTrue(fnmatchcase(record, PSA_PATHS[-1]))
                self.assertTrue((REPO / record).is_file())

    def test_the_web_workflow_starts_for_the_paths_its_checks_need(self):
        web = WEB.read_text()
        for event in ("push", "pull_request"):
            with self.subTest(event=event):
                self.assertEqual(self.manifest["scopes"]["web-ui"], paths_ignore(web, event, "paths"))
        for check in self.manifest["check"]:
            if check["job"].startswith("web-"):
                with self.subTest(check=check["id"]):
                    self.assertEqual("web-ui", check.get("scope"))

    def test_host_workflow_still_runs_for_documentation(self):
        # tests/build reads documentation, so one workflow must keep running on such changes.
        host = HOST.read_text()
        self.assertNotIn("paths-ignore", host)
        self.assertIn('scripts/ci/run-tier.sh "$TIER" --job host-build-tests', host)
        build_tests = next(c for c in self.manifest["check"] if c["id"] == "build-tests")
        self.assertEqual("always", build_tests.get("scope"))
        self.assertIn("-s tests/build", build_tests["run"])


class TierTriggersTest(unittest.TestCase):
    """Every tier workflow starts on the events of the tier model, the same way."""

    def test_pull_requests_run_again_when_marked_ready_for_review(self):
        for workflow in TIER_WORKFLOWS:
            with self.subTest(workflow=workflow.name):
                self.assertIn("    types: [opened, synchronize, reopened, ready_for_review]\n",
                              workflow.read_text())

    def test_every_tier_workflow_runs_nightly_at_one_time(self):
        crons = {w.name: re.findall(r'- cron: "([^"]+)"', w.read_text()) for w in TIER_WORKFLOWS}
        self.assertEqual({name: ["17 2 * * *"] for name in crons}, crons)

    def test_every_job_passes_the_manual_tier_or_auto(self):
        for workflow in TIER_WORKFLOWS:
            text = workflow.read_text()
            with self.subTest(workflow=workflow.name):
                self.assertIn("TIER: ${{ inputs.tier || 'auto' }}", text)
                self.assertIn("options: [full, fast, nightly]", text)
                commands = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
                self.assertNotRegex(commands, r"run-tier\.sh (?!\"\$TIER\")")

    def test_every_job_of_the_map_file_has_a_runner(self):
        texts = "\n".join(w.read_text() for w in [*TIER_WORKFLOWS, REPO / ".github/workflows/coverage.yml"])
        jenkins = (REPO / "Jenkinsfile").read_text()
        for job in load_manifest()["jobs"]:
            with self.subTest(job=job):
                if job.startswith("zephyr-"):
                    self.assertIn(job[len("zephyr-"):], re.search(r"shard: \[(.+)\]", texts).group(1))
                elif not job.startswith("coverage-"):
                    self.assertIn(f"--job {job}", texts)
                self.assertIn(job, jenkins)


SYNTHETIC_JOB = """  shard:
    steps:
      - name: Install pinned Python tools
        run: pip install west
{steps}
"""


def synthetic_steps(*blocks):
    """Build the steps of a small job: the named set-up step plus the given step blocks."""
    return steps(SYNTHETIC_JOB.format(steps="\n".join(blocks)).splitlines())


def step_block(run, title="A check"):
    return "\n".join([f"      - name: {title}", f"        run: {run}"])


TIER_RUN = 'scripts/ci/run-tier.sh "$TIER" --job "zephyr-${{ matrix.shard }}"'


class MisplacedStepsTest(unittest.TestCase):
    """The rule must see every step that runs a command, whatever command it runs."""

    def titles(self, *blocks):
        return [s["title"] for s in misplaced_steps(synthetic_steps(*blocks))]

    def test_the_tier_steps_are_accepted(self):
        self.assertEqual([], self.titles(step_block(TIER_RUN, "Run the checks of this tier"),
                                         step_block(TIER_RUN + " --plan", "Plan the checks of this tier")))

    def test_any_other_command_is_reported(self):
        for run in ("tests/ssh/cli/test-compile.sh", "make check", "./run.sh", "cmake --build build"):
            with self.subTest(run=run):
                self.assertEqual(["name: A check"], self.titles(step_block(run)))

    def test_a_check_cannot_hide_in_a_tier_step(self):
        for run in (TIER_RUN + " && scripts/test-extra.sh", "scripts/test-extra.sh",
                    'scripts/ci/run-tier.sh "$TIER" --job zephyr-io'):
            with self.subTest(run=run):
                self.assertEqual(["name: Run the checks of this tier"],
                                 self.titles(step_block(run, "Run the checks of this tier")))

    def test_the_named_set_up_steps_need_no_condition(self):
        self.assertEqual([], misplaced_steps(synthetic_steps()))

    def test_a_step_that_starts_with_run_is_checked(self):
        block = "      - run: tests/ssh/cli/test-compile.sh"
        self.assertEqual(["run: tests/ssh/cli/test-compile.sh"], self.titles(block))

    def test_a_set_up_step_must_not_gain_a_check_command(self):
        for command in ("scripts/test-extra.sh", "python3 scripts/check-extra.py", "west build -b native_sim app"):
            with self.subTest(command=command):
                block = f"      - name: Collect Twister evidence\n        run: {command}"
                self.assertEqual(["name: Collect Twister evidence"], self.titles(block))

    def test_a_check_cannot_hide_under_a_set_up_title(self):
        block = "      - name: Install pinned Python tools\n        run: scripts/test-extra.sh"
        self.assertEqual(["name: Install pinned Python tools"], self.titles(block))

    def test_a_step_that_only_uses_an_action_is_checked_for_check_commands(self):
        block = "      - uses: some/action@v1\n        with:\n          command: scripts/test-extra.sh"
        self.assertEqual(["uses: some/action@v1"], self.titles(block))

    def test_the_set_up_scripts_stay_exempt_in_a_set_up_step(self):
        block = "      - name: Fetch pinned Zephyr workspace and install SDK\n        run: scripts/bootstrap-zephyr.sh"
        self.assertEqual([], self.titles(block))


if __name__ == "__main__":
    unittest.main()
