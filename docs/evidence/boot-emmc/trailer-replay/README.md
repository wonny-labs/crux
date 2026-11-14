# Replay of MCUboot trailer sequences on a modelled eMMC write path — 14 November 2026

Software evidence for issue [#310](https://github.com/wonny-labs/crux-pilot/issues/310), the follow-up of section 5 of the
[eMMC boot investigation](../../../boot-emmc-investigation.md). It tests the ordering and alignment assumptions that
MCUboot's image activation makes about its storage, in RAM load with revert, against models of two cache behaviours.

**Every result here is an observation of models: a model of MCUboot's trailer rules, a model of a flash-API driver on
the 512-byte disk layer, and the power-cut replay model of the eMMC simulator. None of it is evidence about MCUboot
running on a device or about any eMMC. It makes no eMMC support claim.** The models were written by the same author as
the tests. A medium rebuilt at a cut shows what a model allows, and a real part's translation layer may do something
else. The two device behaviours are described only in generic words and are not named after any part.

## What ran

- Base: `origin/main` at `21e9d438`. The tested tree is the head of the pull request that adds this record. The exact
  head is in that pull request and in its review record.
- Pinned upstream, read outside this repository and never copied into it: MCUboot
  `6d3b3d2c38ab20c242e5b9abb04d050086383eb2` (the revision in Zephyr v4.4.2's `west.yml`) and Zephyr v4.4.2
  (`dccb09599635bdff17633fa7e9dab014b91dce90`). The functions that each rule follows are named in the module
  docstring of [`trailer_model.py`](../../../../tests/native/emmc_trailer/trailer_model.py).
- Environment: a macOS arm64 host with the system Python 3.9. No Docker, no `native_sim` build, no board, no J-Link.
  The C simulator was **not** run in this record. It supplies the replay model (`tests/native/emmc_powercut/replay_model.py`,
  imported unchanged) and the trace format, and the write path of a driver is modelled in Python. A run of the same
  sequences through a driver and the C simulator on `native_sim` belongs to the backend prototype, not to this record.
- Command, from the repository root. Exit 0, 568,710 cases in 68.7 s, 108 rows (54 scenarios on each of the 2 devices):

  ```sh
  python3 tests/native/emmc_trailer/run_trailer_replay.py --seeds 8 \
      --out docs/evidence/boot-emmc/trailer-replay/trailer-replay.json
  ```

- [`trailer-replay.json`](trailer-replay.json) is that run's output: per row the trace size and SHA-256 and the failure
  count of each property under each model, with the first example of each failure, and the controls.
- Tests, which also run in the Host workflow because it discovers `tests/build`:

  ```sh
  python3 -m unittest discover -s tests/build -p test_emmc_trailer_replay.py -v
  ```

  45 tests, OK, 84.8 s. They cover the trailer model, the write path, the device and torn models, and the matrix runner,
  which exits non-zero if any outcome stated in this record does not hold, so the record cannot drift from the run.
  The rest of `tests/build` was also run on the macOS host. It reported 59 failures and 6 errors. One failure was this
  change's own runner test, run while the runner was being edited, and it passes now (the 45 tests above). The other
  58 failures and 6 errors come from that host (AppleClang configuration, a `strip` flag, a linked-worktree
  provenance check, a missing tool with exit 127) in files this change does not touch. The Linux CI run is the gate
  for them.

## What is modelled

**MCUboot rules** (`trailer_model.py`), RAM load with revert as Zephyr v4.4.2 selects it
(`CONFIG_MCUBOOT_BOOTLOADER_MODE_RAM_LOAD_WITH_REVERT` does not select the direct-XIP library, so the application's
requests are the swap-style `boot_set_next`):

- Trailer offsets from the slot end: magic, then `image_ok`, `copy_done` and `swap_info` each one `BOOT_MAX_ALIGN` below
  the last. `boot_write_magic` writes `ALIGN_UP(16, BOOT_MAX_ALIGN)` bytes. `boot_write_trailer` writes one write block
  and refuses a size above `BOOT_MAX_ALIGN`.
- Decoding: a field equal to the erased value throughout is unset, a flag of 1 is set, anything else is bad. A slot is
  scrambled if its magic is not good or `copy_done` is set without `image_ok` (`boot_select_or_erase`). Otherwise
  `copy_done` is written first (a failure is only logged), then the image is validated and an invalid one is scrambled.
  The highest version with a valid header is tried first.
- Application: a test request writes magic then `swap_info` (permanent: magic, `image_ok`, `swap_info`). A confirm
  writes `image_ok` only if the magic is good and `image_ok` is unset, and writes nothing, returning success, otherwise.
- The image is a stand-in: MCUboot's header fields, a body and a SHA-256 digest in place of the hash and signature.

**Update paths.** Erase the inactive slot, write image 2, request, the bootloader's trial boot, then either the
application confirms (`confirm`) or the trial fails and the next boot reverts (`revert`). With `--pad` signing, writing
the image is the request (owner decision 13 of the [update investigation](../../../boot-update-investigation.md)): the
padded image carries the trailer magic, is written in ascending order, and no request call follows. Both request paths
are replayed. A mark follows each step when its last call returns, and a step counts as acknowledged only at a cut after
its mark.

**Write path of a flash-API driver** (`write_path.py`): `flash_write` and `flash_erase` become 512-byte sector writes in
the simulator's trace format. Erase is emulated by writing `0xFF` over whole 4 KiB pages. The driver reports an erase
value of `0xFF`, while the medium reads `0x00` when natively erased. Four flush policies: after every call (`flush`),
after every erase call and every call that touches a slot trailer (`steps`), after calls that touch a trailer only
(`trailer`), and never (`none`). Three trailer layouts: `sector` (write block and `BOOT_MAX_ALIGN` of 512, so each
field is a sector), `rmw` (8 and 8, so each flag write is a read-modify-write of the whole sector and all four fields
share the last sector) and `native` (4096 and 4096, so each field has its own native unit).

**Device behaviours.**

- `fifo-barrier`: the cache drains in the order written and barriers are supported. What survives a cut since the last
  flush is a prefix of those writes, tried at every drain position (or at each side of every trailer write and a seeded
  draw where a window holds more than 64 events). No policy here issues a barrier, so barrier use is not modelled.
- `unordered`: no flush-order guarantee and no barrier. Any subset of the writes since the last flush survives, drawn
  with 8 seeds per cut.
- Both devices also get `lost` (nothing since the last flush survives) and three tears of the write in progress:
  `torn-sector` (bytes of its sector mix old and new, the replay model's torn write), `torn-sector-wide` (its whole
  512-byte sector is indeterminate) and `torn-native` (its whole 4 KiB native unit is indeterminate, for a 4 KiB native
  sector behind 512-byte emulation). The `reliable` rows model reliable write as an assumption: no torn case, because
  each 512-byte sector is old or new and the earlier data of the unit is kept. That assumption is not tested here.

**Properties**, evaluated at every cut position and then after one more reset with nothing confirmed in between:

| # | Property |
| --- | --- |
| P1 | A valid image boots after the cut and after the next reset (safety) |
| P2 | Slot A, the confirmed old image, is byte-identical to the baseline (safety) |
| P3 | An acknowledged confirm survives: image 2 boots, twice |
| P4 | After an acknowledged trial, unconfirmed image 2 is not started again |
| P5 | An acknowledged test request survives until the trial starts: image 2 is tried (liveness) |
| P6 | An acknowledged revert survives: image 1 boots |
| P7 | A torn write changes no trailer field other than the ones it was writing |

At a cut inside the trial step, a torn write may cancel the update, because the trial was not acknowledged. The JSON counts
those cases per model (`trial_cancelled_in_flight`). They are not failures of P1 to P6 and they are a lost update, not a
broken device.

## Result

Failure counts per property over all cases of the group (both paths, padded and not, all models). Zero means the
property held in every case. Rows of the same policy and device that differ only by layout differ only in P7 and in the number of cases.

| Flush policy | Reliable write | Layout | Device | Cases | P1 | P2 | P3 | P4 | P5 | P6 | P7 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flush | no | native | fifo-barrier | 21398 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| flush | no | native | unordered | 23496 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| flush | no | rmw | fifo-barrier | 19020 | 0 | 0 | 0 | 0 | 0 | 0 | 160 |
| flush | no | rmw | unordered | 21054 | 0 | 0 | 0 | 0 | 0 | 0 | 160 |
| flush | no | sector | fifo-barrier | 19020 | 0 | 0 | 0 | 0 | 0 | 0 | 80 |
| flush | no | sector | unordered | 21054 | 0 | 0 | 0 | 0 | 0 | 0 | 80 |
| flush | yes | native | fifo-barrier | 1884 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| flush | yes | native | unordered | 2799 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| flush | yes | rmw | fifo-barrier | 1464 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| flush | yes | rmw | unordered | 2322 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| flush | yes | sector | fifo-barrier | 1464 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| flush | yes | sector | unordered | 2322 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| steps | no | native | fifo-barrier | 22644 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| steps | no | native | unordered | 23166 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| steps | no | rmw | fifo-barrier | 22232 | 0 | 0 | 0 | 0 | 0 | 0 | 160 |
| steps | no | rmw | unordered | 20526 | 0 | 0 | 0 | 0 | 0 | 0 | 160 |
| steps | no | sector | fifo-barrier | 22232 | 0 | 0 | 0 | 0 | 0 | 0 | 80 |
| steps | no | sector | unordered | 20526 | 0 | 0 | 0 | 0 | 0 | 0 | 80 |
| trailer | no | native | fifo-barrier | 25924 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| trailer | no | native | unordered | 22374 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| trailer | no | rmw | fifo-barrier | 31905 | 0 | 0 | 0 | 0 | 0 | 0 | 160 |
| trailer | no | rmw | unordered | 19140 | 0 | 0 | 0 | 0 | 0 | 0 | 160 |
| trailer | no | sector | fifo-barrier | 31905 | 0 | 0 | 0 | 0 | 0 | 0 | 80 |
| trailer | no | sector | unordered | 19140 | 0 | 0 | 0 | **4** | 0 | 0 | 80 |
| none | no | native | fifo-barrier | 33127 | 0 | 0 | **52** | **193** | **98** | **2** | 0 |
| none | no | native | unordered | 20988 | 0 | 0 | **66** | 0 | **36** | 0 | 0 |
| none | no | rmw | fifo-barrier | 29246 | 0 | 0 | **53** | **341** | **88** | **5** | 160 |
| none | no | rmw | unordered | 18546 | 0 | 0 | **66** | 0 | **36** | 0 | 187 |
| none | no | sector | fifo-barrier | 29246 | 0 | 0 | **53** | **341** | **88** | **5** | 80 |
| none | no | sector | unordered | 18546 | 0 | 0 | **66** | 0 | **36** | 0 | 80 |

The two safety properties held in all 568,710 cases, including every tear and every policy, with the slots aligned to
the native unit. Only the acknowledgement properties and P7 move.

### Controls and mutation

Each control is required by the matrix runner to come out as stated, and did.

| Control | Required | Result |
| --- | --- | --- |
| Each mark before its step (early acknowledgement), `flush`, `fifo-barrier` | P3 fails | 24 failures |
| Slot A starting at 2048, inside a native unit, `torn-native` | P1 and P2 fail | 64 and 64 failures (first at cut 1, both slots unbootable) |
| `revert` path with no flush, `unordered`, 4096 draws right after the trial mark | P4 fails | 17 of 4096 draws start the unconfirmed image again |
| Request on a natively erased slot (reads `0x00`) with no driver erase | The request fails and image 1 boots | Magic reads bad, `boot_set_next` returns `BOOT_EBADIMAGE` (3), image 1 boots |
| 8 MiB slots against erase groups of 512 KiB and 4 MiB and write-protect groups of 4 and 8 MiB | 0 problems in each of the four geometries | 0, 0, 0, 0 |

Mutants, each applied to a scratch copy of the model, the write path or the runner. Each made the runner exit non-zero
or the tests fail:

| Mutant | Caught by |
| --- | --- |
| `copy_done` is never written | Scenario: the revert boot is not the expected one |
| A failed trial is not scrambled | Scenario: the same |
| The `flush` policy emits no flush | The runner (P3 and others fail under `flush`) and the tests |
| The scramble skips the header page | The runner (P4 fails under `flush`) and the tests |
| The FIFO device drains everything | The runner (P3 does not fail without a flush under `fifo`) and the tests |
| Erase writes `0x00` | Scenario: the request finds a trailer that is not unset |
| No torn models | The runner and the tests |
| A confirm writes `image_ok` when it is bad | The trailer model's unit test only. The matrix cannot reach it, because its confirms always find `image_ok` unset. |

## Which assumptions hold, in the models

| # | Assumption | Result in the models |
| --- | --- | --- |
| A1 | Image activation works if the driver reports an erase value that differs from what the medium reads when erased | It works only if the slot is erased through the driver first. A request on a natively erased slot fails with `BOOT_EBADIMAGE`. A confirm on such a slot finds `image_ok` bad, writes nothing and still returns success, so the confirm is silently lost (unit test). With the erase step, every case holds. |
| A2 | Writes reach the medium in the order issued | Does not hold on the `unordered` device and holds on `fifo-barrier` between flushes. Safety (P1, P2) holds either way, because MCUboot validates the image and scrambles an invalid slot. |
| A3 | A returned write is durable | Does not hold without a flush. With no flush, an acknowledged confirm or test request is lost (P3 and P5 fail on both devices) and a trial or revert can be repeated or lost (P4, P6). |
| A4 | A flush after every call is enough | Yes: P1 to P6 hold on both devices, in both request paths, all three layouts. |
| A5 | A flush after calls that touch a trailer is enough | On `fifo-barrier`: yes. On `unordered`: no. The scramble erases the header page first, and when it is not flushed before the trailer page is erased, the trailer erase can persist while the header erase is dropped. The slot then keeps a valid header and a good magic with `copy_done` erased, and the unconfirmed image is tried a second time (P4: 4 cases over both request paths with 8 draws per cut, found again by the 4096-draw control). Flushing after every erase call as well (`steps`) holds on both devices. |
| A6 | A write block of 512 works for MCUboot's trailer | Only with `BOOT_MAX_ALIGN` of at least 512. With a smaller maximum, one flag write exceeds it and `boot_write_trailer` refuses (source). The static assert for swap modes (`8 <= MCUBOOT_BOOT_MAX_ALIGN <= 32`, `bootutil_public.h`) then excludes every swap mode, including swap using offset. Swap sequences were not replayed. They would need the `rmw` layout, which is the least isolated. |
| A7 | One write damages only the field being written | Not without reliable write. Under `torn-native` a write can change other trailer fields in both the `sector` and `rmw` layouts (P7), and under `torn-sector-wide` in `rmw`. In every such case P1 to P6 still hold: the damage cancels an unacknowledged step (a lost update), and it never makes an image unbootable or touches slot A. With `BOOT_MAX_ALIGN` of 4096 (`native`, no swap mode) each field has a native unit of its own and P7 holds under every model. With reliable write modelled as no tear, P7 holds in every layout. |
| A8 | The two slots do not share a native unit | If a slot starts inside one, a torn write can destroy the neighbour. Both slots become unbootable (P1, P2). Slots starting and ending on 8 MiB multiples satisfy native units of 4 KiB, erase groups of 512 KiB and 4 MiB, write-protect groups of 4 and 8 MiB, and a file-system volume elsewhere. 4 MiB slots fail the 8 MiB write-protect groups, and 512 KiB slots fail every group larger than themselves. This row is arithmetic on the layout, not a device model. |
| A9 | A padded image (`--pad`) is a safe request | Yes in the models. The trailer magic is the last bytes of an ascending write, so a cut before it leaves a slot without a good magic, which the next boot scrambles. A cut after it leaves a complete image. Under no flush the magic can persist without earlier chunks, and validation then rejects the image (P1 holds). The padded path shows the same P3 to P6 pattern as the request path. |

## What a flash-API driver must do, as these results show

Each item is a result for the models and is not a statement about any device.

1. **Emulate erase by writing `0xFF`** over whole pages and report an erase value of `0xFF`, or MCUboot cannot read its own
   trailer on a slot that reads `0x00` (A1). Erase the inactive slot through the driver before writing an image to it.
   Reporting `0x00` as the erase value is another way to match the medium. It was not replayed, and it needs images
   signed with a matching erase value (`imgtool --erased-val`), so it is not recommended without a test.
2. **Reject** unaligned offsets, lengths that are not whole write blocks, and ranges outside the device, before any
   command is issued. Tested with no event recorded.
3. **Flush before returning** from every call that touches a slot trailer, and from every erase call (the `steps` policy
   is the least that held on both devices). Flushing after every call is simplest and also held. A driver that returns
   before the flush completes acknowledges too early (control). On a device with in-order drain, flushing only after
   trailer calls held, but it gives up the margin the unordered case shows.
4. **Report a write block and `BOOT_MAX_ALIGN` consistently**: a write block of 512 needs `BOOT_MAX_ALIGN` of at least 512,
   which means a 2 KiB trailer on each slot and no swap mode. A write block of 8 with sector read-modify-write works
   for safety and exposes every field to one sector tear. A `BOOT_MAX_ALIGN` of 4096 isolates each field in its own
   native unit and costs a 16 KiB trailer and a 4 KiB buffer for the magic write (source). Reliable write would remove
   the tear but is not in the pinned Zephyr stack (#298, P16), and its model here is an assumption.
5. **Place slots on native-unit boundaries**, and on 8 MiB multiples if one plan is to satisfy every erase and
   write-protect group seen, outside any file-system volume (A8).
6. **Read timeouts from the device** rather than constants, and size the flush wait for the slowest case. This record has
   no timing, so it shows nothing about how long a flush takes.

## What this does not show

- It does not run MCUboot. The rules are re-implemented from reading the pinned source, and a divergence between the
  model and the source would not be seen here. Each rule names its upstream function so that a reviewer can compare.
- It does not use the C simulator, `native_sim` or the Zephyr MMC stack. The write path is Python, and what a driver does
  in C (the flush, the error paths, the alignment checks) is the subject of the backend prototype.
- Swap modes were not replayed. Only RAM load with revert was, in the test path and the `--pad` path.
- Random models are drawn 8 times per cut. A failure that needs one draw in thousands is found only where a control
  searches for it. The absence of a failure in the table is not a proof for every subset of a cache.
- The tears are three simple models. A real part can damage sectors that no write touched, lose a whole erase group or
  reorder across a flush, and none of that is modelled. The erase groups and write-protect groups appear only as
  placement arithmetic.
- Reliable write, a barrier command, an RPMB, boot partitions and the power-up behaviour of any part are not modelled.
- No timing, no wear and no concurrency. The application's own writes after the confirm are not replayed.

## Follow-ups for the owner

- `scripts/test-storage-emmc.sh` and `.github/workflows/` are protected paths and were not changed. The tests run in
  CI anyway because the Host workflow discovers `tests/build`. Listing the matrix runner in `scripts/test-storage-emmc.sh`,
  next to the FatFs and Reliance Edge replays, would be a one-line change if the owner wants it there.
- Whether to replay a swap mode with the `rmw` layout, if a product ever wants one. This record gives no reason to.
