"""The out-of-tree System consumer (ADR-0005 T3, T4, T5): its checks and its fixture, on the host.

The Zephyr build and the run on native_sim are done by scripts/test-consumer-system.sh in the Zephyr runtime shard
(through scripts/test-system.sh). These Host tests need no Zephyr SDK: they call the check functions of
tests/consumer_system/check_build.py on small inputs, run each of them against a weakened copy so that a refusal is
not vacuous, and check that the fixture reads nothing from inside the repository.
"""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import stat
import tempfile
import threading
import time
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests/consumer_system"


def load_checks():
    spec = importlib.util.spec_from_file_location("consumer_system_check_build", FIXTURE / "check_build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = load_checks()

def strip_comments(path, text):
    """The code of a fixture file: comments are removed line by line, never across lines."""
    if path.suffix in (".c", ".h"):
        # A '#' starts a preprocessor directive in C, not a comment.
        return re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S))
    return re.sub(r"#[^\n]*", "", text)


def repository_references(path, text):
    """Every path into the Crux components that the code of a fixture file names."""
    return re.findall(r"components/\S*", strip_comments(path, text))


PLANTED = {
    ".txt": "set(PLANTED ${CRUX_DIR}/components/system/src)\n",
    ".conf": 'CONFIG_PLANTED="components/system/src"\n',
    ".c": 'static const char *planted = "components/system/src";\n',
}


GOOD_RUN = "\n".join([
    "*** Booting Zephyr OS build ***",
    "simwdt: boot 1 cause POR",
    "simwdt: idle before start, simulated",
    "simwdt: started, 2000 ms, active, simulated",
    "simwdt: feed cycle ok, 6 feeds over 3000 ms, no restart",
    "simwdt: missed feed, no more feeds",
    "Crux simulated watchdog expired: no feed for 2000 ms; restarting the simulated process (after 2001 ms)",
    "simwdt: boot 2 cause SOFTWARE, not WATCHDOG",
    "simwdt: boot 2 fresh state, idle, simulated",
    "simwdt: boot 2 feed cycle ok, no second restart, scenario complete",
]) + "\n"


class FixtureLayoutTest(unittest.TestCase):
    def test_the_fixture_reads_nothing_from_inside_the_repository(self):
        # The copy built by the script lives outside the repository; a relative path to it would break there.
        for path in sorted((FIXTURE / "app").rglob("*")):
            if not path.is_file():
                continue
            text = path.read_text()
            with self.subTest(path=str(path.relative_to(FIXTURE))):
                self.assertNotRegex(text, r"\.\./", "no relative path out of the copy")
                self.assertEqual(repository_references(path, text), [])

    def test_the_reference_check_sees_a_path_planted_anywhere_in_each_file(self):
        # A comment must not hide the rest of the file: plant a path at the start and at the end of every file.
        for path in sorted((FIXTURE / "app").rglob("*")):
            if not path.is_file():
                continue
            text = path.read_text()
            planted = PLANTED[path.suffix]
            with self.subTest(path=str(path.relative_to(FIXTURE))):
                self.assertEqual(repository_references(path, text), [])
                self.assertTrue(repository_references(path, planted + text), "planted at the start")
                self.assertTrue(repository_references(path, text + planted), "planted at the end")
                first_code_line = next(line for line in text.splitlines() if line and line[0] in "#@")
                after_first = text.replace(first_code_line + "\n", first_code_line + "\n" + planted, 1)
                self.assertTrue(repository_references(path, after_first), "planted after the first '#' line")

    def test_the_fixture_is_clean_by_its_own_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "copy"
            shutil.copytree(FIXTURE, copy)
            self.assertEqual(check.check_sources(copy), [])

    def test_the_fixture_links_one_public_target_and_includes_the_public_headers_only(self):
        cmake = (FIXTURE / "app/CMakeLists.txt").read_text()
        self.assertEqual(check.link_violations(cmake), [])
        self.assertIn("crux::system", cmake)
        main = (FIXTURE / "app/src/main.c").read_text()
        crux_headers = set(re.findall(r"#include <(crux/[^>]+)>", main))
        self.assertEqual(crux_headers, {"crux/system.h", "crux/status.h"})

    def test_the_native_sim_fragment_holds_the_facilities_and_the_symbol(self):
        fragment = (FIXTURE / "app/boards/native_sim_native_64.conf").read_text()
        for line in ("CONFIG_WATCHDOG=y", "CONFIG_HWINFO=y", "CONFIG_REBOOT=y",
                     "CONFIG_CRUX_SYSTEM_NATIVE_SIM_WATCHDOG=y"):
            self.assertIn(line, fragment)
        conf = (FIXTURE / "app/prj.conf").read_text()
        self.assertNotIn("NATIVE_SIM_WATCHDOG", conf, "the simulated watchdog is a native_sim fragment setting")
        self.assertIn("CONFIG_CRUX_SYSTEM=y", conf)

    def test_the_script_exists_runs_in_the_system_runner_and_builds_outside_the_repository(self):
        script = REPO / "scripts/test-consumer-system.sh"
        self.assertTrue(script.is_file())
        self.assertTrue(script.stat().st_mode & 0o111, "executable")
        text = script.read_text()
        self.assertIn("mktemp -d", text)
        self.assertIn("-DZEPHYR_EXTRA_MODULES=", text)
        self.assertIn("CONFIG_CRUX_SYSTEM_NATIVE_SIM_WATCHDOG=n", text)
        self.assertIn("test-consumer-system.sh", (REPO / "scripts/test-system.sh").read_text())


