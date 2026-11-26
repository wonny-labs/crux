#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate the pinned TCP stack with an initial sequence number that fails closed, without modifying Zephyr.

patches/zephyr/README.md describes the correction. It follows scripts/prepare-mmc-cache-flush.py: an exact
source hash, the patch applied to a copy in a temporary directory, and an exact result hash. A tcp.c that
already fails closed is copied unchanged: the result of this patch, or the wolfSSL bench copy of Zephyr
v4.4.2 that scripts/prepare-isn-fail-closed.py made. Any other tcp.c is refused.

  scripts/prepare-tcp-isn.py ZEPHYR_BASE OUTPUT
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

# tcp.c at the pinned Zephyr (v4.5.0), and after patches/zephyr/tcp-isn-fail-closed.patch.
BASE_SHA256 = "7bd732e592253e5628ee8971d00c7e79adac712b287a3fbb4a8d1440329cbbfa"
PATCH_SHA256 = "a7e0ce1287183daf8f5c48d7dbd6c03c406c1d69f80f687d45c8cd5ade45c89a"
PATCHED_SHA256 = "9edbbac65be7a36f208c51c9cce8c92756794d9efd6331e21001fee9ab642d5e"
# tcp.c files that already fail closed, copied unchanged.
ALREADY_FAIL_CLOSED = {
    PATCHED_SHA256: "Zephyr v4.5.0 with patches/zephyr/tcp-isn-fail-closed.patch",
    "94642fe2257f80dd91b9e84d8c29459ca84144cb56af0cdfdd58039473e0e0cf":
        "Zephyr v4.4.2 with patches/zephyr/zephyr-isn-fail-closed.patch (the wolfSSL bench copy)",
}
RELATIVE_SOURCE = Path("subsys/net/ip/tcp.c")
PATCH = Path(__file__).resolve().parents[1] / "patches/zephyr/tcp-isn-fail-closed.patch"
README = "patches/zephyr/README.md#tcp-initial-sequence-number-that-fails-closed"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def apply(original, patch):
    # --no-index isolates application from any enclosing Git worktree.
    with tempfile.TemporaryDirectory(prefix="crux-tcp-isn-") as directory:
        work = Path(directory)
        copied = work / RELATIVE_SOURCE
        copied.parent.mkdir(parents=True)
        copied.write_bytes(original)
        frozen_patch = work / "correction.patch"
        frozen_patch.write_bytes(patch)
        for check in (["--check"], []):
            subprocess.run(["git", "apply", "--no-index", *check, "--whitespace=error-all",
                            str(frozen_patch)], cwd=work, check=True)
        return copied.read_bytes()


def prepare(zephyr, output, patch_path=PATCH):
    zephyr = zephyr.resolve()
    output = output.resolve()
    if output.is_relative_to(zephyr):
        raise ValueError("the generated tcp.c must stay outside the Zephyr checkout")
    source = (zephyr / RELATIVE_SOURCE).resolve()
    original = source.read_bytes()
    patch = Path(patch_path).read_bytes()
    if digest(patch) != PATCH_SHA256:
        raise ValueError("the patch is not the one whose hash this script knows; nothing written")
    if digest(original) in ALREADY_FAIL_CLOSED:
        corrected = original
        applied = False
        scope = ALREADY_FAIL_CLOSED[digest(original)]
    elif digest(original) == BASE_SHA256:
        corrected = apply(original, patch)
        if digest(corrected) != PATCHED_SHA256:
            raise ValueError("the patched tcp.c is not the expected one; nothing written")
        applied = True
        scope = "Zephyr v4.5.0, patched here"
    else:
        raise ValueError(f"{source} is not the tcp.c of the pinned Zephyr, so the TCP initial sequence number "
                         "would not fail closed; nothing written")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(corrected)
    metadata = {
        "upstream_source": str(source),
        "upstream_sha256": digest(original),
        "patch_sha256": digest(patch),
        "patch_applied": applied,
        "generated_sha256": digest(corrected),
        "source": scope,
        "scope": "with RFC 6528, a failed key read or hash refuses the TCP connection",
    }
    output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("zephyr", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        prepare(args.zephyr, args.output)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"FAIL: {error}. Use the Zephyr that west.yml pins: see {README}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
