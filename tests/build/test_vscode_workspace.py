"""Checks for the VS Code workspace files: the six tasks, the two hidden helper tasks, the debug
profiles and their gdb script, the C/C++ extension next to clangd, gdb in the Dev Container and the
build guide that names them.

CMake Tools builds, tests and debugs the Linux Host presets, so no task does. The tasks build,
run, flash and clean native_sim and the board. The tests read the JSON files, run the two clean
tasks and the probe check in a temporary folder, run native_sim: Run with a stub west and program,
and load the gdb script with a stand-in gdb module; they do not start VS Code or gdb, build an
image or touch a board.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

try:
    import yaml
except ImportError:  # pragma: no cover - CI installs PyYAML
    yaml = None

REPO = Path(__file__).resolve().parents[2]
VSCODE = REPO / ".vscode"
DEVCONTAINER = REPO / ".devcontainer"

TASKS = ["Board: Build", "Board: Flash", "Board: Clean",
         "native_sim: Build", "native_sim: Run", "native_sim: Clean"]
DELETED_TASKS = ["Build firmware", "Clean firmware", "Board: Build and flash",
                 "Host: run_hello_crux", "Host: run_time_shell", "Host: run_echo_client"]
# Hidden tasks ("hide": true) run only as a dependency or a preLaunchTask.
HIDDEN_TASKS = ["Board: Check probe", "Board: Check probe and build"]
PROFILES = ["Board: Debug", "Board: Attach", "Board: Attach (external)", "native_sim: Debug"]
NATIVE_SIM_EXE = "${workspaceFolder}/build/native_sim/zephyr/zephyr.exe"
NATIVE_SIM_GDB_SCRIPT = VSCODE / "native_sim_debug.py"
PROBE_MESSAGE = ("No J-Link probe found. Attach it to WSL2: usbipd attach --wsl --busid <BUSID> "
                 "(Getting started, section 7).")
USB_DEVICES = "/sys/bus/usb/devices"
FLASH_COMMAND = "exec west flash -d build/zephyr/${config:crux.boardKey}--current -r jlink"
# The board of the Board tasks and profiles: workspace settings, defaulting to the RT1060-EVKB Rev B.
BOARD_SETTINGS = {"crux.board": "mimxrt1060_evk@B//qspi", "crux.boardKey": "mimxrt1060_evk_B_qspi",
                  "crux.jlinkDevice": "MIMXRT1062xxx6A"}
RT1180_SETTINGS = {"crux.board": "mimxrt1180_evk/mimxrt1189/cm33",
                   "crux.boardKey": "mimxrt1180_evk_mimxrt1189_cm33", "crux.jlinkDevice": "MIMXRT1189xxx8_M33"}
NATIVE_SIM_DATABASE = "build/native_sim"
DEFAULT_DATABASE = "build/clangd"
# GCC options that Zephyr adds to native_sim builds and that clang rejects or ignores.
GCC_ONLY_FLAGS = {"-fno-reorder-functions", "-fno-defer-pop", "--param=min-pagesize=0",
                  "-fno-freestanding", "-fno-printf-return-value"}
CLANGD_USER_CONFIG = "/home/vscode/.config/clangd/config.yaml"
# Dated pages record what was true when they were written; they keep the old names.
DATED = ("docs/evidence/", "docs/history/", "docs/plans/", "docs/superpowers/", "docs/research/",
         "docs/decisions/", "docs/baseline.md")


def load(path):
    return json.loads(path.read_text())


def with_settings(text, settings=None):
    """Replace ${config:Name} as VS Code does, from settings.json unless settings are given."""
    values = settings if settings is not None else load(VSCODE / "settings.json")
    return re.sub(r"\$\{config:([^}]+)\}", lambda match: values[match.group(1)], text)


class TasksTest(unittest.TestCase):
    def setUp(self):
        self.document = load(VSCODE / "tasks.json")
        self.tasks = {t["label"]: t for t in self.document["tasks"]}

    def test_exactly_the_six_tasks_and_two_hidden_helpers(self):
        visible = [t["label"] for t in self.document["tasks"] if not t.get("hide")]
        hidden = [t["label"] for t in self.document["tasks"] if t.get("hide")]
        self.assertEqual(visible, TASKS)
        self.assertEqual(hidden, HIDDEN_TASKS)
        for label in TASKS + ["Board: Check probe"]:
            task = self.tasks[label]
            with self.subTest(task=label):
                self.assertEqual(task["type"], "process")
                self.assertEqual(task["options"]["cwd"], "${workspaceFolder}")

    def run_probe_check(self, root, vendors):
        # Stand-in for /sys/bus/usb/devices: one folder per device with its idVendor file.
        devices = root / "devices"
        devices.mkdir()
        for number, vendor in enumerate(vendors):
            (devices / f"1-{number}").mkdir()
            (devices / f"1-{number}/idVendor").write_text(vendor + "\n")
        task = self.tasks["Board: Check probe"]
        self.assertIn(USB_DEVICES, " ".join(task["args"]))
        arguments = [a.replace(USB_DEVICES, str(devices)) for a in task["args"]]
        return subprocess.run([task["command"], *arguments], cwd=root, capture_output=True, text=True)

    def test_probe_check_fails_with_one_line_when_no_jlink_is_visible(self):
        for vendors in ([], ["1d6b", "0bda"]):
            with self.subTest(vendors=vendors), tempfile.TemporaryDirectory() as temporary:
                result = self.run_probe_check(Path(temporary), vendors)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((result.stdout + result.stderr).splitlines(), [PROBE_MESSAGE])

    def test_probe_check_passes_silently_with_a_jlink(self):
        # SEGGER's USB vendor ID is 1366.
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_probe_check(Path(temporary), ["1d6b", "1366"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout + result.stderr, "")

    def test_board_flash_runs_the_probe_check_and_west_flash_in_one_process(self):
        # VS Code still starts a task when a task in its dependsOn fails, so the check runs inside
        # the Flash command; a failed check ends the process before west flash starts.
        flash = self.tasks["Board: Flash"]
        check = self.tasks["Board: Check probe"]
        self.assertNotIn("dependsOn", flash)
        self.assertEqual(flash["command"], "bash")
        self.assertEqual(flash["args"][0], "-c")
        self.assertEqual(len(flash["args"]), 2)
        self.assertEqual(flash["args"][1], f"{check['args'][1]}; {FLASH_COMMAND}")
        self.assertIn(PROBE_MESSAGE, flash["args"][1])

    def run_flash(self, root, vendors):
        devices = root / "devices"
        devices.mkdir()
        for number, vendor in enumerate(vendors):
            (devices / f"1-{number}").mkdir()
            (devices / f"1-{number}/idVendor").write_text(vendor + "\n")
        stubs = root / "stubs"
        stubs.mkdir()
        log = root / "calls.log"
        (stubs / "west").write_text(f'#!/bin/sh\necho "west $*" >> "{log}"\n')
        (stubs / "west").chmod(0o755)
        task = self.tasks["Board: Flash"]
        arguments = [with_settings(a).replace(USB_DEVICES, str(devices)) for a in task["args"]]
        env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}")
        result = subprocess.run([task["command"], *arguments], cwd=root, capture_output=True, text=True,
                                env=env)
        calls = log.read_text().splitlines() if log.exists() else []
        return result, calls

    def test_board_flash_without_a_probe_prints_one_line_and_does_not_flash(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, calls = self.run_flash(Path(temporary), ["1d6b"])
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((result.stdout + result.stderr).splitlines(), [PROBE_MESSAGE])
            self.assertEqual(calls, [])

    def test_board_flash_with_a_probe_flashes_the_current_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, calls = self.run_flash(Path(temporary), ["1366"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(calls, ["west flash -d build/zephyr/mimxrt1060_evk_B_qspi--current -r jlink"])

    def test_probe_tasks_do_not_echo_the_command_line(self):
        # echo false hides VS Code's "Executing task" line; the task output still shows.
        for label in ("Board: Flash", "Board: Check probe"):
            with self.subTest(task=label):
                presentation = self.tasks[label]["presentation"]
                self.assertIs(presentation["echo"], False)
                self.assertEqual(presentation["reveal"], "always")

    def test_check_probe_and_build_runs_the_check_then_board_build(self):
        task = self.tasks["Board: Check probe and build"]
        self.assertEqual(task["dependsOn"], ["Board: Check probe", "Board: Build"])
        self.assertEqual(task["dependsOrder"], "sequence")
        self.assertNotIn("command", task)

    def test_one_sample_prompt_serves_both_build_tasks(self):
        inputs = self.document["inputs"]
        self.assertEqual([i["id"] for i in inputs], ["sample"])
        self.assertEqual(inputs[0]["type"], "promptString")
        self.assertEqual(inputs[0]["default"], "samples/hello_crux/zephyr")
        used = {label for label, task in self.tasks.items() if "${input:sample}" in json.dumps(task)}
        self.assertEqual(used, {"Board: Build", "native_sim: Build"})
        self.assertEqual(set(re.findall(r"\$\{input:([^}]+)\}", json.dumps(self.document["tasks"]))),
                         {"sample"})

    def run_build_task(self, label, entered, settings=None):
        # Run a build task as VS Code would, in a tree with two samples, with stub west and build script.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for sample in ("samples/hello_crux/zephyr", "samples/time/shell/zephyr"):
                (root / sample).mkdir(parents=True)
                (root / sample / "CMakeLists.txt").write_text("find_package(Zephyr)\n")
            (root / "samples/time/shell/linux").mkdir(parents=True)
            (root / "samples/time/shell/linux/CMakeLists.txt").write_text("project(x)\n")
            log = root / "calls.log"
            stubs = root / "stubs"
            stubs.mkdir()
            (root / "scripts").mkdir()
            for stub, name in ((stubs / "west", "west"), (root / "scripts/build-debug-target.sh", "build-debug-target.sh")):
                stub.write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\n')
                stub.chmod(0o755)
            task = self.tasks[label]
            arguments = [with_settings(a, settings).replace("${workspaceFolder}", str(root))
                         .replace("${input:sample}", entered) for a in task["args"]]
            env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}")
            result = subprocess.run([task["command"], *arguments], cwd=root, capture_output=True, text=True,
                                    env=env)
            calls = log.read_text().splitlines() if log.exists() else []
            return result, calls

    def test_build_tasks_accept_a_sample_folder_or_its_zephyr_folder(self):
        expected = {"native_sim: Build": "west build -p auto -b native_sim/native/64 -d build/native_sim "
                                         "{app} -- -DCONFIG_NO_OPTIMIZATIONS=y",
                    "Board: Build": "build-debug-target.sh mimxrt1060_evk@B//qspi --app {app}"}
        for label, call in expected.items():
            for entered in ("samples/time/shell", "samples/time/shell/", "samples/time/shell/zephyr",
                            "samples/time/shell/zephyr/"):
                with self.subTest(task=label, entered=entered):
                    result, calls = self.run_build_task(label, entered)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    app = entered.rstrip("/")
                    app = app if app.endswith("/zephyr") else app + "/zephyr"
                    self.assertEqual(calls, [call.format(app=app)])

    def test_build_tasks_refuse_a_folder_without_a_zephyr_application(self):
        for label in ("native_sim: Build", "Board: Build"):
            for entered in ("samples/missing", "samples/time", "samples/time/shell/linux/src"):
                with self.subTest(task=label, entered=entered):
                    result, calls = self.run_build_task(label, entered)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual((result.stdout + result.stderr).splitlines(),
                                     [f"No Zephyr application at {entered}; enter samples/<name>/zephyr."])
                    self.assertEqual(calls, [])

    def test_board_build_takes_the_board_from_the_settings(self):
        # A qualified target with a core, as the dual-core MIMXRT1180-EVK needs.
        result, calls = self.run_build_task("Board: Build", "samples/hello_crux/zephyr", RT1180_SETTINGS)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["build-debug-target.sh mimxrt1180_evk/mimxrt1189/cm33 --app "
                                 "samples/hello_crux/zephyr"])

    def test_board_build_refuses_a_board_key_that_does_not_match_the_board(self):
        # The profiles and Board: Clean find the build through crux.boardKey, so a stale key would
        # debug or delete another board's build.
        for key in ("mimxrt1060_evk_B_qspi", ""):
            with self.subTest(key=key):
                settings = dict(RT1180_SETTINGS, **{"crux.boardKey": key})
                result, calls = self.run_build_task("Board: Build", "samples/hello_crux/zephyr", settings)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((result.stdout + result.stderr).splitlines(),
                                 ["Set crux.boardKey to mimxrt1180_evk_mimxrt1189_cm33 in .vscode/settings.json."])
                self.assertEqual(calls, [])

    def test_native_sim_build_reuses_one_build_folder(self):
        # -p auto makes the folder pristine when the sample or the board differs from the cached one
        # (Zephyr scripts/west_commands/build.py, _sanity_check).
        # CONFIG_NO_OPTIMIZATIONS builds with -O0, which Zephyr's native_sim documentation recommends
        # for debugging; the board tasks keep Zephyr's default size optimization.
        result, calls = self.run_build_task("native_sim: Build", "samples/hello_crux/zephyr")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["west build -p auto -b native_sim/native/64 -d build/native_sim "
                                 "samples/hello_crux/zephyr -- -DCONFIG_NO_OPTIMIZATIONS=y"])
        for label in ("Board: Build", "Board: Flash"):
            with self.subTest(task=label):
                self.assertNotIn("OPTIMIZATIONS", json.dumps(self.tasks[label]))

    def test_native_sim_run_uses_the_build_folder_of_native_sim_build(self):
        task = self.tasks["native_sim: Run"]
        self.assertNotIn("${input:", json.dumps(task))
        build = self.tasks["native_sim: Build"]["args"][1].split()
        folder = build[build.index("-d") + 1]
        self.assertEqual(NATIVE_SIM_EXE, f"${{workspaceFolder}}/{folder}/zephyr/zephyr.exe")
        self.assertIn(folder, " ".join(task["args"]))

    def run_native_sim_run(self, root, west_exit=0, uart=False):
        # Stub west and zephyr.exe that log their arguments, then run the task as VS Code would.
        stubs = root / "stubs"
        stubs.mkdir()
        log = root / "calls.log"
        west = stubs / "west"
        west.write_text(f'#!/bin/sh\necho "west $*" >> "{log}"\nexit {west_exit}\n')
        west.chmod(0o755)
        exe = root / "build/native_sim/zephyr/zephyr.exe"
        exe.parent.mkdir(parents=True, exist_ok=True)
        help_line = "  [-uart_stdinout] : Attach the UART to stdin and stdout" if uart else "  [-stop_at=<time>]"
        exe.write_text(f'#!/bin/sh\necho "zephyr.exe $*" >> "{log}"\n'
                       f'if [ "$1" = -h ]; then echo "{help_line}"; fi\n')
        exe.chmod(0o755)
        task = self.tasks["native_sim: Run"]
        arguments = [a.replace("${workspaceFolder}", str(root)) for a in task["args"]]
        command = task["command"].replace("${workspaceFolder}", str(root))
        env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}")
        result = subprocess.run([command, *arguments], cwd=root, capture_output=True, text=True, env=env)
        calls = [line.rstrip() for line in log.read_text().splitlines()] if log.exists() else []
        return result, calls

    def test_native_sim_run_rebuilds_the_configured_sample_then_runs_it(self):
        # west build with only -d reuses the build folder and takes the source directory from its CMake
        # cache (Zephyr scripts/west_commands/build.py, _find_source_dir; docs: west build, "If west build
        # finds an existing build directory, the application is incrementally re-compiled there").
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "build/native_sim").mkdir(parents=True)
            (root / "build/native_sim/CMakeCache.txt").write_text("APP_DIR:PATH=/x/samples/hello_crux/zephyr\n")
            result, calls = self.run_native_sim_run(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            # -p never: a user's "west config build.pristine always" must not wipe the configured sample.
            self.assertEqual(calls, ["west build -p never -d build/native_sim", "zephyr.exe -h", "zephyr.exe"])

    def test_native_sim_run_passes_uart_stdinout_only_when_the_program_lists_it(self):
        # Only a build with a PTY UART (a console or shell sample) accepts -uart_stdinout; others
        # reject it as an incorrect option.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "build/native_sim").mkdir(parents=True)
            (root / "build/native_sim/CMakeCache.txt").write_text("APP_DIR:PATH=/x/samples/time/shell/zephyr\n")
            result, calls = self.run_native_sim_run(root, uart=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(calls, ["west build -p never -d build/native_sim", "zephyr.exe -h",
                                     "zephyr.exe -uart_stdinout"])

    def test_native_sim_run_does_not_start_the_program_when_the_build_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "build/native_sim").mkdir(parents=True)
            (root / "build/native_sim/CMakeCache.txt").write_text("APP_DIR:PATH=/x/samples/hello_crux/zephyr\n")
            result, calls = self.run_native_sim_run(root, west_exit=1)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(calls, ["west build -p never -d build/native_sim"])

    def test_native_sim_run_without_a_configured_build_asks_for_native_sim_build(self):
        # Without a CMake cache, west build would take the current directory as the source directory.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result, calls = self.run_native_sim_run(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Run native_sim: Build first.", result.stdout + result.stderr)
            self.assertEqual(calls, [])

    def run_clean(self, label, root):
        task = self.tasks[label]
        arguments = [with_settings(a).replace("${workspaceFolder}", str(root)) for a in task["args"]]
        result = subprocess.run([task["command"], *arguments], cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def make_build_tree(self, root):
        zephyr = root / "build/zephyr"
        for name in ("mimxrt1060_evk_B_qspi", "mimxrt1060_evk_B_qspi--samples_hello_crux_zephyr",
                     "mimxrt1060_evk_B_qspi--samples_hello_crux_zephyr--og", "networking-evkb",
                     "mimxrt1060_evk_B_qspi_other"):
            (zephyr / name / "zephyr").mkdir(parents=True)
            (zephyr / name / "zephyr/zephyr.elf").write_text("elf")
        (zephyr / "mimxrt1060_evk_B_qspi--current").symlink_to("mimxrt1060_evk_B_qspi--samples_hello_crux_zephyr")
        for name in ("native_sim/zephyr", "linux/debug", "hello_crux_evkb"):
            (root / "build" / name).mkdir(parents=True)

    def test_board_clean_removes_only_the_board_debug_builds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_build_tree(root)
            self.run_clean("Board: Clean", root)
            zephyr = root / "build/zephyr"
            self.assertEqual(sorted(p.name for p in zephyr.iterdir()),
                             ["mimxrt1060_evk_B_qspi_other", "networking-evkb"])
            self.assertFalse((zephyr / "mimxrt1060_evk_B_qspi--current").is_symlink())
            for name in ("native_sim/zephyr", "linux/debug", "hello_crux_evkb"):
                self.assertTrue((root / "build" / name).is_dir(), name)
            # Nothing left to clean is not an error.
            self.run_clean("Board: Clean", root)

    def test_board_clean_without_a_board_key_removes_nothing(self):
        task = self.tasks["Board: Clean"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_build_tree(root)
            before = sorted(p.name for p in (root / "build/zephyr").iterdir())
            arguments = [with_settings(a, dict(BOARD_SETTINGS, **{"crux.boardKey": ""}))
                         for a in task["args"]]
            result = subprocess.run([task["command"], *arguments], cwd=root, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((result.stdout + result.stderr).splitlines(),
                             ["Set crux.boardKey in .vscode/settings.json."])
            self.assertEqual(sorted(p.name for p in (root / "build/zephyr").iterdir()), before)

    def test_board_clean_refuses_a_key_that_leaves_its_build_directory(self):
        task = self.tasks["Board: Clean"]
        for key in (".", "..", "../linux", "a/b", ".hidden"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.make_build_tree(root)
                before = sorted(str(p.relative_to(root)) for p in (root / "build").rglob("*"))
                arguments = [with_settings(a, dict(BOARD_SETTINGS, **{"crux.boardKey": key}))
                             for a in task["args"]]
                result = subprocess.run([task["command"], *arguments], cwd=root, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((result.stdout + result.stderr).splitlines(),
                                 ["Set crux.boardKey in .vscode/settings.json."])
                self.assertEqual(sorted(str(p.relative_to(root)) for p in (root / "build").rglob("*")), before)

    def test_native_sim_clean_removes_only_its_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_build_tree(root)
            self.run_clean("native_sim: Clean", root)
            self.assertFalse((root / "build/native_sim").exists())
            self.assertEqual(len(list((root / "build/zephyr").iterdir())), 6)
            self.assertTrue((root / "build/linux/debug").is_dir())
            self.run_clean("native_sim: Clean", root)


class LaunchTest(unittest.TestCase):
    def setUp(self):
        self.launch = {c["name"]: c for c in load(VSCODE / "launch.json")["configurations"]}
        self.tasks = {t["label"] for t in load(VSCODE / "tasks.json")["tasks"]}

    def test_the_four_profiles(self):
        self.assertEqual(list(self.launch), PROFILES)

    def test_every_pre_launch_task_exists(self):
        for name, profile in self.launch.items():
            if "preLaunchTask" in profile:
                with self.subTest(profile=name):
                    self.assertIn(profile["preLaunchTask"], self.tasks)

    def test_native_sim_profile_debugs_the_native_sim_build_with_gdb(self):
        profile = self.launch["native_sim: Debug"]
        self.assertEqual(profile["type"], "cppdbg")
        self.assertEqual(profile["request"], "launch")
        self.assertEqual(profile["program"], NATIVE_SIM_EXE)
        # The gdb script sets -uart_stdinout when the program accepts it.
        self.assertNotIn("args", profile)
        self.assertEqual(profile["MIMode"], "gdb")
        self.assertEqual(profile["miDebuggerPath"], "/usr/bin/gdb")
        self.assertEqual(profile["preLaunchTask"], "native_sim: Build")
        # On Linux, false runs the program in the integrated terminal, where the shell takes input
        # (https://code.visualstudio.com/docs/cpp/launch-json-reference, externalConsole).
        self.assertIs(profile["externalConsole"], False)

    def test_native_sim_profile_sources_the_checked_in_gdb_script(self):
        profile = self.launch["native_sim: Debug"]
        texts = [entry["text"] for entry in profile["setupCommands"]]
        self.assertIn("source ${workspaceFolder}/.vscode/native_sim_debug.py", texts)
        self.assertTrue(NATIVE_SIM_GDB_SCRIPT.is_file())
        # The script places the stop at the application main; stopping at entry would stop elsewhere.
        self.assertIs(profile["stopAtEntry"], False)
        # The script's breakpoint is unknown to the C/C++ extension; "stop" reports it as a plain stop
        # instead of "Exception has occurred" (cpptools package.json, unknownBreakpointHandling).
        self.assertEqual(profile["unknownBreakpointHandling"], "stop")

    def test_board_profiles_check_the_probe_before_they_start(self):
        self.assertEqual(self.launch["Board: Debug"]["preLaunchTask"], "Board: Check probe and build")
        self.assertEqual(self.launch["Board: Attach"]["preLaunchTask"], "Board: Check probe")
        # The external GDB Server runs on the host, which owns the probe there.
        self.assertNotIn("preLaunchTask", self.launch["Board: Attach (external)"])


class FakeGdb:
    """The parts of gdb's Python API that the native_sim gdb script uses."""

    def __init__(self, program, sals):
        self.program = program
        self.sals = sals
        self.handlers = []
        self.breakpoints = []
        self.commands = []
        module = types.ModuleType("gdb")
        module.events = types.SimpleNamespace(new_objfile=types.SimpleNamespace(
            connect=self.handlers.append, disconnect=self.handlers.remove))
        module.current_progspace = lambda: types.SimpleNamespace(filename=self.loaded)
        module.decode_line = lambda spec: (None, tuple(self.sals)) if spec == "main" else (None, None)
        module.execute = lambda command, *args, **kwargs: self.commands.append(command)
        module.write = lambda text, *args, **kwargs: None
        module.error = RuntimeError

        def breakpoint(*args, **kwargs):
            self.breakpoints.append((args, kwargs))
        module.Breakpoint = breakpoint
        self.module = module
        self.loaded = None

    def load_script(self):
        previous = sys.modules.get("gdb")
        sys.modules["gdb"] = self.module
        try:
            spec = importlib.util.spec_from_file_location("native_sim_debug", NATIVE_SIM_GDB_SCRIPT)
            spec.loader.exec_module(importlib.util.module_from_spec(spec))
        finally:
            if previous is None:
                del sys.modules["gdb"]
            else:
                sys.modules["gdb"] = previous

    def load_program(self):
        self.loaded = self.program
        for handler in list(self.handlers):
            handler(types.SimpleNamespace(new_objfile=types.SimpleNamespace(filename=self.program)))


