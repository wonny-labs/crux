# The bench image: freezing the patched Zephyr copy and a capture window above 300 s

How the RT1060-EVKB management bench image records the patched Zephyr copy it is built from (blocker B2 of the [bench image plan](rt1060-bench-image-plan.md#what-blocks-the-plan-today)), and how a UART capture longer than 300 s is taken (blocker B4).

| Part | Where it is |
| --- | --- |
| The tree digest, the marker text and the patch parser | `tests/target/zephyr_tree.py` |
| The freeze (`capture` before the build, `freeze` after it) and the check of a frozen record | `tests/target/patched_zephyr.py`, wrapped by `scripts/freeze-patched-zephyr.sh` |
| The image check of the bench profile | `check_image` in `tests/target/bench_image.py` |
| The declaration that both read | the `patched_zephyr` block of `tests/zephyr/management_rt1060_compile/bench_declaration.json` |
| The capture above 300 s | the read-only `watch` mode of `tests/target/program_m5_image.py` |

Software only: host unit tests. The freeze has not run on a real build, the image check has not run on a real freeze, and nothing here ran on a board. The bench profile stays [built, not registered](board-image-profiles.md#the-bench-profile-built-not-registered).

## At a glance

| Question | Answer |
| --- | --- |
| What is frozen, and where? | Per patch: name, SHA-256 and a copy of its bytes. Per patched file: path, SHA-256, the patches that touch it and a copy of its bytes. The marker. A tree digest of the whole copy (`crux-zephyr-tree-v1`), taken **before and after** the build. All of it in one record, `patched-zephyr.json`, plus the bench manifest itself, as two extra frozen roles of the bench profile. |
| What refuses? | `check_image` of the bench profile, on frozen bytes only, refuses a missing, extra, changed or reordered patch, an unpatched tree, a patched file that differs, a tree digest that differs, a manifest block of the old single-patch shape, and a copy that was not the compiled one ([table](#what-check_image-refuses)). |
| Does it weaken the dirty-pin refusal? | **No.** The stock `zephyr` project must still be clean and at the pin, by the same two checks as before. The copy is never accepted as that project ([interaction](#interaction-with-the-dirty-pin-refusal)). |
| How is a capture above 300 s taken? | By the read-only `watch` mode, which runs no probe command, after `program` has released the port: 2,400 s for the bench, at most 3,600 s. `program` keeps its 300 s window ([part 2](#part-2-b4-a-capture-window-above-300-s)). |
| What is not verified | The first freeze on a real build, the paths of a real container build, real report rates, and every behaviour on a board ([list](#what-is-not-verified)). |

---

# Part 1: B2, the freeze of the patched Zephyr copy

## Why the copy needs its own record

- The bench image is built with `ZEPHYR_BASE` pointing at a **copy** of the pinned Zephyr tree, not at the west checkout. The copy is not a west project and has no `.git`.
- `scripts/prepare-wolf-tls-zephyr.sh` makes the copy (`git archive` of the pin without `doc`, `samples` and `tests`), applies the wolfSSL TLS socket patch with `patch --strip=1 --no-backup-if-mismatch --quiet` and writes the marker `.crux-wolf-tls`. `scripts/prepare-isn-fail-closed.py` then applies the fail-closed initial sequence number patch to the same copy and extends the marker ([details](rt1060-isn-fail-closed.md)).
- The build-time guard, `bench_guard.cmake`, checks the marker and the hash of each patched file at configuration. Nothing else in the copy is hashed at build time.
- The build provenance sees only west projects: `record-build-provenance.py` and `frozen_inputs` of `prepare_m5_network.py` require the pinned `zephyr` project to be clean and at the pin. The copy is in neither.
- The freeze is verified again on the host that drives the board before every load, where the copy does not exist. So the image check reads frozen artefacts and nothing else.

Stock Zephyr therefore stays the west project, and the copy's identity is frozen as extra artefacts, checked against the `patched_zephyr` block of the bench manifest.

## The design

### 1. The declaration and the manifest block, as lists

The block holds an ordered list of patches, a list of patched files and a declared tree digest. The declaration today (the patched-file list shortened to its first entry):

```json
"patched_zephyr": {
  "schema": 2,
  "decision": "D8",
  "marker_file": ".crux-wolf-tls",
  "zephyr_pin": "dccb09599635bdff17633fa7e9dab014b91dce90",
  "patches": [
    {"name": "zephyr-tls-4.4.1.patch", "sha256": "3d1cc0307bbeea5f000698bca5be717f73fdb8c47e90083b003336364e8fdbda"},
    {"name": "zephyr-isn-fail-closed.patch", "sha256": "831fecdbc6cfb23f47ace4dda662a95222b977977a167ef786ee02f33712de87"}
  ],
  "patched_files": [
    {"path": "include/zephyr/net/net_compat.h", "change": "modified", "sha256": "651d3e17...", "patches": ["zephyr-tls-4.4.1.patch"]},
    ...
  ],
  "tree": {"algorithm": "crux-zephyr-tree-v1", "sha256": "135c864e8c373ccedc98ff0695654c861536c2218e6388ced91098938ee93b63", "file_count": 37620}
}
```

`patched_files` lists ten files: nine from the TLS patch (seven modified, two added) and `subsys/net/ip/tcp.c` from the fail-closed patch. The declaration also carries `stock_sha256`, `requires_settings` (the Kconfig symbol a patch needs, which the guard checks) and `open_items`, which the manifest block does not mirror.

| Rule | Why |
| --- | --- |
| `patches` is **ordered**: the order is the order of application. | Two patches can touch one file, and the second may not apply to the original. A reordering is a different tree. |
| `patched_files` lists **every** file that any patch adds, modifies or deletes, with its **final** hash after all patches, and the names of the patches that touch it. A deleted file has `"sha256": null`. | One hash does not cover the patch: the TLS patch adds files and changes `subsys/random` as well. A file touched by both patches has one final hash and two names. |
| The declaration (source) holds the list and the tree digest. `bench_guard.cmake` reads the list with a loop, writes the same list into the manifest block, and keeps its configure-time check: the marker and each patched file's hash. The manifest block mirrors the declaration one to one, with the key name `pin` for `zephyr_pin`. | The build-time guard is the first fence; the freeze is the second. |
| A block without `"schema": 2`, or with any of the old single keys (`patch`, `patch_sha256`, `patched_file`, `patched_file_sha256`), is **refused** by `check_image`, not read as a one-element list. | The recorded manifests under `docs/evidence/` have the old shape and stay as they are (frozen evidence). |
| A patch that renames a file, changes a mode, or carries a binary hunk is refused by the freeze. Only text additions, modifications and deletions are understood, and a section without a `diff --git` header is refused. | The touched-file set is parsed from the patch bytes (the `diff --git a/x b/x` headers). The two declared patches have no rename, mode change or binary hunk. |

### 2. The marker for N patches

The copy has **one** marker, `.crux-wolf-tls`: `<pin> <sha256 of patch 1> <sha256 of patch 2>` followed by a newline, hashes in application order. `scripts/prepare-wolf-tls-zephyr.sh` writes `<pin> <tls patch sha256>`; `scripts/prepare-isn-fail-closed.py` requires exactly that text and rewrites it with the second hash appended. The guard and the freeze both build the expected text from the ordered list, so a copy made with only the first patch is **missing** the second, and a copy made in the other order is **reordered**.

### 3. The tree digest, `crux-zephyr-tree-v1`

Implemented in `tests/target/zephyr_tree.py`, which the freeze of the tool set picks up like every module of `tests/target/`. It follows the framing of the source snapshot in `scripts/record-build-provenance.py` and differs where a copy of a git archive needs it to.

| Question | Rule | Reason |
| --- | --- | --- |
| Which entries | Every regular file and every symlink under the copy root, found by walking the directory **without following symlinks**. Directories are not entries. **Empty directories are ignored.** | A `git archive` has no empty directories, and a patch may leave one behind. |
| Order and names | POSIX relative paths, UTF-8, **sorted by their bytes**, never by locale. A name that is not valid UTF-8 is refused. Two names equal under case folding are refused. | Determinism on any host. A case-insensitive file system (a macOS build) would otherwise merge two files silently. |
| Framing | Per entry: `path \0 kind \0 flag \0 sha256(content)` as raw digest bytes, with `kind` `file` or `symlink`; the digest of all entries is SHA-256. | The same unambiguous framing as the source snapshot (the digest is fixed length). |
| Mode | Only the owner's **executable bit**, as `exec` or `plain`. No other mode bit, no owner, no time. | `tar -x` applies the extracting user's umask, so full modes would differ between environments. The cost is stated in [the list of non-proofs](#what-this-does-not-prove). |
| Line endings | **None normalised.** The bytes are hashed as found. CRLF and LF give different digests. | A normalisation would hide a real difference. A test pins it. |
| Symlinks | The digest of the link's **target text** (`readlink`), never the target's content. A link whose target resolves outside the root, or is absolute, is refused. | The tree must be self-contained evidence. |
| Other file types | Sockets, FIFOs and devices are refused. A `.git` entry anywhere under the root is refused. | The copy is not a repository; a pointed-at checkout is a mistake. |
| Excluded | Exactly: `.DS_Store`, any `__pycache__` directory, and `*.pyc` and `*.pyo` files. The list is written into the record and into the digest's algorithm name, so a change is a new algorithm. | The build runs Zephyr's Python scripts, which can write bytecode into `ZEPHYR_BASE`. Without the exclusion the post-build digest would differ from the pre-build one for no real reason. |
| The marker | **Included** in the digest like any other file. The re-derivation writes the **expected marker**, built from the declared patch list, into the re-derived tree before hashing. The comparison of "files that differ from the stock-derived tree" excludes the marker path **by name**, and the marker is checked separately against the declared text. | It is part of what was prepared, and a stock tree has none. |
| What is hashed | The **copy**, not the stock tree. | The stock tree is checked by the existing freeze. |

The declared digest was derived by two independent derivations that agree, on one macOS host, as an interim value ([evidence](evidence/rt1060-patched-zephyr-first-freeze-20261114/README.md)). It is to be re-derived with the Linux and GNU tools in the build environment at the first real bench build. A mismatch there is a refusal, so a wrong digest fails closed. A declared digest changes only after two independent derivations agree.

### 4. What the freeze records, and where

Two calls around the build, through `scripts/freeze-patched-zephyr.sh`, which is one of the bench profile's `tool_scripts`.

| Step | Command | What it does |
| --- | --- | --- |
| 1 | `record-build-provenance.py --capture-inputs` | Captures source and west inputs. |
| 2 | `freeze-patched-zephyr.sh capture --copy DIR --out FILE` | Before the build: the marker text and the tree digest of the copy. Refuses a copy that fails any rule of the digest. |
| 3 | the build and `rom_report ram_report` | |
| 4 | `freeze-patched-zephyr.sh freeze --copy DIR --zephyr DIR --patches DIR --manifest BENCH_MANIFEST --compile-commands FILE --pre FILE --out DIR --inputs FILE --workspace DIR` | After the build, all of: **(a)** the tree digest again, equal to the pre-build one; **(b)** the touched-file set parsed from each patch equals the declared `patched_files` and the set of files that differ from the stock-derived tree **with the marker path excluded by name**; **(c)** the marker equals the text built from the declared list; **(d)** each patch's bytes (read from `--patches`, by name) hash to the declared value; **(e)** the re-derivation: the stock tree from `git archive <pin> ':!doc' ':!samples' ':!tests'` of the clean west `zephyr` checkout, the patches applied in order with the **same `patch` command line** as the preparation into a temporary directory **and then the expected marker written into it**, its digest equal to the copy's and to the declared digest, and different from the digest of the stock tree alone; **(f)** the compile-commands check ([below](#the-compiled-tree-is-the-copy)). It also checks the copy against the west projects of the inputs file. Then it copies the patch files, the patched files, the marker and a per-file listing `tree-files.tsv` into `<build>/patched-zephyr/` and writes `patched-zephyr.json`. |
| 5 | `record-build-provenance.py --build-dir ... --inputs ...` | |
| 6 | `prepare_m5_network.py prepare --profile ...`, then `verify --sha256 ...` | The two extra roles are frozen and re-hashed. |

`freeze` needs `git`, `tar` and `patch`; where one is missing it refuses, because a skipped check is not a pass.

`patched-zephyr.json` (schema 1) holds: the algorithm and the exclusion list; the marker text; the pre-build and post-build digests, file count and symlink count; the stock tree's digest and the re-derived digest; the ordered patches with their hash, size and the frozen copy's relative path; the patched files with `change`, final hash, `stock_sha256` (`null` for an added file), the patches that touch them and the frozen copy's path; the compile-commands counts; and the SHA-256 of the canonical JSON of the manifest's block, using the same canonical form as `firmware_digest` (`sort_keys`, compact separators). The build directory is inside a repository work tree, as the recorder requires, so the folder is covered by the existing freeze pattern.

**Roles.** The bench profile has two extra roles through the `ImageProfile` field `extra_roles`: `bench_manifest` (the build's `bench-manifest.json`, frozen like `.config`) and `patched_zephyr` (the record). Every file that the record names is also listed in the artefacts and re-hashed by the generic loop. The M5 and S2 profiles have no extra role.

**`check_image` signature.** `check_image(binary, elf, config, *, bench_manifest, patched_zephyr)`: the two frozen roles are required keyword arguments with no default. There is no way to skip the group: a missing artefact is a refusal, never a pass.

### The compiled tree is the copy

`compile_commands.json` is already a frozen role. The freeze requires that every translation unit of a Zephyr source path in it lies **under the copy's path as the build saw it**, that **none** lies under the stock project's path, and that at least one does. This shows **which directory the build compiled from**, not what was in it (the digests do that). The paths are compared as strings; a freeze run from a different mount point is refused, not translated. How the paths look in the real container build (a symlinked `/ws`, for example) is not seen yet; the first real freeze is the first contact.

### What `check_image` refuses

`check_image` reads the BIN, the ELF, the `.config` and the two frozen roles. It never reads the copy. Each row is one test.

| Condition | Refusal |
| --- | --- |
| The manifest has no `patched_zephyr` block, a block without `"schema": 2`, or any old single key | "legacy or missing patched Zephyr block" |
| The record is missing, has an unknown schema or algorithm, or its manifest-block hash differs from the frozen manifest's block | "record and manifest differ" |
| A declared patch is **missing** from the record, from the marker, or from the frozen artefacts | "missing patch NAME" |
| The record or the marker lists a patch the block does not declare (**extra**) | "unexpected patch NAME" |
| A patch's frozen bytes do not hash to the block's value (**changed**) | "changed patch NAME" |
| The order of the record or of the marker's hashes differs from the block's (**reordered**) | "patches out of order" |
| The marker is absent, or is not `<pin> <hashes in block order>` | "marker differs" |
| The record's pin differs from the block's or from `bench_image.PINNED['zephyr']` | "pin differs" |
| **Unpatched tree**: a patched file is missing from the record, equals its `stock_sha256`, or the record's re-derived stock digest equals the copy's digest | "tree is not patched" |
| A patched file's final hash differs from the block's, or the record has a patched file the block lacks, or the block has one the record lacks | "patched file differs" |
| **Hash mismatch**: the record's tree digest, file count or algorithm differs from the block's; the pre-build and post-build digests differ; the re-derived digest differs or is absent | "tree digest differs" |
| `sources_under_stock` is not 0, or `sources_under_copy` is 0 | "build was not from the copy" |
| A frozen artefact the record names is missing or its bytes do not hash to the record's value | "frozen artefact changed" |

The facts that `check_image` returns include the patch names, hashes and the tree digest, so the existing equality with `record['image']` also binds them into the approved manifest digest.

### Interaction with the dirty-pin refusal

| Case | Result |
| --- | --- |
| The stock `zephyr` west project is dirty or off the pin (someone patched the west checkout in place) | Refused **as before**: `workspace_inputs` raises and `frozen_inputs` requires `dirty` false and `revision == git_commit == pin`. A valid patched-Zephyr record does not change that. A test pins it for the bench profile. |
| The copy is registered as the `zephyr` project, or its path equals, contains or sits inside a west project path | Refused by the freeze before anything is recorded. |
| The copy holds a `.git` | Refused by the digest (rule above). |
| The pin differs between the west checkout, the marker and the block | Refused: three places, one value. |

The freeze adds evidence next to the existing refusal. It adds **no exception** to it.

### The tests

All host-only: no Docker, no board. Fixtures are small synthetic trees built inside the test, and the real block, pin and hashes as a committed extract. Other files refer to these tests by number.

| # | Tests | File |
| --- | --- | --- |
| T1 | **Known answer** for `crux-zephyr-tree-v1`: the digest of one tiny tree is a literal in the test, and a second, deliberately different implementation in the test file (another walk order) agrees. | `tests/build/test_zephyr_tree.py` |
| T2 | **Determinism**: creation order, readdir order, mtimes, umask-dependent mode bits and owner do not change the digest; only the executable bit does. | `tests/build/test_zephyr_tree.py` |
| T3 | **Sensitivity and refusals**: one byte; CRLF against LF; a rename; a changed symlink target; an extra or missing file; two names equal under case folding; a symlink to the outside; a FIFO; a non-UTF-8 name; a `.git`; empty directories and the excluded names ignored. | `tests/build/test_zephyr_tree.py` |
| T4 | **Marker**: for one patch the text equals the one-patch `<pin> <sha256>` byte for byte; for two it is the ordered list; the guard's expected text and the freeze's agree. | `tests/build/test_zephyr_tree.py` |
| T5 | **Patch parsing**: the touched-file set of a synthetic unified diff (added, modified, deleted); a rename, a mode change and a binary hunk are refused. | `tests/build/test_zephyr_tree.py` |
| T6 | **Freeze record**: deterministic (sorted keys), pre and post digests both recorded (the marker is inside both), and a file changed between them is refused. | `tests/build/test_patched_zephyr.py` |
| T7 | **`check_image` accepts** the one-patch and the two-patch case, and **refuses each row** of the table above, including a file touched by both patches and an added file. | `tests/build/test_bench_patched_zephyr_check.py` |
| T8 | **Re-derivation** with the real `patch` command on a synthetic stock tree and patches. Skipped, and reported as skipped, where `patch` is absent: a skip is not a pass. A wrong marker in the copy fails on the marker check and on the digest. | `tests/build/test_patched_zephyr.py` |
| T9 | **Compile commands**: all under the copy passes; one under the stock path, or none under the copy, is refused. | `tests/build/test_patched_zephyr.py` |
| T10 | **Wiring**: the bench profile freezes with the two extra roles and refuses a missing or altered record at `prepare` and at `verify`; the M5 and S2 profiles and their tests are unchanged. The dirty-pin cases of the table above. | `tests/build/test_bench_profile_wiring.py` |
| T11 | **Declaration and guard**: `bench_declaration.json`, `bench_guard.cmake` and `check_bench_guard.py` for lists, with the `ZEPHYR_BASE_BROKEN` cases extended by a missing, an extra and a reordered patch. | `tests/build/test_management_bench_declaration.py`, `tests/zephyr/management_rt1060_compile/check_bench_guard.py` |

<a id="order-of-work"></a>

### State of the freeze

The tools, the profile roles, `check_image` and the list declaration are in the repository. The tree digest and the ten-file list are declared in the interim form described above. **Open:** the first freeze on a real build in the build environment. Registering the bench profile is a separate step after that freeze and the other blockers of [the plan](rt1060-bench-image-plan.md#what-blocks-the-plan-today), and needs its own approval.

### What this does not prove

| Not proved | Why |
| --- | --- |
| That the **patches are correct or safe**, or that the `tcp_init_isn` change fixes anything | The freeze identifies bytes. Content is a review. Behaviour needs tests and, for the target, a board. |
| That the wolfSSL patch is the one its author meant, or that it is licensed for use | Only its hash is pinned. The licence status is open ([README](../patches/zephyr/README.md)). |
| That a patch generated for Zephyr 4.4.1 gives a correct tree on this pin | The re-derivation proves the copy equals "pin plus these patches applied by this `patch` command", not that the result is right. `patch` applies 3 of the 71 hunks of `sockets_tls.c` only with fuzz, so the tree depends on the patch command that built it. |
| That the copy equals "pin plus patches" on a host whose `patch` or `git archive` behaves differently | The proof holds for the tools that ran. |
| That the ELF was compiled from these bytes | The digests before and after bracket the build, and `compile_commands.json` shows the directory. A file changed and restored inside the window, or a compile from a different tree with the same paths, is not seen. There is no reproducible-build proof here; the two-build comparison of the plan is separate. |
| Mode bits other than the executable bit, owners, times, empty directories | Left out of the digest on purpose. |
| The content of anything outside the copy: other modules, the toolchain, build-local replaced sources (`patches/zephyr/README.md`) | Their freezes are other records. |
| The stock Zephyr checkout beyond its pin and a clean status | Git's own integrity is assumed. |
| Anything about hardware | Nothing here ran on a board. |

---

# Part 2: B4, a capture window above 300 s

## The limits of the program window

- The window of a profile is a whole number of seconds from 1 to `MAX_CAPTURE_SECONDS` = 300 (`tests/target/image_profile.py`), and the bench profile sets the maximum. The driver's series budget is 900 s by default.
- The window runs **after** the one load command has returned, and nothing in it starts a probe command.
- The guard check requires 90 s of validity before each probe command, and never runs while a capture is open.
- The driver takes the board lock (non-blocking `flock`) and the UART exclusively, and holds both to the end, so a second driver for the board cannot start while one runs. Each mode runs once per evidence parent.
- The judge of the bench report needs one stream: it refuses a lost report and a capture with no boot report. The idle report prints **once** until traffic returns.
- The plan needs about 2,000 s of capture (boot, the clients, a reset, a second boot), far above 300 s.

## What the load run needs

| Item | Value | Basis |
| --- | --- | --- |
| Capture time the plan needs | 120 + 1,800 + 120 + 40 = **2,080 s** with the longest client figure; "about 2,000 s" | Derived from the plan: boot up to 120 s, the clients 20 to 30 minutes, the reset and second boot 120 s, at least 40 s after the last client |
| Of which after the first boot | 1,800 + 120 + 40 = **1,960 s** | Derived |
| Window | **2,400 s** (about 15 percent above 2,080 s) | Not a measurement. The plan also gives the client time as 20 to 35 minutes. At 35 minutes the run needs 120 + 2,100 + 120 + 40 = **2,380 s**, which 2,400 s covers by only **20 s**; 2,700 s is the alternative, one constant (`BENCH_WATCH_SECONDS`). |
| Worst-case bytes at line rate, 115,200 baud 8N1 = 11,520 B/s | 330 s: 3,801,600 B. 2,430 s: **27,993,600 B**. A cap of 3,600 s plus 30 s: 41,817,600 B. | Derived. The real rate is unknown and far lower if the image prints only reports (at most one per 5 s); the bound is only for memory and disk sizing. |
| Memory at close | The raw bytes twice, plus `lines.json` rows, plus `receive.jsonl` at twice the raw size in hex | Fine at the real rate, sized for the worst case above. |
| `poll.jsonl` | At most 50 lines per second (0.02 s timeout), so at most about 120,000 lines for 2,400 s | Derived |
| Guard validity the window needs | 90 + 2,400 = 2,490 s at the one check. With `--lifetime 14400` that holds unless the guard has run longer than about 14,400 - 2,490 = 11,910 s at the check | Derived. Whether the guard's deadline counts from its start or from `READY` is not read. |

## The read-only `watch` mode

This is option X of the original design; the options not taken are in the [history record](history/rt1060-bench-freeze-and-capture-record.md).

A fourth driver mode, **`watch`**, that only reads the UART and **runs no probe command**: no identity probe, no verify, no load, no reset. It runs after `program` has finished and released the port. The full decision list and failure orders are in [board image profiles](board-image-profiles.md#the-read-only-watch-mode-blocker-b4-option-x).

| # | Decision | Value |
| --- | --- | --- |
| D1 | The mode | A separate read-only mode. Raising the program window was not chosen, because it edits the mode that writes flash and relaxes a global cap; a driver-controlled reset inside the window was not chosen, because it runs a probe command while a capture is open. |
| D2 | The window | 2,400 s for the bench (`BENCH_WATCH_SECONDS`), under its own cap `MAX_WATCH_SECONDS` = 3,600 s. `capture_seconds` of the bench and `MAX_CAPTURE_SECONDS` stay 300. |
| D3 | The guard covers the window | The one check requires 90 s plus the window. |
| D4 | No guard re-check inside the window | A re-check could only abort the capture, never protect the image. |
| D5 | The series budget of `watch` | 300 s plus the window: 2,700 s for the bench. Every other mode keeps 900 s. |
| D6 | The seam | Accepted, with a procedure (below). |
| D7 | The name | `watch` |

| Item | Content |
| --- | --- |
| Gates that **stay**, using the same code | The approval check; one use per evidence parent (its own marker, `m5-driver-watch.consumed`); the board lock and the exclusive UART selected by its USB serial; the guard, ownership inventory and adapter identity once before the capture opens; re-verification of the frozen manifests; the series budget; a stop on any failure; a new evidence directory; **no retry, no loop**. The gate sequence is one private method, `Driver._checks`, called by `run` and by `watch`, so the two cannot drift. |
| What gets **stronger** | The long window sits in a mode that has no probe command at all, so "no probe command in the window" holds by construction. There is no SWD traffic, so the target cannot be left halted by a probe step. |
| What is **lost** | (1) **No probe identity.** The J-Link identity (core, debug port, probe serial, VTref) is not read, so the tool cannot tell that the board behind the UART is the board behind the probe. The UART's USB serial and the adapter identity stay bound. Offline, the capture's own `BENCH image=` line and the judge identify the image. (2) The **unattended window** is up to 3,600 s. (3) **A seam**: the window of `program` closes, the port is released, and `watch` opens later; bytes printed in between are lost. |
| The seam procedure | The operator starts **no TCP client before `watch/operations.json` shows `capture-open`**, and the evidence for the judge is the program window's `uart-rx.bin` followed by the watch window's. Derived, not measured: with nothing driving traffic, nothing should print in the gap (the idle report is not repeated). A report cut by the close shows as torn, and a report printed in the gap as a lost one. Either is a recorded finding, not a retry. |
| The reset | Compatible with a person pressing the board's reset button inside the `watch` window. A driver-controlled reset during a window cannot be a separate mode: the lock and the port are held. |
| What `program` keeps | Its 300 s cap, its 900 s budget, its 90 s guard rule and every assertion of its tests. |
| The load run in total | `program` (window 300 s) then `watch` (window 2,400 s, series 2,700 s, guard validity at its one check of at least 2,490 s). Two evidence directories, two guard checks, two consumed markers. |

Before the first board run of `watch`, the effect of opening the port (DTR and RTS) on the target must be settled, because a reset at the open would pass the judge unless a person looks ([board image profiles](board-image-profiles.md#the-read-only-watch-mode-blocker-b4-option-x)). **The first physical use of a longer window needs its own approval, reviewed plan and the root mount guard.**

---

## What is not verified

| Item | State |
| --- | --- |
| The first freeze on a real build, in the build environment | **Not done.** The declared digest is the interim macOS derivation. |
| Whether `git archive` converts line endings or expands attributes on the build machine, and whether `patch` behaves alike on two machines | **Unknown.** `patch` needs fuzz for 3 hunks of `sockets_tls.c`. |
| Real report rates, real UART bytes per second, and how long the guard checks take | **Not measured.** The sizes above are worst-case bounds. |
| Whether the guard's deadline counts from its start or from `READY` | **Not read.** |
| The paths in `compile_commands.json` of the real container build | **Not seen.** |
| Whether the identity-only probe leaves the core running | **Unknown.** |
| Everything on hardware | Nothing ran. |

The proposal this design was drafted as, with its options, comparisons, open questions and review requirements, is in [history/rt1060-bench-freeze-and-capture-record.md](history/rt1060-bench-freeze-and-capture-record.md).
