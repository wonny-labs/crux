"""The Dev Container image builds without a west workspace, and bash-completion is there to load west's.

`west completion` is a Zephyr extension command: it exists only inside a west workspace, and
the image build has none. scripts/bootstrap.sh therefore writes west's completion script after
it sets up the workspace (tests/build/test_bootstrap.py checks that); the image only installs
bash-completion, which loads the script from the user directory. The checks read the
Dockerfile only; they do not build the image.
"""
import re
import unittest
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[2] / ".devcontainer" / "Dockerfile"

# Commands that west 1.4.0 itself provides (`west help` outside a workspace). Every other west
# command is an extension that a manifest project supplies, so it needs a workspace.
WEST_BUILT_INS = {
    "compare", "config", "diff", "forall", "grep", "help", "init", "list", "manifest",
    "selfupdate", "status", "topdir", "update", "--version", "-V", "--help", "-h",
}


def steps():
    """Return the Dockerfile instructions in order, comments dropped, continuations joined."""
    result, current = [], ""
    for line in DOCKERFILE.read_text().splitlines():
        if not current and (not line.strip() or line.lstrip().startswith("#")):
            continue
        current += line.rstrip("\\").strip() + " "
        if not line.rstrip().endswith("\\"):
            result.append(current.strip())
            current = ""
    return result


def west_commands(step):
    """Return the first argument of every `west` invocation in a shell step."""
    return re.findall(r"(?:^|[\s;&|(])west\s+(\S+)", step)


class DockerfileTest(unittest.TestCase):
    def test_bash_completion_package_is_installed(self):
        self.assertRegex(next(s for s in steps() if s.startswith("RUN apt-get")), r"\bbash-completion\b")

    def test_no_build_step_runs_a_workspace_only_west_command(self):
        run_steps = [s for s in steps() if s.startswith("RUN ")]
        self.assertTrue(run_steps)
        for step in run_steps:
            for command in west_commands(step[4:]):
                self.assertIn(command, WEST_BUILT_INS, f"needs a west workspace: {step}")

    def test_the_check_catches_the_completion_step(self):
        self.assertEqual(west_commands("install -d /x && west completion bash > /x/west"), ["completion"])

    def test_no_bashrc_edit(self):
        self.assertFalse(any(".bashrc" in step for step in steps() if step.startswith("RUN ")))


if __name__ == "__main__":
    unittest.main()
