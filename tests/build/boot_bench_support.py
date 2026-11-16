"""Shared helpers for the boot-bench tool tests. Synthetic inputs only: no hardware, no real keys."""
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
BENCH_TOOLS = REPO / 'tests' / 'target' / 'boot-bench'
for _path in (BENCH_TOOLS, REPO / 'tools'):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

SHELL_SCRIPTS = ('_jlink-common.sh', 'jlink-load.sh', 'jlink-verify.sh')
FAKE_JLINK = """#!/bin/sh
# Records its arguments and the command file. Never touches a probe.
record="${FAKE_JLINK_RECORD:?}"
printf '%s\\n' "$@" > "$record.args"
while [ "$#" -gt 0 ]; do
    if [ "$1" = "-CommandFile" ]; then cp "$2" "$record.cmd"; fi
    shift
done
if [ "${FAKE_JLINK_VERIFY:-}" = "ok" ]; then echo "Verify successful"; fi
echo "fake jlink output"
exit "${FAKE_JLINK_EXIT:-0}"
"""


def make_bench(testcase, with_scripts=True):
    """A temporary bench directory with the wrapper scripts copied in, as evidence_dir init-bench does."""
    root = Path(tempfile.mkdtemp(prefix='boot-bench-test-'))
    testcase.addCleanup(shutil.rmtree, root, True)
    bench = root / 'bench'
    for name in ('handoff', 'cmd', 'evidence', 'backup'):
        (bench / name).mkdir(parents=True)
    if with_scripts:
        for name in SHELL_SCRIPTS:
            target = bench / name
            shutil.copy(BENCH_TOOLS / name, target)
            target.chmod(0o755)
    fake = root / 'fake-jlink'
    fake.write_text(FAKE_JLINK)
    fake.chmod(0o755)
    return bench, fake


def write_file(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def make_key(directory, name, mode=0o600):
    """A synthetic stand-in for a key file: dummy bytes, never a real key."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(b'DUMMY-KEY-SENTINEL-' + name.encode())
    os.chmod(path, mode)
    return path


def mode_of(path):
    return stat.S_IMODE(os.stat(path).st_mode)