class CheckFunctionTest(unittest.TestCase):
    def test_headers(self):
        self.assertEqual(check.header_violations('#include <crux/system.h>\n#include <crux/status.h>\n'
                                                 '#include <crux/logging.h>\n#include <zephyr/kernel.h>\n'
                                                 '#include <stdint.h>\n#include "local.h"\n'), [])
        for name in ("crux/thread.h", "crux/system_zephyr.h", "crux/file_zephyr.h"):
            self.assertEqual(check.header_violations(f"#include <{name}>\n"), [name], name)
        for name in ("system_zephyr.h", "components/system/ports/zephyr/system_binding.h",
                     "../src/system.h", "system_sim_watchdog.h"):
            self.assertEqual(check.header_violations(f'#include "{name}"\n'), [name], name)

    def test_links(self):
        self.assertEqual(check.link_violations("target_link_libraries(app PRIVATE crux::system)"), [])
        self.assertEqual(check.link_violations("# target_link_libraries(app PRIVATE bad)\n"), [])
        self.assertEqual(check.link_violations("target_link_libraries(app PRIVATE crux::system crux_system_zephyr)"),
                         ["crux_system_zephyr"])
        self.assertEqual(check.link_violations("target_link_libraries(app PRIVATE crux::time)"), ["crux::time"])

    def test_wraps_of_crux_symbols_only(self):
        for option in ("-Wl,--wrap=crux_watchdog_zephyr_device", "-Wl,--wrap,crux_x", "LINKER:--wrap=__wrap_crux_x",
                       "-Xlinker --wrap -Xlinker crux_x", "-Wl,--wrap=sys_reboot,--wrap=__real_crux_x"):
            with self.subTest(option=option):
                self.assertEqual(len(check.wrap_violations(f"target_link_options(app PRIVATE {option})")), 1)
        for option in ("-Wl,--wrap=sys_reboot", "-Wl,--wrap=z_impl_hwinfo_get_reset_cause",
                       "-Wl,--wrap=clock_settime", "-Wl,--undefined=crux_system_status_get"):
            with self.subTest(option=option):
                self.assertEqual(check.wrap_violations(f"target_link_options(app PRIVATE {option})"), [])
        self.assertEqual(check.wrap_violations("# -Wl,--wrap=crux_x\n"), [])

    def test_conf(self):
        self.assertEqual(check.conf_violations("CONFIG_CRUX_SYSTEM=y\nCONFIG_CRUX_TIME=n\n"
                                               "CONFIG_CRUX_SYSTEM_NATIVE_SIM_WATCHDOG=y\nCONFIG_WATCHDOG=y\n"), [])
        self.assertEqual(check.conf_violations("CONFIG_CRUX_THREAD=y\n"), ["CRUX_THREAD=y"])
        self.assertEqual(check.conf_violations("CONFIG_CRUX_TIME=y\n"), ["CRUX_TIME=y"])
        self.assertEqual(check.conf_violations("CONFIG_CRUX_WEB=y\n"), ["CRUX_WEB=y"])

    def test_include_directories(self):
        repo = Path("/work/crux")
        consumer = Path("/work/out/app")
        entry = {"directory": "/work/out/build", "file": "/work/out/app/src/main.c",
                 "command": "cc -I/work/crux/components/system/include -I/work/crux/components/base/include "
                            "-isystem /work/zephyr/include -c main.c"}
        # Neither path exists, so resolve() keeps them as written.
        self.assertEqual(check.include_violations([entry], consumer, repo), [])
        for directory in ("components/system/ports/zephyr", "components/system/src", "components/web/adapter"):
            bad = dict(entry, command=entry["command"] + f" -I/work/crux/{directory}")
            self.assertEqual(len(check.include_violations([bad], consumer, repo)), 1, directory)
        other = dict(entry, file="/work/crux/components/system/src/system.c",
                     command="cc -I/work/crux/components/system/src -c system.c")
        self.assertEqual(check.include_violations([other], consumer, repo), [], "Crux's own sources are not the product's")

    def test_config_and_image(self):
        base = "CONFIG_CRUX_SYSTEM=y\nCONFIG_BOARD_NATIVE_SIM=y\n"
        on = base + "CONFIG_CRUX_SYSTEM_NATIVE_SIM_WATCHDOG=y\nCONFIG_NATIVE_SIM_REBOOT=y\n"
        self.assertEqual(check.config_violations(on, True), [])
        self.assertEqual(check.config_violations(base, False), [])
        self.assertEqual(len(check.config_violations(base, True)), 2)
        self.assertEqual(len(check.config_violations(on, False)), 1)
        self.assertEqual(len(check.config_violations(on.replace("BOARD_NATIVE_SIM=y", "BOARD_X=y"), True)), 1)
        device = "0000 T crux_system_sim_watchdog_device\n"
        self.assertEqual(check.device_violations(device, True), [])
        self.assertEqual(check.device_violations("0000 T main\n", False), [])
        self.assertEqual(len(check.device_violations("0000 T main\n", True)), 1)
        self.assertEqual(len(check.device_violations(device, False)), 1)

    def test_run(self):
        self.assertEqual(check.run_violations(GOOD_RUN), [])
        self.assertTrue(check.run_violations(GOOD_RUN.replace("simwdt: boot 2 cause SOFTWARE, not WATCHDOG\n", "")))
        self.assertTrue(check.run_violations(GOOD_RUN + "simwdt: FAIL boot 2 feed\n"))
        self.assertTrue(check.run_violations(GOOD_RUN.replace("after 2001 ms", "after 900 ms")))
        lines = GOOD_RUN.splitlines()
        lines[5], lines[6] = lines[6], lines[5]
        self.assertTrue(check.run_violations("\n".join(lines) + "\n"), "out of order")
        # The restart loop of a consumer that never feeds on boot 2: the run never reaches the last line.
        loop = "\n".join(GOOD_RUN.splitlines()[:7] + GOOD_RUN.splitlines()[1:7]) + "\n"
        self.assertTrue(check.run_violations(loop))

    def test_the_run_lines_are_those_of_the_in_repository_scenario(self):
        yaml = (REPO / "tests/system/zephyr/native_sim_watchdog/testcase.yaml").read_text()
        expected = [line.strip()[3:-1].replace("\\\\", "\\")
                    for line in yaml.splitlines() if line.strip().startswith('- "')]
        self.assertEqual(check.RUN_LINES, expected)


