# Tree digest of the patched Zephyr copy, derived on macOS, 2026-11-14 (interim, freeze design item 4)

Order of work 4 of [the freeze design](../../rt1060-bench-freeze-and-capture-design.md): the tree digest of the build-local Zephyr copy with both patches, declared after two independent derivations agree. Software only. **No build of the bench image, no Linux container, no board.**

**This is not the "first real freeze on a real build" that the design asks for.** The design says the digest is derived on the build environment (the Linux Dev Container) and that the second derivation is by hand. All four runs here ran on one macOS host, with Apple's `git`, `tar` and `patch` and an APFS file system, the variables the design names as unknown. The declaration is therefore an **interim** one, and the freeze on a real build in the container remains to do. It is safe to declare meanwhile because the freeze and the image check refuse a tree whose digest differs. Whether the interim declaration is accepted, or the container run comes first, is an owner decision, requested in the pull request. Item 5 of the design (registering the bench profile) is not part of this record.

**What this records, and what it does not.** Only facts about the pinned wolfSSL TLS patch: the `wolfSSL/osp` revision, the patch's SHA-256, the paths it touches and what it does to each (added or modified), the SHA-256 of each result file, the tree digest and the counts. **Not** the patch text and no text derived from it or from wolfSSL source. The patch was downloaded by `scripts/prepare-wolf-tls-zephyr.sh` into a copy in a scratch folder outside every repository of the project, and that copy and the download were deleted afterwards. This record decides nothing about the licence of the patch, of wolfSSL, wolfSSH or wolfPSA, or of a binary built with them. Nothing is distributed and nothing is registered. The owner's approval basis is quoted in the pull request.

The machine-readable record is [`derivation.json`](derivation.json). A test (`tests/build/test_management_bench_declaration.py`) keeps it equal to `tests/zephyr/management_rt1060_compile/bench_declaration.json`.

## Result

| Item | Value |
| --- | --- |
| Zephyr | v4.4.2, `dccb09599635bdff17633fa7e9dab014b91dce90` |
| TLS patch | `zephyr-tls-4.4.1.patch`, `wolfSSL/osp` `8c32b060ac6017b1291a6da0875a48637bfb682d`, SHA-256 `3d1cc0307bbeea5f000698bca5be717f73fdb8c47e90083b003336364e8fdbda`, 190,586 bytes |
| ISN patch | `zephyr-isn-fail-closed.patch`, SHA-256 `831fecdbc6cfb23f47ace4dda662a95222b977977a167ef786ee02f33712de87` |
| Marker `.crux-wolf-tls` | `<pin> <tls sha256> <isn sha256>`, 171 bytes, one line |
| Tree digest `crux-zephyr-tree-v1` | `135c864e8c373ccedc98ff0695654c861536c2218e6388ced91098938ee93b63` |
| File count | 37,620 files, 0 symlinks (the stock tree of the archive has 37,617: two added files and the marker) |
| Stock tree digest | `3e9f2129642693c7b7f029b28c3b6c1671f7630363a0a7af41ef64ecda6745bb` |

The copy is the `git archive` of the pin without `doc`, `samples` and `tests`, as `scripts/prepare-wolf-tls-zephyr.sh` makes it.

## The patched files

Ten files, from the parsers of both sides (below). No rename, copy, mode change, binary hunk or deletion. The two added files have mode 100644.

