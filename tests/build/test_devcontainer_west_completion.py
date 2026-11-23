"""The Dev Container image ships west Tab completion for bash in the standard system location.

The Dockerfile step runs after west is installed, writes the script of `west completion bash`
to the bash-completion directory (so every user gets it without a ~/.bashrc edit), needs no
network, and fails the build when `west completion` fails. The checks read the Dockerfile
only; a real image build is the owner's check.
"""
import re
import unittest
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[2] / ".devcontainer" / "Dockerfile"
TARGET = "/usr/share/bash-completion/completions/west"


def run_steps():
    """Return each RUN instruction as one string, in file order, continuations joined."""
    text = DOCKERFILE.read_text().replace("\\\n", " ")
    return [line for line in text.splitlines() if line.startswith("RUN ")]


class WestCompletionStepTest(unittest.TestCase):
    def setUp(self):
        self.steps = run_steps()
        self.install = next(i for i, step in enumerate(self.steps) if "pip install" in step and "west==" in step)
        self.completion = [i for i, step in enumerate(self.steps) if "west completion bash" in step]

    def test_bash_completion_package_is_installed(self):
        self.assertRegex(self.steps[0], r"\bbash-completion\b")

    def test_one_completion_step_follows_the_west_install(self):
        self.assertEqual(len(self.completion), 1)
        self.assertGreaterEqual(self.completion[0], self.install)

    def test_script_is_written_to_the_standard_bash_completion_path(self):
        step = self.steps[self.completion[0]]
        self.assertRegex(step, r"west completion bash\s*>\s*" + re.escape(TARGET) + r"(\s|$)")
        self.assertIn("install -d /usr/share/bash-completion/completions", step)

    def test_step_needs_no_network_and_fails_the_build_on_error(self):
        step = self.steps[self.completion[0]]
        for forbidden in ("curl", "wget", "pip ", "git ", "|| true", ";"):
            self.assertNotIn(forbidden, step)
        # The directory is created first and the redirect is chained with &&.
        self.assertLess(step.index("install -d"), step.index("west completion bash"))
        self.assertIn("&&", step)

    def test_no_bashrc_edit(self):
        self.assertFalse(any(".bashrc" in step for step in self.steps))


if __name__ == "__main__":
    unittest.main()
