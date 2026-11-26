# SPDX-License-Identifier: Apache-2.0
"""Check the CI tier selector and runner in scripts/ci (docs/ci.md).

The rules held here:

- the full tier runs exactly the recorded checks, and removing one fails this test,
- a fast run falls back to the full tier whenever the selector is unsure,
- a fast run is never larger than the full run of the same change,
- documentation-only changes skip the checks that read no documentation, as before tiers,
- the tier and the comparison base come from plain environment values of either CI system,
- the runner stops at the first failing check, keeps advisory failures advisory, and writes JUnit.

Only the standard library and git are used.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
TIERS_PATH = REPO / "scripts/ci/tiers.py"
MANIFEST = REPO / "scripts/ci/checks.toml"


def load_tiers():
    spec = importlib.util.spec_from_file_location("crux_ci_tiers", TIERS_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["crux_ci_tiers"] = module
    spec.loader.exec_module(module)
    return module


tiers = load_tiers()

# The checks of the full tier, by job, in run order. Every CI step that ran a check before the
# tiers existed is here; tests/build was split into its large cases and the rest. Remove an id only
# with an approved change that removes the check, and say so in the pull request.
EXPECTED_FULL = {
    "host": [
        "host-build-and-test", "host-offline", "host-sanitizers", "access-host", "cli-host",
        "cli-ssh-thread-sanitizer", "credential-host", "security-event-host", "mgmt-services-host",
        "web-host", "portable-execution-host", "file-consumers", "file-service-host", "messaging-host",
        "format", "serial-host", "logging-host", "system-host", "static-analysis", "build-boundaries",
    ],
    "host-build-tests": ["build-tests", "build-tests-large", "power-cut-wrapper"],
    "zephyr-storage": [
        "patch-style", "storage-simulators", "file-rt1060-compile", "flash-poc-fault-paths",
        "zephyr-time-evkb", "product-template", "emmc-reliance-edge",
    ],
    "zephyr-controller": [
        "zephyr-smoke", "execution-candidates", "early-controller", "controller-integration",
        "rt1170-cross-build", "m5-integrated-smoke",
    ],
    "zephyr-runtime": [
        "portable-execution", "reboot-native-sanitizers", "time-busy-wait", "messaging",
        "consumer-poc-zephyr", "logging-evkb", "system-evkb", "boot-composition",
    ],
    "zephyr-io": [
        "serial-zephyr", "cli-zephyr", "cli-ssh-compile", "gpio-zephyr", "i2c-zephyr", "spi-zephyr",
        "web-native", "web-assets-native", "networking", "networking-physical-fixture",
    ],
    "psa-crypto": [
        "tf-psa-crypto-host", "tf-psa-crypto-native-sim", "tf-psa-crypto-evkb", "web-evkb-mbedtls",
        "psa-ports-host", "tls-offload-mbed", "management-composition-mbed", "management-module-mbed",
        "web-https-mbedtls", "web-session-native", "psa-ports-evkb", "management-image-rt1060-mbed",
    ],
    "web-specification": ["management-api-lint", "management-api-lint-controls"],
    "web-client": ["web-client-install", "web-client-checks", "web-client-audit", "web-client-sbom"],
    "web-browser": ["web-browser-install", "web-browser-version", "web-browser-tests"],
    "web-angular": [
        "angular-sample-build", "angular-web-tools-install", "angular-sample-sources",
        "angular-shared-browser-cases", "angular-preact-comparison",
    ],
    "docs": ["lychee-install", "docs-selection-rules", "docs-links"],
}
EXPECTED_NIGHTLY_ONLY = {
    "coverage-host": ["coverage-host-run", "coverage-host-report"],
    "coverage-native-sim": ["coverage-native-sim-run", "coverage-native-sim-report"],
}
DOCS_READERS = {"build-tests", "build-tests-large", "lychee-install", "docs-selection-rules", "docs-links"}


def by_job(checks):
    result = {}
    for check in checks:
        result.setdefault(check.job, []).append(check.id)
    return result


class ManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = tiers.load_manifest(MANIFEST)

    def plan(self, tier, changed):
        return tiers.plan(self.manifest, tier, changed).checks

    def test_the_full_tier_runs_every_recorded_check_in_order(self):
        self.assertEqual(EXPECTED_FULL, by_job(self.plan("full", None)))

    def test_the_nightly_tier_adds_only_coverage_to_the_full_tier(self):
        expected = {**EXPECTED_FULL, **EXPECTED_NIGHTLY_ONLY}
        self.assertEqual(expected, by_job(self.plan("nightly", None)))

    def test_the_nightly_tier_ignores_the_change(self):
        self.assertEqual(self.plan("nightly", None), self.plan("nightly", ["docs/a.md"]))

    def test_every_fast_component_exists(self):
        for check in self.manifest.checks:
            if isinstance(check.fast, list):
                with self.subTest(check=check.id):
                    self.assertLessEqual(set(check.fast), set(self.manifest.components))

    def test_the_networking_checks_share_one_job_in_order(self):
        # The fixture check reads the Picolibc checkout that the networking check fetches.
        ids = by_job(self.plan("full", None))["zephyr-io"]
        self.assertLess(ids.index("networking"), ids.index("networking-physical-fixture"))
        networking = next(c for c in self.manifest.checks if c.id == "networking")
        self.assertIn("scripts/bootstrap-networking-tests.sh", networking.run)

    def test_the_optional_west_groups_are_enabled_by_the_last_check_of_their_job(self):
        jobs = by_job(self.plan("full", None))
        self.assertEqual("emmc-reliance-edge", jobs["zephyr-storage"][-1])
        self.assertEqual("boot-composition", jobs["zephyr-runtime"][-1])


class FullTierScopeTest(unittest.TestCase):
    """The full tier keeps the path rules that the workflows applied before tiers."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = tiers.load_manifest(MANIFEST)

    def ids(self, changed):
        return {c.id for c in tiers.plan(self.manifest, "full", changed).checks}

    def test_a_documentation_change_runs_only_the_checks_that_read_documentation(self):
        self.assertEqual(DOCS_READERS, self.ids(["docs/build.md", "tests/README.md"]))

    def test_a_dependency_review_record_also_runs_the_psa_crypto_job(self):
        ids = self.ids(["docs/dependency-review-mbed-tls-4.1.1.md"])
        self.assertEqual(DOCS_READERS | set(EXPECTED_FULL["psa-crypto"]), ids)

    def test_a_source_change_runs_everything_but_the_web_jobs(self):
        web = {i for job, ids in EXPECTED_FULL.items() if job.startswith("web-") for i in ids}
        everything = {i for ids in EXPECTED_FULL.values() for i in ids}
        self.assertEqual(everything - web, self.ids(["components/gpio/src/gpio.c"]))

    def test_a_web_change_runs_the_web_jobs(self):
        self.assertLessEqual(set(EXPECTED_FULL["web-client"]), self.ids(["web/client/app.tsx"]))

    def test_an_unknown_change_runs_every_full_check(self):
        everything = {i for ids in EXPECTED_FULL.values() for i in ids}
        self.assertEqual(everything, self.ids(None))

    def test_an_empty_change_runs_every_code_check(self):
        self.assertIn("host-build-and-test", self.ids([]))


class FastTierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = tiers.load_manifest(MANIFEST)

    def fast(self, changed):
        return tiers.plan(self.manifest, "fast", changed)

    def full(self, changed):
        return tiers.plan(self.manifest, "full", changed)

    def assert_falls_back(self, changed):
        result = self.fast(changed)
        self.assertTrue(result.fallback, f"{changed} must fall back to the full tier")
        self.assertEqual(self.full(changed).checks, result.checks)

    def test_unsure_changes_fall_back_to_the_full_tier(self):
        cases = [
            ["new_area/source.c"],
            [".github/workflows/host.yml"],
            ["scripts/test-gpio.sh"],
            ["scripts/ci/checks.toml"],
            ["scripts/ci/tiers.py"],
            ["CMakeLists.txt"],
            ["CMakePresets.json"],
            ["cmake/CruxWebRoutes.cmake"],
            ["west.yml"],
            ["patches/zephyr/0001-fix.patch"],
            ["zephyr/Kconfig"],
            ["zephyr/module.yml"],
            ["components/gpio/Kconfig"],
            ["tests/gpio/prj.conf"],
            ["components/time/src/time.c"],
            ["components/thread/include/crux/thread.h"],
            [".clang-tidy"],
            ["Jenkinsfile"],
            [".devcontainer/Dockerfile"],
            ["tools/device_control/device_control.py"],
            ["templates/product/CMakeLists.txt"],
            ["components/gpio/src/a.c", "new_area/b.c"],
        ]
        for changed in cases:
            with self.subTest(changed=changed):
                self.assert_falls_back(changed)

    def test_a_change_touching_many_components_falls_back(self):
        self.assert_falls_back(["components/gpio/a.c", "components/spi/a.c", "components/i2c/a.c",
                                "components/serial/a.c"])

    def test_an_unknown_or_empty_change_falls_back(self):
        self.assert_falls_back(None)
        self.assert_falls_back([])

    def test_one_component_runs_the_quick_checks_and_its_own(self):
        result = self.fast(["components/gpio/src/gpio.c", "docs/gpio-contract.md"])
        self.assertFalse(result.fallback)
        ids = {c.id for c in result.checks}
        self.assertLessEqual({"host-build-and-test", "format", "static-analysis", "build-tests",
                              "zephyr-smoke", "patch-style", "gpio-zephyr", "docs-links"}, ids)
        self.assertNotIn("spi-zephyr", ids)
        self.assertNotIn("emmc-reliance-edge", ids)
        self.assertNotIn("build-tests-large", ids)
        self.assertNotIn("web-client-checks", ids)

    def test_a_fast_run_is_never_larger_than_the_full_run(self):
        for name, patterns in self.manifest.components.items():
            changed = [patterns[0].replace("**", "x/y.c")]
            with self.subTest(component=name):
                fast = self.fast(changed).checks
                full = self.full(changed).checks
                self.assertLessEqual(set(fast), set(full))
                ids = [c.id for c in full]
                self.assertEqual(sorted(ids.index(c.id) for c in fast), [ids.index(c.id) for c in fast])

    def test_every_fast_component_selects_less_than_the_full_tier(self):
        for name, patterns in self.manifest.components.items():
            changed = [patterns[0].replace("**", "x/y.c")]
            with self.subTest(component=name):
                self.assertLess(len(self.fast(changed).checks), len(self.full(changed).checks))

    def test_a_documentation_change_runs_only_the_documentation_readers(self):
        result = self.fast(["docs/build.md"])
        self.assertFalse(result.fallback)
        self.assertEqual(DOCS_READERS - {"build-tests-large"}, {c.id for c in result.checks})

    def test_a_web_client_change_runs_the_web_jobs(self):
        ids = {c.id for c in self.fast(["web/client/app.tsx"]).checks}
        self.assertLessEqual(set(EXPECTED_FULL["web-browser"]), ids)
        self.assertIn("web-assets-native", ids)

    def test_the_fallback_names_its_reason(self):
        self.assertIn("scripts/test-gpio.sh", self.fast(["scripts/test-gpio.sh"]).reason)
        self.assertIn("new_area/source.c", self.fast(["new_area/source.c"]).reason)


