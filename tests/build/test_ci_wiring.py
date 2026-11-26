# SPDX-License-Identifier: Apache-2.0
"""Check that CI keeps the gates that reviews rely on.

A gate that CI does not run, or that cannot fail, looks the same as a gate that passes. These
tests read the preset, the workflow text and the CI map file (scripts/ci/checks.toml) and hold
six rules:

- the `host-sanitize` preset aborts on undefined behaviour instead of printing and continuing,
- the host jobs install PyYAML and west, so that the manifest and workspace cases of `tests/build`
  run instead of skipping,
- the tests/build checks set CLANG_TIDY, so that the real-tool case of the product style check runs,
- the host job runs the File service checks, whose consumer build no other step covers,
- a Zephyr job runs the smoke check that AGENTS.md lists as a validation check,
- the host workflow skips a step only when the tier selected no check for its job; which checks
  a documentation-only change skips is the selector's rule, tested in test_ci_tiers.py.

Only the standard library is used.
"""
import json
from pathlib import Path
import re
import tomllib
import unittest

REPO = Path(__file__).resolve().parents[2]
PRESETS = REPO / "CMakePresets.json"
# The tests skip only in a copy without the workflow folder; a single missing workflow fails them.
WORKFLOWS = REPO / ".github/workflows"
HOST = REPO / ".github/workflows/host.yml"
MANIFEST = REPO / "scripts/ci/checks.toml"
NO_GITHUB = "this copy has no .github/workflows; see docs/ci.md#copies-without-github"


def step_text(workflow, title):
    """Return the text of the first step with this name, up to the next step."""
    lines = workflow.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == f"- name: {title}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("      - ")), len(lines))
    return "\n".join(lines[start:end])


def checks():
    return {c["id"]: c for c in tomllib.loads(MANIFEST.read_text())["check"]}


class SanitizePresetTest(unittest.TestCase):
    def test_undefined_behaviour_aborts_the_run(self):
        presets = json.loads(PRESETS.read_text())["configurePresets"]
        flags = next(p for p in presets if p["name"] == "host-sanitize")["cacheVariables"]
        for language in ("CMAKE_C_FLAGS", "CMAKE_CXX_FLAGS"):
            with self.subTest(language=language):
                self.assertIn("-fsanitize=address,undefined", flags[language])
                # Clang's undefined behaviour checks report and continue unless told otherwise.
                self.assertRegex(flags[language], r"-fno-sanitize-recover=(undefined|all)\b")


class HostWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = HOST.read_text() if WORKFLOWS.is_dir() else ""
        cls.checks = checks()

    @unittest.skipUnless(WORKFLOWS.is_dir(), NO_GITHUB)
    def test_the_python_tools_include_pyyaml_and_west(self):
        installs = re.findall(r"- name: Install host tools\n(?:        .*\n)+", self.workflow)
        self.assertEqual(2, len(installs), "one install in each host job")
        for install in installs:
            self.assertRegex(install, r"\bwest==\d")
            self.assertRegex(install, r"\bpyyaml==\d")

    def test_the_build_checks_see_clang_tidy(self):
        for name in ("build-tests", "build-tests-large"):
            with self.subTest(check=name):
                run = self.checks[name]["run"]
                self.assertIn("-s tests/build", run)
                self.assertRegex(run, r"^CLANG_TIDY=clang-tidy-18 ")

    def test_the_file_service_checks_run(self):
        self.assertEqual("./scripts/test-file-service.sh", self.checks["file-service-host"]["run"])
        self.assertEqual("host", self.checks["file-service-host"]["job"])


PLAN_STEP = "Plan the checks of this tier"
PLANNED = "steps.plan.outputs.checks != '0'"


@unittest.skipUnless(WORKFLOWS.is_dir(), NO_GITHUB)
class HostTierStepsTest(unittest.TestCase):
    def test_only_the_plan_runs_before_the_tier_is_known(self):
        workflow = HOST.read_text()
        titles = re.findall(r"^      - name: (.+)$", workflow, re.MULTILINE)
        self.assertEqual(2, titles.count(PLAN_STEP))
        for title in set(titles) - {PLAN_STEP}:
            for block in re.findall(rf"- name: {re.escape(title)}\n(?:        .*\n)+", workflow):
                conditions = re.findall(r"^        if: (.+)$", block, re.MULTILINE)
                with self.subTest(step=title):
                    self.assertEqual(1, len(conditions))
                    self.assertIn(conditions[0], (PLANNED, f"always() && {PLANNED}"))


class ZephyrWorkflowTest(unittest.TestCase):
    def test_the_smoke_check_runs(self):
        smoke = checks()["zephyr-smoke"]
        self.assertEqual("scripts/check-zephyr-smoke.sh", smoke["run"])
        self.assertTrue(smoke["job"].startswith("zephyr-"))


if __name__ == "__main__":
    unittest.main()
