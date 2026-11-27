"""The locks of TF-PSA-Crypto's core have a public provider in the module (Experimental).

CONFIG_CRUX_ACCESS refuses an Mbed profile image without the locks of the core. They used to come from
test glue under tests/native/management_composition, so a product could not enable Access without copying a
file of tests. CONFIG_CRUX_PSA_THREADING is the module's own provider. These checks read the Kconfig, CMake,
sample and documentation text, so the Host job runs them without a Zephyr workspace. The configure and the
build are run by scripts/test-management-module.sh and the Mbed image's cross-build.
"""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[2]
KCONFIG = (REPO / "zephyr/Kconfig").read_text()
MODULE_CMAKE = (REPO / "zephyr/CMakeLists.txt").read_text()
PROVIDER = REPO / "zephyr/psa_threading"
OLD_GLUE = "tests/native/management_composition/composition/tf_psa_threading"
COUNTER_DIR = "tests/native/management_composition/composition/psa_threading_counter"
OLD_CONF = "tests/native/management_composition/mbed-threading.conf"

# What a product reads to enable Access: the sample that stands for one, the module's own files and the guides.
PRODUCT_FACING = (
    "samples/boards/nxp/mimxrt1060_evk/web_management/CMakeLists.txt",
    "samples/boards/nxp/mimxrt1060_evk/web_management/prj.conf",
    "zephyr/Kconfig",
    "zephyr/CMakeLists.txt",
    "docs/management-in-a-product.md",
    "docs/rt1060-mbed-management-image.md",
)


def block(symbol):
    match = re.search(rf"^config {symbol}\n((?:[ \t]+.*\n|\n)*)", KCONFIG, re.M)
    assert match, symbol
    return match.group(1)


