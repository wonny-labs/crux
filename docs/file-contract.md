# Portable File contract

Status: approved for software-only development by the human M4 Architecture and API Review on 23 October 2026. Production backend/layout adoption, upstream/native Flash changes, physical operations, PR merge and Issue closure remain separately gated. The [additions for roots, stat, size, rename and listing](#additions-for-roots-stat-size-rename-and-listing) come from decisions F1, F2, F3 and F6 of [the File extension proposal, PR #206](https://github.com/wonny-labs/crux-pilot/pull/206), with F4 keeping the name rule, accepted by [the owner on 3 November 2026](https://github.com/wonny-labs/crux-pilot/pull/209#issuecomment-6616400894) for Host and `native_sim` work. Target and physical work on them stays behind M7 and needs its own approval.

Baseline: main `225cd21b5fff37c31c5dff52570e9f26179682a1`.

## File alternatives and recommendation

1. **Bounded Crux C17 File contract (recommended):** explicit transferred-byte
   counts, close-failure lifetime and backend acknowledgment; no native types or
   global errno in the consumer. Costs a small maintained adapter and tests.
2. **Qualified POSIX file subset:** reuses open/read/write/lseek/fsync/close/unlink
   and existing Zephyr facilities. Valid alternative, but needs separate qualified
   headers/types/errno and close/partial-I/O semantics; Networking's approved
   POSIX profile does not grant this profile. No current File consumer requires
   POSIX source compatibility, so this does not yet offset its qualification cost.

This recommendation is specific to #23; it is not a rule to wrap all native APIs.
The justified operations follow #15 CRUD/sync/recovery and bounded file-position
access, and later the additions below. Directory trees, atomic replace, append,
sparse files, metadata other than size, permissions, descriptor multiplexing and
asynchronous I/O are out of scope.
Seek is a proposed representative runtime-consumer operation, not a discovered
existing firmware requirement: the qualification fixture will re-read an earlier
record in a two-record file. This operation is approved for software qualification.

## Public contract

Owner: `components/file/include/crux/file.h`; usage target `crux::file`.
C17 implementation, C++17 consumption through `extern "C"`.
Only ISO C headers/public Crux declarations are consumer dependencies.

```c
typedef struct crux_file crux_file_t; /* opaque provider-owned handle */
typedef enum { CRUX_FILE_READ, CRUX_FILE_READ_WRITE,
               CRUX_FILE_CREATE_REPLACE } crux_file_mode_t;
typedef enum {
    CRUX_FILE_OK = 0, CRUX_FILE_PARTIAL = 1,
    CRUX_FILE_ERR_INVALID_ARGUMENT = -1, CRUX_FILE_ERR_INVALID_STATE = -2,
    CRUX_FILE_ERR_NOT_READY = -3, CRUX_FILE_ERR_NOT_FOUND = -4,
    CRUX_FILE_ERR_NO_SPACE = -5, CRUX_FILE_ERR_NO_RESOURCES = -6,
    CRUX_FILE_ERR_ACCESS = -7, CRUX_FILE_ERR_IO = -8,
    CRUX_FILE_ERR_NOT_SUPPORTED = -9, CRUX_FILE_ERR_OUT_OF_RANGE = -10,
    CRUX_FILE_ERR_EXISTS = -11
} crux_file_result_t;
crux_file_result_t crux_file_open(const char *name, crux_file_mode_t mode,
                                crux_file_t **out);
crux_file_result_t crux_file_read(crux_file_t *file, void *buffer,
                                size_t length, size_t *transferred);
crux_file_result_t crux_file_write(crux_file_t *file, const void *buffer,
                                 size_t length, size_t *transferred);
crux_file_result_t crux_file_seek(crux_file_t *file, uint64_t offset);
crux_file_result_t crux_file_sync(crux_file_t *file);
crux_file_result_t crux_file_close(crux_file_t **file);
crux_file_result_t crux_file_remove(const char *name);
```

No ABI stability is promised. Existing base statuses
are left unchanged; File needs distinguishable missing-file, capacity and partial
results. Error mapping must be explicit and unknown native errors map to IO.

- One composition-selected volume, with provider-private native mount/root path.
  Initial qualification profile: flat ASCII names of 1–63 characters from
  `[A-Za-z0-9_.-]`, excluding `.` and `..`; no slash or traversal. This is a
  approved initial qualification choice, not a measured existing-consumer requirement or
  filesystem/security sandbox guarantee. Name and pool bounds are provider build
  configuration with documented supported minima, not a runtime framework.
- A file open for writing (READ_WRITE or CREATE_REPLACE) excludes every other handle on the
  same name, and a writer cannot open a name that is already open: such an open returns
  INVALID_STATE with the output left null. Several READ handles may share a file. Providers
  can hold per-handle state (for example FatFs with file locking disabled), so a second handle
  next to a writer is not supported. The check follows argument validation and precedes the
  pool check and any provider call, so a conflicting open returns INVALID_STATE even when the
  pool is full, and a rejected CREATE_REPLACE never touches the file. Other conflicting
  operations on a name remain the caller's to serialise.
- READ/READ_WRITE open an existing file; CREATE_REPLACE creates or truncates for
  read/write. No hidden retry or automatic directory creation/format/mount.
- Open requires a non-null output initially null; an already non-null output is
  rejected without changing it. A failed accepted open leaves the output null.
  Provider owns a bounded pool (four handles in the initial test profile).
  Buffer ownership remains with caller; buffers are not retained after return.
- Transferred output is mandatory and set to zero before valid dispatch. Zero
  length permits a null buffer. Read returns OK with a short/zero count at EOF.
  Write returns PARTIAL for every nonnegative result below a nonzero requested
  length, including zero progress, without inventing a cause;
  an explicit no-space error maps to NO_SPACE. No successful full-write claim
  follows from a short result. Accepted partial bytes are not rolled back.
  A provider count exceeding the requested length is inconsistent: the common
  layer returns IO and reports zero transferred bytes. This is not rollback or
  proof that the buffer or storage was unchanged. Valid accepted counts still
  survive provider errors.
- Seek is absolute and checked against representable backend offsets and EOF;
  beyond-EOF/sparse extension is unsupported. It does not imply durable changes.
  Unrepresentable offsets/request lengths return OUT_OF_RANGE before dispatch.
- Sync OK acknowledges the selected provider's flush operation. Write OK alone
  is not persistence. No atomic update or general power-loss safety is promised.
- Close consumes the public handle and clears the caller's pointer even when it
  returns an error; do not retry/use aliases afterwards. A close error means no
  successful flush acknowledgment. It does not undo an earlier successful sync.
  This avoids retrying a backend object already released during failed close.
- Remove success acknowledges logical removal, not independently qualified
  directory-metadata durability. Removing an open file is unsupported.
- Synchronous/task-context only; no bounded latency or ISR suitability. Caller
  serializes access to a handle and conflicting same-file operations. No shared
  seek position/concurrent modification guarantee. Providers protect pool state;
  composition owns mount/unmount and does not change it with live handles.

## Additions for roots, stat, size, rename and listing

```c
typedef uint8_t crux_file_root_t;
enum { CRUX_FILE_ROOT_DEFAULT = 0 };
typedef struct crux_file_dir crux_file_dir_t; /* opaque; only crux_file_dir_close retires it */
typedef struct { uint64_t size; } crux_file_info_t;

crux_file_result_t crux_file_open_at(crux_file_root_t root, const char *name,
                                     crux_file_mode_t mode, crux_file_t **out);
crux_file_result_t crux_file_remove_at(crux_file_root_t root, const char *name);
crux_file_result_t crux_file_stat(crux_file_root_t root, const char *name, crux_file_info_t *out);
crux_file_result_t crux_file_size(crux_file_t *file, uint64_t *size);
crux_file_result_t crux_file_rename(crux_file_root_t root, const char *from, const char *to);
crux_file_result_t crux_file_dir_open(crux_file_root_t root, crux_file_dir_t **out);
crux_file_result_t crux_file_dir_read(crux_file_dir_t *dir, char *name, size_t capacity,
                                      crux_file_info_t *info, bool *end);
crux_file_result_t crux_file_dir_close(crux_file_dir_t **dir);
```

The rules above apply: thread context, synchronous, no ISR use, buffers borrowed for the
call, and no retry. The existing functions keep their behaviour on root 0.

- **Roots.** A root is a directory that the composition binds, once per index, with
  `crux_file_linux_bind_root` or `crux_file_zephyr_bind_root`. `crux_file_linux_bind` and
  `crux_file_zephyr_bind` bind root 0. A product reaches the Zephyr functions through the
  composition target `crux::file_zephyr` ([File root binding](file-composition-interface.md)). A path that is equal to, inside or a parent of another
  bound root returns INVALID_STATE, comparing path text only, so a FAT case alias or a Linux
  symbolic link in a composition's paths is not caught. An unbound or out-of-range root
  returns NOT_READY, after argument checks. `CRUX_FILE_ROOTS_MAX` is a build setting, default 8.
  The conflict rule compares the root and the name together. Roots separate names. They are
  not a security sandbox, as for the name rule above. A root can carry a byte limit
  ([Root byte limits](#root-byte-limits)).
- **Stat.** Regular files only: a directory or a Linux symbolic link is NOT_FOUND. The size is
  what the provider last recorded, so a file with an open writer may report an older size.
- **Size.** A handle's current size, which includes unsynced writes and leaves the position
  where it was. It reads the end of the file on the same path as seek's check. It implies no
  durability.
- **Rename.** Inside one root. It refuses an existing destination of any type. Checks run in
  this order: arguments, INVALID_STATE for a live handle on either name, NOT_FOUND for a missing
  or non-regular source, and EXISTS for an existing destination, including `from` equal to `to`.
  No other Crux File call sees a partial state, because it runs under the File lock. **It is not
  atomic across power loss**: on FAT, a cut between the two directory writes of `f_rename` can
  leave two names on one cluster chain. This comes from reading `ff.c` and has not been
  reproduced here. On Linux the provider renames with `renameat2(..., RENAME_NOREPLACE)`, so the
  kernel refuses a destination that another process creates at the last moment. When the kernel
  or the file system lacks that flag (ENOSYS or EINVAL), the provider falls back to a check and a
  replacing `renameat`, and another process can then create the destination in between and lose
  it. A container whose seccomp profile refuses `renameat2` with EPERM gets ACCESS
  from every rename, with no fallback. Zephyr has no rename that refuses an existing destination, so the Zephyr providers check the
  destination with `fs_stat` and then call `fs_rename`: a native client that bypasses File and
  creates the destination between the two has its file replaced. File callers cannot race either
  check, because both run under the File lock.
- **Listing.** A bounded pool of `CRUX_FILE_DIR_POOL_SIZE` handles, default 2 (see
  [Pool size and handle budget](#pool-size-and-handle-budget)), gives NO_RESOURCES
  when full. `crux_file_dir_read` returns entries in provider order and sets `end` at the finish,
  which then repeats without a provider call. It yields only regular files whose names pass the
  name rule, so subdirectories, Linux symbolic links and foreign files are skipped without an
  error. A skipped entry still costs a provider read under the File lock, so a directory full of
  foreign files delays other File callers. A capacity below 64 returns OUT_OF_RANGE and uses up no
  entry. After a failed read the listing can go on, and whether the failed entry comes back
  depends on the provider. An entry created or removed during a listing may be missed or repeated,
  because a listing is not a snapshot and it holds no file open.
- **Pool size.** `CRUX_FILE_POOL_SIZE` is also a public compile definition of `crux::file`, so
  that a consumer can size what it leaves free at build time.

### Root byte limits

Status: Experimental, Host and `native_sim` only. The owner approved the per-root byte limit that
reuses `CRUX_FILE_ERR_NO_SPACE` and counts whole volume units, on 27 November 2026.

A limit keeps one root's files from taking a shared volume, so that other roots, Configuration and
the credential store can still save. The composition sets it when it binds the root:

| Provider | Binding | Unit |
| --- | --- | --- |
| Zephyr (FatFs, LittleFS on a block device, Reliance Edge) | `crux_file_zephyr_bind_root_limited(root, path, max_bytes)` in `<crux/file_zephyr.h>` | `f_frsize` of `fs_statvfs()`: the FatFs cluster, the LittleFS block, the Reliance Edge block |
| Linux Host | `crux_file_linux_bind_root_limited(root, path, max_bytes)` in `file_linux.h` | `f_frsize` of `fstatvfs()` |
| `crux_file_fake` | `crux_file_fake_bind_root_limited(root, path, max_bytes, unit)` | The given unit |

- **Binding.** The rules of the unlimited binding apply, and a `max_bytes` of 0 is INVALID_ARGUMENT.
  The binding lists the root once and needs a free listing handle (NO_RESOURCES otherwise). A
  failure of the volume query or of the listing returns its result. On any error the root stays
  unbound. The limited functions bind once per index like the others; there is no way to change a
  limit later.
- **What counts.** Each file that a listing of the root reports counts its size rounded up to the
  unit, and at least one unit, so an empty file costs one unit. Files that the listing skips
  (foreign names, subdirectories, links) count nothing. Sums saturate at `UINT64_MAX` and never wrap.
- **What is refused.** A write that would take the count above `max_bytes` returns
  `CRUX_FILE_ERR_NO_SPACE` with zero transferred and reaches no provider: the whole write is
  refused, never cut to a part that fits. A write that stays inside the file's last counted unit,
  or overwrites, is accepted at the limit. A `CREATE_REPLACE` open of a new name that would pass the
  limit returns NO_SPACE before any provider call. Truncating an existing file by `CREATE_REPLACE`,
  reading and opening with `CRUX_FILE_READ` are never refused by the limit.
- **What gives space back.** A remove, and the truncation of `CREATE_REPLACE`. A rename keeps the
  count. A binding that finds the root above its limit is accepted, and then only writes that do
  not grow the count succeed until removes or truncations bring it under.
- **Order of checks.** The limit check of an open follows the conflict and pool checks. A writer's
  open on a limited root first reads the file's size with a provider stat, and a remove does the
  same, so these calls make one more provider call than on an unlimited root and return a failed
  stat's result. Readers and unlimited roots make no extra call.
- **Concurrency.** The check, the provider write and the new count happen under the File lock, so
  callers on the same root cannot pass the limit together.
- **After a failure.** The common layer counts from a handle's own size and position. After a failed
  write it reads the size again, and when that fails too, the furthest end the write could reach
  counts. After a failed read, write or seek the position is unknown until the next successful
  seek: a write then counts as if it started at the end of the file, so it can be refused although
  it would only overwrite. A failed open or remove counts what a stat finds afterwards. Each of
  these errs towards counting more.
- **Power loss and restart.** The count lives in memory only and is made again at each binding from
  what the file system reports, so after a power cut it follows what reached the medium.
- **Limits of the limit.** It is not free space: it reserves nothing on the volume, and the sum of
  the limits may exceed the volume. Size it below the free space that the composition plans for,
  with room for file system metadata, which the unit rounding approximates but does not measure.
  Writes made outside File, by another process or a native client, count only at the next binding.

The pattern is a directory-tree quota, as the XFS project quota is
([`xfs_quota(8)`](https://man7.org/linux/man-pages/man8/xfs_quota.8.html)), with Crux's own
counting and error.

The `crux_file_fake` test library is an in-memory provider behind the same private port, for
tests of code built on File. It injects faults and cuts power at a chosen mutation, under a
simple model stated in `tests/file/fake_file.h`. Results from it say nothing about FatFs or a card.

### Native mapping of the additions

The FatFs provider stores a name as `f` followed by the hex of its bytes. Listing decodes this and
skips anything else, including upper-case hex and an encoded NUL, so one file has one identity.
`fatfs_rename` in Zephyr's `subsys/fs/fat_fs.c` calls `f_unlink` on an existing destination before
`f_rename`, so the provider calls `fs_stat` on the destination first under the File lock and never
reaches that path. The Linux provider uses `renameat2` with `RENAME_NOREPLACE`, and the check
followed by `renameat` only where the kernel or file system lacks that flag (see **Rename** above).
`CONFIG_FS_FATFS_NUM_DIRS` must be at least the listing pool, and the build checks this.

`struct fs_dirent` has no modification time, which is why decision F6 leaves time out.
`native_sim` suites run these additions on FatFs, on Reliance Edge and on
[LittleFS over a block device](#littlefs-block-device-mapping), each over a RAM disk.
The LittleFS composition on the flash simulator (`CONFIG_CRUX_FILE_SIMULATOR`) compiles them and no suite calls them there.
Physical results for File do not cover them.

### Reliance Edge mapping

`CONFIG_CRUX_FILE_RELIANCE_EDGE` selects the same provider over the Reliance Edge file system of
the Zephyr VFS (`CONFIG_CRUX_FS_RELIANCE_EDGE`). Every statement of the contract above is unchanged.
What differs is the mapping:

- A name is stored as it is, with no encoding, so a file can be seen on the medium by its own name.
  A name that fails the File name rule, or a directory, is not listed.
- The destination of a rename is checked first under the File lock, as on FatFs, because Reliance
  Edge's own rename replaces an existing file.
- A full volume gives `CRUX_FILE_ERR_NO_SPACE`, including for an empty file when no inode is left
  although blocks are free.
- After a media error the file system is read-only until it is mounted again, and every change then
  gives `CRUX_FILE_ERR_ACCESS`. A close that has unsaved data on such a volume gives it too.
- A thread that uses the file system takes one of `CONFIG_CRUX_FS_RELIANCE_EDGE_TASK_COUNT` slots for
  good. A thread beyond them can still close a file or a listing, including one that another thread
  opened: the file system's task table has one spare entry for such closes, and they take it one at
  a time, so a close may wait for another thread's close. Every other call from such a thread gets
  `CRUX_FILE_ERR_NO_RESOURCES` and never reaches the file system, so it cannot take a slot from
  another thread. That includes reading a handle that another thread opened. The thread limit
  therefore leaves no handle open, and the volume can be unmounted once every handle is closed. A
  composition keeps its threads within the limit, because the other calls are refused.
- The File pools hold open files and listings together, so the file system's handle count must
  cover both, and `CONFIG_FILE_SYSTEM_MAX_FILE_NAME` must hold the longest name. The build checks
  both.

The selection works on any board that has the file system and excludes the other File selections.
The run on `native_sim` is a software result, and no physical-board result exists for it.

### LittleFS block device mapping

`CONFIG_CRUX_FILE_LITTLEFS_BLK_DEV` selects the same provider over the LittleFS file system of the Zephyr VFS on a disk (`CONFIG_FS_LITTLEFS_BLK_DEV`).
It needs an enabled `zephyr,sdmmc-disk` node with the SD card disk driver, or an enabled `zephyr,mmc-disk` node with the eMMC disk driver, on any board.
On `native_sim` a RAM disk is accepted too, for tests.
It excludes the other File selections, and the build refuses FatFs in the same image.
It mounts and formats nothing by itself: see [Mounting a LittleFS volume](#mounting-a-littlefs-volume).

Every statement of the contract above holds. What differs is the mapping:

- A name is stored as it is, with no encoding. A name that fails the File name rule, or a directory, is not listed.
- The destination of a rename is checked first under the File lock, as on FatFs, because LittleFS's own rename replaces an existing file.
- A full volume gives `CRUX_FILE_ERR_NO_SPACE`, at a write, a sync or the creation of a file.
  LittleFS reports a creation that finds no room as a name-too-long error, which Zephyr returns as an I/O error: after such an error with fewer than two free blocks, the provider returns NO_SPACE.
- **A writable handle keeps its first native error.** After a failed write, sync, read, seek or size call on a handle opened with `CRUX_FILE_READ_WRITE` or `CRUX_FILE_CREATE_REPLACE`, every later call on that handle returns the same error without a native call.
  `crux_file_close` still closes the native file and returns an error: a native close error if one comes, otherwise the kept error.
  The reason: LittleFS closes a file whose write failed without committing it, and reports success.
  Close the handle, open the file again and read its size before retrying.
  A refused argument, such as a seek past the end, does not count as a failure.
- LittleFS commits a file's data and size at a sync or a close. Data that no successful sync or close followed is lost at a reset.
- File offers no atomic replace here either. The [rename limits](#rename-limits) apply.

| Setting | Rule | Checked |
| --- | --- | --- |
| `CONFIG_FILE_SYSTEM_MAX_FILE_NAME` | Above 63, or unset. A longer native name is cut in a directory entry, and the cut name must not be a File name | At build |
| `CONFIG_FS_LITTLEFS_NUM_FILES` | At least `CONFIG_CRUX_FILE_POOL_SIZE`. Add the files that other code holds open: two for a Settings File save | The pool at build, the rest not |
| `CONFIG_FS_LITTLEFS_NUM_DIRS` | At least `CONFIG_CRUX_FILE_DIR_POOL_SIZE` | At build |
| `CONFIG_FS_LITTLEFS_CACHE_SIZE` | At least 512, one sector. The selection defaults it to 512 | At build |
| `CONFIG_CRUX_MMC_CACHE_FLUSH` | `y` on an eMMC disk, because a sync does not otherwise flush the eMMC cache | At configuration |

[Configuration](configuration-contract.md) can save on the same volume through `CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS`, in a directory that no File root covers.

Limits of LittleFS on a large disk, from its upstream design and not measured here:
its block allocator scans the file system to find free blocks, a free-space query traverses the whole file system, and one block is one sector.
Expect slow first writes after a mount on a large card; a small partition or a larger lookahead buffer shortens them.
LittleFS assumes that the disk keeps what it synced: what a card does with its own mapping at a power cut is outside that.

The `native_sim` suites use a RAM disk and an eMMC simulator, and they are software results.
No physical-board result exists for this selection; the [power-cut evidence plan](plans/littlefs-power-cut-evidence-plan.md) says what a product would need.

## Recipes for consumers

This section is guidance. It restates the contract above and adds no function, option or
promise. Where it states a limit, the source is named.

### Shared limits to plan for

Every File user in an image, the credential store and the file service included, shares these:

- One global File lock, held around each provider call, so one slow write delays every other File caller
  ([File service limits](file-service-contract.md#limits)).
- One handle pool and one listing pool, 4 handles and 2 listings by default
  ([Pool size and handle budget](#pool-size-and-handle-budget)).
- A writer excludes every other handle on its name, readers included ([Public contract](#public-contract)).
- No free-space query ([Free space](#free-space)).
- No atomic replace ([Pool size and handle budget](#pool-size-and-handle-budget), [Rename limits](#rename-limits)).

### Append

File has no append call or open mode ([the list of excluded operations](#file-alternatives-and-recommendation)).
Appending is the three existing calls in this order, on a handle that the caller alone uses:

1. `crux_file_open(name, CRUX_FILE_READ_WRITE, &file)` for an existing file. A missing file gives
   `CRUX_FILE_ERR_NOT_FOUND` (`tests/native/file_fatfs/main.c:252`). Do not reach for
   `CRUX_FILE_CREATE_REPLACE` first: it truncates an existing file. After NOT_FOUND, and only when
   no other code can create the same name meanwhile, open it with `CREATE_REPLACE`. Same-file
   conflicts are the caller's to serialise, except that a writer excludes every other handle on its
   name (INVALID_STATE for the second open).
2. `crux_file_size(file, &size)`. The size includes unsynced writes, and the call leaves the
   position where it was.
3. `crux_file_seek(file, size)`. EOF itself is a valid offset (`tests/native/file_fatfs/main.c:529`).
   A larger offset gives `CRUX_FILE_ERR_OUT_OF_RANGE` and a sparse extension is not supported
   (`components/file/ports/linux/file_linux.c:158-170`, `components/file/ports/zephyr/file_native.c:326-352`).
4. `crux_file_write(file, data, length, &transferred)`, then `crux_file_sync(file)` where the data
   must reach the medium.

Rules for the result. `transferred` is mandatory and set to zero before dispatch. A short write
returns `CRUX_FILE_PARTIAL`, and an explicit no-space error returns `CRUX_FILE_ERR_NO_SPACE`.
Accepted bytes are not rolled back, and after an error `transferred` may be lower than what
reached the file. On the Zephyr FatFs path Zephyr's `fatfs_write` discards the count of `f_write`
when it fails (`subsys/fs/fat_fs.c:225-232`, Zephyr v4.4.0), and
`components/file/ports/zephyr/file_native.c:312-315` then reports zero transferred. For errors
from other providers the count is not verified. Read the size again and seek again before
retrying, and do not retry the whole record blindly.
`crux_file_sync()` returning OK acknowledges the provider's flush and not power-loss safety, and no
atomic update is promised, so a cut during an append can leave a partial last record. A log format
that lets a reader ignore an incomplete tail is the product's own design, and this contract says
nothing more about it.

### Pool size and handle budget

- Every open file holds one slot of a pool of `CRUX_FILE_POOL_SIZE` handles. When all are in use,
  `crux_file_open` returns `CRUX_FILE_ERR_NO_RESOURCES`, before any provider call
  (`components/file/src/file.c:96-102`). A listing uses a separate pool, `CRUX_FILE_DIR_POOL_SIZE`.
- `CRUX_FILE_POOL_SIZE` and `CRUX_FILE_DIR_POOL_SIZE` are compile definitions of `crux::file`, so a product can state its
  budget at build time, for example `_Static_assert(PRODUCT_MAX_OPEN_FILES <= CRUX_FILE_POOL_SIZE,
  "...")`. Count the most handles that the product's code holds at once, and add those that other
  Crux services in the same image hold.
- A Zephyr image sets the pools with `CONFIG_CRUX_FILE_POOL_SIZE` (default 4, range 4 to 32) and
  `CONFIG_CRUX_FILE_DIR_POOL_SIZE` (default 2, range 1 to 8) in `zephyr/Kconfig`. The Host build has
  the CMake cache variables `CRUX_FILE_POOL_SIZE` and `CRUX_FILE_DIR_POOL_SIZE` with the same
  defaults and ranges (`components/file/CMakeLists.txt`). 4 is the minimum that File itself
  requires (`components/file/src/file.c:5`). One value holds for the whole image: every user of
  File shares the pool, including the Access credential store, which takes one handle while it
  saves or reads a record, and the file service. The file system must hold the handles as well:
  on FatFs `CONFIG_FS_FATFS_NUM_FILES` must cover the handle pool and any native files of the
  image, and `CONFIG_FS_FATFS_NUM_DIRS` the listing pool (the build checks the listings only). With
  Reliance Edge, `CONFIG_CRUX_FS_RELIANCE_EDGE_HANDLE_COUNT` must cover both pools, and the build
  checks it. On `native_sim`, the FatFs suite runs with a pool of 8 as well as the default
  (`tests/native/file_fatfs/testcase.yaml`).
- **The reserved handle is a known limit, not a guarantee.** The file service accepts at most
  `CRUX_FILE_SERVICE_TRANSFER_MAX` transfers (default 3) and the build fails unless that is below
  `CRUX_FILE_POOL_SIZE`, so one handle stays free for the credential store and the project. Project
  code can still take that handle ([File service](file-service-contract.md#transfers)).
- **Replace.** File has no replace call, and `rename` refuses an existing destination. A
  replace built from File calls is: write the new content under another name, close every handle on
  both names (removing an open file is unsupported, and `rename` returns INVALID_STATE for a live
  handle), remove the old name, then rename. A power cut between the remove and the rename leaves
  the temporary file and no target, and File does not recover it. The file service's upload commit
  is the one place with a recovery sequence ([Commit and power
  loss](file-service-contract.md#commit-and-power-loss)). In it, the open of the target at the
  commit step needs a free handle. The service reports a full pool as `ERR_NO_RESOURCES`, which
  changes nothing and keeps the upload handle, so the caller can retry or close. Which commit step
  returns it when clients hold the whole pool is not verified.
- **Copy.** File has no copy call. A copy built from File calls holds a `READ` handle on the source
  and a `CREATE_REPLACE` handle on the destination at once, so it needs two free slots. With the
  default pool of 4 and 3 service transfers open, one slot is free and the destination open returns
  NO_RESOURCES. `CREATE_REPLACE` truncates an existing destination when it opens, so a copy over an
  existing name loses the old content at once and is not a safe replace.

### Mounting a LittleFS volume

Zephyr's `littlefs` mount **formats a volume that it cannot mount**, unless the mount has `FS_MOUNT_FLAG_NO_FORMAT` (a devicetree `zephyr,fstab` entry: the `no-format` property).
A corrupt card, a card of another file system or a blank card would otherwise be erased at boot.

1. Mount with both flags, and never call `fs_mkfs` on the path of a failed mount.
2. After a failed mount, report it and leave File unbound.
3. Format only as a separate action that an authorised person starts, never as part of the start sequence.
4. Create the directories when the volume is provisioned, not at each boot. Check that they exist before binding.

```c
FS_LITTLEFS_DECLARE_DEFAULT_CONFIG(product_littlefs);

static struct fs_mount_t mount = {
    .type = FS_LITTLEFS,
    .mnt_point = "/lfs",
    .fs_data = &product_littlefs,
    .storage_dev = (void *)"SD", /* the disk-name of the devicetree node */
    .flags = FS_MOUNT_FLAG_USE_DISK_ACCESS | FS_MOUNT_FLAG_NO_FORMAT,
};

int product_storage_start(void)
{
    struct fs_dirent entry;
    int result = fs_mount(&mount);

    if (result != 0) {
        return result; /* report it: no format here */
    }
    if (fs_stat("/lfs/files", &entry) != 0 || entry.type != FS_DIR_ENTRY_DIR ||
        crux_file_zephyr_bind("/lfs/files") != CRUX_FILE_OK) {
        (void)fs_unmount(&mount);
        return -ENOENT;
    }
    return 0;
}
```

`tests/native/file_littlefs_blk` shows that the mount with the flag leaves a blank and a damaged disk as they are, and that the same mount without it formats the damaged one.
`samples/file/basic` formats after a failed mount because its partition is simulated; do not copy that into a product.

### Rename limits

`crux_file_rename(root, from, to)` works inside one root. Checks run in this order: arguments,
INVALID_STATE for a live handle on either name, NOT_FOUND for a missing or non-regular source, and
`CRUX_FILE_ERR_EXISTS` for an existing destination of any type, including `from` equal to `to`
(`tests/file/conformance.c:150-205`). It is **not atomic across power loss**: on FAT a cut between
the two directory writes can leave two names on one cluster chain. That comes from reading `ff.c`
and has not been reproduced here. Native clients that bypass File can race the destination check.
See [Additions](#additions-for-roots-stat-size-rename-and-listing).

### Free space

**Not provided.** There is no call that reports the free or total space of a volume.
`crux_file_info_t` holds only a size, and `crux_file_stat` and `crux_file_size` report one file.
A product learns that a volume is full from `CRUX_FILE_ERR_NO_SPACE` on a write or a create, and on
Reliance Edge also for an empty file when no inode is left ([Reliance Edge mapping](#reliance-edge-mapping)).
The FatFs and LittleFS block-device providers both call `fs_statvfs` internally, only to map a
refused create on a full volume to NO_SPACE, and neither returns the value
(`crux_file_impl_open` in `components/file/ports/zephyr/file_native.c`).
The file service's area counters are limits that it enforces, not free space on the medium
([File service](file-service-contract.md#capacity)), and so is a [root byte limit](#root-byte-limits). A public volume-information call would be a
new Experimental function and an owner decision under [AGENTS.md](../AGENTS.md), and this section
promises none. A product that needs the figure now can call Zephyr's `fs_statvfs()` on its mount
point in its own adapter, outside File's lock and tests. That call is not verified with a File
volume in use.

## Verified native mapping and limits

Pinned Zephyr is `684c9e8f32e4373a21098559f748f06915f950c9`.
`include/zephyr/fs/fs.h` and `subsys/fs/fs.c` supply open/read/write/seek/sync/
close/unlink, with native object/errno translation kept private. Absolute seek
needs checked offset conversion and size inspection; it must not silently narrow.

Important source finding: `fs_close()` retains `mp` after backend error
(`subsys/fs/fs.c:206–226`), but `littlefs_close()` releases its file data even on
an error (`subsys/fs/littlefs_fs.c:330–342`). Therefore failed-close retry is not
a safe generic contract. The adapter must retire/reset its own slot after close,
preserve the error, and test that path without dereferencing freed backend state.
This is source evidence, not a reproduced runtime defect or physical test.

A second pinned mapping hazard exists in `fs_open(...FS_O_TRUNC)`: after backend
open succeeds, a truncate failure clears `mp` without calling backend close
(`subsys/fs/fs.c:182–200`). A subsequent `fs_close()` is then a no-op. The future
adapter must not use that combined path: open without TRUNC, call `fs_truncate(0)`
while the handle is valid, then close exactly once on truncation failure. Preserve
the primary failure and retain any cleanup failure in provider diagnostics/tests.
Failed creation/truncation is not rollback: a file may have been created/changed.
Controlled failure tests must prove cleanup and error behavior before adopting
the mapping. This requires no upstream or production Flash-driver change.

#23 implements a Linux Host provider and a private deterministic fault provider.
The [software validation and handoff](file-validation.md) specify the Zephyr mapping.
A future change may compile a provider against a controlled
RAM-backed software fixture; this implementation does not enable native QSPI/LittleFS writes.
Media/partition/format/startup policy remains #14/#15 composition work.


## Result convention

The capability-specific result enum is a separate domain from `crux_status_t`.
As with the base convention, zero denotes full success and negative values are
errors; positive File partial/Configuration default outcomes require explicit
handling. Compare named values from the declaring API, never cast or compare
against base enum values, and do not treat every nonzero value as an error.
Any necessary composition-level translation uses an explicit switch; no generic
conversion service or change to base status values is introduced.

## Migration notes

### Board-neutral names of the FatFs selections

The Zephyr selections of the FatFs provider on a real medium were renamed after what they select, and their dependencies are generic devicetree and disk facts instead of the RT1062 SoC and the RT1060-EVK board and revision.

| Old Kconfig symbol | Replacement | The replacement needs |
| --- | --- | --- |
| `CONFIG_CRUX_FILE_FATFS_RT1060` | `CONFIG_CRUX_FILE_FATFS_SDMMC` | An enabled `zephyr,sdmmc-disk` node and `CONFIG_DISK_DRIVER_SDMMC` |
| `CONFIG_CRUX_FILE_FATFS_RT1060_RAM_DISK` | `CONFIG_CRUX_FILE_FATFS_RAM_DISK` | An enabled `zephyr,ram-disk` node and `CONFIG_DISK_DRIVER_RAM`, with no SD card driver, SD host driver or flash disk |
| `CONFIG_CRUX_FILE_FATFS_RT1060_COMPILE_CHECK` | `CONFIG_CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK` | As `CONFIG_CRUX_FILE_FATFS_SDMMC` |

Each old symbol still works: it has the dependencies of its replacement, selects it, and selects Zephyr's `DEPRECATED` symbol, so the build prints `Deprecated symbol ... is enabled`.
The old symbols stay through the first tagged Crux release that carries them and will be removed in the tagged release after it, which gives one tagged release of notice ([ADR-0001](decisions/0001-application-boundary-and-api-stability.md#43-deprecation-window)).
To move, replace the old name with the new one in `prj.conf` and in any CMake or C check of the image.
An image on another board than the RT1060-EVKB now gets the selection whenever its devicetree has the disk; the RT1060-EVKB images build as before.