def sal(path):
    symtab = types.SimpleNamespace(filename=path, fullname=lambda: path)
    return types.SimpleNamespace(symtab=symtab, line=10)


class NativeSimGdbScriptTest(unittest.TestCase):
    RUNNER = "/workspace/zephyr/scripts/native_simulator/common/src/main.c"
    APP = "/workspace/crux/samples/time/shell/zephyr/src/main.c"

    def program(self, root, uart):
        exe = root / "zephyr.exe"
        line = "  [-uart_stdinout] : Attach the UART to stdin and stdout" if uart else "  [-stop_at=<time>]"
        exe.write_text(f'#!/bin/sh\n[ "$1" = -h ] && echo "{line}"\nexit 0\n')
        exe.chmod(0o755)
        return str(exe)

    def run_script(self, uart, sals=None):
        with tempfile.TemporaryDirectory() as temporary:
            gdb = FakeGdb(self.program(Path(temporary), uart), sals or [sal(self.RUNNER), sal(self.APP)])
            gdb.load_script()
            gdb.load_program()
            return gdb

    def test_breaks_once_at_the_application_main_not_the_runner_main(self):
        # zephyr.exe has two functions named main; a plain "tbreak main" stops in the runner's.
        gdb = self.run_script(uart=False)
        self.assertEqual(len(gdb.breakpoints), 1)
        args, kwargs = gdb.breakpoints[0]
        self.assertEqual(kwargs.get("source"), self.APP)
        self.assertEqual(kwargs.get("function"), "main")
        self.assertIs(kwargs.get("temporary"), True)

    def test_sets_uart_stdinout_only_when_the_program_lists_it(self):
        self.assertIn("set args -uart_stdinout", self.run_script(uart=True).commands)
        self.assertNotIn("set args -uart_stdinout", self.run_script(uart=False).commands)

    def test_without_an_application_main_it_sets_no_breakpoint(self):
        self.assertEqual(self.run_script(uart=False, sals=[sal(self.RUNNER)]).breakpoints, [])


