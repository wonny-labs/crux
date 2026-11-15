"""Static rules of the RT1060-EVK Rev B management image on the Mbed TLS profile.

The image is samples/management_rt1060_mbed. These checks read its text, so the Host job runs them
without a Zephyr workspace. They hold what the cross-build cannot show on its own: the profile that was
selected, the symbols and sources that must be absent, the order of the boot steps, and the one test
form (the first account) that is off by default. The cross-build and the checks of its output are
scripts/test-management-mbed-rt1060.sh. Nothing here runs on a board.
"""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[2]
IMAGE = REPO / "samples/management_rt1060_mbed"
BOARD = "mimxrt1060_evk@B//qspi"

SOURCES = ("main.c", "composition.c", "composition.h", "medium.c", "medium.h", "first_account_test.c")
# The only private include roots of the image, each with the reason it still needs one. Remove an entry
# when the public header exists on main: a stale entry fails this test.
TRANSITIONAL_INCLUDES = {
    # Web lifecycle: ADR-0004 phase 1a PRs 4 and 5 (#448, #450) publish crux/web_session.h,
    # crux/web_management.h and crux/web_zephyr.h. Until they are on main these are the only headers.
    "crux_web_session.h",
    "crux_web_management.h",
    "crux_web_adapter.h",
}
# The first account has no public header by decision (ADR-0004 section 2): only the test form uses it.
TEST_ONLY_INCLUDES = {"crux_access_adapter.h"}
# Test code of this repository that the image takes by path, because no public form exists yet.
SHARED_FROM_TESTS = {
    "tests/native/management_composition",  # the profile files and the locks glue of the Mbed core
    "tests/native/tls_offload_probe/mbed",  # mbed.conf only
    "tests/zephyr/entropy_boot",
}


def read(name):
    return (IMAGE / name).read_text()


