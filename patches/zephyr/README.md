# Zephyr patches

Crux carries a few corrections to Zephyr at the pinned revision `41d10b59730406bbab4ca9f1fbbe9e96aafb4966` (v4.5.0), without a dependency upgrade. The wolfSSL TLS socket patch and the ISN patch belong to the wolfSSL bench line, which stays on v4.4.2 (`dccb09599635`) for now. The MDIO, Mbed TLS entropy, eMMC and HTTP patches each apply to one file: a prepare script checks the original file's hash, applies the patch in a temporary directory and checks the result's hash, and CMake replaces exactly one source in the existing library with that build-local copy. A generated `.json` records the original, patch and output hashes. Source drift, a missing or ambiguous library member, or output inside the dependency tree fails configuration; there is no dirty-dependency exception. The wolfSSL and ISN patches are instead applied by their scripts to a build-local copy of the whole tree, checked through the marker `.crux-wolf-tls` and the bench guard. No patch edits the Zephyr checkout, and every original file keeps its copyright and Apache-2.0 notice in the copy. None is a platform API, a driver replacement or a qualification claim, and each is removed when the correction is available upstream at the pinned Zephyr.

| Patch | Zephyr file | Option | Prepare script | Test | Record |
| --- | --- | --- | --- | --- | --- |
| `nxp-enet-mdio-completion.patch` | `drivers/ethernet/mdio/mdio_nxp_enet.c` | `CONFIG_CRUX_M3_MDIO_COMPLETION_FIX` | `scripts/prepare-nxp-mdio.py` | `tests/native/mdio_completion/test_driver.py` | [Controller validation](../../docs/m3-validation.md) |
| wolfSSL TLS socket backend (not stored here) | `subsys/net/lib/sockets/sockets_tls.c` and eight more | build-local copy | `scripts/prepare-wolf-tls-zephyr.sh` | [TLS probe](../../docs/native-management-composition.md#tls-probe) | [Dependency review](../../docs/dependency-review-wolf-pins.md) |
| `mbedtls-entropy-fail-closed.patch` | `modules/mbedtls/zephyr_entropy.c` | image calls `crux_mbedtls_fail_closed_entropy()` (entropy driver route) | `scripts/prepare-mbedtls-entropy.py` | `tests/psa_entropy` | [PSA qualification](../../docs/psa-crypto-qualification.md#entropy-failure) |
| `mmc-cache-flush.patch` | `subsys/sd/mmc.c` | `CONFIG_CRUX_MMC_CACHE_FLUSH` | `scripts/prepare-mmc-cache-flush.py` | `tests/native/emmc_stack/test_prepare.py` | [eMMC composition](../../docs/emmc-reliance-composition.md) |
| `zephyr-isn-fail-closed.patch` | `subsys/net/ip/tcp.c` | with the wolfSSL copy | `scripts/prepare-isn-fail-closed.py` | `tests/native/isn_fail_closed/test_prepare.py` | [ISN record](../../docs/rt1060-isn-fail-closed.md) |
| `settings-file-error.patch`, `settings-store-error.patch` | `subsys/settings/src/settings_file.c`, `settings_store.c` | `CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE` or `_ANY_FS` | `zephyr/prepare_settings_file.py` | `tests/native/configuration_settings_file/test_prepare.py` | [Settings File backend](#settings-file-backend-faults) |
| `http-header-deadline.patch` | `subsys/net/lib/http/http_server_core.c` | `CONFIG_CRUX_WEB` (deadline `CONFIG_CRUX_WEB_HEADER_DEADLINE_MS`) | `components/web/ports/zephyr/prepare_header_deadline.py` | `tests/native/web_http/test_prepare_header_deadline.py` | [Web contract](../../docs/web-contract.md) |

## Reference-controller native MDIO correction

At v4.4.2 the MDIO wait discarded the semaphore timeout result and could return a successful zero read without completion, and an old token gave an early successful read. These are source-level counterexamples; they do not establish the cause of a physical failure. Zephyr v4.5.0 returns `-ETIMEDOUT` on a semaphore timeout and resets the semaphore before each command, so the patch is smaller there: the upstream reset is kept, inside the patch's interrupt lock. Upstream still busy-waits the whole timeout and reports success during initial polling, and a late completion still makes the bus reusable.

The correction requires a real completion indication during initial polling, clears the old event and semaphore before a new command with the single-core IRQ handler excluded, returns `-ETIMEDOUT` when completion is not received (preserving the caller's output), rejects later transactions with `-EIO` until a fresh boot, and rejects ISR callers before taking the sleeping mutex. A late IRQ, ordinary callback or module-reset notification cannot silently make an uncertain operation reusable. No timeout is increased. Native PHY errors do not necessarily change cached carrier state, so the patch alone does not establish readiness or link-loss acceptance; ordinary profiles keep their original driver selection.

`CONFIG_CRUX_M3_MDIO_COMPLETION_FIX` defaults off and requires the native NXP ENET MDIO driver (`CONFIG_MDIO_NXP_ENET`), no SMP and no zero-latency interrupts. Append `tests/board_images/integration_probe/mdio_completion_fix.conf` to the network configuration for a candidate build. Run the test in the Linux development container with the pinned workspace initialised. It compiles the generated function bodies against explicitly modelled IRQ, MMIO (including write-one-to-clear) and semaphore schedules, and rejects drift, output in the dependency tree and ambiguous CMake replacement. It does not reproduce electrical timing, the physical IRQ seed, scheduling or worst-case execution; target compilation and physical evidence remain separate gates.

`CONFIG_CRUX_M3_MDIO_FAILURE_TRACE` (configuration `mdio_failure_trace.conf`, PHY diagnostic composition only) retains the first wait failure in CPU-accessed BSS for the sample to report. It adds observation only: a private getter (not a public Crux interface) copies the record under IRQ protection, no extra MDIO operation or register write is made, a later error never overwrites the first, ordinary images do not compile it, and the generated unit uses scoped `-Wall -Wextra -Werror`. Cycle and millisecond fields are 32-bit and wrap, fields are sequential rather than a snapshot, and the observer is valid on the POST_KERNEL path only. The private `deferred_output.conf` is a separate opt-in software evaluation of deferred console output through one native UART backend: a 4096-byte buffer and a 2048-byte logger stack at priority 14, not adopted for Ethernet or integrated qualification.

## wolfSSL TLS socket backend

The secure management work uses a wolfSSL backend behind the Zephyr TLS socket API. Its patch is not stored in this repository, and Crux refers to it by revision until its licence terms are confirmed ([dependency review](../../docs/dependency-review-wolf-pins.md), [ADR-0006](../../docs/decisions/0006-cryptographic-dependency-policy.md)).

| Input | Value |
| --- | --- |
| Repository | `wolfSSL/osp`, revision `8c32b060ac6017b1291a6da0875a48637bfb682d` |
| Core patch | `zephyr/4.4/zephyr-tls-4.4.1.patch`, SHA-256 `3d1cc0307bbeea5f000698bca5be717f73fdb8c47e90083b003336364e8fdbda` |
| Decoupling patch | `zephyr/4.4/zephyr-tls-4.4.1-mbedtls-decoupling.patch`, SHA-256 `b581396c70e7ecaf4b09ae66875b8cc5d29e428fd74c9938d3249d426b185c05` |

The core patch touches nine files (seven modified, two added); the paths and the hashes of the results are in `tests/zephyr/management_rt1060_compile/bench_declaration.json`. Upstream generated it for Zephyr 4.4.1. On v4.4.2, `git apply --check` fails in `sockets_tls.c` and `git apply --3way` merges it with no conflict.

**Zephyr v4.5.0.** `wolfSSL/osp` has no patch for Zephyr 4.5 (its `zephyr` folder holds 3.7, 4.3 and 4.4 only). The 4.4 patch does not apply to v4.5.0: a three-way merge with `diff3` against v4.4.2 leaves conflicts in seven of the nine files (`sockets_tls.c` 20, sockets `Kconfig` 5, random `Kconfig` 2, and one each in `net_compat.h`, `socket.h` and the two `CMakeLists.txt`). Crux does not store a patch of its own here while the licence question of Issue #185 is open, so the wolfSSL line keeps its own Zephyr v4.4.2 revision in `scripts/test-web.sh`, `scripts/test-ssh-wolf-settings.sh` and the bench image pins of `tests/target/bench_image.py`. Those runs need a workspace that has that revision, and they are not part of any default workflow. The line moves when a 4.5 patch exists. How a product composition applies it without editing the Zephyr checkout is open (Issue #185).

`scripts/prepare-wolf-tls-zephyr.sh` makes the patched copy of the tree for the other wolfSSL runs, and the patch runs on `native_sim` only. These runs take the Zephyr that `west.yml` pins. On v4.5.0 the TLS socket patch does not apply (and, for the ISN test, `tcp.c` is not the declared one), so they always fail, closed:

- `scripts/test-native-composition.sh`: `wolf`, `e2e-wolf` and the default `all`
- `scripts/test-ssh-integrated.sh`: `build` and the default `all`
- `scripts/test-tls-offload-probe.sh`: `wolf` and the default `all`
- `scripts/test-isn-fail-closed.sh`: `patched` and the default `all`

No default workflow runs these modes: `scripts/ci/checks.toml` runs the `host`, `mbed` and `target-mbed` modes of those scripts.

The wolfSSL, wolfSSH and wolfPSA projects are fetched only when a workspace enables the `crux-secure-management` group. wolfSSL and wolfSSH are offered under GPL-3.0-or-later or a commercial licence, and wolfPSA's source states GPL-3.0-or-later only; binaries built with these stacks are subject to those terms when distributed. The `mbedtls` and `tf-psa-crypto` projects in the same group are Apache-2.0 OR GPL-2.0-or-later.

## Mbed TLS entropy without a fallback

`mbedtls-entropy-fail-closed.patch` changes one line of `modules/mbedtls/zephyr_entropy.c`: `mbedtls_platform_get_entropy` passes `false` instead of `true` for whether a failed entropy read may fall back to `sys_rand_get()`. At v4.5.0 the file has SHA-256 `0f0b8deb…` (one line changed from v4.4.2: the device comes from `entropy_get_default_device()`), the patch applies unchanged, and the patched copy has `417617f6…`.

Without it, a failed read on RT1060-EVKB seeds the PSA random generator from a non-cryptographic source and still reports full entropy; the TRNG driver returns `-EIO` on a failed read, so that path is reachable. With it, Mbed TLS reports the failure and PSA does not initialise.

`cmake/CruxMbedtlsEntropy.cmake` replaces the one source in the one library that compiles it; a missing library or a second one in `modules/mbedtls` fails configuration. A compile of the file from another directory would not, and only the RT1060-EVKB conformance image checks the compile commands. It applies only on the entropy driver route (`CONFIG_MBEDTLS_PSA_DRIVER_GET_ENTROPY`). The external-RNG route does not fall back unless `CONFIG_MBEDTLS_PSA_CRYPTO_EXTERNAL_RNG_ALLOW_NON_CSPRNG` is set, but it accepts whatever its entropy driver returns. It does not touch the TLS socket patch.

## eMMC cache flush on disk sync

`mmc-cache-flush.patch` corrects `subsys/sd/mmc.c` (SHA-256 `7bb737ec…` at v4.5.0, and `3c0de5a2…` after the patch, which applies unchanged; v4.5.0 adds HS400 enhanced strobe and still has no flush). At the pin, `mmc_card_init` turns on the eMMC cache whenever the device reports one, and `DISK_IOCTL_CTRL_SYNC` only waits for the card to be ready. No flush command exists in the stack, so on a device with a cache a successful sync does not mean that the data reached the medium. The simulator in `tests/support/emmc_sim` reproduces this; it has not been observed on a device.

With the correction, `mmc_set_cache` records in a private bit of `card->flags` that it turned the cache on, after it has sent the cache-on command and waited for the card, and `sd_init` clears the flags on each initialisation. When the bit is set, a sync holds the card lock and:

1. Waits for the card with `sdmmc_wait_ready`, which finishes earlier writes and clears any stale status.
2. Sends CMD6 to write `FLUSH_CACHE` (EXT_CSD byte 32) with value 1, with `CONFIG_SD_DATA_TIMEOUT` as its timeout.
3. Polls `sdhc_card_busy`, bounded by the same timeout.
4. Sends CMD13 until the card is ready in the transfer state, bounded by the same timeout.

A failure returns an error: the wait's own value in step 1 (`-EBUSY` when the card stays busy), the host's value for a failed command, `-ETIMEDOUT` for a busy period or status poll that does not end, and `-EIO` when a status response carries the switch error bit (bit 7). Steps 3 and 4 do not use `sdmmc_wait_ready`, because its status reads discard bit 7 (the card clears it when it is read), and CMD13 is sent without retries because a lost response may have held that bit. Without a cache, or before initialisation, the sync behaves as at the pin.

`CONFIG_CRUX_MMC_CACHE_FLUSH` defaults off and needs `MMC_STACK`. Limits:

- Only the bit 7 error is read from the status. The correction does not read back whether the card accepted the cache-on command; if it rejected it, an extra flush is sent, which is the safe direction.
- Linux allows 30 s for a flush while `CONFIG_SD_DATA_TIMEOUT` defaults to 10 s; a composition that needs longer raises that value. Timeouts count polling delays, so they are a lower bound.
- The disk de-initialisation path sends the sync and discards its result.
- The drift check covers `mmc.c` only. The correction relies on bit 15 of `card->flags` staying unused in `sd_spec.h`, on `sd_init_io` clearing the flags and on `sdmmc_wait_ready` behaving as at the pin, so a Zephyr update that leaves `mmc.c` unchanged still needs review. At v4.5.0 the flags use bits 1 to 9, `sd_init_io` still clears them and `sdmmc_wait_ready` is unchanged.
- A transient CMD13 status error makes the sync fail and the caller gets that error. With Reliance Edge the volume then becomes read-only until a remount, which is the safe direction.

`zephyr/mmc_cache_flush.cmake` replaces the one `subsys/sd/mmc.c` in the `subsys__sd` library, adds `subsys/sd` to its private include path and builds the copy with `-Wall -Wextra -Werror`. `tests/native/emmc_stack` runs the corrected stack against the simulator (`crux.emmc.stack.flush.cached` and `.flush.nocache`), and `tests/native/emmc_restart` checks that a sync through it outlives a restart with the cache on. These are model results, not device evidence.

## TCP initial sequence number that fails closed

`zephyr-isn-fail-closed.patch` changes `subsys/net/ip/tcp.c` of Zephyr v4.4.2 (SHA-256 `393b940e…`, and `94642fe2…` after the patch; Intel Corporation copyright). See the [ISN record](../../docs/rt1060-isn-fail-closed.md). It is applied only on the build-local copy of the wolfSSL bench line, after the TLS socket patch, so it stays on that line's Zephyr v4.4.2 together with the bench declaration and its recorded first freeze, until a 4.5 TLS socket patch exists (see [wolfSSL TLS socket backend](#wolfssl-tls-socket-backend)). On the v4.5.0 pin `scripts/prepare-isn-fail-closed.py` refuses the copy, because `tcp.c` is not the declared one.

At v4.4.2, `tcp_init_isn()` (RFC 6528, `CONFIG_NET_TCP_ISN_RFC6528`, Zephyr's default) has two defects:

- It ignores the result of `sys_csrand_get()` for its 16-byte key and marks the key as read, so after one failed read the key stays all zero for the rest of the boot.
- It hashes with SHA-256 into a 16-byte buffer. PSA refuses that with `PSA_ERROR_BUFFER_TOO_SMALL`, which is ignored too, so the hash is never produced (wolfPSA leaves the buffer as it was, Mbed TLS fills it with `'!'`) and the key is never used.

With the patch, a missing key or a failed hash makes `tcp_init_isn()` return an error. A SYN to a listening port gets a RST, and `net_context_connect()` returns the error and sends nothing. The key is read again at the next attempt; when the read works, the number is the hash of the key and the tuple plus the uptime, as the code intends.

`scripts/prepare-isn-fail-closed.py` applies the patch to a build-local copy of the pinned tree (it refuses a Git checkout), after `scripts/prepare-wolf-tls-zephyr.sh` has made the copy and applied the TLS socket patch. It extends the copy's marker `.crux-wolf-tls` from `<pin> <tls patch sha256>` to `<pin> <tls patch sha256> <isn patch sha256>` and writes no marker of its own. The bench guard compares that marker with the pin and the declared patches' hashes in order, and checks every patched file's hash (`patched_zephyr`, schema 2, in `bench_declaration.json`).

**Zephyr v4.5.0** (`tcp.c` SHA-256 `7bd732e5…`) corrects both defects: the key is read again until a read works, and the buffer has the size of a SHA-256 digest. When the key read or the hash fails, it falls back to `sys_rand32_get()`, which is not a cryptographic generator (`tcp.c` lines 2685-2693).

**Which images are fail-closed.** This patch has only ever been applied to the wolfSSL bench copy. Every other image ran upstream `tcp.c` before the baseline move and runs it after: at v4.4.2 upstream ignored the result of the key read and of the hash, and on v4.5.0 it uses the keyed hash with the fallback above.

A v4.5.0 rebase that keeps the fail-closed behaviour is smaller: `tcp_init_isn()` returns the error instead of falling back, and the two callers refuse as above; without RFC 6528, or for an address family that the hash does not cover, the number still comes from `sys_rand32_get()`. It is not stored or applied here, and moves with the wolfSSL line.

## HTTP header-phase deadline

`http-header-deadline.patch` changes `subsys/net/lib/http/http_server_core.c` (SHA-256 `db56e2d1…` at v4.5.0, and `98ef028a…` after the patch; copyright Emna Rekik and Nordic Semiconductor ASA). v4.5.0 moves the client read into `handle_http_data()` and adds HTTP/3 to the file; the deadline is unchanged and still not upstream. See [Issue #268](https://github.com/wonny-labs/crux-pilot/issues/268) and the [web contract](../../docs/web-contract.md).

At the pin, every read that returns data restarts the client's inactivity timer, and request headers run no resource callback. A client that trickles an incomplete request head, one byte per period, holds its client slot for as long as the parser accepts headers, and three such clients hold every slot of the web adapter.

With the patch, after each read that leaves the client open, the server checks whether the client is in the header phase: bytes received in the preface state, or the HTTP/1 request state before the parser has the complete headers. The phase starts at the first read of a request. While it lasts, the inactivity timer is set to the earlier of its usual period and the end of `CONFIG_CRUX_WEB_HEADER_DEADLINE_MS`, and a read past that end closes the client. A client idle between requests keeps the usual timer, and the body of a request that reaches a web route is under the adapter's request deadline. The phase is cleared when a client slot is initialised. The copy refuses to build without the Kconfig value or with HTTP/2 or HTTP/3, whose states it does not cover; the web adapter already builds HTTP/1.1 only.

`components/web/ports/zephyr/header_deadline.cmake` replaces the one `http_server_core.c` in the `subsys__net__lib__http` library for every image with `CONFIG_CRUX_WEB`; the script sits beside the web adapter rather than under `scripts/`. The `native_sim` suites `tests/native/web_http` and `tests/native/web_https` expect three trickling clients closed at the deadline while a fourth is served, and a head sent in pieces within the deadline served on each request of a kept connection. These are not device evidence. Two limits are declared:

- A client that reconnects holds a slot for up to the deadline per connection.
- A body on a request that the server answers itself, the plain `404` of a path with no resource or the plain `405` of a method outside the mask, runs no callback, so neither deadline bounds it: every byte restarts the inactivity timer, and a client that trickles such a body and reads the answers holds a slot with no time limit. Bounding that is a change beyond the decided option ([Issue #529](https://github.com/wonny-labs/crux-pilot/issues/529)).

The RT1060-EVKB bench image enables `CONFIG_CRUX_WEB`, so it compiles this copy too.

## Settings File backend faults

At the pin, the Settings File backend can report a failed write or read as success or as a missing key.
`settings-file-error.patch` corrects `subsys/settings/src/settings_file.c`, and `settings-store-error.patch` corrects `subsys/settings/src/settings_store.c`.
`settings_line.c` needs no patch and is staged unchanged, so that the three sources come from one place.

`zephyr/prepare_settings_file.py` refuses a source that differs from the pinned revision and an output inside the checkout, and writes the three copies and a `manifest.json` of hashes to the build folder `settings-file-candidate`.
`zephyr/settings_file.cmake` puts them in the place of the originals in the `zephyr` library, for both Settings File selections of Configuration ([Configuration validation](../../docs/configuration-validation.md)).
`CRUX_SETTINGS_FILE_CONTROL` keeps the unpatched backend for the negative controls of the `native_sim` fixtures, and is refused on any other board.

The suites `tests/native/configuration_settings_file`, `tests/native/configuration_settings_reliance` and `tests/native/configuration_settings_littlefs` run the corrected backend, and their controls show the cases that fail without it.
The NVS candidate (`tests/native/configuration_settings`) and the [error experiment](../../docs/settings-error-investigation.md) apply `settings-store-error.patch` as well.
The corrections add no checksum or resynchronisation, and a torn tail can lose the latest save.