class ContainerTest(unittest.TestCase):
    def test_dockerfile_installs_gdb(self):
        text = (DEVCONTAINER / "Dockerfile").read_text()
        install = text[text.index("apt-get install"):text.index("rm -rf /var/lib/apt/lists/*")]
        self.assertRegex(install, r"(?m)^\s+gdb \\$")

    def test_c_cpp_extension_debugs_and_clangd_keeps_intellisense(self):
        extensions = load(DEVCONTAINER / "devcontainer.json")["customizations"]["vscode"]["extensions"]
        self.assertIn("ms-vscode.cpptools", extensions)
        self.assertIn("ms-vscode.cmake-tools", extensions)
        self.assertIn("llvm-vs-code-extensions.vscode-clangd", extensions)
        # The clangd extension warns while cpptools IntelliSense is on and offers this setting.
        self.assertEqual(load(VSCODE / "settings.json")["C_Cpp.intelliSenseEngine"], "disabled")

    def test_board_settings_default_to_the_rt1060_evkb(self):
        settings = load(VSCODE / "settings.json")
        self.assertEqual({key: settings[key] for key in BOARD_SETTINGS}, BOARD_SETTINGS)
        # The key is the board target as scripts/build-debug-target.sh names its build folder.
        self.assertEqual(re.sub(r"[^A-Za-z0-9_.-]+", "_", settings["crux.board"]), settings["crux.boardKey"])

    def test_board_tasks_and_profiles_name_no_board_of_their_own(self):
        tasks = json.dumps([t for t in load(VSCODE / "tasks.json")["tasks"] if t["label"].startswith("Board:")])
        profiles = json.dumps([c for c in load(VSCODE / "launch.json")["configurations"]
                               if c["name"].startswith("Board:")])
        for text in (tasks, profiles):
            self.assertNotRegex(text, r"mimxrt1060|MIMXRT1062")
            self.assertTrue(set(re.findall(r"\$\{config:([^}]+)\}", text)) <= set(BOARD_SETTINGS))

    def test_cmake_tools_debug_stops_at_main(self):
        # cmake.debugConfig passes cppdbg attributes to the CMake Tools Debug command.
        self.assertEqual(load(VSCODE / "settings.json")["cmake.debugConfig"], {"stopAtEntry": True})


