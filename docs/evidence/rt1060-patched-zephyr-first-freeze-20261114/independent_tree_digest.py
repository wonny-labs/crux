"""Independent derivation of crux-zephyr-tree-v1, written from the design text (docs/rt1060-bench-freeze-and-capture-design.md,
part 3) and NOT importing anything from the repository. Differences from tests/target/zephyr_tree.py: os.walk over bytes
paths (not os.scandir over str), one flat list sorted by raw bytes, reading with hashlib.file_digest-free fixed blocks, the
executable bit from os.lstat directly, no refusals except a minimal sanity set. Prints JSON: digest, counts, and the sha256 of
the files named on the command line.  usage: independent_tree_digest.py TREE [PATH ...]"""
import hashlib, json, os, stat, sys

root = os.fsencode(sys.argv[1])
want = [p.encode() for p in sys.argv[2:]]
EXCL_NAMES = {b'.DS_Store'}
EXCL_DIR = b'__pycache__'
rows = []
for here, dirs, files in os.walk(root, followlinks=False):
    dirs[:] = [d for d in dirs if d != EXCL_DIR]
    names = list(files) + [d for d in dirs if os.path.islink(os.path.join(here, d))]
    for name in names:
        if name in EXCL_NAMES or name.endswith((b'.pyc', b'.pyo')):
            continue
        full = os.path.join(here, name)
        rel = os.path.relpath(full, root)
        st = os.lstat(full)
        if stat.S_ISLNK(st.st_mode):
            kind, content = b'symlink', hashlib.sha256(os.readlink(full)).digest()
        elif stat.S_ISREG(st.st_mode):
            h = hashlib.sha256()
            with open(full, 'rb') as f:
                while True:
                    block = f.read(65536)
                    if not block:
                        break
                    h.update(block)
            kind, content = b'file', h.digest()
        else:
            raise SystemExit('unexpected entry type: %r' % rel)
        flag = b'exec' if (st.st_mode & 0o100 and kind == b'file') else b'plain'
        rel.decode('utf-8')  # must be valid UTF-8
        rows.append((rel, kind, flag, content))
rows.sort(key=lambda r: r[0])
assert not any(r[0].lower().split(b'/')[0] == b'.git' for r in rows)
lowered = [r[0].lower() for r in rows]
assert len(set(lowered)) == len(lowered), 'case-fold collision'
total = hashlib.sha256()
for rel, kind, flag, content in rows:
    total.update(rel + b'\0' + kind + b'\0' + flag + b'\0' + content)
out = dict(sha256=total.hexdigest(), file_count=sum(1 for r in rows if r[1] == b'file'),
           symlink_count=sum(1 for r in rows if r[1] == b'symlink'), files={})
index = {r[0]: r for r in rows}
for w in want:
    out['files'][w.decode()] = index[w][3].hex() if w in index else None
print(json.dumps(out, indent=1, sort_keys=True))
