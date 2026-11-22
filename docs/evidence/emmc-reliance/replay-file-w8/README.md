# Power-cut replay of W8 and W8-control, a file replaced through File — 22 November 2026

Software evidence for the smallest next step of the atomic file update spike (`docs/plans/file-atomic-update-spike.md`,
proposed in pull request 540; decision 1 of that note): replay workload W8 and its control W8C (W8-control) on the eMMC simulator, with the
Crux File provider on Reliance Edge, and the same workloads on FatFs as observations. No interface changes.

**Every result here is an observation of the simulator's model on `native_sim`. None of it is evidence about
power loss on an eMMC device.** The simulator and the replay are models, written by the same author as the
tests. A rebuilt image shows what the model allows at a cut. It leaves out damage outside the write being made,
and it says nothing about a device's flash translation layer, its cache order or its supply ramp. Only a board
power-cut campaign can show those.

## What ran

- Revision: `30c1abd7` on branch `claude/file-w8-replay`, based on `main` at `2c017f68`. The working tree was
  clean. Zephyr `dccb09599635bdff17633fa7e9dab014b91dce90`, Reliance Edge
  `6706984258c5bb61c778fe8ca2edd04b559efb78`, FatFs `f4ead3bf4a6dab3a07d7b5f5315795c073db568d`,
  `native_sim/native/64`.
- Environment: the Dev Container image, run with Docker as `linux/amd64` under emulation on an arm64 Mac, limited
  to 4 CPUs and 6 GB, with the west workspace mounted read-only. No CI runner was used for these numbers, so all
  times are emulated times. The images link the GPLv2 Reliance Edge source. They are test images and are not
  kept here.
- Images, built under `build/zephyr/emmc-powercut/` from `tests/native/emmc_powercut`:
  - `red-fix-file`: `-DEXTRA_CONF_FILE="reliance.conf;file.conf" -DCONFIG_CRUX_MMC_CACHE_FLUSH=y`.
  - `red-nofix-file`: the same with `-DCONFIG_CRUX_MMC_CACHE_FLUSH=n -DCRUX_EMMC_FLUSH_CONTROL=ON`, the unmodified
    stack, which the adapter's guard allows only on `native_sim`.
  - `fat-fix-file`: `-DEXTRA_CONF_FILE="fatfs.conf;fatfs-file.conf" -DEXTRA_DTC_OVERLAY_FILE=fatfs-file.overlay
    -DCONFIG_CRUX_MMC_CACHE_FLUSH=y`, with FatFs as the only module. The overlay adds a small RAM disk only
    because the FatFs simulator File selection depends on a RAM or flash disk driver. Nothing mounts it.
- Commands, from the repository in the container. They are the W8 step of `scripts/test-storage-emmc.sh`, which
  also builds the three images and checks the counts below:

  ```sh
  python3 tests/native/emmc_powercut/run_replay.py \
      --exe-fix build/zephyr/emmc-powercut/red-fix-file/zephyr/zephyr.exe \
      --exe-nofix build/zephyr/emmc-powercut/red-nofix-file/zephyr/zephyr.exe \
      --fs reliance --workload W8 --seed 1 --samples 64 --max-seconds 300 --out build/zephyr/emmc-powercut/replay
  python3 tests/native/emmc_powercut/run_replay.py \
      --exe-fix build/zephyr/emmc-powercut/fat-fix-file/zephyr/zephyr.exe \
      --fs fatfs --workload W8 --seed 1 --samples 64 --max-seconds 300 --out build/zephyr/emmc-powercut/replay
  ```

  Reliance Edge: exit 0, 3546 cases, 454 verifier processes, 94.9 s. FatFs: exit 0, 897 cases, 375 verifier
  processes, 29.0 s. The same seed gave the same counts in an earlier run from the uncommitted tree.
- [`reliance-w8.json`](reliance-w8.json) and [`fatfs-w8.json`](fatfs-w8.json) are the runs' output, with every
  sampled position and its seed. No medium image is kept.
- The rest of `scripts/test-storage-emmc.sh`, and `scripts/test-storage-simulators.sh`, were not part of this
  local run. The W1 to W3 and W4 runs build other images, which this change does not alter, so their pinned
  counts (4947, 1182 and 2232) are not expected to move. The full scripts run in CI on the pull request.

## The workloads

- Root 0 of File is bound to `/MMC:/atomic`, once per process, after the mount, as a composition binds it. The
  baseline holds `atomic/w8` at generation 0, written at provision. A generation is a 16-byte header (magic,
  generation, length, CRC-32 of the body) and a body that is a function of the generation.
- Both workloads write generations 1 to 8. For each, `atomic/w8.tmp` is opened with `CRUX_FILE_CREATE_REPLACE`,
  written, synced with `crux_file_sync` and closed, all through File. Then:
  - **W8** puts it in place with `fs_rename` on the same mount, because no File operation replaces yet. This is
    the File-level data path of the proposed capability-gated replace.
  - **W8C** (W8-control) does what File allows today: `crux_file_remove_at` of `w8`, then `crux_file_rename`.
  - A mark follows each completed replace. With `run-early`, the mark comes before the temporary's sync.
- On FatFs the File provider stores `f` and the name's bytes in hexadecimal, so the VFS rename and the check use
  those stored names. On Reliance Edge names are stored as they are.
