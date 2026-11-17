#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Write and check per-delivery hash lists of a vendor kit tree.

A reference tool of the kit module template, not a Crux interface. It needs Python 3.9 or
later and nothing else.

    kit_hashes.py generate KIT_DIR                 print the hash list of a kit tree
    kit_hashes.py check KIT_DIR --lists DIR [--expect-line LINE]
                                                   name the committed list the tree matches

The hash list has one line per regular file, `<sha256 hex>  ./<path>`, sorted by the bytes of
the path, which is what `find . -type f -exec sha256sum {} + | LC_ALL=C sort -k 2` prints. A
`.git` entry at the top of the tree is skipped, so a west project checkout and an unpacked
delivery give the same list. A symbolic link or a file name with a newline is refused. The
digest of a list is the SHA-256 of its bytes.

Committed lists live at `<lists>/<line>/<delivery>.sha256`. `check` prints
`MATCH line=<line> delivery=<delivery> digest=<digest>` and exits 0, or prints
`UNKNOWN digest=<digest of the tree's own list>` and exits 1. Any other problem exits 2.
"""
import argparse
import hashlib
import os
from pathlib import Path
import sys


class KitError(Exception):
    pass


def _entries(root):
    if not root.is_dir():
        raise KitError(f"no kit directory at {root}")
    entries = []
    for directory, dirs, files in os.walk(root):
        here = Path(directory)
        if here == root:
            dirs[:] = [name for name in dirs if name != ".git"]
            files = [name for name in files if name != ".git"]
        for name in list(dirs):
            if (here / name).is_symlink():
                raise KitError(f"symbolic link in the kit: {(here / name).relative_to(root)}")
        for name in files:
            path = here / name
            rel = path.relative_to(root).as_posix()
            if "\n" in rel or "\r" in rel:
                raise KitError(f"file name with a newline in the kit: {rel!r}")
            if path.is_symlink():
                raise KitError(f"symbolic link in the kit: {rel}")
            if not path.is_file():
                raise KitError(f"not a regular file in the kit: {rel}")
            entries.append(("./" + rel, path))
    entries.sort(key=lambda item: os.fsencode(item[0]))
    return entries


def _file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_list(root):
    """Return the hash list of a kit tree as text."""
    return "".join(f"{_file_sha256(path)}  {name}\n" for name, path in _entries(Path(root)))


def digest_of(path):
    """Return the SHA-256 of a committed hash list file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def committed_lists(lists):
    lists = Path(lists)
    if not lists.is_dir():
        raise KitError(f"no hash list directory at {lists}")
    found = []
    for path in sorted(lists.rglob("*.sha256")):
        parts = path.relative_to(lists).parts
        if len(parts) != 2:
            raise KitError(f"hash list {path.relative_to(lists)} is not at <line>/<delivery>.sha256")
        found.append((parts[0], path.name[: -len(".sha256")], path))
    return found


def check(root, lists, expect_line=None):
    """Return (line, delivery, digest), or (None, None, digest of the tree's list)."""
    text = hash_list(root).encode()
    matches = [(line, delivery, path) for line, delivery, path in committed_lists(lists)
               if path.read_bytes() == text]
    if len(matches) > 1:
        names = ", ".join(f"{line}/{delivery}" for line, delivery, _ in matches)
        raise KitError(f"more than one committed list matches the kit: {names}")
    if not matches:
        return None, None, hashlib.sha256(text).hexdigest()
    line, delivery, path = matches[0]
    if expect_line is not None and line != expect_line:
        raise KitError(f"kit matches line {line} delivery {delivery}, expected line {expect_line}")
    return line, delivery, digest_of(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="print the hash list of a kit tree")
    gen.add_argument("kit", type=Path)
    chk = sub.add_parser("check", help="name the committed list that a kit tree matches")
    chk.add_argument("kit", type=Path)
    chk.add_argument("--lists", type=Path, required=True)
    chk.add_argument("--expect-line")
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            sys.stdout.write(hash_list(args.kit))
            return 0
        line, delivery, digest = check(args.kit, args.lists, args.expect_line)
    except (KitError, OSError) as error:
        print(f"kit_hashes.py: {error}", file=sys.stderr)
        return 2
    if line is None:
        print(f"UNKNOWN digest={digest}")
        return 1
    print(f"MATCH line={line} delivery={delivery} digest={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
