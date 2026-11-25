"""Check the starter sample samples/hello_crux: no Crux Time, the version in the greeting.

Each composition's main prints with its own OS facility and links crux::base for <crux/version.h>.
The output checks accept any version, so a version bump does not break them. The Host program
is compiled and run here when a C compiler is found; Twister runs the Zephyr application.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

try:
    import yaml
except ImportError:  # pragma: no cover - depends on the environment
    yaml = None

REPO = Path(__file__).resolve().parents[2]
SAMPLE = REPO / "samples/hello_crux"
VERSIONS = ("0.1.0-dev", "0.1.0", "1.2.3-rc.1")


def compiler():
    for name in ("cc", "gcc", "clang"):
        path = shutil.which(name)
        if path:
            return path
    return None


class HelloCruxSourcesTest(unittest.TestCase):
    def test_no_crux_time_anywhere_in_the_sample(self):
        for path in SAMPLE.rglob("*"):
            if path.is_file() and path.suffix in {".c", ".h", ".txt", ".conf", ".yaml"}:
                with self.subTest(path=path.relative_to(REPO).as_posix()):
                    text = path.read_text()
                    self.assertNotRegex(text, r"CONFIG_CRUX_TIME|crux::time|CRUX_BUILD_TIME|crux/time\.h|Crux Time")

    def test_no_portable_source_remains(self):
        self.assertFalse((SAMPLE / "common").exists())

    def test_both_compositions_link_crux_base(self):
        for path in (SAMPLE / "zephyr/CMakeLists.txt", SAMPLE / "linux/CMakeLists.txt"):
            with self.subTest(path=path.relative_to(REPO).as_posix()):
                self.assertRegex(path.read_text(), r"target_link_libraries\([^)]*crux::base")

    def test_each_main_prints_the_version_with_its_own_os_facility(self):
        zephyr = (SAMPLE / "zephyr/src/main.c").read_text()
        host = (SAMPLE / "linux/main.c").read_text()
        for text in (zephyr, host):
            self.assertIn("#include <crux/version.h>", text)
            self.assertIn("CRUX_VERSION_STRING", text)
        self.assertIn("printk(", zephyr)
        self.assertNotIn("printk", host)
        self.assertIn("printf(", host)


@unittest.skipUnless(yaml, "PyYAML is required to parse sample.yaml")
class HelloCruxTwisterTest(unittest.TestCase):
    def regexes(self):
        sample = yaml.safe_load((SAMPLE / "zephyr/sample.yaml").read_text())
        return sample["tests"]["crux.sample.hello_crux"]["harness_config"]["regex"]

    def test_console_check_accepts_any_version_then_the_ready_line(self):
        greeting, ready = self.regexes()
        for version in VERSIONS:
            with self.subTest(version=version):
                self.assertRegex(f"Hello from Crux {version} on zephyr", greeting)
        self.assertNotRegex("Hello from Crux on zephyr", greeting)
        self.assertRegex("CRUX_HELLO_READY composition=zephyr", ready)


@unittest.skipUnless(compiler(), "no C compiler")
class HelloCruxHostProgramTest(unittest.TestCase):
    def test_host_program_prints_the_version_and_the_ready_line(self):
        with tempfile.TemporaryDirectory() as temporary:
            program = Path(temporary) / "hello-crux-host"
            subprocess.run([compiler(), "-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
                            "-I", str(REPO / "components/base/include"), str(SAMPLE / "linux/main.c"),
                            "-o", str(program)], check=True)
            output = subprocess.run([str(program)], check=True, capture_output=True, text=True).stdout
        version = re.search(r'#define CRUX_VERSION_STRING "([^"]+)"',
                            (REPO / "components/base/include/crux/version.h").read_text()).group(1)
        self.assertEqual(output.splitlines(),
                         [f"Hello from Crux {version} on host", "CRUX_HELLO_READY composition=host"])


if __name__ == "__main__":
    unittest.main()
