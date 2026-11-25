# SPDX-License-Identifier: Apache-2.0
"""Check that CI keeps the gates that reviews rely on.

A gate that CI does not run, or that cannot fail, looks the same as a gate that passes. These
tests read the preset and the workflow text and hold six rules:

- the `host-sanitize` preset aborts on undefined behaviour instead of printing and continuing,
- the host job installs PyYAML and west, so that the manifest and workspace cases of `tests/build`
  run instead of skipping,
- the host job sets CLANG_TIDY, so that the real-tool case of the product style check runs,
- the host job runs the File service checks, whose consumer build no other step covers,
- the Zephyr workflow runs the smoke check that AGENTS.md lists as a validation check,
- the host job skips steps only for a pull request that changes nothing but documentation, and
  never skips the documentation checks in `tests/build`.

Only the standard library, bash and git are used.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import unittest

REPO = Path(__file__).resolve().parents[2]
PRESETS = REPO / "CMakePresets.json"
HOST = REPO / ".github/workflows/host.yml"
ZEPHYR = REPO / ".github/workflows/zephyr.yml"


def step_text(workflow, title):
    """Return the text of the step with this name, up to the next step."""
    lines = workflow.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == f"- name: {title}")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("      - ")), len(lines))
    return "\n".join(lines[start:end])


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
        cls.workflow = HOST.read_text()

    def test_the_python_tools_include_pyyaml_and_west(self):
        install = step_text(self.workflow, "Install host tools")
        self.assertRegex(install, r"\bwest==\d")
        self.assertRegex(install, r"\bpyyaml==\d")

    def test_the_build_checks_see_clang_tidy(self):
        checks = step_text(self.workflow, "Check build provenance safeguards")
        self.assertIn("python3 -m unittest discover -s tests/build", checks)
        self.assertRegex(checks, r"CLANG_TIDY: clang-tidy-18\b")

    def test_the_file_service_checks_run(self):
        self.assertIn("run: ./scripts/test-file-service.sh", self.workflow)


SCOPE_STEP = "Decide the scope of the run"
SKIPPED_FOR_DOCS = "steps.scope.outputs.docs_only != 'true'"
ALWAYS_RUN = {SCOPE_STEP, "Install host tools", "Check build provenance safeguards"}


class HostScopeStepsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = HOST.read_text()

    def test_only_the_documentation_checks_and_their_tools_always_run(self):
        titles = re.findall(r"^      - name: (.+)$", self.workflow, re.MULTILINE)
        self.assertLessEqual(ALWAYS_RUN, set(titles))
        for title in titles:
            conditions = re.findall(r"^        if: (.+)$", step_text(self.workflow, title), re.MULTILINE)
            with self.subTest(step=title):
                if title in ALWAYS_RUN:
                    self.assertEqual([], conditions)
                else:
                    self.assertEqual(1, len(conditions))
                    self.assertIn(conditions[0], (SKIPPED_FOR_DOCS, f"always() && {SKIPPED_FOR_DOCS}"))


class HostScopeScriptTest(unittest.TestCase):
    """Run the script of the scope step in a temporary clone."""

    def setUp(self):
        step = step_text(HOST.read_text(), SCOPE_STEP)
        self.script = textwrap.dedent(step.split("run: |\n", 1)[1])
        self.temporary = tempfile.TemporaryDirectory(prefix="crux-scope-test-")
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        origin = root / "origin"
        origin.mkdir()
        self.git(origin, "init", "-q", "-b", "main")
        self.commit(origin, {"README.md": "a\n", "src/a.c": "int a;\n" * 20})
        self.clone = root / "clone"
        self.git(root, "clone", "-q", str(origin), str(self.clone))
        self.output = root / "output"

    @staticmethod
    def git(directory, *arguments):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        "-c", "commit.gpgsign=false", *arguments],
                       cwd=directory, check=True, capture_output=True)

    def commit(self, directory, files):
        for name, text in files.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.git(directory, "add", "-A")
        self.git(directory, "commit", "-q", "--allow-empty", "-m", "change")

    def docs_only(self, event="pull_request"):
        self.output.write_text("")
        env = {**os.environ, "GITHUB_EVENT_NAME": event, "GITHUB_BASE_REF": "main",
               "GITHUB_OUTPUT": str(self.output)}
        result = subprocess.run(["bash", "-eo", "pipefail", "-c", self.script], cwd=self.clone, env=env,
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return self.output.read_text().strip()

    def test_a_documentation_change_is_documentation_only(self):
        self.commit(self.clone, {"docs/data.txt": "d\n", "tests/README.md": "t\n"})
        self.assertEqual("docs_only=true", self.docs_only())

    def test_a_source_change_is_complete(self):
        self.commit(self.clone, {"src/b.c": "int b;\n"})
        self.assertEqual("docs_only=false", self.docs_only())

    def test_a_mixed_change_is_complete(self):
        self.commit(self.clone, {"README.md": "b\n", "scripts/check.sh": "true\n"})
        self.assertEqual("docs_only=false", self.docs_only())

    def test_a_source_file_moved_into_the_documentation_is_complete(self):
        (self.clone / "docs").mkdir()
        self.git(self.clone, "mv", "src/a.c", "docs/a.md")
        self.commit(self.clone, {})
        self.assertEqual("docs_only=false", self.docs_only())

    def test_a_source_change_among_many_documents_is_complete(self):
        # The list of names is larger than a pipe buffer, so an early exit must not hide the match.
        files = {f"docs/{'n' * 80}-{number}.md": "d\n" for number in range(1500)}
        self.commit(self.clone, {"a.c": "int a;\n", **files})
        self.assertEqual("docs_only=false", self.docs_only())

    def test_an_empty_change_is_complete(self):
        self.commit(self.clone, {})
        self.assertEqual("docs_only=false", self.docs_only())

    def test_a_push_is_complete(self):
        self.commit(self.clone, {"README.md": "b\n"})
        self.assertEqual("docs_only=false", self.docs_only(event="push"))


class ZephyrWorkflowTest(unittest.TestCase):
    def test_the_smoke_check_runs(self):
        self.assertIsNotNone(re.search(r"run: scripts/check-zephyr-smoke\.sh", ZEPHYR.read_text()))


if __name__ == "__main__":
    unittest.main()
