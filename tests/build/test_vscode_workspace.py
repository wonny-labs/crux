"""Checks for the VS Code workspace files: the six tasks, the debug profiles, the C/C++ extension
next to clangd, gdb in the Dev Container and the build guide that names them.

CMake Tools builds, tests and debugs the Linux Host presets, so no task does. The tasks build,
run, flash and clean native_sim and the board. The tests read the JSON files, run the two clean
tasks in a temporary folder and run native_sim: Run with a stub west and program; they do not
start VS Code, build an image or touch a board.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
VSCODE = REPO / ".vscode"
DEVCONTAINER = REPO / ".devcontainer"

TASKS = ["Board: Build", "Board: Flash", "Board: Clean",
         "native_sim: Build", "native_sim: Run", "native_sim: Clean"]
DELETED_TASKS = ["Build firmware", "Clean firmware", "Board: Build and flash",
                 "Host: run_hello_crux", "Host: run_time_shell", "Host: run_echo_client"]
PROFILES = ["Board: Debug", "Board: Attach", "Board: Attach (external)", "native_sim: Debug"]
NATIVE_SIM_EXE = "${workspaceFolder}/build/native_sim/zephyr/zephyr.exe"
# Dated pages record what was true when they were written; they keep the old names.
DATED = ("docs/evidence/", "docs/history/", "docs/plans/", "docs/superpowers/", "docs/research/",
         "docs/decisions/", "docs/baseline.md")


def load(path):
    return json.loads(path.read_text())


class TasksTest(unittest.TestCase):
    def setUp(self):
        self.document = load(VSCODE / "tasks.json")
        self.tasks = {t["label"]: t for t in self.document["tasks"]}

    def test_exactly_the_six_tasks(self):
        self.assertEqual([t["label"] for t in self.document["tasks"]], TASKS)
        for task in self.tasks.values():
            with self.subTest(task=task["label"]):
                self.assertEqual(task["type"], "process")
                self.assertEqual(task["options"]["cwd"], "${workspaceFolder}")

    def test_one_sample_prompt_serves_both_build_tasks(self):
        inputs = self.document["inputs"]
        self.assertEqual([i["id"] for i in inputs], ["sample"])
        self.assertEqual(inputs[0]["type"], "promptString")
        self.assertEqual(inputs[0]["default"], "samples/hello_crux")
        used = {label for label, task in self.tasks.items() if "${input:sample}" in json.dumps(task)}
        self.assertEqual(used, {"Board: Build", "native_sim: Build"})
        self.assertEqual(set(re.findall(r"\$\{input:([^}]+)\}", json.dumps(self.document["tasks"]))),
                         {"sample"})

    def test_native_sim_build_reuses_one_build_folder(self):
        # -p auto makes the folder pristine when the sample or the board differs from the cached one
        # (Zephyr scripts/west_commands/build.py, _sanity_check).
        task = self.tasks["native_sim: Build"]
        self.assertEqual(task["command"], "west")
        self.assertEqual(task["args"], ["build", "-p", "auto", "-b", "native_sim/native/64",
                                        "-d", "build/native_sim", "${input:sample}"])

    def test_native_sim_run_uses_the_build_folder_of_native_sim_build(self):
        task = self.tasks["native_sim: Run"]
        self.assertNotIn("${input:", json.dumps(task))
        build = self.tasks["native_sim: Build"]["args"]
        folder = build[build.index("-d") + 1]
        self.assertEqual(NATIVE_SIM_EXE, f"${{workspaceFolder}}/{folder}/zephyr/zephyr.exe")
        self.assertIn(folder, " ".join(task["args"]))

    def run_native_sim_run(self, root, west_exit=0):
        # Stub west and zephyr.exe that log their arguments, then run the task as VS Code would.
        stubs = root / "stubs"
        stubs.mkdir()
        log = root / "calls.log"
        west = stubs / "west"
        west.write_text(f'#!/bin/sh\necho "west $*" >> "{log}"\nexit {west_exit}\n')
        west.chmod(0o755)
        exe = root / "build/native_sim/zephyr/zephyr.exe"
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_text(f'#!/bin/sh\necho "zephyr.exe $*" >> "{log}"\n')
        exe.chmod(0o755)
        task = self.tasks["native_sim: Run"]
        arguments = [a.replace("${workspaceFolder}", str(root)) for a in task["args"]]
        command = task["command"].replace("${workspaceFolder}", str(root))
        env = dict(os.environ, PATH=f"{stubs}:{os.environ['PATH']}")
        result = subprocess.run([command, *arguments], cwd=root, capture_output=True, text=True, env=env)
        calls = log.read_text().splitlines() if log.exists() else []
        return result, calls

    def test_native_sim_run_rebuilds_the_configured_sample_then_runs_it(self):
        # west build with only -d reuses the build folder and takes the source directory from its CMake
        # cache (Zephyr scripts/west_commands/build.py, _find_source_dir; docs: west build, "If west build
        # finds an existing build directory, the application is incrementally re-compiled there").
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "build/native_sim").mkdir(parents=True)
            (root / "build/native_sim/CMakeCache.txt").write_text("APP_DIR:PATH=/x/samples/hello_crux\n")
            result, calls = self.run_native_sim_run(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(calls, ["west build -d build/native_sim", "zephyr.exe -uart_stdinout"])

    def test_native_sim_run_does_not_start_the_program_when_the_build_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "build/native_sim").mkdir(parents=True)
            (root / "build/native_sim/CMakeCache.txt").write_text("APP_DIR:PATH=/x/samples/hello_crux\n")
            result, calls = self.run_native_sim_run(root, west_exit=1)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(calls, ["west build -d build/native_sim"])

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
        arguments = [a.replace("${workspaceFolder}", str(root)) for a in task["args"]]
        result = subprocess.run([task["command"], *arguments], cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def make_build_tree(self, root):
        zephyr = root / "build/zephyr"
        for name in ("mimxrt1060_evk_B_qspi", "mimxrt1060_evk_B_qspi--samples_hello_crux",
                     "mimxrt1060_evk_B_qspi--samples_hello_crux--og", "networking-evkb",
                     "mimxrt1060_evk_B_qspi_other"):
            (zephyr / name / "zephyr").mkdir(parents=True)
            (zephyr / name / "zephyr/zephyr.elf").write_text("elf")
        (zephyr / "mimxrt1060_evk_B_qspi--current").symlink_to("mimxrt1060_evk_B_qspi--samples_hello_crux")
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
        self.assertEqual(profile["args"], ["-uart_stdinout"])
        self.assertEqual(profile["MIMode"], "gdb")
        self.assertEqual(profile["miDebuggerPath"], "/usr/bin/gdb")
        self.assertEqual(profile["preLaunchTask"], "native_sim: Build")
        # On Linux, false runs the program in the integrated terminal, where the shell takes input
        # (https://code.visualstudio.com/docs/cpp/launch-json-reference, externalConsole).
        self.assertIs(profile["externalConsole"], False)


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


class PresetNamesTest(unittest.TestCase):
    def test_display_names_use_ide_wording_without_a_language_standard(self):
        presets = {p["name"]: p for p in load(REPO / "CMakePresets.json")["configurePresets"]}
        self.assertEqual(presets["host-debug"]["displayName"], "Host Debug")
        self.assertEqual(presets["host-sanitize"]["displayName"], "Host Debug (ASan, UBSan)")
        for preset in presets.values():
            text = preset["displayName"] + preset.get("description", "")
            self.assertNotRegex(text, r"C\+\+\d\d|C\d\d")


class DocsTest(unittest.TestCase):
    def test_build_guide_names_every_task_profile_and_preset(self):
        guide = (REPO / "docs/build.md").read_text()
        section = guide[guide.index("\n## VS Code\n"):]
        section = section[:section.index("\n## ", 1)]
        for name in TASKS + PROFILES + ["host-debug", "host-sanitize", "CMake Tools", "Testing"]:
            self.assertIn(name, section)

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
