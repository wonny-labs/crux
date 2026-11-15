"""The public web session and web management lifecycle interface (ADR-0004, T2, phase 1a PR 4).

These checks run on the host, without a Zephyr SDK. They compile the new headers alone, read the CMake
definitions of the two public targets that the Zephyr module creates, and hold the private headers to
declaring nothing a second time. They show that a product reaches the session and management lifecycle
through `<crux/web_session.h>`, `<crux/web_management.h>`, `crux::web_session` and `crux::web_management`
alone, that these are ordinary service API (they bind nothing to Zephyr, so no `_zephyr` name and no
composition interface), that the headers pull in only the web contract and the Access types it names, and
that the authentication types which `crux_web_config_t` of the next change needs now sit in the public
`<crux/web.h>` without exposing the request head's fields.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "components/web"
INCLUDE = WEB / "include"
WEB_H = INCLUDE / "crux/web.h"
SESSION = INCLUDE / "crux/web_session.h"
MANAGEMENT = INCLUDE / "crux/web_management.h"
PRIVATE_SESSION = WEB / "session/crux_web_session.h"
PRIVATE_MANAGEMENT = WEB / "management/crux_web_management.h"
ADAPTER = WEB / "adapter/crux_web_adapter.h"
SESSION_CMAKE = WEB / "ports/zephyr/session/CMakeLists.txt"
MANAGEMENT_CMAKE = WEB / "ports/zephyr/management/CMakeLists.txt"
CC = os.environ.get("CC", "cc")
FLAGS = ["-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror"]
FROZEN = ("thread.h", "sync.h", "queue.h", "serial.h")
ROOTS = [INCLUDE, ROOT / "components/access/include"]

# What ADR-0004 section 2 lists, with the three names that these two headers cannot work without: the
# session settings type, the function that fills crux_web_config_t.authenticate, and the save query that
# the reboot wait calls. Nothing else of the private headers is public.
SESSION_FUNCTIONS = ("crux_web_session_init", "crux_web_session_start_worker",
                     "crux_web_session_authenticate")
MANAGEMENT_FUNCTIONS = ("crux_web_management_init", "crux_web_management_start_worker",
                        "crux_web_management_save_pending")
PRIVATE_ONLY = ("crux_web_session_stats_get", "crux_web_management_stats_get")

SESSION_USES = """
#include <crux/web_session.h>
static const crux_web_session_config_t settings = {.scheme = "https", .origins = 0, .origin_count = 0};
crux_web_result_t (*init)(const crux_web_session_config_t *) = crux_web_session_init;
crux_web_result_t (*worker)(void) = crux_web_session_start_worker;
crux_web_authenticate_t authenticate = crux_web_session_authenticate;
int main(void) { return init && worker && authenticate && settings.scheme ? 0 : 1; }
"""
MANAGEMENT_USES = """
#include <crux/web_management.h>
crux_web_result_t (*init)(void) = crux_web_management_init;
crux_web_result_t (*worker)(void) = crux_web_management_start_worker;
bool (*pending)(void) = crux_web_management_save_pending;
int main(void) { return init && worker && pending ? 0 : 1; }
"""


def compile_source(source, roots, extra=()):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "tu.c"
        path.write_text(source)
        command = [CC, *FLAGS, *extra, *[arg for root in roots for arg in ("-I", str(root))],
                   "-fsyntax-only", str(path)]
        return subprocess.run(command, capture_output=True, text=True)


def declared_functions(path):
    """Names declared as functions: a name, its parameters and a semicolon, outside comments and macros."""
    code = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
    code = re.sub(r"^#.*$", "", code, flags=re.M)
    return sorted(set(re.findall(r"\b(crux_\w+)\s*\([^;{]*\)\s*;", code)))


def words(path):
    return " ".join(path.read_text().replace("\n *", " ").split())


class PublicHeaders(unittest.TestCase):
    def test_the_headers_exist_and_compile_alone_with_their_own_roots(self):
        for header, uses in ((SESSION, SESSION_USES), (MANAGEMENT, MANAGEMENT_USES)):
            with self.subTest(header=header.name):
                self.assertTrue(header.is_file())
                result = compile_source(uses, ROOTS)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_headers_pull_in_only_the_web_contract_and_its_access_types(self):
        for header, uses in ((SESSION, SESSION_USES), (MANAGEMENT, MANAGEMENT_USES)):
            with self.subTest(header=header.name):
                result = compile_source(uses, ROOTS, ["-H"])
                self.assertEqual(result.returncode, 0, result.stderr)
                included = [line.lstrip(". ").strip() for line in result.stderr.splitlines()
                            if line.startswith(".")]
                crux = {Path(path).name for path in included if "/crux/" in path}
                self.assertEqual(crux, {header.name, "web.h", "access.h"})
                for name in crux:
                    self.assertNotIn(name, FROZEN)
                for path in [p for p in included if not p.startswith(str(ROOT))]:
                    self.assertNotRegex(path.lower(), r"zephyr|nxp|cmsis|mcux|/boards?/|wolf|mbedtls|psa")

    def test_the_headers_include_no_private_zephyr_frozen_or_native_header(self):
        for header in (SESSION, MANAGEMENT):
            text = header.read_text()
            for pattern in (r"crux_web_adapter", r"crux_web_session\.h", r"crux_web_management\.h",
                            r"crux/(thread|sync|queue|serial)\.h", r"web_zephyr",
                            r"#\s*include\s*[<\"](zephyr|wolf|mbedtls|psa)/"):
                self.assertNotRegex(text, pattern, f"{header.name}: {pattern}")

    def test_they_declare_what_adr_0004_lists_and_nothing_else(self):
        self.assertEqual(declared_functions(SESSION), sorted(SESSION_FUNCTIONS))
        self.assertEqual(declared_functions(MANAGEMENT), sorted(MANAGEMENT_FUNCTIONS))
        self.assertRegex(SESSION.read_text(), r"\}\s*crux_web_session_config_t\s*;")

    def test_the_private_headers_declare_nothing_a_second_time_and_keep_the_stats(self):
        for private, functions, stats in ((PRIVATE_SESSION, SESSION_FUNCTIONS, "crux_web_session_stats_get"),
                                          (PRIVATE_MANAGEMENT, MANAGEMENT_FUNCTIONS,
                                           "crux_web_management_stats_get")):
            with self.subTest(header=private.name):
                text = private.read_text()
                for name in functions:
                    self.assertNotRegex(text, rf"\b{name}\s*\(", name)
                self.assertRegex(text, rf"\b{stats}\s*\(")
        self.assertNotRegex(PRIVATE_SESSION.read_text(), r"\}\s*crux_web_session_config_t\s*;")
        self.assertRegex(PRIVATE_SESSION.read_text(), r"#include\s+<crux/web_session\.h>")
        self.assertRegex(PRIVATE_MANAGEMENT.read_text(), r"#include\s+<crux/web_management\.h>")

    def test_the_stats_functions_are_not_public(self):
        for name in PRIVATE_ONLY:
            for header in (SESSION, MANAGEMENT):
                self.assertNotIn(name, header.read_text())

    def test_the_private_headers_still_compile_for_existing_compositions(self):
        for private, adapter_dirs in ((PRIVATE_SESSION, [WEB / "session", WEB / "adapter"]),
                                      (PRIVATE_MANAGEMENT, [WEB / "management", WEB / "adapter"])):
            with self.subTest(header=private.name):
                result = compile_source(f'#include "{private.name}"\n' + "int main(void) { return 0; }\n",
                                        [*adapter_dirs, *ROOTS])
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_header_guards_differ_from_the_private_ones(self):
        self.assertRegex(SESSION.read_text(), r"#ifndef CRUX_WEB_SESSION_API_H")
        self.assertRegex(MANAGEMENT.read_text(), r"#ifndef CRUX_WEB_MANAGEMENT_API_H")
        self.assertIn("#ifndef CRUX_WEB_SESSION_H", PRIVATE_SESSION.read_text())
        self.assertIn("#ifndef CRUX_WEB_MANAGEMENT_H", PRIVATE_MANAGEMENT.read_text())

    def test_the_headers_name_their_tier_and_are_ordinary_service_api(self):
        for header in (SESSION, MANAGEMENT):
            self.assertRegex(header.read_text().split("*/", 1)[0], r"Status:\s+Experimental")
            self.assertRegex(words(header), r"not Zephyr-bound|binds nothing to Zephyr")

    def test_the_headers_say_the_order_and_the_thread(self):
        session = words(SESSION)
        for phrase in ("after crux_access_init()", "before crux_web_start()", "on one thread"):
            self.assertIn(phrase, session, phrase)
        management = words(MANAGEMENT)
        for phrase in ("after the services have started", "before crux_web_start()", "on one thread"):
            self.assertIn(phrase, management, phrase)

    def test_lines_fit_the_column_limit_of_the_format_check(self):
        for path in (SESSION, MANAGEMENT, WEB_H, PRIVATE_SESSION, PRIVATE_MANAGEMENT, ADAPTER):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                self.assertLessEqual(len(line), 100, f"{path.name}:{number}")

    def test_the_headers_are_usable_from_c_plus_plus(self):
        for header in (SESSION, MANAGEMENT):
            self.assertIn('extern "C" {', header.read_text())

    def test_the_public_paths_are_unique_across_components(self):
        for header in (SESSION, MANAGEMENT):
            found = sorted(p.relative_to(ROOT).as_posix()
                           for p in (ROOT / "components").rglob(header.name))
            self.assertEqual(found, [header.relative_to(ROOT).as_posix()])


class AuthenticationTypes(unittest.TestCase):
    def test_web_h_carries_the_authentication_types_without_the_heads_fields(self):
        text = WEB_H.read_text()
        self.assertRegex(text, r"typedef struct crux_web_request_head crux_web_request_head_t;")
        self.assertRegex(text, r"\}\s*crux_web_auth_t\s*;")
        self.assertRegex(text, r"typedef crux_web_auth_t \(\*crux_web_authenticate_t\)")
        for field in ("cookie", "xsrf_token", "content_length", "headers_incomplete", "source_length"):
            self.assertNotIn(field, text)

    def test_the_adapter_header_keeps_the_fields_and_declares_the_types_once(self):
        text = ADAPTER.read_text()
        self.assertRegex(text, r"struct crux_web_request_head \{")
        self.assertNotRegex(text, r"\}\s*crux_web_request_head_t\s*;")
        self.assertNotRegex(text, r"\}\s*crux_web_auth_t\s*;")
        self.assertNotRegex(text, r"typedef crux_web_auth_t \(\*crux_web_authenticate_t\)")

    def test_a_public_user_cannot_read_a_field_of_the_request_head(self):
        result = compile_source("#include <crux/web.h>\n"
                                "int main(const crux_web_request_head_t *head) { return head->host != 0; }\n",
                                ROOTS)
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr, r"incomplete|member")

    def test_the_adapter_header_still_compiles_with_the_fields(self):
        result = compile_source('#include "crux_web_adapter.h"\n'
                                "int main(void) { crux_web_request_head_t head = {0}; return head.host != 0; }\n",
                                [WEB / "adapter", *ROOTS])
        self.assertEqual(result.returncode, 0, result.stderr)


class PublicTargets(unittest.TestCase):
    cases = (
        ("session", SESSION_CMAKE, "crux_web_session", "web_session", "CRUX_WEB_SESSION"),
        ("management", MANAGEMENT_CMAKE, "crux_web_management", "web_management", "CRUX_WEB_MANAGEMENT"),
    )

    @staticmethod
    def body(text, name):
        match = re.search(rf"function\({name}_public_target\)(.*?)endfunction\(\)", text, re.S)
        return match.group(1) if match else None

    def test_each_port_defines_its_target_as_a_function_and_calls_it_once(self):
        for label, path, name, _alias, _symbol in self.cases:
            with self.subTest(target=label):
                text = path.read_text()
                self.assertIsNotNone(self.body(text, name))
                self.assertEqual(len(re.findall(rf"^{name}_public_target\(\)\s*$", text, re.M)), 1)

    def test_each_target_is_an_interface_library_with_a_crux_alias(self):
        for label, path, name, alias, _symbol in self.cases:
            with self.subTest(target=label):
                body = self.body(path.read_text(), name) or ""
                self.assertIn(f"add_library({name} INTERFACE)", body)
                self.assertIn(f"add_library(crux::{alias} ALIAS {name})", body)

    def test_each_target_links_crux_web_only_and_names_no_private_directory(self):
        for label, path, name, alias, _symbol in self.cases:
            with self.subTest(target=label):
                body = self.body(path.read_text(), name) or ""
                for forbidden in ("/src", "/adapter", "/session", "/management", "/ports", "/assets",
                                  "zephyr_interface", "PUBLIC", "_zephyr", "zephyr_append_cmake_library",
                                  "target_link_options", "target_compile", "target_include_directories"):
                    self.assertNotIn(forbidden, body, forbidden)
                linked = {word for entry in re.findall(r"target_link_libraries\(\w+ INTERFACE ([^)]*)\)", body)
                          for word in entry.split()}
                self.assertEqual(linked, {"crux::web"})

    def test_each_target_refuses_a_configuration_without_crux_web_by_name(self):
        for label, path, name, alias, _symbol in self.cases:
            with self.subTest(target=label):
                body = self.body(path.read_text(), name) or ""
                self.assertRegex(body, r"if\(NOT TARGET crux::web\)\s*message\(FATAL_ERROR \"crux::" + alias)

    def test_the_target_comes_from_the_ports_that_the_module_adds_after_crux_web(self):
        module = (ROOT / "zephyr/CMakeLists.txt").read_text()
        web = module.index("components/web/ports/zephyr\"")
        self.assertGreater(module.index("components/web/ports/zephyr/session\""), web)
        self.assertGreater(module.index("components/web/ports/zephyr/management\""), web)
        port = (WEB / "ports/zephyr/CMakeLists.txt").read_text()
        self.assertIn("add_library(crux::web ALIAS crux_web)", port)

    def test_the_provider_libraries_are_not_linked_by_the_targets(self):
        for label, path, name, _alias, _symbol in self.cases:
            with self.subTest(target=label):
                text = path.read_text()
                self.assertIn("zephyr_append_cmake_library", text)
                self.assertNotIn("zephyr_append_cmake_library", self.body(text, name) or "")

    def test_each_port_checks_its_target_with_the_guards(self):
        for label, path, _name, alias, _symbol in self.cases:
            with self.subTest(target=label):
                text = path.read_text()
                for check in ("crux_assert_portable_usage", "crux_assert_access_adapter_unreachable",
                              "crux_assert_web_internal_unreachable"):
                    self.assertIn(f"DEFER CALL {check} crux::{alias}", text, check)
                self.assertIn("CruxWebBoundary.cmake", text)
                self.assertIn("CruxAccessBoundary.cmake", text)

    def test_the_porting_comments_no_longer_say_there_is_no_target_or_header(self):
        for label, path, _name, _alias, _symbol in self.cases:
            with self.subTest(target=label):
                self.assertNotIn("No crux:: target and no public header", path.read_text())

    def test_the_kconfig_help_names_the_target_and_the_header(self):
        kconfig = (ROOT / "zephyr/Kconfig").read_text()
        for _label, _path, _name, alias, symbol in self.cases:
            block = re.search(rf"config {symbol}\n(.*?)\nconfig ", kconfig, re.S).group(1)
            block = " ".join(block.split())
            self.assertNotIn("adds no crux:: target and no public header", block)
            self.assertIn(f"crux::{alias}", block)
            self.assertIn(f"<crux/{alias}.h>", block)

    def test_the_docs_row_of_each_symbol_names_the_target(self):
        text = (ROOT / "docs/management-in-a-product.md").read_text()
        for _label, _path, _name, alias, symbol in self.cases:
            row = next(line for line in text.splitlines() if line.startswith(f"| `{symbol}` |"))
            self.assertIn(f"crux::{alias}", row)

    def test_the_two_docs_that_called_the_headers_internal_say_where_the_public_part_is(self):
        for doc, name in (("docs/web-session.md", "web_session"), ("docs/web-management-apis.md", "web_management")):
            text = " ".join((ROOT / doc).read_text().split())
            self.assertIn(f"<crux/{name}.h>", text, doc)


if __name__ == "__main__":
    unittest.main()
