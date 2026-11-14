"""Portable usage targets of the Configuration core, Configuration service, network settings, status
service, file service and reboot service in the Zephyr module (ADR-0004, T1 and T2, PR 3b).

HELD for the owner's approval of the new public target names: ADR-0004 section 2 lists none of these
six targets. The checks are the same as for crux::access and the other first targets, and they run on
the host without a Zephyr SDK:

T2: each public header compiles alone, pulls in only the capability's own Crux headers and the
contracts it names, no frozen or native header, names its tier, and the CMake definition of its
target exposes the include root and those contracts only.

T1: the real guards (cmake/Crux*Boundary.cmake) accept a portable consumer of the six targets and
refuse every way past them, against the real definitions taken from the port CMake files. The same
projects configure against weakened copies of the guards, which are anchored at this repository so
that they check the real adapter directories, and an unweakened copy is shown to reject.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
COMPONENTS = ROOT / "components"
CMAKE = shutil.which("cmake")
CC = os.environ.get("CC", "cc")
FLAGS = ["-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror"]
FROZEN = ("thread.h", "sync.h", "queue.h", "serial.h")
GUARDS = {name: ROOT / "cmake" / name for name in
          ("CruxConsumerBoundary.cmake", "CruxAccessBoundary.cmake", "CruxCredentialBoundary.cmake")}

# name -> (port CMake, function, target, alias, the contracts it links, header, the Crux headers that
# the header pulls in, the include roots needed to compile it, Kconfig symbol)
CASES = {
    "configuration": ("configuration/ports/zephyr/core/CMakeLists.txt", "crux_configuration_public_target",
                      "crux_configuration", "crux::configuration", set(), "configuration.h",
                      {"configuration.h"}, ["configuration/include"], "CRUX_CONFIGURATION_CORE"),
    "config_service": ("config_service/ports/zephyr/CMakeLists.txt", "crux_config_service_public_target",
                       "crux_config_service", "crux::config_service",
                       {"crux::access", "crux::configuration"}, "config_service.h",
                       {"config_service.h", "access.h", "configuration.h"},
                       ["config_service/include", "access/include", "configuration/include"],
                       "CRUX_CONFIG_SERVICE"),
    "network_settings": ("network_settings/ports/zephyr/CMakeLists.txt",
                         "crux_network_settings_public_target", "crux_network_settings",
                         "crux::network_settings", {"crux::access", "crux::config_service"},
                         "network_settings.h",
                         {"network_settings.h", "access.h", "config_service.h", "configuration.h"},
                         ["network_settings/include", "access/include", "config_service/include",
                          "configuration/include"], "CRUX_NETWORK_SETTINGS"),
    "mgmt_status": ("mgmt_status/ports/zephyr/CMakeLists.txt", "crux_mgmt_status_public_target",
                    "crux_mgmt_status", "crux::mgmt_status",
                    {"crux::access", "crux::base", "crux::system"}, "management_status.h",
                    {"management_status.h", "access.h", "status.h", "system.h"},
                    ["mgmt_status/include", "access/include", "base/include", "system/include"],
                    "CRUX_MGMT_STATUS"),
    "file_service": ("file_service/ports/zephyr/CMakeLists.txt", "crux_file_service_public_target",
                     "crux_file_service", "crux::file_service", {"crux::access", "crux::file"},
                     "file_service.h", {"file_service.h", "access.h", "file.h"},
                     ["file_service/include", "access/include", "file/include"], "CRUX_FILE_SERVICE"),
    "reboot": ("reboot/ports/zephyr/CMakeLists.txt", "crux_reboot_public_target", "crux_reboot",
               "crux::reboot", {"crux::access"}, "reboot.h", {"reboot.h", "access.h"},
               ["reboot/include", "access/include"], "CRUX_REBOOT"),
}
ORDER = ("configuration", "config_service", "network_settings", "mgmt_status", "file_service", "reboot")
DIR_VARIABLES = {"configuration": "CRUX_CONFIGURATION_COMPONENT_DIR",
                 "config_service": "CRUX_CONFIG_SERVICE_COMPONENT_DIR",
                 "network_settings": "CRUX_NETWORK_SETTINGS_COMPONENT_DIR",
                 "mgmt_status": "CRUX_MGMT_STATUS_COMPONENT_DIR",
                 "file_service": "CRUX_FILE_SERVICE_COMPONENT_DIR",
                 "reboot": "CRUX_REBOOT_COMPONENT_DIR"}


def port_text(name):
    return (COMPONENTS / CASES[name][0]).read_text()


def function_text(name):
    match = re.search(rf"function\({CASES[name][1]}\).*?endfunction\(\)", port_text(name), re.S)
    return match.group(0) if match else ""


def header_path(name):
    return COMPONENTS / name / "include/crux" / CASES[name][5]


def compile_source(source, roots, extra=()):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "tu.c"
        path.write_text(source)
        command = [CC, *FLAGS, *extra, *[arg for root in roots for arg in ("-I", str(root))],
                   "-fsyntax-only", str(path)]
        return subprocess.run(command, capture_output=True, text=True)


class PublicHeaders(unittest.TestCase):
    def test_each_header_compiles_alone_and_pulls_in_only_its_contracts(self):
        for name, case in CASES.items():
            roots = [COMPONENTS / relative for relative in case[7]]
            with self.subTest(component=name):
                result = compile_source(f"#include <crux/{case[5]}>\nint main(void) {{ return 0; }}\n", roots,
                                        ["-H"])
                self.assertEqual(result.returncode, 0, result.stderr)
                included = [line.lstrip(". ").strip() for line in result.stderr.splitlines()
                            if line.startswith(".")]
                crux = {Path(path).name for path in included if "/crux/" in path}
                self.assertEqual(crux, case[6])
                for header in crux:
                    self.assertNotIn(header, FROZEN)
                for path in [p for p in included if not p.startswith(str(ROOT))]:
                    self.assertNotRegex(path.lower(), r"zephyr|nxp|cmsis|mcux|/boards?/|wolf|mbedtls|psa")

    def test_each_header_names_its_tier_and_fits_the_format_check(self):
        for name in CASES:
            text = header_path(name).read_text()
            with self.subTest(component=name):
                self.assertRegex(text.split("*/", 1)[0], r"Status:\s+Experimental")
                self.assertIn('extern "C" {', text)
                for number, line in enumerate(text.splitlines(), 1):
                    self.assertLessEqual(len(line), 100, f"{header_path(name).name}:{number}")

    def test_no_header_names_a_frozen_native_or_private_header(self):
        for name in CASES:
            text = header_path(name).read_text()
            with self.subTest(component=name):
                self.assertNotRegex(text, r"#\s*include\s*[<\"]crux/(thread|sync|queue|serial)\.h")
                self.assertNotRegex(text, r"#\s*include\s*[<\"](zephyr|wolf|mbedtls|psa)/")
                self.assertNotRegex(text, r"#\s*include\s*[<\"][^>\"]*(adapter|_port)\.h")


class TargetDefinitions(unittest.TestCase):
    def test_each_port_defines_its_target_as_a_function_and_calls_it_once(self):
        for name, case in CASES.items():
            with self.subTest(component=name):
                self.assertTrue(function_text(name), "no function")
                self.assertEqual(len(re.findall(rf"^\s*{case[1]}\(\)\s*$", port_text(name), re.M)), 1)

    def test_each_target_is_an_interface_library_with_a_crux_alias(self):
        for name, case in CASES.items():
            text = function_text(name)
            with self.subTest(component=name):
                self.assertIn(f"add_library({case[2]} INTERFACE)", text)
                self.assertIn(f"add_library({case[3]} ALIAS {case[2]})", text)

    def test_each_target_exposes_the_include_root_and_its_contracts_only(self):
        for name, case in CASES.items():
            text = function_text(name)
            with self.subTest(component=name):
                self.assertIn(f'"${{{DIR_VARIABLES[name]}}}/include"', text)
                for forbidden in ("/src", "/adapter", "/ports", "credential", "zephyr_interface", "PUBLIC",
                                  "_zephyr", "target_link_options", "target_compile"):
                    self.assertNotIn(forbidden, text)
                linked = {word for entry in re.findall(r"target_link_libraries\(\w+ INTERFACE ([^)]*)\)", text)
                          for word in entry.split()}
                self.assertEqual(linked, case[4])

    def test_the_include_root_uses_a_variable_that_the_file_defines(self):
        for name in CASES:
            variable = DIR_VARIABLES[name]
            with self.subTest(component=name):
                self.assertRegex(port_text(name), rf'get_filename_component\({variable} "\$\{{CMAKE_CURRENT_LIST_DIR\}}/(\.\./)+\.\.')

    def test_each_target_is_checked_and_does_not_link_the_provider(self):
        for name, case in CASES.items():
            text = port_text(name)
            with self.subTest(component=name):
                self.assertIn(f"DEFER CALL crux_assert_portable_usage {case[3]}", text)
                self.assertIn(f"DEFER CALL crux_assert_access_adapter_unreachable {case[3]}", text)
                self.assertNotIn("zephyr_append_cmake_library", function_text(name))

    def test_the_configuration_core_defines_its_target_only_without_the_settings_file_selection(self):
        # The Settings File selection defines crux::configuration itself; the core returns early under it.
        text = port_text("configuration")
        self.assertLess(text.index("return()"), text.index("crux_configuration_public_target()\n"))

    def test_the_kconfig_help_of_each_symbol_no_longer_says_it_adds_no_target(self):
        kconfig = (ROOT / "zephyr/Kconfig").read_text()
        for name, case in CASES.items():
            block = " ".join(re.search(rf"config {case[8]}\n(.*?)\n(?:menu)?config ", kconfig, re.S).group(1).split())
            with self.subTest(component=name):
                self.assertNotIn("adds no crux:: target", block)
                self.assertNotIn("no public header", block)
                self.assertIn(case[3], block)


def demote(text):
    return re.sub(r'message\(FATAL_ERROR "(native consumer requirement|Access adapter header reachable'
                  r'|Credential adapter header reachable)', r'message(STATUS "\1', text)


def project():
    lines = ["cmake_minimum_required(VERSION 3.28)", "project(probe LANGUAGES C)",
             'include("@GUARDS@/CruxConsumerBoundary.cmake")', 'include("@GUARDS@/CruxAccessBoundary.cmake")',
             'include("@GUARDS@/CruxCredentialBoundary.cmake")']
    for name in ORDER:
        lines.append(f'set({DIR_VARIABLES[name]} "{COMPONENTS / name}")')
    for alias, component in (("access", "access"), ("base", "base"), ("system", "system"), ("file", "file")):
        lines += [f"add_library(mock_{alias} INTERFACE)",
                  f'target_include_directories(mock_{alias} INTERFACE "{COMPONENTS}/{component}/include")',
                  f"add_library(crux::{alias} ALIAS mock_{alias})"]
    for name in ORDER:
        lines += [function_text(name), f"{CASES[name][1]}()"]
    lines.append('file(WRITE "${CMAKE_BINARY_DIR}/main.c" "int main(void) { return 0; }\\n")')
    return "\n".join(lines) + "\n"


TARGETS = [CASES[name][3] for name in ORDER]
PORTABLE_CONSUMER = ('add_executable(app "${CMAKE_BINARY_DIR}/main.c")\n'
                     f'target_link_libraries(app PRIVATE {" ".join(TARGETS)})\n'
                     "crux_assert_portable_consumer(app)\n"
                     f'crux_assert_portable_usage({" ".join(TARGETS)})\n'
                     f'crux_assert_access_adapter_unreachable({" ".join(TARGETS)})\n'
                     f'crux_assert_credential_adapter_unreachable({" ".join(TARGETS)})\n'
                     "crux_assert_access_consumer(app)\ncrux_assert_credential_consumer(app)\n")


def escapes():
    found = {"the Access adapter directory on the include path": (
        f'add_executable(app "${{CMAKE_BINARY_DIR}}/main.c")\ntarget_link_libraries(app PRIVATE {TARGETS[1]})\n'
        f'target_include_directories(app PRIVATE "{COMPONENTS}/access/adapter")\n'
        "crux_assert_access_consumer(app)\n", "Access adapter header reachable", "CruxAccessBoundary.cmake")}
    for name in ORDER:
        alias = CASES[name][3]
        found[f"a provider source directory through {alias}"] = (
            f"add_library(product_{name} INTERFACE)\ntarget_link_libraries(product_{name} INTERFACE {alias})\n"
            f'target_include_directories(product_{name} INTERFACE "{COMPONENTS}/{name}/src")\n'
            f"crux_assert_portable_usage(product_{name})\n", "native consumer requirement",
            "CruxConsumerBoundary.cmake")
        found[f"the native provider library through {alias}"] = (
            f"add_library(zephyr_interface_{name} INTERFACE)\nadd_library(zephyr_interface INTERFACE)\n"
            f"add_library(product_{name} INTERFACE)\n"
            f"target_link_libraries(product_{name} INTERFACE {alias} zephyr_interface)\n"
            f"crux_assert_portable_usage(product_{name})\n", "native consumer requirement",
            "CruxConsumerBoundary.cmake")
    return found


@unittest.skipUnless(CMAKE and all(function_text(n) for n in ORDER), "CMake and the target definitions are required")
class GuardsAcceptThePortableTargetsAndRefuseEverythingPast(unittest.TestCase):
    def configure(self, body, weaken=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = ROOT / "cmake"
            if weaken is not None:
                directory = root / "cmake"
                directory.mkdir()
                for name, path in GUARDS.items():
                    text = path.read_text().replace("${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../", f"{ROOT}/")
                    if name == weaken:
                        changed = demote(text)
                        self.assertNotEqual(changed, text, "the weakening changed nothing: " + name)
                        text = changed
                    (directory / name).write_text(text)
            (root / "CMakeLists.txt").write_text(project().replace("@GUARDS@", str(directory)) + body)
            result = subprocess.run([CMAKE, "-S", str(root), "-B", str(root / "build")],
                                    capture_output=True, text=True)
        return result, result.stdout + result.stderr

    def test_the_mock_carries_the_real_definitions(self):
        result, output = self.configure("")
        self.assertEqual(result.returncode, 0, output)

    def test_a_portable_consumer_of_the_six_targets_passes_every_check(self):
        result, output = self.configure(PORTABLE_CONSUMER)
        self.assertEqual(result.returncode, 0, output)
        for rejection in ("native consumer requirement", "adapter header reachable"):
            self.assertNotIn(rejection, output)

    def test_every_way_past_a_target_is_rejected(self):
        for name, (body, message, _guard) in escapes().items():
            with self.subTest(escape=name):
                result, output = self.configure(body)
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn(message, output)

    def test_an_unweakened_copy_of_the_guards_still_rejects_each_escape(self):
        for name, (body, message, _guard) in escapes().items():
            with self.subTest(escape=name):
                result, output = self.configure(body, weaken="copy")
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn(message, output)

    def test_each_escape_passes_against_the_guard_that_it_needs_weakened(self):
        for name, (body, _message, guard) in escapes().items():
            with self.subTest(escape=name, weakened=guard):
                result, output = self.configure(body, weaken=guard)
                self.assertEqual(result.returncode, 0, output)


if __name__ == "__main__":
    unittest.main()
