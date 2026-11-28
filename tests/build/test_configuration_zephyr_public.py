"""The Settings File provider's start is a documented composition interface, reachable through a public target.

`<crux/configuration_zephyr.h>` and `crux::configuration_zephyr` publish one existing declaration,
`crux_config_zephyr_init()`, unchanged, so that a product's composition can start the provider after it
mounts the volume and checks its layout, with no private include path. These checks run on the host.
They compile the header alone, hold the provider's private header and its definition to the same
declaration, and read the CMake definition of the target. tests/zephyr/configuration_settings_link
links the provider through the target.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONFIGURATION = ROOT / "components/configuration"
PORT = CONFIGURATION / "ports/zephyr"
PUBLIC_INCLUDE = PORT / "include"
HEADER = PUBLIC_INCLUDE / "crux/configuration_zephyr.h"
PRIVATE = PORT / "configuration_settings.h"
DEFINITION = PORT / "configuration_settings.c"
PORTABLE = CONFIGURATION / "include/crux/configuration.h"
CC = os.environ.get("CC", "cc")
FLAGS = ["-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror"]
ROOTS = [PUBLIC_INCLUDE, CONFIGURATION / "include", ROOT / "components/base/include"]
USES = """
#include <crux/configuration_zephyr.h>
crux_config_result_t (*start)(void) = crux_config_zephyr_init;
int main(void) { return start ? 0 : 1; }
"""
CONSUMERS = (
    ROOT / "tests/zephyr/configuration_settings_link/CMakeLists.txt",
    ROOT / "tests/zephyr/file_littlefs_link/CMakeLists.txt",
    ROOT / "samples/boards/nxp/mimxrt1060_evk/emmc_file/CMakeLists.txt",
)


def compile_source(source, roots, extra=()):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "tu.c"
        path.write_text(source)
        command = [CC, *FLAGS, *extra, *[arg for root in roots for arg in ("-I", str(root))],
                   "-fsyntax-only", str(path)]
        return subprocess.run(command, capture_output=True, text=True)


def declarations(path):
    """The function declarations of a header, without comments and preprocessor lines."""
    code = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
    code = re.sub(r"^\s*#.*$", "", code, flags=re.M)
    code = code.replace('extern "C" {', "")
    return [" ".join(match.split()) for match in re.findall(r"[A-Za-z_][\w\s*]*\([^;{{]*\)\s*;", code)]


def comment_text(path):
    return " ".join(path.read_text().replace("\n *", " ").split())


class PublicHeader(unittest.TestCase):
    def test_the_header_exists_under_the_composition_path_and_compiles_alone(self):
        self.assertTrue(HEADER.is_file(), HEADER)
        result = compile_source(USES, ROOTS)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_it_is_usable_from_c_plus_plus(self):
        self.assertIn('extern "C" {', HEADER.read_text())

    def test_it_includes_the_portable_header_only(self):
        # Rule 5: no Zephyr header, because the start names no Zephyr type.
        includes = re.findall(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', HEADER.read_text(), re.M)
        self.assertEqual(includes, ["crux/configuration.h"])

    def test_it_publishes_the_existing_start_unchanged_and_nothing_else(self):
        self.assertEqual(declarations(HEADER), ["crux_config_result_t crux_config_zephyr_init(void);"])
        self.assertRegex(DEFINITION.read_text(), r"(?m)^crux_config_result_t crux_config_zephyr_init\(void\)$")

    def test_the_private_header_takes_the_declaration_from_the_public_one(self):
        # One declaration, which the provider's own source sees, so the compiler holds it to the definition.
        self.assertEqual(declarations(PRIVATE), [])
        self.assertIn('#include "include/crux/configuration_zephyr.h"', PRIVATE.read_text())
        self.assertIn('#include "configuration_settings.h"', DEFINITION.read_text())
        both = compile_source('#include "configuration_settings.h"\n'
                              "crux_config_result_t (*start)(void) = crux_config_zephyr_init;\n"
                              "int main(void) { return start ? 0 : 1; }\n",
                              [PORT, CONFIGURATION / "include", ROOT / "components/base/include"])
        self.assertEqual(both.returncode, 0, both.stderr)

    def test_the_portable_header_does_not_declare_it(self):
        self.assertNotIn("crux_config_zephyr_init", " ".join(declarations(PORTABLE)))

    def test_it_documents_tier_order_context_and_results(self):
        text = comment_text(HEADER)
        self.assertRegex(HEADER.read_text().split("*/", 1)[0], r"Status:\s+Experimental")
        for phrase in ("composition interface", "crux::configuration_zephyr", "mounted",
                       "CONFIG_SETTINGS_FILE_PATH", "creates", "Thread context", "before any other",
                       "again", "CRUX_CONFIG_ERR_NOT_READY", "CRUX_CONFIG_ERR_NO_SPACE",
                       "CRUX_CONFIG_ERR_NOT_SUPPORTED", "CRUX_CONFIG_ERR_IO",
                       "CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE"):
            self.assertIn(phrase, text, phrase)

    def test_the_lines_fit_the_column_limit_of_the_format_check(self):
        for path in (HEADER, PRIVATE):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                self.assertLessEqual(len(line), 100, f"{path.name}:{number}")

    def test_the_public_path_is_unique(self):
        found = sorted(p.relative_to(ROOT).as_posix()
                       for p in (ROOT / "components").rglob("configuration_zephyr.h"))
        self.assertEqual(found, [HEADER.relative_to(ROOT).as_posix()])


class Target(unittest.TestCase):
    @staticmethod
    def body():
        text = (PORT / "CMakeLists.txt").read_text()
        match = re.search(r"function\(crux_configuration_zephyr_composition\)(.*?)endfunction\(\)",
                          text, re.S)
        return text, match.group(1) if match else None

    def test_the_target_exposes_the_include_root_and_the_portable_target_only(self):
        text, body = self.body()
        self.assertIsNotNone(body)
        self.assertIn("add_library(crux_configuration_zephyr_composition INTERFACE)", body)
        self.assertIn("add_library(crux::configuration_zephyr ALIAS "
                      "crux_configuration_zephyr_composition)", body)
        self.assertIn('"${CRUX_CONFIGURATION_COMPONENT_DIR}/ports/zephyr/include"', body)
        linked = re.findall(r"target_link_libraries\(\w+ INTERFACE ([^)]*)\)", body)
        self.assertEqual(" ".join(linked).split(), ["crux_configuration"])
        # Rule 2: never the STATIC provider, the private source directory or the port directory itself.
        for forbidden in ("/src", "crux_configuration_zephyr ", "crux_configuration_zephyr)", "PUBLIC",
                          '/ports/zephyr"'):
            self.assertNotIn(forbidden, body)
        self.assertEqual(len(re.findall(r"^crux_configuration_zephyr_composition\(\)\s*$", text, re.M)), 1)

    def test_the_target_is_defined_after_the_provider_selection_check(self):
        # The directory refuses to configure without a Settings File selection, so a product that
        # links the target without a provider fails at CMake instead of linking nothing.
        text = (PORT / "CMakeLists.txt").read_text()
        guard = text.index("if(NOT CONFIG_CRUX_CONFIGURATION_SETTINGS_PROVIDER)")
        call = re.search(r"^crux_configuration_zephyr_composition\(\)\s*$", text, re.M)
        self.assertIsNotNone(call)
        self.assertLess(guard, call.start())

    def test_in_tree_compositions_use_the_target_and_no_private_path(self):
        for path in CONSUMERS:
            text = path.read_text()
            with self.subTest(consumer=path.relative_to(ROOT).as_posix()):
                self.assertIn("crux::configuration_zephyr", text)
                self.assertNotIn("components/configuration/ports/zephyr", text)

    def test_in_tree_compositions_include_the_public_header(self):
        for path in (ROOT / "tests/zephyr/configuration_settings_link/main.c",
                     ROOT / "tests/zephyr/file_littlefs_link/main.c",
                     ROOT / "samples/boards/nxp/mimxrt1060_evk/emmc_file/emmc_configuration.c"):
            text = path.read_text()
            with self.subTest(source=path.relative_to(ROOT).as_posix()):
                self.assertIn("#include <crux/configuration_zephyr.h>", text)
                self.assertNotIn('#include "configuration_settings.h"', text)


if __name__ == "__main__":
    unittest.main()