- `verify` mounts without formatting and reads `atomic/w8` through the VFS:
  - I3, reported as `replace`: `atomic/w8` is one complete generation, old or new (and `settings/w2`, which W8
    never touches, is intact).
  - I2, reported as `data`: that generation is not older than the number of acknowledged replaces.
  - `missing=1`: `atomic/w8` does not exist at all, as distinct from a damaged file.
  - I1, I4 (`files/keep`), I5 (a further write, sync and remount) and `read_error` as in the other workloads.
- On `red-fix-file`, a W8C case whose only violations are I2 and I3 with `missing=1` is counted as a window case.
  Any other W8C violation, and any W8 violation, is a failure.

## Result on Reliance Edge (`red-fix-file`)

| Workload | Profile | Model | Cases | Passed | Window (`missing=1`) |
| --- | --- | --- | --- | --- | --- |
| W8 | cached | lost | 161 | 161 | 0 |
| W8 | cached | prefix | 311 | 311 | 0 |
| W8 | cached | reordered | 298 | 298 | 0 |
| W8 | cached | torn | 260 | 260 | 0 |
| W8 | no cache | prefix | 258 | 258 | 0 |
| W8 | no cache | torn | 259 | 259 | 0 |
| W8C | cached | lost | 193 | 141 | 52 |
| W8C | cached | prefix | 391 | 291 | 100 |
| W8C | cached | reordered | 394 | 301 | 93 |
| W8C | cached | torn | 331 | 248 | 83 |
| W8C | no cache | prefix | 331 | 250 | 81 |
| W8C | no cache | torn | 332 | 245 | 87 |

- **W8 kept I1 to I5 with `read_error=0` in every case**, in all four cut models of the cached profile and both of
  the no-cache profile. The positions include each side of every flush (96 on the cached trace) and each side of
  every metaroot sector (216 on each trace), so every metaroot sector was torn. 236 and 251 of the torn cases
  tore a write. The cached W8 trace holds 8 marks, 48 flushes and 24 commits (a flush, one whole metaroot, a
  flush), three per replace (create, sync, rename), in 761 events and 704 written sectors.
- **W8C failed I3 with the target missing, as required.** Every one of its 496 violations was a window case:
  `atomic/w8` absent, mount, `files/keep`, recommit and reads all intact. No W8C case showed a damaged target.
  Under `lost` on the cached profile, the target was missing at 52 positions, covering all eight generations,
  each with the generations before it acknowledged. That is the cut after the removal's commit and before the
  rename's. The cached W8C trace holds 32 commits, four per replace (create, sync, unlink, rename).
- Controls, each required to fail, all failed as required:
  - window: W8C, cached, `lost`, `atomic/w8` missing with `mount=1` in every generation (generations 1 to 8).
  - flush: `red-nofix-file`, cached, `lost`, W8: `data=0` with `mount=1` after each of the 8 marks. The trace has
    no flush at all, so nothing after the baseline reaches the medium.
  - early acknowledgement: `red-fix-file`, `run-early`, cached, `lost`, W8: `data=0` with `mount=1` after each mark.
  - damaged image: the baseline with both metaroots overwritten does not mount.
- The 3546 cases are 3519 cut cases, 8 sanity cases (the baseline and the complete run of each workload and
  profile), 8 flush and 8 early-acknowledgement controls, and 3 damaged-image cases.

## Observation on FatFs (`fat-fix-file`)

| Workload | Profile | Model | Cases | Passed | Target missing | Target present but not complete |
| --- | --- | --- | --- | --- | --- | --- |
| W8 | cached | lost | 86 | 70 | 16 | 0 |
| W8 | cached | prefix | 88 | 68 | 20 | 0 |
| W8 | cached | reordered | 82 | 65 | 17 | 0 |
| W8 | cached | torn | 64 | 48 | 14 | 2 |
| W8 | no cache | prefix | 64 | 53 | 11 | 0 |
| W8 | no cache | torn | 64 | 44 | 17 | 3 |
| W8C | cached | lost | 80 | 64 | 16 | 0 |
| W8C | cached | prefix | 86 | 64 | 22 | 0 |
| W8C | cached | reordered | 82 | 63 | 19 | 0 |
| W8C | cached | torn | 64 | 48 | 15 | 1 |
| W8C | no cache | prefix | 64 | 53 | 11 | 0 |
| W8C | no cache | torn | 64 | 45 | 17 | 2 |

- Recorded, not asserted. **W8C lost the target in all eight generations (100 cases)**, as the spike expected and
  as the board's microSD replace cuts showed. W8 lost it too: Zephyr's FatFs rename removes an existing
  destination before it renames, so on FatFs the VFS rename has the same window as W8C. Under `torn` a few cuts
  left the target present but not one complete generation. Mount, `files/keep`, recommit and reads held in every
  case. The damaged image control (boot sector overwritten) did not mount, as required.
- The 897 cases are 888 cut cases, 8 sanity cases and 1 damaged-image case.

## What this shows and does not show

- In the model, a replace whose data goes through the File provider and whose last step is one Reliance Edge
  rename transaction leaves the target complete, old or new, at every tested cut. The same data path with File's
  remove and rename leaves no target at a cut between the two commits, in every generation, and the replay sees
  that. So the W8 result is not a blind check.
- It shows nothing about a device. It does not test the proposed File operation itself, which does not exist: W8
  calls the VFS rename directly. The flush correction (`CONFIG_CRUX_MMC_CACHE_FLUSH`) is set on `red-fix-file`,
  and only `red-nofix-file` uses `CRUX_EMMC_FLUSH_CONTROL`. The guard is unchanged.
- The optional W9 (in-place update under a concurrent commit) was not run.
