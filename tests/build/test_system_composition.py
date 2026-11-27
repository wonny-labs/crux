"""Focused native configuration/ownership checks; software builds only."""
import os
from pathlib import Path
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[2]
# A fictional, compile-only board with its own name and the RT1062 SoC: it stands for a
# custom board with an i.MX RT1062 (tests/zephyr/board_fixture, no hardware).
FIXTURE_BOARD_ROOT = REPO / 'tests/zephyr/board_fixture'
FIXTURE_BOARD = 'crux_rt1062_fixture'


@unittest.skipUnless(os.environ.get('CRUX_SYSTEM_COMPOSITION_TESTS') == '1',
                     'requires pinned Zephyr environment; run scripts/test-system.sh')
class SystemCompositionTest(unittest.TestCase):
    def test_compositions(self):
        root = Path(os.environ.get('CRUX_SYSTEM_COMPOSITION_ROOT', str(REPO / 'build/system-composition')))
        root.mkdir(parents=True, exist_ok=True)
        cases = {
            'no_reboot': ('', 'CONFIG_REBOOT=n\n', 'requires CONFIG_REBOOT=y'),
            'no_hwinfo': ('', 'CONFIG_HWINFO=n\n', 'requires CONFIG_HWINFO=y'),
            'no_watchdog': ('', 'CONFIG_WATCHDOG=n\n', 'requires CONFIG_WATCHDOG=y'),
            'm3_owner': ('', 'CONFIG_CRUX_CONTROLLER_M3=y\n', 'conflicts with native owner CONFIG_CRUX_CONTROLLER_M3'),
            'wdt_shell': ('', 'CONFIG_SHELL=y\nCONFIG_WDT_SHELL=y\n', 'conflicts with native owner CONFIG_WDT_SHELL'),
            'cause_shell': ('', 'CONFIG_SHELL=y\nCONFIG_HWINFO_SHELL=y\n', 'conflicts with native owner CONFIG_HWINFO_SHELL'),
            'task_fallback': ('', 'CONFIG_TASK_WDT=y\nCONFIG_TASK_WDT_HW_FALLBACK=y\n', 'conflicts with native owner CONFIG_TASK_WDT_HW_FALLBACK'),
            'evkb_missing': ('/ { aliases { /delete-property/ crux-watchdog0; }; };', '', 'requires explicit crux-watchdog0'),
            'evkb_disabled': ('&wdog0 { status = "disabled"; };', '', 'watchdog must be enabled'),
            # The watchdog is chosen by devicetree and its code by compatible: WDOG2, another nxp,imx-wdog
            # node, builds; a node of another driver is refused.
            'evkb_wdog2': ('/ { aliases { crux-watchdog0 = &wdog1; }; };\n&wdog1 { status = "okay"; };', '', None),
            'evkb_other_driver': ('/ { aliases { crux-watchdog0 = &other_wdt; }; '
                                  'other_wdt: other-wdt { compatible = "test,watchdog"; status = "okay"; }; };', '',
                                  'Crux System unsupported watchdog driver'),
            # ADR-0005: the native_sim test watchdog is refused on the board (the component's configure error,
            # with the binding's #error as the second line) and does not bypass the existing native checks.
            'evkb_native_sim_watchdog': ('', 'CONFIG_CRUX_SYSTEM_NATIVE_SIM_WATCHDOG=y\n',
                                         'CONFIG_CRUX_SYSTEM_NATIVE_SIM_WATCHDOG is a native_sim test setting'),
            'sim_watchdog_no_watchdog': ('', 'CONFIG_CRUX_SYSTEM_NATIVE_SIM_WATCHDOG=y\nCONFIG_WATCHDOG=n\n',
                                         'requires CONFIG_WATCHDOG=y'),
            # No board revision check: Rev C of the EVK builds, by its devicetree like any board.
            'evk_revision_c': ('', '', None),
            # A custom board with an i.MX RT1062 and its own board name: accepted by devicetree, as
            # every board is.
            'custom_positive': ('', '', None),
            'custom_missing': ('/ { aliases { /delete-property/ crux-watchdog0; }; };', '',
                               'requires explicit crux-watchdog0'),
            'custom_disabled': ('&wdog0 { status = "disabled"; };', '', 'watchdog must be enabled'),
            'custom_wdog2': ('/ { aliases { crux-watchdog0 = &wdog1; }; };\n&wdog1 { status = "okay"; };', '', None),
            # Another SoC with the same watchdog block builds: no SoC or board name is checked.
            'other_soc': ('/ { aliases { crux-watchdog0 = &wdog0; }; };\n&wdog0 { status = "okay"; };', '', None),
        }
        selected = os.environ.get('CRUX_SYSTEM_COMPOSITION_CASE')
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
                target = name.startswith(('evkb_', 'evk_')) or custom or name == 'other_soc'
                modules = [str(REPO)]
                if target:
                    modules += subprocess.check_output(
                        ['west', 'list', 'cmsis', 'cmsis_6', 'hal_nxp', '-f', '{abspath}'],
                        cwd=os.environ['CRUX_WORKSPACE'], text=True).splitlines()
                board = 'mimxrt1060_evk@B//qspi' if target else 'native_sim/native/64'
                build = root / ('evkb-build' if target else 'native-build')
                extra = []
                if name == 'evk_revision_c':
                    board = 'mimxrt1060_evk@C//qspi'
                    build = root / 'revision-build'
                elif custom:
                    board = FIXTURE_BOARD
                    build = root / 'custom-build'
                    extra = [f'-DBOARD_ROOT={FIXTURE_BOARD_ROOT}']
                elif name == 'other_soc':
                    board = 'mimxrt1064_evk'
                    build = root / 'other-soc-build'
                app = REPO / ('tests/system_consumer/zephyr' if target else 'tests/system/zephyr')
                result = subprocess.run([
                    'west', 'build', '--cmake-only', '-b', board, '-d', str(build), str(app), '--',
                    f'-DZEPHYR_MODULES={";".join(modules)}',
                    f'-DKCONFIG_ROOT={REPO / "tests/board_images/integration_probe/Kconfig"}',
                    f'-DEXTRA_DTC_OVERLAY_FILE={case / "case.overlay"}',
                    f'-DEXTRA_CONF_FILE={case / "case.conf"}', *extra],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
                if result.returncode == 0:
                    built = subprocess.run(['cmake', '--build', str(build), '--target', 'crux_system_zephyr', '-j', '2'],
                                           text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
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
