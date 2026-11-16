# Boot bench kit

Board-free tools for the first RT1060-EVK Rev B boot experiments. They implement the two wrapper scripts and the
hand-off steps of the [secure boot board test procedure](../../../docs/secure-boot-board-test-procedure.md) (sections 4
and 5) and serve the [bench session runbook](../../../docs/secure-boot-bench-session.md), which says in what order
to use them and which approvals each step needs.

**Status: never run against a board.** The host tests in `tests/build/test_boot_bench_*.py` use synthetic files, dummy
key bytes and a fake J-Link. They show the tools' own rules, not the behaviour of the real J-Link Commander, a probe or
a board. No tool here generates, reads, copies or stores a key, and none reads or writes a fuse.

| File | Purpose |
| --- | --- |
| `jlink-load.sh`, `jlink-verify.sh`, `_jlink-common.sh` | Commander wrappers: one hand-off file name in, fixed address by name, `exec DisableAutoUpdateFW` first, refuse any erase or fuse argument |
| `make_manifest.py` | Hand-off manifest (SHA-256 of every file) and a completeness check |
| `build_test_images.py` | The procedure's test images from given build outputs; key paths are arguments |
| `evidence_dir.py` | Bench directories, timestamped case directories, session record, `SHA256SUMS` |
| `boot_timing.py` | Time between two console lines from a device-control `events.jsonl` |

Run the tests from the repository root (no Docker, no west):

```sh
python3 -m unittest discover -s tests/build -p 'test_boot_bench_*.py' -v
```
