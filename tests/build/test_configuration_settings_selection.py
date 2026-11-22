"""The Settings File selections of Configuration, read from the module's Kconfig and CMake.

Two visible symbols link the same provider, `configuration_settings.c`, over the Zephyr Settings File
backend with the corrected sources that the module stages:

- `CRUX_CONFIGURATION_SETTINGS_FILE`, on Reliance Edge only, unchanged.
- `CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS`, on the file system that the composition mounts, with no
  Reliance Edge dependency. It refuses FatFs, whose rename can leave the settings file missing after a
  power cut (docs/plans/configuration-persistence-spike.md, owner decision 4). The refusal is a CMake
  error and an #error, not a Kconfig dependency, which would only drop the selection with a warning
  and leave the image without a provider.

Both select the hidden `CRUX_CONFIGURATION_SETTINGS_PROVIDER`, which every build file tests, so that the
two cannot drift apart. These checks run on the host. The native_sim suites of
scripts/test-storage-emmc.sh and scripts/test-storage-simulators.sh run the selections.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
KCONFIG = ROOT / "zephyr/Kconfig"
PROVIDER = "CRUX_CONFIGURATION_SETTINGS_PROVIDER"
RELIANCE = "CRUX_CONFIGURATION_SETTINGS_FILE"
ANY_FS = "CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS"
BUILD_FILES = (
    "zephyr/CMakeLists.txt",
    "components/configuration/ports/zephyr/CMakeLists.txt",
    "components/configuration/ports/zephyr/core/CMakeLists.txt",
    "components/configuration/ports/zephyr/configuration_settings.c",
)


def symbol_block(name):
    match = re.search(rf"^config {name}\n(.*?)(?=^(?:menu)?config |^if |^endif|^endmenu|\Z)",
                      KCONFIG.read_text(), re.S | re.M)
    return match.group(1) if match else None


def depends(block):
    return " && ".join(re.findall(r"^\s+depends on (.+)$", block, re.M))


class Selections(unittest.TestCase):
    def test_the_provider_symbol_is_hidden_and_selected_by_both_selections(self):
        provider = symbol_block(PROVIDER)
        self.assertIsNotNone(provider, PROVIDER)
        self.assertRegex(provider, r"(?m)^\s+bool\s*$", "the provider symbol has no prompt")
        for name in (RELIANCE, ANY_FS):
            block = symbol_block(name)
            self.assertIsNotNone(block, name)
            self.assertIn(f"select {PROVIDER}", block, name)

    def test_the_reliance_edge_selection_keeps_its_dependencies(self):
        self.assertEqual(depends(symbol_block(RELIANCE)),
                         "CRUX_MODULE && CRUX_FS_RELIANCE_EDGE && SETTINGS_FILE")

    def test_the_new_selection_does_not_depend_on_reliance_edge_or_on_fatfs_being_absent(self):
        terms = {term.strip() for term in depends(symbol_block(ANY_FS)).split("&&")}
        self.assertEqual(terms, {"CRUX_MODULE", "SETTINGS_FILE", f"!{RELIANCE}"})

    def test_the_build_refuses_fatfs_with_the_new_selection_at_cmake(self):
        text = (ROOT / BUILD_FILES[1]).read_text()
        block = re.search(rf"if\(CONFIG_{ANY_FS}\)(.*?)\nendif\(\)", text, re.S)
        self.assertIsNotNone(block)
        self.assertRegex(block.group(1),
                         r"if\(CONFIG_FAT_FILESYSTEM_ELM\)\n\s+message\(FATAL_ERROR \"The Settings File "
                         r"selection refuses FatFs")

    def test_every_build_file_tests_the_provider_symbol_and_not_one_selection(self):
        for relative in BUILD_FILES:
            text = (ROOT / relative).read_text()
            self.assertIn(f"CONFIG_{PROVIDER}", text, relative)
            code = "\n".join(line for line in text.splitlines()
                             if not line.lstrip().startswith(("#", "*", "/*")))
            self.assertNotRegex(code, rf"CONFIG_{RELIANCE}\b", relative)

    def test_the_provider_refuses_fatfs_at_compile_time_as_well(self):
        text = (ROOT / BUILD_FILES[-1]).read_text()
        self.assertRegex(text, rf"#if defined\(CONFIG_{ANY_FS}\) && "
                               r"defined\(CONFIG_FAT_FILESYSTEM_ELM\)\n#error ")

    def test_the_reliance_edge_selection_is_not_refused_with_fatfs(self):
        text = (ROOT / BUILD_FILES[-1]).read_text()
        self.assertNotRegex(text, r"#if defined\(CONFIG_FAT_FILESYSTEM_ELM\)\n#error ")


if __name__ == "__main__":
    unittest.main()
