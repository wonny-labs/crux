# Lines edited in place during the documentation restructure

> **Historical record.** When the documentation was restructured as a developer entry point, some lines in the main documents were edited in place: a link to a page that moved to this folder was replaced, a recorded observation or a process remark was dropped from a sentence, or the set-up text was merged into Getting started. This page keeps each original line word for word, grouped by its source file, so that no text is lost. Links are as they were and are not checked.

## `README.md`

~~~text
**Crux** is a reusable embedded software platform for controller and firmware applications. It provides portable C17 components and selected standard APIs, supported by OS-specific integration, build tools and tests. Portable application code remains separate from operating-system and board details.
~~~

## `docs/build.md`

~~~text
**First set-up on native Linux or Windows with WSL2:** read [Getting started on Linux and Windows with WSL2](getting-started-linux-wsl2.md) first. It covers the Git clone, the folder layout, line endings, network access and sizing, which are summarised below.
~~~

~~~text
**Apple silicon and other arm64 hosts.** The Dev Container is pinned to `linux/amd64` (`--platform=linux/amd64` in `devcontainer.json`). On an arm64 machine, such as an Apple-silicon Mac, Docker runs it under emulation, which is slow. Running the full Host and Zephyr suites that way is impractical. CI is the supported way to run them in full: push the branch to a (Draft) pull request, or start the workflow manually, and read the results of the `host-foundation` and `zephyr-software` workflows (the Zephyr workflow ignores changes that touch only Markdown or `docs/`). Use a local run for the narrow checks of the code you changed. This guide gives no time estimate. For disk and memory, see [Disk and memory](#disk-and-memory) below, and confirm the available disk space before the SDK installation (see [Zephyr build and module integration](#zephyr-build-and-module-integration)).
~~~

~~~text
### Requirements for the checkout
~~~

~~~text
- **Crux must be a Git clone.** The scripts call `git rev-parse --show-toplevel`. Prefer a real clone made inside Linux or WSL2, which keeps the executable bits and LF line endings. An exported archive is a fallback with caveats, described on the [WSL2 page](getting-started-linux-wsl2.md#1-use-a-git-clone).
~~~

~~~text
- **The repository folder must be named `crux-pilot`, and its parent folder is the west workspace.** The Dev Container mounts the parent (`${localWorkspaceFolder}/..`) as `/workspaces/crux`, and `scripts/bootstrap-zephyr.sh` stops unless the repository is at `<workspace>/crux-pilot`. West then writes `zephyr/` and `modules/` into that parent. `bootloader/` appears only when the optional group `crux-boot` is enabled, for example by `scripts/test-boot-composition.sh`. Use an empty folder only for Crux, for example `~/work/crux-ws/crux-pilot`. Do not clone directly into your home directory: it would become the mounted workspace.
~~~

~~~text
- **On Windows, use WSL2.** Clone inside the WSL2 file system, never under `/mnt/c`, with `core.autocrlf` set to `false`. Use Docker Desktop with the WSL2 backend, or Docker Engine in WSL2. `.gitattributes` keeps LF line endings for shell scripts and the other files that run in Linux.
~~~

~~~text
The first set-up downloads from `mcr.microsoft.com` (base image), the Ubuntu archive, PyPI (the Dev Container's `postCreateCommand`, the Zephyr requirements in `scripts/bootstrap-zephyr.sh`, and the MCUboot requirements in `scripts/test-boot-composition.sh`), and `github.com` (the west projects of `west.yml`, the GoogleTest archive that CMake fetches, and the Zephyr SDK, which `west sdk install` looks up through the GitHub REST API). The scripts set no proxy: behind one, configure Docker's proxy and pass `HTTP_PROXY`, `HTTPS_PROXY` and `NO_PROXY` into the container. The wolfSSL and tuxera projects are fetched only when their optional west groups are enabled. If the unauthenticated GitHub API limit stops the SDK download, export `CRUX_GITHUB_TOKEN=<read-only token>` before `scripts/bootstrap-zephyr.sh --install-sdk`; the script passes it to `west sdk install`. A proxy allowlist may also need `api.github.com`, `codeload.github.com` and the hosts of the SDK release files. The [WSL2 page](getting-started-linux-wsl2.md#4-network-and-proxy-prerequisites) lists each source and the script that uses it.
~~~

~~~text
These are estimates, not measured minimums. The container runs with `--memory=4g` and `--cpus=2` (`devcontainer.json`), so Docker Desktop or the WSL2 virtual machine must offer at least that. The recorded planning headroom is 30 to 40 GiB free; in the recorded run free space fell by about 10 GiB (41 to 31 GiB) for the image, the SDK and the west workspace. Plan for at least 30 GiB free before `--install-sdk`. The 10 GiB figure comes from an early macOS run on 2026-10-16, when builds were smaller, so treat it as a lower bound. See [baseline](baseline.md) for the record.
~~~

~~~text
**Recorded on macOS only.** The only debug and physical-test host that has been used is macOS. `scripts/macos/start-jlink-gdbserver.command` and `scripts/test-target.sh` exit on any other system, and no Linux or Windows route has been run. The script prefers `/usr/local/bin/JLinkGDBServer` and falls back to a `JLinkGDBServerCLExe` under `/Applications/SEGGER`. It starts the server with `-device MIMXRT1062xxx6A -if SWD -speed 400 -endian little -port 2331 -localhostonly 0`; whether that command works on Linux is not verified. On native Linux the container also needs `--add-host=host.docker.internal:host-gateway` for the VS Code profiles below, which is untried too. See [Getting started on Linux and Windows with WSL2](getting-started-linux-wsl2.md#7-boards-and-debug-probes).
~~~

## `docs/component-readiness.md`

~~~text
| `gpio` | Implemented, one input line. [Contract](gpio-contract.md) | `crux_gpio_host`: in-memory simulation, `ports/host/gpio_host.c`. A loopback test double (the stored value of one line), not a GPIO model; a Zephyr build cannot select it (`zephyr/CMakeLists.txt:110-112` adds only `ports/zephyr`) | `module`: `CONFIG_CRUX_GPIO`; alias `crux-gpio0`. `tests/ only`: `tests/gpio/zephyr`, `tests/gpio/evkb`, `tests/gpio_physical` | **E3** (RT1060-EVKB twice, and RT1170-EVK A1), also E1, E2. `scripts/test-gpio.sh`. The physical item P1 is a plan: `tests/gpio_physical` has no recorded result ([plan](physical-verification-plan.md)) | "Neither board is qualified for physical use" ([contract](gpio-contract.md)). No output or interrupt API | Experimental: no composition outside `tests/`, and frozen as Experimental by accepted [ADR-0001 Decision 3](decisions/0001-application-boundary-and-api-stability.md#decision-3-what-crux-will-and-will-not-abstract) (D4). Deprecation at the first tag and removal are follow-up change 4 (the plan), not yet done; the header carries the opt-in frozen-header warning |
~~~

~~~text
| `i2c` | Implemented. [Contract](i2c-contract.md) | `crux_i2c_host`: loopback, `components/i2c/host/i2c_port_host.c`. A test double: it echoes the transmitted bytes, zero-fills a read and ignores the address, so it models no bus; a Zephyr build cannot select it (`zephyr/CMakeLists.txt:95-97`) | `module`: `CONFIG_CRUX_I2C`; alias `crux-i2c0`. `tests/ only`: `tests/i2c_zephyr`, `tests/i2c_consumer_zephyr`, `tests/i2c/evkb` | **E3**, also E1, E2. `scripts/test-i2c.sh`. The TMP117 model is written from a data sheet, with no part used ([tests/README.md](../tests/README.md#i2c)) | No application consumer or physical bus ([contract](i2c-contract.md)) | Experimental, as `gpio`: frozen by accepted D4, with deprecation and removal not yet done (follow-up change 4 is the plan); the header carries the opt-in frozen-header warning |
~~~

~~~text
| `spi` | Implemented. [Contract](spi-contract.md) | `crux_spi_host`: loopback, `components/spi/host/spi_port_host.c`. A test double: it echoes the transmitted bytes, so it models no peripheral; a Zephyr build cannot select it (`zephyr/CMakeLists.txt:100-102`) | `module`: `CONFIG_CRUX_SPI`; alias `crux-spi0`. `tests/ only`: `tests/spi_zephyr`, `tests/spi_consumer_zephyr`, `tests/spi/evkb` | **E3**, also E1, E2. `scripts/test-spi.sh`. The flash model follows data sheets, with no part used ([tests/README.md](../tests/README.md#spi)) | No application consumer or physical peripheral ([contract](spi-contract.md)) | Experimental, as `gpio`: frozen by accepted D4, with deprecation and removal not yet done (follow-up change 4 is the plan); the header carries the opt-in frozen-header warning |
~~~

## `docs/decisions/0002-platform-direction-zephyr-execution-crux-services.md`

~~~text
**Corrected H2 evidence.** ADR-0001 ([ADR-0001, Decision 5](0001-application-boundary-and-api-stability.md#decision-5-crux-value-and-the-evidence-that-would-show-it), the H2 row, `:347` at this head) cites `crux-controller`'s Host tests as evidence for H2. Those tests link `workload` and `net_client` only, and no Crux provider. No product consumer uses a Crux Host provider today, so H2 has no product evidence. D10 phase 1 is what can show it.
~~~

~~~text
- **Decision 5, option c** (`:357-359` at this head) is **not adopted**. The staged path freezes, measures, then decides. The result of D10 can reopen it, as ADR-0001 says.
~~~

~~~text
- **Decision 5, H2 evidence** (`:347`) is corrected as above.
~~~

## `docs/decisions/0005-native-sim-test-watchdog-for-system-consumers.md`

~~~text
| 11 | `CONFIG_CRUX_SYSTEM` depends on `CRUX_PILOT_MODULE && MULTITHREADING` and the module adds its subdirectory under that symbol. The Zephyr provider links `crux_system_api` (and through it `crux::base`), `zephyr_interface` and `crux_interrupt`, and none of them links a Thread, Sync, Queue or Serial target as far as I read. System needs no frozen Thread, Sync, Queue or Serial symbol | `zephyr/Kconfig:223-228`, `zephyr/CMakeLists.txt:108-111`, `components/system/ports/zephyr/CMakeLists.txt` last two lines | Verified |
~~~

~~~text
**T1, Host, no Zephyr SDK: a consumer cannot reach the private seam.** On the model of the table in section 1.2, fixed as a test: a consumer target that adds `components/system/ports/zephyr` or `components/system/src` is refused, and the public include root is accepted. This part passes at the baseline (**Verified** by the probe) and runs on macOS. It needs no change to the guard.
~~~

## `docs/decisions/README.md`

~~~text
- An accepted record is not rewritten. A later decision supersedes it with a new record, and the old record's status line links to the new one.
~~~

~~~text
- A record states options, trade-offs and a recommendation for each decision. It ends with a list of the owner's decisions.
~~~

## `docs/getting-started-linux-wsl2.md`

~~~text
This page is for a first set-up on native Linux or on Windows with WSL2. It states what the scripts and the Dev Container require, so that the first build does not fail for a reason that the README does not show. For the builds themselves, see the [Build and Integration Guide](build.md).
~~~

~~~text
A real clone, made inside Linux or WSL2, is the recommended form. It keeps the executable bits and the LF line endings. An archive is a fallback with these caveats. If you received one, make it a Git repository from its root:
~~~

~~~text
- **Disk.** The recorded planning headroom of the project is 30 to 40 GiB free ([baseline](baseline.md)). In the recorded run, free space fell from 41 GiB to 31 GiB after the image, the SDK and the west workspace, and to 26 GiB after an image rebuild for the sanitizer runtime. The 10 GiB drop comes from an early macOS run on 2026-10-16, when builds were smaller, so it is a lower bound. Plan for at least 30 GiB free before the SDK installation, and more if you keep several build directories.
~~~

~~~text
The only recorded host for debugging and physical tests is macOS. `scripts/macos/start-jlink-gdbserver.command` (it prefers `/usr/local/bin/JLinkGDBServer` and falls back to a SEGGER `JLinkGDBServerCLExe`) and `scripts/test-target.sh` both exit on any other system, and `.vscode/launch.json` connects to `host.docker.internal:2331`. No Linux or Windows route has been run. On native Linux, Docker does not resolve `host.docker.internal` unless the container is started with `--add-host=host.docker.internal:host-gateway`; this too has not been tried. On WSL2, USB forwarding to the distribution is needed only if the GDB server runs inside WSL2; running the server on Windows is the other option. Both are untried. Any operation on a board needs approval for the task. See [RT1060-EVKB debugging](build.md#rt1060-evkb-debugging).
~~~

## `docs/history/README.md`

~~~text
Status: **historical.** The files in this folder are earlier proposals and validation snapshots that were replaced by a contract or a later record. Each keeps its original decisions and measurements. They are not current usage guidance, and the documentation link check does not read them.
~~~

~~~text
For current Thread and Sync behaviour use the [Thread and Sync contract](../thread-sync.md). For everything else start at the [repository README](../../README.md) and [Component readiness](../component-readiness.md).
~~~

## `docs/management-in-a-product.md`

~~~text
To review the security model, read the [secure management review guide](secure-management-review.md); to check a board on your own bench, the [bench test procedure](secure-management-board-test-procedure.md), which has not yet been run.
~~~

## `docs/secure-boot-bench-session.md`

~~~text
1. Start the logger, so that it is reading before the reset (DTR and RTS low, nothing sent; the open must not reset the board, which is an open question of procedure section 10):
~~~

~~~text
5. `make_manifest.py check`; the same keys (if the development key was lost, rebuild MCUboot and every image: procedure section 10).
~~~

~~~text
- [ ] Does the installed J-Link Commander accept the `loadfile "<file>", <address>` and `verifybin "<file>", <address>` forms the wrappers write, and does `-ExitOnError 1` give a non-zero status on a failed script command? The procedure asks the first (section 10); the second is new. The wrappers never rely on the exit status alone for a verify.
~~~

~~~text
- [ ] The other open questions of [procedure section 10](secure-boot-board-test-procedure.md#10-open-questions-for-the-first-bench-session) still apply and are not repeated.
~~~

## `docs/secure-boot-board-test-procedure.md`

~~~text
- **Open configuration only.** No fuse operation and no HAB operation, ever. The Zephyr-built image carries no CSF and the ROM is expected to boot it in open configuration (**Inference**, plan section 3). No tool of the repository reads the fuse or lifecycle state of the board (section 10).
~~~

~~~text
| Probe | SEGGER J-Link PLUS on the 20-pin J2 header with J9 and J10 removed to isolate the on-board SWD; SWD at 400 kHz, device `MIMXRT1062xxx6A`; J-Link software V9.86a. The first connection failed until J9/J10 were corrected and was made at 100 kHz | Verified in repository ([baseline](baseline.md), recorded observation). A different probe, or only the on-board DAPLink for debug, has no recorded flow: see section 10 |
~~~

~~~text
| Private key directory | A place for the development key in the Linux environment that builds: outside every repository, outside the bind-mounted workspace and every shared volume, mode 700. In the Dev Container the container user's home is outside the bind mount but disappears with the container; see section 10 | Decision 18 ([boot and update investigation](boot-update-investigation.md)) |
~~~

~~~text
Addresses: MCUboot and the restore image at `0x60000000`, slot 0 at `0x60020000` (the QSPI window starts at `0x60000000`; partitions `mcuboot` at `0x0` size `0x20000`, `image-0` at `0x20000` size `0x300000`; Verified by build in [Stage 6](evidence/boot-update/stage6-layout-and-write-analysis.md)). The `r`, `h`, `loadfile` order is that of [`capture_m3.py`](../tests/target/capture_m3.py) and the [microSD physical gate](microsd-physical-gate.md) (`h`, `loadfile`, `r`, `g`). The punctuation follows SEGGER's Commander reference and the repository's tests (`loadfile "<file>", <address>`); the repository's gate pages write `savebin` and `loadbin` without commas. If your Commander refuses one form, try the other and record which (section 10). The probe's serial number comes from a probe list; its script starts with `exec DisableAutoUpdateFW` like the others (the repository's baseline ran the same list with `ShowEmuList USB`, which also prints `VTref`):
~~~

~~~text
- `dtr` and `rts` are `false` because the repository's own capture sets neither; the README says to check them on a new board, since a USB bridge can move the lines at open (section 10). `ready_marker` is the last line of the controller sample (`samples/controller/zephyr/main.c`, **Verified in repository**) and is matched literally. For T0 use a copy of the profile whose marker is `CRUX_TIME_READY composition=zephyr` and whose timeout is 10 (`samples/time/src/main.c`).
~~~

~~~text
1. Run `identify.jlink`. Expected: connect succeeds, `VTref` about 3.3 V (3.322 to 3.34 V recorded), SW-DP ID `0x0BD11477`, AHB-AP IDR `0x04770041`, Cortex-M7 r1p1, CPUID `0x411FC271` (**Verified in repository**, recorded observation of this board, [baseline](baseline.md)). If it fails at 400 kHz, retry once at 100 kHz and record both.
~~~

~~~text
4. SWD: run `identify.jlink`; at 100 kHz if needed; check J9 and J10 (the first recorded connection failure was these jumpers).
~~~

~~~text
   **Every off-pause is 3 s or less**, counted as the whole time the port is off, including the command's own latency and the VTref read. That page records two bench observations, reported there without logs and without a cause: on 5 November 2026 a port cut left 3.322 V on the board when read after 3 s, and on 7 November 2026 the supply came back about 4.4 s after a port cut. So before any cut, switch the port off, read `VTref` at the end of **that same pause** (the `ShowEmuList USB` command of section 5), and require about 0.000 V, then switch on and see about 3.3 V. **If `VTref` stays at its on value, stop: that is not a power cut** ([microSD physical gate](microsd-physical-gate.md), precondition 3). A longer pause is dangerous for the result: the supply can return, the board then boots unobserved and may erase a slot, and the state is blamed on the wrong cut. Whether a J-Link start and `ShowEmuList` fit inside 3 s is not known (section 10).
~~~

~~~text
| T7 | Not run: needs M9 | | | | |
~~~

~~~text
## 10. Open questions for the first bench session
~~~

## `docs/secure-boot-verification-ladder.md`

~~~text
> **Read this first / then:** the [boot overview](boot-overview.md) and the [secure boot and update review](secure-boot-and-update-review.md), then this page. People who will bring up a product board continue with the [product board hand-off checklist](secure-boot-product-board-handoff.md).
~~~

~~~text
| Next step | The product team on the product board, after the board owner supplies the inputs of the [hand-off checklist](secure-boot-product-board-handoff.md), and after the owner decides D2 and the first-stage issue. Crux supplies the checkers, the porting guide and the simulator results. |
~~~

~~~text
The product team's final verification covers what only L5 proves: ROM boot of the first stage from the eMMC boot partition, the eMMC provisioning on the product's wiring, HAB in closed configuration with the product's keys and fuses, hardware anti-rollback, power cuts on the product's supply, the product's recovery path and the update over the product's network. The [hand-off checklist](secure-boot-product-board-handoff.md) lists what to supply and the order to work in.
~~~

## `docs/secure-management-review.md`

~~~text
Status: a guide for a reviewer who must judge the secure communication and management stack of Crux for a real product, from the documents alone. It adds no behaviour and no decision. Each claim cites the code, a test or a document that was read on `origin/main` for this guide, and a claim that could not be checked is marked **unverified**. The bench checks that go with it are in the [board test procedure](secure-management-board-test-procedure.md). Terms are in [the glossary](management-glossary.md), and the product integration steps are in [secure management in a product](management-in-a-product.md).
~~~

## Lines edited after the independent review

`docs/decisions/0002-platform-direction-zephyr-execution-crux-services.md`:

~~~text
8. **P8. `README.md:5` is reworded:** Embedded Linux is not planned for the foreseeable future, and if needed it would be designed at the service boundary.
~~~

`docs/decisions/0002-platform-direction-zephyr-execution-crux-services.md`:

~~~text
1. Documentation: `docs/architecture.md`, `docs/native-interface-policy.md`, `docs/thread-sync.md`, `docs/messaging-contract.md`, `docs/serial-contract.md`, `docs/component-readiness.md`, `README.md:5` (P8) and `README.md:9,14-15`.
~~~

`docs/decisions/0003-p9-result-services-keep-narrow-thread-sync.md`:

~~~text
5. **R5. P8, new wording.** An Embedded Linux integration is expected. It will be designed at the service boundary when its first product is defined. No date is set. The Linux providers remain test providers (P7) until then. The text of `README.md:5` and `:37` follows this wording in its own change.
~~~

`docs/decisions/0003-p9-result-services-keep-narrow-thread-sync.md`:

~~~text
1. Documentation that still says P9 is undecided or that Embedded Linux is not planned: `README.md:5,37`, `docs/architecture.md`, `docs/thread-sync.md` (its freeze notice and the remark at `:150` that workers may become native threads under P9), and the freeze notices of `docs/messaging-contract.md` and `docs/serial-contract.md`.
~~~

`docs/decisions/README.md`:

~~~text
- Each record has a status line: **Proposed**, **Accepted** (with the owner's words, their date and where they were given), **Amended by ADR-NNNN** (the body stays and the later record names what it changes), **Superseded by ADR-NNNN** or **Withdrawn**.
~~~
