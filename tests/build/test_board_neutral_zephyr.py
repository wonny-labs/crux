"""Crux's Zephyr integration names no board and no SoC.

A board is a build input (`west build -b <board>`), and what a board has comes from its devicetree and
Kconfig, so Crux selects a provider or a driver-specific code path by generic facts: a devicetree chosen
node, alias or compatible, a DT_HAS_<compatible>_ENABLED symbol, or a generic Kconfig symbol
(docs/porting-to-a-new-board.md#board-neutral-conventions). These checks run on the host without a Zephyr
SDK:

- No public Crux Kconfig symbol has a board or SoC name, except the deprecated aliases listed here.
- No Crux Kconfig expression, and no C or CMake source of the Zephyr integration, tests a SoC or board
  symbol. `native_sim` is the one exception: it is the simulator that the test-only selections model.
- The deprecated aliases follow Zephyr's deprecation pattern and select their replacements.
- The File provider's configure step and its preprocessor guards accept the replacements on a board with
  no SoC or board symbol at all, and key on the replacements only.

With Kconfiglib available (pip's `kconfiglib`, or Zephyr's scripts/kconfig through ZEPHYR_BASE or
CRUX_WORKSPACE), the Kconfig tree itself is evaluated as well. The Zephyr-level builds of these
selections are in the Zephyr CI shards (scripts/test-file-rt1060-compile.sh, scripts/test-logging.sh,
scripts/test-serial.sh, scripts/test-system.sh).
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
KCONFIG_FILES = [REPO / "zephyr/Kconfig", REPO / "zephyr/fs/reliance_edge/Kconfig"]
FILE_PORT = REPO / "components/file/ports/zephyr"
CMAKE = shutil.which("cmake")
CC = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")

# Old name -> replacement. Each alias stays for one tagged release of notice (ADR-0001 4.3, Unstable).
DEPRECATED_ALIASES = {
    "CRUX_FILE_FATFS_RT1060": "CRUX_FILE_FATFS_SDMMC",
    "CRUX_FILE_FATFS_RT1060_RAM_DISK": "CRUX_FILE_FATFS_RAM_DISK",
    "CRUX_FILE_FATFS_RT1060_COMPILE_CHECK": "CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK",
}
# Test-only symbols of the native_sim simulator (ADR-0005). native_sim is the simulator that the test
# selections model, not a board that a product runs on.
SIMULATOR_SYMBOLS = {"CRUX_SYSTEM_NATIVE_SIM_WATCHDOG"}

# Name parts that identify a board, a board family, a SoC or a SoC-specific peripheral instance.
BOARD_OR_SOC = re.compile(
    r"(?:^|_)(?:RT\d{3,4}\w*|MIMX\w*|IMXRT\w*|IMX\d\w*|EVKB?|EVKC|LPC\d+\w*|STM32\w*|NRF\d+\w*|ESP32\w*"
    r"|SAM[A-Z]?\d+\w*|NATIVE_SIM|NATIVE_POSIX|QEMU\w*|NUCLEO\w*|FRDM\w*|MCX[A-Z]?\d*\w*|RP2\d+\w*"
    r"|KINETIS|LPUART\d*|USDHC\d*|WDOG\d+)(?:_|$)")
# A Kconfig or C/CMake reference to a SoC or board symbol, other than the simulator's.
KCONFIG_BOARD_REFERENCE = re.compile(r"\b(?:SOC_\w+|BOARD_(?!NATIVE_SIM\b)\w+|BOARD\b)")
SOURCE_BOARD_REFERENCE = re.compile(
    r"\bCONFIG_SOC_\w+|\bCONFIG_BOARD_(?!NATIVE_SIM\b)\w+|\bCONFIG_BOARD\b|\bBOARD_REVISION\b|\bBOARD_QUALIFIERS\b")


def kconfig_symbols(path):
    return re.findall(r"^(?:menu)?config\s+(\w+)\s*$", path.read_text(), re.M)


def kconfig_block(name, path=REPO / "zephyr/Kconfig"):
    """Return the text of one `config NAME` block, up to the next unindented line."""
    match = re.search(rf"^config {name}\n(.*?)(?=^\S)", path.read_text() + "\nend\n", re.S | re.M)
    return match.group(1) if match else None


def kconfig_logic_lines(path):
    """The lines of a Kconfig file without comments and help text: the ones Kconfig evaluates."""
    lines = []
    in_help = None
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        if in_help is not None:
            if not stripped or indent > in_help:
                continue
            in_help = None
        if stripped in ("help", "---help---"):
            in_help = indent
            continue
        code = raw.split("#", 1)[0]
        if code.strip():
            lines.append((number, code))
    return lines


def integration_sources():
    """C, header and CMake files of the Zephyr integration: the module, its CMake and every Zephyr port."""
    roots = [REPO / "zephyr", REPO / "cmake"] + sorted((REPO / "components").glob("*/ports/zephyr"))
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_file() and (path.suffix in (".c", ".h", ".cmake") or path.name == "CMakeLists.txt"):
                yield path


class PublicKconfigNamesTest(unittest.TestCase):
    def test_the_pattern_finds_board_and_soc_names(self):
        for name in ("CRUX_FILE_FATFS_RT1060", "CRUX_FILE_FATFS_RT1060_RAM_DISK", "CRUX_X_MIMXRT1062",
                     "CRUX_LOG_LPUART1", "CRUX_X_EVKB", "CRUX_X_STM32F7", "CRUX_X_NATIVE_SIM_Y"):
            with self.subTest(name=name):
                self.assertRegex(name, BOARD_OR_SOC)
        for name in ("CRUX_FILE_FATFS_SDMMC", "CRUX_FILE_FATFS_RAM_DISK", "CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK",
                     "CRUX_SYSTEM", "CRUX_FILE_SIMULATOR", "CRUX_WEB_SESSION"):
            with self.subTest(name=name):
                self.assertNotRegex(name, BOARD_OR_SOC)

    def test_no_public_symbol_has_a_board_or_soc_name(self):
        allowed = set(DEPRECATED_ALIASES) | SIMULATOR_SYMBOLS
        for path in KCONFIG_FILES:
            for name in kconfig_symbols(path):
                if name.startswith("CRUX_") and name not in allowed:
                    with self.subTest(symbol=name, file=str(path.relative_to(REPO))):
                        self.assertNotRegex(name, BOARD_OR_SOC,
                                            "name a Crux symbol after what it selects, not after a board or SoC")

    def test_every_allowed_name_exists(self):
        names = {name for path in KCONFIG_FILES for name in kconfig_symbols(path)}
        for name in set(DEPRECATED_ALIASES) | set(DEPRECATED_ALIASES.values()) | SIMULATOR_SYMBOLS:
            with self.subTest(symbol=name):
                self.assertIn(name, names)


class KconfigDependenciesTest(unittest.TestCase):
    def test_the_pattern_finds_board_and_soc_references(self):
        for line in ("depends on CRUX_MODULE && SOC_MIMXRT1062", "depends on !BOARD_MIMXRT1060_EVK || BOARD_REVISION_B",
                     'depends on BOARD_REVISION = "B"', "default y if SOC_SERIES_IMXRT10XX"):
            with self.subTest(line=line):
                self.assertRegex(line, KCONFIG_BOARD_REFERENCE)
        self.assertNotRegex("depends on CRUX_MODULE && BOARD_NATIVE_SIM && FILE_SYSTEM", KCONFIG_BOARD_REFERENCE)

    def test_no_expression_tests_a_soc_or_board(self):
        for path in KCONFIG_FILES:
            for number, code in kconfig_logic_lines(path):
                with self.subTest(file=str(path.relative_to(REPO)), line=number):
                    self.assertNotRegex(code, KCONFIG_BOARD_REFERENCE,
                                        "depend on a generic or DT_HAS_<compatible>_ENABLED symbol instead")


class IntegrationSourcesTest(unittest.TestCase):
    def test_the_pattern_finds_board_and_soc_tests(self):
        for line in ("#if defined(CONFIG_SOC_MIMXRT1062)", "if(CONFIG_BOARD_MIMXRT1060_EVK AND",
                     'NOT BOARD_REVISION STREQUAL "B"', "defined(CONFIG_BOARD_REVISION_B)"):
            with self.subTest(line=line):
                self.assertRegex(line, SOURCE_BOARD_REFERENCE)
        self.assertNotRegex("#if defined(CONFIG_BOARD_NATIVE_SIM)", SOURCE_BOARD_REFERENCE)

    def test_the_scan_covers_the_bindings(self):
        scanned = {path.relative_to(REPO).as_posix() for path in integration_sources()}
        for name in ("components/logging/ports/zephyr/logging_binding.c",
                     "components/serial/ports/zephyr/serial_binding.c",
                     "components/system/ports/zephyr/system_binding.c",
                     "components/system/ports/zephyr/CMakeLists.txt",
                     "components/logging/ports/zephyr/CMakeLists.txt",
                     "components/file/ports/zephyr/CMakeLists.txt",
                     "components/file/ports/zephyr/file_native.c", "zephyr/CMakeLists.txt"):
            with self.subTest(name=name):
                self.assertIn(name, scanned)

    def test_no_source_tests_a_soc_or_board(self):
        for path in integration_sources():
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if SOURCE_BOARD_REFERENCE.search(line):
                    with self.subTest(file=str(path.relative_to(REPO)), line=number):
                        self.fail(f"{line.strip()}: select by devicetree (chosen, alias, compatible) or a "
                                  "generic Kconfig symbol instead")

    def test_the_system_binding_selects_the_watchdog_code_by_compatible(self):
        text = (REPO / "components/system/ports/zephyr/system_binding.c").read_text()
        self.assertIn("DT_NODE_HAS_COMPAT(SYSTEM_WDOG, nxp_imx_wdog)", text)
        self.assertNotIn("0x400b8000", text)
        self.assertNotIn("DT_NODELABEL(wdog0)", text)

    def test_the_uart_bindings_name_no_node_label(self):
        for name in ("logging/ports/zephyr/logging_binding.c", "serial/ports/zephyr/serial_binding.c"):
            with self.subTest(name=name):
                self.assertNotIn("DT_NODELABEL(", (REPO / "components" / name).read_text())


class DeprecatedAliasTest(unittest.TestCase):
    def test_each_alias_follows_the_zephyr_deprecation_pattern(self):
        for old, new in DEPRECATED_ALIASES.items():
            with self.subTest(alias=old):
                block = kconfig_block(old)
                self.assertIsNotNone(block, f"config {old} is missing")
                self.assertRegex(block, r'(?m)^\s+bool "[^"]*\[DEPRECATED\]"$')
                self.assertRegex(block, r"(?m)^\s+select DEPRECATED$")
                self.assertRegex(block, rf"(?m)^\s+select {new}$")
                self.assertIn(f"Use CONFIG_{new} instead", block)

    def test_each_alias_has_the_dependencies_of_its_replacement(self):
        # A select ignores the dependencies of the selected symbol, and Zephyr's Kconfig stops on that
        # warning, so the alias carries the same `depends on` lines.
        for old, new in DEPRECATED_ALIASES.items():
            with self.subTest(alias=old):
                depends = lambda name: re.findall(r"(?m)^\s+depends on (.*)$", kconfig_block(name))
                self.assertEqual(depends(old), depends(new))

    def test_each_replacement_is_a_prompted_bool_off_by_default(self):
        for new in DEPRECATED_ALIASES.values():
            with self.subTest(symbol=new):
                block = kconfig_block(new)
                self.assertIsNotNone(block, f"config {new} is missing")
                self.assertRegex(block, r'(?m)^\s+bool "')
                self.assertNotRegex(block, r"(?m)^\s+default y")

    def test_the_sd_card_selections_depend_on_the_disk_not_the_host(self):
        for name in ("CRUX_FILE_FATFS_SDMMC", "CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK"):
            with self.subTest(symbol=name):
                block = kconfig_block(name)
                self.assertIn("DT_HAS_ZEPHYR_SDMMC_DISK_ENABLED", block)
                self.assertIn("DISK_DRIVER_SDMMC", block)
                self.assertNotIn("USDHC", block)
        self.assertIn("DT_HAS_ZEPHYR_RAM_DISK_ENABLED", kconfig_block("CRUX_FILE_FATFS_RAM_DISK"))

    def test_reliance_edge_excludes_the_replacements(self):
        block = kconfig_block("CRUX_FILE_RELIANCE_EDGE")
        for new in DEPRECATED_ALIASES.values():
            with self.subTest(symbol=new):
                self.assertRegex(block, rf"!{new}\b")

    def test_code_keys_on_the_replacements_only(self):
        # An alias selects its replacement, so code that tests the old name would test it twice at best.
        for path in (FILE_PORT / "CMakeLists.txt", FILE_PORT / "file_native.c", REPO / "zephyr/CMakeLists.txt"):
            text = path.read_text()
            for old, new in DEPRECATED_ALIASES.items():
                with self.subTest(file=str(path.relative_to(REPO)), alias=old):
                    self.assertNotRegex(text, rf"\bCONFIG_{old}\b")
        kconfig = (REPO / "zephyr/Kconfig").read_text()
        for old in DEPRECATED_ALIASES:
            with self.subTest(alias=old):
                # Only its own block and the comment before the blocks name an alias.
                uses = [m.start() for m in re.finditer(rf"\b{old}\b", kconfig)]
                self.assertEqual(len(uses), 1, f"{old} is used outside its own block")

    def test_the_removal_is_documented(self):
        contract = (REPO / "docs/file-contract.md").read_text()
        notes = contract.split("## Migration notes", 1)
        self.assertEqual(len(notes), 2, "docs/file-contract.md needs a Migration notes section")
        for old, new in DEPRECATED_ALIASES.items():
            with self.subTest(alias=old):
                self.assertIn(f"`CONFIG_{old}`", notes[1])
                self.assertIn(f"`CONFIG_{new}`", notes[1])
        readiness = (REPO / "docs/component-readiness.md").read_text()
        self.assertIn("CONFIG_CRUX_FILE_FATFS_SDMMC", readiness)
        self.assertRegex(readiness, r"Deprecated[^|]*CRUX_FILE_FATFS_RT1060")


def load_kconfiglib():
    try:
        import kconfiglib  # noqa: PLC0415
        return kconfiglib
    except ImportError:
        pass
    candidates = [Path(os.environ[v]) for v in ("ZEPHYR_BASE",) if os.environ.get(v)]
    if os.environ.get("CRUX_WORKSPACE"):
        candidates.append(Path(os.environ["CRUX_WORKSPACE"]) / "zephyr")
    candidates.append(REPO.parent / "zephyr")
    for base in candidates:
        if (base / "scripts/kconfig/kconfiglib.py").is_file():
            sys.path.insert(0, str(base / "scripts/kconfig"))
            import kconfiglib  # noqa: PLC0415
            return kconfiglib
    return None


KCONFIGLIB = load_kconfiglib()
# The module Kconfig, then the Zephyr symbols that the File selections read, as plain prompted symbols.
# Zephyr sources module Kconfig files before the drivers, so a module's configdefault comes first.
KCONFIG_STUB = """
source "{module}"
config DEPRECATED
    bool