class PatternTest(unittest.TestCase):
    def test_patterns_follow_the_workflow_path_filter_rules(self):
        self.assertTrue(tiers.matches("README.md", ["**.md"]))
        self.assertTrue(tiers.matches("docs/a/b.md", ["**.md"]))
        self.assertTrue(tiers.matches("docs/a/b.png", ["docs/**"]))
        self.assertFalse(tiers.matches("docsx/a", ["docs/**"]))
        self.assertTrue(tiers.matches("components/gpio/Kconfig.gpio", ["**/Kconfig*"]))
        self.assertTrue(tiers.matches("Kconfig", ["**/Kconfig*"]))
        self.assertFalse(tiers.matches("components/gpio/src/a.c", ["components/*.c"]))

    def test_a_later_negation_removes_earlier_matches(self):
        psa = ["**", "!docs/**", "!**.md", "docs/dependency-review-*.md"]
        self.assertTrue(tiers.matches("components/a.c", psa))
        self.assertFalse(tiers.matches("docs/build.md", psa))
        self.assertFalse(tiers.matches("README.md", psa))
        self.assertTrue(tiers.matches("docs/dependency-review-x.md", psa))


class ManifestValidationTest(unittest.TestCase):
    BASE = textwrap.dedent("""\
        version = 1
        [selection]
        docs = ["docs/**"]
        escalate = []
        max_components = 3
        [components]
        a = ["a/**"]
        [jobs.one]
        description = "one"
        """)

    def load(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checks.toml"
            path.write_text(self.BASE + text)
            return tiers.load_manifest(path)

    def assert_rejected(self, text, words):
        with self.assertRaises(tiers.ManifestError) as caught:
            self.load(text)
        self.assertIn(words, str(caught.exception))

    def test_a_valid_manifest_loads(self):
        manifest = self.load('[[check]]\nid = "x"\njob = "one"\nrun = "true"\nfast = ["a"]\n')
        self.assertEqual(["x"], [c.id for c in manifest.checks])

    def test_mistakes_are_rejected(self):
        cases = [
            ('[[check]]\nid = "x"\njob = "two"\nrun = "true"\n', "unknown job"),
            ('[[check]]\nid = "x"\njob = "one"\nrun = "true"\nfast = ["b"]\n', "unknown component"),
            ('[[check]]\nid = "x"\njob = "one"\nrun = "true"\n[[check]]\nid = "x"\njob = "one"\nrun = "true"\n',
             "duplicate"),
            ('[[check]]\nid = "x"\njob = "one"\nrun = "true"\nfsat = "always"\n', "unknown key"),
            ('[[check]]\nid = "x"\njob = "one"\nrun = "true"\nscope = "nowhere"\n', "unknown scope"),
            ('[[check]]\nid = "x"\njob = "one"\nrun = "true"\ntiers = ["fast"]\n', "tiers"),
            ('[[check]]\nid = "x"\njob = "one"\nrun = "true"\nfast = "sometimes"\n', "fast"),
            ('[[check]]\nid = "x"\njob = "one"\nrun = "true"\ntiers = ["nightly"]\nfast = "always"\n', "fast"),
            ('[jobs.two]\ndescription = "two"\n[[check]]\nid = "x"\njob = "one"\nrun = "true"\n', "no checks"),
        ]
        for text, words in cases:
            with self.subTest(words=words):
                self.assert_rejected(text, words)


def git(directory, *arguments):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *arguments],
                          cwd=directory, check=True, capture_output=True, text=True).stdout.strip()


