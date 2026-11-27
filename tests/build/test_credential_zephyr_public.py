"""The credential store's erase is a documented composition interface, reachable through a public target.

`<crux/credential_store_zephyr.h>` and `crux::credential_store_zephyr` publish one existing declaration,
`crux_credential_erase()`, so that a product's composition can reset a device to its first-account state
behind a local trigger of its own (decision S4: no unauthenticated wipe). These checks run on the host.
They compile the header alone, read the CMake definition of the target, and hold the private adapter
header to the same declaration. tests/native/management_module runs the erase through the target.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CREDENTIAL = ROOT / "components/credential"
PORT = CREDENTIAL / "ports/zephyr"
PUBLIC_INCLUDE = PORT / "include"
HEADER = PUBLIC_INCLUDE / "crux/credential_store_zephyr.h"
PORTABLE = CREDENTIAL / "include/crux/credential_store.h"
ADAPTER = CREDENTIAL / "adapter/crux_credential_adapter.h"
CC = os.environ.get("CC", "cc")
FLAGS = ["-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror"]
ROOTS = [PUBLIC_INCLUDE, CREDENTIAL / "include", ROOT / "components/file/include",
         ROOT / "components/base/include"]
USES = """
#include <crux/credential_store_zephyr.h>
crux_credential_result_t (*erase)(void) = crux_credential_erase;
int main(void) { return erase ? 0 : 1; }
"""


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
        includes = re.findall(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', HEADER.read_text(), re.M)
        self.assertEqual(includes, ["crux/credential_store.h"])

    def test_it_publishes_the_erase_and_nothing_else(self):
        self.assertEqual(declarations(HEADER), ["crux_credential_result_t crux_credential_erase(void);"])

    def test_the_adapter_header_holds_the_same_declaration(self):
        self.assertIn(declarations(HEADER)[0], declarations(ADAPTER))
        both = compile_source('#include <crux/credential_store_zephyr.h>\n'
                              '#include "crux_credential_adapter.h"\nint main(void) { return 0; }\n',
                              ROOTS + [CREDENTIAL / "adapter"])
        self.assertEqual(both.returncode, 0, both.stderr)

    def test_the_portable_header_does_not_declare_it(self):
        # A portable consumer cannot erase the store: only composition code includes the other header.
        self.assertNotIn("crux_credential_erase", " ".join(declarations(PORTABLE)))

    def test_it_documents_tier_context_trigger_and_what_follows(self):
        text = comment_text(HEADER)
        self.assertRegex(HEADER.read_text().split("*/", 1)[0], r"Status:\s+Experimental")
        for phrase in ("composition interface", "no session", "Thread context", "unauthenticated",
                       "button", "access.manage", "restart", "UNUSABLE", "physical erasure",
                       "CRUX_CREDENTIAL_ERR_STORE", "CRUX_CREDENTIAL_ERR_NOT_READY",
                       "crux_credential_start"):
            self.assertIn(phrase, text, phrase)

    def test_the_lines_fit_the_column_limit_of_the_format_check(self):
        for number, line in enumerate(HEADER.read_text().splitlines(), 1):
            self.assertLessEqual(len(line), 100, f"{HEADER.name}:{number}")

    def test_the_public_path_is_unique(self):
        found = sorted(p.relative_to(ROOT).as_posix()
                       for p in (ROOT / "components").rglob("credential_store_zephyr.h"))
        self.assertEqual(found, [HEADER.relative_to(ROOT).as_posix()])


class Target(unittest.TestCase):
    @staticmethod
    def body():
        text = (PORT / "CMakeLists.txt").read_text()
        match = re.search(r"function\(crux_credential_store_zephyr_composition\)(.*?)endfunction\(\)",
                          text, re.S)
        return text, match.group(1) if match else None

    def test_the_target_exposes_the_include_root_and_the_portable_target_only(self):
        text, body = self.body()
        self.assertIsNotNone(body)
        self.assertIn("add_library(crux_credential_store_zephyr_composition INTERFACE)", body)
        self.assertIn("add_library(crux::credential_store_zephyr ALIAS "
                      "crux_credential_store_zephyr_composition)", body)
        self.assertIn('"${CRUX_CREDENTIAL_COMPONENT_DIR}/ports/zephyr/include"', body)
        linked = re.findall(r"target_link_libraries\(\w+ INTERFACE ([^)]*)\)", body)
        self.assertEqual(" ".join(linked).split(), ["crux_credential_store"])
        for forbidden in ("/adapter", "/src", "crux_credential_zephyr", "PUBLIC"):
            self.assertNotIn(forbidden, body)
        self.assertEqual(len(re.findall(r"^crux_credential_store_zephyr_composition\(\)\s*$", text, re.M)), 1)


if __name__ == "__main__":
    unittest.main()
