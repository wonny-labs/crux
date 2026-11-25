"""Check the Crux release version: <crux/version.h> and the root CMake project version.

The header is the one place the number is kept (ADR-0008). The root CMakeLists.txt reads it into
project(crux VERSION ...). The compile and configure cases skip when no C compiler or CMake 3.28
is found.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
HEADER = REPO / "components/base/include/crux/version.h"
PRERELEASE = re.compile(r"(|dev|rc\.(0|[1-9][0-9]*))")


def macros():
    found = {}
    for name, value in re.findall(r"(?m)^#define\s+(CRUX_VERSION_\w+)\s+(.+?)\s*$", HEADER.read_text()):
        found[name] = value
    return found


def parts():
    values = macros()
    numbers = [int(values[f"CRUX_VERSION_{part}"]) for part in ("MAJOR", "MINOR", "PATCH")]
    prerelease = re.fullmatch(r'"([^"]*)"', values["CRUX_VERSION_PRERELEASE"]).group(1)
    return numbers, prerelease


def expected_string():
    numbers, prerelease = parts()
    text = ".".join(str(number) for number in numbers)
    return f"{text}-{prerelease}" if prerelease else text


def compiler():
    for name in ("cc", "gcc", "clang"):
        path = shutil.which(name)
        if path:
            return path
    return None


def cmake_at_least_3_28():
    cmake = shutil.which("cmake")
    if not cmake:
        return None
    version = subprocess.run([cmake, "--version"], capture_output=True, text=True).stdout
    match = re.search(r"cmake version (\d+)\.(\d+)", version)
    return cmake if match and (int(match.group(1)), int(match.group(2))) >= (3, 28) else None


class VersionHeaderTest(unittest.TestCase):
    def test_header_defines_each_part_once(self):
        text = HEADER.read_text()
        for name in ("MAJOR", "MINOR", "PATCH", "PRERELEASE", "STRING"):
            with self.subTest(name=name):
                self.assertEqual(len(re.findall(rf"(?m)^#define\s+CRUX_VERSION_{name}\s", text)), 1)

    def test_numeric_parts_are_decimal_integers(self):
        values = macros()
        for part in ("MAJOR", "MINOR", "PATCH"):
            with self.subTest(part=part):
                self.assertRegex(values[f"CRUX_VERSION_{part}"], r"^(0|[1-9][0-9]*)$")

    def test_prerelease_is_empty_dev_or_a_release_candidate(self):
        _, prerelease = parts()
        self.assertRegex(prerelease, PRERELEASE)

    def test_string_equals_the_parts(self):
        self.assertEqual(macros()["CRUX_VERSION_STRING"], f'"{expected_string()}"')

    def test_no_version_number_macro_before_1_0(self):
        # Before 1.0 the numbers name the target release, so a number cannot tell a snapshot of
        # main from the release. Version-number feature checks are not supported (ADR-0008).
        self.assertNotIn("CRUX_VERSION_NUMBER", HEADER.read_text())

    @unittest.skipUnless(compiler(), "no C compiler")
    def test_header_compiles_alone_and_gives_the_string(self):
        probe = (
            "#include <crux/version.h>\n"
            "#include <stdio.h>\n"
            "_Static_assert(CRUX_VERSION_MAJOR >= 0 && CRUX_VERSION_MINOR >= 0 && CRUX_VERSION_PATCH >= 0,\n"
            "               \"numeric parts\");\n"
            "int main(void)\n{\n"
            "    printf(\"%d.%d.%d|%s|%s\\n\", CRUX_VERSION_MAJOR, CRUX_VERSION_MINOR, CRUX_VERSION_PATCH,\n"
            "           CRUX_VERSION_PRERELEASE, CRUX_VERSION_STRING);\n"
            "    return 0;\n}\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "probe.c"
            program = Path(temporary) / "probe"
            source.write_text(probe)
            subprocess.run([compiler(), "-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
                            "-I", str(REPO / "components/base/include"), str(source), "-o", str(program)],
                           check=True)
            output = subprocess.run([str(program)], check=True, capture_output=True, text=True).stdout
        numbers, prerelease = parts()
        self.assertEqual(output.strip(),
                         f"{'.'.join(map(str, numbers))}|{prerelease}|{expected_string()}")


class CMakeVersionTest(unittest.TestCase):
    def test_root_project_takes_its_version_from_the_header(self):
        text = (REPO / "CMakeLists.txt").read_text()
        self.assertTrue("components/base/include/crux/version.h" in text, "CMakeLists.txt does not read the header")
        self.assertTrue(re.search(r"project\(crux\s+VERSION\s+\$\{", text), "project(crux) has no VERSION variable")

    def test_no_package_version_file_while_dev(self):
        # CMake versions have no pre-release part, so a package version file would claim the release.
        for path in [REPO / "CMakeLists.txt", *REPO.glob("cmake/*.cmake"), *REPO.glob("components/*/CMakeLists.txt")]:
            with self.subTest(path=path.relative_to(REPO).as_posix()):
                self.assertNotIn("write_basic_package_version_file", path.read_text())

    @unittest.skipUnless(cmake_at_least_3_28() and compiler(), "needs CMake 3.28 and a C compiler")
    def test_configured_project_version_matches_the_header(self):
        # Configure Crux as an external application does, with no capability selected.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.28)\n"
                "project(version_probe LANGUAGES C)\n"
                f'add_subdirectory("{REPO.as_posix()}" crux)\n'
                f'get_directory_property(crux_version DIRECTORY "{REPO.as_posix()}" DEFINITION crux_VERSION)\n'
                'message(STATUS "CRUX_PROJECT_VERSION=${crux_version}")\n'
            )
            result = subprocess.run([cmake_at_least_3_28(), "-S", str(root), "-B", str(root / "build")],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        match = re.search(r"CRUX_PROJECT_VERSION=(\S*)", result.stdout)
        self.assertIsNotNone(match, result.stdout)
        self.assertEqual(match.group(1), ".".join(map(str, parts()[0])))


if __name__ == "__main__":
    unittest.main()
