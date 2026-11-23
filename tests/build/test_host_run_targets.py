"""Check that each Linux Host sample has a `run_<sample>` build target, the Host counterpart of
`west build -t run` on native_sim.

`cmake --build --preset host-debug --target run_clock_shell` builds the program and runs it in the
terminal (USES_TERMINAL gives it stdin under Ninja). This reads the CMake files; it does not
configure or run a build, because the Host composition builds on Linux only.
"""
import json
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[2]

# target name -> (CMake file, what the target runs)
TARGETS = {
    "run_clock_shell": ("samples/time/clock_shell/host/CMakeLists.txt", "crux-time-host"),
    "run_echo_client": ("samples/networking/echo_client/host/CMakeLists.txt",
                        "$<TARGET_FILE:crux-networking-host> --echo-peer"),
    "run_hello_crux": ("samples/hello_crux/host/CMakeLists.txt", "hello-crux-host"),
}


def custom_target(text, name):
    match = re.search(r"add_custom_target\(\s*" + re.escape(name) + r"\b(.*?)\)\s*$", text, re.S | re.M)
    return match.group(1) if match else None


class HostRunTargetTest(unittest.TestCase):
    def test_each_host_sample_has_a_run_target(self):
        for name, (path, runs) in TARGETS.items():
            with self.subTest(target=name):
                body = custom_target((REPO / path).read_text(), name)
                self.assertIsNotNone(body, f"{path} defines no add_custom_target({name} ...)")
                self.assertIn(runs, body)
                self.assertIn("USES_TERMINAL", body)

    def test_echo_client_runs_with_its_echo_peer(self):
        body = custom_target((REPO / TARGETS["run_echo_client"][0]).read_text(), "run_echo_client")
        self.assertIn("scripts/run-host-sample.py", body)
        self.assertIn("DEPENDS crux-networking-host", body)


    def test_vs_code_tasks_run_the_host_samples(self):
        # Terminal > Run Task in VS Code runs the same build targets without typing a command.
        tasks = {t["label"]: t for t in json.loads((REPO / ".vscode/tasks.json").read_text())["tasks"]}
        for name in ("run_clock_shell", "run_echo_client"):
            with self.subTest(target=name):
                task = tasks[f"Host: {name}"]
                self.assertEqual(task["command"], "cmake")
                self.assertEqual(task["args"], ["--build", "--preset", "host-debug", "--target", name])
                self.assertEqual(task["options"]["cwd"], "${workspaceFolder}")

    def test_vs_code_task_runs_hello_crux_as_its_own_project(self):
        # hello_crux/host is its own CMake project (tutorial step 2): the task configures it with
        # the tutorial's command line, then builds and runs its run target.
        tasks = {t["label"]: t for t in json.loads((REPO / ".vscode/tasks.json").read_text())["tasks"]}
        task = tasks["Host: run_hello_crux"]
        self.assertEqual(task["options"]["cwd"], "${workspaceFolder}")
        script = " ".join(task["args"])
        self.assertIn('cmake -S samples/hello_crux/host -B build/samples/hello_crux_host -G Ninja '
                      '-DCRUX_SOURCE_DIR="$PWD"', script)
        self.assertIn("cmake --build build/samples/hello_crux_host --target run_hello_crux", script)
        tutorial = (REPO / "docs/tutorial.md").read_text()
        self.assertIn("Host: run_hello_crux", tutorial)


if __name__ == "__main__":
    unittest.main()
