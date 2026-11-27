#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate the pinned MMC stack with a cache flush on disk sync, without modifying Zephyr."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

BASE_SHA256 = "7bb737ece3b291b26527214cb375ce59fe3550ee1d88db146856014dc7c8e9b0"
PATCHED_SHA256 = "3c0de5a2a2979c30df9c68836b54e33e6d82fedf18f1f8be4eba08730c743f4f"
RELATIVE_SOURCE = Path("subsys/sd/mmc.c")
PATCH = Path(__file__).resolve().parents[1] / "patches/zephyr/mmc-cache-flush.patch"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(zephyr, output):
    zephyr = zephyr.resolve()
    output = output.resolve()
    if output.is_relative_to(zephyr):
        raise ValueError("Generated source must remain outside the Zephyr checkout")
    source = (zephyr / RELATIVE_SOURCE).resolve()
    original = source.read_bytes()
    if digest(original) != BASE_SHA256:
        raise ValueError("Unsupported upstream MMC source; no generated source written")
    patch = PATCH.read_bytes()
    # --no-index isolates application from any enclosing Git worktree.
    with tempfile.TemporaryDirectory(prefix="crux-mmc-") as directory:
        work = Path(directory)
        copied = work / RELATIVE_SOURCE
        copied.parent.mkdir(parents=True)
        copied.write_bytes(original)
        frozen_patch = work / "correction.patch"
        frozen_patch.write_bytes(patch)
        for check in (["--check"], []):
            subprocess.run(["git", "apply", "--no-index", *check, "--whitespace=error-all",
                            str(frozen_patch)], cwd=work, check=True)
        corrected = copied.read_bytes()
    if digest(corrected) != PATCHED_SHA256:
        raise ValueError("Unexpected patched MMC source; no generated source written")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(corrected)
    metadata = {
        "upstream_source": str(source),
        "upstream_sha256": digest(original),
        "patch_sha256": digest(patch),
        "generated_sha256": digest(corrected),
        "scope": "DISK_IOCTL_CTRL_SYNC flushes the eMMC cache when the stack turned it on",
    }
    output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zephyr", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare(args.zephyr.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
