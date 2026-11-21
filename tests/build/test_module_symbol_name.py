# SPDX-License-Identifier: Apache-2.0
"""Check the names of the Zephyr module, its master Kconfig switch and its generated symbols.

The switch is CRUX_MODULE. The old name CRUX_PILOT_MODULE has no alias, so no live file may use
it, except the migration line in the product composition guide. Accepted evidence, the history and
plan records, ADR-0005 and the measured S2 configuration of an older pin keep it as recorded.

zephyr/module.yml sets name: crux, so Zephyr makes CONFIG_ZEPHYR_CRUX_MODULE and the CMake variable
ZEPHYR_CRUX_MODULE_DIR whatever the checkout folder is called. Before, the folder name gave
CONFIG_ZEPHYR_CRUX_PILOT_MODULE and ZEPHYR_CRUX_PILOT_MODULE_DIR in a crux-pilot checkout. No live
file may use those, except the migration lines in the product composition guide.

Only the standard library is used.
"""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[2]
OLD = re.compile(r"(?<!ZEPHYR_)CRUX_PILOT_MODULE\b")
RECORDED = ("docs/evidence/", "docs/history/", "docs/superpowers/", "tests/build/fixtures/recorded/",
            "docs/decisions/0005-native-sim-test-watchdog-for-system-consumers.md",
            # The real, hash-locked .config of the S2 build at an older pin.
            "tests/build/fixtures/s2-controller/",
            "tests/build/test_module_symbol_name.py")
MIGRATION_DOC = "docs/product-composition.md"
MIGRATION = "renamed from `CONFIG_CRUX_PILOT_MODULE`"
OLD_GENERATED = re.compile(r"(?:ZEPHYR|SYSBUILD)_CRUX_PILOT_(?:MODULE|KCONFIG|CMAKE)")
# The claim that the module name follows the folder was true before name: crux.
FOLDER_CLAIM = re.compile(r"(?i)module name follows the checkout")
# The proposal keeps its PoC finding with a dated note that it no longer holds.
FOLDER_CLAIM_RECORDED = "docs/test-foundation-proposal.md"
GENERATED_MIGRATION = ("`ZEPHYR_CRUX_PILOT_MODULE_DIR` by `ZEPHYR_CRUX_MODULE_DIR`",
                       "`CONFIG_ZEPHYR_CRUX_PILOT_MODULE` by `CONFIG_ZEPHYR_CRUX_MODULE`")
HAS_GIT = shutil.which("git") is not None and (REPO / ".git").exists()


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
    @unittest.skipUnless(HAS_GIT, "needs git and a checkout to list tracked files")
    def test_old_name_is_gone_from_live_files(self):
        hits = [f"{name}:{n}" for name, text in tracked_text_files()
                for n, line in enumerate(text.splitlines(), 1)
                if OLD.search(line) and not (name == MIGRATION_DOC and MIGRATION in line)]
        self.assertEqual([], hits)

    def test_module_has_the_fixed_name_crux(self):
        module = (REPO / "zephyr/module.yml").read_text()
        self.assertEqual(["crux"], re.findall(r"^name:[ \t]*(\S+)[ \t]*$", module, re.M))

    @unittest.skipUnless(HAS_GIT, "needs git and a checkout to list tracked files")
    def test_old_generated_names_are_gone_from_live_files(self):
        hits = [f"{name}:{n}" for name, text in tracked_text_files()
                for n, line in enumerate(text.splitlines(), 1)
                if OLD_GENERATED.search(line)
                and not (name == MIGRATION_DOC and any(m in line for m in GENERATED_MIGRATION))]
        self.assertEqual([], hits)

    @unittest.skipUnless(HAS_GIT, "needs git and a checkout to list tracked files")
    def test_no_live_doc_says_the_module_name_follows_the_folder(self):
        hits = [f"{name}:{n}" for name, text in tracked_text_files() if name != FOLDER_CLAIM_RECORDED
                for n, line in enumerate(text.splitlines(), 1) if FOLDER_CLAIM.search(line)]
        self.assertEqual([], hits)

    def test_product_doc_gives_the_generated_name_migration(self):
        doc = (REPO / MIGRATION_DOC).read_text()
        for line in GENERATED_MIGRATION:
            self.assertIn(line, doc)
        self.assertIn("`name: crux`", doc)

    def test_new_symbol_is_defined_once_and_gates_the_module(self):
        kconfig = (REPO / "zephyr/Kconfig").read_text()
        self.assertEqual(1, len(re.findall(r"^(?:menu)?config CRUX_MODULE$", kconfig, re.M)))
        self.assertEqual(1, len(re.findall(r"^menuconfig CRUX_MODULE$", kconfig, re.M)))
        self.assertIn("if CRUX_MODULE\n", kconfig)
        self.assertEqual(3, (REPO / "zephyr/CMakeLists.txt").read_text().count("if(CONFIG_CRUX_MODULE)"))
        self.assertIn("if(CONFIG_CRUX_MODULE)", (REPO / "components/interrupt/CMakeLists.txt").read_text())

    def test_no_alias_for_the_old_name(self):
        for path in sorted((REPO / "zephyr").rglob("Kconfig*")):
            self.assertNotRegex(path.read_text(), r"(?<!ZEPHYR_)CRUX_PILOT", str(path))

    def test_product_doc_gives_the_migration_line(self):
        doc = (REPO / MIGRATION_DOC).read_text()
        self.assertIn(MIGRATION, doc)
        self.assertIn("`CONFIG_CRUX_MODULE`", doc)
        self.assertRegex(doc, r"(?i)no alias")


if __name__ == "__main__":
    unittest.main()
