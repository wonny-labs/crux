"""Host checks of the RT1060-EVKB cross-build of the console that shares its UART with Logging.

The cross-build is tests/zephyr/cli_console_shared_compile/run.sh, which scripts/test-management-mbed-rt1060.sh
build runs in CI. These checks read the fixture, and run the script against a fake `west` that writes the build
outputs the script inspects, so that each of its assertions is shown to fail. No Zephyr workspace is needed, and
nothing here builds for or runs on a board.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests/zephyr/cli_console_shared_compile"
RUN = FIXTURE / "run.sh"
BOARD = "mimxrt1060_evk@B//qspi"

REQUIRED_CONFIG = (
    "CONFIG_CRUX_CLI_CONSOLE=y",
    "CONFIG_CRUX_CLI_CONSOLE_UART_SHARED=y",
    "CONFIG_CRUX_LOGGING_CONSOLE_BACKEND=y",
    "CONFIG_CRUX_LOGGING=y",
    "CONFIG_CRUX_SERIAL=y",
    "CONFIG_CRUX_CLI_CONSOLE_BAUD_RATE=115200",
    "CONFIG_ENTROPY_MCUX_TRNG=y",
)
FORBIDDEN_CONFIG = (
    "CONFIG_CRUX_CLI_CONSOLE_UART_DEDICATED=y",
    "CONFIG_LOG_BACKEND_UART=y",
    "CONFIG_UART_CONSOLE=y",
    "CONFIG_SHELL=y",
    "CONFIG_TEST_RANDOM_GENERATOR=y",
)
REQUIRED_SYMBOLS = (
    ("T", "crux_cli_serial_start"),
    ("T", "crux_cli_console_run"),
    ("R", "crux_logging_console"),
    ("r", "crux_logging_console_backend"),
    ("T", "crux_log_queue_put"),
)
DTS = ("\taliases {\n\t\tcrux-serial0 = &lpuart1;\n\t};\n",
       "\tchosen {\n\t\tzephyr,console = &lpuart1;\n\t};\n")
# The extra -DCONFIG_ settings of each refusal, and the message that it must stop with.
REFUSALS = {
    "CONFIG_UART_CONSOLE=y": "Crux Serial conflicts with UART Console",
    "CONFIG_UART_CONSOLE=y CONFIG_LOG_BACKEND_UART=y": "requires CONFIG_LOG_BACKEND_UART=n",
    "CONFIG_CRUX_CLI_CONSOLE_BAUD_RATE=9600": "CONFIG_CRUX_CLI_CONSOLE_BAUD_RATE (9600) differs",
}

FAKE_WEST = r'''
import json, os, sys
from pathlib import Path
scenario = json.loads(Path(os.environ["FAKE_SCENARIO"]).read_text())
args = sys.argv[1:]
with open(scenario["calls"], "a") as calls:
    calls.write(json.dumps(args) + "\n")
overrides = " ".join(a[2:] for a in args if a.startswith("-DCONFIG_"))
if overrides:
    answer = scenario["refusals"].get(overrides)
    if answer is None:
        sys.exit(0)
    print(answer)
    sys.exit(1)
build = Path(args[args.index("-d") + 1])
(build / "zephyr").mkdir(parents=True, exist_ok=True)
(build / "zephyr/.config").write_text("".join(line + "\n" for line in scenario["config"]))
(build / "zephyr/zephyr.dts").write_text(scenario["dts"])
(build / "zephyr/zephyr.elf").write_text("".join("60000000 %s %s\n" % tuple(s) for s in scenario["symbols"]))
(build / "CMakeCache.txt").write_text("CMAKE_NM:FILEPATH=%s\n" % scenario["nm"])
'''


def good_scenario():
    return {"config": list(REQUIRED_CONFIG), "dts": "".join(DTS), "symbols": [list(s) for s in REQUIRED_SYMBOLS],
            "refusals": dict(REFUSALS)}


class Runner(unittest.TestCase):
    def run_script(self, scenario, board=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tools = root / "tools"
            tools.mkdir()
            (tools / "west").write_text(f"#!{sys.executable}\n{FAKE_WEST}")
            (tools / "nm").write_text('#!/bin/sh\ncat "$1"\n')
            for tool in tools.iterdir():
                tool.chmod(0o755)
            scenario = dict(scenario, nm=str(tools / "nm"), calls=str(root / "calls"))
            (root / "scenario.json").write_text(json.dumps(scenario))
            env = dict(os.environ, PATH=f"{tools}{os.pathsep}{os.environ['PATH']}",
                       FAKE_SCENARIO=str(root / "scenario.json"), CRUX_WORKSPACE=str(root),
                       CRUX_CONSOLE_SHARED_OUTPUT=str(root / "out"))
            env.pop("CRUX_BOARD_TARGET", None)
            if board:
                env["CRUX_BOARD_TARGET"] = board
            result = subprocess.run(["bash", str(RUN)], env=env, capture_output=True, text=True, timeout=120)
            calls = root / "calls"
            result.calls = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
            return result

    def assert_fails(self, scenario, text):
        result = self.run_script(scenario)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(text, result.stderr)

    def test_a_good_build_passes_with_the_three_refusals(self):
        result = self.run_script(good_scenario())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(result.calls), 1 + len(REFUSALS))
        for call in result.calls:
            self.assertEqual(call[call.index("-b") + 1], BOARD)
            self.assertIn(str(FIXTURE), call)
        self.assertIn("not run on a board", result.stdout)

    def test_the_board_input_is_read_and_another_board_is_refused(self):
        result = self.run_script(good_scenario(), board="mimxrt1170_evk@A/mimxrt1176/cm7")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("is not supported", result.stderr)
        self.assertEqual(result.calls, [])
        result = self.run_script(good_scenario(), board="mimxrt1060_evk@B/mimxrt1062/qspi")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_each_required_configuration_line_is_checked(self):
        for line in REQUIRED_CONFIG:
            with self.subTest(line=line):
                scenario = good_scenario()
                scenario["config"].remove(line)
                self.assert_fails(scenario, line)

    def test_each_forbidden_configuration_line_is_checked(self):
        for line in FORBIDDEN_CONFIG:
            with self.subTest(line=line):
                scenario = good_scenario()
                scenario["config"].append(line)
                self.assert_fails(scenario, line.split("=")[0])

    def test_the_console_uart_is_checked_in_the_devicetree(self):
        for index, name in enumerate(("crux-serial0", "zephyr,console")):
            with self.subTest(name=name):
                scenario = good_scenario()
                scenario["dts"] = "".join(DTS).replace(DTS[index], DTS[index].replace("lpuart1", "lpuart3"))
                self.assert_fails(scenario, name)

    def test_each_linked_symbol_is_checked(self):
        for _, name in REQUIRED_SYMBOLS:
            with self.subTest(symbol=name):
                scenario = good_scenario()
                scenario["symbols"] = [s for s in scenario["symbols"] if s[1] != name]
                self.assert_fails(scenario, name)

    def test_an_undefined_reference_does_not_count(self):
        scenario = good_scenario()
        scenario["symbols"] = [["U", n] if n == "crux_cli_serial_start" else [t, n] for t, n in scenario["symbols"]]
        self.assert_fails(scenario, "crux_cli_serial_start")

    def test_zephyrs_uart_backend_in_the_image_fails(self):
        scenario = good_scenario()
        scenario["symbols"].append(["r", "log_backend_uart"])
        self.assert_fails(scenario, "UART backend")

    def test_an_accepted_refusal_fails(self):
        for overrides in REFUSALS:
            with self.subTest(overrides=overrides):
                scenario = good_scenario()
                del scenario["refusals"][overrides]
                self.assert_fails(scenario, "was accepted")

    def test_a_refusal_for_another_reason_fails(self):
        for overrides in REFUSALS:
            with self.subTest(overrides=overrides):
                scenario = good_scenario()
                scenario["refusals"][overrides] = "some other error"
                self.assert_fails(scenario, "for another reason")


class Fixture(unittest.TestCase):
    def test_the_fixture_selects_the_shared_mode_of_the_native_sim_fixture(self):
        cmake = (FIXTURE / "CMakeLists.txt").read_text()
        self.assertIn("tests/native/cli_console/shared/shared.conf", cmake)
        self.assertRegex(cmake, r"if\(NOT CONFIG_CRUX_CLI_CONSOLE_UART_SHARED\)\s+message\(FATAL_ERROR")
        self.assertIn('STREQUAL "mimxrt1060_evk@B/mimxrt1062/qspi"', cmake)
        self.assertIn("crux_mbedtls_fail_closed_entropy()", cmake)

    def test_crux_serial0_is_the_console_uart(self):
        overlay = (FIXTURE / "app.overlay").read_text()
        self.assertRegex(overlay, r"crux-serial0 = &lpuart1;")
        self.assertNotIn("zephyr,log-uart", re.sub(r"/\*.*?\*/", "", overlay, flags=re.S))

    def test_the_application_starts_the_console_through_public_headers(self):
        source = (FIXTURE / "main.c").read_text()
        self.assertEqual(re.findall(r"#include [<\"]([^>\"]+)", source), ["crux/cli.h", "crux/cli_zephyr.h"])
        self.assertIn("crux_cli_serial_start(", source)

    def test_the_runner_is_valid_shell_and_operates_no_board(self):
        result = subprocess.run(["bash", "-n", str(RUN)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(os.access(RUN, os.X_OK))
        text = RUN.read_text()
        for forbidden in ("west flash", "west debug", "pyocd", "openocd", "JLink"):
            self.assertNotIn(forbidden, text, forbidden)

    def test_ci_runs_it_from_the_rt1060_cross_build_check(self):
        script = (REPO / "scripts/test-management-mbed-rt1060.sh").read_text()
        start = script.index("run_build() {")
        build = script[start:script.index('case "$mode" in static | all)')]
        self.assertIn('"$repo/tests/zephyr/cli_console_shared_compile/run.sh"', build)
        checks = (REPO / "scripts/ci/checks.toml").read_text()
        self.assertIn('run = "scripts/test-management-mbed-rt1060.sh build"', checks)


if __name__ == "__main__":
    unittest.main()
