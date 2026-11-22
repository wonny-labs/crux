"""Check that each Linux Host sample has a `run_<sample>` build target, the Host counterpart of
`west build -t run` on native_sim.

`cmake --build --preset host-debug --target run_clock_shell` builds the program and runs it in the
terminal (USES_TERMINAL gives it stdin under Ninja). This reads the CMake files; it does not
configure or run a build, because the Host composition builds on Linux only.
"""
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


if __name__ == "__main__":
    unittest.main()