@unittest.skipUnless(yaml, "PyYAML is required to parse .clangd")
class ClangdTest(unittest.TestCase):
    """Zephyr sources use the native_sim database, the others build/clangd (https://clangd.llvm.org/config)."""

    # Files that the Host build compiles although they sit in a Zephyr-looking folder
    # (root CMakeLists.txt, tests/{gpio,i2c,spi,networking,bench_first_account,time/busy_wait}).
    HOST_BUILT = ["samples/time/shell/common/time_command.c", "samples/time/shell/linux/main.c",
                  "samples/hello_crux/linux/main.c", "samples/networking/echo_client/common/client.c",
                  "components/gpio/ports/zephyr/gpio_status.c", "components/i2c/ports/zephyr/i2c_status.c",
                  "components/spi/ports/zephyr/spi_status.c", "components/time/ports/zephyr/busy_wait_zephyr.c",
                  "tests/time/busy_wait/zephyr_shim/zephyr/kernel.h",
                  "tests/zephyr/management_rt1060_compile/first_account/bench_first_account_provision.c",
                  "tests/execution/src/posix.c"]
    OTHER = ["components/time/src/busy_wait.c", "components/time/ports/linux/time_clock_linux.c",
             "tests/time/busy_wait/zephyr_port_test.c", "tests/gpio/status_test.c"]
    WEST_ONLY = ["components/time/ports/zephyr/time_clock_zephyr.c", "tests/execution/src/native.c", "zephyr/psa_threading/crux_tf_psa_threading.c",
                 "tests/zephyr/management_rt1060_compile/report/bench_report_core.c"]

    def setUp(self):
        self.fragments = list(yaml.safe_load_all((REPO / ".clangd").read_text()))

    def test_fragments_use_only_documented_keys(self):
        self.assertTrue(self.fragments)
        unconditional = []
        for fragment in self.fragments:
            self.assertLessEqual(set(fragment), {"If", "CompileFlags"})
            if "If" in fragment:
                self.assertEqual(set(fragment["CompileFlags"]), {"CompilationDatabase"})
            else:
                unconditional.append(fragment)
            for key, value in fragment.get("If", {}).items():
                self.assertIn(key, {"PathMatch", "PathExclude"})
                self.assertIsInstance(value, list)
                for pattern in value:
                    re.compile(pattern)
        # One fragment without a condition only removes flags, so it applies to every file.
        self.assertEqual(len(unconditional), 1)
        self.assertEqual(set(unconditional[0]["CompileFlags"]), {"Remove"})

    def matching(self, path):
        # Conditions are ANDed, the values of one condition ORed, and each regex must match the whole
        # path relative to the .clangd folder.
        for fragment in self.fragments:
            condition = fragment.get("If", {})
            if "PathMatch" in condition and not any(re.fullmatch(p, path) for p in condition["PathMatch"]):
                continue
            if any(re.fullmatch(p, path) for p in condition.get("PathExclude", [])):
                continue
            yield fragment

    def databases(self, path):
        return {fragment["CompileFlags"]["CompilationDatabase"] for fragment in self.matching(path)
                if "CompilationDatabase" in fragment["CompileFlags"]}

    def removed(self, path):
        return {flag for fragment in self.matching(path) for flag in fragment["CompileFlags"].get("Remove", [])}

    def repository_remove_list(self):
        return next(f for f in self.fragments if "If" not in f)["CompileFlags"]["Remove"]

    def container_remove_list(self):
        # The Dockerfile writes the clangd user config with printf, one quoted argument per line.
        dockerfile = (DEVCONTAINER / "Dockerfile").read_text()
        step = next(s for s in dockerfile.split("\nRUN ")[1:] if CLANGD_USER_CONFIG in s)
        printf = step[step.index("printf '%s\\n'"):step.index(f"> {CLANGD_USER_CONFIG}")]
        lines = shlex.split(printf.replace("\\\n", " "))[2:]
        return yaml.safe_load("\n".join(lines))["CompileFlags"]["Remove"]

    def test_gcc_only_flags_are_removed(self):
        for path in self.WEST_ONLY + self.HOST_BUILT + ["samples/hello_crux/zephyr/src/main.c"]:
            with self.subTest(path=path):
                self.assertLessEqual(GCC_ONLY_FLAGS, self.removed(path))
        self.assertEqual(set(self.repository_remove_list()), GCC_ONLY_FLAGS)

    def test_container_user_config_removes_the_same_flags(self):
        # Zephyr headers sit outside the repository, where only the clangd user config applies.
        self.assertEqual(self.container_remove_list(), self.repository_remove_list())
        dockerfile = (DEVCONTAINER / "Dockerfile").read_text()
        self.assertIn(f"chown -R vscode:vscode /home/vscode/.config", dockerfile)

    @unittest.skipUnless(shutil.which("clangd") and (REPO / "build/native_sim/compile_commands.json").is_file(),
                         "needs clangd and a native_sim: Build")
    def test_clangd_accepts_a_native_sim_source(self):
        result = subprocess.run(["clangd", "--check=samples/hello_crux/zephyr/src/main.c"], cwd=REPO,
                                capture_output=True, text=True, timeout=300)
        output = result.stdout + result.stderr
        self.assertNotIn("Unknown argument", output)
        self.assertNotIn("drv_unknown_argument", output)

    def west_app_sources(self):
        # A folder with prj.conf is a west application root; the Host build compiles none of its
        # files except the HOST_BUILT ones.
        # Its host/ subfolders are Host builds.
        sources = set()
        for conf in list(REPO.glob("samples/**/prj.conf")) + list(REPO.glob("tests/**/prj.conf")):
            for source in conf.parent.rglob("*.c"):
                path = source.relative_to(REPO)
                if "host" not in path.parts:
                    sources.add(path.as_posix())
        return sorted(sources - set(self.HOST_BUILT))

    def test_listed_files_exist(self):
        for path in self.HOST_BUILT + self.OTHER + self.WEST_ONLY:
            with self.subTest(path=path):
                self.assertTrue((REPO / path).is_file())

    def test_west_application_sources_use_the_native_sim_database(self):
        sources = self.west_app_sources()
        self.assertGreater(len(sources), 100)
        for path in sources + self.WEST_ONLY:
            with self.subTest(path=path):
                self.assertEqual(self.databases(path), {NATIVE_SIM_DATABASE})

    def test_host_built_sources_use_build_clangd(self):
        for path in self.HOST_BUILT + self.OTHER:
            with self.subTest(path=path):
                self.assertEqual(self.databases(path), {DEFAULT_DATABASE})