def commit(directory, files):
    for name, text in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    git(directory, "add", "-A")
    git(directory, "commit", "-q", "--allow-empty", "-m", "change")
    return git(directory, "rev-parse", "HEAD")


class ChangedFilesTest(unittest.TestCase):
    """The change comes from plain git, as the host workflow computed it before tiers."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="crux-tiers-test-")
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        origin = root / "origin"
        origin.mkdir()
        git(origin, "init", "-q")
        commit(origin, {"README.md": "a\n", "src/a.c": "int a;\n" * 20})
        self.clone = root / "clone"
        git(root, "clone", "-q", str(origin), str(self.clone))
        git(self.clone, "checkout", "-q", "-b", "topic")
        self.origin = origin

    def changed(self, base="origin/main"):
        return tiers.changed_files(self.clone, base)

    def docs_only(self):
        files = self.changed().files
        return files is not None and tiers.is_docs_only(files, ["docs/**", "**.md"])

    def test_a_documentation_change_is_documentation_only(self):
        commit(self.clone, {"docs/data.txt": "d\n", "tests/README.md": "t\n"})
        self.assertTrue(self.docs_only())

    def test_a_source_change_is_not(self):
        commit(self.clone, {"src/b.c": "int b;\n"})
        self.assertFalse(self.docs_only())

    def test_a_mixed_change_is_not(self):
        commit(self.clone, {"README.md": "b\n", "scripts/check.sh": "true\n"})
        self.assertFalse(self.docs_only())

    def test_a_source_file_moved_into_the_documentation_is_not(self):
        (self.clone / "docs").mkdir()
        git(self.clone, "mv", "src/a.c", "docs/a.md")
        commit(self.clone, {})
        self.assertEqual(["docs/a.md", "src/a.c"], self.changed().files)
        self.assertFalse(self.docs_only())

    def test_a_source_change_among_many_documents_is_not(self):
        files = {f"docs/{'n' * 80}-{number}.md": "d\n" for number in range(1500)}
        commit(self.clone, {"a.c": "int a;\n", **files})
        self.assertFalse(self.docs_only())

    def test_an_empty_change_is_not(self):
        commit(self.clone, {})
        self.assertEqual([], self.changed().files)
        self.assertFalse(self.docs_only())

    def test_changes_made_only_on_the_target_branch_are_not_counted(self):
        commit(self.origin, {"src/main-only.c": "int m;\n"})
        git(self.clone, "fetch", "-q", "origin")
        mine = commit(self.clone, {"docs/mine.md": "m\n"})
        change = self.changed()
        self.assertEqual(["docs/mine.md"], change.files)
        self.assertEqual(git(self.clone, "rev-parse", f"{mine}^"), change.diff_base)

    def test_an_unknown_base_gives_no_change(self):
        self.assertIsNone(self.changed(base="origin/no-such-branch").files)
        self.assertIsNone(self.changed(base="0" * 40).files)
        self.assertIsNone(self.changed(base=None).files)


class ContextTest(unittest.TestCase):
    """The tier and base of `auto` come from either CI system's environment."""

    def context(self, env, event=None):
        with tempfile.TemporaryDirectory() as directory:
            if event is not None:
                path = Path(directory) / "event.json"
                path.write_text(json.dumps(event))
                env = {**env, "GITHUB_EVENT_PATH": str(path)}
            return tiers.ci_context(env)

    def github(self, name, event, **extra):
        return self.context({"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": name, **extra}, event)

    def test_github_events(self):
        draft = self.github("pull_request", {"pull_request": {"draft": True}}, GITHUB_BASE_REF="main")
        ready = self.github("pull_request", {"pull_request": {"draft": False}}, GITHUB_BASE_REF="main")
        self.assertEqual(("fast", "origin/main", "change-request"), draft)
        self.assertEqual(("full", "origin/main", "change-request"), ready)
        repository = {"default_branch": "main"}
        merged = self.github("push", {"before": "a" * 40, "repository": repository}, GITHUB_REF="refs/heads/main")
        self.assertEqual(("full", "a" * 40, "post-merge"), merged)
        created = self.github("push", {"before": "0" * 40, "repository": repository}, GITHUB_REF="refs/heads/main")
        self.assertEqual(("full", None, "post-merge"), created)
        branch = self.github("push", {"before": "a" * 40, "repository": repository}, GITHUB_REF="refs/heads/topic")
        self.assertEqual(("fast", "origin/main", "branch"), branch)
        self.assertEqual(("nightly", None, "scheduled"), self.github("schedule", {}))
        self.assertEqual(("full", None, "manual"), self.github("workflow_dispatch", {}))
        queue = self.github("merge_group", {"merge_group": {"base_sha": "b" * 40}})
        self.assertEqual(("full", "b" * 40, "merge-queue"), queue)

    def test_jenkins_builds(self):
        jenkins = {"JENKINS_URL": "https://ci.example.invalid/"}
        change = self.context({**jenkins, "CHANGE_ID": "12", "CHANGE_TARGET": "main", "BRANCH_NAME": "PR-12"})
        self.assertEqual(("full", "origin/main", "change-request"), change)
        merged = self.context({**jenkins, "BRANCH_NAME": "main", "GIT_PREVIOUS_SUCCESSFUL_COMMIT": "c" * 40})
        self.assertEqual(("full", "c" * 40, "post-merge"), merged)
        first = self.context({**jenkins, "BRANCH_NAME": "main"})
        self.assertEqual(("full", None, "first-build"), first)
        branch = self.context({**jenkins, "BRANCH_NAME": "feature/x"})
        self.assertEqual(("fast", "origin/main", "branch"), branch)
        timer = self.context({**jenkins, "BRANCH_NAME": "main", "CRUX_CI_TRIGGER": "timer"})
        self.assertEqual(("nightly", None, "scheduled"), timer)
        other_default = self.context({**jenkins, "BRANCH_NAME": "develop", "CRUX_CI_DEFAULT_BRANCH": "develop"})
        self.assertEqual("full", other_default[0])

    def test_a_local_run_is_fast_against_main(self):
        self.assertEqual(("fast", "origin/main", "local"), self.context({}))


