"""The Zephyr web start is a documented composition interface, reachable through a public target (ADR-0004, T2, phase 1a PR 5).

`<crux/web_zephyr.h>` and `crux::web_zephyr` are the one composition interface that ADR-0004 route A adds
(section 2): `crux_web_start` binds the management web server to Zephyr's HTTP server, its sockets and its
TLS security tag. These checks run on the host. They compile the header alone, read the CMake definition of
the target, and hold the private adapter header to the same declaration. The Zephyr builds that use the
target are exercised by the Zephyr CI shards.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "components/web"
PORT = WEB / "ports/zephyr"
PUBLIC_INCLUDE = PORT / "include"
HEADER = PUBLIC_INCLUDE / "crux/web_zephyr.h"
WEB_H = WEB / "include/crux/web.h"
ADAPTER = WEB / "adapter/crux_web_adapter.h"
CC = os.environ.get("CC", "cc")
FLAGS = ["-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror"]
FROZEN = ("thread.h", "sync.h", "queue.h", "serial.h")
ROOTS = [PUBLIC_INCLUDE, WEB / "include", ROOT / "components/access/include"]
USES = """
#include <crux/web_zephyr.h>
static crux_web_auth_t refuse(const crux_web_request_head_t *head, crux_access_session_t *session,
                              void *context) {
    (void)head; (void)session; (void)context;
    return CRUX_WEB_AUTH_NO_SESSION;
}
static const crux_web_config_t config = {.authenticate = refuse, .authenticate_context = 0,
                                         .request_deadline_ms = 5000u, .handler_limit_ms = 100u};