| Path | Change | Patch | SHA-256 of the result |
| --- | --- | --- | --- |
| `include/zephyr/net/net_compat.h` | modified | TLS | `651d3e17e767c604c087a80ebc9fb5af9c8bf8fdfa3114d764113a73e3fdb6d8` |
| `include/zephyr/net/socket.h` | modified | TLS | `48634a50dd7ff7736154f71dd981b5d028cbe679e6aef6bceca74ab162226ccd` |
| `include/zephyr/net/tls_verify.h` | added | TLS | `6becb48cfde92a6aac85454c9da0c0ef7e62ccb339db29a5f74253839acb14a3` |
| `subsys/net/ip/tcp.c` | modified | ISN | `94642fe2257f80dd91b9e84d8c29459ca84144cb56af0cdfdd58039473e0e0cf` |
| `subsys/net/lib/sockets/CMakeLists.txt` | modified | TLS | `998d677693f2fb59974a09b3ef000fb0a14d5dfc9ea0d718edb092b57803aebf` |
| `subsys/net/lib/sockets/Kconfig` | modified | TLS | `dbbdccc00aa2b5de59d5e5b60ba3312de26ea31620a622ee2ce078ca0780585e` |
| `subsys/net/lib/sockets/sockets_tls.c` | modified | TLS | `106acdbb725fc72e4eca242125fd02283b0cd67403b205c7c231b2db6328552a` |
| `subsys/random/CMakeLists.txt` | modified | TLS | `0a9d9a2d371a482d9f3f8a1b475bc03192d2c7815f92c89682d019f1c54bba86` |
| `subsys/random/Kconfig` | modified | TLS | `0a07662a8daae3c88f9f8a1ec6d1708719b895d2448196429dbf43744599afef` |
| `subsys/random/random_wolfssl.c` | added | TLS | `f3a633e54edbe616b9d53ee6c1c3d7a7706f48a6a2e42c5707950ce5f2749b1e` |

The stock hashes of the eight modified files are in `derivation.json`. The TLS patch has nine files, `subsys/net/ip/tcp.c` is the ISN patch's only one, and the two patches share no file.

## Two independent derivations

Four runs, two methods. All four give the digest and file count above, and the per-file hashes of the ten files, the set of executable files and the marker are equal between the two trees.

| Run | Tree built by | Digest by |
| --- | --- | --- |
| A1 | `scripts/prepare-wolf-tls-zephyr.sh`, then `scripts/prepare-isn-fail-closed.py` (`patch(1)`, then `git apply --no-index`) | `zephyr_tree.tree_digest()` of the repository |
| A2 | `patched_zephyr.rederive()`: `git archive` of the stock pin, `patch --strip=1 --no-backup-if-mismatch --quiet` for both patches in order, the expected marker | `zephyr_tree.tree_digest()` |
| B1 | the tree of A1 | [`independent_tree_digest.py`](independent_tree_digest.py), written from the design text and importing nothing from the repository: `os.walk` over byte paths, one list sorted by raw bytes, fixed blocks |
| B2 | a **new** tree: `git archive` of the pin, `git apply --no-index -C1` for the TLS patch and `git apply --no-index` for the ISN patch, the marker written with `printf` | the same independent script |

For the TLS patch, B2 differs from A in the patch engine (`git apply -C1` against `patch(1)`); for the ISN patch both used `git apply`. B2 and B1 differ from A in the code that hashes. B1 differs from A1 only in the code that hashes. A and B share the host, Apple's `git archive` and `tar`, the file system, the pin, the exclusion list, the patch bytes and the algorithm as written in the design.

Commands (paths shortened; `$S` is a scratch folder outside every repository, `$R` this repository):

```bash
git init $S/ws/zephyr && git -C $S/ws/zephyr fetch --depth 1 https://github.com/zephyrproject-rtos/zephyr dccb09599635bdff17633fa7e9dab014b91dce90 && git -C $S/ws/zephyr checkout FETCH_HEAD
CRUX_WORKSPACE=$S/ws $R/scripts/prepare-wolf-tls-zephyr.sh $S/copy          # A1, downloads the patch
python3 -I $R/scripts/prepare-isn-fail-closed.py $S/copy                     # A1
python3 -I -c "import zephyr_tree; print(zephyr_tree.tree_digest('$S/copy')['sha256'])"   # A1 (sys.path = tests/target)
python3 -I -c "import patched_zephyr as p; ..."                              # A2: p.rederive(zephyr, pin, patches, '.crux-wolf-tls', scratch)
python3 -I independent_tree_digest.py $S/copy <the ten paths>                # B1
git -C $S/ws/zephyr archive $PIN ':!doc' ':!samples' ':!tests' | tar -x -C $S/hand        # B2
(cd $S/hand && git apply --no-index -C1 <tls patch> && git apply --no-index $R/patches/zephyr/zephyr-isn-fail-closed.patch && printf '%s %s %s\n' $PIN $TLS_SHA $ISN_SHA > .crux-wolf-tls)
python3 -I independent_tree_digest.py $S/hand <the ten paths>                # B2
```