class Provider(unittest.TestCase):
    def test_the_provider_sources_are_in_the_module(self):
        for name in ("crux_tf_psa_threading.c", "crux_tf_psa_user_config.h",
                     "threading_alt.h", "CMakeLists.txt"):
            self.assertTrue((PROVIDER / name).is_file(), name)
        self.assertFalse((REPO / OLD_GLUE).exists(), "the test copy of the glue must be gone")
        # The lock counter header is test code: it is not in the module directory (CONTRIBUTING.md, public headers).
        self.assertFalse((PROVIDER / "crux_tf_psa_threading.h").exists())
        self.assertTrue((REPO / COUNTER_DIR / "crux_tf_psa_threading.h").is_file())

    def test_symbol_is_experimental_and_off_by_default(self):
        text = block("CRUX_PSA_THREADING")
        self.assertIn("Experimental", text)
        self.assertIn("ADR-0001", text)
        self.assertNotRegex(text, r"default\s+y")
        self.assertIn("PSA_CRYPTO_PROVIDER_MBEDTLS", text)
        self.assertIn("MULTITHREADING", text)

    def test_symbol_sets_the_core_user_configuration_file(self):
        self.assertRegex(
            KCONFIG,
            r'(?m)^config TF_PSA_CRYPTO_USER_CONFIG_FILE\n\s+string\n'
            r'\s+default "crux_tf_psa_user_config\.h" if CRUX_PSA_THREADING\n')

    def test_the_redefinition_is_typed_and_is_not_a_configdefault(self):
        # The Mbed TLS module defines this symbol and is absent from the default workspace. A definition without a
        # type is an untyped symbol there, which kconfig.py rejects, and configdefault leaves it untyped too.
        self.assertNotRegex(KCONFIG, r"(?m)^configdefault TF_PSA_CRYPTO_USER_CONFIG_FILE")
        definitions = re.findall(r"(?m)^config TF_PSA_CRYPTO_USER_CONFIG_FILE\n((?:[ \t]+.*\n)+)", KCONFIG)
        self.assertEqual(len(definitions), 1)
        self.assertRegex(definitions[0], r"(?m)^\s+string\s*$")
        self.assertNotIn("depends", definitions[0])  # no dependency that would hide the default

    def test_the_lock_counter_is_a_native_sim_test_setting(self):
        cmake = (PROVIDER / "CMakeLists.txt").read_text()
        self.assertIn("CRUX_PSA_THREADING_TEST_COUNTER", cmake)
        self.assertRegex(cmake, r"if\(NOT CONFIG_BOARD_NATIVE_SIM\)\s+message\(FATAL_ERROR")
        source = (PROVIDER / "crux_tf_psa_threading.c").read_text()
        self.assertIn("#ifdef CRUX_PSA_THREADING_TEST_COUNTER", source)
        self.assertNotRegex(source.split("#ifdef CRUX_PSA_THREADING_TEST_COUNTER")[0], r"lock_count")
        self.assertEqual(KCONFIG.count("COUNTER"), 0, "no Kconfig name for the counter")
        for name in ("tests/native/management_composition/CMakeLists.txt",
                     "tests/native/management_module/CMakeLists.txt"):
            text = (REPO / name).read_text()
            self.assertLess(text.index("set(CRUX_PSA_THREADING_TEST_COUNTER ON)"), text.index("find_package(Zephyr"))
        for name in ("samples/boards/nxp/mimxrt1060_evk/web_management/CMakeLists.txt", "tests/native/cli_console/CMakeLists.txt"):
            self.assertNotIn("CRUX_PSA_THREADING_TEST_COUNTER", (REPO / name).read_text(), name)

    def test_option_with_another_user_config_file_is_refused(self):
        start = MODULE_CMAKE.index("if(CONFIG_CRUX_PSA_THREADING)")
        guard = MODULE_CMAKE[start:MODULE_CMAKE.index("add_subdirectory", start)]
        self.assertIn('NOT "${CONFIG_TF_PSA_CRYPTO_USER_CONFIG_FILE}" STREQUAL "crux_tf_psa_user_config.h"', guard)
        self.assertIn("FATAL_ERROR", guard)
        self.assertIn("CONFIG_CRUX_PSA_THREADING", guard)
        self.assertIn("CONFIG_TF_PSA_CRYPTO_USER_CONFIG_FILE", guard)

    def test_sample_refuses_an_image_without_the_option(self):
        cmake = (REPO / "samples/boards/nxp/mimxrt1060_evk/web_management/CMakeLists.txt").read_text()
        self.assertRegex(cmake, r"if\(NOT CONFIG_CRUX_PSA_THREADING\)\s+message\(FATAL_ERROR[^)]*CONFIG_CRUX_PSA_THREADING=y")

    def test_native_composition_refuses_the_mbed_profile_without_the_option(self):
        text = (REPO / "tests/native/management_composition/composition/composition.cmake").read_text()
        self.assertRegex(text, r"if\(CONFIG_PSA_CRYPTO_PROVIDER_MBEDTLS\)[\s\S]*?"
                               r"if\(NOT CONFIG_CRUX_PSA_THREADING\)\s+message\(FATAL_ERROR[^)]*CONFIG_CRUX_PSA_THREADING=y")

    def test_module_builds_the_provider_only_under_the_symbol(self):
        self.assertRegex(MODULE_CMAKE, r"if\(CONFIG_CRUX_PSA_THREADING\)[\s\S]*?add_subdirectory\(\"[^\n]*/psa_threading\"")

    def test_user_config_is_the_two_threading_definitions(self):
        text = (PROVIDER / "crux_tf_psa_user_config.h").read_text()
        self.assertIn("#define MBEDTLS_THREADING_C", text)
        self.assertIn("#define MBEDTLS_THREADING_ALT", text)

    def test_provider_uses_no_test_or_wolf_header(self):
        self.assertTrue(PROVIDER.is_dir())
        files = list(PROVIDER.glob("*"))
        self.assertGreaterEqual(len(files), 4)
        for path in files:
            self.assertNotRegex(path.read_text(), r"tests/|wolf", path.name)

    def test_the_missing_provider_is_refused_by_name(self):
        text = MODULE_CMAKE[MODULE_CMAKE.index("if(CONFIG_CRUX_ACCESS)"):]
        refusal = text[text.index("CONFIG_TF_PSA_CRYPTO_USER_CONFIG"):]
        refusal = refusal[:refusal.index("endif()")]
        self.assertIn("CONFIG_CRUX_ACCESS needs the locks", refusal)  # scripts/test-management-module.sh greps this
        self.assertIn("CONFIG_CRUX_PSA_THREADING", refusal)
        self.assertNotIn("tests/", refusal)

    def test_access_help_names_the_public_option(self):
        text = block("CRUX_ACCESS")
        self.assertIn("CONFIG_CRUX_PSA_THREADING", text)
        self.assertNotIn("tests/", text)

    def test_help_states_what_an_image_without_the_mbed_module_gets(self):
        # An image that leaves the option off keeps its behaviour. The module's definition of the Mbed TLS symbol has
        # no prompt and a default that applies only with this option, so without the Mbed TLS module (where Zephyr's
        # own definition is hidden) the symbol is not written to .config. kconfiglib on a reduced model shows this.
        text = " ".join(block("CRUX_PSA_THREADING").split())
        self.assertNotIn("nothing changes in an image", text)
        self.assertIn("no behaviour changes in an image that leaves it off", text)
        self.assertRegex(text, r"CONFIG_TF_PSA_CRYPTO_USER_CONFIG_FILE as a string whose default applies only "
                               r"when this option is on")
        self.assertRegex(text, r"without the Mbed TLS module[^.]*no prompt and no active default[^.]*"
                               r"not written to \.config")
        self.assertIn("nothing reads it", text)
        self.assertNotRegex(text, r"symbol, empty")

    def test_wolf_profile_is_untouched(self):
        # The option needs the Mbed provider, and nothing selects or implies it.
        self.assertNotRegex(KCONFIG, r"(select|imply)\s+CRUX_PSA_THREADING")
        self.assertIn("depends on CRUX_MODULE && MULTITHREADING && PSA_CRYPTO_PROVIDER_MBEDTLS",
                      block("CRUX_PSA_THREADING"))