crux_web_result_t (*start)(const crux_web_config_t *) = crux_web_start;
int main(void) { return start && config.authenticate ? 0 : 1; }
"""


def compile_source(source, roots, extra=()):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "tu.c"
        path.write_text(source)
        command = [CC, *FLAGS, *extra, *[arg for root in roots for arg in ("-I", str(root))],
                   "-fsyntax-only", str(path)]
        return subprocess.run(command, capture_output=True, text=True)


def prototype(path, name):
    code = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
    code = re.sub(r"^#.*$", "", code, flags=re.M)
    match = re.search(rf"[\w\s*]+\b{name}\s*\([^;{{]*\)\s*;", code)
    return " ".join(match.group(0).split()) if match else None


class PublicHeader(unittest.TestCase):
    def test_the_header_exists_under_the_composition_path_and_compiles_alone(self):
        self.assertEqual(HEADER.relative_to(ROOT).as_posix(),
                         "components/web/ports/zephyr/include/crux/web_zephyr.h")
        self.assertTrue(HEADER.is_file())
        result = compile_source(USES, ROOTS)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_header_includes_no_native_or_frozen_header_and_no_adapter(self):
        result = compile_source(USES, ROOTS, ["-H"])
        self.assertEqual(result.returncode, 0, result.stderr)
        included = [line.lstrip(". ").strip() for line in result.stderr.splitlines() if line.startswith(".")]
        crux = {Path(path).name for path in included if "/crux/" in path}
        self.assertEqual(crux, {"web_zephyr.h", "web.h", "access.h"})
        for name in crux:
            self.assertNotIn(name, FROZEN)
        for path in [p for p in included if not p.startswith(str(ROOT))]:
            self.assertNotRegex(path.lower(), r"zephyr|nxp|cmsis|mcux|/boards?/|wolf|mbedtls|psa")
        text = HEADER.read_text()
        for pattern in (r"crux_web_adapter", r"#\s*include\s*[<\"][^>\"]*web_(session|management)",
                        r"crux/(thread|sync|queue|serial)\.h",
                        r"#\s*include\s*[<\"](zephyr|wolf|mbedtls|psa)/"):
            self.assertNotRegex(text, pattern)

    def test_it_declares_crux_web_start_and_no_other_function(self):
        code = re.sub(r"/\*.*?\*/", "", HEADER.read_text(), flags=re.S)
        code = re.sub(r"^#.*$", "", code, flags=re.M)
        self.assertEqual(sorted(set(re.findall(r"\b(crux_\w+)\s*\([^;{]*\)\s*;", code))), ["crux_web_start"])

    def test_the_config_type_is_public_in_web_h_and_not_declared_twice(self):
        text = WEB_H.read_text()
        self.assertRegex(text, r"\}\s*crux_web_config_t\s*;")
        for field in ("authenticate", "authenticate_context", "request_deadline_ms", "handler_limit_ms"):
            self.assertRegex(text, rf"\b{field}\b")
        self.assertNotRegex(ADAPTER.read_text(), r"\}\s*crux_web_config_t\s*;")
        self.assertNotRegex(HEADER.read_text(), r"\}\s*crux_web_config_t\s*;")

    def test_the_private_adapter_header_declares_the_same_prototype(self):
        # Existing compositions include only the adapter header and call crux_web_start(), so the adapter
        # keeps its declaration. The two must not drift: C allows the repeat only when they agree.
        public = prototype(HEADER, "crux_web_start")
        private = prototype(ADAPTER, "crux_web_start")
        self.assertIsNotNone(public)
        self.assertEqual(public, private)
        result = compile_source('#include "crux_web_adapter.h"\n#include <crux/web_zephyr.h>\n'
                                "int main(void) { return crux_web_start(0) == CRUX_WEB_OK; }\n",
                                [WEB / "adapter", *ROOTS])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_private_adapter_header_still_compiles_for_existing_compositions(self):
        result = compile_source('#include "crux_web_adapter.h"\n'
                                "static const crux_web_config_t c = {0};\n"
                                "int main(void) { crux_web_core_init(&c); return crux_web_start(&c) == 0; }\n",
                                [WEB / "adapter", WEB / "include", ROOT / "components/access/include"])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_header_names_its_tier_and_says_what_it_binds(self):
        self.assertRegex(HEADER.read_text().split("*/", 1)[0], r"Status:\s+Experimental")
        text = " ".join(HEADER.read_text().replace("\n *", " ").split())
        for phrase in ("composition interface", "Zephyr HTTP server", "crux::web_zephyr",
                       "not a portable", "then crux_web_start()", "TLS security tag"):
            self.assertIn(phrase, text, phrase)

    def test_the_header_says_the_order_the_start_can_fail_and_the_thread(self):
        text = " ".join(HEADER.read_text().replace("\n *", " ").split())
        for phrase in ("crux_web_session_init()", "crux_web_management_init()", "one thread",
                       "CRUX_WEB_OK"):
            self.assertIn(phrase, text, phrase)

    def test_lines_fit_the_column_limit_of_the_format_check(self):
        for path in (HEADER, WEB_H, ADAPTER):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                self.assertLessEqual(len(line), 100, f"{path.name}:{number}")

    def test_the_header_is_usable_from_c_plus_plus(self):
        text = HEADER.read_text()
        self.assertIn('extern "C" {', text)
        self.assertRegex(text, r"#ifdef __cplusplus\s*\n\}\s*\n#endif")

    def test_the_public_path_is_unique_across_components(self):
        found = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "components").rglob("web_zephyr.h"))
        self.assertEqual(found, ["components/web/ports/zephyr/include/crux/web_zephyr.h"])


class Target(unittest.TestCase):
    cmake = (PORT / "CMakeLists.txt").read_text()

    @classmethod
    def body(cls):
        match = re.search(r"function\(crux_web_zephyr_composition\)(.*?)endfunction\(\)", cls.cmake, re.S)
        return match.group(1) if match else None

    def test_the_target_is_defined_by_a_function_that_is_called_once(self):
        self.assertIsNotNone(self.body())
        self.assertEqual(len(re.findall(r"^crux_web_zephyr_composition\(\)\s*$", self.cmake, re.M)), 1)

    def test_the_interface_target_has_a_name_unlike_the_provider_library(self):
        text = self.body() or ""
        self.assertIn("add_library(crux_web_zephyr_composition INTERFACE)", text)
        self.assertIn("add_library(crux::web_zephyr ALIAS crux_web_zephyr_composition)", text)
        # The STATIC provider keeps its own name (ADR-0004 section 2), and nothing else is called that.
        self.assertEqual(self.cmake.count("add_library(crux_web_zephyr STATIC"), 1)
        self.assertNotIn("add_library(crux_web_zephyr INTERFACE", self.cmake)

    def test_the_target_adds_the_include_root_and_links_the_portable_target_only(self):
        text = self.body() or ""
        self.assertIn('"${CRUX_WEB_COMPONENT_DIR}/ports/zephyr/include"', text)
        for forbidden in ("zephyr_interface", "/src", "/adapter", "/session", "/management", "PUBLIC",
                          "zephyr_append_cmake_library", "target_link_options", "target_compile",
                          "crux_web_zephyr)", "crux_web_zephyr "):
            self.assertNotIn(forbidden, text, forbidden)
        linked = {word for entry in re.findall(r"target_link_libraries\(\w+ INTERFACE ([^)]*)\)", text)
                  for word in entry.split()}
        self.assertEqual(linked, {"crux_web"})
        self.assertEqual(len(re.findall(r"^\s*target_", text, re.M)), 2)

    def test_the_target_does_not_link_the_provider_which_kconfig_selects(self):
        self.assertIn("zephyr_append_cmake_library(crux_web_zephyr)", self.cmake)
        self.assertNotIn("zephyr_append_cmake_library", self.body() or "")

    def test_the_target_comes_after_the_portable_target_it_links(self):
        self.assertLess(self.cmake.index("add_library(crux_web INTERFACE)"),
                        self.cmake.index("crux_web_zephyr_composition()\n"))

    def test_the_include_root_variable_is_defined_by_the_file(self):
        self.assertRegex(self.cmake, r"get_filename_component\(CRUX_WEB_COMPONENT_DIR ")

    def test_the_provider_includes_the_public_header_so_its_definition_is_checked(self):
        source = (PORT / "web_http_server.c").read_text()
        self.assertIn("#include <crux/web_zephyr.h>", source)
        self.assertRegex(self.cmake, r"target_include_directories\(crux_web_zephyr PRIVATE[^)]*ports/zephyr/include")


class Documents(unittest.TestCase):
    def test_the_kconfig_help_names_the_composition_target(self):
        text = (ROOT / "zephyr/Kconfig").read_text()
        block = " ".join(re.search(r"config CRUX_WEB\n(.*?)\n(?:menu)?config ", text, re.S).group(1).split())
        self.assertIn("crux::web_zephyr", block)
        self.assertIn("<crux/web_zephyr.h>", block)

    def test_the_composition_rules_name_the_second_interface(self):
        text = " ".join((ROOT / "docs/composition-interfaces.md").read_text().split())
        self.assertIn("`crux::web_zephyr`", text)
        self.assertIn("`<crux/web_zephyr.h>`", text)

    def test_the_web_contract_says_where_crux_web_start_is_declared(self):
        text = " ".join((ROOT / "docs/web-contract.md").read_text().split())
        self.assertIn("<crux/web_zephyr.h>", text)


if __name__ == "__main__":
    unittest.main()