class VariantTest(unittest.TestCase):
    """Each negative variant is one change, and a check refuses it. Each check also runs weakened."""

    def variants(self):
        return json.loads((FIXTURE / "variants.json").read_text())

    def refused(self, variant, checks):
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "copy"
            shutil.copytree(FIXTURE, copy)
            check.apply_variant(copy, variant)
            return "\n".join(f"FAIL: {problem}" for problem in checks.check_sources(copy))

    def test_every_variant_applies_exactly_once(self):
        for variant in self.variants():
            with self.subTest(variant=variant["name"]):
                self.assertEqual((FIXTURE / variant["file"]).read_text().count(variant["old"]), 1)

    def test_variants_that_need_no_build_are_refused_with_their_message(self):
        for variant in self.variants():
            if variant["expect"].startswith("include:"):
                continue
            with self.subTest(variant=variant["name"]):
                self.assertIn(variant["expect"], self.refused(variant, check))

    FUNCTION_OF = (("headers:", "header_violations"), ("link:", "link_violations"),
                   ("wrap:", "wrap_violations"), ("symbol in", "conf_violations"))

    def test_each_refusal_goes_when_the_function_it_relies_on_is_weakened(self):
        # The one function that finds the variant returns nothing: the variant is then accepted, so the refusal
        # above is that function's and not the fixture's. Nothing else refuses the variant.
        for variant in self.variants():
            if variant["expect"].startswith("include:"):
                continue
            name = next(function for prefix, function in self.FUNCTION_OF if variant["expect"].startswith(prefix))
            with self.subTest(variant=variant["name"], weakened=name):
                refused = self.refused(variant, check)
                with mock.patch.object(check, name, return_value=[]):
                    accepted = self.refused(variant, check)
                self.assertIn(variant["expect"], refused)
                self.assertNotEqual(refused, accepted, "the weakening changed nothing")
                self.assertEqual(accepted, "")

    def test_the_variants_are_the_six_of_the_record(self):
        self.assertEqual([variant["name"] for variant in self.variants()],
                         ["private_include_directory", "private_header_in_the_shell",
                          "frozen_header_in_the_shell", "target_without_a_crux_name",
                          "wrap_of_the_binding_seam", "frozen_symbol_in_prj_conf"])

    def test_the_include_variant_is_refused_by_the_include_check_and_named_in_variants(self):
        include = [v for v in self.variants() if v["expect"].startswith("include:")]
        self.assertEqual(len(include), 1)
        self.assertIn("components/system/ports/zephyr", include[0]["new"])
        entry = {"directory": "/work/out/build", "file": "/work/out/app/src/main.c",
                 "command": "cc -I/work/crux/components/system/ports/zephyr -c main.c"}
        self.assertEqual(len(check.include_violations([entry], "/work/out/app", "/work/crux")), 1)

    def test_the_wrap_of_a_zephyr_symbol_is_not_a_variant(self):
        # S6 leaves a product's own wraps of Zephyr symbols alone; only a Crux symbol is refused.
        for variant in self.variants():
            self.assertNotIn("sys_reboot", variant["new"])


