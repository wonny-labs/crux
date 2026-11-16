"""The evidence-directory helper and the boot-time extractor of the boot bench kit. Synthetic inputs only."""
import hashlib
import json
from pathlib import Path
import re
import unittest

from boot_bench_support import BENCH_TOOLS, SHELL_SCRIPTS, make_bench, mode_of, write_file

import boot_timing  # noqa: E402
import console_log  # noqa: E402
import evidence_dir  # noqa: E402

UTC = '20261116T093000Z'


class EvidenceDirTest(unittest.TestCase):
    def setUp(self):
        root = make_bench(self, with_scripts=False)[0].parent
        self.bench = root / 'fresh-bench'

    def test_init_bench_creates_directories_and_installs_the_scripts(self):
        evidence_dir.init_bench(self.bench)
        for name in ('handoff', 'cmd', 'evidence', 'backup'):
            self.assertTrue((self.bench / name).is_dir(), name)
        for name in SHELL_SCRIPTS:
            installed = self.bench / name
            self.assertEqual(installed.read_bytes(), (BENCH_TOOLS / name).read_bytes())
            self.assertEqual(mode_of(installed) & 0o111, 0o111, name)

    def test_init_bench_is_idempotent_and_keeps_existing_content(self):
        evidence_dir.init_bench(self.bench)
        write_file(self.bench / 'handoff' / 'keep.bin', b'x')
        evidence_dir.init_bench(self.bench)
        self.assertTrue((self.bench / 'handoff' / 'keep.bin').exists())

    def test_init_bench_refuses_to_replace_an_edited_script(self):
        evidence_dir.init_bench(self.bench)
        (self.bench / 'jlink-load.sh').write_text('#!/bin/sh\necho changed\n')
        with self.assertRaises(evidence_dir.EvidenceError):
            evidence_dir.init_bench(self.bench)
        self.assertIn('changed', (self.bench / 'jlink-load.sh').read_text())
        evidence_dir.init_bench(self.bench, force=True)
        self.assertEqual((self.bench / 'jlink-load.sh').read_bytes(), (BENCH_TOOLS / 'jlink-load.sh').read_bytes())

    def test_new_case_creates_a_timestamped_directory(self):
        evidence_dir.init_bench(self.bench)
        case = evidence_dir.new_case(self.bench, 'T1-boot1', utc=UTC)
        self.assertEqual(case, self.bench / 'evidence' / f'{UTC}-T1-boot1')
        self.assertTrue(case.is_dir())

    def test_new_case_uses_the_clock_by_default(self):
        evidence_dir.init_bench(self.bench)
        case = evidence_dir.new_case(self.bench, 'T0')
        self.assertRegex(case.name, r'^\d{8}T\d{6}Z-T0$')

    def test_new_case_never_reuses_a_name(self):
        evidence_dir.init_bench(self.bench)
        evidence_dir.new_case(self.bench, 'T1-boot1', utc=UTC)
        with self.assertRaises(evidence_dir.EvidenceError):
            evidence_dir.new_case(self.bench, 'T1-boot1', utc=UTC)

    def test_new_case_refuses_bad_labels_times_and_uninitialised_benches(self):
        evidence_dir.init_bench(self.bench)
        for label in ('', 'a b', '../x', 'a/b', '.hidden', 'x;y', '-lead'):
            with self.subTest(label=label), self.assertRaises(evidence_dir.EvidenceError):
                evidence_dir.new_case(self.bench, label, utc=UTC)
        for utc in ('2026-11-16', '20261116T0930Z', UTC + 'x', '../' + UTC):
            with self.subTest(utc=utc), self.assertRaises(evidence_dir.EvidenceError):
                evidence_dir.new_case(self.bench, 'T0', utc=utc)
        with self.assertRaises(evidence_dir.EvidenceError):
            evidence_dir.new_case(self.bench.parent / 'nowhere', 'T0', utc=UTC)

    def test_seal_writes_sha256sums_for_every_file(self):
        evidence_dir.init_bench(self.bench)
        case = evidence_dir.new_case(self.bench, 'T2', utc=UTC)
        write_file(case / 'console.log', b'hello')
        write_file(case / 'tool-1' / 'rx.bin', b'raw')
        sums = evidence_dir.seal(case)
        lines = sums.read_text().splitlines()
        self.assertEqual(sorted(lines), sorted([
            f'{hashlib.sha256(b"hello").hexdigest()}  console.log',
            f'{hashlib.sha256(b"raw").hexdigest()}  tool-1/rx.bin']))
        self.assertEqual(sums.name, 'SHA256SUMS')

    def test_seal_refuses_twice_symlinks_and_empty_directories(self):
        evidence_dir.init_bench(self.bench)
        case = evidence_dir.new_case(self.bench, 'T2', utc=UTC)
        with self.assertRaises(evidence_dir.EvidenceError):
            evidence_dir.seal(case)
        write_file(case / 'a.log', b'x')
        evidence_dir.seal(case)
        with self.assertRaises(evidence_dir.EvidenceError):
            evidence_dir.seal(case)
        other = evidence_dir.new_case(self.bench, 'T3', utc=UTC)
        write_file(other / 'a.log', b'x')
        (other / 'link').symlink_to(other / 'a.log')
        with self.assertRaises(evidence_dir.EvidenceError):
            evidence_dir.seal(other)

    def test_verify_seal_detects_changes(self):
        evidence_dir.init_bench(self.bench)
        case = evidence_dir.new_case(self.bench, 'T2', utc=UTC)
        write_file(case / 'a.log', b'x')
        evidence_dir.seal(case)
        self.assertEqual(evidence_dir.verify_seal(case), [])
        write_file(case / 'a.log', b'y')
        write_file(case / 'new.log', b'z')
        problems = '\n'.join(evidence_dir.verify_seal(case))
        self.assertIn('a.log: hash differs', problems)
        self.assertIn('new.log: not sealed', problems)

    def test_session_record(self):
        evidence_dir.init_bench(self.bench)
        path = evidence_dir.write_session(
            self.bench, operator='Bench Person', crux_revision='a' * 40, zephyr_revision='b' * 40,
            mcuboot_revision='c' * 40, approvals=['task-record#1', 'task-record#2'], utc=UTC,
            notes='first session')
        data = json.loads(path.read_text())
        self.assertEqual(path, self.bench / 'evidence' / f'session-{UTC}.json')
        self.assertEqual(data['utc'], UTC)
        self.assertEqual(data['operator'], 'Bench Person')
        self.assertEqual(data['approvals'], ['task-record#1', 'task-record#2'])
        self.assertEqual(data['crux_revision'], 'a' * 40)
        self.assertIn('system', data['host'])
        with self.assertRaises(evidence_dir.EvidenceError):
            evidence_dir.write_session(self.bench, operator='x', crux_revision='a' * 40, zephyr_revision='b' * 40,
                                       mcuboot_revision='c' * 40, approvals=['r'], utc=UTC)

    def test_session_refuses_missing_approvals_and_bad_revisions(self):
        evidence_dir.init_bench(self.bench)
        with self.assertRaises(evidence_dir.EvidenceError):
            evidence_dir.write_session(self.bench, operator='x', crux_revision='a' * 40, zephyr_revision='b' * 40,
                                       mcuboot_revision='c' * 40, approvals=[], utc=UTC)
        with self.assertRaises(evidence_dir.EvidenceError):
            evidence_dir.write_session(self.bench, operator='x', crux_revision='nothex', zephyr_revision='b' * 40,
                                       mcuboot_revision='c' * 40, approvals=['r'], utc=UTC)

    def test_cli(self):
        self.assertEqual(evidence_dir.main(['init-bench', '--bench', str(self.bench)]), 0)
        self.assertEqual(evidence_dir.main(['new-case', '--bench', str(self.bench), '--label', 'T0', '--utc', UTC]), 0)
        self.assertNotEqual(evidence_dir.main(['new-case', '--bench', str(self.bench), '--label', 'T0',
                                               '--utc', UTC]), 0)
        case = self.bench / 'evidence' / f'{UTC}-T0'
        write_file(case / 'a.log', b'x')
        self.assertEqual(evidence_dir.main(['seal', '--case', str(case)]), 0)
        self.assertEqual(evidence_dir.main(['verify-seal', '--case', str(case)]), 0)
        write_file(case / 'a.log', b'changed')
        self.assertNotEqual(evidence_dir.main(['verify-seal', '--case', str(case)]), 0)