config CRUX_MODULE
    bool "m"
config FILE_SYSTEM
    bool "fs"
config FILE_SYSTEM_MKFS
    bool "mkfs"
config DISK_ACCESS
    bool "da"
config FAT_FILESYSTEM_ELM
    bool "fat"
config FS_FATFS_LFN
    bool "lfn"
config FS_FATFS_MAX_LFN
    int "max lfn"
    default 255
config FS_FATFS_REENTRANT
    bool "re"
config FS_FATFS_MOUNT_MKFS
    bool "mkfs at mount"
config FS_FATFS_WINDOW_ALIGNMENT
    int "window"
    default 1
config DISK_DRIVER_SDMMC
    bool "sdmmc"
config DISK_DRIVER_RAM
    bool "ram"
config DISK_DRIVER_FLASH
    bool "flash disk"
config SDHC
    bool "sdhc"
config IMX_USDHC
    bool "usdhc"
config RCAR_MMC
    bool "rcar"
config SDHC_BUFFER_ALIGNMENT
    int "align"
    default 128 if RCAR_MMC
    default 4
config DT_HAS_ZEPHYR_SDMMC_DISK_ENABLED
    bool "dt sd"
config DT_HAS_ZEPHYR_RAM_DISK_ENABLED
    bool "dt ram"