def strip_c_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def active_lines(text):
    """Lines of a conf, Kconfig or CMake file that are not comments."""
    return [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def all_text(*names):
    return "\n".join(read(name) for name in names)


class Layout(unittest.TestCase):
    def test_files_exist(self):
        for name in ("CMakeLists.txt", "Kconfig", "prj.conf", "testcase.yaml", "reviewed-routes.txt",
                     "site/index.html", "target.overlay", "ram_disk.overlay",
                     *("src/" + source for source in SOURCES)):
            self.assertTrue((IMAGE / name).is_file(), name)

    def test_testcase_is_build_only_for_the_one_board(self):
        text = read("testcase.yaml")
        self.assertIn("build_only: true", text)
        self.assertIn("platform_allow: [mimxrt1060_evk@B/mimxrt1062/qspi]", text)


class Profile(unittest.TestCase):
    def setUp(self):
        profile_files = [REPO / "tests/native/tls_offload_probe/mbed.conf",
                         REPO / "tests/native/management_composition/profile-psa.conf",
                         REPO / "tests/native/management_composition/mbed-threading.conf"]
        text = read("prj.conf") + "\n" + "\n".join(path.read_text() for path in profile_files)
        self.conf = "\n".join(active_lines(text))

    def test_mbed_profile_is_selected(self):
        for line in ("CONFIG_MBEDTLS=y", "CONFIG_MBEDTLS_PSA_CRYPTO_C=y", "CONFIG_PSA_CRYPTO_PROVIDER_MBEDTLS=y",
                     "CONFIG_MBEDTLS_ENABLE_HEAP=y", "CONFIG_MBEDTLS_SSL_PROTO_TLS1_3=y"):
            self.assertIn(line, self.conf)

    def test_no_wolf_and_no_ssh_anywhere(self):
        # CMakeLists.txt is left out: it names CONFIG_WOLFSSL and CONFIG_CRUX_SSH to refuse them.
        text = "\n".join(
            ["\n".join(active_lines(read(name))) for name in ("prj.conf", "Kconfig")] +
            [strip_c_comments(read("src/" + name)) for name in SOURCES])
        self.assertIsNone(re.search(r"wolf|CRUX_SSH|WOLFSSH|wolfPSA", text, re.I), "a Wolf or SSH symbol")
        self.assertNotIn("CONFIG_CRUX_SSH=y", self.conf)

    def test_no_bench_symbols(self):
        # The bench image keeps its own guards, declaration and refusal: this image shares none of them.
        text = "\n".join(strip_c_comments(read("src/" + name)) for name in SOURCES) + read("CMakeLists.txt")
        self.assertNotIn("CRUX_BENCH", text)
        self.assertNotIn("bench_guard", text)

    def test_services_of_the_task_are_selected(self):
        for symbol in ("CRUX_ACCESS", "CRUX_CONFIG_SERVICE", "CRUX_MGMT_STATUS", "CRUX_NETWORK_SETTINGS",
                       "CRUX_TLS_CERTIFICATE", "CRUX_FILE_SERVICE", "CRUX_REBOOT", "CRUX_WEB",
                       "CRUX_WEB_SESSION", "CRUX_WEB_MANAGEMENT", "CRUX_LOGGING"):
            self.assertIn(f"CONFIG_{symbol}=y", self.conf, symbol)

    def test_thread_sync_and_time_come_from_the_service_symbols(self):
        # ADR-0004 C6: the service symbol selects them, so a product's prj.conf names none of the
        # Thread, Sync or Time symbols. The tuning of the thread stack is the web session's own default.
        self.assertIsNone(re.search(r"CONFIG_CRUX_(THREAD|SYNC|TIME)[A-Z_]*=", self.conf))

    def test_https_only_and_file_backend_is_a_ram_disk(self):
        self.assertNotIn("CRUX_WEB_PLAIN_HTTP_FOR_TESTS=y", self.conf)
        self.assertIn("CONFIG_CRUX_FILE_FATFS_RT1060_RAM_DISK=y", self.conf)
        self.assertIn("CONFIG_DISK_DRIVER_SDMMC=n", self.conf)  # no card driver: nothing to format
        self.assertIn("CONFIG_FS_FATFS_MOUNT_MKFS=n", self.conf)
        self.assertIn("CONFIG_CRUX_NETWORK_SETTINGS_NO_APPLY=y", self.conf)

    def test_no_test_entropy_and_trng_is_the_source(self):
        self.assertNotIn("CONFIG_TEST_RANDOM_GENERATOR=y", self.conf)
        self.assertNotRegex(self.conf, r"FAKE_ENTROPY")
        self.assertIn("CONFIG_ENTROPY_GENERATOR=y", self.conf)
        self.assertIn("CONFIG_HWINFO=y", self.conf)

    def test_shell_is_off(self):
        self.assertIn("CONFIG_SHELL=n", self.conf)

    def test_first_account_form_is_not_set_in_prj_conf(self):
        self.assertNotIn("TEST_FIRST_ACCOUNT", self.conf)


class Cmake(unittest.TestCase):
    def setUp(self):
        self.cmake = read("CMakeLists.txt")

    def test_board_is_refused_unless_exact(self):
        self.assertIn(BOARD, self.cmake)
        self.assertRegex(self.cmake, r"CONFIG_BOARD_TARGET")
        self.assertRegex(self.cmake, r"FATAL_ERROR")

    def test_profile_files_are_the_mbed_ones(self):
        for name in ("tls_offload_probe/mbed.conf", "profile-psa.conf", "mbed-threading.conf"):
            self.assertIn(name, self.cmake)
        self.assertNotIn("wolf.conf", self.cmake)
        self.assertNotIn("wolf-ssh", self.cmake)

    def test_entropy_is_fail_closed_at_configuration(self):
        self.assertIn("cmake/CruxMbedtlsEntropy.cmake", self.cmake)
        self.assertIn("crux_mbedtls_fail_closed_entropy()", self.cmake)
        # The correction is made before anything is linked, and a refusal of test entropy is spelled out.
        self.assertRegex(self.cmake, r"TEST_RANDOM_GENERATOR")
        self.assertRegex(self.cmake, r"ENTROPY_MCUX_TRNG")

    def test_shared_test_code_is_only_the_listed_directories(self):
        used = set(re.findall(r"tests/[A-Za-z0-9_/]+", self.cmake))
        used = {path for path in used if not path.endswith("/")}
        self.assertTrue(used, "the image takes the locks glue and the entropy boot check by path")
        for path in used:
            self.assertTrue(any(path.startswith(allowed) for allowed in SHARED_FROM_TESTS), path)

    def test_no_private_source_or_port_directory(self):
        # Only the transitional web directories and the test form's adapter directory may be added.
        # The include() of a component's sources.cmake is how the route sources are named, not an include root.
        text = "\n".join(line for line in self.cmake.splitlines() if not line.lstrip().startswith(("include(", "#")))
        directories = re.findall(r"components/[a-z_]+/(?:src|ports|host|zephyr|tests|[a-z_/]+)", text)
        allowed = {"components/web/session", "components/web/management", "components/web/adapter",
                   "components/access/adapter"}
        for directory in directories:
            self.assertIn(directory.rstrip("/"), allowed, directory)

    def test_service_sources_are_not_compiled_into_app(self):
        # The Zephyr module builds the cores under the service symbols. app holds only its own sources
        # and the route sources, which the module cannot build because the route table is per image.
        self.assertNotRegex(self.cmake, r"components/(access|credential|config_service|mgmt_status)/src")

    def test_first_account_source_only_under_the_form(self):
        self.assertRegex(
            self.cmake,
            r"if\s*\(\s*CONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT\s*\)[^()]*?(?:\n[^\n]*?)*?first_account_test\.c")
        # and nowhere else
        self.assertEqual(self.cmake.count("first_account_test.c"), 1)

    def test_password_comes_from_a_file_outside_the_repository(self):
        helper = read("first_account_password.cmake")
        self.assertIn("$ENV{CRUX_MBED_MGMT_PASSWORD_FILE}", helper)
        self.assertIn("inside the repository", helper)
        self.assertIn(".incbin", helper)
        self.assertNotRegex(self.cmake + helper, r"CRUX_MBED_MGMT_PASSWORD\s*[=\"]")


class Kconfig(unittest.TestCase):
    def setUp(self):
        self.kconfig = read("Kconfig")

    def block(self, symbol):
        match = re.search(rf"config {symbol}\n((?:[ \t]+.*\n|\n)*)", self.kconfig)
        self.assertIsNotNone(match, symbol)
        return match.group(1)

    def test_test_first_account_is_off_and_named_as_test_only(self):
        block = self.block("CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT")
        self.assertIn("default n", block)
        self.assertRegex(block, r'bool "[^"]*TEST ONLY')
        self.assertNotIn("default y", block)
        self.assertNotIn("select", block)

    def test_nothing_selects_or_implies_the_form(self):
        for path in (REPO / "zephyr/Kconfig", IMAGE / "prj.conf", IMAGE / "Kconfig"):
            for line in path.read_text().splitlines():
                if re.match(r"\s*(select|imply)\s+CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT", line):
                    self.fail(f"{path}: {line}")

    def test_kconfig_includes_zephyr(self):
        self.assertIn('source "Kconfig.zephyr"', self.kconfig)


class Sources(unittest.TestCase):
    def includes(self, name):
        return set(re.findall(r'#include\s+[<"]([^>"]+)[>"]', read("src/" + name)))

    def test_include_discipline(self):
        local = set(SOURCES) | {"entropy_boot.h", "crux_tf_psa_threading.h"}
        system = {"errno.h", "stdbool.h", "stddef.h", "stdint.h", "string.h", "stdio.h", "ff.h"}
        for name in SOURCES:
            if not name.endswith(".c"):
                continue
            for header in self.includes(name):
                base = header.split("/")[-1]
                if base in TRANSITIONAL_INCLUDES or base in TEST_ONLY_INCLUDES:
                    continue
                if header.startswith(("crux/", "zephyr/", "psa/")) or header in local | system:
                    continue
                self.fail(f"{name}: unexpected include {header}")

    def test_access_adapter_only_in_the_test_form(self):
        for name in SOURCES:
            uses = "crux_access_adapter.h" in self.includes(name) if name.endswith(".c") else False
            self.assertEqual(uses, name == "first_account_test.c", name)

    def test_transitional_includes_are_all_still_used(self):
        used = set()
        for name in SOURCES:
            if name.endswith(".c"):
                used |= {header.split("/")[-1] for header in self.includes(name)}
        self.assertEqual(TRANSITIONAL_INCLUDES - used, set(), "a transitional entry is stale")

    def test_test_form_checks_its_symbol_first(self):
        text = read("src/first_account_test.c")
        self.assertRegex(text, r"#ifndef CONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT\s*\n#error")

    def test_no_password_literal_and_no_printing_of_it(self):
        text = strip_c_comments(read("src/first_account_test.c"))
        self.assertNotRegex(text, r"printk\([^;]*password\s*[,)]")
        self.assertNotRegex(text, r'"[^"\n]{16,}"\s*[,;]\s*(?://|$)')

    def test_boot_order_entropy_before_any_key(self):
        text = strip_c_comments(read("src/main.c"))
        first_read = text.index("crux_entropy_boot_check()")
        for later in ("composition_address_up", "composition_core_start", "composition_services_start"):
            self.assertLess(first_read, text.index(later), later)
        # a failed read stops the image with a message, and nothing else runs
        self.assertRegex(
            text, r"crux_entropy_boot_check\(\)\)\s*\{\s*printk\([^;]*refusing to start[^;]*;\s*return")
        # nothing that makes a key runs before the read: the key is made inside the certificate start
        composition = strip_c_comments(read("src/composition.c"))
        self.assertNotIn("crux_entropy_boot_check", composition)

    def test_listener_starts_only_after_the_certificate_is_registered(self):
        text = strip_c_comments(read("src/composition.c"))
        body = text[text.index("bool composition_services_start"):]
        self.assertLess(body.index("crux_tls_certificate_start("), body.index("tls_credentials_register("))
        self.assertLess(body.index("tls_credentials_register("), body.index("crux_web_start("))
        self.assertLess(body.index("crux_web_session_init("), body.index("crux_web_start("))
        self.assertLess(body.index("crux_web_management_init("), body.index("crux_web_start("))
        self.assertIn("tls_credential_add", text)

    def test_https_only_session_config(self):
        self.assertIn('"https"', strip_c_comments(read("src/composition.c")))

    def test_medium_never_formats_a_card(self):
        text = strip_c_comments(read("src/medium.c"))
        self.assertEqual(text.count("fs_mkfs"), 1)
        self.assertIn('"RAM:"', text)
        self.assertNotIn("SD:", text)

    def test_security_events_reach_logging(self):
        self.assertIn("CONFIG_CRUX_LOGGING=y", read("prj.conf"))
        self.assertIn("crux_security_event_start", read("src/composition.c"))


class Checks(unittest.TestCase):
    def test_check_script_exists_and_is_executable_text(self):
        script = REPO / "scripts/test-management-mbed-rt1060.sh"
        self.assertTrue(script.is_file())
        text = script.read_text()
        self.assertTrue(text.startswith("#!/usr/bin/env bash"))
        self.assertIn("set -euo pipefail", text)
        self.assertIn(f"board='{BOARD}'", text)
        self.assertIn("never flashes, resets or runs one", text)


if __name__ == "__main__":
    unittest.main()