class ProductRoute(unittest.TestCase):
    def test_no_product_facing_file_names_the_test_locks(self):
        for name in PRODUCT_FACING:
            text = (REPO / name).read_text()
            self.assertNotIn(OLD_CONF, text, name)
            self.assertNotIn("tf_psa_threading/", text, name)
            self.assertNotIn("mbed-threading.conf", text, name)

    def test_sample_takes_the_public_option(self):
        cmake = (REPO / "samples/boards/nxp/mimxrt1060_evk/web_management/CMakeLists.txt").read_text()
        conf = (REPO / "samples/boards/nxp/mimxrt1060_evk/web_management/prj.conf").read_text()
        self.assertRegex(conf, r"(?m)^CONFIG_CRUX_PSA_THREADING=y")
        self.assertNotIn("crux_tf_psa_threading.c", cmake)
        self.assertNotIn("management_composition/composition", cmake)

    def test_product_prj_conf_snippet_enables_access_with_the_option(self):
        doc = (REPO / "docs/management-in-a-product.md").read_text()
        snippet = re.search(r"```kconfig\n# prj\.conf of the product.*?```", doc, re.S)
        self.assertIsNotNone(snippet)
        lines = {line.split("#")[0].strip() for line in snippet.group(0).splitlines()}
        self.assertIn("CONFIG_CRUX_ACCESS=y", lines)
        self.assertIn("CONFIG_CRUX_PSA_THREADING=y", lines)
        self.assertNotIn("tests/", snippet.group(0))

    def test_guide_step_3_does_not_send_a_product_to_test_files_for_the_locks(self):
        doc = (REPO / "docs/management-in-a-product.md").read_text()
        step = re.search(r"(?m)^3\. \*\*Set the Kconfig symbols\.\*\*.*$", doc)
        self.assertIsNotNone(step)
        step = step.group(0)
        # The profile files of the test images are the reference for the algorithms and the rest, not for the locks.
        self.assertNotIn("PSA and file system symbols", step)
        profile_sentence = re.search(r"[^.]*come from the profile files that the test images use[^.]*\.", step)
        self.assertIsNotNone(profile_sentence)
        self.assertRegex(profile_sentence.group(0), r"PSA algorithm, key type and file system symbols, but not the locks")
        # The locks come from the public option, which the step names after the test files.
        self.assertIn("CONFIG_CRUX_PSA_THREADING=y", step)
        self.assertNotIn("mbed-threading.conf", step)

    def test_guides_say_experimental(self):
        for name in ("docs/management-in-a-product.md", "docs/rt1060-mbed-management-image.md"):
            text = (REPO / name).read_text()
            row = [line for line in text.splitlines() if "CRUX_PSA_THREADING" in line]
            self.assertTrue(row, name)
            self.assertTrue(any("Experimental" in line for line in row), name)

    def test_native_tests_reach_the_locks_through_the_option(self):
        conf = (REPO / "tests/native/management_composition/mbed-threading.conf").read_text()
        self.assertRegex(conf, r"(?m)^CONFIG_CRUX_PSA_THREADING=y")
        self.assertNotIn("CONFIG_TF_PSA_CRYPTO_USER_CONFIG_FILE", conf)
        for name in ("tests/native/management_composition/composition/composition.cmake",
                     "tests/native/management_module/CMakeLists.txt",
                     "tests/native/cli_console/CMakeLists.txt"):
            text = (REPO / name).read_text()
            self.assertNotIn("tf_psa_threading/", text, name)
            self.assertNotIn("crux_tf_psa_threading.c", text, name)


if __name__ == "__main__":
    unittest.main()
