"""The hand-off manifest generator of the boot bench kit. Synthetic files only."""
import hashlib
import json
from pathlib import Path
import unittest

from boot_bench_support import REPO, make_bench, write_file

import make_manifest  # noqa: E402  (path set by boot_bench_support)

REV = 'a' * 40
ZREV = 'b' * 40


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.bench, _ = make_bench(self, with_scripts=False)
        self.handoff = self.bench / 'handoff'
        write_file(self.handoff / 'mcuboot.zephyr.bin', b'boot')
        write_file(self.handoff / 'app.signed.confirmed.bin', b'signed')
        write_file(self.handoff / 'blank-slot0.bin', b'\xff' * 16)

    def generate(self, **changes):
        kwargs = dict(handoff=self.handoff, source_revision=REV, zephyr_revision=ZREV)
        kwargs.update(changes)
        return make_manifest.generate(**kwargs)

    def test_lists_every_file_sorted_with_its_hash(self):
        path = self.generate()
        self.assertEqual(path, self.handoff / 'manifest.json')
        data = json.loads(path.read_text())
        self.assertEqual(data['schema_version'], 1)
        self.assertEqual(data['board'], 'mimxrt1060_evk@B//qspi')
        self.assertEqual(data['source_revision'], REV)
        self.assertEqual(data['zephyr_revision'], ZREV)
        self.assertNotIn('build_id', data)
        self.assertEqual(data['files'], [
            {'path': 'app.signed.confirmed.bin', 'sha256': sha(b'signed')},
            {'path': 'blank-slot0.bin', 'sha256': sha(b'\xff' * 16)},
            {'path': 'mcuboot.zephyr.bin', 'sha256': sha(b'boot')},
        ])

    def test_regeneration_excludes_the_manifest_itself_and_is_stable(self):
        first = self.generate().read_text()
        self.assertEqual(self.generate().read_text(), first)
        self.assertNotIn('manifest.json', first.split('"files"')[1])

    def test_output_loads_in_the_device_control_tool_and_verifies(self):
        from device_control.manifest import Manifest
        manifest = Manifest.load(self.generate())
        manifest.verify('mimxrt1060_evk@B//qspi')
        self.assertEqual(set(manifest.files), {'app.signed.confirmed.bin', 'blank-slot0.bin', 'mcuboot.zephyr.bin'})

    def test_refuses_bad_revisions(self):
        for bad in ('', 'abc', 'G' * 40, 'A' * 40, 'a' * 39, 'a' * 41, REV + '\n'):
            with self.subTest(revision=bad):
                with self.assertRaises(make_manifest.ManifestError):
                    self.generate(source_revision=bad)
                with self.assertRaises(make_manifest.ManifestError):
                    self.generate(zephyr_revision=bad)
        self.assertFalse((self.handoff / 'manifest.json').exists())

    def test_refuses_empty_directory_subdirectory_and_symlink(self):
        empty = self.bench / 'cmd'
        with self.assertRaises(make_manifest.ManifestError):
            self.generate(handoff=empty)
        (self.handoff / 'nested').mkdir()
        with self.assertRaises(make_manifest.ManifestError):
            self.generate()
        (self.handoff / 'nested').rmdir()
        (self.handoff / 'link.bin').symlink_to(self.handoff / 'mcuboot.zephyr.bin')
        with self.assertRaises(make_manifest.ManifestError):
            self.generate()

    def test_refuses_a_missing_directory(self):
        with self.assertRaises(make_manifest.ManifestError):
            self.generate(handoff=self.bench / 'nothing-here')

    def test_check_passes_for_a_current_manifest(self):
        self.generate()
        self.assertEqual(make_manifest.check(self.handoff), [])

    def test_check_reports_changed_added_and_missing_files(self):
        self.generate()
        write_file(self.handoff / 'mcuboot.zephyr.bin', b'changed')
        write_file(self.handoff / 'extra.bin', b'x')
        (self.handoff / 'blank-slot0.bin').unlink()
        problems = make_manifest.check(self.handoff)
        joined = '\n'.join(problems)
        self.assertIn('mcuboot.zephyr.bin: hash differs', joined)
        self.assertIn('extra.bin: not listed', joined)
        self.assertIn('blank-slot0.bin: listed but missing', joined)

    def test_check_without_a_manifest_reports_it(self):
        self.assertTrue(make_manifest.check(self.handoff))

    def test_cli(self):
        self.assertEqual(make_manifest.main(['generate', '--handoff', str(self.handoff), '--source-revision', REV,
                                             '--zephyr-revision', ZREV]), 0)
        self.assertEqual(make_manifest.main(['check', '--handoff', str(self.handoff)]), 0)
        write_file(self.handoff / 'extra.bin', b'x')
        self.assertNotEqual(make_manifest.main(['check', '--handoff', str(self.handoff)]), 0)
        self.assertNotEqual(make_manifest.main(['generate', '--handoff', str(self.handoff),
                                                '--source-revision', 'bad', '--zephyr-revision', ZREV]), 0)

    def test_custom_board(self):
        data = json.loads(self.generate(board='other@B').read_text())
        self.assertEqual(data['board'], 'other@B')


if __name__ == '__main__':
    unittest.main()