config BOARD_NATIVE_SIM
    bool "native_sim"
"""
FATFS = ("CRUX_MODULE", "FILE_SYSTEM", "FAT_FILESYSTEM_ELM", "FS_FATFS_LFN", "FS_FATFS_REENTRANT")
SD_CARD = FATFS + ("DISK_DRIVER_SDMMC", "DT_HAS_ZEPHYR_SDMMC_DISK_ENABLED", "SDHC", "IMX_USDHC")
RAM_DISK = FATFS + ("DISK_DRIVER_RAM", "DT_HAS_ZEPHYR_RAM_DISK_ENABLED")


@unittest.skipUnless(KCONFIGLIB, "Kconfiglib is not available (pip kconfiglib, or ZEPHYR_BASE)")
class KconfigEvaluationTest(unittest.TestCase):
    """The real zephyr/Kconfig on a board that has no SoC or board symbol at all."""

    def kconf(self, *enabled):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        stub = Path(tmp.name) / "Kconfig"
        stub.write_text(KCONFIG_STUB.replace("{module}", str(REPO / "zephyr/Kconfig")))
        env = dict(os.environ, srctree=str(REPO / "zephyr"))
        previous = os.environ.copy()
        os.environ.update(env)
        try:
            kconf = KCONFIGLIB.Kconfig(str(stub), warn=False)
        finally:
            os.environ.clear()
            os.environ.update(previous)
        for name in enabled:
            kconf.syms[name].set_value("y")
        return kconf

    def value(self, kconf, name):
        return kconf.syms[name].str_value

    def test_the_replacements_are_available_from_disk_facts_alone(self):
        kconf = self.kconf(*SD_CARD, "CRUX_FILE_FATFS_SDMMC")
        self.assertEqual(self.value(kconf, "CRUX_FILE_FATFS_SDMMC"), "y")
        self.assertEqual(self.value(kconf, "SDHC_BUFFER_ALIGNMENT"), "32")
        self.assertEqual(self.value(kconf, "FS_FATFS_WINDOW_ALIGNMENT"), "32")
        self.assertEqual(self.value(kconf, "DEPRECATED"), "n")
        kconf = self.kconf(*RAM_DISK, "CRUX_FILE_FATFS_RAM_DISK")
        self.assertEqual(self.value(kconf, "CRUX_FILE_FATFS_RAM_DISK"), "y")
        kconf = self.kconf(*SD_CARD, "CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK")
        self.assertEqual(self.value(kconf, "CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK"), "y")

    def test_the_buffer_alignment_default_is_keyed_by_the_usdhc_driver(self):
        # A module configdefault comes before the driver's default, so it must not lower a stricter one.
        other_host = tuple(f for f in SD_CARD if f != "IMX_USDHC")
        kconf = self.kconf(*other_host, "RCAR_MMC", "CRUX_FILE_FATFS_SDMMC")
        self.assertEqual(self.value(kconf, "SDHC_BUFFER_ALIGNMENT"), "128")
        kconf = self.kconf(*other_host, "CRUX_FILE_FATFS_SDMMC")
        self.assertEqual(self.value(kconf, "SDHC_BUFFER_ALIGNMENT"), "4")
        kconf = self.kconf(*SD_CARD, "RCAR_MMC")
        self.assertEqual(self.value(kconf, "SDHC_BUFFER_ALIGNMENT"), "128")

    def test_an_alias_selects_its_replacement_and_deprecated(self):
        for old, new in DEPRECATED_ALIASES.items():
            with self.subTest(alias=old):
                facts = RAM_DISK if "RAM_DISK" in old else SD_CARD
                kconf = self.kconf(*facts, old)
                self.assertEqual(self.value(kconf, old), "y")
                self.assertEqual(self.value(kconf, new), "y")
                self.assertEqual(self.value(kconf, "DEPRECATED"), "y")

    def test_the_sd_card_selection_needs_the_sdmmc_disk_node(self):
        facts = tuple(f for f in SD_CARD if f != "DT_HAS_ZEPHYR_SDMMC_DISK_ENABLED")
        kconf = self.kconf(*facts, "CRUX_FILE_FATFS_SDMMC", "CRUX_FILE_FATFS_RT1060")
        self.assertEqual(self.value(kconf, "CRUX_FILE_FATFS_SDMMC"), "n")
        self.assertEqual(self.value(kconf, "CRUX_FILE_FATFS_RT1060"), "n")

    def test_the_ram_disk_selection_refuses_any_card_path(self):
        for extra in ("DISK_DRIVER_SDMMC", "DISK_DRIVER_FLASH", "SDHC", "FS_FATFS_MOUNT_MKFS"):
            with self.subTest(extra=extra):
                kconf = self.kconf(*RAM_DISK, extra, "CRUX_FILE_FATFS_RAM_DISK", "CRUX_FILE_FATFS_RT1060_RAM_DISK")
                self.assertEqual(self.value(kconf, "CRUX_FILE_FATFS_RAM_DISK"), "n")
                self.assertEqual(self.value(kconf, "CRUX_FILE_FATFS_RT1060_RAM_DISK"), "n")

    def test_reliance_edge_is_refused_next_to_an_alias(self):
        kconf = self.kconf(*SD_CARD, "DISK_ACCESS", "CRUX_FS_RELIANCE_EDGE", "CRUX_FILE_FATFS_RT1060",
                           "CRUX_FILE_RELIANCE_EDGE")
        self.assertEqual(self.value(kconf, "CRUX_FILE_RELIANCE_EDGE"), "n")


CMAKE_HARNESS = """cmake_minimum_required(VERSION 3.20)
project(probe LANGUAGES C)
add_library(zephyr_interface INTERFACE)
add_custom_target(zephyr_generated_headers)
function(zephyr_append_cmake_library library)
endfunction()
{settings}
add_subdirectory("{port}" port)
"""
GENERIC_FATFS = {"CONFIG_FAT_FILESYSTEM_ELM": "y", "CONFIG_FILE_SYSTEM": "y", "CONFIG_FS_FATFS_LFN": "y",
                 "CONFIG_FS_FATFS_MAX_LFN": "255", "CONFIG_FS_FATFS_REENTRANT": "y",
                 "CONFIG_CRUX_FILE_POOL_SIZE": "4", "CONFIG_CRUX_FILE_DIR_POOL_SIZE": "2"}
GENERIC_SD = dict(GENERIC_FATFS, CONFIG_DISK_DRIVER_SDMMC="y", CONFIG_DT_HAS_ZEPHYR_SDMMC_DISK_ENABLED="y",
                  CONFIG_SDHC="y")
GENERIC_RAM = dict(GENERIC_FATFS, CONFIG_DISK_DRIVER_RAM="y", CONFIG_DT_HAS_ZEPHYR_RAM_DISK_ENABLED="y")


@unittest.skipUnless(CMAKE and CC, "cmake and a C compiler are needed")
class FileProviderConfigureTest(unittest.TestCase):
    """The provider's real CMakeLists.txt, configured with Kconfig values and no SoC or board symbol."""

    def configure(self, settings):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            lines = "\n".join(f"set({name} {value})" for name, value in settings.items())
            (source / "CMakeLists.txt").write_text(CMAKE_HARNESS.format(settings=lines, port=FILE_PORT))
            return subprocess.run([CMAKE, "-S", str(source), "-B", str(Path(tmp) / "build")], text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)

    def assertConfigures(self, settings):
        result = self.configure(settings)
        self.assertEqual(result.returncode, 0, result.stdout)

    def assertRefused(self, settings, message):
        result = self.configure(settings)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(message, result.stdout)

    def test_the_sd_card_provider_configures_on_any_board_with_the_disk(self):
        self.assertConfigures(dict(GENERIC_SD, CONFIG_CRUX_FILE_FATFS_SDMMC="y"))

    def test_the_ram_disk_provider_configures_on_any_board_with_the_disk(self):
        self.assertConfigures(dict(GENERIC_RAM, CONFIG_CRUX_FILE_FATFS_RAM_DISK="y"))

    def test_the_compile_check_configures_on_any_board_with_the_disk(self):
        self.assertConfigures(dict(GENERIC_SD, CONFIG_CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK="y"))

    def test_the_sd_card_provider_needs_the_disk(self):
        for missing in ("CONFIG_DISK_DRIVER_SDMMC", "CONFIG_DT_HAS_ZEPHYR_SDMMC_DISK_ENABLED",
                        "CONFIG_FAT_FILESYSTEM_ELM", "CONFIG_FS_FATFS_LFN"):
            with self.subTest(missing=missing):
                settings = dict(GENERIC_SD, CONFIG_CRUX_FILE_FATFS_SDMMC="y")
                del settings[missing]
                self.assertRefused(settings, "The SD card File provider requires")

    def test_the_ram_disk_provider_refuses_every_card_path(self):
        for extra in ("CONFIG_DISK_DRIVER_SDMMC", "CONFIG_SDHC", "CONFIG_DISK_DRIVER_FLASH",
                      "CONFIG_FS_FATFS_MOUNT_MKFS"):
            with self.subTest(extra=extra):
                self.assertRefused(dict(GENERIC_RAM, CONFIG_CRUX_FILE_FATFS_RAM_DISK="y", **{extra: "y"}),
                                   "The RAM disk File provider requires")

    def test_selections_stay_mutually_exclusive(self):
        cases = [
            (dict(GENERIC_SD, CONFIG_CRUX_FILE_FATFS_SDMMC="y", CONFIG_CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK="y"),
             "mutually exclusive"),
            (dict(GENERIC_RAM, CONFIG_CRUX_FILE_FATFS_RAM_DISK="y", CONFIG_CRUX_FILE_RELIANCE_EDGE="y"),
             "cannot be combined"),
            (dict(GENERIC_SD, CONFIG_CRUX_FILE_FATFS_SDMMC="y", CONFIG_CRUX_FILE_FATFS_SIMULATOR="y"),
             "cannot be combined"),
        ]
        for settings, message in cases:
            with self.subTest(settings=sorted(k for k in settings if "CRUX_FILE_" in k)):
                self.assertRefused(settings, message)

    def test_an_old_name_alone_selects_nothing(self):
        # Kconfig turns an alias into its replacement; the CMake must not look at the alias itself.
        self.assertRefused(dict(GENERIC_SD, CONFIG_CRUX_FILE_FATFS_RT1060="y"),
                           "requires an approved simulator composition")