The tool dry run: `capture`, `freeze` and `check_record` of `tests/target/patched_zephyr.py` ran on the real copy against the real declaration block, with the real patch bytes in a scratch patch folder, a synthetic inputs file and a **synthetic** one-entry `compile_commands.json`. All accepted: the copy digest, the re-derived digest and the declared one are equal. Because no build ran, that run proves nothing about the compile-commands check.

## What the real patch showed

- **Fuzz.** `patch(1)` applies the TLS patch to v4.4.2 only with fuzz: 3 of the 71 hunks of `sockets_tls.c` are rejected with `--fuzz=0` and 2 with `--fuzz=1`, and `--quiet` hides the fuzz. `git apply` refuses the patch with its default context and takes it with `-C1` (three fragments). Both give the same result hash. Every other file applies with exact context. So the tree depends on the patch command that built it, which is why the freeze re-derives with the same `patch` command line as the preparation script. The earlier `git apply --3way` note in [`patches/zephyr/README.md`](../../../patches/zephyr/README.md) is consistent with this.
- **The one-marker flow runs.** The TLS script, then the ISN script, give `.crux-wolf-tls` as `<pin> <tls sha256> <isn sha256>`, and the copy has no other `.crux-*` file.
- **One unverified item closed, for Apple's `patch` only:** `patch --strip=1` (Apple `patch` 2.0-12u11) and `git apply --no-index` do give the same `tcp.c` (the ISN patch's file, hash `94642fe2…`): A1 applies it with `git apply`, A2 with `patch`.

## Environment

macOS 15.7.4 (24G517) on arm64, **not** the Linux Dev Container (no container was started): `patch` 2.0-12u11-Apple, git 2.39.5 (Apple Git-154), bsdtar 3.5.3, curl 8.7.1, Python 3.9.6 run with `-I`.

`/sbin/sha256sum` on macOS has no `--check`, which `scripts/prepare-wolf-tls-zephyr.sh` uses. A shim on `PATH` in the scratch folder supplied `sha256sum --check [--quiet]` on top of `shasum -a 256`, and was tested to fail on a mismatch. The protected script was not changed. With that script the check of the pinned hash of the patch and of `sockets_tls.c` ran for real.

## What was not done

- No build, no freeze of a build, no run of the image check on a real freeze, no board.
- No Linux container and no GNU patch. The digest is the one of a copy made by Apple's `patch`. The `sockets_tls.c` result hash equals the one that the preparation script has carried since #263 and that the bench manifests of earlier container builds record (for example [this one](../rt1060-wolf-entropy-c5/bench/bench-manifest.json)); those files do not say which `patch` made them. So there is agreement for that one file and none shown for the other eight. If GNU patch yields other bytes, the freeze refuses (the digest is the fail-closed element), and the declaration must be revisited then.
- The licence of the patch and of binaries built with wolfSSL, wolfSSH or wolfPSA is not decided here.
- The bench profile is not registered, and `scripts/freeze-patched-zephyr.sh` and the other protected files are unchanged.
- The scratch folder (the Zephyr checkout, the copy, the downloaded patch, the dry-run output, the shim and the second tree) was deleted afterwards. Free space on /System/Volumes/Data was 14 GiB at the first check, 12 GiB after the Zephyr fetch, 14 GiB just before the deletion and 15 GiB after it (other sessions use the same volume, so the figures also move for other reasons).
