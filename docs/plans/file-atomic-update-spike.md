# Atomic file updates across power loss: spike

Status: **spike result, proposed, not adopted.** It authorises no implementation, public interface, dependency,
hardware operation or merge, and it changes no source, test, script or evidence file. The owner approved the spike on
22 November 2026 as item 4 of a product team's list of Crux gaps. Baseline: `main` at
`2c017f685e0215e0e269d4bc77272889d06a07d8`.

The question: what Crux needs so that a product can update a file and, after a power cut at any moment, find either the
complete old content or the complete new content, never a torn or missing file. A product needs this for the power-loss
campaign of its second and third increments.

This note builds on the [Reliance Edge assessment of the File service](../emmc-reliance-file-service-assessment.md)
(issue #257), which compared the options for File-level atomic replace in detail. This note does not repeat that
comparison. It adds the product's view, the in-place update case, the flush rule and a concrete next step.

Labels, as in the assessment: **[O]** observed in source, tests or recorded evidence at the baseline, **[I]** inference,
**[U]** unknown. No probe ran for this note: the deciding tests need the Reliance Edge `native_sim` build, which needs the
Docker workspace, and free disk space was under the limit for new builds.

## 1. What exists

### The contracts say "no atomicity"

- **[O]** The [File contract](../file-contract.md) lists atomic replace as out of scope. It says "No atomic update or
  general power-loss safety is promised". `crux_file_sync` OK acknowledges the provider's flush only.
- **[O]** `crux_file_rename` refuses an existing destination on every provider. So a replace built from File calls is
  write temporary, close, remove target, rename. A cut between the remove and the rename leaves no target. File does not
  recover from this ([Pool size and handle budget](../file-contract.md#pool-size-and-handle-budget), "Replace").
- **[O]** The [File service contract](../file-service-contract.md#commit-and-power-loss) says that neither write mode
  is atomic across power loss. Its managed upload uses a sidecar and a recovery at start. The recovery is ordered and
  conservative. One same-size state keeps both files and holds the name until a host repair, and no repair tool exists
  for Reliance Edge (assessment, row 4).
- **[O]** The credential store does not rename. It writes two slots with a tag and a generation and takes the valid slot
  with the higher generation. Its guarantee does not depend on file system atomicity
  ([credential store](../credential-store.md)).
- **[O]** On 4 November 2026 the owner decided to keep the File contract as it is and to reconsider atomic replace
  after physical evidence (recorded in the owner's decisions of 4 November 2026 in the [eMMC design](emmc-reliance-design.md), and in the assessment).

### What each file system offers

| File system, medium | Replace | In-place update of one file | Sync | Source |
| --- | --- | --- | --- | --- |
| FatFs, microSD (and FAT on any disk) | **[O]** Zephyr's `fatfs_rename` removes an existing destination and then calls `f_rename`. The two steps are not one transaction. **[O]** On the board, 29 of 100 cuts of a replace loop left no target and a complete newer temporary. | **[I]** Not atomic: a cut inside a multi-sector write leaves a mix of sectors. | `f_sync`. Durable only if the disk honours it. | `subsys/fs/fat_fs.c:169-186`; [replace cuts](../evidence/microsd-replace-cut/README.md) |
| Reliance Edge, eMMC or microSD | **[O]** `REDCONF_RENAME_ATOMIC` is 1, and the profile commits on `RENAME`. So the VFS rename replaces the destination in one transaction. **[O]** In the replay model, W2 (temporary, then VFS rename) kept I3, "complete old or complete new", at every cut on `red-fix`. | **[I]** A file written and then synced is one transaction, **but a transaction covers the whole volume**. Another handle's sync, close or create, and an automatic commit when the volume fills (`RED_TRANSACT_VOLFULL`), commit a half-written file too. So "write, then sync" is atomic only when nothing else commits in between. | `red_fsync` commits: flush, metaroot write, flush. | `zephyr/fs/reliance_edge/config/redconf.h:35`, `:88-91`; [design](emmc-reliance-design.md), F3, F9 and "Failure behaviour"; [replay record](../evidence/emmc-reliance/replay-reliance/README.md) |
| littlefs, NOR flash | **[O]** `lfs_rename` replaces a destination of the same type, and Zephyr's `littlefs_rename` passes through. The littlefs README says all POSIX operations are atomic across power loss. | **[O]** The README says that file updates are committed only at sync or close. **[I]** So an update of one file, then a sync, is old or new. | Commit at sync or close. | littlefs 2.11 `README.md:112-114`, `lfs.h:512-519`; Zephyr `subsys/fs/littlefs_fs.c:359-372` |
| Linux, Host | **[O]** `rename(2)` replaces atomically in the namespace. | **[I]** Not atomic. | **[I]** Durability of a rename also needs an `fsync` of the directory, which the Linux provider does not do. Host only, so not product-relevant. | `components/file/ports/linux/file_linux.c` |

Rows for littlefs: **[O]** the File provider's littlefs composition compiles on `native_sim` and has never run
([File contract](../file-contract.md#native-mapping-of-the-additions)). No product composition uses littlefs for File
today.

### eMMC cache and flush order

- **[O]** At the Zephyr pin, the MMC stack turns the eMMC cache on when the device has one, and the disk sync only waits
  for the card to be ready. It sends no flush (design F2, [eMMC semantics](../evidence/boot-emmc/emmc-semantics-and-hardware.md), E17).
  So on such a device, without the correction below, a successful sync does not mean the data is on the medium, whatever
  the file system.
- **[O]** Reliance Edge needs the flush as a barrier before and after the metaroot write (design F3). Without it, the
  file system's own atomicity is not guaranteed.
- **[O]** The correction exists as a build-local patch, `CONFIG_CRUX_MMC_CACHE_FLUSH`, **default `n`**
  (`zephyr/Kconfig:419`). **[O]** The Reliance Edge adapter's build guard stops configuration on an MMC disk without it
  (`zephyr/fs/reliance_edge/CMakeLists.txt:17-19`). The only exception is the replay's flush-control fixture
  `CRUX_EMMC_FLUSH_CONTROL`, which the same file refuses on any board but `native_sim` (lines 13-15). **[O]** No such
  guard exists for other file systems on an MMC disk, for example FatFs.
- **[U]** Whether a single-sector write is atomic on a device, and whether its cache keeps write order, are not
  established from any free source (E16). Reliable Write is not used by the stack (E19). Cache and flush behaviour
  depend on the part, so each candidate eMMC part is its own case.

### Tests and evidence

| Level | What exists | What it shows |
| --- | --- | --- |
| Host, fake | `crux_file_fake` cuts a forked child at a chosen mutation. File service and credential store cut walks use it. | The order of a caller's sequence. The fake's power model is simpler than any file system (`tests/file/fake_file.h:14-18`). |
| `native_sim`, replay | `tests/native/emmc_powercut`: an eMMC simulator, four cut models (lost, prefix, reordered, torn), invariants I1 to I5, workloads W1 to W4, negative controls. | Reliance Edge keeps I1 to I5 for append, VFS-rename replace and Settings saves, in a model written by the author of the code. **[O]** W2 and W4 call the VFS rename. No workload replaces a file through File or runs the File service. |
| Physical, FatFs, microSD | 33 append cuts and 100 replace cuts on one board and one card. | Appends with a sync each held. The replace window is real. |
| Physical, Reliance Edge | **None.** Stage A (Reliance Edge on microSD) of the [physical gate](../emmc-reliance-physical-gate.md) has images and a run sheet. Stage B (eMMC) has a list of steps, and its images and board values are still to be fixed. Neither has run. | Nothing. |
| Rig | `scripts/power_cut.py` with `--cut-cmd`, and the Stage A replace image `samples/storage_reliance_sd` with `CONFIG_SAMPLE_RELIANCE_SD_REPLACE_TEST`. | Ready for a campaign. The replace image calls `fs_rename`, not File. |

## 2. The gap

| Guarantee a product wants | State |
| --- | --- |
| Replace a named file, old or new after a cut | **Not offered by File on any provider.** The File contract forbids it on purpose. Shown on a model only for Reliance Edge, through the VFS rename, not through File. Shown to fail on FatFs on the board. |
| Update a file in place, old or new after a cut | **Not offered and not safe to offer generally.** Plausible on littlefs. **[I]** On Reliance Edge it holds only while no other handle commits. Not true on FatFs. |
| A sync that means "on the medium" | **Claimed by the contract only as "the provider's flush".** On a cached eMMC it is false without `CONFIG_CRUX_MMC_CACHE_FLUSH`. The build requires it for Reliance Edge on an MMC disk, not for other file systems there. |
| Append, with acknowledged records kept | Shown on FatFs on the board (33 cuts) and on Reliance Edge in the model. The product owns the record format that skips a torn tail. |
| Two-slot records, old or new | Offered by the credential store's design for its own records. Not offered as a general File helper. |

What a product's power-loss campaign needs from Crux:

1. **A named guarantee it can test against**: one File operation whose contract says "old or new after a cut", and a
   way for the product to know at build time whether the selected provider gives it.
2. **A sync that reaches the medium** in every composition that claims the guarantee, enforced by the build. This
   holds today for Reliance Edge on an MMC disk.
3. **A reference workload and a checker** that use File, not the VFS, so the product runs the same code path in its
   campaign that Crux tested. The existing rig, `scripts/power_cut.py`, can drive it.
4. **Software evidence before board time**: the same workload in the replay model, with a negative control, so that a
   board run confirms a model instead of exploring.

## 3. Options

| Option | Summary | Fits a product on Reliance Edge | Fits FatFs | Public change |
| --- | --- | --- | --- | --- |
| A. Keep File as it is | The product builds its own recovery (temporary, remove, rename, scan at start), as the File service does. | Works, but every product rewrites and tests a recovery, and the window stays open on a file system that could close it. | Same | None |
| **B. Capability-gated replace (recommended)** | One new File operation that replaces an existing regular file in one step. A provider offers it only when its file system replaces atomically. FatFs returns `NOT_SUPPORTED` without touching any file. This is option 3 of the assessment. | Yes: Reliance Edge (rename atomic and committed), littlefs, Linux. | Refused explicitly. The product uses two slots or its own recovery. | Experimental function in `crux/file.h`, contract text, providers, fake, tests |
| C. Transactional commit over several files | Begin and commit around a set of writes, mapped to a Reliance Edge transaction. | **[I]** No: a transaction covers the whole volume, so another File user's sync commits half of it. It would need File to own every commit on the volume. | No | Large, file-system specific |
| D. A two-slot record helper over File | A Crux helper that keeps two copies with a check value and a generation, as the credential store does. | Yes, on any file system. | Yes | New helper interface |

Option D is the only one that also works on FatFs. It changes the product's file layout and doubles storage for each
record, and the credential store already shows the pattern. It is a useful later addition, not the first step. It is not
recommended now, because it does not give the "named file, old or new" semantics that a campaign tests, and the
product's medium is eMMC, where the M14 design chose a transactional file system. The product's own file system choice
is still open (decision 5).

## 4. Recommendation

**Path: option B, a capability-gated atomic replace in File, offered only where the build already guarantees a durable
sync.** In-place atomic update and multi-file transactions are not offered.

Why:

- **[O]** The one failure measured on a board (missing target after a cut) is exactly the window that File's own rule
  forces open. **[O]** Reliance Edge, the file system of the M14 design, closes it in one transaction, and the model agrees. **[U]**
  Whether the product ships Reliance Edge is decision 5.
- **[I]** A replace through a temporary file is safe against other File users' commits, because the target does not
  change until the rename transaction. An in-place update is not, on Reliance Edge.
- **[I]** Refusing on FatFs keeps every promise true. A name that means "atomic" only on some providers, the
  assessment's option 2, is avoided.
- **[I]** The File service can drop its sidecar path where the operation is offered and keep it for FatFs.

Shape for discussion only, not adopted:

```c
/* Experimental. Replaces `to` with `from` inside one root. On a provider that offers it, a power cut leaves `to` with
 * its complete old content or the complete content that `from` had at its last successful sync or close, and `from`
 * either still present or gone. Without the capability it returns CRUX_FILE_ERR_NOT_SUPPORTED and changes nothing. */
crux_file_result_t crux_file_replace(crux_file_root_t root, const char *from, const char *to);
```

Rules to settle in the proposal: live handles on either name give `INVALID_STATE` (as rename). A missing or
non-regular source gives `NOT_FOUND`. A destination that is not a regular file is refused, because the Reliance Edge
VFS rename would replace an empty directory. A missing destination is allowed and behaves as rename. How a product learns
the capability (a compile definition of `crux::file`, such as `CRUX_FILE_HAS_ATOMIC_REPLACE`, or a runtime call) is an
owner decision below.

### Smallest next step: replay workload W8, no interface change

W8 is numbered after the assessment's proposed W5 (credential save) and W6 (File service commit), which it does not
replace.

This answers the deciding question in software, before any public change: **does a replace through the File provider
stack keep "old or new" on the Reliance Edge model, and can the replay see the window when it does not?**

Work, all inside `tests/native/emmc_powercut` and its driver. **[O]** The replay image calls the VFS only today and
links no File provider, so the Reliance Edge image first selects `CONFIG_CRUX_FILE_RELIANCE_EDGE` and binds a File root
on the replay's mount:

- **W8**, through File: open the temporary with `CREATE_REPLACE`, write, `crux_file_sync`, close, then replace the
  target with the VFS rename on the same mount. The rename is called directly, because no File operation exists yet.
  This is the File-level data path of the proposed operation. W2 has no File layer.
- **W8-control**, the sequence File allows today: the same, but `crux_file_remove_at` of the target, then
  `crux_file_rename`.
- Optional **W9**, in-place update under a concurrent commit: overwrite a file through one handle while a second handle
  syncs another file, to confirm on the model the reason option C and in-place update are rejected.

Acceptance criteria:

1. On `red-fix`, W8 keeps I1 to I5 with `read_error=0` in all four cut models, at every mandatory position (each side of
   every flush, each metaroot sector), with the sampled positions recorded with their seeds.
2. On `red-fix`, W8-control **fails I3** (target missing) at the cut between the removal's transaction and the rename's.
   If it does not fail, the workload cannot see the window, and criterion 1 proves nothing.
3. On `red-nofix`, cached, lost model, W8 fails I2 or I3, as the existing flush control does.
4. On `fat-fix`, W8-control is run and recorded as an observation (expected: missing target, as W2).
5. Only test code and the replay driver change. The CI selection stays within the replay's existing bound. A new record
   under `docs/evidence/` gives the revision, commands, images, counts and seeds. No existing evidence file changes.
6. The images keep the existing flush guard: `red-fix` sets `CONFIG_CRUX_MMC_CACHE_FLUSH`, and only `red-nofix` uses
   `CRUX_EMMC_FLUSH_CONTROL`.

Cost: it needs the
Reliance Edge west group and the Docker workspace, so it waits for free disk space above the stop line.

### After the owner's decisions: the operation itself

If the owner adopts option B, implement it test first:

- **Host.** Conformance cases in `tests/file/conformance.c` for each rule above. The fake gains the operation with the
  rule "reaches storage when it returns", and a cut walk of the consumer pattern (write temporary, sync, close, replace)
  shows old or new at every mutation. The fake's result proves order only. The FatFs provider test shows
  `NOT_SUPPORTED` with both files unchanged.
- **`native_sim`.** `tests/native/file_reliance` runs the conformance cases. W8 switches from the direct VFS call to
  `crux_file_replace`, with the same criteria. The littlefs composition (`tests/native/file_littlefs`) must run, not only
  compile, before littlefs claims the capability. littlefs on NOR has no cut model here, so its claim rests on upstream
  documentation until a NOR cut model or a board run exists.
- **File service.** Uses the operation when offered: temporary, sync, close, replace, no sidecar. Keeps the current path
  where it is refused. Both paths keep their cut walks.

### What only a board power-cut campaign can show

- What the eMMC part does at a real cut: its translation layer, cache order, damage outside the sector being written,
  and the supply ramp. The replay models none of these.
- That the flush correction works on the real host controller and part, and what each flush costs. Under the current
  transaction mask a replace through a temporary is at least three Reliance Edge commits (create, sync, rename), each
  two flushes.
- Rates over many cuts, wear and temperature, and slow effects such as the orphaned clusters seen on FatFs.
- Each candidate eMMC part separately, because cache and flush behaviour are part specific.

Sequence: the existing Stage A replace image with the File-level replace (Reliance Edge on the microSD, no eMMC
needed), then Stage B on each eMMC part. Each needs the owner's approval for the current task.

## 5. Decisions for the owner

| # | Decision | Recommendation | Impact |
| --- | --- | --- | --- |
| 1 | Start W8 (software only, no interface change) now, before Stage A has run? The 4 November decision waits for physical evidence before changing the contract. W8 changes no contract. | **Yes.** It gives the model evidence that a Stage A run then confirms, and it can fail cleanly. | Test code and one evidence record. Needs disk space for the Reliance Edge build. |
| 2 | Adopt option B as the direction, with the contract sentence held until physical evidence? | **Yes**, direction now, contract text after Stage A. | The alternative is option A: each product writes its own recovery. |
| 3 | How a product learns the capability: a compile definition of `crux::file` or a runtime call. | **Compile definition.** One File provider is selected per image, and a campaign wants a build-time answer. | A runtime call would also serve images with providers per root, which no composition has. |
| 4 | Extend the existing flush guard, today only in the Reliance Edge adapter, to every File composition on an MMC disk (FatFs too), and offer the replace capability only where the guard applies? | **Yes.** Without the correction no sync on a cached eMMC is durable, on any file system. | A small build change outside protected paths. Until the upstream fix lands, every eMMC image carries the build-local patch, as Reliance Edge images already do. |
| 5 | Which file system the product ships on eMMC. The Reliance Edge commercial licence is still open. | Decide before option B is implemented. | If not Reliance Edge, option B helps only if littlefs or another atomic-rename file system is chosen. On FAT, option D or option A is the only route. |
| 6 | Must the File service keep its FatFs commit path? (Assessment, option 3.) | Keep it while any composition uses FatFs for the service. | Two commit paths and two sets of tests. |
| 7 | Board time for Stage A and Stage B. | Later, after W8 passes. | Needs the board, its custody and an approval for that task. |

## What this note does not do

It runs no probe, changes no code, adopts no interface and states no result for any device. Statements about littlefs
and Reliance Edge come from their documentation and the repository's earlier source readings. The Reliance Edge source
was not re-read for this note.