def event(t, data):
    return json.dumps({'monotonic': t, 'utc': 'x', 'event': 'rx', 'hex': data.encode().hex()})


class BootTimingTest(unittest.TestCase):
    def events(self, lines):
        bench, _ = make_bench(self, with_scripts=False)
        return write_file(bench / 'events.jsonl', ('\n'.join(lines) + '\n').encode())

    def test_interval_between_two_lines(self):
        path = self.events([
            json.dumps({'monotonic': 99.0, 'utc': 'x', 'event': 'reset-start'}),
            event(100.000, 'I: Starting bootloader\r\n'),
            event(100.010, 'I: Primary   slot: version=0.0.0+0\r\n'),
            event(100.020, 'I: Image 0 RAM loading to 0x80000000 is succeeded.\r\n'),
            event(100.075, 'I: Image 0 loaded from the primary slot\r\nI: Jumping to the first image slot\r\n'),
        ])
        result = boot_timing.interval(path, r'RAM loading to 0x[0-9a-f]+ is succeeded', r'loaded from the primary slot')
        self.assertAlmostEqual(result['seconds'], 0.055, places=6)
        self.assertEqual(result['start_line'].strip(), 'I: Image 0 RAM loading to 0x80000000 is succeeded.')

    def test_lines_split_across_chunks_are_joined(self):
        path = self.events([event(1.0, 'I: Starting boot'), event(1.004, 'loader\r\n'),
                            event(1.100, 'I: Jumping to the first image slot\r\n')])
        result = boot_timing.interval(path, r'Starting bootloader', r'Jumping to the first image slot')
        self.assertAlmostEqual(result['seconds'], 0.096, places=6)  # a line's time is when its last byte arrived

    def test_missing_pattern_is_an_error(self):
        path = self.events([event(1.0, 'I: Starting bootloader\r\n')])
        with self.assertRaises(boot_timing.TimingError):
            boot_timing.interval(path, r'Starting bootloader', r'never printed')
        with self.assertRaises(boot_timing.TimingError):
            boot_timing.interval(path, r'never printed', r'Starting bootloader')

    def test_end_must_not_precede_start(self):
        path = self.events([event(1.0, 'B\r\n'), event(2.0, 'A\r\n')])
        with self.assertRaises(boot_timing.TimingError):
            boot_timing.interval(path, r'^A', r'^B')

    def test_summary_of_several_boots(self):
        summary = boot_timing.summarise([0.050, 0.060, 0.055, 0.052, 0.200])
        self.assertEqual(summary['count'], 5)
        self.assertAlmostEqual(summary['min'], 0.050)
        self.assertAlmostEqual(summary['median'], 0.055)
        self.assertAlmostEqual(summary['max'], 0.200)
        with self.assertRaises(boot_timing.TimingError):
            boot_timing.summarise([])

    def test_lines_read_in_the_burst_after_a_reset_command_are_refused(self):
        done = json.dumps({'monotonic': 2.0, 'utc': 'x', 'event': 'tool_done', 'operation': 'reset', 'seconds': 1.2})
        path = self.events([event(1.0, 'old\r\n'), done,
                            event(2.01, 'I: Starting bootloader\r\nI: Jumping to the first image slot\r\n')])
        with self.assertRaisesRegex(boot_timing.TimingError, 'console_log'):
            boot_timing.interval(path, r'Starting bootloader', r'Jumping')
        result = boot_timing.interval(path, r'Starting bootloader', r'Jumping', allow_buffered=True)
        self.assertTrue(result['buffered'])
        self.assertEqual(result['seconds'], 0.0)

    def test_lines_after_the_first_chunk_are_not_a_burst(self):
        done = json.dumps({'monotonic': 2.0, 'utc': 'x', 'event': 'tool_done', 'operation': 'reset', 'seconds': 1.2})
        path = self.events([done, event(2.01, 'noise\r\n'), event(2.20, 'A\r\n'), event(2.30, 'B\r\n')])
        result = boot_timing.interval(path, r'^A', r'^B')
        self.assertFalse(result['buffered'])
        self.assertAlmostEqual(result['seconds'], 0.10, places=6)

    def test_cli(self):
        path = self.events([event(1.0, 'start\r\n'), event(1.5, 'stop\r\n')])
        self.assertEqual(boot_timing.main(['--events', str(path), '--start', 'start', '--end', 'stop']), 0)
        self.assertNotEqual(boot_timing.main(['--events', str(path), '--start', 'start', '--end', 'absent']), 0)