class RunnerTest(unittest.TestCase):
    """Run a small manifest end to end through scripts/ci/run-tier.sh."""

    MANIFEST = textwrap.dedent("""\
        version = 1
        [selection]
        docs = ["docs/**"]
        escalate = []
        max_components = 3
        [components]
        a = ["a/**"]
        [jobs.one]
        description = "one"
        env = { CRUX_TEST_JOB_VALUE = "job" }
        [jobs.two]
        description = "two"
        [[check]]
        id = "first"
        job = "one"
        run = "echo first-ran $CRUX_TEST_JOB_VALUE $CRUX_CI_TIER"
        [[check]]
        id = "fails"
        job = "one"
        run = "echo about-to-fail; exit 3"
        [[check]]
        id = "after"
        job = "one"
        run = "echo after-ran"
        [[check]]
        id = "report"
        job = "one"
        run = "echo report-ran; exit 4"
        tiers = ["nightly"]
        advisory = true
        [[check]]
        id = "other"
        job = "two"
        run = "echo other-ran"
        """)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="crux-runner-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        git(self.root, "init", "-q")
        (self.root / "checks.toml").write_text(self.MANIFEST)
        commit(self.root, {"a/x.c": "x\n"})

    def run_tier(self, *arguments):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("GITHUB_", "CHANGE_", "JENKINS_", "CRUX_CI_"))}
        env["CRUX_CI_PYTHON"] = sys.executable
        command = [str(REPO / "scripts/ci/run-tier.sh"), *arguments, "--manifest", str(self.root / "checks.toml"),
                   "--root", str(self.root)]
        return subprocess.run(command, cwd=self.root, env=env, capture_output=True, text=True, check=False)

    def test_the_first_failure_stops_the_job_and_names_the_rerun(self):
        result = self.run_tier("full", "--job", "one")
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("first-ran job full", result.stdout)
        self.assertIn("about-to-fail", result.stdout)
        self.assertNotIn("after-ran", result.stdout)
        self.assertNotIn("other-ran", result.stdout)
        self.assertIn("fails failed (exit 3)", result.stderr)
        self.assertIn("scripts/ci/run-tier.sh full --job one --check fails", result.stderr)
        self.assertIn("docs/ci.md", result.stderr)

    def test_junit_and_logs_are_written(self):
        self.run_tier("full", "--job", "one")
        suite = ET.parse(self.root / "build/ci/one.junit.xml").getroot().find("testsuite")
        cases = {case.get("name"): case for case in suite.iter("testcase")}
        self.assertEqual({"first", "fails", "after"}, set(cases))
        self.assertIsNone(cases["first"].find("failure"))
        self.assertIsNotNone(cases["fails"].find("failure"))
        self.assertIsNotNone(cases["after"].find("skipped"))
        self.assertEqual("1", suite.get("failures"))
        self.assertIn("about-to-fail", (self.root / "build/ci/logs/one/fails.log").read_text())

    def test_an_advisory_check_runs_after_a_failure_and_never_fails_the_job(self):
        result = self.run_tier("nightly", "--job", "one")
        self.assertEqual(1, result.returncode)
        self.assertIn("report-ran", result.stdout)
        self.assertIn("advisory", result.stderr)

    def test_an_advisory_failure_alone_passes(self):
        result = self.run_tier("nightly", "--job", "one", "--check", "report")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("warning", result.stderr)

    def test_a_named_check_runs_alone(self):
        result = self.run_tier("full", "--job", "one", "--check", "first")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("about-to-fail", result.stdout)

    def test_plan_and_count_run_nothing(self):
        plan = self.run_tier("full", "--job", "two", "--plan")
        self.assertEqual(0, plan.returncode, plan.stderr)
        self.assertIn("other", plan.stdout)
        self.assertNotIn("other-ran", plan.stdout)
        count = self.run_tier("full", "--job", "one", "--count")
        self.assertEqual("3", count.stdout.strip())

    def test_a_job_with_nothing_selected_passes(self):
        commit(self.root, {"docs/x.md": "x\n"})
        result = self.run_tier("full", "--job", "two", "--base", "HEAD^")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("No checks selected", result.stdout)

    def test_usage_errors_exit_2(self):
        self.assertEqual(2, self.run_tier("sometimes").returncode)
        self.assertEqual(2, self.run_tier("full", "--job", "three").returncode)
        self.assertEqual(2, self.run_tier("full", "--check", "missing").returncode)


