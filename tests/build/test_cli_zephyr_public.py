"""The Zephyr serial console start is a documented composition interface (ADR-0004, T2, phase 1b).

`<crux/cli_zephyr.h>` and `crux::cli_zephyr` let a product start the serial console with the first-account
setup without a frozen header (`<crux/serial.h>`, `<crux/thread.h>`) and without the private CLI adapter
header, which pulls in first-account provisioning. These checks run on the host. They compile the header
alone, read the CMake definition of the target and the module's wiring, and read the Kconfig symbols. No
Zephyr build uses the target yet: the native_sim fixture of the next change is the first.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "components/cli"
PORT = CLI / "ports/zephyr"
PUBLIC_INCLUDE = PORT / "include"
HEADER = PUBLIC_INCLUDE / "crux/cli_zephyr.h"
START = PORT / "cli_serial_start.c"
PORT_CMAKE = PORT / "CMakeLists.txt"
KCONFIG = ROOT / "zephyr/Kconfig"
CC = os.environ.get("CC", "cc")
FLAGS = ["-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror"]
FROZEN = ("thread.h", "sync.h", "queue.h", "serial.h")
ROOTS = [PUBLIC_INCLUDE, CLI / "include", ROOT / "components/access/include"]
USES = """
#include <crux/cli_zephyr.h>
static const crux_cli_serial_config_t config = {.setup_role = "admin"};
crux_cli_result_t (*start)(const crux_cli_serial_config_t *) = crux_cli_serial_start;
int main(void) { return start && config.setup_role ? 0 : 1; }
"""


def compile_source(source, roots, extra=()):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "tu.c"
        path.write_text(source)
        command = [CC, *FLAGS, *extra, *[arg for root in roots for arg in ("-I", str(root))],
                   "-fsyntax-only", str(path)]
        return subprocess.run(command, capture_output=True, text=True)


def words(path):
    return " ".join(path.read_text().replace("\n *", " ").split())


def symbol_block(name):
    match = re.search(rf"^config {name}\n(.*?)(?=^(?:menu)?config |^endif|^endmenu|\Z)", KCONFIG.read_text(),
                      re.S | re.M)
    return match.group(1) if match else None


class PublicHeader(unittest.TestCase):
    def test_the_header_sits_under_the_composition_path_and_compiles_alone(self):
        self.assertEqual(HEADER.relative_to(ROOT).as_posix(),
                         "components/cli/ports/zephyr/include/crux/cli_zephyr.h")
        self.assertTrue(HEADER.is_file())
        result = compile_source(USES, ROOTS)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_include_set_has_no_frozen_adapter_serial_or_native_header(self):
        result = compile_source(USES, ROOTS, ["-H"])
        self.assertEqual(result.returncode, 0, result.stderr)
        included = [line.lstrip(". ").strip() for line in result.stderr.splitlines() if line.startswith(".")]
        crux = {Path(path).name for path in included if "/crux/" in path}
        self.assertEqual(crux, {"cli_zephyr.h", "cli.h", "access.h"})
        for name in crux:
            self.assertNotIn(name, FROZEN)
        for path in [p for p in included if not p.startswith(str(ROOT))]:
            self.assertNotRegex(path.lower(), r"zephyr|nxp|cmsis|mcux|/boards?/|wolf|mbedtls|psa")
        includes = "\n".join(re.findall(r"^\s*#\s*include\s*[^\n]*$", HEADER.read_text(), re.M))
        for pattern in (r"crux_cli_adapter", r"crux_access_adapter", r"crux_cli_console\.h", r"crux/serial\.h",
                        r"crux/(thread|sync|queue)\.h", r"(zephyr|wolf|mbedtls|psa)/"):
            self.assertNotRegex(includes, pattern)
        self.assertEqual(includes.strip(), "#include <crux/cli.h>")

    def test_it_declares_one_function_and_one_type(self):
        code = re.sub(r"/\*.*?\*/", "", HEADER.read_text(), flags=re.S)
        code = re.sub(r"^#.*$", "", code, flags=re.M)
        self.assertEqual(sorted(set(re.findall(r"\b(crux_\w+)\s*\([^;{]*\)\s*;", code))), ["crux_cli_serial_start"])
        self.assertRegex(code, r"\}\s*crux_cli_serial_config_t\s*;")
        self.assertEqual(len(re.findall(r"\btypedef\b", code)), 1)

    def test_the_header_names_its_tier_and_says_what_it_binds(self):
        self.assertRegex(HEADER.read_text().split("*/", 1)[0], r"Status:\s+Experimental")
        text = words(HEADER)
        for phrase in ("composition interface", "not a portable", "crux-serial0", "crux::cli_zephyr",
                       "owns the serial", "access.manage", "own thread", "no first account"):
            self.assertIn(phrase, text, phrase)

    def test_the_header_says_the_order_and_the_results(self):
        text = words(HEADER)
        for phrase in ("crux_access_init()", "crux_cli_init()", "thread context", "CRUX_CLI_OK",
                       "CRUX_CLI_ERR_INVALID_ARGUMENT", "CRUX_CLI_ERR_NOT_READY", "CRUX_CLI_ERR_FAILED"):
            self.assertIn(phrase, text, phrase)

    def test_the_header_says_the_typed_password_limit_of_the_cli_contract(self):
        text = words(HEADER)
        self.assertIn("docs/cli-contract.md", text)

    def test_lines_fit_the_column_limit_of_the_format_check(self):
        for path in (HEADER, START):
            self.assertTrue(path.is_file(), path)
            for number, line in enumerate(path.read_text().splitlines(), 1):
                self.assertLessEqual(len(line), 100, f"{path.name}:{number}")

    def test_the_header_is_usable_from_c_plus_plus(self):
        text = HEADER.read_text()
        self.assertIn('extern "C" {', text)
        self.assertRegex(text, r"#ifdef __cplusplus\s*\n\}\s*\n#endif")

    def test_the_public_path_is_unique_across_components(self):
        found = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "components").rglob("cli_zephyr.h"))
        self.assertEqual(found, ["components/cli/ports/zephyr/include/crux/cli_zephyr.h"])


class StartSource(unittest.TestCase):
    text = START.read_text() if START.is_file() else ""

    def test_the_definition_checks_itself_against_the_public_declaration(self):
        self.assertIn("#include <crux/cli_zephyr.h>", self.text)

    def test_it_opens_port_zero_with_the_kconfig_settings_and_creates_one_placed_thread(self):
        code = re.sub(r"/\*.*?\*/|//[^\n]*", "", self.text, flags=re.S)
        self.assertEqual(len(re.findall(r"\bcrux_thread_create\s*\(", code)), 1)
        self.assertIn("CONFIG_CRUX_CLI_CONSOLE_BAUD_RATE", code)
        self.assertRegex(code, r"crux_cli_console_run\(")
        self.assertRegex(code, r"#ifdef\s+CRUX_SERVICE_PRIORITY_PLACEMENT\s*\n\s*crux_service_priority_place\(CRUX_SERVICE_THREAD_CLI_CONSOLE\);")

    def test_it_refuses_a_missing_argument_and_a_registry_that_is_not_ready(self):
        self.assertRegex(self.text, r"CRUX_CLI_ERR_INVALID_ARGUMENT")
        self.assertRegex(self.text, r"crux_cli_registry_ready\(\)")
        self.assertRegex(self.text, r"CRUX_CLI_ERR_NOT_READY")

    def test_the_source_includes_no_zephyr_or_native_header(self):
        for pattern in (r"#\s*include\s*[<\"](zephyr|wolf|mbedtls|psa)/",):
            self.assertNotRegex(self.text, pattern)


class Target(unittest.TestCase):
    cmake = PORT_CMAKE.read_text()
    code = re.sub(r"#[^\n]*", "", cmake)

    @classmethod
    def body(cls):
        match = re.search(r"function\(crux_cli_zephyr_composition\)(.*?)endfunction\(\)", cls.cmake, re.S)
        return match.group(1) if match else None

    def test_the_target_is_defined_by_a_function_that_is_called_once_under_the_console_symbol(self):
        self.assertIsNotNone(self.body())
        calls = [m.start() for m in re.finditer(r"^\s*crux_cli_zephyr_composition\(\)\s*$", self.cmake, re.M)]
        self.assertEqual(len(calls), 1)
        opening = self.cmake.rfind("if(CONFIG_CRUX_CLI_CONSOLE)", 0, calls[0])
        closing = self.cmake.find("endif()", calls[0])
        self.assertTrue(0 <= opening < calls[0] < closing)

    def test_the_interface_target_has_a_name_unlike_the_provider_library(self):
        text = self.body() or ""
        self.assertIn("add_library(crux_cli_zephyr_composition INTERFACE)", text)
        self.assertIn("add_library(crux::cli_zephyr ALIAS crux_cli_zephyr_composition)", text)
        self.assertEqual(self.cmake.count("add_library(crux_cli_zephyr STATIC"), 1)

    def test_the_target_adds_the_include_root_and_links_the_portable_target_only(self):
        text = self.body() or ""
        self.assertIn('"${CRUX_CLI_COMPONENT_DIR}/ports/zephyr/include"', text)
        for forbidden in ("zephyr_interface", "/src", "/adapter", "/console", "PUBLIC", "crux::serial",
                          "crux::thread", "zephyr_append_cmake_library", "target_link_options",
                          "target_compile", "crux_cli_zephyr)", "crux_cli_zephyr ", "crux_cli_adapter"):
            self.assertNotIn(forbidden, text, forbidden)
        linked = {word for entry in re.findall(r"target_link_libraries\(\w+ INTERFACE ([^)]*)\)", text)
                  for word in entry.split()}
        self.assertEqual(linked, {"crux_cli"})
        self.assertEqual(len(re.findall(r"^\s*target_", text, re.M)), 2)

    def test_the_provider_is_registered_and_given_its_extra_sources_only_under_the_symbol(self):
        for needle in ("zephyr_append_cmake_library(crux_cli_zephyr)",
                       "../../src/cli_security_events.c", "cli_serial_start.c"):
            self.assertEqual(self.code.count(needle), 1, needle)
            index = self.code.index(needle)
            opening = self.code.rfind("if(CONFIG_CRUX_CLI_CONSOLE)", 0, index)
            closing = self.code.find("endif()", opening)
            self.assertTrue(0 <= opening < index < closing, needle)

    def test_the_provider_links_the_placement_and_sees_the_public_and_event_headers(self):
        self.assertRegex(self.cmake, r"target_link_libraries\(crux_cli_zephyr PRIVATE[^)]*crux_service_priority_placement")
        self.assertRegex(self.cmake, r"target_link_libraries\(crux_cli_zephyr PRIVATE[^)]*crux::security_event")
        self.assertRegex(self.cmake, r"target_include_directories\(crux_cli_zephyr PRIVATE[^)]*ports/zephyr/include")

    def test_the_composition_target_does_not_link_the_provider(self):
        self.assertNotIn("zephyr_append_cmake_library", self.body() or "")

    def test_the_target_comes_after_the_portable_target_it_links(self):
        call = re.search(r"^\s*crux_cli_zephyr_composition\(\)\s*$", self.cmake, re.M).start()
        self.assertLess(self.cmake.index("add_library(crux_cli INTERFACE)"), call)


class Kconfig(unittest.TestCase):
    def test_the_console_symbol_is_experimental_and_needs_what_it_calls(self):
        block = symbol_block("CRUX_CLI_CONSOLE")
        self.assertIsNotNone(block)
        self.assertRegex(block, r"depends on[^\n]*CRUX_CLI\b")
        self.assertRegex(block, r"depends on[^\n]*CRUX_ACCESS\b")
        self.assertRegex(block, r"depends on[^\n]*CRUX_SERIAL\b|depends on[^\n]*CRUX_CLI\b")
        self.assertIn("Experimental", block)
        help_text = " ".join(block.split())
        self.assertIn("crux::cli_zephyr", help_text)
        self.assertIn("<crux/cli_zephyr.h>", help_text)
        self.assertIn("crux-serial0", help_text)

    def test_the_settings_exist_with_the_defaults_the_plan_states(self):
        baud = symbol_block("CRUX_CLI_CONSOLE_BAUD_RATE")
        self.assertIsNotNone(baud)
        self.assertRegex(baud, r"default 115200\b")
        self.assertIsNone(symbol_block("CRUX_CLI_CONSOLE_STACK_BYTES"))

    def test_the_priority_is_in_the_per_service_menu_and_defaults_to_todays_number(self):
        text = KCONFIG.read_text()
        menu = text[text.index('menu "Priorities of Crux service workers"'):]
        menu = menu[:menu.index("endmenu")]
        self.assertIn("config CRUX_CLI_CONSOLE_PRIORITY", menu)
        block = symbol_block("CRUX_CLI_CONSOLE_PRIORITY")
        self.assertRegex(block, r"default 6\b")

    def test_the_console_thread_gets_the_login_stack_default_of_the_web_worker(self):
        # The console verifies a login with the same PBKDF2 derivation on its own stack.
        block = symbol_block("CRUX_THREAD_STACK_BYTES")
        self.assertRegex(block, r"default 8192 if [^\n]*CRUX_CLI_CONSOLE")

    def test_the_baud_rate_has_a_range(self):
        self.assertRegex(symbol_block("CRUX_CLI_CONSOLE_BAUD_RATE"), r"range \d+ \d+")

    def test_the_cli_help_no_longer_says_access_has_no_zephyr_composition(self):
        block = " ".join((symbol_block("CRUX_CLI") or "").split())
        self.assertNotIn("have no Zephyr composition yet", block)

    def test_the_symbols_are_documented_in_the_management_guide(self):
        text = (ROOT / "docs/management-in-a-product.md").read_text()
        for symbol in ("CRUX_CLI_CONSOLE",):
            row = next((line for line in text.splitlines() if line.startswith(f"| `{symbol}`")), "")
            self.assertIn("crux::cli_zephyr", row, symbol)


class Documents(unittest.TestCase):
    def test_the_composition_rules_name_the_third_interface(self):
        text = " ".join((ROOT / "docs/composition-interfaces.md").read_text().split())
        self.assertIn("`crux::cli_zephyr`", text)
        self.assertIn("`<crux/cli_zephyr.h>`", text)

    def test_the_composition_doc_states_the_departure_from_rule_4_and_does_not_overstate_adr_0004(self):
        text = " ".join((ROOT / "docs/composition-interfaces.md").read_text().split())
        self.assertIn("It departs from rule 4", text)
        self.assertIn("crux_cli_serial_run()", text)
        self.assertNotIn("ADR-0004 adds `crux::web_zephyr`", text)
        self.assertNotIn("ADR-0004 adds", text)

    def test_the_header_says_the_order_differs_from_adr_0004_step_7(self):
        text = words(HEADER)
        self.assertIn("ADR-0004 section 3 puts the first account at step 7", text)

    def test_the_thread_docs_count_six_workers_and_say_no_image_starts_the_console(self):
        text = " ".join((ROOT / "docs/thread-sync.md").read_text().split())
        self.assertIn("one of the six worker sources", text)
        self.assertNotIn("one of the five worker sources", text)
        self.assertIn("no Zephyr image starts the reboot worker or the serial console thread", text)

    def test_the_cli_contract_says_where_a_product_starts_the_console(self):
        text = " ".join((ROOT / "docs/cli-contract.md").read_text().split())
        self.assertIn("<crux/cli_zephyr.h>", text)

    def test_the_priority_map_names_the_console_thread(self):
        text = (ROOT / "docs/thread-sync.md").read_text()
        self.assertIn("CRUX_CLI_CONSOLE_PRIORITY", text)


if __name__ == "__main__":
    unittest.main()