class FakeSerial:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.log = []
        self.in_waiting = 0
        self.closed = False

    def read(self, size):
        self.tick()
        return self.chunks.pop(0) if self.chunks else b''

    def tick(self):
        pass

    def close(self):
        self.closed = True


class ConsoleLogTest(unittest.TestCase):
    def setUp(self):
        self.root = make_bench(self, with_scripts=False)[0].parent
        self.now = [0.0]

    def clock(self):
        self.now[0] += 0.001
        return self.now[0]

    def run_log(self, chunks, **kwargs):
        fake = FakeSerial(chunks)
        out = self.root / 'boot-1' / 'events.jsonl'
        matched = console_log.log('/dev/fake', out, serial_factory=lambda port, baud: fake, clock=self.clock, **kwargs)
        return matched, out, fake

    def test_logs_chunks_until_the_pattern_and_feeds_boot_timing(self):
        matched, out, fake = self.run_log(
            [b'I: Starting bootloader\r\n', b'', b'I: Image 0 loaded from the primary slot\r\n',
             b'I: Jumping to the first image slot\r\n', b'never read'], until='Jumping to the first image slot')
        self.assertTrue(matched)
        self.assertTrue(fake.closed)
        self.assertEqual(fake.chunks, [b'never read'])
        result = boot_timing.interval(out, r'Starting bootloader', r'Jumping to the first image slot')
        self.assertGreater(result['seconds'], 0)
        self.assertFalse(result['buffered'])

    def test_timeout_is_a_result_not_an_error(self):
        matched, out, fake = self.run_log([b'only this'], until='never', timeout=0.05)
        self.assertFalse(matched)
        self.assertTrue(fake.closed)
        self.assertIn('"matched": false', out.read_text())

    def test_refuses_an_existing_output_and_never_opens_the_port(self):
        out = write_file(self.root / 'boot-1' / 'events.jsonl', b'x')
        opened = []
        with self.assertRaises(console_log.LogError):
            console_log.log('/dev/fake', out, serial_factory=lambda p, b: opened.append(1))
        self.assertEqual(opened, [])

    def test_serial_is_opened_with_dtr_and_rts_low_and_sends_nothing(self):
        text = (BENCH_TOOLS / 'console_log.py').read_text()
        self.assertRegex(text, r'connection\.dtr = False\n\s+connection\.rts = False\n\s+connection\.open\(\)')
        self.assertNotIn('.write(', text.replace('events.write(', '').replace('out.write', ''))


if __name__ == '__main__':
    unittest.main()
