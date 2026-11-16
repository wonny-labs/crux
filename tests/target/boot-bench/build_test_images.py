#!/usr/bin/env python3
"""Make the hand-off files of the boot bench from given build outputs (procedure section 4, step 6).

Inputs are the unsigned application, the signed and signed-confirmed application, the MCUboot binary, the path
of imgtool.py and the paths of three key files. This script never generates, copies, reads or stores a key: it
passes the paths to imgtool, checks that each file exists, is not readable by others and lies outside every
git working tree and outside the hand-off directory, and writes no key path into its record. Outputs are built
in a staging directory and moved into the hand-off directory only when every image succeeded. Nothing here
touches a board. Not run on a board.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

DEFAULT_SIGN_ARGS = (('--version', '0.0.0+0'), ('--header-size', '0x400'), ('--align', '1'),
                     ('--load-addr', '0x80000000'))
DEFAULT_SLOT_SIZE = 3145728
DEFAULT_OFFSETS = (0x300, 0x500)
PUBLIC_KEY_PREFIX = 'root-'  # MCUboot's published test keys: root-ec-p256.pem, root-rsa-2048.pem, ...


class BuildError(Exception):
    pass


def _file(path, what):
    path = Path(path)
    if not path.is_file():
        raise BuildError(f'{what} is not a file: {path}')
    return path


def _inside_git_tree(path):
    for parent in Path(path).resolve().parents:
        if (parent / '.git').exists():
            return parent
    return None


def _check_key(path, role, handoff):
    path = _file(path, f'{role} key')
    resolved = path.resolve()
    if path.name.startswith(PUBLIC_KEY_PREFIX):
        raise BuildError(f'{role} key {path.name} looks like a public MCUboot test key; never program images signed with it')
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & 0o077:
        raise BuildError(f'{role} key has mode {mode:04o}; it must not be readable by group or others (use 0600)')
    if handoff.resolve() in resolved.parents:
        raise BuildError(f'{role} key lies inside the hand-off directory')
    tree = _inside_git_tree(resolved)
    if tree is not None:
        raise BuildError(f'{role} key lies inside the git repository {tree}; keys stay outside every repository')
    return path


SACRIFICIAL_BYTES = 4096


def build_sacrificial(handoff, overwrite=False):
    """The two first-sector files of the ROM serial downloader check (#309): a blank sector and a sector of
    a repeated pattern. Both are synthetic, one sector long, and are loaded at the base address only."""
    handoff = Path(handoff)
    handoff.mkdir(parents=True, exist_ok=True)
    files = {'sacrificial-blank.bin': b'\xff' * SACRIFICIAL_BYTES,
             'sacrificial-pattern.bin': b'\xa5' * SACRIFICIAL_BYTES}
    if not overwrite:
        for name in files:
            if (handoff / name).exists():
                raise BuildError(f'{name} exists in the hand-off directory; use --overwrite to replace it')
    for name, data in files.items():
        (handoff / name).write_bytes(data)
    return sorted(files)


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def build_images(handoff, imgtool, python, app_bin, mcuboot_bin, signed_bin, signed_confirmed_bin,
                 dev_key, wrong_key_ec, wrong_key_rsa, version=None, header_size=None, slot_size=DEFAULT_SLOT_SIZE,
                 align=None, load_addr=None, extra_sign_args=(), modify_offsets=DEFAULT_OFFSETS,
                 overwrite=False, record=None):
    """Creates the ten hand-off files; returns the list of names. Raises BuildError and leaves handoff untouched."""
    handoff = Path(handoff)
    imgtool = _file(imgtool, 'imgtool')
    app_bin = _file(app_bin, 'unsigned application')
    mcuboot_bin = _file(mcuboot_bin, 'MCUboot binary')
    signed_bin = _file(signed_bin, 'signed application')
    signed_confirmed_bin = _file(signed_confirmed_bin, 'signed confirmed application')
    keys = {'development': _check_key(dev_key, 'development', handoff),
            'wrong-key-ec': _check_key(wrong_key_ec, 'wrong-key-ec', handoff),
            'wrong-key-rsa': _check_key(wrong_key_rsa, 'wrong-key-rsa', handoff)}
    if len({key.resolve() for key in keys.values()}) != 3:
        raise BuildError('the development key and the two throwaway keys must be three distinct files')
    confirmed = signed_confirmed_bin.read_bytes()
    if len(confirmed) != slot_size:
        raise BuildError(f'the signed confirmed image is {len(confirmed)} bytes; the slot size is {slot_size}')
    for offset in modify_offsets:
        if not 0 <= offset < len(confirmed):
            raise BuildError(f'offset {offset:#x} is outside the image')

    options = dict(DEFAULT_SIGN_ARGS)
    for key, value in (('--version', version), ('--header-size', header_size), ('--align', align),
                       ('--load-addr', load_addr)):
        if value is not None:
            options[key] = value
    sign = ['sign']
    for key in ('--version', '--header-size'):
        sign += [key, options[key]]
    sign += ['--slot-size', str(slot_size)]
    for key in ('--align', '--load-addr'):
        sign += [key, options[key]]
    sign += list(extra_sign_args)

    names = ['mcuboot.zephyr.bin', 'app.signed.bin', 'app.signed.confirmed.bin', 'app.padded-unconfirmed.bin',
             'app.unsigned.confirmed.bin', 'app.wrongkey-ec.confirmed.bin', 'app.wrongkey-rsa.confirmed.bin',
             *[f'app.modified-{offset:#x}.confirmed.bin' for offset in modify_offsets], 'blank-slot0.bin']
    handoff.mkdir(parents=True, exist_ok=True)
    if not overwrite:
        for name in names:
            if (handoff / name).exists():
                raise BuildError(f'{name} exists in the hand-off directory; use --overwrite to replace it')

    plans = [  # name, imgtool tail after `sign <args>`, key role (for the record only)
        ('app.padded-unconfirmed.bin', ['--pad'], 'development'),
        ('app.unsigned.confirmed.bin', ['--confirm'], None),
        ('app.wrongkey-ec.confirmed.bin', ['--confirm'], 'wrong-key-ec'),
        ('app.wrongkey-rsa.confirmed.bin', ['--confirm'], 'wrong-key-rsa'),
    ]
    staging = Path(tempfile.mkdtemp(prefix='.stage-', dir=str(handoff.parent)))
    commands = []
    try:
        shutil.copyfile(mcuboot_bin, staging / 'mcuboot.zephyr.bin')
        shutil.copyfile(signed_bin, staging / 'app.signed.bin')
        shutil.copyfile(signed_confirmed_bin, staging / 'app.signed.confirmed.bin')
        for name, tail, role in plans:
            command = [str(python), str(imgtool), *sign, *tail]
            if role is not None:
                command += ['-k', str(keys[role])]
            command += [str(app_bin), str(staging / name)]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if result.returncode != 0 or not (staging / name).is_file():
                raise BuildError(f'imgtool failed for {name} (exit {result.returncode}):\n'
                                 + result.stdout.decode('utf-8', 'replace'))
            shown = [Path(a).name if a == str(keys.get(role)) else a for a in command[2:-1]]
            commands.append({'name': name, 'imgtool_arguments': shown})
        for offset in modify_offsets:
            changed = bytearray(confirmed)
            changed[offset] ^= 0xFF
            (staging / f'app.modified-{offset:#x}.confirmed.bin').write_bytes(bytes(changed))
        (staging / 'blank-slot0.bin').write_bytes(b'\xff' * slot_size)
        for name in names:
            os.replace(staging / name, handoff / name)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    shutil.rmtree(staging, ignore_errors=True)

    if record is not None:
        data = {'slot_size': slot_size, 'modified_offsets': [f'{o:#x}' for o in modify_offsets],
                'imgtool_runs': commands,
                'images': [{'name': name, 'bytes': (handoff / name).stat().st_size,
                            'sha256': sha256_file(handoff / name)} for name in names]}
        Path(record).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    return names


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--sacrificial-only', action='store_true',
                        help='write only the two #309 first-sector files; no other input is needed')
    for flag in ('handoff', 'imgtool', 'app-bin', 'mcuboot-bin', 'signed-bin', 'signed-confirmed-bin',
                 'dev-key', 'wrong-key-ec', 'wrong-key-rsa'):
        parser.add_argument(f'--{flag}', type=Path, required=flag == 'handoff')
    parser.add_argument('--python', default=sys.executable, help='the Python that runs imgtool')
    parser.add_argument('--version')
    parser.add_argument('--header-size')
    parser.add_argument('--align')
    parser.add_argument('--load-addr')
    parser.add_argument('--slot-size', type=int, default=DEFAULT_SLOT_SIZE)
    parser.add_argument('--extra-sign-arg', action='append', default=[], help='an extra imgtool sign argument; repeat')
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--record', type=Path, help='write a JSON record of the runs and hashes (no key paths)')
    args = parser.parse_args(argv)
    try:
        if args.sacrificial_only:
            names = build_sacrificial(args.handoff, args.overwrite)
            print('\n'.join(names))
            return 0
        missing = [flag for flag in ('imgtool', 'app_bin', 'mcuboot_bin', 'signed_bin', 'signed_confirmed_bin',
                                     'dev_key', 'wrong_key_ec', 'wrong_key_rsa') if getattr(args, flag) is None]
        if missing:
            parser.error('required: ' + ', '.join('--' + m.replace('_', '-') for m in missing))
        names = build_images(
            handoff=args.handoff, imgtool=args.imgtool, python=args.python, app_bin=args.app_bin,
            mcuboot_bin=args.mcuboot_bin, signed_bin=args.signed_bin,
            signed_confirmed_bin=args.signed_confirmed_bin, dev_key=args.dev_key,
            wrong_key_ec=args.wrong_key_ec, wrong_key_rsa=args.wrong_key_rsa, version=args.version,
            header_size=args.header_size, slot_size=args.slot_size, align=args.align,
            load_addr=args.load_addr, extra_sign_args=args.extra_sign_arg, overwrite=args.overwrite,
            record=args.record)
    except BuildError as error:
        print(f'build_test_images: {error}', file=sys.stderr)
        return 2
    for name in names:
        print(name)
    return 0


if __name__ == '__main__':
    sys.exit(main())
