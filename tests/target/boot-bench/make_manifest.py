#!/usr/bin/env python3
"""Write or check the hand-off manifest of the boot bench: the SHA-256 of every file in <bench>/handoff/.

The manifest has the schema of tools/device_control (schema_version 1). The device-control tool checks the
files that the manifest lists; it does not check that the list is complete. `check` does: it reports a file
that is listed and missing, listed with another hash, or present and not listed. Nothing here touches a
board. Not run on a board.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

MANIFEST_NAME = 'manifest.json'
DEFAULT_BOARD = 'mimxrt1060_evk@B//qspi'
_REVISION = re.compile(r'[0-9a-f]{40}')


class ManifestError(Exception):
    pass


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _scan(handoff):
    """name -> sha256 of every file of the directory except the manifest. Refuses anything else."""
    handoff = Path(handoff)
    if not handoff.is_dir():
        raise ManifestError(f'not a directory: {handoff}')
    found = {}
    for entry in sorted(handoff.iterdir(), key=lambda p: p.name):
        if entry.name == MANIFEST_NAME:
            continue
        if entry.is_symlink():
            raise ManifestError(f'{entry.name}: a symbolic link is not a hand-off file')
        if not entry.is_file():
            raise ManifestError(f'{entry.name}: only plain files belong in the hand-off directory')
        found[entry.name] = sha256_file(entry)
    if not found:
        raise ManifestError(f'no files in {handoff}')
    return found


def _revision(name, value):
    if not isinstance(value, str) or not _REVISION.fullmatch(value):
        raise ManifestError(f'{name} must be 40 lowercase hexadecimal digits')
    return value


def generate(handoff, source_revision, zephyr_revision, board=DEFAULT_BOARD):
    """Writes <handoff>/manifest.json and returns its path. The write is atomic."""
    _revision('source revision', source_revision)
    _revision('zephyr revision', zephyr_revision)
    if not board or not isinstance(board, str):
        raise ManifestError('board must be a non-empty string')
    files = _scan(handoff)
    data = {
        'schema_version': 1,
        'board': board,
        'source_revision': source_revision,
        'zephyr_revision': zephyr_revision,
        'files': [{'path': name, 'sha256': digest} for name, digest in files.items()],
    }
    target = Path(handoff) / MANIFEST_NAME
    handle, temporary = tempfile.mkstemp(dir=str(handoff), prefix='.manifest-')
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            stream.write(json.dumps(data, indent=2) + '\n')
        os.replace(temporary, target)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    return target


def check(handoff):
    """A list of problems; empty when the manifest lists exactly the files that are there, with their hashes."""
    handoff = Path(handoff)
    manifest = handoff / MANIFEST_NAME
    try:
        data = json.loads(manifest.read_text(encoding='utf-8'))
        listed = {entry['path']: entry['sha256'] for entry in data['files']}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return [f'{MANIFEST_NAME}: cannot read the manifest ({error})']
    try:
        found = _scan(handoff)
    except ManifestError as error:
        return [str(error)]
    problems = []
    for name, digest in sorted(listed.items()):
        if name not in found:
            problems.append(f'{name}: listed but missing')
        elif found[name] != digest:
            problems.append(f'{name}: hash differs from the manifest')
    for name in sorted(set(found) - set(listed)):
        problems.append(f'{name}: not listed in the manifest')
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    commands = parser.add_subparsers(dest='command', required=True)
    gen = commands.add_parser('generate', help='write manifest.json for every file of the hand-off directory')
    gen.add_argument('--handoff', required=True, type=Path)
    gen.add_argument('--source-revision', required=True, help='git rev-parse HEAD of the Crux checkout')
    gen.add_argument('--zephyr-revision', required=True, help='git rev-parse HEAD of the Zephyr checkout')
    gen.add_argument('--board', default=DEFAULT_BOARD)
    chk = commands.add_parser('check', help='verify that the manifest is complete and current')
    chk.add_argument('--handoff', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'generate':
            path = generate(args.handoff, args.source_revision, args.zephyr_revision, args.board)
            print(f'wrote {path}')
            return 0
        problems = check(args.handoff)
    except ManifestError as error:
        print(f'make_manifest: {error}', file=sys.stderr)
        return 2
    for problem in problems:
        print(f'make_manifest: {problem}', file=sys.stderr)
    if problems:
        return 1
    print('manifest is complete and current')
    return 0


if __name__ == '__main__':
    sys.exit(main())
