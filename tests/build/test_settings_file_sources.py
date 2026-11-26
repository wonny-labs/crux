"""Where the corrected Settings File sources of Configuration come from.

A product image with a Settings File selection of Configuration builds corrected copies of three Zephyr
Settings sources. What stages them is part of the module: the patches are in `patches/zephyr/`, and the
script and the CMake that stage them are in `zephyr/`. No file of a product build is under `tests/`, so a
copy of the repository without its tests still builds. These checks run on the host. The pinned-source
checks of the script itself are tests/native/configuration_settings_file/test_prepare.py, which the
storage gate runs.
"""
import hashlib
import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "zephyr/prepare_settings_file.py"
CMAKE = ROOT / "zephyr/settings_file.cmake"
PATCHES = ROOT / "patches/zephyr"
# The content of both corrections, unchanged by where they are stored. The second hash is also the one
# that the evidence of docs/evidence/settings-error-experiment records.
SHA256 = {
    "settings-file-error.patch": "f82e8575200a4a5fcc024c157702c8431e2c0eac5d2e4a860bb1de052c33b29e",
    "settings-store-error.patch": "37beba8c288eb30427fe17db46b2e6f7bbb87b995bf4fbc8c42fcde77ed5a118",
}
SOURCES = {
    "settings_file.c": ("subsys/settings/src/settings_file.c", "settings-file-error.patch"),
    "settings_line.c": ("subsys/settings/src/settings_line.c", None),
    "settings_store.c": ("subsys/settings/src/settings_store.c", "settings-store-error.patch"),
}


def load_script():
    spec = importlib.util.spec_from_file_location("prepare_settings_file", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def code_lines(path):
    return [line for line in path.read_text().splitlines() if not line.lstrip().startswith("#")]


def product_build_files():
    """The CMake of the module: what a product's configure step can run."""
    roots = [ROOT / "zephyr", ROOT / "cmake"] + sorted((ROOT / "components").glob("*/ports/zephyr"))
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_file() and (path.suffix == ".cmake" or path.name == "CMakeLists.txt"):
                yield path


class ModuleOwnsTheStaging(unittest.TestCase):
    def test_the_patches_are_with_the_other_zephyr_patches_and_unchanged(self):
        for name, digest in SHA256.items():
            with self.subTest(patch=name):
                path = PATCHES / name
                self.assertTrue(path.is_file(), path)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

    def test_the_patch_page_lists_both(self):
        text = (PATCHES / "README.md").read_text()
        for name in SHA256:
            self.assertIn(f"`{name}`", text, name)

    def test_the_script_stages_the_three_sources_from_the_module(self):
        module = load_script()
        found = {name: (relative, None if patch is None else patch.resolve())
                 for name, (relative, patch) in module.SOURCES.items()}
        expected = {name: (relative, None if patch is None else (PATCHES / patch).resolve())
                    for name, (relative, patch) in SOURCES.items()}
        self.assertEqual(found, expected)

    def test_the_module_includes_its_own_cmake_for_the_corrected_sources(self):
        text = "\n".join(code_lines(ROOT / "zephyr/CMakeLists.txt"))
        self.assertIn('include("${CMAKE_CURRENT_LIST_DIR}/settings_file.cmake")', text)

    def test_the_staging_cmake_watches_every_input_and_keeps_the_build_folder_name(self):
        text = CMAKE.read_text()
        for needle in ("prepare_settings_file.py", "settings-file-error.patch",
                       "settings-store-error.patch", "settings-file-candidate",
                       "subsys/settings/src/settings_file.c", "subsys/settings/src/settings_line.c",
                       "subsys/settings/src/settings_store.c", "CMAKE_CONFIGURE_DEPENDS"):
            self.assertIn(needle, text, needle)

    def test_no_module_build_file_reaches_a_test_directory(self):
        # The one exception is a test-only counter that a test option adds (zephyr/psa_threading).
        for path in product_build_files():
            for line in code_lines(path):
                if "psa_threading_counter" in line:
                    continue
                with self.subTest(file=path.relative_to(ROOT).as_posix(), line=line.strip()):
                    self.assertNotRegex(line, r"(?:\.\./|CRUX_ROOT\}?/|_repo\}/)tests/")

    def test_the_kconfig_help_sends_nobody_to_a_test_directory(self):
        self.assertNotIn("tests/native/configuration_settings_file", (ROOT / "zephyr/Kconfig").read_text())

    def test_the_old_copies_are_gone(self):
        for relative in ("tests/native/configuration_settings_file/candidate.cmake",
                         "tests/native/configuration_settings_file/prepare.py",
                         "tests/native/configuration_settings_file/settings_file.patch",
                         "tests/native/settings_error/settings_store.patch"):
            self.assertFalse((ROOT / relative).exists(), relative)

    def test_the_fixture_and_both_experiments_use_the_module_s_files(self):
        fixture = (ROOT / "tests/native/configuration_settings_file/CMakeLists.txt").read_text()
        self.assertIn("${CRUX_ROOT}/zephyr/settings_file.cmake", fixture)
        for relative in ("tests/native/configuration_settings/prepare.py",
                         "tests/native/settings_error/support.py"):
            with self.subTest(file=relative):
                self.assertIn("settings-store-error.patch", (ROOT / relative).read_text())
        # The experiment still records the shared patch's hash beside its own.
        report = (ROOT / "tests/native/settings_error/test_experiment.py").read_text()
        self.assertRegex(report, r"'patch_sha256': \{[^}]*for p in CANDIDATE_PATCHES\}")


if __name__ == "__main__":
    unittest.main()
