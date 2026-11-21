# SPDX-License-Identifier: Apache-2.0
"""Check the name of the Zephyr module's master Kconfig switch.

The switch is CRUX_MODULE. The old name CRUX_PILOT_MODULE has no alias, so no live file may use
it, except a line that says it was renamed, which gives the migration. Accepted evidence and the history, plan and decision records keep it as recorded. The symbol
CONFIG_ZEPHYR_CRUX_PILOT_MODULE is made by Zephyr from the west project name, so it is not the old
switch and stays until that project is renamed.

Only the standard library is used.
"""
from pathlib import Path
import re
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[2]
OLD = re.compile(r"(?<!ZEPHYR_)CRUX_PILOT_MODULE\b")
RECORDED = ("docs/evidence/", "docs/history/", "docs/superpowers/", "docs/decisions/",
            "tests/build/test_module_symbol_name.py")


def tracked_text_files():
    names = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, check=True,
                           capture_output=True).stdout.decode().split("\0")
    for name in filter(None, names):
        if name.startswith(RECORDED) or not (REPO / name).is_file():
            continue
        try:
            yield name, (REPO / name).read_text()
        except UnicodeDecodeError:
            continue


class ModuleSymbolNameTest(unittest.TestCase):
    def test_old_name_is_gone_from_live_files(self):
        hits = [f"{name}:{n}" for name, text in tracked_text_files()
                for n, line in enumerate(text.splitlines(), 1)
                if OLD.search(line) and "renamed" not in line]
        self.assertEqual([], hits)

    def test_new_symbol_is_defined_once_and_gates_the_module(self):
        kconfig = (REPO / "zephyr/Kconfig").read_text()
        self.assertEqual(1, len(re.findall(r"^(?:menu)?config CRUX_MODULE$", kconfig, re.M)))
        self.assertEqual(1, len(re.findall(r"^menuconfig CRUX_MODULE$", kconfig, re.M)))
        self.assertIn("if CRUX_MODULE\n", kconfig)
        self.assertEqual(3, (REPO / "zephyr/CMakeLists.txt").read_text().count("if(CONFIG_CRUX_MODULE)"))
        self.assertIn("if(CONFIG_CRUX_MODULE)", (REPO / "components/interrupt/CMakeLists.txt").read_text())

    def test_no_alias_for_the_old_name(self):
        kconfig = (REPO / "zephyr/Kconfig").read_text()
        self.assertNotRegex(kconfig, r"(?<!ZEPHYR_)CRUX_PILOT")

    def test_product_doc_gives_the_migration_line(self):
        doc = (REPO / "docs/product-composition.md").read_text()
        self.assertIn("`CONFIG_CRUX_PILOT_MODULE`", doc)
        self.assertIn("`CONFIG_CRUX_MODULE`", doc)
        self.assertRegex(doc, r"(?i)no alias")


if __name__ == "__main__":
    unittest.main()
