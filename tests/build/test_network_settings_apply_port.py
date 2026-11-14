"""The network settings apply port, a public header that the product implements (ADR-0004, T2, PR 3).

ADR-0004 decision C3: the apply port is a header with two declarations, `crux_network_settings_port_apply`
and `crux_network_settings_port_running`, which the product implements with its own native code. It is
the inverse of a composition interface: Crux declares it, the product defines it, and the header names
no native type. These checks run on the host. They compile the header alone, compile a product-style
definition against it, and hold the private port header to declaring the event port only.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = ROOT / "components/network_settings"
PUBLIC = COMPONENT / "include/crux/network_settings_apply_port.h"
STATE = COMPONENT / "include/crux/network_settings.h"
PRIVATE = COMPONENT / "src/network_settings_port.h"
PORT_CMAKE = COMPONENT / "ports/zephyr/CMakeLists.txt"
CC = os.environ.get("CC", "cc")
FLAGS = ["-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror"]
FROZEN = ("thread.h", "sync.h", "queue.h", "serial.h")
ROOTS = [COMPONENT / "include", ROOT / "components/access/include",
         ROOT / "components/config_service/include", ROOT / "components/configuration/include"]
FUNCTIONS = ("crux_network_settings_port_apply", "crux_network_settings_port_running")
# A product's adapter: the definitions that its Zephyr net_if code would give, with the public header only.
PRODUCT = """
#include <crux/network_settings_apply_port.h>

bool crux_network_settings_port_apply(const crux_network_settings_t *settings)
{
    return settings != NULL;
}

bool crux_network_settings_port_running(crux_network_settings_t *settings)
{
    return settings == NULL;
}
"""


def compile_source(source, roots, extra=()):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "tu.c"
        path.write_text(source)
        command = [CC, *FLAGS, *extra, *[arg for root in roots for arg in ("-I", str(root))],
                   "-fsyntax-only", str(path)]
        return subprocess.run(command, capture_output=True, text=True)


def comments_and_preprocessor_removed(text):
    code = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"^#.*$", "", code, flags=re.M)


class PublicHeader(unittest.TestCase):
    def test_the_header_exists_and_compiles_alone(self):
        self.assertTrue(PUBLIC.is_file())
        result = compile_source("#include <crux/network_settings_apply_port.h>\nint main(void) { return 0; }\n",
                                ROOTS)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_product_can_define_both_functions_with_this_header_only(self):
        result = compile_source(PRODUCT, ROOTS)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_definition_with_another_signature_is_refused(self):
        wrong = PRODUCT.replace("bool crux_network_settings_port_apply(const crux_network_settings_t *settings)",
                                "int crux_network_settings_port_apply(const crux_network_settings_t *settings)")
        self.assertNotEqual(wrong, PRODUCT)
        self.assertNotEqual(compile_source(wrong, ROOTS).returncode, 0)

    def test_the_header_pulls_in_only_the_capabilitys_crux_headers(self):
        result = compile_source(PRODUCT, ROOTS, ["-H"])
        self.assertEqual(result.returncode, 0, result.stderr)
        included = [line.lstrip(". ").strip() for line in result.stderr.splitlines() if line.startswith(".")]
        crux = {Path(path).name for path in included if "/crux/" in path}
        self.assertEqual(crux, {"network_settings_apply_port.h", "network_settings.h", "access.h",
                                "config_service.h", "configuration.h"})
        for name in crux:
            self.assertNotIn(name, FROZEN)
        for path in [p for p in included if not p.startswith(str(ROOT))]:
            self.assertNotRegex(path.lower(), r"zephyr|nxp|cmsis|mcux|/boards?/|wolf|mbedtls|psa")

    def test_the_header_names_no_native_frozen_or_private_thing(self):
        text = PUBLIC.read_text()
        for pattern in (r"net_if", r"struct device", r"crux/(thread|sync|queue|serial)\.h",
                        r"#\s*include\s*[<\"](zephyr|wolf|mbedtls|psa)/", r"network_settings_port\.h",
                        r"crux_network_settings_event_t", r"crux_network_settings_port_event"):
            self.assertNotRegex(text, pattern)

    def test_it_declares_exactly_the_two_functions_of_decision_c3(self):
        code = comments_and_preprocessor_removed(PUBLIC.read_text())
        declared = re.findall(r"\b(crux_\w+)\s*\([^;{]*\)\s*;", code)
        self.assertEqual(sorted(declared), sorted(FUNCTIONS))

    def test_the_private_header_declares_the_event_port_only(self):
        text = PRIVATE.read_text()
        code = comments_and_preprocessor_removed(text)
        declared = re.findall(r"\b(crux_\w+)\s*\([^;{]*\)\s*;", code)
        self.assertEqual(declared, ["crux_network_settings_port_event"])
        self.assertRegex(text, r"#include\s+<crux/network_settings_apply_port\.h>")
        self.assertIn("crux_network_settings_event_t", text)

    def test_the_private_header_still_compiles_for_the_core_and_the_fakes(self):
        source = ('#include "network_settings_port.h"\n'
                  "bool (*apply)(const crux_network_settings_t *) = crux_network_settings_port_apply;\n"
                  "bool (*running)(crux_network_settings_t *) = crux_network_settings_port_running;\n"
                  "void (*event)(crux_network_settings_event_t, crux_access_session_t) =\n"
                  "    crux_network_settings_port_event;\n"
                  "int main(void) { return apply && running && event ? 0 : 1; }\n")
        result = compile_source(source, [COMPONENT / "src", *ROOTS])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_state_header_declares_neither_function(self):
        text = STATE.read_text()
        for name in FUNCTIONS:
            self.assertNotIn(name, text)

    def test_the_documentation_says_who_implements_it_and_when_it_runs(self):
        text = " ".join(PUBLIC.read_text().replace("\n *", " ").split())
        for phrase in ("The product implements", "once, at boot", "before any management channel starts",
                       "Thread context", "returns false", "never both with CONFIG_CRUX_NETWORK_SETTINGS_NO_APPLY",
                       "no running values"):
            self.assertIn(phrase, text, phrase)

    def test_the_header_names_its_tier(self):
        self.assertRegex(PUBLIC.read_text().split("*/", 1)[0], r"Status:\s+Experimental")

    def test_lines_fit_the_column_limit_of_the_format_check(self):
        for path in (PUBLIC, PRIVATE):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                self.assertLessEqual(len(line), 100, f"{path.name}:{number}")

    def test_the_header_is_usable_from_c_plus_plus(self):
        self.assertIn('extern "C" {', PUBLIC.read_text())

    def test_the_public_path_is_unique_across_components(self):
        found = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "components").rglob(PUBLIC.name))
        self.assertEqual(found, [PUBLIC.relative_to(ROOT).as_posix()])


class Texts(unittest.TestCase):
    def test_the_kconfig_help_names_the_header(self):
        text = (ROOT / "zephyr/Kconfig").read_text()
        block = " ".join(re.search(r"config CRUX_NETWORK_SETTINGS\n(.*?)\nconfig ", text, re.S).group(1).split())
        self.assertIn("<crux/network_settings_apply_port.h>", block)
        self.assertNotIn("adds no crux:: target and no public header", block)

    def test_the_port_comment_names_the_header(self):
        text = PORT_CMAKE.read_text()
        self.assertIn("<crux/network_settings_apply_port.h>", text)
        self.assertNotIn("from src/network_settings_port.h", text)


if __name__ == "__main__":
    unittest.main()
