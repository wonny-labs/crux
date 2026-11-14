"""The public TLS certificate start and material interface (ADR-0004, T2, phase 1a PR 2).

These checks run on the host. They compile the new header alone, read the CMake definition of the public
target that the Zephyr module creates, and hold the private adapter header to declaring nothing a second
time. They show that a product reaches `crux_tls_certificate_start`, the material calls and the
fingerprint through `<crux/tls_certificate_start.h>` and `crux::tls_certificate` alone, that the header
pulls in only the capability's own Crux headers and no frozen or native header, and that
`<crux/tls_certificate.h>` keeps its promise that no operation there returns the private key.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = ROOT / "components/tls_certificate"
INCLUDE = COMPONENT / "include"
START = INCLUDE / "crux/tls_certificate_start.h"
STATE = INCLUDE / "crux/tls_certificate.h"
ADAPTER = COMPONENT / "adapter/crux_tls_certificate_adapter.h"
PORT_CMAKE = COMPONENT / "ports/zephyr/CMakeLists.txt"
CC = os.environ.get("CC", "cc")
FLAGS = ["-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror"]
FROZEN = ("thread.h", "sync.h", "queue.h", "serial.h")
ROOTS = [INCLUDE, ROOT / "components/access/include"]

# Everything ADR-0004 section 2 lists for the TLS certificate, with the types that these take.
FUNCTIONS = ("crux_tls_certificate_start", "crux_tls_certificate_on_change",
             "crux_tls_certificate_material_take", "crux_tls_certificate_material_release",
             "crux_tls_certificate_fingerprint")
TYPES = ("crux_tls_certificate_options_t", "crux_tls_certificate_material_t",
         "crux_tls_certificate_start_t")
USES = """
crux_tls_certificate_result_t (*start)(const crux_tls_certificate_options_t *,
                                       crux_tls_certificate_start_t *) = crux_tls_certificate_start;
void (*on_change)(void (*)(void *), void *) = crux_tls_certificate_on_change;
crux_tls_certificate_result_t (*take)(crux_tls_certificate_material_t *) =
    crux_tls_certificate_material_take;
crux_tls_certificate_result_t (*release)(const crux_tls_certificate_material_t *) =
    crux_tls_certificate_material_release;