class PresetNamesTest(unittest.TestCase):
    def test_display_names_use_ide_wording_without_a_language_standard(self):
        presets = {p["name"]: p for p in load(REPO / "CMakePresets.json")["configurePresets"]}
        self.assertEqual(presets["host-debug"]["displayName"], "Host Debug")
        self.assertEqual(presets["host-sanitize"]["displayName"], "Host Debug (ASan, UBSan)")
        for preset in presets.values():
            text = preset["displayName"] + preset.get("description", "")
            self.assertNotRegex(text, r"C\+\+\d\d|C\d\d")


class DocsTest(unittest.TestCase):
    def test_board_page_binds_only_a_device_that_is_not_shared(self):
        board = (REPO / "docs/boards/mimxrt1060_evkb.md").read_text()
        self.assertNotIn("then `usbipd bind --busid <BUSID>` (administrator, once per device)", board)
        self.assertIn("`Not shared`", board)

    def test_tutorial_troubleshooting_names_the_board_tool_symptoms(self):
        tutorial = (REPO / "docs/tutorial.md").read_text()
        section = tutorial[tutorial.index("\n## Troubleshooting\n"):]
        section = section[:section.index("\n## ", 1)]
        for symptom in ("JLinkExe not found", "spawn JLinkGDBServer ENOENT", "scripts/bootstrap.sh status",
                        "GDB Server Quit Unexpectedly", "No J-Link probe found", "lsusb -d 1366:",
                        "Attached"):
            self.assertIn(symptom, section)

    def test_build_guide_names_every_task_profile_and_preset(self):
        guide = (REPO / "docs/build.md").read_text()
        section = guide[guide.index("\n## VS Code\n"):]
        section = section[:section.index("\n## ", 1)]
        for name in TASKS + PROFILES + ["host-debug", "host-sanitize", "CMake Tools", "Testing"]:
            self.assertIn(name, section)

    def test_build_guide_describes_host_debug_and_optimization(self):
        guide = (REPO / "docs/build.md").read_text()
        section = guide[guide.index("\n## VS Code\n"):]
        section = section[:section.index("\n## ", 1)]
        for text in ("CMake: Set Launch/Debug Target", "cmake.debugConfig", "-O0", "-Os", "CONFIG_NO_OPTIMIZATIONS",
                     "unknownBreakpointHandling", "build/native_sim/compile_commands.json"):
            self.assertIn(text, section)
        self.assertNotIn("status bar", section)
        self.assertNotIn("CMake: Set Debug Target", section)

    def test_build_guide_gives_the_linux_host_steps_with_cmake_tools_command_names(self):
        # Command titles from the CMake Tools package.json and package.nls.json (category "CMake").
        guide = (REPO / "docs/build.md").read_text()
        section = guide[guide.index("\n### Linux Host in VS Code\n"):]
        section = section[:section.index("\n## ", 1)]
        # A new workspace shows the other CMake commands only after its first configure.
        self.assertLess(section.index("CMake: Configure"), section.index("CMake: Select Build Preset"))
        for text in ("CMake: Select Build Preset", "CMake: Select Test Preset",
                     "**Host Debug**", "CMake: Configure", "CMake: Build", "CMake: Run Tests",
                     "CMake/Build", "Testing", "run_time_shell", "run_echo_client",
                     "CMake: Run Without Debugging", "crux-time-host"):
            self.assertIn(text, section)
        self.assertNotIn("Project Status", section)
        tutorial = (REPO / "docs/tutorial.md").read_text()
        self.assertIn("(build.md#linux-host-in-vs-code)", tutorial)
        self.assertNotIn("CMake: Select Configure Preset", tutorial)

    def test_board_route_fixes_a_stale_probe_after_reattaching(self):
        page = (REPO / "docs/board-jlink-usbipd.md").read_text()
        section = page[page.index("\n## If a step fails\n"):]
        section = section[:section.index("\n## ", 1)]
        for text in ("lsusb -d 1366:", "usbipd detach --busid <BUSID>", "wsl --shutdown",
                     "usbipd attach --wsl --busid <BUSID>"):
            self.assertIn(text, section)
        tutorial = (REPO / "docs/tutorial.md").read_text()
        self.assertIn("(board-jlink-usbipd.md#if-a-step-fails)", tutorial)

    def test_no_current_page_names_a_deleted_task(self):
        pages = [p for p in REPO.rglob("*.md")
                 if p.relative_to(REPO).parts[0] not in {"build", ".git"}
                 and "node_modules" not in p.relative_to(REPO).parts
                 and not p.relative_to(REPO).as_posix().startswith(DATED)]
        self.assertTrue(pages)
        for page in pages:
            text = page.read_text()
            for label in DELETED_TASKS:
                with self.subTest(page=page.relative_to(REPO).as_posix(), task=label):
                    self.assertNotIn(label, text)


if __name__ == "__main__":
    unittest.main()