STUB_HEADERS = {"zephyr/fs/fs.h": "#pragma once\n", "zephyr/kernel.h": "#pragma once\n"}


@unittest.skipUnless(CC, "no C compiler is installed")
class FileProviderGuardTest(unittest.TestCase):
    """The preprocessor guards of file_native.c, without Zephyr: an #error stops the preprocessor."""

    def preprocess(self, *defines):
        with tempfile.TemporaryDirectory() as tmp:
            for name, body in STUB_HEADERS.items():
                path = Path(tmp) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body)
            command = [CC, "-E", f"-I{tmp}", f"-I{REPO / 'components/file/include'}",
                       f"-I{REPO / 'components/file/src'}", f"-I{FILE_PORT}", "-DCRUX_FILE_POOL_SIZE=4",
                       "-DCRUX_FILE_DIR_POOL_SIZE=2"] + [f"-D{d}=1" for d in defines]
            command += [str(FILE_PORT / "file_native.c"), "-o", os.devnull]
            return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  timeout=60)

    FATFS = ("CONFIG_FAT_FILESYSTEM_ELM", "CONFIG_FILE_SYSTEM", "CONFIG_FS_FATFS_LFN", "CONFIG_FS_FATFS_REENTRANT")
    SD = FATFS + ("CONFIG_DISK_DRIVER_SDMMC", "CONFIG_DT_HAS_ZEPHYR_SDMMC_DISK_ENABLED", "CONFIG_SDHC")
    RAM = FATFS + ("CONFIG_DISK_DRIVER_RAM", "CONFIG_DT_HAS_ZEPHYR_RAM_DISK_ENABLED")

    def assertAccepted(self, *defines):
        result = self.preprocess(*defines)
        self.assertEqual(result.returncode, 0, result.stdout)

    def assertRefused(self, message, *defines):
        result = self.preprocess(*defines)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(message, result.stdout)

    def test_the_replacements_pass_on_a_board_with_no_soc_symbol(self):
        self.assertAccepted(*self.SD, "CONFIG_CRUX_FILE_FATFS_SDMMC")
        self.assertAccepted(*self.SD, "CONFIG_CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK")
        self.assertAccepted(*self.RAM, "CONFIG_CRUX_FILE_FATFS_RAM_DISK")

    def test_the_sd_card_guard_needs_the_disk(self):
        for missing in ("CONFIG_DISK_DRIVER_SDMMC", "CONFIG_DT_HAS_ZEPHYR_SDMMC_DISK_ENABLED"):
            with self.subTest(missing=missing):
                defines = [d for d in self.SD if d != missing] + ["CONFIG_CRUX_FILE_FATFS_SDMMC"]
                self.assertRefused("SD card File selections require", *defines)

    def test_the_ram_disk_guard_refuses_every_card_path(self):
        for extra in ("CONFIG_DISK_DRIVER_SDMMC", "CONFIG_SDHC", "CONFIG_DISK_DRIVER_FLASH"):
            with self.subTest(extra=extra):
                self.assertRefused("RAM disk File provider requires", *self.RAM, extra,
                                   "CONFIG_CRUX_FILE_FATFS_RAM_DISK")

    def test_an_old_name_alone_is_not_a_selection(self):
        self.assertRefused("requires an approved simulator composition", *self.SD, "CONFIG_CRUX_FILE_FATFS_RT1060")


if __name__ == "__main__":
    unittest.main()
