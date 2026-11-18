# SPDX-License-Identifier: Apache-2.0
"""Check that CI keeps the gates that reviews rely on.

A gate that CI does not run, or that cannot fail, looks the same as a gate that passes. These
tests read the preset and the workflow text and hold five rules:

- the `host-sanitize` preset aborts on undefined behaviour instead of printing and continuing,
- the host job installs PyYAML and west, so that the manifest and workspace cases of `tests/build`
  run instead of skipping,
- the host job sets CLANG_TIDY, so that the real-tool case of the product style check runs,
- the host job runs the File service checks, whose consumer build no other step covers,
- the Zephyr workflow runs the smoke check that AGENTS.md lists as a validation check.

Only the standard library is used.
"""
import json
from pathlib import Path
import re
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
        self.assertIn("scripts/test-file-service.sh", self.workflow)


class ZephyrWorkflowTest(unittest.TestCase):
    def test_the_smoke_check_runs(self):
        self.assertIsNotNone(re.search(r"run: scripts/check-zephyr-smoke\.sh", ZEPHYR.read_text()))


if __name__ == "__main__":
    unittest.main()
