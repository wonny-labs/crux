#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Stage disposable Settings File fault-propagation copies; never touch the pinned checkout.

The Settings File selections of Configuration build these copies (zephyr/settings_file.cmake).
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

PIN = '41d10b59730406bbab4ca9f1fbbe9e96aafb4966'
PATCHES = Path(__file__).resolve().parents[1] / 'patches' / 'zephyr'
SOURCES = {
    'settings_file.c': ('subsys/settings/src/settings_file.c', PATCHES / 'settings-file-error.patch'),
    # Zephyr v4.5.0 returns the name write error itself, which was this copy's only correction, so
    # the copy is staged unchanged and the build still takes all three sources from one place.
    'settings_line.c': ('subsys/settings/src/settings_line.c', None),
    # The NVS candidate and the error experiment under tests/native apply this patch too: one
    # reviewed settings_store.c correction, not a second copy.
    'settings_store.c': ('subsys/settings/src/settings_store.c',
                         PATCHES / 'settings-store-error.patch'),
}


def prepare(zephyr, output):
    zephyr, output = zephyr.resolve(), output.resolve()
    if output == zephyr or zephyr in output.parents:
        raise RuntimeError('Output must be outside the pinned checkout')
    manifest = {'pin': PIN}
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as staging:
        staging = Path(staging)
        for name, (relative, patch) in SOURCES.items():
            content = (zephyr / relative).read_bytes()
            pinned = subprocess.check_output(['git', '-C', str(zephyr), 'show', PIN + ':' + relative])
            if content != pinned:
                raise RuntimeError(f'{relative} differs from the pinned Zephyr source')
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            if patch is not None:
                subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)],
                               cwd=staging, check=True)
            manifest[name] = {'original_sha256': hashlib.sha256(content).hexdigest(),
                              'patch_sha256': hashlib.sha256(patch.read_bytes()).hexdigest() if patch else None,
                              'generated_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
            target.replace(output / name)
        (staging / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (staging / 'manifest.json').replace(output / 'manifest.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zephyr', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.zephyr, args.output)
