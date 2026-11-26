"""The File provider on LittleFS over a block device, selected by `CONFIG_CRUX_FILE_LITTLEFS_BLK_DEV`.

Like the other selections on a real medium it is keyed on generic disk and devicetree facts, never on a
board or SoC name: an SD card disk or an eMMC disk, and a RAM disk on native_sim only, for tests. These
checks run on the host. They read zephyr/Kconfig, configure the provider's real CMakeLists.txt and run
the preprocessor over file_native.c. The Zephyr builds and the native_sim suites are in
scripts/test-storage-simulators.sh and scripts/test-file-rt1060-compile.sh.
"""
import os
from pathlib import Path
import re
import tempfile
import unittest

import test_board_neutral_zephyr as neutral

REPO = Path(__file__).resolve().parents[2]
SYMBOL = "CRUX_FILE_LITTLEFS_BLK_DEV"
CONFIG = f"CONFIG_{SYMBOL}"
OTHER_SELECTIONS = ("CRUX_FILE_SIMULATOR", "CRUX_FILE_FATFS_SIMULATOR", "CRUX_FILE_FATFS_SDMMC",
                    "CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK", "CRUX_FILE_FATFS_RAM_DISK",
                    "CRUX_FILE_RELIANCE_EDGE")
LITTLEFS = ("FILE_SYSTEM", "FILE_SYSTEM_LITTLEFS", "FS_LITTLEFS_BLK_DEV")
DISKS = {
    "an SD card disk": ("DT_HAS_ZEPHYR_SDMMC_DISK_ENABLED", "DISK_DRIVER_SDMMC"),
    "an eMMC disk": ("DT_HAS_ZEPHYR_MMC_DISK_ENABLED", "DISK_DRIVER_MMC"),
    "a RAM disk on native_sim": ("BOARD_NATIVE_SIM", "DT_HAS_ZEPHYR_RAM_DISK_ENABLED",
                                 "DISK_DRIVER_RAM"),
}


def settings(disk, **extra):
    names = LITTLEFS + DISKS[disk]
    values = {f"CONFIG_{name}": "y" for name in names}
    values.update({CONFIG: "y", "CONFIG_CRUX_FILE_POOL_SIZE": "4",
                   "CONFIG_CRUX_FILE_DIR_POOL_SIZE": "2"})
    values.update(extra)
    return values


class KconfigBlock(unittest.TestCase):
    def block(self):
        block = neutral.kconfig_block(SYMBOL)
        self.assertIsNotNone(block, f"config {SYMBOL} is missing")
        return block

    def test_it_is_a_prompted_bool_off_by_default(self):
        block = self.block()
        self.assertRegex(block, r'(?m)^\s+bool "')
        self.assertNotRegex(block, r"(?m)^\s+default\s+y")

    def test_it_depends_on_the_file_system_and_a_disk_not_a_board(self):
        block = self.block()
        for needed in LITTLEFS + tuple(name for names in DISKS.values() for name in names):
            self.assertRegex(block, rf"\b{needed}\b", needed)
        for other in OTHER_SELECTIONS:
            self.assertRegex(block, rf"!{other}\b", other)
        self.assertNotRegex(block, r"\bUSDHC\b")

    def test_the_help_states_the_mount_rule(self):
        text = " ".join(self.block().split())
        self.assertIn("FS_MOUNT_FLAG_NO_FORMAT", text)
        self.assertIn("never formats", text)

    def test_the_cache_holds_a_sector_by_default(self):
        kconfig = (REPO / "zephyr/Kconfig").read_text()
        self.assertRegex(kconfig, rf"configdefault FS_LITTLEFS_CACHE_SIZE\n\s+default 512 if {SYMBOL}\n")

    def test_the_module_builds_the_provider_and_keeps_the_mmc_flush_guard_on_it(self):
        text = (REPO / "zephyr/CMakeLists.txt").read_text()
        guarded = re.search(r"if\((CONFIG_CRUX_FILE_SIMULATOR OR[^)]*)\)\n\s+# The guard of the eMMC", text)
        self.assertIsNotNone(guarded, "no File selection block with the eMMC guard")
        self.assertIn(CONFIG, guarded.group(1))
        usage = re.search(r"if\((CONFIG_CRUX_FILE_SIMULATOR OR[^)]*)\)\n\s+cmake_language\(DEFER CALL "
                          r"crux_assert_portable_usage crux::file\)", text)
        self.assertIsNotNone(usage)
        self.assertIn(CONFIG, usage.group(1))


