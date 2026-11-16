#!/usr/bin/env python3
"""Evidence-directory helper of the boot bench (procedure sections 3 and 8).

  init-bench   create <bench>/{handoff,cmd,evidence,backup} and install the reviewed J-Link wrapper scripts
  new-case     create <bench>/evidence/<UTC>-<label>, a directory that must not exist yet
  session      write <bench>/evidence/session-<UTC>.json: date, operator, host, revisions, approval references
  seal         write SHA256SUMS for every file of one case directory
  verify-seal  check a case directory against its SHA256SUMS

It never reads a key, never talks to a probe and never touches a board. Results stay under <bench>; do not
commit them under docs/evidence/ (procedure section 8). Not run on a board.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
SCRIPTS = ('_jlink-common.sh', 'jlink-load.sh', 'jlink-verify.sh')
BENCH_DIRECTORIES = ('handoff', 'cmd', 'evidence', 'backup')
SUMS = 'SHA256SUMS'
_LABEL = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*')
_UTC = re.compile(r'\d{8}T\d{6}Z')
_REVISION = re.compile(r'[0-9a-f]{40}')


class EvidenceError(Exception):
    pass


def _now():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def _utc(value):
    value = _now() if value is None else value
    if not _UTC.fullmatch(value):
        raise EvidenceError(f'time must look like 20261116T093000Z: {value!r}')
    return value


def init_bench(bench, force=False):
    """Creates the bench directories and copies the wrapper scripts. Replaces an edited script only with force."""
    bench = Path(bench)
    for name in BENCH_DIRECTORIES:
        (bench / name).mkdir(parents=True, exist_ok=True)
    for name in SCRIPTS:
        source = HERE / name
        target = bench / name
        if target.exists() and not force and target.read_bytes() != source.read_bytes():
            raise EvidenceError(f'{target} differs from the reviewed script; compare it, then use --force')
        shutil.copyfile(source, target)
        target.chmod(0o755)
    return bench


def new_case(bench, label, utc=None):
    bench = Path(bench)
    if not _LABEL.fullmatch(label or ''):
        raise EvidenceError(f'bad case label: {label!r} (letters, digits, dot, dash, underscore)')
    stamp = _utc(utc)
    evidence = bench / 'evidence'
    if not evidence.is_dir():
        raise EvidenceError(f'{evidence} does not exist; run init-bench first')
    case = evidence / f'{stamp}-{label}'
    try:
        case.mkdir()
    except FileExistsError as error:
        raise EvidenceError(f'case directory already exists: {case}') from error
    return case


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _files(case):
    case = Path(case)
    if not case.is_dir():
        raise EvidenceError(f'not a directory: {case}')
    found = {}
    for root, directories, names in os.walk(case):
        for entry in directories + names:
            if (Path(root) / entry).is_symlink():
                raise EvidenceError(f'{Path(root) / entry}: a symbolic link cannot be sealed')
        for name in names:
            path = Path(root) / name
            relative = path.relative_to(case).as_posix()
            if relative != SUMS:
                found[relative] = path
    return found


def seal(case):
    case = Path(case)
    sums = case / SUMS
    if sums.exists():
        raise EvidenceError(f'{sums} exists; a sealed case is not sealed again')
    files = _files(case)
    if not files:
        raise EvidenceError(f'{case} holds no files to seal')
    sums.write_text(''.join(f'{_sha256(files[name])}  {name}\n' for name in sorted(files)), encoding='utf-8')
    return sums


def verify_seal(case):
    """Problems found: a file changed, missing or not sealed. Empty when the case matches its SHA256SUMS."""
    case = Path(case)
    try:
        lines = (case / SUMS).read_text(encoding='utf-8').splitlines()
        sealed = dict(reversed(line.split('  ', 1)) for line in lines)
    except (OSError, ValueError) as error:
        return [f'{SUMS}: cannot read ({error})']
    files = _files(case)
    problems = []
    for name, digest in sorted(sealed.items()):
        if name not in files:
            problems.append(f'{name}: sealed but missing')
        elif _sha256(files[name]) != digest:
            problems.append(f'{name}: hash differs')
    for name in sorted(set(files) - set(sealed)):
        problems.append(f'{name}: not sealed')
    return problems


def write_session(bench, operator, crux_revision, zephyr_revision, mcuboot_revision, approvals, utc=None, notes=''):
    bench = Path(bench)
    if not operator:
        raise EvidenceError('operator must not be empty')
    for name, value in (('crux revision', crux_revision), ('zephyr revision', zephyr_revision),
                        ('mcuboot revision', mcuboot_revision)):
        if not _REVISION.fullmatch(value or ''):
            raise EvidenceError(f'{name} must be 40 lowercase hexadecimal digits')
    approvals = [a for a in approvals if a]
    if not approvals:
        raise EvidenceError('at least one approval reference is required: write it down before the step runs')
    evidence = bench / 'evidence'
    if not evidence.is_dir():
        raise EvidenceError(f'{evidence} does not exist; run init-bench first')
    stamp = _utc(utc)
    target = evidence / f'session-{stamp}.json'
    if target.exists():
        raise EvidenceError(f'{target} exists')
    uname = platform.uname()
    data = {'utc': stamp, 'operator': operator, 'crux_revision': crux_revision,
            'zephyr_revision': zephyr_revision, 'mcuboot_revision': mcuboot_revision, 'approvals': approvals,
            'host': {'system': uname.system, 'node': uname.node, 'release': uname.release, 'machine': uname.machine},
            'notes': notes}
    target.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init-bench')
    init.add_argument('--bench', required=True, type=Path)
    init.add_argument('--force', action='store_true', help='replace a wrapper script that differs from the reviewed one')
    case = commands.add_parser('new-case')
    case.add_argument('--bench', required=True, type=Path)
    case.add_argument('--label', required=True)
    case.add_argument('--utc', help='override the clock, for tests: 20261116T093000Z')
    session = commands.add_parser('session')
    session.add_argument('--bench', required=True, type=Path)
    session.add_argument('--operator', required=True)
    session.add_argument('--crux-revision', required=True)
    session.add_argument('--zephyr-revision', required=True)
    session.add_argument('--mcuboot-revision', required=True)
    session.add_argument('--approval', action='append', default=[], help='an approval reference of the task record; repeat')
    session.add_argument('--utc')
    session.add_argument('--notes', default='')
    for name in ('seal', 'verify-seal'):
        sub = commands.add_parser(name)
        sub.add_argument('--case', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'init-bench':
            print(init_bench(args.bench, args.force))
        elif args.command == 'new-case':
            print(new_case(args.bench, args.label, args.utc))
        elif args.command == 'session':
            print(write_session(args.bench, args.operator, args.crux_revision, args.zephyr_revision,
                                args.mcuboot_revision, args.approval, args.utc, args.notes))
        elif args.command == 'seal':
            print(seal(args.case))
        else:
            problems = verify_seal(args.case)
            for problem in problems:
                print(f'evidence_dir: {problem}', file=sys.stderr)
            if problems:
                return 1
            print('case matches its SHA256SUMS')
    except EvidenceError as error:
        print(f'evidence_dir: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