class UnittestPartitionTest(unittest.TestCase):
    """The large tests/build cases and the rest together are every case, each once."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="crux-partition-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "test_one.py").write_text(textwrap.dedent("""\
            import unittest
            class A(unittest.TestCase):
                def test_quick(self):
                    print("ran-quick")
                def test_slow(self):
                    print("ran-slow")
            class B(unittest.TestCase):
                def test_other(self):
                    print("ran-other")
            """))
        (self.root / "large.txt").write_text("# comment\ntest_one.A.test_slow\n")

    def run_partition(self, *arguments):
        command = [sys.executable, str(REPO / "scripts/ci/run_unittests.py"), "-s", str(self.root), *arguments]
        return subprocess.run(command, capture_output=True, text=True, check=False)

    def test_exclude_and_only_partition_the_cases(self):
        rest = self.run_partition("--exclude-from", str(self.root / "large.txt"))
        large = self.run_partition("--only-from", str(self.root / "large.txt"))
        self.assertEqual(0, rest.returncode, rest.stderr)
        self.assertEqual(0, large.returncode, large.stderr)
        self.assertIn("ran-quick", rest.stdout)
        self.assertIn("ran-other", rest.stdout)
        self.assertNotIn("ran-slow", rest.stdout)
        self.assertIn("ran-slow", large.stdout)
        self.assertNotIn("ran-quick", large.stdout)

    def test_a_listed_case_that_does_not_exist_is_an_error(self):
        (self.root / "large.txt").write_text("test_one.A.test_renamed\n")
        for option in ("--exclude-from", "--only-from"):
            with self.subTest(option=option):
                result = self.run_partition(option, str(self.root / "large.txt"))
                self.assertEqual(2, result.returncode)
                self.assertIn("test_one.A.test_renamed", result.stderr)

    def test_a_failing_case_fails_the_run(self):
        (self.root / "test_two.py").write_text(
            "import unittest\nclass C(unittest.TestCase):\n    def test_bad(self):\n        self.fail('x')\n")
        self.assertEqual(1, self.run_partition("--exclude-from", str(self.root / "large.txt")).returncode)

    def test_the_large_list_names_existing_cases(self):
        large = REPO / "scripts/ci/large-tests.txt"
        ids = [line.strip() for line in large.read_text().splitlines() if line.strip() and not line.startswith("#")]
        self.assertTrue(ids)
        for test_id in ids:
            module, class_name, method = test_id.split(".")
            with self.subTest(test=test_id):
                sources = list(REPO.glob(f"tests/**/{module}.py"))
                self.assertTrue(sources, f"{module}.py not found")
                self.assertTrue(any(f"class {class_name}(" in s.read_text() and f"def {method}(" in s.read_text()
                                    for s in sources))


def workflow_job(path, job):
    """Return the text of one job of a workflow, up to the next job."""
    lines = path.read_text().splitlines()
    start = lines.index(f"  {job}:")
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"  \S", lines[i])), len(lines))
    return "\n".join(lines[start:end])


PINS = r"\b([A-Za-z][\w-]*==[\d.]+)"


class JenkinsTest(unittest.TestCase):
    """The Jenkins wrapper runs the same jobs with the same tools as the GitHub workflows."""

    @classmethod
    def setUpClass(cls):
        cls.jenkinsfile = (REPO / "Jenkinsfile").read_text()
        cls.run_job = (REPO / "scripts/ci/jenkins/run-job.sh").read_text()
        cls.manifest = tiers.load_manifest(MANIFEST)

    def jenkins_pins(self, job):
        for line in self.run_job.splitlines():
            match = re.match(r"\s+([\w*| -]+)\) tools=\"(.*)\" ;;$", line)
            if not match:
                continue
            labels = [label.strip() for label in match.group(1).split("|")]
            if job in labels or any(label.endswith("*") and job.startswith(label[:-1]) for label in labels):
                return set(re.findall(PINS, match.group(2)))
        self.fail(f"run-job.sh has no tools line for {job}")

    def test_every_job_has_a_stage_that_runs_it(self):
        stages = re.findall(r"stage\('([\w-]+)'\) \{\n\s+agent .*\n\s+steps \{ script \{ runJob\('([\w-]+)'\) \} \}",
                            self.jenkinsfile)
        self.assertEqual(sorted((job, job) for job in self.manifest.jobs), sorted(stages))

    def test_every_job_has_tools_in_the_jenkins_set_up(self):
        for job in self.manifest.jobs:
            with self.subTest(job=job):
                self.jenkins_pins(job)

    def test_every_container_stage_builds_the_image_without_j_link(self):
        agents = re.findall(r"agent \{ dockerfile \{([^}]*)\}", self.jenkinsfile)
        self.assertTrue(agents)
        for agent in agents:
            self.assertIn("filename '.devcontainer/Dockerfile'", agent)
            self.assertIn("--build-arg CRUX_JLINK=0", agent)

    def test_the_stages_call_only_the_repository_scripts(self):
        commands = re.findall(r"\bsh \"([^\"]+)\"", self.jenkinsfile)
        self.assertEqual(["scripts/ci/jenkins/run-job.sh ${job}"], commands)
        self.assertIn('exec scripts/ci/run-tier.sh "$tier" --job "$job"', self.run_job)

    def test_the_tools_match_the_github_workflows(self):
        workflows = REPO / ".github/workflows"
        cases = {
            "host": workflow_job(workflows / "host.yml", "host"),
            "host-build-tests": workflow_job(workflows / "host.yml", "host-build-tests"),
            "zephyr-io": workflow_job(workflows / "zephyr.yml", "shard"),
            "psa-crypto": workflow_job(workflows / "psa-crypto.yml", "psa-crypto"),
            "coverage-host": workflow_job(workflows / "coverage.yml", "host"),
            "coverage-native-sim": workflow_job(workflows / "coverage.yml", "native-sim"),
        }
        for job, text in cases.items():
            with self.subTest(job=job):
                self.assertEqual(set(re.findall(PINS, text)), self.jenkins_pins(job))

    def test_the_coverage_workflow_runs_the_nightly_coverage_checks(self):
        coverage = (REPO / ".github/workflows/coverage.yml").read_text()
        for job, ids in EXPECTED_NIGHTLY_ONLY.items():
            for check in (c for c in self.manifest.checks if c.id in ids):
                with self.subTest(check=check.id):
                    self.assertIn(check.run, coverage)

    def test_no_github_workflow_runs_the_jenkins_files(self):
        for workflow in (REPO / ".github/workflows").glob("*.yml"):
            with self.subTest(workflow=workflow.name):
                self.assertNotIn("Jenkinsfile", workflow.read_text())
                self.assertNotIn("scripts/ci/jenkins", workflow.read_text())


if __name__ == "__main__":
    unittest.main()
