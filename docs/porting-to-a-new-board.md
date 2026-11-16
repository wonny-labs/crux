# Porting Crux to a new board

**Status: guide, written against `origin/main` at `35431b1e`, with the links and the boot section re-checked at `ea5eefdb`. Nothing in it is a qualification.** It tells a product team how to bring a Crux-based product up on a board that this repository has not seen. It adds no decision and no interface. Every statement cites a file or a document of this repository, and says what level of evidence stands behind it. Where the repository has no evidence, the text says **not verified**. Evidence levels E1 to E4 are those of [Component readiness](component-readiness.md#how-to-read-this): Host test, `native_sim`, target build, physical board.

## Quick path

1. Prove the bare board with Zephyr's own samples ([3.1](#31-zephyr-board-support)).
2. Copy the product template and build it for the target ([3.2](#32-product-skeleton)).
3. Add Crux components one at a time, and list every Crux binding that refuses your board ([3.3](#33-kconfig-and-devicetree)).
4. Review each Zephyr patch against your own drivers ([3.3](#33-kconfig-and-devicetree)).
5. Choose the storage medium, then the management services, then the boot composition ([3.3](#33-kconfig-and-devicetree) to [3.5](#35-secure-boot-composition)).
6. Keep a size record from the first build on ([3.6](#36-memory-budget)).
7. Run the board only under a written plan ([5.2](#52-first-board-run)), and report with the checklist ([5](#5-checklist-and-first-board-run)).

## 1. Who this is for, and what "porting" means

The reader is an engineer who has a Zephyr-supported board, a Crux checkout and no help from the people who wrote Crux. The board is assumed not to be one of the two this repository has worked with.

Crux components are portable C17 behind public contracts. The platform composition, not the component, knows the board ([architecture overview](architecture.md), [README](../README.md#architecture)). So a board port has four parts, and only the first is outside Crux:

| Part | What it is | Where it lives |
| --- | --- | --- |
| Zephyr board support | The board definition: devicetree, Kconfig defaults, drivers, boot header, flash layout, runner | Zephyr (in tree) or the product repository (out of tree) |
| Product composition | Kconfig fragments, devicetree overlays, the Crux module, the usage targets the product links, the adapters | The product repository, from [`templates/product/`](../templates/product/README.md) |
| Storage, network and boot choices | Which medium holds files, which interface carries management, which boot loader starts the image | The product, with the composition pages cited in section 3 |
| Crux bindings that name a board | A few Crux Zephyr ports check the board and refuse any other. Section 3.3 lists them | Crux source: a reviewed change, not a product setting |

**What Crux does not provide.** Crux has no hardware abstraction layer and no universal OS layer. Threads, locks, queues, UART, GPIO, I2C, SPI, network drivers and the network stack are Zephyr's, used directly in the product's Zephyr code. Crux supplies platform services (management, configuration, files, time, logging, system health) and the composition rules around them. The rule for each piece of code is in [Choosing an API](choosing-an-api.md). Four older Crux headers (`thread`, `sync`, `queue`, `serial`) are frozen for new product code.

## 2. Prerequisites and the test ladder

**Prerequisites.** Docker and the Dev Container of [Build and Integration Guide](build.md#development-environment), a pinned west workspace, and the pinned Zephyr SDK, through `scripts/bootstrap-zephyr.sh --install-sdk`. The Zephyr revision is pinned in [`west.yml`](../west.yml) (v4.4.2, `dccb09599635`). A different Zephyr gives a CMake warning and no Crux evidence applies to that build ([Zephyr baseline gate](product-composition.md#zephyr-baseline-gate)); each patch of section 3.3, when enabled, checks the exact source of that pin and refuses to configure if the file differs.

Climb one rung at a time. A rung does not include the ones below it, and a pass on one says nothing about the next ([AGENTS.md](../AGENTS.md#validation-and-evidence), [README](../README.md#development-and-target-environments)).

| Rung | What runs | Scripts that exist | What a pass proves | What it does not prove |
| --- | --- | --- | --- | --- |
| 0. Host | Portable C and the product's domain, on Linux with fakes | `scripts/bootstrap-host.sh`, `scripts/check-host.sh`, `CRUX_HOST_PRESET=host-sanitize scripts/check-host.sh`, `scripts/check-format.sh`, `scripts/analyze-host.sh`, `scripts/check-dependencies.sh`; the template's `check_domain_includes.py` ([README](../templates/product/README.md#zones-and-the-domain-include-check)) | Logic, contracts, sanitizer-clean behaviour of the portable code, include boundaries | Anything about Zephyr, a driver, timing or memory on the target |
| 1. `native_sim` | The product or a Crux test image on Zephyr's simulated board | `scripts/check-zephyr-smoke.sh`, `scripts/test-controller.sh`, `scripts/test-execution.sh`, `scripts/test-system.sh`, `scripts/test-mgmt-services.sh`, `scripts/test-native-composition.sh`, `scripts/test-consumer-system.sh` and the other `scripts/test-*.sh` of [tests/README.md](../tests/README.md) | Zephyr API use, Kconfig and devicetree selection, service composition, with the host TCP stack and a test entropy source | Target drivers, timing, entropy quality, persistence, memory use. `native_sim` has no board file for your board |
| 2. Cross-build | The same sources compiled and linked for the target | `CRUX_BOARD_TARGET='<your target>' scripts/check-zephyr-smoke.sh` (adds a Zephyr Hello World for the board), `scripts/test-product-template.sh '<your target>'`, `scripts/test-zephyr-time.sh '<your target>'`, `scripts/build-target.sh '<your target>'` (builds the Time sample and records provenance and `rom_report`); the per-component scripts hard-code the RT1060 or RT1170 target, so for them copy the `west build` line, not the script | That the selection configures, links and fits the memory map. Reports of size ([section 3.6](#36-memory-budget)) | That the image boots, that a peripheral works, that anything fits at run time |
| 3. First board run | A signed-off procedure ([section 5](#5-checklist-and-first-board-run)) | None for a new board. The repository's board tooling is specific to the RT1060-EVK Rev B ([section 4](#4-worked-examples)) | One run of one image on one board, as far as its log shows | Other boards, other cards, endurance, timing under load |

Build only is the default. Programming, resetting, debug attach, fuse or boot-mode changes are separate steps with their own approval in this repository ([AGENTS.md](../AGENTS.md#safety-and-workspace-boundaries)); do the same in your project.

## 3. Step by step

### 3.1 Zephyr board support

1. **Find the board.** Zephyr names a target `<board>[@<revision>][/<qualifiers>]`. `west boards` lists them. The two targets in this repository show the shape: `mimxrt1060_evk@B//qspi` (board, revision, SoC left to the default, flash variant `qspi`) in the scripts, and `mimxrt1060_evk@B/mimxrt1062/qspi` in [the microSD page](microsd-composition.md); `mimxrt1170_evk@A/mimxrt1176/cm7` (revision, SoC, core) for the other board ([RT1170 review](rt1170-evk-a1-feasibility.md#scope-and-evidence-boundary)). The revision and the qualifiers change devices, memory and layout. Read the upstream board files for the exact target before you rely on any value. The mapping from a PCB marking to a Zephyr revision is something to check on the board: the RT1170 review records it as not verified ([limits](rt1170-evk-a1-feasibility.md#recorded-limits)).
2. **In-tree or out-of-tree.** If the board is in the pinned Zephyr, use it unchanged. If it is not, put a board definition in the product repository and add its root to the build with `-DBOARD_ROOT`. Crux does not carry board definitions: its repository holds no board directory, only devicetree overlays and Kconfig fragments for existing boards. A board that is new to Zephyr needs its definition reviewed against the vendor's reference design before Crux sits on it. That work is Zephyr's, and this repository has no example.
3. **Prove the bare board first.** Build and run Zephyr's own `hello_world` and a network sample for the board before adding Crux. `scripts/check-zephyr-smoke.sh` does the build with `CRUX_BOARD_TARGET` set; it does not run it.
4. **Record what the upstream board file assumes.** Console UART, flash part, flash layout, external RAM, boot header and boot mode, watchdog, PHY. The RT1170 review is the model of this reading: [Rev A board defaults](rt1170-evk-a1-feasibility.md#rev-a-board-defaults) and the [review of boot, flash and debug path](rt1170-evk-a1-feasibility.md#review-of-boot-flash-fitted-devices-and-debug-path). A default in the board file is a source assumption until a board shows it.

### 3.2 Product skeleton

Copy [`templates/product/`](../templates/product/README.md) into an empty workspace directory, as its README says, and build it for your target:

```sh
west init -l product-x && west update && west crux-pins
west build -b '<your target>' -d product-x/build/app product-x/app
```

The template is its own west manifest repository. It imports `crux-pilot`, so Zephyr and the allowlisted modules come at the revisions Crux pins ([Product Composition Guide](product-composition.md#composition)). It has a domain (plain C, no Zephyr), an execution shell (`app/`) and `prj.conf` with `CONFIG_CRUX_TIME=y`. Board-specific files go next to the application under `boards/` (`<board>.conf`, `<board>.overlay`) or in `-DEXTRA_CONF_FILE` and `-DEXTRA_DTC_OVERLAY_FILE`, as `samples/controller/zephyr/boards/` does. Keep the domain free of board names: `check_domain_includes.py --product .` checks the include rules; run it in the product's own CI. For versioning, locks and release records, use [`RELEASE.md`](../templates/product/RELEASE.md) and the [release flow](product-composition.md#release).

State of the template: its own build is E3 on the RT1060 target, and nothing ran on a board ([readiness row](component-readiness.md)). No Crux release tag exists, so the template follows `main` until you pin a revision.

### 3.3 Kconfig and devicetree

Select only the Crux components the product needs. For each, the [readiness table](component-readiness.md#readiness-table) says what exists and at what level.

**Console and serial.**

- The Zephyr console and shell are Zephyr's: set `zephyr,console` and `zephyr,shell-uart` in the board or overlay. An image that has `CONFIG_CRUX_CLI`, `CONFIG_CRUX_WEB` or `CONFIG_CRUX_SSH` and is not marked as a development image must have no Zephyr shell ([shell rule](management-in-a-product.md#security-assumptions)).
- **Crux Logging** needs `zephyr,log-uart` chosen, exactly one enabled UART, 115200 baud 8N1, no flow control, no single-wire or RS-485 mode, no enabled child node, and refuses sharing the UART with Serial, a shell or other owners. On the RT1062 SoC it may share the console only when output goes through Logging alone (`LOG_PRINTK` on; `STDOUT_CONSOLE`, `CONSOLE_HANDLER`, `CONSOLE_SUBSYS`, `EARLY_CONSOLE` and `SHELL` off); on any other board a shared console is refused. The binding accepts `native_sim` and any enabled `nxp,lpuart` node on a board with the RT1062 SoC, the RT1060-EVK included: `components/logging/ports/zephyr/logging_binding.c`. On LPUART3 it refuses an enabled `csi` node, the rule that Serial has. Apart from that rule Crux checks no pin conflict on your board: whether the LPUART's pins collide with another enabled peripheral is yours to review in your devicetree.
- **Crux Serial** needs a dedicated `crux-serial0` UART alias, no flow control, no single-wire or RS-485 mode, no enabled child node and no other owner of the UART, and accepts `native_sim` and any enabled `nxp,lpuart` node on a board with the RT1062 SoC, the RT1060-EVK included. On LPUART3 it refuses an enabled `csi` node: `components/serial/ports/zephyr/serial_binding.c`. The pin review of your board is yours, as for Logging. Serial is frozen for new product code; use Zephyr's UART API in the shell instead ([Choosing an API](choosing-an-api.md#frozen-for-new-product-code-thread-sync-queue-and-serial)).

**Crux bindings that name a SoC.** System, Logging, Serial and the FatFs selections accept a board with the RT1062 SoC by the SoC and its devicetree, whatever the board's name, and refuse every other SoC with a compile or configuration error. On the RT1060-EVK itself they keep the checks that the EVKB evidence needs: Rev B for System and Logging, the Rev B QSPI target for the FatFs selections. The others only constrain what you can select. Treat a change to any refusal as a design change to Crux (read [CONTRIBUTING.md](../CONTRIBUTING.md) and raise it first), not as a setting. **Accepted is not qualified:** on a custom board with an i.MX RT1062 the evidence is a compile-only build of a fictional test board (`tests/zephyr/board_fixture`, E3 for that fixture only). Nothing checks how your board wires the UART pins, the SD card slot or the watchdog reset.

| Component | Where | What it accepts today |
| --- | --- | --- |
| System (watchdog, reset cause, reset) | `components/system/ports/zephyr/system_binding.c`, `CMakeLists.txt` | `native_sim`, and any board with the RT1062 SoC whose `crux-watchdog0` alias selects the SoC's `wdog0` (compatible `nxp,imx-wdog`, at `0x400b8000`, enabled). The RT1060-EVK only at Rev B (configure error otherwise); another RT1062 board has no EVK revision to check. Any other SoC: `#error "Crux System unsupported SoC or watchdog resource"` |
| Logging | `components/logging/ports/zephyr/logging_binding.c`, `CMakeLists.txt` | `native_sim` (UART emulator), and any board with the RT1062 SoC with any enabled `nxp,lpuart` node, under the node and owner checks of the bullet above. The RT1060-EVK only at Rev B (configure error otherwise). On LPUART3 it also refuses an enabled `csi` node (`#error "Crux Logging on LPUART3 conflicts with enabled CSI ..."`). Any other SoC: `BUILD_ASSERT` "Crux Logging unsupported UART resource" |
| Serial (frozen) | `components/serial/ports/zephyr/serial_binding.c` | `native_sim` (UART emulator), and any board with the RT1062 SoC with any enabled `nxp,lpuart` node, under the mode and owner checks of the bullet above. On LPUART3 it also refuses an enabled `csi` node (`#error "LPUART3 Serial pins conflict with enabled EVKB CSI"`); the rule names SoC labels, so it also refuses a board whose LPUART3 pins do not collide with CSI. Any other SoC: `BUILD_ASSERT` "Crux Serial unsupported UART resource". The Serial API is unchanged and stays frozen for new product code |
| File on FatFs | `components/file/ports/zephyr/file_native.c`, `CMakeLists.txt`, `zephyr/Kconfig` (`CRUX_FILE_FATFS_RT1060*`) | `native_sim` (test simulator selections), and for a real medium any board with the RT1062 SoC: the microSD provider and its compile check need an enabled `nxp,imx-usdhc` node with a `zephyr,sdmmc-disk` child (Kconfig), the RAM disk provider no card driver at all. On the RT1060-EVK only the Rev B QSPI target (Rev C and the hyperflash variant are refused). The symbols keep their `RT1060` names. The physical evidence is one RT1060-EVKB and one card ([microSD composition](microsd-composition.md)) |
| File on Reliance Edge | `zephyr/Kconfig` (`CRUX_FILE_RELIANCE_EDGE`) | Its help text says it works on any board that has the file system. No hardware target other than the RT1060 has been built with it (link only). It also runs on `native_sim` against a test-only eMMC simulator |
| GPIO, I2C, SPI | `components/gpio/ports/zephyr/gpio_binding.c`, `components/i2c/ports/zephyr/i2c_port_zephyr.c`, `components/spi/ports/zephyr/spi_port_zephyr.c` | Resource selected by an alias (`crux-gpio0`, `crux-i2c0`, `crux-spi0`). The RT1170 review shows cross-builds with overlays and no pin or bus evidence ([integration gaps](rt1170-evk-a1-feasibility.md#crux-integration-gaps)) |

**A `board: extend:` variant of the RT1060-EVK is not your own board to Crux.** Zephyr lets a repository extend an existing board with a new variant, and the variant keeps the existing board name, so `CONFIG_BOARD_MIMXRT1060_EVK` stays set. Crux then treats the image as the EVK and the variant inherits whatever EVK claims remain: System and Logging require Rev B, and the FatFs selections require the Rev B QSPI target, which a variant, with one more qualifier, is not. None of this compares your hardware with an EVKB, and it is no route to a qualification. A custom board with an i.MX RT1062 that has its own board name needs no extension: System, Logging, Serial and the FatFs selections accept it by SoC and devicetree, as the table above says.

**Clock and time.** Crux Time on Zephyr uses the system clock and needs no RTC. An RTC source is optional (`CONFIG_CRUX_TIME_RTC`, the `rtc` alias, `zephyr/Kconfig`). An RTC-backed run exists only for earlier Time code ([readiness, `time` row](component-readiness.md)).

**Network.** The MAC, PHY and MDIO drivers, DHCP or static addressing and the TCP/IP stack are Zephyr's. Crux Netif uses Zephyr's default interface and Sockets is a documented POSIX subset ([networking contract](networking-contract.md)). For the shape of a static-address wired composition read `samples/controller/zephyr/m3-network.conf` and `m3-network.overlay`: IPv4 only, static address, a PHY monitor period, the PHY reset line removed from other uses, a fixed MAC. Which listener binds which address is the composition's (`CONFIG_CRUX_WEB_BIND_ADDRESS`, `CONFIG_CRUX_SSH_BIND_ADDRESS`, [management guide](management-in-a-product.md#what-you-get-and-what-is-not-built)).

**Zephyr patches in this repository.** Crux replaces a few upstream sources in the build and never edits the Zephyr checkout. Each patch applies to one file at the pinned Zephyr, after a hash check, and configuration fails if the file differs ([patches/zephyr/README.md](../patches/zephyr/README.md)). Judge whether your board needs the same by reading the defect, not by copying the option:

| Patch | File at the pin | The defect, in short | Why it may or may not concern your board | How it is wired, and its evidence |
| --- | --- | --- | --- | --- |
| NXP ENET MDIO completion ([README](../patches/zephyr/README.md#reference-controller-native-mdio-correction)) | `drivers/ethernet/mdio/mdio_nxp_enet.c` | The wait discards the semaphore timeout, so a read can return success without completion | Only the NXP native MDIO driver on a single-core RT1062; the Kconfig refuses other setups. A board with another MAC or MDIO driver has a different code path to review | Opt-in `CONFIG_CRUX_M3_MDIO_COMPLETION_FIX`, wired by `samples/controller/zephyr/CMakeLists.txt` (a sample, not the module). Source-level counterexamples and a model test; the physical cause of the failure that led to it was not established |
| MMC cache flush ([README](../patches/zephyr/README.md#emmc-cache-flush-on-disk-sync)) | `subsys/sd/mmc.c` | The stack turns the eMMC cache on, and a disk sync does not flush it, so a successful sync does not mean the data reached the medium | Any eMMC with a cache, on any board, if file-system commits rely on sync as a barrier (Reliance Edge does) | Opt-in `CONFIG_CRUX_MMC_CACHE_FLUSH`, wired by `zephyr/CMakeLists.txt`. Tested against a simulator only; not observed on a device |
| Mbed TLS entropy without a fallback ([README](../patches/zephyr/README.md#mbed-tls-entropy-without-a-fallback)) | `modules/mbedtls/zephyr_entropy.c` | A failed entropy read falls back to `sys_rand_get()` and still reports full entropy | Any board that uses the entropy-driver route (`CONFIG_MBEDTLS_PSA_DRIVER_GET_ENTROPY`). Whether your TRNG driver can return an error is the question | Included through `cmake/CruxMbedtlsEntropy.cmake` by the test compositions `tests/psa_crypto/zephyr` and `tests/psa_entropy/zephyr`; the module does not include it, so a product that wants it includes it itself. Host and `native_sim` tests, and a compile check on the RT1060 conformance image |
| TCP initial sequence number ([README](../patches/zephyr/README.md#tcp-initial-sequence-number-that-fails-closed), [record](rt1060-isn-fail-closed.md)) | `subsys/net/ip/tcp.c` | A failed key read leaves an all-zero key, and a hash into a too-small buffer is never produced | The file is generic Zephyr networking code, so assume it applies wherever `CONFIG_NET_TCP_ISN_RFC6528` is on. Upstream status was not checked | `scripts/prepare-isn-fail-closed.py` on a build-local copy of the tree made by `scripts/prepare-wolf-tls-zephyr.sh`, used by the bench image |
| wolfSSL TLS socket backend ([README](../patches/zephyr/README.md#wolfssl-tls-socket-backend)) | Zephyr TLS sockets | Needed only for the Wolf TLS profile (HTTPS plus SSH) | The patch is **not stored here**. How a product applies it is an open decision; the recommendation is a Zephyr fork in the product manifest ([HTTPS composition](https-composition.md#how-a-product-applies-the-wolfssl-patch)). wolfSSL and wolfSSH are GPL-3.0-or-later or commercial | `native_sim` and compile only |

If you move to another Zephyr revision, each patch check fails by design. Redo the review of the file at the new revision before you regenerate anything. The route for third-party changes in a product is in [Modifying third-party code](product-composition.md#modifying-third-party-code).

**Storage.** Choose the medium first, then the composition page. The File component never mounts, formats or selects media, and the composition never formats automatically.

| Medium | Page | Level, from the repository |
| --- | --- | --- |
| QSPI NOR (settings or files) | [flash safety](flash-safety-acceptance.md), [storage assessment (historical)](storage-configuration-assessment.md) | The RT1060 firmware executes in place from the QSPI flash. The Pilot chose microSD over QSPI NOR for writable files ([Issue #14](https://github.com/wonny-labs/crux-pilot/issues/14), [microSD decisions](microsd-composition.md#decisions-in-force)), so no writable QSPI composition is maintained. The flash safety page is a software assessment, not an adopted driver |
| microSD with FatFs | [microSD composition](microsd-composition.md), [physical gate](microsd-physical-gate.md) | E4, narrow slice: one RT1060-EVKB, one card, named source revisions. It does not qualify the card, the board or power-loss behaviour ([evidence](evidence/microsd-physical/README.md)) |
| eMMC with Reliance Edge | [composition](emmc-reliance-composition.md), [physical gate](emmc-reliance-physical-gate.md) | E3 link only, and E2 against a test-only eMMC simulator. The RT1060-EVKB has no eMMC, so no result comes from an eMMC device. Reliance Edge is GPLv2 only and sits in the optional group `crux-reliance` ([licence note](product-composition.md#commercial-editions)); check the terms before a distributed product. The MMC cache flush patch above applies |
| RAM disk | [bench file backend](rt1060-bench-file-backend.md) | A test form of the bench image: blank at every boot |

**Watchdog and reset cause (Crux System).** System needs `CONFIG_WATCHDOG`, `CONFIG_HWINFO` and `CONFIG_REBOOT`, and a `crux-watchdog0` alias to an enabled watchdog node (`components/system/ports/zephyr/CMakeLists.txt`, `system_binding.c`). It reads the reset cause through Zephyr's hardware-info API and arms the watchdog with `WDT_FLAG_RESET_SOC`; a timeout is 500 to 64000 ms in multiples of 500 (`system_zephyr.c`). Selecting System does not arm a watchdog ([build guide](build.md#support-and-safety-boundaries)). Your board needs: a Zephyr watchdog driver that resets the SoC, `hwinfo` support for its reset-cause register, and, on a SoC other than the RT1062, a reviewed edit of the System binding (table above). On an RT1062 board the alias to the SoC's `wdog0` is enough for the build; whether the watchdog reset reaches the rest of your board is yours to check. The RT1170 review lists the same gap for its `wdog1` ([integration gaps](rt1170-evk-a1-feasibility.md#crux-integration-gaps)). Level: E3, plus E1 and E2 ([readiness, `system`](component-readiness.md); [validation](system-validation.md)). No physical acceptance exists.

### 3.4 Management services, TLS and entropy

Follow [Secure management in a product](management-in-a-product.md): its [steps](management-in-a-product.md#steps), [Kconfig table](management-in-a-product.md#kconfig), [boot order](management-in-a-product.md#boot-order) and [limits](management-in-a-product.md#limits-at-a-glance). The services are Experimental and nothing there has run on a board; the guide's tables say which parts are real on `native_sim`, Host, faked or untested. A product writes the composition code itself: the in-repository composition is test-only and refuses to build outside a declared `native_sim` test image.

For a new board, these are the points that depend on the board:

- **Entropy.** The credential store, session tokens, the TLS certificate key and the SSH host key all draw from PSA or wolfCrypt random. `native_sim` uses a declared test-only source. The target path is the SoC's TRNG through a Zephyr entropy driver, **compile only** in this repository ([PSA design](psa-crypto-design.md), [Wolf entropy record](rt1060-wolf-entropy.md)). Before any TLS or key generation on your board: confirm that its entropy driver exists, that it reports failure as an error, and keep the fail-closed behaviour: the Mbed TLS entropy patch above, and a check that an image that falls back to `sys_rand_get()` does not build ([record](rt1060-wolf-entropy.md#result)). Entropy quality of any TRNG is not evidenced here.
- **TLS certificate.** Every `native_sim` composition serves a declared test certificate whose private key is public. It must never ship. A product generates or installs its own with the certificate module and registers it with Zephyr's TLS credentials before the listener starts. No composition does that registration, apart from compile-only bench code ([TLS certificate](tls-certificate.md), [security assumptions](management-in-a-product.md#security-assumptions)). The first connection is trust on first use by fingerprint.
- **Other product work.** Host key holding, the first account, user key registration and the frontend are the product's ([what is not built](management-in-a-product.md#what-you-get-and-what-is-not-built)).
- **Memory.** The web and SSH stacks are large; see [3.6](#36-memory-budget).

### 3.5 Secure boot composition

Start with the [boot overview](boot-overview.md), which gives the phases and what is merged. [Boot composition](boot-composition.md) is the recipe: MCUboot built with sysbuild, RAM load with revert, ECDSA P-256 signature, for the RT1060-EVK Rev B. **It is build-only. Nothing was programmed or booted, and a successful build does not show that the boot loader accepts the image** ([not verified list](boot-composition.md#not-verified)).

What a new board needs:

1. **The MCUboot source** through the `crux-boot` west group, as the page's prerequisite table says.
2. **Four board files** in `zephyr/boot/boards/<board>/` of the Crux module: `mcuboot.conf`, `mcuboot.overlay`, `app.conf`, `app.overlay`. The directory name of the existing board is `mimxrt1060_evk_mimxrt1062_qspi_B`: board, SoC, qualifier, revision. A product that cannot add files to the Crux module keeps the same four files in its own repository and passes their paths in the same `-Dmcuboot_EXTRA_CONF_FILE`, `-Dmcuboot_EXTRA_DTC_OVERLAY_FILE`, `-D<image>_EXTRA_CONF_FILE` and `-D<image>_EXTRA_DTC_OVERLAY_FILE` arguments; the page documents how they merge with a product's own files.
3. **What the RT1060 files do**, so you can decide what yours must: they reserve a 256-byte retained RAM region at the end of OCRAM2 (`0x2027ff00`) for boot information and trim OCRAM2 by that amount in both images; they point MCUboot's executable RAM window at the SDRAM (`0x80000000`, 32 MiB) because RAM load copies the image there; they select the retention share-data backend so the application can confirm. Every address, size and node name there is the RT1060's. A board without external RAM, or with another RAM map, needs a different composition, and the page's "Board" paragraph says only that another board needs its own four files and its own build.
4. **The flash layout.** The slot partitions and the `mcuboot` partition come from the board's devicetree. On the RT1060 the `mcuboot` partition is 128 KiB and the signed image slot 3,145,728 B, a provisional size ([what the build produces](boot-composition.md#what-the-build-produces)); the RT1170 Rev A inherits a different layout and Rev B replaces it ([RT1170 review](rt1170-evk-a1-feasibility.md#rev-a-board-defaults)). Do not copy a layout from another board.
5. **The ROM boot path.** Whether the SoC ROM accepts the MCUboot-in-flash layout and jumps to it is **not verified** on any board in this repository. Vendor-specific ROM authentication, fuses and lifecycle states are outside this guide; read the vendor's public documentation, and keep every fuse or lifecycle step out of a first bring-up. The [boot investigation](boot-update-investigation.md) and the [eMMC boot investigation](boot-emmc-investigation.md) record desk studies, with their own labels.
6. **At v4.4.2 RAM load with revert also writes a padded, confirmed image.** A flow that tests revert must use the unconfirmed `zephyr.signed.bin` ([the page](boot-composition.md#what-the-build-produces)).

**Keys.** The composition signs with MCUboot's published test key `root-ec-p256.pem`, which sysbuild uses when no key is given; the build log warns of it. **That key is public. An image signed with it must never be programmed to a board, and no release is signed with it.** For production, a product generates its own key outside every repository, passes it with `-DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE=\"<path>\"` as the page states, decides how the key is stored and who may sign, and records the security counter separately from the product version ([versions](product-composition.md#versions)). This repository holds no key and no key-generation step, so everything beyond that line (key custody, rotation, rollback policy, the ROM trust chain) is yours to design and review.

The check that exists is `scripts/test-boot-composition.sh`: it builds, signs and verifies with the public test key. It is hard-coded to the RT1060 board.

### 3.6 Memory budget

Read the sizes from your own build, then compare with the recorded ones:

| Where | What |
| --- | --- |
| `west build -t rom_report` and `-t ram_report` | Symbol-based totals per build ([release flow](product-composition.md#release)). The linker's region summary and these totals are different views ([baseline note](baseline.md)) |
| `scripts/record-build-provenance.py` | Needs `rom.json` and `ram.json` from those reports; it records the image hash and `firmware_identity` ([Identity](product-composition.md#identity)) |
| [Boot composition outputs](boot-composition.md#what-the-build-produces) | MCUboot Flash and RAM, signed image size, slot size, for RT1060 |
| [RT1060 management image report](rt1060-management-image-feasibility.md#result) | The large case: Flash and SDRAM of the integrated HTTPS, SSH and SFTP image, and the stack findings. These are compile and link figures |
| [Limits at a glance](management-in-a-product.md#limits-at-a-glance) | Heap for three TLS clients, session slots (worker stacks are in the [Kconfig section](management-in-a-product.md#kconfig)). `native_sim` or source figures, none measured on a target |
| [RT1170 recorded identification](rt1170-evk-a1-feasibility.md#recorded-build-identification) | Image size of the M3-only candidate on that board |
| [Priority map and pools](thread-sync.md#priority-map-of-crux-threads) | Crux thread priorities, pool counts and stack settings |

Points that bite on a new board: the management worker stack default of 8192 B equals the tested images and is **not a measured high-water mark**; the HTTP server and SSH worker stacks are estimates, not target measurements ([stacks](rt1060-management-image-feasibility.md#thread-stacks)). Measure your own with Zephyr's `CONFIG_THREAD_STACK_INFO` and `CONFIG_INIT_STACKS` under load, including a login. Fit the image to your RAM map before you add the management stacks, and give the network buffer pools their own measurement ([network buffers](rt1060-bench-network-buffers.md)).

## 4. Worked examples

### RT1060-EVK Rev B (`mimxrt1060_evk@B//qspi`)

The first target. Everything in sections 2 and 3 was written against it. What exists, and at what level ([readiness table](component-readiness.md#readiness-table)):

| Area | Exists | Level |
| --- | --- | --- |
| Time, Thread, Sync, Queue, Serial, Logging, System | Zephyr ports, bindings for this board | E3 and below. Earlier physical runs were of the controller sample or earlier code and are not counted |
| Netif and Sockets | Port plus the M5 network image | E4, narrow slice: a reduced, non-qualifying, one-boot run of one image on 2026-11-08 completed its phases 1 to 6. Link loss, recovery and the final idle phase were not run ([run 3](evidence/networking-physical-stage1-run3/README.md)). Two earlier runs were inconclusive |
| File on microSD (FatFs) | Provider, composition, samples | E4, narrow slice, one board and one card ([evidence](evidence/microsd-physical/README.md)) |
| File on Reliance Edge, eMMC | Provider and composition | E3 link only. The board has no eMMC |
| Management services (HTTPS, SSH, SFTP) | A bench image `tests/zephyr/management_rt1060_compile` | E3 only. It compiles, links and **refuses to start**. "Ready for a board run? No." ([report](rt1060-management-image-feasibility.md#result)) |
| MCUboot RAM load with revert | Four board files and a CI build check | Build only. Boot, confirm and revert not verified |
| Board tooling | A profile-based freeze and programming driver with safety gates, in `tests/target`, and a separate device-control tool in `tools/` | The driver was used in the recorded RT1060 board windows for the network image ([run 3](evidence/networking-physical-stage1-run3/README.md)). The device-control tool has had no run on hardware ([README](../tools/device_control/README.md)). Both are written for one board and one probe and UART setup; see [image profiles](board-image-profiles.md) |

The three Zephyr patches that grew out of this board (MDIO, MMC flush, entropy) and the ISN patch are in [3.3](#33-kconfig-and-devicetree). They are the best list of what went wrong when Crux first met real hardware: read them as examples of checks to repeat, not as a list of what your board needs.

### RT1170-EVK Rev A (`mimxrt1170_evk@A/mimxrt1176/cm7`)

A **desk and cross-build** scope only, recorded in [the RT1170 review](rt1170-evk-a1-feasibility.md): the controller sample's M3-only candidate configures and links in CI (`scripts/test-m3-rt1170.sh`), with its image identification recorded. It is not a supported or qualified target. No board, probe or serial adapter was touched. System, Serial and Logging are not enabled for it because their bindings accept only the RT1062 SoC and `native_sim`. Netif has no board check, but the M3-only candidate does not enable it and no network evidence exists for this board; GPIO, I2C and SPI cross-build with overlays and no pin evidence. Boot mode, recovery from a bad image and the fitted flash part are source assumptions. Read the review as the template for the desk work of a port: board defaults, integration gaps per component, boot and recovery, recorded limits.

## 5. Checklist and first board run

### 5.1 Porting checklist

Copy this table into your issue and fill it in. Keep the evidence it names.

| Item | Where | How to verify | Evidence to keep |
| --- | --- | --- | --- |
| Zephyr board target chosen, revision and qualifiers named | Product `README`, build scripts | `west boards`; `west build -b '<target>'` of Zephyr `hello_world` | The target string, the Zephyr SHA, `west.yml` freeze |
| Zephyr pin matches Crux's | `west.yml`, manifest | `west crux-pins`; a configure without the baseline warning | Output of `west crux-pins` |
| Domain compiles on Host with fakes | `domain/`, `tests/` of the product | `check_domain_includes.py --product .`; Host tests; sanitizer preset | CI log, commit SHA |
| `native_sim` build of the shell | `app/` | Twister or the product's native run | Log of the run |
| Cross-build for the target | `app/` | `west build -b '<target>'` with `-DCRUX_REQUIRE_VERIFIED_ZEPHYR=ON` | `zephyr.bin` SHA-256, `firmware_identity`, build log |
| Console and log UART | Overlay, `prj.conf` | Section 3.3; Logging and Serial binding accept the node, or an edit is reviewed | Resolved `.config`, `zephyr.dts` |
| Time source | `prj.conf` | `CONFIG_CRUX_TIME`; RTC only if used | `.config` |
| Network: MAC, PHY, address, reset line | Overlay, `prj.conf` | Link and traffic on the board ([5.2](#52-first-board-run)) | Capture of link state and a counted exchange |
| Patch review (section 3.3 table) | Each patch README | Read the defect against your drivers; write the answer down | A line per patch: needed, not needed, why |
| Storage medium and layout | Composition page for the medium | Mount, remount, reboot on the board; never auto-format | Log, medium identity, card or part number |
| Watchdog and reset cause | System binding, overlay | Watchdog node and `hwinfo` support read; reset-cause test on the board | Reset cause before and after a forced watchdog reset |
| Entropy | Entropy driver, `prj.conf` | Failure is an error; image refuses a `sys_rand_get()` fallback | Test log, driver source reference |
| TLS certificate | Product code | Test certificate absent from the image (symbol or string check); fingerprint printed | Image check output, fingerprint |
| Management services | Product composition | [Steps](management-in-a-product.md#steps); route review | Reviewed route list, test log |
| Boot composition | Four board files | `west build --sysbuild` as in [boot composition](boot-composition.md); `imgtool verify` with your own key | Build log, signed image hash, key id (not the key) |
| Production keys | Key custody, outside repositories | Written procedure; the public test key never in a release | Procedure, not the key |
| Memory budget | `rom_report`, `ram_report` | Section 3.6; stack watermarks under load | Reports, watermark log |
| Release record | `templates/product/RELEASE.md` | [Release flow](product-composition.md#release) and bundle check | Filled record, `release-manifest.json` |

### 5.2 First board run

An outline for the person who holds the board. The repository has no procedure for a new board, and the one it has for the RT1060-EVK Rev B depends on that board's probe, UART and mount guard ([physical preparation](networking-physical-preparation.md)). Adapt its principles, not its tools.

**Before power.**

1. Write a plan: image, hash, board, what the run will show, what stops it, and how to return the board to a known state. Get it approved by whoever owns the board and the programmer.
2. Identify the board: PCB marking and revision, boot-mode switches and straps, jumpers on the console and power paths, the probe and its firmware, the flash part actually fitted. The RT1170 review lists these items as the minimum before any programming ([reading for the hardware item](rt1170-evk-a1-feasibility.md#review-of-boot-flash-fitted-devices-and-debug-path)).
3. Decide the recovery path in advance (a second probe, a boot-mode switch, a vendor tool). Do not start without one.
4. Use a power source and cable as designed. Do not hot-plug cards, display or camera connectors.
5. Make one owner for the serial port and one for the programmer. Do not share either between tools while a run is active. Check whether opening the port toggles DTR or RTS and resets the target; the device-control README says a new board needs this checked ([README](../tools/device_control/README.md)).

**During.**

6. Program one image whose hash you recorded, read it back and compare. Do not program fuses or change lifecycle or boot-security state during first bring-up.
7. Start with the console: capture the boot banner from the first byte. Then network link, then one exchange, then the first storage mount, then the services. Stop at the first surprise.
8. Never retry a failed programming step blindly: record the state and decide.
9. Never program an image signed with the public MCUboot test key to a board ([boot composition](boot-composition.md#the-argument-set)).

**After.**

10. Return the board to its known state and record that you did.
11. Keep raw logs unedited, with timestamps and the exact command lines.

**What to capture.** Revisions: the Crux and product SHAs, `west.yml` freeze, Zephyr SHA. Build: target, `.config`, `zephyr.dts`, `zephyr.bin` SHA-256, `firmware_identity` (`scripts/record-build-provenance.py`), `rom_report` and `ram_report`. Board: photo or description of the revision, switches and jumpers. Run: console log from reset, probe log, stack watermarks, heap and network pool use if printed, timing of each step, what you saw and did not see.

**How to report.** One page per run in the product's issue: what ran (image hash, target), what was done, result (pass, fail, inconclusive), the evidence files, what the run does **not** show, and what you would repeat. Use the vocabulary of this repository: say which level (E1 to E4) the result is, for which component and revision. An inconclusive or failed run goes into the record as it is. A run that passed on one board and one card is a narrow slice, as the microSD evidence says of itself.

## 6. Status and limits

- **Verified in this repository, by level.** Host and `native_sim` tests of the portable components and compositions; cross-builds for the RT1060-EVK Rev B and (software only) the RT1170-EVK Rev A; narrow physical slices on the RT1060 for Netif and Sockets and for File on microSD ([readiness table](component-readiness.md#notes)).
- **Not verified.** Any board other than the RT1060-EVK Rev B at E4. The management services on any board. Booting through MCUboot on any board. eMMC on any device. Entropy quality of any TRNG. Stack and memory high-water marks of the management stacks on a target. The behaviour of any patch of section 3.3 on your board.
- **Moving parts.** The Zephyr pin, the readiness table and the composition pages change. Where this guide and a cited page disagree, the page wins; report the difference.
- **Not a qualification.** Nothing here qualifies a board, a card, a flash part, a product or its power-loss, security or timing behaviour. A successful port means that the checklist items have their recorded evidence, at the levels named, and no more.
- **Not covered.** Vendor ROM secure boot and fuse programming, production key custody, manufacturing flow, Embedded Linux ([README](../README.md#development-and-target-environments)), and licence review of the optional groups.
