#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate the pinned HTTP server core with a header-phase deadline, without modifying Zephyr.

patches/zephyr/README.md describes the correction. It follows scripts/prepare-mmc-cache-flush.py:
an exact source hash, the patch applied to a copy in a temporary directory, and an exact result
hash. It sits beside the web adapter, the one component that builds it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

BASE_SHA256 = "f0d0ce9123bb2b07fd512c04a8f94d8b0142e80c54894adddd83b61e0e1e5150"
PATCHED_SHA256 = "1361df15056810006c98e7f4a66c5de84dcf15ebf6f2cd0413acccffa77774ef"
RELATIVE_SOURCE = Path("subsys/net/lib/http/http_server_core.c")
PATCH = Path(__file__).resolve().parents[4] / "patches/zephyr/http-header-deadline.patch"


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
        raise ValueError("Unsupported upstream HTTP server source; no generated source written")
    patch = PATCH.read_bytes()
    # --no-index isolates application from any enclosing Git worktree.
    with tempfile.TemporaryDirectory(prefix="crux-http-") as directory:
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
        raise ValueError("Unexpected patched HTTP server source; no generated source written")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(corrected)
    metadata = {
        "upstream_source": str(source),
        "upstream_sha256": digest(original),
        "patch_sha256": digest(patch),
        "generated_sha256": digest(corrected),
        "scope": "an HTTP/1 request head must be complete within CONFIG_CRUX_WEB_HEADER_DEADLINE_MS",
    }
    output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("zephyr", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare(args.zephyr.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
