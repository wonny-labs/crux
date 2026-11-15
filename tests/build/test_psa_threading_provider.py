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
OLD_CONF = "tests/native/management_composition/mbed-threading.conf"

# What a product reads to enable Access: the sample that stands for one, the module's own files and the guides.
PRODUCT_FACING = (
    "samples/management_rt1060_mbed/CMakeLists.txt",
    "samples/management_rt1060_mbed/prj.conf",
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
        for name in ("crux_tf_psa_threading.c", "crux_tf_psa_threading.h", "crux_tf_psa_user_config.h",
                     "threading_alt.h", "CMakeLists.txt"):
            self.assertTrue((PROVIDER / name).is_file(), name)
        self.assertFalse((REPO / OLD_GLUE).exists(), "the test copy of the glue must be gone")

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
            r'config TF_PSA_CRYPTO_USER_CONFIG_FILE\n\s+default "crux_tf_psa_user_config\.h" if CRUX_PSA_THREADING')

    def test_module_builds_the_provider_only_under_the_symbol(self):
        self.assertRegex(MODULE_CMAKE, r"if\(CONFIG_CRUX_PSA_THREADING\)[\s\S]*?add_subdirectory\(\"[^\n]*/psa_threading\"")

    def test_user_config_is_the_two_threading_definitions(self):
        text = (PROVIDER / "crux_tf_psa_user_config.h").read_text()
        self.assertIn("#define MBEDTLS_THREADING_C", text)
        self.assertIn("#define MBEDTLS_THREADING_ALT", text)

    def test_provider_uses_no_test_or_wolf_header(self):
        for path in PROVIDER.glob("*"):
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

    def test_wolf_profile_is_untouched(self):
        # The option needs the Mbed provider, and nothing selects or implies it.
        self.assertNotRegex(KCONFIG, r"(select|imply)\s+CRUX_PSA_THREADING")
        self.assertIn("depends on CRUX_PILOT_MODULE && MULTITHREADING && PSA_CRYPTO_PROVIDER_MBEDTLS",
                      block("CRUX_PSA_THREADING"))


class ProductRoute(unittest.TestCase):
    def test_no_product_facing_file_names_the_test_locks(self):
        for name in PRODUCT_FACING:
            text = (REPO / name).read_text()
            self.assertNotIn(OLD_CONF, text, name)
            self.assertNotIn("tf_psa_threading/", text, name)
            self.assertNotIn("mbed-threading.conf", text, name)

    def test_sample_takes_the_public_option(self):
        cmake = (REPO / "samples/management_rt1060_mbed/CMakeLists.txt").read_text()
        conf = (REPO / "samples/management_rt1060_mbed/prj.conf").read_text()
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