crux_tls_certificate_result_t (*fingerprint)(char *) = crux_tls_certificate_fingerprint;
int main(void) { return start && on_change && take && release && fingerprint ? 0 : 1; }
"""


def compile_source(source, roots, extra=()):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "tu.c"
        path.write_text(source)
        command = [CC, *FLAGS, *extra, *[arg for root in roots for arg in ("-I", str(root))],
                   "-fsyntax-only", str(path)]
        return subprocess.run(command, capture_output=True, text=True)


class PublicHeader(unittest.TestCase):
    def test_the_header_exists_and_compiles_alone_with_its_own_roots(self):
        self.assertTrue(START.is_file())
        result = compile_source("#include <crux/tls_certificate_start.h>\n" + USES, ROOTS)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_header_pulls_in_only_the_capabilitys_crux_headers(self):
        result = compile_source("#include <crux/tls_certificate_start.h>\n" + USES, ROOTS, ["-H"])
        self.assertEqual(result.returncode, 0, result.stderr)
        included = [line.lstrip(". ").strip() for line in result.stderr.splitlines() if line.startswith(".")]
        crux = {Path(path).name for path in included if "/crux/" in path}
        self.assertEqual(crux, {"tls_certificate_start.h", "tls_certificate.h", "access.h"})
        for name in crux:
            self.assertNotIn(name, FROZEN)
        for path in [p for p in included if not p.startswith(str(ROOT))]:
            self.assertNotRegex(path.lower(), r"zephyr|nxp|cmsis|mcux|/boards?/|wolf|mbedtls|psa")

    def test_the_header_names_no_credential_frozen_or_native_header(self):
        text = START.read_text()
        for pattern in (r"crux_credential", r"crux/credential", r"crux/(thread|sync|queue|serial)\.h",
                        r"#\s*include\s*[<\"](zephyr|wolf|mbedtls|psa)/"):
            self.assertNotRegex(text, pattern)

    def test_it_declares_everything_adr_0004_lists_and_no_other_function(self):
        text = START.read_text()
        for name in (*FUNCTIONS, *TYPES):
            self.assertRegex(text, rf"\b{name}\b", name)
        # Without comments and preprocessor lines, a declaration is a name, its parameters and a
        # semicolon, over any number of lines. Typedefs and macros do not match.
        code = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        code = re.sub(r"^#.*$", "", code, flags=re.M)
        declared = re.findall(r"\b(crux_\w+)\s*\([^;{]*\)\s*;", code)
        self.assertEqual(sorted(set(declared)), sorted(FUNCTIONS))

    def test_the_private_header_declares_nothing_a_second_time(self):
        text = ADAPTER.read_text()
        for name in FUNCTIONS:
            self.assertNotRegex(text, rf"\b{name}\s*\(", name)
        self.assertNotRegex(text, r"\}\s*crux_tls_certificate_(options|material|start)_t\s*;")
        self.assertRegex(text, r"#include\s+<crux/tls_certificate_start\.h>")

    def test_the_private_header_still_compiles_for_existing_compositions(self):
        result = compile_source('#include "crux_tls_certificate_adapter.h"\n' + USES,
                                [COMPONENT / "adapter", *ROOTS])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_state_header_keeps_its_promise_about_the_private_key(self):
        text = " ".join(STATE.read_text().replace("\n *", " ").split())
        self.assertIn("No operation here returns the private key, and no output holds it", text)
        for name in (*FUNCTIONS, *TYPES):
            self.assertNotRegex(STATE.read_text(), rf"\b{name}\b", name)
        self.assertNotIn("private_key", STATE.read_text())

    def test_the_new_header_says_where_the_key_goes_and_who_clears_it(self):
        text = " ".join(START.read_text().replace("\n *", " ").split())
        for phrase in ("PKCS #8", "tls_credential_add", "same image", "no management route",
                       "Thread context only", "must return before any other operation",
                       "crux_tls_certificate_material_release", "CRUX_TLS_CERTIFICATE_ERR_BUSY"):
            self.assertIn(phrase, text, phrase)

    def test_the_header_names_its_tier(self):
        self.assertRegex(START.read_text().split("*/", 1)[0], r"Status:\s+Experimental")

    def test_lines_fit_the_column_limit_of_the_format_check(self):
        for path in (START, ADAPTER):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                self.assertLessEqual(len(line), 100, f"{path.name}:{number}")

    def test_the_header_is_usable_from_c_plus_plus(self):
        self.assertIn('extern "C" {', START.read_text())

    def test_the_public_path_is_unique_across_components(self):
        found = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "components").rglob(START.name))
        self.assertEqual(found, [START.relative_to(ROOT).as_posix()])


class PublicTarget(unittest.TestCase):
    text = PORT_CMAKE.read_text()

    @classmethod
    def body(cls):
        match = re.search(r"function\(crux_tls_certificate_public_target\)(.*?)endfunction\(\)",
                          cls.text, re.S)
        return match.group(1) if match else None

    def test_the_port_defines_the_target_as_a_function_and_calls_it_once(self):
        self.assertIsNotNone(self.body())
        self.assertEqual(len(re.findall(r"^crux_tls_certificate_public_target\(\)\s*$", self.text, re.M)), 1)

    def test_the_target_is_an_interface_library_with_a_crux_alias(self):
        text = self.body() or ""
        self.assertIn("add_library(crux_tls_certificate INTERFACE)", text)
        self.assertIn("add_library(crux::tls_certificate ALIAS crux_tls_certificate)", text)

    def test_the_target_exposes_the_include_root_and_the_access_contract_only(self):
        text = self.body() or ""
        self.assertIn('"${CRUX_TLS_CERTIFICATE_COMPONENT_DIR}/include"', text)
        for forbidden in ("/src", "/adapter", "/ports", "credential", "zephyr_interface", "PUBLIC",
                          "crux_tls_certificate_zephyr", "target_link_options", "target_compile"):
            self.assertNotIn(forbidden, text)
        linked = {word for entry in re.findall(r"target_link_libraries\(\w+ INTERFACE ([^)]*)\)", text)
                  for word in entry.split()}
        self.assertEqual(linked, {"crux::access"})

    def test_the_target_needs_crux_access_and_the_module_defines_it(self):
        # The target links crux::access, which only the module's Access port defines, under
        # CONFIG_CRUX_ACCESS, which CONFIG_CRUX_TLS_CERTIFICATE depends on. PR 1 added it, so this
        # change builds on that one, and the port refuses a configuration without it by name.
        access = (ROOT / "components/access/ports/zephyr/CMakeLists.txt").read_text()
        self.assertIn("add_library(crux::access ALIAS", access)
        self.assertRegex(self.body() or "", r"if\(NOT TARGET crux::access\)\s*message\(FATAL_ERROR")
        kconfig = (ROOT / "zephyr/Kconfig").read_text()
        block = re.search(r"config CRUX_TLS_CERTIFICATE\n(.*?)\nconfig ", kconfig, re.S).group(1)
        self.assertRegex(block, r"depends on [^\n]*CRUX_ACCESS")

    def test_the_texts_about_the_key_agree_with_the_header_that_hands_it_out(self):
        start = " ".join(START.read_text().replace("\n *", " ").split())
        self.assertNotIn("No public operation of the module", start)
        self.assertIn("crux_tls_certificate_material_take() hands it only to the image's TLS registration", start)
        doc = " ".join((ROOT / "docs/tls-certificate.md").read_text().split())
        self.assertNotIn("No public operation returns it", doc)
        self.assertIn("The one accepted exception is `crux_tls_certificate_material_take()`", doc)

    def test_the_provider_library_is_not_linked_by_the_target(self):
        self.assertIn("zephyr_append_cmake_library", self.text)
        self.assertNotIn("zephyr_append_cmake_library", self.body() or "")

    def test_the_port_checks_the_target_with_the_three_guards(self):
        for check in ("crux_assert_portable_usage", "crux_assert_access_adapter_unreachable",
                      "crux_assert_credential_adapter_unreachable"):
            self.assertIn(f"DEFER CALL {check} crux::tls_certificate", self.text, check)

    def test_the_include_root_uses_a_variable_that_the_file_defines(self):
        used = re.findall(r'"\$\{(CRUX_\w+_COMPONENT_DIR)\}/include"', self.body() or "")
        self.assertTrue(used)
        for variable in used:
            self.assertRegex(self.text, rf'get_filename_component\({variable} "\$\{{CMAKE_CURRENT_LIST_DIR\}}/\.\./\.\."')

    def test_the_host_target_carries_the_new_header_through_the_same_include_root(self):
        text = (COMPONENT / "CMakeLists.txt").read_text()
        self.assertIn("target_include_directories(crux_tls_certificate_api INTERFACE include)", text)


class Texts(unittest.TestCase):
    def test_the_kconfig_help_no_longer_says_the_header_is_private(self):
        text = (ROOT / "zephyr/Kconfig").read_text()
        match = re.search(r"config CRUX_TLS_CERTIFICATE\n(.*?)\nconfig ", text, re.S)
        block = " ".join(match.group(1).split())
        self.assertNotIn("adds no crux:: target and no public header", block)
        self.assertNotIn("is private, on purpose", block)
        self.assertIn("crux::tls_certificate", block)
        self.assertIn("<crux/tls_certificate_start.h>", block)

    def test_the_port_comment_no_longer_says_it_adds_no_target(self):
        text = PORT_CMAKE.read_text()
        self.assertNotIn("adds no target either", text)
        self.assertNotIn("No crux:: target and no public header", text)


if __name__ == "__main__":
    unittest.main()
