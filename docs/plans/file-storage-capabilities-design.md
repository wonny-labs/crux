# File storage capabilities: design proposal

Status: **Proposed, for the owner. Nothing here is adopted, and implementation is not approved.**
The owner approved writing this document on 26 November 2026.
It is documentation only: it changes no source, test, build, check, contract or protected path.
Every decision row in [Decisions for the owner](#decisions-for-the-owner) is open.
Baseline: `main` at `cc39cba5`, Zephyr v4.4.2 `dccb095`, Reliance Edge v3.0 `6706984`.

This page proposes the next File capabilities for a set of provisional consumer requirements that are not tied to one product.
It is for the owner, who decides, and for the implementer of an adopted part.
For each requirement it says what the current code already satisfies, with file and line, and proposes changes only for the gaps.
Policy, such as sizes, the reserve and who may recover a medium, stays in the application, because another product may choose differently.

It builds on the [File contract](../file-contract.md), the [File service contract](../file-service-contract.md), the [atomic update spike](file-atomic-update-spike.md), whose replay workload W8 has run ([record](../evidence/emmc-reliance/replay-file-w8/README.md)), and the [Reliance Edge assessment of the File service](../emmc-reliance-file-service-assessment.md).
It does not repeat their analysis, and it links to them where they are the home of a fact.

## Evidence labels

| Label | Meaning |
| --- | --- |
| **[R]** | Verified in this repository at `cc39cba5`, by file and line. |
| **[Z]** | Verified on pinned upstream source: Zephyr `dccb095` read with `git show dccb095:<path>` outside this repository, or littlefs as fetched by the workspace. |
| **[U]** | Documented upstream: an official specification, manual or the pinned project's own source comments, with the link in [Sources](#sources). |
| **[I]** | Inference from the rows named. The reasoning is stated. |
| **[N]** | Not verified: not read, not run, or needs a board. |

Each proposal is also classed as **industry standard** (an established practice with a cited source), **documented option** (a configuration or call that the upstream project documents) or **workaround** (local to Crux, compensating for an upstream gap).

## Requirements and the current state

| # | Requirement | Already satisfied | Gap | Section |
| --- | --- | --- | --- | --- |
| 1 | Free-space query | No. Only an internal FatFs use of `fs_statvfs` exists. | A public query | [1](#1-free-space-query) |
| 2 | Atomic replace of a file | No. Rename refuses an existing destination on every provider. | The operation, its capability flag and the flush guard for every MMC composition | [2](#2-atomic-replace) |
| 3 | At least 16 handles and two listings, shared | Mostly: the pools are build settings with ranges 4 to 32 and 1 to 8. | No measurement of use; 16 is untested; FatFs file objects are not checked at build | [3](#3-handles-and-listings) |
| 4 | Shared lock held per chunk at most | Yes at the File layer: the lock is held for one provider call. | No bound on what one call holds; no measurement | [4](#4-lock-hold-time) |
| 5 | Uploads and staging refused below a reserve | No. The file service's limits are counters, not free space on the medium. | A reserve check, which needs requirement 1 | [5](#5-reserve-for-critical-writers) |
| 6 | Last committed state after power loss, no automatic format, explicit recovery | Mostly: no File composition can format at mount, and Reliance Edge on MMC requires the cache flush. | Atomicity only where the file system gives it; the flush guard misses FatFs on MMC; no guard for littlefs mounts | [6](#6-power-loss-and-recovery) |
| 7 | Retention log built on File later | Its building blocks exist: append, size, stat, remove, rename, listing. | Requirements 1 and 5 | [7](#7-what-a-retention-log-needs-from-file) |

## 1. Free-space query

### What exists

- **[R]** File has no volume call. `crux_file_info_t` holds only a size (`components/file/include/crux/file.h:30-33`), and the contract says so ([Free space](../file-contract.md#free-space)).
- **[R]** The FatFs selection calls `fs_statvfs` only to map a refused create on a full volume to `CRUX_FILE_ERR_NO_SPACE`, and returns no value (`components/file/ports/zephyr/file_native.c:276-284`).
- **[R]** The Reliance Edge adapter implements `statvfs` and fills block size, fragment size, total and free blocks from `red_statvfs` (`zephyr/fs/reliance_edge/fs_reliance_edge.c:540-555`).
- **[Z]** `struct fs_statvfs` has four members: `f_bsize`, `f_frsize`, `f_blocks` and `f_bfree`, with sizes in `f_frsize` units (`include/zephyr/fs/fs.h:137-146`). `fs_statvfs` takes a path inside a mount and calls the file system's `statvfs`, or returns `-ENOTSUP` (`subsys/fs/fs.c:666-692`).
- **[Z]** FatFs answers from `f_getfree` (`subsys/fs/fat_fs.c:414-445`).
  **[U]** On FAT32 the count comes from the FSINFO sector, which can be out of step, and FatFs can be forced to scan the whole FAT instead (FatFs `f_getfree` notes).
- **[Z]** littlefs computes free blocks as total minus `lfs_fs_size` (`subsys/fs/littlefs_fs.c:561-585`), which traverses the file system and is "best effort" (`lfs.h:718-724`).
- **[U]** On Reliance Edge, data freed by an operation "will not return to free space until after a transaction point" (`red_rename` comment, `posix/posix.c`). `REDSTATFS` also counts free inodes (`f_ffree`, `include/redstat.h`), which `struct fs_statvfs` cannot carry.
- **[U]** POSIX `statvfs` leaves it unspecified whether every member is meaningful on every file system, and Linux reports `f_bavail` (blocks an unprivileged process may use) apart from `f_bfree`.

### Options

| Option | Summary | Class |
| --- | --- | --- |
| **A. One File call over the native volume query (recommended)** | `crux_file_volume_info(root, &info)` maps to `fs_statvfs` on Zephyr and `fstatvfs` on Linux. | Industry standard: POSIX `statvfs`, Zephyr `fs_statvfs` |
| B. The product calls `fs_statvfs` in its own adapter | What the contract suggests today. Outside File's lock, tests and the Host build. | Workaround |
| C. A File-maintained free counter | File counts bytes written and removed. It cannot see file system overhead, copy-on-write blocks or native writers. | Workaround, rejected |

### Recommendation and interface

Option A, Experimental, in the owner header `components/file/include/crux/file.h` (CONTRIBUTING: one public header per component, `crux_` prefix):

```c
/** What File reports about the volume that holds a root. Figures are estimates, not reservations. */
typedef struct {
    uint64_t total_bytes; /**< Capacity for file data, in bytes. */
    uint64_t free_bytes;  /**< Bytes this image may still allocate, in bytes. */
} crux_file_volume_info_t;

/**
 * Experimental. Read the size and free space of the volume that holds a bound root.
 * Thread context. Holds the File lock for one provider call.
 * @return CRUX_FILE_OK, CRUX_FILE_ERR_NOT_READY for an unbound or unmounted root,
 *         CRUX_FILE_ERR_NOT_SUPPORTED when the file system has no volume query, or another error.
 */
crux_file_result_t crux_file_volume_info(crux_file_root_t root, crux_file_volume_info_t *out);
```

Rules to put in the contract:

- `total_bytes = f_frsize * f_blocks` and `free_bytes = f_frsize * f_bfree` on Zephyr; `f_frsize * f_bavail` on Linux, because that is what the process can use. Overflow is checked and gives `CRUX_FILE_ERR_OUT_OF_RANGE`.
- The figure is an estimate at the moment of the call. It does not reserve space, and a later write may still give `CRUX_FILE_ERR_NO_SPACE`. On Reliance Edge it may stay low until the next commit, on FAT32 it may be wrong if FSINFO is stale, and on littlefs it is best effort (sources above).
- On Reliance Edge a create may give `CRUX_FILE_ERR_NO_SPACE` with free blocks left, when no inode is left ([Reliance Edge mapping](../file-contract.md#reliance-edge-mapping)). This call does not report inodes, because no listed requirement needs it and `fs_statvfs` has no field for it.
- Argument and root checks run as for `crux_file_stat`.

### Compatibility, concurrency, power loss and cost

- **Compatibility:** an addition only. File is Unstable ([Component readiness](../component-readiness.md)); a new function starts Experimental with a release-note entry ([ADR-0001](../decisions/0001-application-boundary-and-api-stability.md#41-tiers)). The private port `components/file/src/file_port.h` gains `crux_file_impl_volume_info`, and every provider, the fake included, implements it.
- **Concurrency:** under the File lock, like `crux_file_stat`. **[I]** Moving it outside would not shorten waits on FatFs: with `CONFIG_FS_FATFS_REENTRANT` the volume mutex is held through `f_getfree` anyway, and a FAT scan blocks other calls on that volume whatever File does. A product that fears a first-call FAT scan calls it once at start.
  On Reliance Edge the call takes one of the adapter's thread slots for the calling thread, as every call does ([Reliance Edge mapping](../file-contract.md#reliance-edge-mapping)).
- **Power loss:** reads only; no change.
- **Cost:** **[I]** a few hundred bytes of code and no RAM. Measure with the existing cross-build size reports before claiming a figure.

### Tests

- **Host:** conformance cases in `tests/file/conformance.c` for arguments, an unbound root and the result shape, run on the Linux provider and the fake. The fake already has `crux_file_fake_set_capacity` (`tests/file/fake_file.h:70`), so free space can be asserted to fall with writes and rise with removes.
- **`native_sim`:** `tests/native/file_fatfs` and `tests/native/file_reliance`: total matches the RAM disk within the file system's overhead; free falls after a synced write and rises after a remove (on Reliance Edge, after the commit). `tests/native/file_littlefs` compiles it.
- **Cross-build:** `scripts/test-file-rt1060-compile.sh` and `scripts/test-file-emmc-compile.sh` link it.
- **Physical board:** one read on a provisioned microSD card against a host's figure. Needs its own approval.

## 2. Atomic replace

The spike is the home of the analysis: what each file system offers, the options and the evidence plan ([spike](file-atomic-update-spike.md), sections 1 to 4).
This section records what changed since it and what an implementation needs.

### What exists

- **[R]** `crux_file_rename` refuses an existing destination on every provider (`components/file/src/file_port.h:40`, `components/file/ports/zephyr/file_native.c:444-455`, `components/file/ports/linux/file_linux.c:237-259`). A replace built from File calls leaves no target after a cut between remove and rename ([Pool size and handle budget](../file-contract.md#pool-size-and-handle-budget), "Replace").
- **[R]** Reliance Edge is configured with `REDCONF_RENAME_ATOMIC 1` and a commit on rename (`zephyr/fs/reliance_edge/config/redconf.h:35`, `:88-91`).
  **[U]** With atomic rename, "in one atomic operation" the destination is unlinked and the source renamed (`red_rename` comment).
- **[R]** Replay W8, a replace through the File provider ending in one Reliance Edge rename, kept the target complete, old or new, at every cut of the model, and its control lost the target in every generation ([W8 record](../evidence/emmc-reliance/replay-file-w8/README.md)). It is model evidence on `native_sim`, not device evidence. On FatFs both workloads lost the target.
- **[Z]** Zephyr's `fs_rename` clobbers an existing destination (`include/zephyr/fs/fs.h:347-371`); it says nothing about power loss.
- **[U]** POSIX `rename` keeps the destination name visible throughout and calls the action atomic, but says nothing about a crash. **[U]** On Linux, durability of a rename also needs `fsync` of the directory (`fsync(2)`).
- The spike's decisions 2 to 7 have no recorded owner decision **[N]** (no comment on its pull request, no issue found).

### Recommendation and interface

The spike's option B, a capability-gated replace, in `crux/file.h`. Class: **industry standard** where offered (write a temporary, sync, rename over the target is the POSIX pattern; Reliance Edge and littlefs document atomic rename), and an explicit refusal where the file system cannot keep it.

```c
/**
 * Experimental. Replace `to` with `from` inside one root. Where CRUX_FILE_HAS_ATOMIC_REPLACE is 1,
 * a power cut leaves `to` with its complete old content or the complete content of `from`, and
 * `from` either present or gone. Otherwise it returns CRUX_FILE_ERR_NOT_SUPPORTED and changes
 * nothing. A missing `to` behaves as crux_file_rename().
 */
crux_file_result_t crux_file_replace(crux_file_root_t root, const char *from, const char *to);
```

- Checks in this order: arguments; `NOT_SUPPORTED` without the capability; `INVALID_STATE` for a live handle on either name; `NOT_FOUND` for a missing or non-regular source; `EXISTS` when `to` exists and is not a regular file (the Reliance Edge rename would replace an empty directory); `from` equal to `to` is `INVALID_ARGUMENT`.
- `CRUX_FILE_HAS_ATOMIC_REPLACE` is a public compile definition of `crux::file`, like `CRUX_FILE_POOL_SIZE`: 1 for the Reliance Edge selection on a build that satisfies the flush guard, 0 for FatFs selections, 0 for the Linux provider until it syncs the directory after the rename, and 0 for littlefs until its composition runs, not only compiles ([spike](file-atomic-update-spike.md#after-the-owners-decisions-the-operation-itself)).
- The content of `from` that survives is what its last successful sync or close left. On Reliance Edge the rename's commit covers the whole volume, so it also commits unsynced data **[U]** ("Fsyncing one file effectively fsyncs all files", `red_fsync` comment); the contract promises only the weaker rule.

### Compatibility, concurrency, power loss and cost

- **Compatibility:** an addition. `crux_file_rename` keeps refusing an existing destination. The File service may later use the replace where offered and keep its sidecar path elsewhere (spike decision 6).
- **Concurrency:** one provider call under the File lock, like rename.
- **Power loss:** as stated, only where the flag is 1. A product on FatFs keeps a two-slot record, as the [credential store](../credential-store.md) does, or its own recovery.
- **Cost:** **[I]** a provider branch and a compile definition. On Reliance Edge a replace through a temporary is three commits (create, sync, rename), each two flushes ([W8 record](../evidence/emmc-reliance/replay-file-w8/README.md)).

### Tests

- **Host:** conformance cases for each rule; the fake gains the operation, with "reaches storage when it returns", and a cut walk of write, sync, close, replace shows old or new at every mutation. The FatFs build returns `NOT_SUPPORTED` with both files unchanged.
- **`native_sim`:** `tests/native/file_reliance` runs the cases; W8 in `tests/native/emmc_powercut` switches from the VFS call to `crux_file_replace` and keeps its criteria and controls.
- **Cross-build:** the eMMC link (`scripts/test-file-emmc-compile.sh`) shows the flag is 1 there and 0 in the FatFs RT1060 link.
- **Physical board:** Stage A of the [physical gate](../emmc-reliance-physical-gate.md) (Reliance Edge on microSD) with the File-level replace, then each eMMC part. Each needs the owner's approval for that task.

## 3. Handles and listings

### What exists

- **[R]** One handle pool and one listing pool for the image, `CONFIG_CRUX_FILE_POOL_SIZE` (range 4 to 32, default 4) and `CONFIG_CRUX_FILE_DIR_POOL_SIZE` (range 1 to 8, default 2) (`zephyr/Kconfig:378-405`), with the same CMake cache variables on Host. So 16 handles and two listings are a configuration value today.
- **[R]** A full pool gives `CRUX_FILE_ERR_NO_RESOURCES` before any provider call (`components/file/src/file.c:96-103`, `:300-305`).
- **[R]** The build refuses a Reliance Edge handle count below both pools (`components/file/ports/zephyr/file_native.c:84-86`) and FatFs directory objects below the listing pool (`:71-72`). FatFs file objects (`CONFIG_FS_FATFS_NUM_FILES`, Zephyr default 4) are not checked.
- **[R]** The file service keeps its transfers below the pool (`components/file_service/src/file_service.c:10-12`) and takes up to `CRUX_FILE_SERVICE_DIR_MAX` listings, default 1, plus one for its stale-file rule ([Transfers](../file-service-contract.md#transfers)).
- **[R]** On Reliance Edge each thread that ever uses the file system takes one of `CONFIG_CRUX_FS_RELIANCE_EDGE_TASK_COUNT` slots for good, default 8 (`zephyr/fs/reliance_edge/Kconfig:38-40`). The listed consumers may run on more than eight threads.
- **[R]** Tests run the pools at the default and at 8 handles (`tests/file/pool_test.c`, `tests/native/file_fatfs/testcase.yaml`). No test runs 16.

The listed consumers (credential store, security-event log, diagnostic log, configuration, a runtime with 2 or 3 files, a transfer with a listing, update staging) fit 16 handles and two listings only if no consumer holds more than its share. **[I]** No figure for the peak exists, and the requirement asks for one by measurement.

### Options

| Option | Summary | Class |
| --- | --- | --- |
| **A. Keep one pool; add a usage read and a build check (recommended)** | `crux_file_pool_usage()` reports open, peak and refused counts for both pools. The FatFs build checks `CONFIG_FS_FATFS_NUM_FILES >= CRUX_FILE_POOL_SIZE`. | Industry standard: high-water marks are how Zephyr sizes pools, as with `CONFIG_INIT_STACKS` and `k_mem_slab_max_used_get` |
| B. Measure in tests only | An instrumented fake counts the peak in a `native_sim` composition. It measures the test, not the product's image. | Workaround |
| C. Per-consumer handle quotas in File | Reserved slots per class of caller. No listed requirement asks for handle classes, and the product already budgets with `_Static_assert` ([Pool size and handle budget](../file-contract.md#pool-size-and-handle-budget)). | Rejected: not needed |

### Recommendation and interface

Option A. In `crux/file.h`, Experimental:

```c
/** Use of the File pools since start. */
typedef struct {
    uint16_t files_open, files_peak; /**< Handles now, and the most at once. */
    uint16_t dirs_open, dirs_peak;   /**< Listings now, and the most at once. */
    uint32_t files_refused;          /**< Opens refused with CRUX_FILE_ERR_NO_RESOURCES by the pool. */
    uint32_t dirs_refused;           /**< Listing opens refused by the pool. */
} crux_file_pool_usage_t;

/** Experimental. Copy the counters. Thread context; takes the File lock and calls no provider. */
crux_file_result_t crux_file_pool_usage(crux_file_pool_usage_t *out);
```

The FatFs check is a `_Static_assert` next to the listing check in `file_native.c`. It allows more file objects than handles, for native files of the image, so it rejects only a configuration that would fail at run time.

Product guidance for the recipes section, not code: count the consumer threads against the Reliance Edge thread slots, and size the handle count to both pools.

### Compatibility, concurrency, power loss and cost

- **Compatibility:** additions. The build check can refuse an existing configuration whose FatFs file objects are below its pool; such an image already fails opens at run time with `NO_RESOURCES`. **[R]** `samples/` and `tests/` must be checked for one before merging.
- **Concurrency:** counters updated under the existing File lock; no new lock.
- **Power loss:** none; the counters live in RAM.
- **Cost:** **[I]** 16 bytes of RAM. Raising the pool to 16 costs per handle about 72 bytes of common state (`components/file/src/file.c:11-16`), a `fs_file_t` and a path buffer of up to 192 bytes on FatFs or 128 on Reliance Edge (`file_native.c:89-92`), plus the file system's object: one `FIL` per FatFs handle (`subsys/fs/fat_fs.c:30`), which **[U]** carries a sector buffer unless FatFs is built tiny. Measure the image before and after; the figures are source readings, not measurements.

### Tests

- **Host:** pool cases at 4, 8 and 16: open to the limit, check peak and refusals, close, check open falls and peak stays. The existing pool test pattern (`tests/file/pool_test.c`) takes the build value.
- **`native_sim`:** `tests/native/file_fatfs` and `tests/native/file_reliance` add a 16-handle variant in `testcase.yaml`; a negative build case shows the FatFs check refusing too few file objects.
- **Cross-build:** the RT1060 File links at 16 handles, for size.
- **Physical board:** the product reads the counters after a soak with all consumers active. That is the measurement the requirement asks for.

## 4. Lock hold time

### What exists

- **[R]** The File lock is taken and released around each call, and a read or write is one provider call for the caller's length (`components/file/src/file.c:142-168`). The contract says so ([Shared limits to plan for](../file-contract.md#shared-limits-to-plan-for)).
- **[R]** The file service's own lock is "never held across storage" (`components/file_service/src/file_service.c:80`); each client chunk is one File call (`:1406`, `:1457`). The stale-file rule removes files one call at a time.
- **[R]** On Zephyr the File lock and the Reliance Edge mutex are `k_mutex` (`file_native.c:88`, `:126-139`; `zephyr/fs/reliance_edge/os_mutex.c`). **[U]** A `k_mutex` raises its owner to a waiting thread's priority (Zephyr mutex documentation), so a high-priority login does not also wait behind unrelated medium-priority work.
- **[R]** The SFTP adapter's packet is 16 KiB by default and must stay at or below 32 KiB ([SFTP design](../sftp-design.md)). **[N]** The web upload's chunk size was not checked for this page.
- **[U]** A Reliance Edge sync commits the whole volume: flush, metaroot, flush ([spike](file-atomic-update-spike.md#emmc-cache-and-flush-order) and `red_fsync` comment). One sync is one call and cannot be split.

So a login or a security-event write waits for at most one in-flight File call of another thread, plus the file system's own lock for that call. The requirement holds as long as no caller passes one large buffer. **[N]** No worst-case hold time has been measured on any medium.

### Options

| Option | Summary | Class |
| --- | --- | --- |
| A. Contract sentence and adapter limits only | State the per-call rule as a guarantee and cap each transfer adapter's chunk. A consumer that writes 1 MiB in one call still holds the lock for it. | Workaround: relies on every consumer's chunk size |
| **B. Optional chunk cap inside File (recommended)** | `CONFIG_CRUX_FILE_IO_CHUNK_MAX` (0 = off, the default). When set, `crux_file_read` and `crux_file_write` split a longer request into provider calls of at most that length and release the lock between them. | Workaround, local to Crux: it bounds the hold of one shared lock. Keeping a lock's hold short is common practice, but no single source for this form was verified **[N]** |
| C. Per-consumer priority or a second lock for critical writers | A critical path that bypasses the shared lock. Breaks the pool and conflict rules, which depend on one lock. | Rejected |

### Recommendation

Option B, with option A's contract sentence.
Rules: the handle's caller already serialises use of the handle, and another thread cannot close it in between, so the slot stays live; each piece rechecks it.
Results keep today's rules: a short piece ends the call with `CRUX_FILE_PARTIAL` (write) or a short count (read); an error after progress returns the error with the accepted total, which the contract already allows ("valid accepted counts survive provider errors").
A write split this way is not one provider call, so another thread's call on another file may run between pieces; same-file conflicts stay excluded by the open rule.
Sync, close, rename and listing reads stay single calls.
The size is policy: the product sets it, and Crux sets no default.

### Compatibility, concurrency, power loss and cost

- **Compatibility:** off by default, so no behaviour changes unless a product sets it. With it on, a write may report `PARTIAL` after some pieces where one provider call would have failed whole; the contract already requires callers to handle that.
- **Concurrency:** the bound is one piece plus one sync or close of another thread. **[I]** A Reliance Edge sync remains the longest single hold; a product that needs a tighter bound syncs less often.
- **Power loss:** unchanged: no write is durable before a sync.
- **Cost:** **[I]** a loop in `transfer()`; no RAM. Throughput may fall with small pieces; measure on the board.

### Tests

- **Host:** with the fake and a cap of 4 bytes, a 10-byte write is three provider writes (`crux_file_fake_calls`), the lock is released between them (a hook on `crux_file_fake_on_write` takes the lock from another thread), and failure in the second piece reports 4 transferred. Cases with the cap off are unchanged.
- **`native_sim`:** the FatFs and Reliance Edge suites run once with a small cap.
- **Cross-build:** none beyond compiling.
- **Physical board:** the only meaningful latency figure: the wait of a login-sized read while a transfer runs, with and without the cap. Needs its own approval.

## 5. Reserve for critical writers

### What exists

- **[R]** The file service limits each area by `max_file_bytes`, `max_area_bytes` and `max_entries`, counted in RAM; these "do not reserve room on the medium" ([Capacity](../file-service-contract.md#capacity)).
- **[R]** A full medium gives `CRUX_FILE_SERVICE_ERR_NO_SPACE` with `file.storage_failed`; nothing refuses an upload while space remains.
- **[R]** Reliance Edge space reservation is compiled out (`REDCONF_API_POSIX_FRESERVE 0`, `zephyr/fs/reliance_edge/config/redconf.h:43`). **[U]** `red_freserve` reserves room for sequential writes to one file only, and "is _not_ persistent".
- **[I]** On Reliance Edge, rewriting an existing file needs free blocks until the commit, because freed data returns to free space only after a transaction point (above). So a credential store with fixed-size slots still needs free space there; on FatFs an in-place overwrite of allocated clusters does not.

### Options

| Option | Summary | Class |
| --- | --- | --- |
| **A. A per-area free-space floor in the file service, and the same check in application writers (recommended)** | The composition sets `min_volume_free_bytes` in an area. Before a write that grows a file, the service calls `crux_file_volume_info` and refuses below the floor. Update staging, an application consumer, does the same check itself. | Industry standard idea: reserved blocks for privileged writers (`f_bfree` versus `f_bavail`, ext4 reserved blocks); here as an admission check |
| B. Enforce the reserve inside File by caller class | Every write classed critical or not. File cannot know how many blocks a write will take on a copy-on-write file system, and every consumer changes. | Rejected |
| C. Separate volumes for critical data and transfers | A hard reserve by construction. The Reliance Edge profile has one volume (`REDCONF_VOLUME_COUNT 1U`, `redconf.h:100`) and the adapter one mount (`fs_reliance_edge.c:461-463`), so this is a file system configuration change, and sizes are fixed at format. | Industry standard (separate partitions), documented option of Reliance Edge (**[N]** multi-volume not read) |
| D. `red_freserve` | Reliance Edge only, not persistent, sequential only, not reachable through the Zephyr VFS. | Workaround, rejected |

### Recommendation and interface

Option A. It keeps the value in the product's composition table, as the requirement asks.
In `components/file_service/include/crux/file_service.h`, append to `crux_file_area_t`:

```c
    uint64_t min_volume_free_bytes; /**< Refuse growth below this much free space. 0: no check. */
```

- The check runs for a write that grows a file and for a managed upload's `declared_size`, after the area's own limits, outside the service lock (the lock is never held across storage).
- Below the floor the result is `CRUX_FILE_SERVICE_ERR_LIMIT` with nothing written, as for the area limits. A failed volume query refuses too (fail closed), with `file.storage_failed`.
- **[I]** The check and the write are two File calls, so other writers can use space in between. The floor must cover the critical writers' worst case plus, on Reliance Edge, copy-on-write growth, plus `CRUX_FILE_SERVICE_TRANSFER_MAX` times one chunk. The recipes section states this sizing rule; the value stays the product's.

### Compatibility, concurrency, power loss and cost

- **Compatibility:** appended field; zero, the value of every existing designated initialiser, keeps today's behaviour. The file service is Experimental. Depends on section 1.
- **Concurrency:** one extra File call per growing write; the File lock is held only for it.
- **Power loss:** none; the check writes nothing.
- **Cost:** **[I]** one volume query per growing chunk. Cheap on Reliance Edge and on FatFs after the first call; on littlefs a traversal per chunk (**[Z]** `lfs_fs_size`), so a littlefs product would check less often. Not measured.

### Tests

- **Host:** with the fake's capacity, an upload stops with `ERR_LIMIT` at the floor, a zero floor changes nothing, a failed query refuses, and the counters settle as for the other limits.
- **`native_sim`:** the services image (`tests/native/management_services`) runs one upload to the floor on FatFs over a host file.
- **Cross-build:** the management images link it.
- **Physical board:** none needed for the rule; a soak with a near-full medium belongs to the product's campaign.

## 6. Power loss and recovery

### What exists

| Concern | State | Evidence |
| --- | --- | --- |
| No format at mount, FatFs | Satisfied. Every FatFs File selection refuses `CONFIG_FS_FATFS_MOUNT_MKFS` at build | **[R]** `zephyr/Kconfig:302`, `:315`, `:339`, `:358`; `file_native.c:63-66`. **[Z]** that option is what formats in `fatfs_mount` (`subsys/fs/fat_fs.c:447-476`) |
| No format at mount, Reliance Edge | Satisfied. The mount never formats; the formatter compiles only with `CONFIG_CRUX_FS_RELIANCE_EDGE_FORMAT`, default `n`, and the eMMC sample's link check requires `red_format` absent | **[R]** `fs_reliance_edge.c:452-480`, `:557-583`; `zephyr/fs/reliance_edge/Kconfig:16-22`; [eMMC composition](../emmc-reliance-composition.md) |
| No format at mount, littlefs | Not guarded. **[Z]** Zephyr's `littlefs_mount` formats unless `FS_MOUNT_FLAG_NO_FORMAT` is set (`subsys/fs/littlefs_fs.c:965-972`). The repository's littlefs mounts set the flag | **[R]** `samples/file/basic/zephyr/src/storage_littlefs.c:26`. No product composition uses littlefs for File |
| A mount failure is reported, not repaired | Satisfied by the compositions: a failed mount stops the start sequence | **[R]** `samples/boards/nxp/mimxrt1060_evk/emmc_file/emmc_storage.c:31-34`; [microSD composition](../microsd-composition.md) |
| Cache flush before a commit | Required for Reliance Edge on an MMC disk; not for FatFs on one | **[R]** `zephyr/fs/reliance_edge/CMakeLists.txt:17-20`; [spike](file-atomic-update-spike.md#emmc-cache-and-flush-order), decision 4 |
| Last committed state | Reliance Edge: transactional, model evidence only. FatFs: not atomic (board replace cuts, W8). Sync means "the provider's flush" | [W8 record](../evidence/emmc-reliance/replay-file-w8/README.md); [File contract](../file-contract.md#public-contract) |
| Media error | Reliance Edge turns read-only until a remount, and changes give `ACCESS` | [Reliance Edge mapping](../file-contract.md#reliance-edge-mapping) |
| Recovery by an explicit, authorised action | Satisfied by construction: no Crux code formats or repairs. A format is the product's call, with the formatter compiled in only where the product allows it. The file service's kept temporary needs a host repair | [File service limits](../file-service-contract.md#limits) |

### Proposal

- **Flush guard (spike decision 4):** extend the guard to every File composition on an MMC disk, FatFs included. Class: **workaround** for an upstream gap: the pinned MMC stack's sync does not flush the eMMC cache. It is a CMake check next to the existing one; `zephyr/` is not a protected path.
- **littlefs:** no code now. **[I]** A build cannot see a run-time mount flag. The recipes section states that a littlefs composition sets `FS_MOUNT_FLAG_NO_FORMAT`, and `crux_file_replace` keeps the capability at 0 there until it runs.
- **Recovery:** no Crux recovery API. Who may format, and when, is policy. The recipes section gives the pattern the compositions already follow: report the mount failure, keep File unbound, and let an authorised application action call `fs_mkfs` in an image built with the formatter.

### Tests

- **Host:** none new.
- **`native_sim`:** the existing corrupted-media cases stay (`tests/native/file_fatfs`); a configure-time negative case shows FatFs on an MMC disk refused without the flush.
- **Cross-build:** an MMC FatFs link with and without the option.
- **Physical board:** the product's power-cut campaign on its part, with the rig `scripts/power_cut.py`. Needs approval.

## 7. What a retention log needs from File

The log itself is later work. File must provide:

| Need | Provided by | State |
| --- | --- | --- |
| Append records, sync acknowledged ones | open `READ_WRITE`, size, seek, write, sync ([Append](../file-contract.md#append)) | Exists. The product's record format skips a torn tail. |
| Oldest-first rotation | Segments with ordered names (for example a sequence number), remove the oldest, create the next | Exists. File has no modification time (decision F6), so order comes from names. A fixed set of names needs no listing. |
| Know when to rotate | `crux_file_size`, `crux_file_stat`, and free space | Free space is section 1. |
| Never starve critical writers | The log is a critical writer itself or not, by product choice | Section 5's floor and the product's checks. |
| Survive a cut | Append plus sync | FatFs kept acknowledged appends on the board (33 cuts); Reliance Edge in the model ([spike](file-atomic-update-spike.md#2-the-gap)). |

Rotation by remove and create needs no atomic replace. A log index or a retained summary that must change as a whole needs section 2, or a two-slot record.
On Reliance Edge each sync commits the whole volume, so a log that syncs every record adds a commit, two flushes, per record **[I]**; the sync rate is product policy.

## Implementation steps

Each step is one pull request with its own approval, following the repository's preference for fewer, larger changes. Each changes the [File contract](../file-contract.md) or the [File service contract](../file-service-contract.md) and its recipes in the same pull request, test first.

| Step | Contents | Depends on | Protected paths |
| --- | --- | --- | --- |
| 1. Capacity and concurrency in File | Section 1, section 3 (usage read and FatFs check), section 4 (chunk cap); private port; Linux, Zephyr and fake providers; conformance, pool and `native_sim` cases | Decisions FS1 to FS5 | Edits to the runners of the File suites (`scripts/test-storage-simulators.sh`, `scripts/test-file-*.sh`) fall under the work package rule in AGENTS.md; no suite or flag removed |
| 2. Atomic replace | Section 2; W8 through `crux_file_replace`; the flush guard of section 6 | FS6 to FS8; step 1 not required | `scripts/test-storage-emmc.sh` as above |
| 3. File service reserve | Section 5 | Step 1, FS9 | `scripts/test-file-service.sh` as above |

Each step gets an independent review by the repository's reviewer, and its checks are recorded in the pull request. None includes hardware.

## Decisions for the owner

| ID | Decision | Recommendation | Reason | Alternative |
| --- | --- | --- | --- | --- |
| FS1 | Add `crux_file_volume_info` as Experimental | **Yes** | Requirement 1 and the reserve need it; it maps one standard call on every provider | The product calls `fs_statvfs` itself: no File test, no Host provider |
| FS2 | The free figure on Linux is `f_bavail`, on Zephyr `f_bfree`; an estimate, not a reservation | **Yes** | It is what the caller can use; the upstream caveats are stated, not hidden | Report `f_bfree` everywhere: simpler, but on Linux it counts root-reserved blocks |
| FS3 | The volume query holds the File lock | **Yes** | Same rule as every File call; on FatFs the volume mutex serialises anyway | Run it outside the lock: no gain on FatFs, a new exception in the contract |
| FS4 | Add `crux_file_pool_usage` and the FatFs file-object build check | **Yes** | The requirement asks for a measured peak on the product's image; the check turns a run-time failure into a build error | Measure only in tests, which says nothing about the product image |
| FS5 | Add the optional chunk cap `CONFIG_CRUX_FILE_IO_CHUNK_MAX`, off by default | **Yes** | It enforces requirement 4 for every consumer, without changing anyone who leaves it off | Contract sentence and adapter limits only: a large single write still holds the lock |
| FS6 | Adopt the spike's option B: `crux_file_replace`, Experimental, offered only where the file system replaces atomically | **Yes, now, with the guarantee worded as model evidence** until Stage A has run | W8 has passed with a working control; consumers need the operation; refusing on FatFs keeps every promise true | Keep the decision of 4 November 2026 and wait for Stage A before any interface |
| FS7 | Capability discovery by the compile definition `CRUX_FILE_HAS_ATOMIC_REPLACE` (spike decision 3) | **Yes** | One provider per image; a campaign wants a build-time answer; the call still refuses at run time | A run-time query, which no composition with mixed providers needs |
| FS8 | Extend the MMC flush guard to every File composition on an MMC disk (spike decision 4) | **Yes** | Without it no sync on a cached eMMC is durable on any file system | Leave FatFs on MMC unguarded and document it |
| FS9 | Add `min_volume_free_bytes` to file service areas, refusing growth with `ERR_LIMIT` below it | **Yes** | Requirement 5 with the value in the product's table; zero keeps today's behaviour | Separate volumes: a hard reserve, but a file system and adapter change with fixed sizes |
| FS10 | littlefs: no build guard, a recipe rule for `FS_MOUNT_FLAG_NO_FORMAT` | **Yes** | No product composition uses littlefs for File; a build cannot see the run-time flag | A run-time check in File at bind: it would need the mount flags, which File does not own |

## Not verified

- No step here has been built or run; every cost figure is a source reading.
- The Reliance Edge source was read from the pinned project's comments on the web, not built or traced: free-space accounting before a commit, the cost of `red_statvfs`, multi-volume support and the copy-on-write cost of an overwrite are **[N]** or **[I]**.
- FatFs: whether the pinned configuration keeps FSINFO, and the first-call cost of `f_getfree` on a large card, were not checked.
- The web upload's chunk size, and the worst-case File lock hold time on any medium.
- Whether 16 handles and two listings cover the listed consumers: that is what section 3's counters are for.
- Every power-loss statement for Reliance Edge is model evidence; no eMMC device or board has run it.
- The spike's decisions 2 to 7 have no recorded owner decision that this author found.

## Sources

- POSIX.1-2024 [`rename`](https://pubs.opengroup.org/onlinepubs/9799919799/functions/rename.html) and [`fstatvfs`](https://pubs.opengroup.org/onlinepubs/9799919799/functions/fstatvfs.html).
- Linux [`fsync(2)`](https://man7.org/linux/man-pages/man2/fsync.2.html) (directory sync after a rename) and [`statvfs(3)`](https://man7.org/linux/man-pages/man3/statvfs.3.html).
- Zephyr v4.4.2 `dccb095`: `include/zephyr/fs/fs.h`, `subsys/fs/fs.c`, `subsys/fs/fat_fs.c`, `subsys/fs/littlefs_fs.c`; [mutexes and priority inheritance](https://docs.zephyrproject.org/latest/kernel/services/synchronization/mutexes.html).
- Reliance Edge v3.0 `6706984`: `include/redposix.h`, `include/redstat.h`, `posix/posix.c` (comments of `red_rename`, `red_fsync`, `red_freserve`, `red_statvfs`).
- FatFs [`f_getfree`](http://elm-chan.org/fsw/ff/doc/getfree.html).
- littlefs `lfs.h` (`lfs_fs_size`), as fetched by the workspace.
