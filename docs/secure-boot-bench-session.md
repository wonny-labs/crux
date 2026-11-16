# Secure boot bench session kit (RT1060-EVK Rev B)

> **Not yet run.** Nothing on this page has been executed on a board. Every duration is an **Estimate**, and every board result named below is a prediction from the sources next to it.
> **Status:** Proposal for one consolidated bench session of milestone M8 ([issue #296](https://github.com/wonny-labs/crux-pilot/issues/296)). It builds on the merged [secure boot board test procedure](secure-boot-board-test-procedure.md) (T0 to T7) and does not repeat it: where this page says "as procedure section N", that section is the instruction. It decides nothing, grants no approval and adopts no interface.
> **Verified:** Only that the kit's tools exist and pass their host tests against a fake J-Link and synthetic files (see [section 4](#4-the-kit)). The runbook's own content is documentation.
> **Not verified:** Every board result, every J-Link Commander behaviour, that the device-control tool passes the probe serial through its environment to a wrapper, and everything marked so below.
> **Read this first / then:** the [boot overview](boot-overview.md), the [boot composition](boot-composition.md) page and the [procedure](secure-boot-board-test-procedure.md); then this page. The tools are described in the [kit README](../tests/target/boot-bench/README.md).

Labels: **Verified** (a repository file, a host test or a build says so; the source is named), **Inference** (derived, not run), **Estimate** (a figure of this page, not a source), **Not verified**. Section references such as "procedure section 6" point into the [procedure](secure-boot-board-test-procedure.md); evidence names such as D9 and T4 point into the [secure boot development plan](plans/secure-boot-development-plan.md) and the [image-state contract proposal](plans/image-state-contract-proposal.md).

## 1. Purpose and scope

The owner wants every board-dependent step of the secure boot work in one bench session that they approve once and run once. This page orders those steps, says what each needs and what it produces, and puts the steps that depend on [#165](https://github.com/wonny-labs/crux-pilot/issues/165) (the FlexSPI write path of MCUboot, open) after the steps that do not, so the session can be cut in two without redoing anything.

**In:** preflight, T0, the ROM serial downloader fall-through check ([#309](https://github.com/wonny-labs/crux-pilot/issues/309)), T1 to T5 of the procedure, the boot-time measurement of the tinycrypt backend (follow-up of decision D9), the image-state board case IS-T4 (defined here, **pending**), and the optional T6 power-cut block.
**Out:** fuses, HAB, lifecycle or closed configuration; the RT1170; eMMC; T7 (needs milestone M9); the PSA-backend measurement (a separate session, block M2); any commit of results under `docs/evidence/`; any key, tag or release.

**Naming.** The image-state proposal also has a case named T4 ("shared data present at application start", question Q4). To avoid a clash with the procedure's T4a and T4b (modified image), this page calls it **IS-T4**.

## 2. Blocks at a glance

Blocks run in this order. **Part 1** needs none of #165. **Part 2** starts with the gate G and needs a recorded decision on #165. **Part 3** is optional and separate.

| Part | Block | What | Needs #165 | Can run now | Estimate (bench time) |
| --- | --- | --- | --- | --- | --- |
| 0 | B0 | Build host work: images, manifest, profiles, wrapper review. No board | No | Yes | Not bench time |
| 1 | P | Preflight: SW4, probe, double backup, slot 1 header check | No | Yes | 20 min |
| 1 | T0 | Restore point boots, identity | No | Yes | 10 min after P |
| 1 | N | [#309](https://github.com/wonny-labs/crux-pilot/issues/309): does a damaged first sector fall through to the serial downloader. Open configuration, no fuses | No (the ROM and the probe write; the bootloader does not) | Yes, for the observation. The flashloader recovery is **blocked** (origin and licence not decided) | 30 min without the flashloader recovery, 60 min or more with it |
| 2 | G | Gate: the task record states the decision on #165 | | | 0 |
| 2 | T1 | MCUboot and the signed, confirmed application, two boots | **Yes** (`copy_done` write) | After G | 15 min |
| 2 | M1 | Boot-time measurement, tinycrypt backend (D9) | **Yes** (needs MCUboot running; Inference: the resets write nothing) | After T1 | 10 min |
| 2 | IS-T4 | Shared boot data present at application start (Q4) | **Yes** | **Pending**: the test image does not exist | 15 min once the image exists |
| 2 | T2, T3a, T3b, T4a, T4b | Unsigned, wrong-key, modified images are refused | **Yes** (whole-slot erase) | After G | 13 min each, 65 min |
| 2 | T5a, T5c | Unpadded and unconfirmed images | **Yes** (whole-slot erase) | After G | 16 + 13 min, 30 min |
| 3 | T6 | Power cut at first selection and at the revert erase | **Yes** | After G and its own approval | 30 min to prove the fixture, then about 2.5 h |
| | T7, M2 | Update by the application; PSA-backend measurement | | **No**: need M9 and a separate approval | |

**Estimates** use the repository's measured Commander rates (at most 4.52 s per 128 KiB to load, about 4.9 s per 128 KiB to read back; [image profiles](board-image-profiles.md), decision 26): reading the 6 MiB backup takes about 4 min and is done twice, one 3 MiB slot load plus verify takes about 4 min, and a slot erase has no recorded duration, so each refusal case waits 360 s (the procedure's figure). Part 1 is about 1 h to 1.5 h, Part 2 about 2.5 h, Part 3 about 3 h. Part 3 is the only part where the board's power is cut. These are **Estimates**, not measurements.

**Splitting.** Part 1 and Part 2 are separate sessions if #165 is not closed on the day (see [section 6](#6-splitting-the-session)). Part 3 is always its own session.

## 3. Consolidated approval checklist

The procedure requires the person who owns the board to approve each hardware step in the task record, with the record reference written down before the step ([procedure section 2](secure-boot-board-test-procedure.md#2-safety-and-approvals)). This list is built so that the owner can write it into the task record once; an operator then cites the item ID of each step as its approval reference (`evidence_dir.py session --approval`). **This page grants none of it.** An approval from an earlier task does not carry over ([`AGENTS.md`](../AGENTS.md)), so the owner writes this list into the record of the task that runs the session.

**Recommendation.** Approve Part 1 (H1 to H5) now. Approve Part 2 (H7, H8, H9) only together with a recorded statement under D165, and keep H6, H10 and H11 not approved until their conditions are met. Reason: Part 1 touches nothing that #165 covers and settles the recovery routes that Part 2 relies on; Part 2's bootloader writes are the exact risk #165 names. The alternative is to approve everything at once and write D165 as "run with the finding open": that is quicker, but the first MCUboot run then writes and erases NOR on a path the #22 matrix did not close, with a backup that stops 2 MiB short of the flash.

| ID | What the owner approves | Covers | Default |
| --- | --- | --- | --- |
| **D165** | The decision on [#165](https://github.com/wonny-labs/crux-pilot/issues/165): (a) it is closed, reference: ___; or (b) Part 2 runs with the finding open, for T1 to T5 and M1 only; or (c) not approved, the session stops after Part 1 | G, and every block of Parts 2 and 3 | Not approved |
| **H1** | Connect the approved probe (J-Link PLUS, SWD 400 kHz, 100 kHz as the one retry) and read identification. Read-only | P, T0, all later reads | |
| **H2** | Read back flash `0x60000000` to `0x60600000` (backup twice) and the small reads of slot heads and tails (`0x60320000`, `0x60020000`, `0x6031F000`). Read-only | P, T0, Parts 2 and 3 | |
| **H3** | Program and verify the restore image R1 (`time-baseline.bin`, at most `0x20000` bytes at `0x60000000`) with the wrapper scripts | T0, N, end-of-session restore | |
| **H4** | Reset the board with the probe, and power-cycle it at J1 by hand. Not the hub fixture | all | |
| **H5** | #309 observation: program the sacrificial first sector (`sacrificial-blank.bin`, then `sacrificial-pattern.bin`, at most `0x1000` bytes at `0x60000000`), power-cycle with SW4 unchanged, read the host's USB listing, restore with H3. SW4 is not touched | N | |
| **H6** | #309 recovery through the serial downloader: change SW4, use a flashloader and a vendor tool. Needs a decision on the flashloader's origin and licence first ([procedure section 6](secure-boot-board-test-procedure.md#6-restore-point-and-recovery), step 6) | N | **Not approved** |
| **H7** | Bootloader NOR writes: program MCUboot (`0x60000000`, at most `0x20000` bytes) and images (`0x60020000`, at most `0x300000` bytes) with the wrapper scripts, and run MCUboot, which writes `copy_done` and erases slot 0 or slot 1 (`0x20000` to `0x620000`) on its own. Includes the whole-slot erase of T2 to T5. Depends on D165 | T1 to T5, M1, IS-T4 | Not approved |
| **H8** | The tester generates the development key and two throwaway keys on the Linux build host, outside every repository, mode 700 and 600, and signs the hardware images with them (decision 18). Keys are never committed, shared or released | B0 | |
| **H9** | M1: up to 10 probe resets per measurement, capturing the console. No probe write | M1 | |
| **H10** | T6: the power-cut fixture (`uhubctl`, J48 removed), the proving cuts and up to 14 measured cuts, off-pauses of 3 s or less. Own approval, own session | T6 | **Not approved** |
| **H11** | IS-T4: boot the IS-T4 image in slot 0. Not approvable until the image is built, reviewed and its hash is in the task record | IS-T4 | **Not approved** |

**Never approved by this list (hard exclusions).** A fuse, HAB or lifecycle operation of any kind, in any block. Any probe write above `0x60600000` (the wrapper scripts refuse any write past `0x320000`). Any erase command from the operator or the tools (the wrappers refuse the word). A probe other than the approved one, `west flash`, or the on-board DAPLink as debug probe. A tag, a key release, a merge. Committing results under `docs/evidence/`: results stay under `<bench>` and go to the maintainers ([procedure section 8](secure-boot-board-test-procedure.md#8-evidence-to-capture-and-how-to-record-it)).

**Which block needs which item.**

| Block | Items |
| --- | --- |
| B0 | H8 (a tester action, no board) |
| P | H1, H2, H4 |
| T0 | H1, H2, H3, H4 |
| N | H1, H2, H3, H4, H5 (H6 only if approved) |
| T1 | D165, H1, H2, H3, H4, H7, H8 |
| M1 | the items of T1, and H9 |
| IS-T4 | the items of T1, and H11 |
| T2, T3, T4, T5 | the items of T1 |
| T6 | the items of T1, and H10 |

## 4. The kit

The kit is `tests/target/boot-bench/`. It implements [procedure section 5](secure-boot-board-test-procedure.md#5-prepare-the-bench) (the two wrapper scripts it says the repository does not have) and the hand-off steps of section 4, step 6. It adds no new test case. **Verified:** each tool has host tests with synthetic inputs and a fake J-Link under `tests/build/test_boot_bench_*.py`. **Not verified:** any behaviour with the real J-Link Commander, a probe or a board.

| Tool | What it does | What it refuses |
| --- | --- | --- |
| `jlink-load.sh`, `jlink-verify.sh` (with `_jlink-common.sh`) | Take one argument, a file name of `<bench>/handoff/` or its full path. Fix the address by file name (`mcuboot.zephyr.bin`, `time-baseline.bin`, `sacrificial-*.bin` at `0x60000000`; `blank-slot0.bin` and every `app.*.bin` at `0x60020000`). Write a command file that begins with `exec DisableAutoUpdateFW` and holds only `usb`, `connect`, `r`, `h`, `loadfile` or `verifybin`, `q`. Run Commander with the procedure's fixed arguments. `jlink-verify.sh` exits 0 only on `Verify successful` | Any other argument count, any argument that mentions erase or fuse, any name or directory outside the table and the hand-off directory, a symbolic link, an empty file, a file larger than its region (`0x20000` at the base, `0x1000` for the sacrificial files, `0x300000` in slot 0), a missing or non-numeric `BENCH_PROBE_SERIAL` |
| `make_manifest.py` | Writes `manifest.json` for every file of the hand-off directory in the device-control schema; `check` reports a file that is listed and missing, changed, or present and not listed (the device-control tool does not check completeness) | Anything but plain files, an empty directory, a revision that is not 40 lowercase hex digits |
| `build_test_images.py` | Builds the procedure's images from given build outputs through `imgtool`, in a staging directory, and moves them into the hand-off directory only if all succeed. Key paths are arguments. `--sacrificial-only` writes the two #309 files | A key inside any git working tree or the hand-off directory, a key readable by group or others, a key named like MCUboot's public `root-*.pem`, the same key in two roles, a confirmed image that is not slot-sized, an existing output (without `--overwrite`). It never reads or copies a key and writes no key path into its record |
| `evidence_dir.py` | `init-bench` creates `handoff cmd evidence backup` and installs the wrappers (refusing to replace an edited script without `--force`); `new-case` creates `<bench>/evidence/<UTC>-<label>`; `session` writes `session-<UTC>.json` (needs at least one approval reference; one file per session); `seal` and `verify-seal` write and check `SHA256SUMS` | A bad label or time, an existing case, a symbolic link, a second seal |
| `boot_timing.py` | Time between two console lines from the `events.jsonl` of a device-control run, over several runs, with min, median and max | A missing pattern, an end before the start |

`BENCH_PRINT_ONLY=1` makes a wrapper write its command file and print the Commander command line without starting the probe. **The person who approves the hardware steps reviews the wrapper scripts and the printed command files first** (procedure section 5).

**Environment of a wrapper.** `BENCH_PROBE_SERIAL` (digits), optionally `JLINK` (the Commander path; default `JLinkExe`). The device-control tool starts a command without a shell and does not change the environment (**Inference** from `tools/device_control/run.py`, which passes none to `subprocess.Popen`), so export both in the shell that runs the tool. A wrapper's directory is its bench: it takes no bench argument.

**Pass rule for a load.** A load is a pass only when a separate `jlink-verify.sh` run follows it and prints `Verify successful` ([procedure section 5](secure-boot-board-test-procedure.md#5-prepare-the-bench), Procedure P). The device-control `flash` operation does both and then requires the verify to pass.

## 5. Blocks

Every block follows the same fields. "Approvals" are the items of [section 3](#3-consolidated-approval-checklist). Stop conditions are those of [procedure section 2](secure-boot-board-test-procedure.md#2-safety-and-approvals) plus the ones named. A stop means: stop, record the state, ask the maintainers.

### B0. Preparation on the build host (no board)

**Purpose.** Everything the bench needs that is not the board. **Preconditions.** Procedure section 3 prerequisites, steps 1 to 5 of procedure section 4 done (build-only check, development key, hardware build, outputs located, signature checks). **Approvals.** H8. No hardware.

```bash
python3 <crux>/tests/target/boot-bench/evidence_dir.py init-bench --bench <bench>
```

```bash
python3 <crux>/tests/target/boot-bench/build_test_images.py --handoff <bench>/handoff \
  --imgtool <mcuboot>/scripts/imgtool.py --python <python> \
  --app-bin <app-out>/zephyr.bin --mcuboot-bin <hwbuild>/mcuboot/zephyr/zephyr.bin \
  --signed-bin <app-out>/zephyr.signed.bin --signed-confirmed-bin <app-out>/zephyr.signed.confirmed.bin \
  --dev-key <keydir>/dev-ec-p256.pem --wrong-key-ec <keydir>/throwaway/wrong-ec-p256.pem \
  --wrong-key-rsa <keydir>/throwaway/wrong-rsa-2048.pem --record <bench>/evidence/images-build.json
```

Pass `--version`, `--header-size`, `--align`, `--load-addr`, `--slot-size` or `--extra-sign-arg` if the build's own `imgtool` arguments differ (procedure section 4, step 6, `grep -h imgtool <hwbuild>/zephyr/build.ninja`). Then the restore image and the #309 files, the manifest, the profiles and the session record:

```bash
cp <crux>/build/zephyr/mimxrt1060_evk_B_qspi/zephyr/zephyr.bin <bench>/handoff/time-baseline.bin
python3 <crux>/tests/target/boot-bench/build_test_images.py --handoff <bench>/handoff --sacrificial-only
python3 <crux>/tests/target/boot-bench/make_manifest.py generate --handoff <bench>/handoff \
  --source-revision "$(git -C <crux> rev-parse HEAD)" --zephyr-revision "$(git -C <workspace>/zephyr rev-parse HEAD)"
python3 <crux>/tests/target/boot-bench/make_manifest.py check --handoff <bench>/handoff
```

Create the read-only command files of procedure section 5 by hand (`identify`, `backup-1`, `backup-2`, `slot1-head`, `slot0-head`, `slot0-tail`, `reset`; the kit generates only the load and verify files) and have the approver read them with the wrappers. Write the profiles of procedure section 5 (T0 marker `CRUX_TIME_READY composition=zephyr`, timeout 10; image marker `CONTROLLER_COMPLETE cycles=20`, timeout 30; erase-wait copy with timeout 360) and a fourth for M1 (marker `Jumping to the first image slot`, timeout 10; **Inference** that the line appears once per boot, from the T1 prediction). Use `<bench>/jlink-load.sh {image}` and `<bench>/jlink-verify.sh {image}` as the `flash` and `verify` commands. Preview every command file without a probe:

```bash
BENCH_PRINT_ONLY=1 BENCH_PROBE_SERIAL=<serial> <bench>/jlink-load.sh app.signed.confirmed.bin
```

Regenerate and re-check the manifest after any change to the hand-off directory; the tool checks every listed file at the start of every run. After the session, `seal` every case directory.

**Stop.** The key directory cannot be made outside every repository; the dumpinfo key hash is `e30466f6b8470c1f29070b17f1e2d3e94d445e3f608087fdc711e4382bb538b6` (procedure section 4, step 5). **Restore.** Nothing to restore; delete `<keydir>/throwaway` once the images exist. **Evidence.** `images-build.json` (hashes and imgtool arguments, no key path), `session-<UTC>.json`, `shasum` and `dumpinfo` of every image, the manifest.

### P. Preflight

**Purpose.** Establish that probe, switch and flash are as the procedure assumes, and keep a backup. **Preconditions.** B0 done. **Approvals.** H1, H2, H4. **Per step:** one record reference each for identify, backup, reset.

1. SW4 `OFF-OFF-ON-OFF` by eye, photographed; board marking photographed (procedure section 3).
2. `ShowEmuList USB` with `exec DisableAutoUpdateFW` first; note `<serial>`, VTref, the J-Link banner.
3. `identify.jlink` (procedure section 6, "Before any test", step 1). At 100 kHz once if 400 kHz fails.
4. `backup-1.jlink` and `backup-2.jlink`, compare the two hashes (step 2); check `FCFB`.
5. `slot1-head.jlink`, check for `3d b8 f3 96` (step 4).
6. `evidence_dir.py session` with the approval references (it refuses without one).

**Expected.** As procedure section 6. **Stop.** Probe cannot connect at 100 kHz; the backups differ; slot 1 carries the image magic. **Restore.** Nothing was written. **Duration.** 20 min (**Estimate**). **Evidence.** Photographs, identify log, both backup hashes, `session-<UTC>.json`.

### T0. Restore point boots

As procedure section 7, T0 with the T0 profile. The R1 programming (H3) now uses `jlink-load.sh` and `jlink-verify.sh` (or the device-control `flash --allow-flash=<H3 reference>`). **Approvals.** H1 to H4. **Stop.** As the procedure's T0. **Restore.** R1 is the restore point. **Duration.** 10 min after P (**Estimate**). **Evidence.** As the procedure's T0.

### N. ROM serial downloader fall-through ([#309](https://github.com/wonny-labs/crux-pilot/issues/309))

**Purpose.** Turn the main inference of the bootloader update investigation into evidence: that the boot ROM falls through to the serial downloader when the first sector of the QSPI NOR is damaged ([boot bootloader update investigation](boot-bootloader-update-investigation.md), rows 1 to 3; the reference-manual statement is **Verified by public vendor document** there, and that a corrupt first sector counts as an error is **Inference**). Open configuration, no fuses. **Preconditions.** T0 passed in this session, so a backup, R1 and a working console exist. **Approvals.** H1 to H5; H6 only if approved.

**Part N-1: observation (kit supports it).**
1. Program `sacrificial-blank.bin` at `0x60000000` with `jlink-load.sh`; verify with `jlink-verify.sh`. This replaces the first sector (4 KiB) of R1.
2. Power-cycle at J1 with SW4 unchanged. Wait 30 s. Record: whether the DAPLink serial port appears, the console bytes (expected none), and what the host's USB listing shows (the ROM serial downloader's USB identifiers are **Not verified** in this repository; record what enumerates, do not rely on a remembered number).
3. Repeat with `sacrificial-pattern.bin` (a different kind of damage: a sector of a repeated pattern instead of an erased one). The issue asks "for which kind of corruption".
4. Restore with H3: `jlink-load.sh time-baseline.bin`, `jlink-verify.sh time-baseline.bin`, then T0's reset capture. The SWD probe can still reach the target in the damaged state (**Inference**: the probe's flash algorithm runs from RAM); if it cannot, stop at step 6 of procedure section 6.

**Part N-2: recovery through the serial downloader (blocked).** Needs H6 and a decision on where the flashloader comes from and its licence (**Not verified**; procedure section 6, step 6), a vendor programming tool, and the SW4 value for the downloader (`OFF-OFF-OFF-ON`, an **Inference**). The kit has no tool for this and the repository holds none. **Do not try it** until those exist and H6 is approved. If it is not run, #309's acceptance criteria on recovery steps stay open; record that.

**Optional part (not in this session).** The application's call of the ROM `runBootloader` entry needs application code that does not exist.

**Stop.** The probe cannot connect after the damage and R1 cannot be restored (procedure section 6, steps 1 to 6); a probe write would go above `0x1000` in this block; anything needs a fuse. **Restore.** R1 programmed and verified; if that fails, R2 (the backup) as in procedure section 6, step 5. **Duration.** 30 min for part N-1, 60 min or more with part N-2 (**Estimates**). **Evidence.** Photograph of SW4, both hashes of the sacrificial files, load and verify logs, the console and USB observation for each kind of damage (what enumerated or not), the restore logs, a written statement that no fuse was written.

### G. Gate: #165

Part 2 starts here. **Do not start T1 until the task record states D165** (procedure section 2). If it says (c), end the session after N: the board is left on R1, verified. If it says (a) or (b), re-check the board's state first (section 6, re-entry) and continue.

### T1. MCUboot and the signed application

As procedure section 7, T1, with the wrappers. **Approvals.** D165, H1 to H4, H7, H8. **Stop.** As the procedure's T1: `Verify successful` missing; no output is a finding about ROM acceptance or console routing, not a pass; slot 1 header carries the image magic. **Restore.** R1 via H3 (replaces MCUboot and the first sectors; slot 0 is left alone, an **Inference**). **Duration.** 15 min (**Estimate**). **Evidence.** As the procedure's T1. **Order inside the block** is the procedure's: slot 0 first, MCUboot second, so MCUboot never runs against a half-programmed slot.

### M1. Boot-time measurement, tinycrypt backend (follow-up of D9)

**Purpose.** Give the owner a first board figure for how long MCUboot spends validating the image with its bundled tinycrypt, which is the evidence trigger R3 of the [tinycrypt policy proposal](plans/mcuboot-tinycrypt-policy-proposal.md) (T4 there names "boot time" as **Not measured**). **Preconditions.** T1 passed, boot 2 included, with `app.signed.confirmed.bin` and MCUboot in place: both flags are set, so the resets below write nothing (**Inference** from T1's prediction for boot 2). **Approvals.** H9 and T1's items.

**Steps.**
1. Capture 10 boots with Procedure R and the M1 profile (each in its own `tool-<n>` directory under one case directory), by a probe reset each. A reset only; no write.
2. Extract two intervals per boot:

```bash
python3 <crux>/tests/target/boot-bench/boot_timing.py --events <case>/tool-*/events.jsonl \
  --start 'RAM loading to 0x[0-9a-f]+ is succeeded' --end 'loaded from the primary slot'
python3 <crux>/tests/target/boot-bench/boot_timing.py --events <case>/tool-*/events.jsonl \
  --start 'Starting bootloader' --end 'Jumping to the first image slot'
```

**What each interval is (Inference).** The first covers what MCUboot does between copying the image to SDRAM and choosing it, which in RAM load includes the hash and the signature check (T1's predicted order, [procedure section 7](secure-boot-board-test-procedure.md#t1-flash-the-bootloader-and-the-signed-application-boot)); the second is from the first MCUboot line to the jump. Both leave out the boot ROM and USB start-up.

**Limits, stated before the run.** The time is the arrival time of the chunk that carried the line's last byte, on the host. At 115200 baud one byte takes about 87 µs, so a 50-character line takes about 4 to 5 ms, and USB chunking adds jitter of an unknown size. **Intervals of 20 ms or less are not resolved** (**Estimate**). The result is a bound at host resolution. If the first interval is close to that floor, the finding is "not resolved", and a measurement with a pin or the cycle counter, which needs an instrumented bootloader build that does not exist, is the follow-up; it is not part of this session. No figure for this exists in the repository (**Not verified**). The PSA backend (block M2) is not measured here: it needs a PSA bootloader build on the current Mbed TLS pair, which no record holds (the comparison record's sizes date from the earlier pair), and its own approval.

**Stop.** Any `E:` line or restart loop; a capture without the start line. **Restore.** None; the board stays on T1's state. **Duration.** 10 min (**Estimate**). **Evidence.** Ten tool directories, both interval outputs with min, median, max, the J-Link banner, the statement of the resolution limit.

### IS-T4. Shared boot data at application start (Q4): pending

**Purpose.** Answer [Q4](plans/image-state-contract-proposal.md#open-questions): is the data MCUboot shares through the retention region intact when the SDRAM-loaded application starts? Contract invariant I6 says this case must run before any other use of the record. **Status: pending. No test image exists, so no hardware step can be approved (H11).**

**What exists.** The composition already enables the sharing on both sides: MCUboot has `CONFIG_BOOT_SHARE_DATA`, `CONFIG_BOOT_SHARE_DATA_BOOTINFO` and the retention backend, and the application has `CONFIG_RETENTION_BOOTLOADER_INFO` with the `zephyr,bootloader-info` region (`zephyr/boot/boards/mimxrt1060_evk_mimxrt1062_qspi_B/`, **Verified in repository**). No application code reads the record: the controller sample does not, and the image-state provider is not implemented.

**Definition of the image (what must exist before H11).** A small Zephyr application, built with the same composition arguments and signed with the development key as a padded, confirmed image (`--pad --confirm`), named `app.is-t4.confirmed.bin` so the wrapper accepts it at `0x60020000`. At start it reads the running slot (`BLINFO_RUNNING_SLOT`), the mode (`BLINFO_MODE`) and the bootloader version (`BLINFO_BOOTLOADER_VERSION`) with `blinfo_lookup()`, prints one line each with the return value and the data, and then prints the marker `IS_T4_COMPLETE`. It writes nothing to flash and never confirms. **Pass (prediction, Inference):** a return of the key's length, running slot 0, mode RAM load, the bootloader version equal to the built value (that last one is image-state case T5). **A missing key or a wrong value is the finding** (the contract's provider would then fail closed, `ERR_NO_BOOT_DATA`).

**Steps once it exists.** Add it to the hand-off directory and manifest; procedure P at `0x60020000`; Procedure R with a profile whose marker is `IS_T4_COMPLETE`; then restore slot 0 with the T1 image. **Approvals.** T1's items and H11. **Stop.** As T1. **Restore.** Program `app.signed.confirmed.bin` again. **Duration.** 15 min (**Estimate**). **Evidence.** Hash and `dumpinfo` of the image, the capture, a statement of which values matched.

### T2, T3a, T3b, T4a, T4b. Refused images

As procedure section 7, T2 to T4. Order: T2, T3a, T3b, T4a, T4b, each with its file from `<bench>/handoff/`, the erase-wait profile (timeout 360 s) and the slot 0 head and tail reads. **Approvals.** T1's items. **Stop.** An application line appears (a security finding: stop and report); no MCUboot output; the console shows a fault. **Restore.** Slot 0 is erased after each case: program the next case's file before its boot; at the end, program `app.signed.confirmed.bin`. **Duration.** 13 min each, 65 min (**Estimate**). **Evidence.** As the procedure's T2.

### T5a, T5c. Unpadded and unconfirmed

As procedure section 7, T5, after the refusals (T5c's second boot erases slot 0). **Approvals.** T1's items. **Restore.** As above. **Duration.** 16 + 13 min (**Estimate**). **Evidence.** As the procedure's T5, plus the console of every boot, in order. A difference from the prediction is the finding; do not repeat the case to make it pass.

### T6. Power cuts (optional, Part 3)

As procedure section 7, T6, in its own session after Part 2. **Approvals.** T1's items and H10. **Preconditions.** T5c done; the cut proven (the `VTref` read inside the same off-pause, `uhubctl -l <hub>` always with the hub named); J48 removed; the slot 1 header check repeated. **Stop.** `VTref` stays at its on value (that is not a power cut); MCUboot does not start after a cut. **Restore.** Program `app.padded-unconfirmed.bin` or `app.signed.confirmed.bin` again; R1 at the end. **Duration.** 30 min to prove the fixture, then 14 cuts at about 10 min (**Estimate**). **Evidence.** As the procedure's T6. The count and fractions are the procedure's proposal, not a repository rule.

### T7 and M2. Not runnable

T7 needs the update agent of milestone M9 ([update agent design proposal](plans/update-agent-design-proposal.md)). M2 (PSA-backend boot time) needs a PSA bootloader build and its own approval. Nothing in this session prepares them except the results of T1 to T6 and M1.

## 6. Splitting the session

The order puts everything that lets the bootloader write NOR after P, T0 and N, so cutting after N loses nothing.

**Session A (Part 1):** B0 (any time before), P, T0, N. It leaves the board on R1, verified, with the backup on the bench machine. Nothing in it depends on #165.

**Session B (Part 2):** G, then T1, M1, IS-T4 (if its image exists), T2, T3a, T3b, T4a, T4b, T5a, T5c. It ends with `app.signed.confirmed.bin` and MCUboot in place or with R1 restored, as the owner chooses before the session.

**Re-entry at the start of session B** (instead of repeating P):
1. SW4 by eye; the probe's `<serial>` unchanged; `identify.jlink`.
2. `jlink-verify.sh time-baseline.bin`: the flash still holds R1. If not, stop and ask; the backup of session A is the reference.
3. `slot1-head.jlink`: no image magic.
4. `make_manifest.py check`; the same keys (if the development key was lost, rebuild MCUboot and every image: procedure section 10).
5. `evidence_dir.py session` again, with the new approval references; it writes a new `session-<UTC>.json` and never replaces an earlier one.

**Session C (Part 3, T6):** as session B's re-entry, plus the fixture proof.

## 7. After the session

1. Program R1 again (H3) unless the owner chose to leave MCUboot in place, and say which.
2. Read slot heads and tails once for the record (H2).
3. `evidence_dir.py seal --case <case>` for every case; keep `<bench>` and give the maintainers its path.
4. Destroy `<keydir>` or keep it private; delete the signed images unless the maintainers decide to keep them ([procedure section 2](secure-boot-board-test-procedure.md#2-safety-and-approvals), "After the campaign").
5. Fill the results table of [procedure section 9](secure-boot-board-test-procedure.md#9-results-table), plus these rows: N (what enumerated for each kind of damage), M1 (min, median, max of both intervals and the limit), IS-T4 (pending or the values).

## 8. Open questions

- [ ] D165: which of (a), (b) or (c)? Every block of Parts 2 and 3 waits for it.
- [ ] H6: where does the flashloader come from, under what licence, and who may run it? Until then #309's recovery acceptance stays open.
- [ ] Does the installed J-Link Commander accept the `loadfile "<file>", <address>` and `verifybin "<file>", <address>` forms the wrappers write, and does `-ExitOnError 1` give a non-zero status on a failed script command? The procedure asks the first (section 10); the second is new. The wrappers never rely on the exit status alone for a verify.
- [ ] Does the device-control tool's start of a command keep `BENCH_PROBE_SERIAL` in the environment? Inference yes; a host test of the wrapper with a fake tool does not show it.
- [ ] Who writes and reviews the IS-T4 image, and in which change? It is the one block of Part 2 that has no artefact.
- [ ] Is a host-side figure of 20 ms resolution enough for D9, or does the owner want the instrumented measurement first? The answer decides whether M1 is worth the bench time.
- [ ] Are the resets of M1 free of NOR writes? Inference from T1's boot 2; read slot 0's tail before and after the ten resets to see (the kit's `slot0-tail.jlink` of procedure section 5).
- [ ] The other open questions of [procedure section 10](secure-boot-board-test-procedure.md#10-open-questions-for-the-first-bench-session) still apply and are not repeated.