@unittest.skipUnless(neutral.KCONFIGLIB, "Kconfiglib is not available (pip kconfiglib, or ZEPHYR_BASE)")
class KconfigEvaluation(unittest.TestCase):
    STUB = """
config FILE_SYSTEM_LITTLEFS
    bool "littlefs"
config FS_LITTLEFS_BLK_DEV
    bool "blk"
config DISK_DRIVER_MMC
    bool "mmc"
config DT_HAS_ZEPHYR_MMC_DISK_ENABLED
    bool "dt mmc"
config FS_LITTLEFS_CACHE_SIZE
    int "cache"
    default 64
"""

    def kconf(self, *enabled):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        stub = Path(tmp.name) / "Kconfig"
        text = neutral.KCONFIG_STUB.replace("{module}", str(REPO / "zephyr/Kconfig"))
        for block in re.split(r"(?m)^(?=config )", self.STUB.strip() + "\n"):
            name = re.match(r"config (\w+)", block)
            if name and not re.search(rf"(?m)^config {name.group(1)}$", text):
                text += block
        stub.write_text(text)
        previous = os.environ.copy()
        os.environ["srctree"] = str(REPO / "zephyr")
        try:
            kconf = neutral.KCONFIGLIB.Kconfig(str(stub), warn=False)
        finally:
            os.environ.clear()
            os.environ.update(previous)
        for name in enabled:
            kconf.syms[name].set_value("y")
        return kconf

    def value(self, kconf, name):
        return kconf.syms[name].str_value

    def test_each_disk_makes_it_available_with_a_sector_sized_cache(self):
        for disk, facts in DISKS.items():
            with self.subTest(disk=disk):
                kconf = self.kconf("CRUX_MODULE", "DISK_ACCESS", *LITTLEFS, *facts, SYMBOL)
                self.assertEqual(self.value(kconf, SYMBOL), "y")
                self.assertEqual(self.value(kconf, "FS_LITTLEFS_CACHE_SIZE"), "512")

    def test_the_cache_default_is_untouched_without_the_selection(self):
        kconf = self.kconf("CRUX_MODULE", *LITTLEFS)
        self.assertEqual(self.value(kconf, "FS_LITTLEFS_CACHE_SIZE"), "64")

    def test_a_ram_disk_is_not_enough_on_a_board(self):
        facts = ("DT_HAS_ZEPHYR_RAM_DISK_ENABLED", "DISK_DRIVER_RAM")
        kconf = self.kconf("CRUX_MODULE", "DISK_ACCESS", *LITTLEFS, *facts, SYMBOL)
        self.assertEqual(self.value(kconf, SYMBOL), "n")

    def test_the_usdhc_alignment_default_covers_it(self):
        kconf = self.kconf("CRUX_MODULE", "DISK_ACCESS", *LITTLEFS, *DISKS["an SD card disk"], "SDHC",
                           "IMX_USDHC", SYMBOL)
        self.assertEqual(self.value(kconf, "SDHC_BUFFER_ALIGNMENT"), "32")


@unittest.skipUnless(neutral.CMAKE and neutral.CC, "cmake and a C compiler are needed")
class Configure(neutral.FileProviderConfigureTest):
    """The provider's real CMakeLists.txt, with Kconfig values and no SoC or board symbol."""

    def test_each_disk_configures(self):
        for disk in DISKS:
            with self.subTest(disk=disk):
                self.assertConfigures(settings(disk))

    def test_it_needs_littlefs_over_a_block_device(self):
        for missing in LITTLEFS:
            with self.subTest(missing=missing):
                values = settings("an SD card disk")
                del values[f"CONFIG_{missing}"]
                self.assertRefused(values, "The LittleFS block device File provider requires")

    def test_it_needs_a_disk(self):
        for disk, names in DISKS.items():
            for missing in names:
                with self.subTest(disk=disk, missing=missing):
                    values = settings(disk)
                    del values[f"CONFIG_{missing}"]
                    self.assertRefused(values, "The LittleFS block device File provider requires")

    def test_it_refuses_fatfs_in_the_image(self):
        self.assertRefused(settings("an SD card disk", CONFIG_FAT_FILESYSTEM_ELM="y"),
                           "The LittleFS block device File provider refuses FatFs")

    def test_it_cannot_be_combined(self):
        for other in OTHER_SELECTIONS:
            with self.subTest(other=other):
                result = self.configure(settings("an SD card disk", **{f"CONFIG_{other}": "y"}))
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertRegex(result.stdout, r"cannot be combined|mutually exclusive")


# The inherited cases belong to the board-neutral suite; run each once, there.
for _name in [name for name in dir(neutral.FileProviderConfigureTest) if name.startswith("test_")]:
    setattr(Configure, _name, None)


@unittest.skipUnless(neutral.CC, "no C compiler is installed")
class Guard(unittest.TestCase):
    """The preprocessor guards of file_native.c, without Zephyr."""

    def preprocess(self, *defines):
        return neutral.FileProviderGuardTest.preprocess(self, *defines)

    def defines(self, disk):
        return [f"CONFIG_{name}" for name in LITTLEFS + DISKS[disk]] + [CONFIG]

    def test_each_disk_passes(self):
        for disk in DISKS:
            with self.subTest(disk=disk):
                result = self.preprocess(*self.defines(disk))
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_a_missing_fact_is_an_error(self):
        for disk, names in DISKS.items():
            for missing in LITTLEFS + names:
                with self.subTest(disk=disk, missing=missing):
                    result = self.preprocess(*[d for d in self.defines(disk) if d != f"CONFIG_{missing}"])
                    self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_fatfs_and_other_selections_are_errors(self):
        for extra in ("FAT_FILESYSTEM_ELM",) + OTHER_SELECTIONS:
            with self.subTest(extra=extra):
                result = self.preprocess(*self.defines("an SD card disk"), f"CONFIG_{extra}")
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("LittleFS block device File", result.stdout)

    def test_the_names_are_stored_as_they_are(self):
        source = (neutral.FILE_PORT / "file_native.c").read_text()
        fatfs = re.search(r"/\* One selector for every FatFs-specific behaviour.*?\n#endif", source, re.S)
        self.assertIsNotNone(fatfs)
        self.assertNotIn(CONFIG, fatfs.group(0))

    def test_the_build_checks_name_length_pools_and_cache(self):
        source = " ".join((neutral.FILE_PORT / "file_native.c").read_text().split())
        for needle in ("MAX_FILE_NAME > CRUX_FILE_NATIVE_LEAF_MAX",
                       "CONFIG_FS_LITTLEFS_NUM_FILES >= CRUX_FILE_POOL_SIZE",
                       "CONFIG_FS_LITTLEFS_NUM_DIRS >= CRUX_FILE_DIR_POOL_SIZE",
                       "CONFIG_FS_LITTLEFS_CACHE_SIZE >= 512"):
            self.assertIn(needle, source, needle)


if __name__ == "__main__":
    unittest.main()
