"""The console fixture keeps to the public surface of ADR-0004 phase 1b (static checks, Host).

These checks read tests/native/cli_console, which a native_sim run (tests/native/cli_console/run.sh) builds
and runs: they hold what that run cannot show by passing. The fixture starts the console through
`<crux/cli_zephyr.h>` and includes no frozen header (`<crux/serial.h>`, `<crux/thread.h>`), no adapter
header and no console header; it links public `crux::` targets only; it does not create the first account
in code; and its UART is not the one of the Zephyr log backend.
"""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/native/cli_console"
MAIN = FIXTURE / "src/main.c"
CMAKE = FIXTURE / "CMakeLists.txt"
CONF = FIXTURE / "prj.conf"
OVERLAY = FIXTURE / "app.overlay"
RUN = FIXTURE / "run.sh"
FROZEN = ("crux/thread.h", "crux/sync.h", "crux/queue.h", "crux/serial.h")


def includes(text):
    return re.findall(r'^\s*#\s*include\s*[<"]([^>"\n]+)[>"]', text, re.M)


def code(text):
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)


class Fixture(unittest.TestCase):
    def test_the_fixture_files_exist(self):
        for path in (MAIN, CMAKE, CONF, OVERLAY, RUN):
            self.assertTrue(path.is_file(), path)

    def test_the_application_includes_public_headers_only(self):
        found = includes(MAIN.read_text())
        self.assertIn("crux/cli_zephyr.h", found)
        for name in found:
            self.assertNotIn(name, FROZEN)
            self.assertNotRegex(name, r"adapter|console|_port|internal|/src/")
        self.assertFalse([n for n in found if n.startswith("crux_")], found)

    def test_the_application_does_not_create_the_first_account_in_code(self):
        text = code(MAIN.read_text())
        self.assertNotIn("crux_access_provision_first_account", text)
        self.assertNotIn("crux_access_account_create", text)
        self.assertIn('"!setup"', MAIN.read_text())

    def test_the_cmake_links_public_targets_only_and_adds_no_private_directory(self):
        text = code(CMAKE.read_text().replace("#", "//"))
        linked = re.search(r"target_link_libraries\(app PRIVATE ([^)]*)\)", text).group(1).split()
        self.assertEqual(sorted(linked), sorted(["crux::access", "crux::credential_store", "crux::security_event",
                                                 "crux::cli", "crux::cli_zephyr", "crux::file_zephyr",
                                                 "crux::time"]))
        for forbidden in ("/adapter", "/src\"", "/console", "components/cli", "components/access"):
            self.assertNotIn(forbidden, text)
        self.assertNotIn("crux_cli_zephyr)", text)

    def test_the_configuration_names_the_service_symbols_and_not_thread_sync_or_time(self):
        conf = CONF.read_text()
        for symbol in ("CRUX_ACCESS", "CRUX_SERIAL", "CRUX_CLI", "CRUX_CLI_CONSOLE"):
            self.assertRegex(conf, rf"(?m)^CONFIG_{symbol}=y$")
        self.assertNotRegex(conf, r"CONFIG_CRUX_(THREAD|SYNC|TIME)[A-Z_]*=")
        self.assertRegex(conf, r"(?m)^CONFIG_SHELL=n$")
        self.assertRegex(conf, r"(?m)^CONFIG_UART_INTERRUPT_DRIVEN=y$")
        self.assertRegex(conf, r"(?m)^CONFIG_UART_USE_RUNTIME_CONFIGURE=y$")

    def test_the_console_uart_is_its_own_emulated_device_beside_the_log_uart(self):
        text = OVERLAY.read_text()
        self.assertRegex(text, r"aliases\s*\{\s*crux-serial0\s*=\s*&serial_test;")
        node = re.search(r"serial_test:\s*serial-test\s*\{(.*?)\};", text, re.S).group(1)
        self.assertIn('compatible = "zephyr,uart-emul"', node)
        self.assertRegex(node, r"tx-fifo-size = <1024>")
        self.assertIn("zephyr,log-uart = &logging_uarts", text)
        self.assertNotIn("logging_test", node)

    def test_the_number_of_cases_matches_what_the_runner_expects(self):
        cases = len(re.findall(r"^ZTEST\(cli_console, test_\d\d_", MAIN.read_text(), re.M))
        self.assertEqual(cases, 5)
        self.assertIn(f"pass = {cases}, fail = 0", RUN.read_text())

    def test_the_cases_are_numbered_in_the_order_they_depend_on(self):
        names = re.findall(r"^ZTEST\(cli_console, (test_\d\d_\w+)\)", MAIN.read_text(), re.M)
        self.assertEqual(names, sorted(names))
        self.assertTrue(names[2].startswith("test_03_setup"))

    def test_the_runner_is_valid_shell_and_never_flashes_or_resets(self):
        result = subprocess.run(["bash", "-n", str(RUN)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = RUN.read_text()
        for forbidden in ("west flash", "west debug", "pyocd", "openocd", "JLink", "reset"):
            self.assertNotIn(forbidden, text.replace("resets anything", ""), forbidden)

    def test_the_runner_checks_the_start_the_event_port_and_the_first_account_symbols(self):
        text = RUN.read_text()
        for entry in ("crux_cli_serial_start", "crux_cli_port_event", "crux_access_provision_first_account"):
            self.assertIn(entry, text)
        self.assertIn("CONFIG_CRUX_THREAD_STACK_BYTES=8192", text)


if __name__ == "__main__":
    unittest.main()
