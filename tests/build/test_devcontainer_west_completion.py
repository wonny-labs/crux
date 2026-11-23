"""The Dev Container image ships west Tab completion for bash without needing a workspace to build.

`west completion` is a Zephyr extension command: it exists only inside a west workspace, so
an image build, which has none, cannot run it. The image therefore installs a small file,
.devcontainer/west-completion.bash, in the bash-completion directory. bash-completion loads
it on the first `west <Tab>`; it then defines the completion from `west completion bash` when
that works and defines nothing, silently, when it does not.

The checks read the Dockerfile and source the file in bash with a fake `west` on PATH. They
do not build the image or use a real workspace.
"""
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import unittest

DEVCONTAINER = Path(__file__).resolve().parents[2] / ".devcontainer"
DOCKERFILE = DEVCONTAINER / "Dockerfile"
STUB = DEVCONTAINER / "west-completion.bash"
TARGET = "/usr/share/bash-completion/completions/west.bash"

# Commands that west itself provides (`west help` outside a workspace). Every other west
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
        for step in steps():
            if step.startswith("RUN "):
                for command in west_commands(step[4:]):
                    self.assertIn(command, WEST_BUILT_INS, f"needs a west workspace: {step}")

    def test_the_stub_is_copied_to_the_standard_bash_completion_path(self):
        copies = [s for s in steps() if s.startswith("COPY ") and TARGET in s]
        self.assertEqual(copies, [f"COPY .devcontainer/west-completion.bash {TARGET}"])

    def test_no_bashrc_edit(self):
        self.assertFalse(any(".bashrc" in step for step in steps()))


@unittest.skipUnless(shutil.which("bash"), "bash is not installed")
class StubTest(unittest.TestCase):
    """Source the stub the way bash-completion does, with a fake `west` first on PATH."""

    def source_stub(self, fake_west, after='complete -p west 2>/dev/null || echo "no compspec"'):
        with tempfile.TemporaryDirectory() as tmp:
            west = Path(tmp) / "west"
            west.write_text("#!/bin/sh\n" + fake_west)
            west.chmod(west.stat().st_mode | stat.S_IXUSR)
            env = dict(os.environ, PATH=f"{tmp}{os.pathsep}{os.environ.get('PATH', '')}")
            script = f'. "{STUB}"; echo "status=$?"; {after}'
            return subprocess.run(["bash", "--norc", "--noprofile", "-c", script],
                                  env=env, capture_output=True, text=True, check=True)

    def test_inside_a_workspace_it_defines_the_completion_from_west(self):
        result = self.source_stub(
            'if [ "$*" = "completion bash" ]; then echo \'complete -W "build flash" west\'; '
            'else exit 2; fi\n')
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout.splitlines(), ["status=0", "complete -W 'build flash' west"])

    def test_outside_a_workspace_it_defines_nothing_and_prints_nothing(self):
        result = self.source_stub(
            "echo 'west: unknown command \"completion\"; do you need to run this inside a "
            "workspace?' >&2\nexit 1\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout.splitlines(), ["status=0", "no compspec"])

    def test_empty_output_defines_nothing(self):
        result = self.source_stub("exit 0\n")
        self.assertEqual(result.stdout.splitlines(), ["status=0", "no compspec"])

    def test_leaves_no_variable_behind(self):
        result = self.source_stub("echo 'complete -W build west'\n", after="compgen -v")
        before = subprocess.run(["bash", "--norc", "--noprofile", "-c", 'echo "status=0"; compgen -v'],
                                env=dict(os.environ), capture_output=True, text=True, check=True)
        ignored = {"PATH", "_", "BASH_COMMAND", "BASH_LINENO", "BASH_SOURCE", "FUNCNAME", "LINENO"}
        new = set(result.stdout.split()) - set(before.stdout.split()) - ignored
        self.assertEqual(new, set())


if __name__ == "__main__":
    unittest.main()
