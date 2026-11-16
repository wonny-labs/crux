"""The test-image builder of the boot bench kit, run against a fake imgtool and dummy key files."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from boot_bench_support import make_bench, make_key, write_file

import build_test_images as builder  # noqa: E402

SLOT = 3145728
FAKE_IMGTOOL = """\
import json, sys
args = sys.argv[1:]
out = args[-1]
with open(out, 'wb') as stream:
    stream.write(b'FAKE-IMAGE\\n' + json.dumps(args[:-1]).encode())
"""
FAILING_IMGTOOL = "import sys\nsys.exit(3)\n"


class ImageBuilderTest(unittest.TestCase):
    def setUp(self):
        self.bench, _ = make_bench(self, with_scripts=False)
        self.handoff = self.bench / 'handoff'
        self.inputs = self.bench.parent / 'inputs'
        self.keys = self.bench.parent / 'keys'
        self.mcuboot_bin = write_file(self.inputs / 'mcuboot.bin', b'MCUBOOT-BIN')
        self.app_bin = write_file(self.inputs / 'zephyr.bin', b'UNSIGNED-APP')
        self.signed = write_file(self.inputs / 'zephyr.signed.bin', b'SIGNED-APP')
        confirmed = bytearray(b'\x00' * SLOT)
        confirmed[:4] = b'\x3d\xb8\xf3\x96'
        self.confirmed = write_file(self.inputs / 'zephyr.signed.confirmed.bin', bytes(confirmed))
        self.imgtool = write_file(self.inputs / 'imgtool.py', FAKE_IMGTOOL.encode())
        self.dev = make_key(self.keys, 'dev-ec-p256.pem')
        self.wrong_ec = make_key(self.keys / 'throwaway', 'wrong-ec-p256.pem')
        self.wrong_rsa = make_key(self.keys / 'throwaway', 'wrong-rsa-2048.pem')

    def build(self, **changes):
        kwargs = dict(handoff=self.handoff, imgtool=self.imgtool, python=sys.executable, app_bin=self.app_bin,
                      mcuboot_bin=self.mcuboot_bin, signed_bin=self.signed, signed_confirmed_bin=self.confirmed,
                      dev_key=self.dev, wrong_key_ec=self.wrong_ec, wrong_key_rsa=self.wrong_rsa)
        kwargs.update(changes)
        return builder.build_images(**kwargs)

    def imgtool_args(self, name):
        text = (self.handoff / name).read_bytes().split(b'\n', 1)[1]
        return json.loads(text)

    def test_produces_the_procedure_set(self):
        self.build()
        names = sorted(p.name for p in self.handoff.iterdir())
        self.assertEqual(names, sorted([
            'mcuboot.zephyr.bin', 'app.signed.bin', 'app.signed.confirmed.bin', 'app.padded-unconfirmed.bin',
            'app.unsigned.confirmed.bin', 'app.wrongkey-ec.confirmed.bin', 'app.wrongkey-rsa.confirmed.bin',
            'app.modified-0x300.confirmed.bin', 'app.modified-0x500.confirmed.bin', 'blank-slot0.bin']))

    def test_copies_are_byte_identical(self):
        self.build()
        self.assertEqual((self.handoff / 'mcuboot.zephyr.bin').read_bytes(), b'MCUBOOT-BIN')
        self.assertEqual((self.handoff / 'app.signed.bin').read_bytes(), b'SIGNED-APP')
        self.assertEqual((self.handoff / 'app.signed.confirmed.bin').read_bytes(), self.confirmed.read_bytes())

    def test_imgtool_arguments_per_image(self):
        self.build()
        common = ['sign', '--version', '0.0.0+0', '--header-size', '0x400', '--slot-size', '3145728',
                  '--align', '1', '--load-addr', '0x80000000']
        padded = self.imgtool_args('app.padded-unconfirmed.bin')
        self.assertEqual(padded[:len(common)], common)
        self.assertEqual(padded[len(common):], ['--pad', '-k', str(self.dev), str(self.app_bin)])
        self.assertNotIn('--confirm', padded)
        unsigned = self.imgtool_args('app.unsigned.confirmed.bin')
        self.assertEqual(unsigned[len(common):], ['--confirm', str(self.app_bin)])
        self.assertNotIn('-k', unsigned)
        for name, key in (('app.wrongkey-ec.confirmed.bin', self.wrong_ec),
                          ('app.wrongkey-rsa.confirmed.bin', self.wrong_rsa)):
            args = self.imgtool_args(name)
            self.assertEqual(args[len(common):], ['--confirm', '-k', str(key), str(self.app_bin)])
            self.assertNotIn(str(self.dev), args)

    def test_custom_signing_arguments(self):
        self.build(version='1.2.3+4', header_size='0x200', slot_size=SLOT, align='8', load_addr='0x80010000',
                   extra_sign_args=['--security-counter', 'auto'])
        args = self.imgtool_args('app.padded-unconfirmed.bin')
        self.assertIn('1.2.3+4', args)
        self.assertIn('0x200', args)
        self.assertIn('0x80010000', args)
        self.assertEqual(args[args.index('--security-counter') + 1], 'auto')

    def test_modified_images_differ_in_exactly_one_byte(self):
        self.build()
        original = self.confirmed.read_bytes()
        for name, offset in (('app.modified-0x300.confirmed.bin', 0x300), ('app.modified-0x500.confirmed.bin', 0x500)):
            data = (self.handoff / name).read_bytes()
            self.assertEqual(len(data), len(original))
            diffs = [i for i, (a, b) in enumerate(zip(original, data)) if a != b]
            self.assertEqual(diffs, [offset])
            self.assertEqual(data[offset], original[offset] ^ 0xFF)

    def test_blank_slot_is_all_ff_of_the_slot_size(self):
        self.build()
        data = (self.handoff / 'blank-slot0.bin').read_bytes()
        self.assertEqual(len(data), SLOT)
        self.assertEqual(data.count(b'\xff'), SLOT)

    def test_key_bytes_never_reach_the_outputs_or_the_record(self):
        record = self.bench / 'evidence' / 'images.json'
        self.build(record=record)
        for path in list(self.handoff.iterdir()) + [record]:
            self.assertNotIn(b'DUMMY-KEY-SENTINEL', path.read_bytes(), path.name)
        self.assertFalse(any(self.handoff.rglob('*.pem')))
        self.assertEqual(self.dev.read_bytes(), b'DUMMY-KEY-SENTINEL-dev-ec-p256.pem')
        data = json.loads(record.read_text())
        self.assertNotIn(str(self.keys), record.read_text())
        self.assertEqual({entry['name'] for entry in data['images']} >= {'app.padded-unconfirmed.bin'}, True)
        for entry in data['images']:
            self.assertEqual(len(entry['sha256']), 64)

    def test_refuses_key_inside_a_git_working_tree(self):
        tree = self.bench.parent / 'repo'
        (tree / '.git').mkdir(parents=True)
        inside = make_key(tree / 'keys', 'dev.pem')
        with self.assertRaisesRegex(builder.BuildError, 'repository'):
            self.build(dev_key=inside)
        self.assertEqual(list(self.handoff.iterdir()), [])

    def test_refuses_key_readable_by_others(self):
        loose = make_key(self.keys, 'loose.pem', mode=0o644)
        with self.assertRaisesRegex(builder.BuildError, 'mode'):
            self.build(dev_key=loose)

    def test_refuses_key_inside_the_handoff_directory(self):
        inside = make_key(self.handoff / 'k', 'dev.pem')
        with self.assertRaisesRegex(builder.BuildError, 'hand-off'):
            self.build(dev_key=inside)

    def test_refuses_the_public_test_key_and_missing_keys(self):
        public = make_key(self.keys, 'root-ec-p256.pem')
        with self.assertRaisesRegex(builder.BuildError, 'public'):
            self.build(dev_key=public)
        with self.assertRaises(builder.BuildError):
            self.build(wrong_key_ec=self.keys / 'absent.pem')

    def test_refuses_the_same_key_for_two_roles(self):
        with self.assertRaisesRegex(builder.BuildError, 'distinct'):
            self.build(wrong_key_ec=self.dev)

    def test_refuses_to_overwrite_existing_outputs(self):
        write_file(self.handoff / 'app.signed.bin', b'old')
        with self.assertRaisesRegex(builder.BuildError, 'exists'):
            self.build()
        self.assertEqual((self.handoff / 'app.signed.bin').read_bytes(), b'old')
        self.assertEqual(sorted(p.name for p in self.handoff.iterdir()), ['app.signed.bin'])

    def test_overwrite_flag_replaces(self):
        write_file(self.handoff / 'app.signed.bin', b'old')
        self.build(overwrite=True)
        self.assertEqual((self.handoff / 'app.signed.bin').read_bytes(), b'SIGNED-APP')

    def test_imgtool_failure_leaves_the_handoff_directory_untouched(self):
        failing = write_file(self.inputs / 'bad_imgtool.py', FAILING_IMGTOOL.encode())
        with self.assertRaises(builder.BuildError):
            self.build(imgtool=failing)
        self.assertEqual(list(self.handoff.iterdir()), [])
        self.assertEqual([p.name for p in self.handoff.parent.iterdir() if p.name.startswith('.stage')], [])

    def test_refuses_confirmed_image_of_the_wrong_size_and_offsets_beyond_it(self):
        short = write_file(self.inputs / 'short.bin', b'\x00' * 0x400)
        with self.assertRaisesRegex(builder.BuildError, 'slot size'):
            self.build(signed_confirmed_bin=short)
        with self.assertRaisesRegex(builder.BuildError, 'offset'):
            self.build(modify_offsets=(0x300, SLOT))

    def test_refuses_missing_inputs(self):
        with self.assertRaises(builder.BuildError):
            self.build(app_bin=self.inputs / 'nothing.bin')
        with self.assertRaises(builder.BuildError):
            self.build(imgtool=self.inputs / 'nothing.py')

    def test_does_not_modify_its_inputs(self):
        before = {p: p.read_bytes() for p in self.inputs.iterdir()}
        self.build()
        self.assertEqual(before, {p: p.read_bytes() for p in self.inputs.iterdir()})

    def test_sacrificial_files(self):
        names = builder.build_sacrificial(self.handoff)
        self.assertEqual(names, ['sacrificial-blank.bin', 'sacrificial-pattern.bin'])
        self.assertEqual((self.handoff / 'sacrificial-blank.bin').read_bytes(), b'\xff' * 4096)
        self.assertEqual((self.handoff / 'sacrificial-pattern.bin').read_bytes(), b'\xa5' * 4096)
        with self.assertRaisesRegex(builder.BuildError, 'exists'):
            builder.build_sacrificial(self.handoff)
        builder.build_sacrificial(self.handoff, overwrite=True)
        self.assertEqual(builder.main(['--handoff', str(self.handoff), '--sacrificial-only', '--overwrite']), 0)

    def test_cli_requires_every_input_unless_sacrificial_only(self):
        with self.assertRaises(SystemExit):
            builder.main(['--handoff', str(self.handoff)])

    def test_cli_key_paths_are_arguments(self):
        args = ['--handoff', str(self.handoff), '--imgtool', str(self.imgtool), '--app-bin', str(self.app_bin),
                '--mcuboot-bin', str(self.mcuboot_bin), '--signed-bin', str(self.signed),
                '--signed-confirmed-bin', str(self.confirmed), '--dev-key', str(self.dev),
                '--wrong-key-ec', str(self.wrong_ec), '--wrong-key-rsa', str(self.wrong_rsa)]
        self.assertEqual(builder.main(args), 0)
        self.assertTrue((self.handoff / 'app.padded-unconfirmed.bin').exists())
        self.assertNotEqual(builder.main(args), 0)  # outputs exist now
        with self.assertRaises(SystemExit):
            builder.main(args[:-2])  # a key argument is required


if __name__ == '__main__':
    unittest.main()
