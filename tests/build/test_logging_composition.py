"""Actual qualified native builds; opt in with the pinned Zephyr environment."""
import os
from pathlib import Path
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[2]
# A fictional, compile-only board with its own name and the RT1062 SoC: it stands for a
# custom board with an i.MX RT1062 (tests/zephyr/board_fixture, no hardware). Its app
# overlay puts Logging on LPUART2, Serial on LPUART3, and leaves the board console on LPUART1.
FIXTURE_BOARD_ROOT = REPO / 'tests/zephyr/board_fixture'
FIXTURE_BOARD = 'crux_rt1062_fixture'


@unittest.skipUnless(os.environ.get('CRUX_LOGGING_COMPOSITION_TESTS') == '1',
                     'requires pinned Zephyr environment; run scripts/test-logging.sh')
class LoggingCompositionTest(unittest.TestCase):
    def test_rejected_compositions(self):
        root = Path(os.environ.get('CRUX_LOGGING_COMPOSITION_ROOT', str(REPO / 'build/logging-composition')))
        root.mkdir(parents=True, exist_ok=True)
        cases = {
            'missing': ('/ { chosen { /delete-property/ zephyr,log-uart; }; };', '',
                        'requires explicit zephyr,log-uart'),
            'disabled': ('&logging_test { status = "disabled"; };', '', 'UART must be enabled'),
            'multiple': ('&logging_uarts { uarts = <&logging_test &uart0>; };', '',
                         'requires exactly one UART'),
            'unsupported': ('/ { other_uart: other-uart { compatible = "crux,test-other-uart"; '
                            'status = "okay"; }; };\n&logging_uarts { uarts = <&other_uart>; };', '',
                            'unsupported UART resource'),
            # The native PTY UART is accepted under the same mode and owner checks.
            'pty_speed': ('&logging_uarts { uarts = <&uart0>; };', '', 'unsupported UART mode'),
            'pty_shell': ('&uart0 { current-speed = <115200>; };\n'
                          '&logging_uarts { uarts = <&uart0>; };',
                          'CONFIG_SHELL=y\nCONFIG_SHELL_BACKEND_SERIAL=y\n'
                          'CONFIG_SHELL_BACKEND_SERIAL_API_POLLING=y\nCONFIG_SHELL_LOG_BACKEND=n\n',
                          'conflicts with UART Shell'),
            'parity': ('&logging_test { parity = "even"; };', '', 'unsupported UART mode'),
            'flow_control': ('&logging_test { hw-flow-control; };', '', 'unsupported UART mode'),
            # The shared-Console rule is about the Console, not the board: without Logging-only routing
            # (this image has LOG_PRINTK off) a shared Console is refused on every board.
            'console': ('/ { chosen { zephyr,console = &logging_test; }; };', '',
                        'shared Console requires Logging-only routing'),
            'shell': ('/ { chosen { zephyr,shell-uart = &logging_test; }; };',
                      'CONFIG_SHELL=y\nCONFIG_SHELL_BACKEND_SERIAL=y\n'
                      'CONFIG_SHELL_BACKEND_SERIAL_API_POLLING=y\nCONFIG_SHELL_LOG_BACKEND=n\n', 'conflicts with UART Shell'),
            'serial': ('/ { aliases { crux-serial0 = &logging_test; }; };',
                       'CONFIG_CRUX_SERIAL=y\nCONFIG_UART_INTERRUPT_DRIVEN=y\n'
                       'CONFIG_UART_USE_RUNTIME_CONFIGURE=y\n', 'conflicts with'),
            'child': ('&logging_test { child { compatible = "zephyr,bt-hci-uart"; '
                      'status = "okay"; }; };', '', 'rejects UART child consumers'),
            'shell_backend': ('', 'CONFIG_SHELL=y\nCONFIG_SHELL_LOG_BACKEND=y\n',
                              'unsupported CONFIG_SHELL_LOG_BACKEND'),
            'backend': ('', 'CONFIG_LOG_BACKEND_NATIVE_POSIX=y\n', 'unsupported CONFIG_LOG_BACKEND_NATIVE_POSIX'),
            'overflow': ('', 'CONFIG_LOG_MODE_OVERFLOW=y\n', 'unsupported CONFIG_LOG_MODE_OVERFLOW'),
            'filter': ('', 'CONFIG_LOG_RUNTIME_FILTERING=y\n', 'unsupported CONFIG_LOG_RUNTIME_FILTERING'),
            'ceiling': ('', 'CONFIG_LOG_MAX_LEVEL=3\n', 'requires DEBUG native ceiling'),
            'worker': ('', 'CONFIG_LOG_PROCESS_THREAD=n\n', 'requires CONFIG_LOG_PROCESS_THREAD=y'),
            'custom_macros': ('', 'CONFIG_LOG_CUSTOM_HEADER=y\n', 'unsupported CONFIG_LOG_CUSTOM_HEADER'),
            'no_severity': ('', 'CONFIG_LOG_BACKEND_SHOW_LEVEL=n\n', 'requires CONFIG_LOG_BACKEND_SHOW_LEVEL=y'),
            'no_boundary': ('', 'CONFIG_LOG_BACKEND_CRLF_NONE=y\n', 'unsupported CONFIG_LOG_BACKEND_CRLF_NONE'),
            # No board revision check: Rev C of the EVK builds, by its devicetree like any board.
            'evk_revision_c': ('', '', None),
            'evkb_stdout': ('', 'CONFIG_STDOUT_CONSOLE=y\n', 'shared Console requires Logging-only routing'),
            'evkb_printk': ('', 'CONFIG_LOG_PRINTK=n\n', 'shared Console requires Logging-only routing'),
            'evkb_input': ('', 'CONFIG_CONSOLE_SUBSYS=y\nCONFIG_CONSOLE_GETCHAR=y\n',
                           'shared Console requires Logging-only routing'),
            'evkb_positive': ('', '', None),
            # The board's devicetree chooses the instance: another enabled LPUART builds on the EVKB as on
            # any board, with Serial off so that it has one owner.
            'evkb_lpuart3': ('&logging_uarts { uarts = <&lpuart3>; };', 'CONFIG_CRUX_SERIAL=n\n', None),
            'positive': ('', '', None),
            # A custom board with an i.MX RT1062 and its own board name: any enabled LPUART,
            # with the same mode and owner checks, as on every board.
            'custom_positive': ('', '', None),
            'custom_shared_console': ('/ { chosen { zephyr,console = &lpuart2; }; };', '', None),
            'custom_shared_stdout': ('/ { chosen { zephyr,console = &lpuart2; }; };', 'CONFIG_STDOUT_CONSOLE=y\n',
                                     'shared Console requires Logging-only routing'),
            'custom_flow_control': ('&lpuart2 { hw-flow-control; };', '', 'unsupported UART mode'),
            'custom_serial': ('/ { aliases { crux-serial0 = &lpuart2; }; };', 'CONFIG_CRUX_SERIAL=y\n',
                              'conflicts with Crux Serial'),
            'custom_not_lpuart': ('/ { log_emul: log-emul { compatible = "zephyr,uart-emul"; '
                                  'current-speed = <115200>; rx-fifo-size = <16>; tx-fifo-size = <16>; '
                                  'status = "okay"; }; };\n&logging_uarts { uarts = <&log_emul>; };', '',
                                  'unsupported UART resource'),
        }
        selected = os.environ.get('CRUX_LOGGING_COMPOSITION_CASE')
        if selected and selected not in cases:
            self.fail(f'Unknown case {selected}')
        for name, (overlay, config, diagnostic) in cases.items():
            if selected and name != selected:
                continue
            with self.subTest(case=name):
                case = root / name
                case.mkdir(exist_ok=True)
                (case / 'case.overlay').write_text(overlay)
                (case / 'case.conf').write_text(config)
                custom = name.startswith('custom_')
                target = name.startswith(('evkb_', 'evk_')) or custom
                modules = [str(REPO)]
                if target:
                    modules += subprocess.check_output(
                        ['west', 'list', 'cmsis', 'cmsis_6', 'hal_nxp', '-f', '{abspath}'],
                        cwd=os.environ['CRUX_WORKSPACE'], text=True).splitlines()
                board = 'mimxrt1060_evk@B//qspi' if target else 'native_sim/native/64'
                if name == 'evk_revision_c':
                    board = 'mimxrt1060_evk@C//qspi'
                app = REPO / ('tests/logging_consumer/zephyr' if target else 'tests/logging/zephyr')
                build = root / ('evkb-build' if target else 'native-build')
                extra = []
                if name == 'evk_revision_c':
                    build = root / 'revision-build'
                elif custom:
                    board = FIXTURE_BOARD
                    build = root / 'custom-build'
                    extra = [f'-DBOARD_ROOT={FIXTURE_BOARD_ROOT}']
                result = subprocess.run([
                    'west', 'build', '--cmake-only', '-b', board, '-d', str(build),
                    str(app), '--', f'-DZEPHYR_MODULES={";".join(modules)}',
                    f'-DEXTRA_DTC_OVERLAY_FILE={case / "case.overlay"}',
                    f'-DEXTRA_CONF_FILE={case / "case.conf"}', *extra],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
                if result.returncode == 0:
                    built = subprocess.run(['cmake', '--build', str(build),
                                            '--target', 'crux_logging_zephyr', '-j', '2'],
                                           text=True, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT, timeout=240)
                    result.stdout += built.stdout
                    result.returncode = built.returncode
                (case / 'build.log').write_text(result.stdout)
                if diagnostic:
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(diagnostic, result.stdout)
                else:
                    self.assertEqual(result.returncode, 0, result.stdout)
                print(f'{name}: {"rejected at build/configuration" if diagnostic else "build PASS"}',
                      flush=True)


if __name__ == '__main__':
    unittest.main()
