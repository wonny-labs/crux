"""The J-Link wrapper scripts of the boot bench kit, run against a fake J-Link. No probe, no board."""
import os
from pathlib import Path
import subprocess
import unittest

from boot_bench_support import BENCH_TOOLS, FAKE_JLINK, make_bench, write_file

ALLOWED_COMMANDS = {'exec', 'usb', 'connect', 'r', 'h', 'loadfile', 'verifybin', 'q'}
BASE = '0x60000000'
SLOT0 = '0x60020000'
NAMES = {
    'mcuboot.zephyr.bin': BASE,
    'time-baseline.bin': BASE,
    'app.signed.bin': SLOT0,
    'app.signed.confirmed.bin': SLOT0,
    'app.padded-unconfirmed.bin': SLOT0,
    'app.unsigned.confirmed.bin': SLOT0,
    'app.wrongkey-ec.confirmed.bin': SLOT0,
    'app.wrongkey-rsa.confirmed.bin': SLOT0,
    'app.modified-0x300.confirmed.bin': SLOT0,
    'app.modified-0x500.confirmed.bin': SLOT0,
    'blank-slot0.bin': SLOT0,
    'sacrificial-blank.bin': BASE,
    'sacrificial-pattern.bin': BASE,
}


class JlinkWrapperTest(unittest.TestCase):
    def setUp(self):
        self.bench, self.fake = make_bench(self)
        self.record = self.bench.parent / 'record'
        self.env = dict(os.environ, BENCH_PROBE_SERIAL='123456789', JLINK=str(self.fake),
                        FAKE_JLINK_RECORD=str(self.record), FAKE_JLINK_VERIFY='ok')
        self.env.pop('BENCH_PRINT_ONLY', None)

    def run_script(self, script, *args, **env):
        merged = dict(self.env, **env)
        return subprocess.run([str(self.bench / script), *args], env=merged, capture_output=True, text=True)

    def put(self, name, size=64):
        return write_file(self.bench / 'handoff' / name, b'\x5a' * size)

    def commands(self, text):
        return [line.split()[0] for line in text.splitlines() if line.strip()]

    def assert_refused(self, script, *args, **env):
        result = self.run_script(script, *args, **env)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(Path(str(self.record) + '.cmd').exists(), 'J-Link must not start')
        self.assertFalse(Path(str(self.record) + '.args').exists(), 'J-Link must not start')
        return result

    def test_load_command_file_per_name(self):
        for name, address in NAMES.items():
            with self.subTest(name=name):
                self.put(name)
                result = self.run_script('jlink-load.sh', name, BENCH_PRINT_ONLY='1')
                self.assertEqual(result.returncode, 0, result.stderr)
                cmd = (self.bench / 'cmd' / f'load-{name}.jlink').read_text().splitlines()
                self.assertEqual(cmd[0], 'exec DisableAutoUpdateFW')
                self.assertEqual(cmd[1], 'usb 123456789')
                self.assertEqual(cmd[2], 'connect')
                self.assertEqual(cmd[3:5], ['r', 'h'])
                self.assertEqual(cmd[5], f'loadfile "{self.bench.resolve()}/handoff/{name}", {address}')
                self.assertEqual(cmd[-1], 'q')
                self.assertEqual(len(cmd), 7)

    def test_verify_command_file_per_name(self):
        for name, address in NAMES.items():
            with self.subTest(name=name):
                self.put(name)
                result = self.run_script('jlink-verify.sh', name, BENCH_PRINT_ONLY='1')
                self.assertEqual(result.returncode, 0, result.stderr)
                cmd = (self.bench / 'cmd' / f'verify-{name}.jlink').read_text().splitlines()
                self.assertEqual(cmd[0], 'exec DisableAutoUpdateFW')
                self.assertEqual(cmd[3], f'verifybin "{self.bench.resolve()}/handoff/{name}", {address}')
                self.assertEqual(cmd[-1], 'q')
                self.assertEqual(len(cmd), 5)

    def test_command_files_use_only_allowed_commands(self):
        for script, prefix in (('jlink-load.sh', 'load'), ('jlink-verify.sh', 'verify')):
            for name in NAMES:
                self.put(name)
                self.run_script(script, name, BENCH_PRINT_ONLY='1')
                text = (self.bench / 'cmd' / f'{prefix}-{name}.jlink').read_text()
                self.assertLessEqual(set(self.commands(text)), ALLOWED_COMMANDS, text)
                self.assertNotIn('erase', text.lower())

    def test_print_only_does_not_start_jlink(self):
        self.put('mcuboot.zephyr.bin')
        result = self.run_script('jlink-load.sh', 'mcuboot.zephyr.bin', BENCH_PRINT_ONLY='1')
        self.assertEqual(result.returncode, 0)
        self.assertIn('-CommandFile', result.stdout)
        self.assertFalse(Path(str(self.record) + '.args').exists())

    def test_accepts_the_full_path_of_a_handoff_file(self):
        path = self.put('app.signed.bin')
        result = self.run_script('jlink-load.sh', str(path), BENCH_PRINT_ONLY='1')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_commander_arguments(self):
        self.put('app.signed.bin')
        result = self.run_script('jlink-verify.sh', 'app.signed.bin')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        args = Path(str(self.record) + '.args').read_text().splitlines()
        self.assertEqual(args[:-1], ['-Device', 'MIMXRT1062xxx6A', '-If', 'SWD', '-Speed', '400', '-NoGui', '1',
                                     '-ExitOnError', '1', '-AutoConnect', '0', '-CommandFile'])
        self.assertTrue(args[-1].endswith('verify-app.signed.bin.jlink'))
        self.assertTrue(Path(str(self.record) + '.cmd').read_text().startswith('exec DisableAutoUpdateFW\n'))

    def test_verify_fails_without_success_line(self):
        self.put('app.signed.bin')
        result = self.run_script('jlink-verify.sh', 'app.signed.bin', FAKE_JLINK_VERIFY='no')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Verify successful', result.stderr)

    def test_verify_passes_with_success_line_and_prints_output(self):
        self.put('app.signed.bin')
        result = self.run_script('jlink-verify.sh', 'app.signed.bin')
        self.assertEqual(result.returncode, 0)
        self.assertIn('Verify successful', result.stdout)

    def test_commander_exit_status_is_propagated(self):
        self.put('app.signed.bin')
        for script in ('jlink-load.sh', 'jlink-verify.sh'):
            result = self.run_script(script, 'app.signed.bin', FAKE_JLINK_EXIT='7')
            self.assertNotEqual(result.returncode, 0, script)

    def test_refuses_wrong_argument_count(self):
        self.put('app.signed.bin')
        self.assert_refused('jlink-load.sh')
        self.assert_refused('jlink-load.sh', 'app.signed.bin', 'app.signed.confirmed.bin')
        self.assert_refused('jlink-verify.sh', 'app.signed.bin', 'extra')

    def test_refuses_erase_and_fuse_arguments(self):
        self.put('app.signed.bin')
        for argument in ('erase', '--erase', 'app.erase.bin', 'ERASE', 'fuse', '--fuse=1', 'app.Fuse.bin', 'eraseall'):
            for script in ('jlink-load.sh', 'jlink-verify.sh'):
                with self.subTest(argument=argument, script=script):
                    self.assert_refused(script, argument)
        self.assert_refused('jlink-load.sh', 'app.signed.bin', 'erase')

    def test_refuses_names_outside_the_table(self):
        for name in ('manifest.json', 'evil.bin', 'app..bin', 'app.bin', 'app.x.hex', 'mcuboot.zephyr.bin.old',
                     'Mcuboot.zephyr.bin', 'app.a b.bin', 'app.$x.bin', 'app.`x`.bin', 'app.a"b.bin', '.hidden',
                     'time-baseline.bin;ls'):
            with self.subTest(name=name):
                try:
                    write_file(self.bench / 'handoff' / name, b'x' * 8)
                except OSError:
                    pass
                self.assert_refused('jlink-load.sh', name)
                self.assert_refused('jlink-verify.sh', name)

    def test_refuses_paths_outside_the_handoff_directory(self):
        other = write_file(self.bench / 'backup' / 'app.signed.bin', b'x' * 8)
        self.assert_refused('jlink-load.sh', str(other))
        self.assert_refused('jlink-load.sh', '../backup/app.signed.bin')
        self.assert_refused('jlink-load.sh', f'{self.bench}/handoff/../backup/app.signed.bin')
        self.assert_refused('jlink-load.sh', '/etc/passwd')

    def test_refuses_missing_empty_and_symlinked_files(self):
        self.assert_refused('jlink-load.sh', 'app.signed.bin')
        self.put('app.signed.bin', size=0)
        self.assert_refused('jlink-load.sh', 'app.signed.bin')
        target = write_file(self.bench / 'backup' / 'elsewhere.bin', b'x' * 8)
        (self.bench / 'handoff' / 'app.signed.confirmed.bin').symlink_to(target)
        self.assert_refused('jlink-load.sh', 'app.signed.confirmed.bin')

    def test_refuses_images_that_overrun_their_region(self):
        self.put('mcuboot.zephyr.bin', size=0x20000)
        self.assertEqual(self.run_script('jlink-load.sh', 'mcuboot.zephyr.bin', BENCH_PRINT_ONLY='1').returncode, 0)
        self.put('mcuboot.zephyr.bin', size=0x20001)
        self.assert_refused('jlink-load.sh', 'mcuboot.zephyr.bin')
        self.put('app.signed.confirmed.bin', size=0x300000)
        self.assertEqual(self.run_script('jlink-load.sh', 'app.signed.confirmed.bin',
                                         BENCH_PRINT_ONLY='1').returncode, 0)
        self.put('app.signed.confirmed.bin', size=0x300001)
        self.assert_refused('jlink-load.sh', 'app.signed.confirmed.bin')
        self.put('blank-slot0.bin', size=0x300001)
        self.assert_refused('jlink-verify.sh', 'blank-slot0.bin')
        for name in ('sacrificial-blank.bin', 'sacrificial-pattern.bin'):
            self.put(name, size=4096)
            self.assertEqual(self.run_script('jlink-load.sh', name, BENCH_PRINT_ONLY='1').returncode, 0)
            self.put(name, size=4097)
            self.assert_refused('jlink-load.sh', name)

    def test_refuses_missing_or_bad_probe_serial(self):
        self.put('app.signed.bin')
        env = dict(self.env)
        env.pop('BENCH_PROBE_SERIAL')
        result = subprocess.run([str(self.bench / 'jlink-load.sh'), 'app.signed.bin'], env=env,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        for bad in ('', 'abc', '12 34', '123;ls', '1\n2'):
            with self.subTest(serial=bad):
                self.assert_refused('jlink-load.sh', 'app.signed.bin', BENCH_PROBE_SERIAL=bad)

    def test_refuses_a_symlinked_handoff_directory_and_command_file(self):
        self.put('app.signed.bin')
        real = self.bench.parent / 'real-handoff'
        (self.bench / 'handoff').rename(real)
        (self.bench / 'handoff').symlink_to(real)
        self.assert_refused('jlink-load.sh', 'app.signed.bin')
        (self.bench / 'handoff').unlink()
        real.rename(self.bench / 'handoff')
        target = self.bench.parent / 'elsewhere.jlink'
        (self.bench / 'cmd' / 'load-app.signed.bin.jlink').symlink_to(target)
        self.assert_refused('jlink-load.sh', 'app.signed.bin')
        self.assertFalse(target.exists())

    def test_serial_length_limit(self):
        self.put('app.signed.bin')
        ok = self.run_script('jlink-load.sh', 'app.signed.bin', BENCH_PRINT_ONLY='1', BENCH_PROBE_SERIAL='1' * 12)
        self.assertEqual(ok.returncode, 0)
        self.assert_refused('jlink-load.sh', 'app.signed.bin', BENCH_PROBE_SERIAL='1' * 13)

    def test_temporary_output_is_removed(self):
        self.put('app.signed.bin')
        tmp = self.bench.parent / 'tmp'
        tmp.mkdir()
        self.run_script('jlink-verify.sh', 'app.signed.bin', TMPDIR=str(tmp))
        self.run_script('jlink-load.sh', 'app.signed.bin', TMPDIR=str(tmp), FAKE_JLINK_EXIT='3')
        self.assertEqual(list(tmp.iterdir()), [])

    def test_refuses_a_bench_path_that_would_break_the_command_file(self):
        quoted = self.bench.parent / 'we"ird'
        quoted.mkdir()
        for name in ('handoff', 'cmd'):
            (quoted / name).mkdir()
        for script in ('_jlink-common.sh', 'jlink-load.sh'):
            write_file(quoted / script, (self.bench / script).read_bytes()).chmod(0o755)
        write_file(quoted / 'handoff' / 'app.signed.bin', b'x' * 8)
        result = subprocess.run([str(quoted / 'jlink-load.sh'), 'app.signed.bin'], env=self.env,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(Path(str(self.record) + '.cmd').exists())

    def test_scripts_state_their_safety_rules(self):
        common = (BENCH_TOOLS / '_jlink-common.sh').read_text()
        self.assertIn('exec DisableAutoUpdateFW', common)
        for name in ('jlink-load.sh', 'jlink-verify.sh', '_jlink-common.sh'):
            text = (BENCH_TOOLS / name).read_text()
            self.assertTrue(text.startswith('#!/usr/bin/env bash\n'), name)
            self.assertIn('set -eu', text)
        for name in ('jlink-load.sh', 'jlink-verify.sh'):
            self.assertTrue(os.access(BENCH_TOOLS / name, os.X_OK), name)

    def test_fake_probe_is_never_the_real_tool(self):
        self.assertIn('Never touches a probe', FAKE_JLINK)


if __name__ == '__main__':
    unittest.main()