class RunTest(unittest.TestCase):
    """check.run reads the image with a real deadline: a silent image cannot block the runner."""

    def stub(self, directory, printed, tail="exec sleep 30"):
        path = Path(directory) / "image"
        path.write_text("#!/bin/sh\ncat <<'EOF'\n" + printed + "EOF\n" + tail + "\n")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def run_limited(self, executable, timeout):
        result = {}
        worker = threading.Thread(target=lambda: result.update(output=check.run(str(executable), timeout=timeout)),
                                  daemon=True)
        started = time.monotonic()
        worker.start()
        worker.join(20)
        self.assertFalse(worker.is_alive(), "run() did not return: it blocks on a silent image")
        return result["output"], time.monotonic() - started

    def test_a_silent_image_times_out_and_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            output, elapsed = self.run_limited(self.stub(directory, ""), 1)
        self.assertLess(elapsed, 10)
        self.assertIn("check_build: FAIL", output)
        self.assertTrue(check.run_violations(output))

    def test_an_image_that_stops_after_some_lines_times_out_and_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            output, elapsed = self.run_limited(self.stub(directory, "\n".join(GOOD_RUN.splitlines()[:3]) + "\n"), 1)
        self.assertLess(elapsed, 10)
        self.assertIn("simwdt: boot 1 cause POR", output)
        self.assertIn("check_build: FAIL", output)
        self.assertTrue(check.run_violations(output))

    def test_an_image_that_reaches_its_last_line_returns_at_once_and_clean(self):
        with tempfile.TemporaryDirectory() as directory:
            output, elapsed = self.run_limited(self.stub(directory, GOOD_RUN), 60)
        self.assertLess(elapsed, 10, "it must not wait for the image to exit")
        self.assertNotIn("check_build: FAIL", output)
        self.assertEqual(check.run_violations(output), [])


class ScriptTest(unittest.TestCase):
    def setUp(self):
        self.text = (REPO / "scripts/test-consumer-system.sh").read_text()

    def test_the_work_directory_is_outside_the_repository(self):
        self.assertIn('"$work/" == "$repo/"*', self.text)

    def test_crux_dir_is_passed_to_the_variant_build_only(self):
        self.assertEqual(self.text.count("-DCRUX_DIR"), 1)
        self.assertGreater(self.text.index("-DCRUX_DIR"), self.text.index("# T4:"))


if __name__ == "__main__":
    unittest.main()
