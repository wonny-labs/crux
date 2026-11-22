# Layout of `samples/`: proposal

Status: **proposal, for review in a Draft PR. Not adopted.** Nothing here is moved, renamed or deleted. It changes no
protected path, no CTest name and no Twister id. Every change it describes waits for the owner's decisions in
[section 9](#9-decisions-for-the-owner); the owner approves the concrete rename and delete lists and the protected
files before any change.

Baseline: `main` at `2d8553e2`. The Zephyr readings below were made in a local checkout at
`684c9e8f32e4373a21098559f748f06915f950c9` (v4.4.0). `west.yml` pins v4.4.2; the sample rules and Twister options
quoted should be rechecked at the pin before they are relied on.

Owner input taken into this version (2026-11-22, relayed by the Crux main session): names as explicit as `tcp_echo`
or `hello_world`; only a few representative starter samples, chosen by platform concept rather than by recent
features; power-loss and replay scenarios belong in `tests/`; clean up all old milestone names such as `m3`; consider
removing `samples/controller`; explain how samples relate to platform verification.

## Problem

`samples/` mixes five kinds of folder (the classification table in [`samples/README.md`](../../samples/README.md)), and
only some of them are samples in the sense a reader expects: something that builds and runs on its own and shows one
thing. The main cases:

- **`samples/controller`** has the same name as the product repository `crux-controller`, but its default
  configuration is a finite 20-cycle Time observation on a 100 ms periodic schedule. It is not a controller product.
- The same folder holds the board-only probes: nine `m3*.conf` files, `m3-network.overlay` and `m3_main.c` with its
  sources. `M3` is a historical Pilot milestone name, and the probes test devices, networking and health on the EVKB;
  they are tests, not samples.
- `controller/core`, `controller/include`, `controller/system` and `controller/configuration` are building blocks that
  only tests or the two controller programs compile.
- Of the 16 top-level folders, 4 are building blocks as a whole (`logging`, `serial`, `messaging`, `web_project`), and
  `controller` and `networking` contain more. 8 are board-only images as a whole, most of them probe, power-cut or
  formatter test images.
- Only `time/` and `controller/zephyr/` have a `sample.yaml`. Seven board-only folders have a `testcase.yaml` with
  `crux.sample.*` ids. Four top-level folders have a README.
- No sample shows the platform concepts a new user needs first: how a consumer links Crux, how a composition picks a
  provider, how one portable source runs on Linux Host and on `native_sim`.

## 1. Current inventory

Counted with `git grep -l -E "samples/<folder>([/\"' )\`]|$)"` on the baseline, excluding the folder itself and
`package-lock.json`. "Evidence" means files under `docs/evidence/` or `docs/baseline.md`: protected accepted records,
which stay unchanged and keep naming the old paths. "Protected (live)" lists the other files on the protected paths of
[`AGENTS.md`](../../AGENTS.md#protected-paths) that would have to change. "Other" counts the remaining files
(source, CMake, tests, docs, `web/`). The pattern misses references written as alternations or path fragments, such
as `^samples/(storage_[a-z_]+|flash_safety_poc|product_template)/` in `scripts/measure-tidy-coverage.py` and
`samples/time|...` in `scripts/check-dependencies.sh`; those were found by a second search for the folder names in
`scripts/` and are added to the rows below.

| Folder | Kind (from `samples/README.md`) | Evidence | Protected (live) | Other |
| --- | --- | --- | --- | --- |
| `time/` (Zephyr app) and `time/host/` | Runnable Zephyr application; runnable Linux Host program | 18 | `scripts/build-debug-target.sh`, `scripts/build-target.sh`, `scripts/check-host-sample.sh`, `scripts/check-native-interfaces.py`, `scripts/measure-tidy-coverage.py`, `scripts/test-zephyr-time.sh`, `scripts/check-dependencies.sh` (a negative check: the Zephyr module must not name `samples/time`; no change needed) | 17, incl. root `CMakeLists.txt`, `.vscode/tasks.json`, `tests/time/zephyr/CMakeLists.txt`, three `tests/build/` tests |
| `controller/zephyr/`, default `prj.conf` | Runnable Zephyr application | 106 for the whole folder | `scripts/test-controller.sh`, `scripts/check-boot-config.py`, `scripts/test-boot-composition.sh` | 64 for the whole folder, incl. root `CMakeLists.txt`, `tests/target/check_boot_images.sh`, `tests/target/check_boot_reproducibility.sh`, `tests/target/compare-mcuboot-crypto-backends.sh` (the boot checks build the default controller as their application) |
| `controller/zephyr/`, `m3*.conf`, `m3-network.overlay`, `m3_main.c` and the probe sources | Board-only application | (in the 106) | `scripts/test-controller-integration.sh`, `scripts/test-m3.sh` (historical alias that `exec`s the former), `scripts/test-m3-rt1170.sh`, `scripts/test-networking.sh`, `scripts/test-networking-physical.sh`; `scripts/measure-tidy-coverage.py` classifies the probe sources by their `zephyr` path segment, which a move loses | `tests/controller_m3`, `tests/controller_integrated`, `tests/controller_network`, `tests/controller_network_stack`, `tests/native/{integrated_output,logger_phase,network_output_burst,mdio_completion}`, `tests/networking_physical`, `tests/zephyr/management_rt1060_compile`, `samples/management_rt1060_mbed/CMakeLists.txt`, `tests/build/test_m3_*.py`, `tests/target/capture_m3_integrated.py` |
| `controller/host/` | Runnable Linux Host program | (in the 106) | `.github/workflows/host.yml` (uploads `build/linux/debug/samples/controller/host/controller.log`) | root `CMakeLists.txt` (`CRUX_BUILD_REFERENCE_CONTROLLER`), `docs/first-hour.md` |
| `controller/core/`, `controller/include/` | Building block | (in the 106) | `scripts/check-native-interfaces.py` | root `CMakeLists.txt` (`crux_controller_core`), `tests/controller` |
| `controller/system/` | Building block | (in the 106) | `scripts/test-system.sh`, `scripts/check-native-interfaces.py` | `tests/system_consumer/` (3 files), `tests/build/test_system_composition.py` |
| `controller/configuration/` | Building block | (in the 106) | `scripts/check-native-interfaces.py` | `tests/configuration/CMakeLists.txt` |
| `networking/host/`, `networking/zephyr/`, `networking/client.*` | Runnable Linux Host program; board-only application; building block | 15 | `scripts/check-native-interfaces.py`, `scripts/check-networking-dependencies.py`, `scripts/compile-networking-cpp-probe.py`, `scripts/run-host-sample.py`, `scripts/test-networking.sh` | 15, incl. root `CMakeLists.txt`, `tests/networking`, `tests/networking_zephyr` |
| `messaging/` | Building block | 2 | `scripts/check-native-interfaces.py`, `scripts/test-messaging.sh` | 7, incl. `tests/messaging_consumer`, `tests/consumer_poc` |
| `logging/` | Building block | 1 | `scripts/check-native-interfaces.py` | 5, incl. `tests/logging_consumer`, `tests/logging/zephyr/consumers.cmake` |
| `serial/` | Building block | 8 | `scripts/check-native-interfaces.py` | 6, incl. `tests/serial_consumer` |
| `flash_safety_poc/` | Board-only application | 3 | `scripts/test-flash-poc.sh`, `scripts/measure-tidy-coverage.py` (pattern) | 1 (`docs/flash-safety-poc.md`) |
| `management_rt1060_mbed/` | Board-only application | 0 | `scripts/test-management-mbed-rt1060.sh` | 9, incl. two `tests/build/` tests |
| `storage_emmc/` | Board-only application | 2 | `scripts/test-file-emmc-compile.sh`, `scripts/measure-tidy-coverage.py` (pattern) | 21, incl. `tests/native/file_emmc_composition`, `tests/native/configuration_settings_reliance`, `samples/storage_reliance_sd/CMakeLists.txt` |
| `storage_reliance_sd/` | Board-only application | 1 | `scripts/test-file-emmc-compile.sh`, `scripts/test-storage-emmc.sh`, `scripts/measure-tidy-coverage.py` (pattern) | 11, incl. `tests/native/reliance_stage_a/run_rehearsal.py` |
| `storage_sd/` | Board-only application | 3 | `scripts/test-file-rt1060-compile.sh`, `scripts/measure-tidy-coverage.py` (pattern) | 25, incl. the three other `storage_sd_*` CMake files, seven `tests/native/file_sd_*` folders |
| `storage_sd_interrupt/` | Board-only application (power-cut test image) | 3 | `scripts/test-file-rt1060-compile.sh`, `scripts/test-storage-simulators.sh`, `scripts/measure-tidy-coverage.py` (pattern) | 13, incl. `tests/native/reliance_stage_a/test_rehearsal.py` (imports its `host/` capture script) |
| `storage_sd_probe/` | Board-only application (physical-gate probes) | 1 | `scripts/test-file-rt1060-compile.sh`, `scripts/measure-tidy-coverage.py` (pattern) | 7 |
| `storage_sd_replace/` | Board-only application (power-cut test image) | 2 | `scripts/test-file-rt1060-compile.sh`, `scripts/test-storage-simulators.sh`, `scripts/measure-tidy-coverage.py` (pattern) | 11 |
| `web/angular/`, `web/preact/` | Web front end | 0 | `.github/workflows/web.yml`, `scripts/test-native-composition.sh` | 18, all in `web/` and `docs/` |
| `web_project/` | Building block | 0 | none | 8, incl. `tests/web/project_sample`, `tests/build/test_project_sample.py`, `tests/build/test_web_routes.py` |

Folder-wide references that are not to one folder: `scripts/check-cli-session-commands.py`,
`scripts/check-ssh-boundaries.py`, `scripts/check-web-routes.py`, `scripts/measure-tidy-coverage.py` and
`scripts/tidy-sources.py` scan the whole `samples/` root (all protected). Moving code from `samples/` into `tests/` can
change what they scan; each move PR checks this.

### Test names that carry sample paths or names

| Kind | Name | Defined in |
| --- | --- | --- |
| CTest | `Sample.TimeHost` | `samples/time/host/CMakeLists.txt` |
| CTest | `Sample.NetworkingHost` | `samples/networking/host/CMakeLists.txt` |
| CTest | `Controller.HostScenario` (label `sample`) | `samples/controller/host/CMakeLists.txt` |
| CTest | `Configuration.ControllerScenario` | `tests/configuration/CMakeLists.txt` |
| CTest | `Messaging.ControllerConsumer` | `tests/messaging_consumer/CMakeLists.txt` |
| CTest | `Web.project_sample` | `tests/web/project_sample/CMakeLists.txt` |
| Twister, `sample.yaml` | `crux.sample.time.shell`, `crux.sample.controller.basic` | `samples/time/`, `samples/controller/zephyr/` |
| Twister, `testcase.yaml` | `crux.sample.management_rt1060_mbed` | `samples/management_rt1060_mbed/` |
| Twister, `testcase.yaml` | `crux.sample.storage_emmc` and `.start`, `.settings` | `samples/storage_emmc/` |
| Twister, `testcase.yaml` | `crux.sample.storage_reliance_sd` and `.start`, `.append`, `.replace`, `.format`, `.native`, `.native.{start,append,replace,format}` | `samples/storage_reliance_sd/` |
| Twister, `testcase.yaml` | `crux.sample.storage_sd` and `.start`; `crux.sample.storage_sd_interrupt` and `.test`; `crux.sample.storage_sd_probe` and `.stack`, `.removal`; `crux.sample.storage_sd_replace` and `.test` | the four `samples/storage_sd*` folders |

The Twister ids are asserted by protected scripts: `scripts/test-file-emmc-compile.sh` (eMMC and Reliance ids),
`scripts/test-file-rt1060-compile.sh` (microSD ids) and `scripts/test-storage-emmc.sh` (Reliance `native` ids). Docs that
name ids include `docs/component-readiness.md`, `docs/emmc-reliance-composition.md`, `docs/microsd-composition.md`,
`docs/plans/configuration-persistence-spike.md` and `tests/README.md`.

### Build directory names

Scripts derive build folders from the old names, for example `build/zephyr/controller-{normal,missing-rtc,evkb}`
(`scripts/test-controller.sh`) and `build/zephyr/m3-<profile>-evkb` (`scripts/test-controller-integration.sh`). Docs
and evidence quote them. A rename should change them together with the script, or keep them and say so.

## 2. Conventions of reference projects

### Zephyr

Read in the local Zephyr tree (v4.4.0) unless a URL is given.

- **Area folders.** `samples/` is grouped by area: `basic/`, `kernel/`, `subsys/<subsystem>/` (for example
  `subsys/fs/`, `subsys/logging/`), `net/`, `drivers/`, `boards/<vendor>/<board>/<sample>/` (for example
  `boards/nxp/mimxrt1060_evk/system_off/`), and `application_development/`. Shared material for an area sits in a
  `common/` folder (`samples/net/common/`).
- **Names say what the sample shows**: `blinky`, `button`, `threads`, `dhcpv4_client`, `fatfs_fstab`, `system_off`.
- **Criteria** (`samples/sample_definition_and_criteria.rst`): a sample is "a concise Zephyr application" that gives an
  overview of a feature. It "must not be used to test features or verify platforms", must not use Ztest, and does not
  test negative or edge cases; that work goes to `tests/`. Every sample has a YAML file, builds in Twister, and is not
  marked build-only: it should "build *and* run on the documented platforms", using the `harness` option to skip
  execution where needed. Its default configuration is in `prj.conf` and works on all supported platforms, without
  relying on `extra_args`. `platform_allow` lists only verified platforms, which the README names. Every sample has a
  `README.rst` with overview, requirements, building and running, and sample output.
- **Ids.** `doc/develop/test/twister.rst`: a scenario id starts with a section name followed by subsections
  separated by dots, and is unique in its file; the full name is `<application path>/<scenario id>`. Samples use
  `sample.<area>.<name>` (`sample.basic.blinky`, `sample.kernel.synchronization`,
  `sample.boards.mimxrt1060_evk.system_off`). Tests use `<area>.<name>` (`kernel.timer`, `filesystem.fat.api`).
- **Layout of one sample**: `CMakeLists.txt`, `prj.conf`, `sample.yaml`, `README.rst`, `src/`, `boards/`
  (`samples/basic/blinky/`).

Crux docs are Markdown, so a Crux sample has `README.md` instead of `README.rst`.

### NXP MCUXpresso SDK

Read on GitHub on 2026-11-22. Not checked against an installed SDK.

- The older examples repository (now `nxp-mcuxpresso/legacy-mcux-sdk-examples`, archived) is grouped **by board
  first**: `<board>/<category>/<example>`. Under `evkbmimxrt1060/` the categories include `demo_apps`,
  `driver_examples`, `rtos_examples`, `cmsis_driver_examples`, `component_examples`, `freertos_examples`,
  `lwip_examples`, `mbedtls_examples`, `sdmmc_examples`, `usb_examples`, with the board files (`board.c`,
  `clock_config.c`) beside them. ([repository](https://github.com/nxp-mcuxpresso/legacy-mcux-sdk-examples/tree/main/evkbmimxrt1060))
- The current repository `nxp-mcuxpresso/mcuxsdk-examples` is grouped **by category first** (`demo_apps`,
  `driver_examples`, `freertos_examples`, `cmsis_driver_examples`, `usb_examples` ...) with board enablement files in
  `_boards/<board>/` and shared files in `_common/`. ([repository](https://github.com/nxp-mcuxpresso/mcuxsdk-examples))
- Driver examples are named `<peripheral>/<feature>` (`dsc_rgpio/led_output`, `dual_adc/interrupt`); demos have flat
  names (`hello_world`, `led_blinky`). The one example opened has `readme.md` with a supported-boards list,
  `example.yml`, `CMakeLists.txt` and `prj.conf`.
- **Unverified:** whether every example has a readme, and whether one example source serves several boards through
  `_boards/`. The SDK's own examples index page was not read.

### First samples a new user runs

Zephyr, read in the local tree (v4.4.0). The getting-started guide builds `samples/basic/blinky` and names
`hello_world` as the alternative for a board without an LED (`doc/develop/getting_started/index.rst`).

| Sample | Id in its `sample.yaml` | Runs without a board |
| --- | --- | --- |
| `samples/hello_world` | `sample.basic.helloworld` | yes, `native_sim` |
| `samples/basic/blinky`, `samples/basic/button` | `sample.basic.blinky`, `sample.basic.button` | no, needs an LED or button |
| `samples/basic/threads` | `sample.basic.threads` | no, needs LEDs |
| `samples/synchronization`, `samples/philosophers` | `sample.kernel.synchronization`, `sample.kernel.philosopher` | yes |
| `samples/subsys/shell/shell_module` | `sample.shell.shell_module` | yes, `native_sim` |
| `samples/subsys/logging/logger` | `sample.logger.basic` | yes, `native_sim` |
| `samples/drivers/uart/echo_bot` | `sample.drivers.uart` | `qemu_x86` |
| `samples/net/sockets/echo_server`, `echo_client` | `sample.net.sockets.echo_server`, `sample.net.sockets.echo_client` | `qemu_x86` |
| `samples/subsys/settings` | `sample.subsys.settings.nvs` | yes, `native_sim` |
| `samples/subsys/fs/fs_sample`, `littlefs` | `sample.filesystem.fat_fs`, `sample.filesystem.littlefs` | board or emulated disk |

NXP MCUXpresso SDK, read on GitHub on 2026-11-22 in
[`mcuxsdk-examples`](https://github.com/nxp-mcuxpresso/mcuxsdk-examples): `demo_apps/hello_world` (its readme calls it
a sanity check for new build environments and board bring-up), `demo_apps/led_blinky`, `driver_examples/gpio/led_output`,
`driver_examples/lpuart/interrupt`, `freertos_examples/freertos_hello`, `sdmmc_examples/sdcard_fatfs`. **Unverified:** a
`demo_apps/shell` example (not in the part of the listing that was read); an lwIP TCP echo example is named
`lwip_ipv4_ipv6_echo`, not `tcpecho`; the repository README does not say which example to run first.

Pattern in both: a first example that only proves the build and the console (`hello_world`), then one example per
basic capability, named by what it does (`blinky`, `echo_server`, `led_output`, `sdcard_fatfs`).

### What Crux takes from them

Zephyr's rules fit Crux directly, because Crux samples are Zephyr applications and Twister already runs them. From the
NXP SDK, Crux takes one idea only: board-specific images live under a board folder, apart from portable examples.
Zephyr's `samples/boards/<vendor>/<board>/` already expresses that, so no NXP-style top-level categories are proposed.
Names follow both: they say what the sample does and read well without their folder (`hello_crux`, `tcp_udp_echo`).

## 3. Samples and platform verification

### Zephyr

- **Samples are documentation that must keep building and running.** The criteria
  (`samples/sample_definition_and_criteria.rst`) say samples "must not be used to test features or verify platforms",
  must not use Ztest or `zassert`, and should check their output against an expected value "to have some level of
  testing for the sample itself"; a sample run "should not replace dedicated and comprehensive tests ... in the
  `tests/` folder". In the local tree 230 of the 610 tracked `sample.yaml` files set `harness: console` (`git ls-files 'samples/**/sample.yaml'`, then `grep -l`).
- **Twister runs samples and tests together.** By default it searches both `samples/` and `tests/`
  (`scripts/pylib/twister/twisterlib/environment.py`, option `--testsuite-root`). `integration_platforms` limits a
  scenario to a few platforms when Twister runs with `--integration` (`doc/develop/test/twister.rst`), and the pull
  request job in `.github/workflows/twister.yaml` passes `--integration`. So in CI every sample is built, and run where
  a simulator or emulator such as `native_sim` or `qemu_x86` is its integration platform, as a smoke check.
- **Functional and regression verification lives in `tests/`** (1113 tracked `testcase.yaml` files, `git ls-files 'tests/**/testcase.yaml'`), mostly
  Ztest suites, with ids such as `kernel.timer` and `filesystem.fat.api`. A `build_only` scenario is never run, and the option is reserved for code that is only built (`twister.rst`).

### NXP MCUXpresso SDK

No public NXP source read for this proposal says how SDK examples are tested. The one example opened has an
`example.yml`, whose fields were not read. **Unverified.**

### Crux today

- Runnable samples carry the Twister tag `sample` (`west twister -T crux-pilot/samples -t sample`) and CTest label
  `sample` (`ctest --preset host-debug -L sample`); `samples/README.md` describes both.
- Most verification already lives in `tests/` (61 `testcase.yaml` files, GoogleTest suites, Python checks under
  `tests/build/`, replay tools under `tests/native/`) and is driven by `scripts/check-*.sh` and `scripts/test-*.sh`.
- But `samples/` also holds code whose only purpose is verification: building blocks that tests compile, power-cut and
  probe images, a formatter, and the Reliance Edge `native` rehearsal entries that fail without the optional west
  group. The boot checks use the controller sample as their MCUboot application.

### Recommendation

1. **Samples are documentation with a smoke check.** Each runnable sample has a console regular expression (Twister)
   or a CTest output check, so CI catches a sample that no longer builds or runs. A sample never asserts platform
   behaviour beyond its own output.
2. **Platform verification lives in `tests/`**: unit tests (GoogleTest, Ztest), composition images, power-cut and
   replay tools, consumer-boundary checks.
3. **Board qualification images are separate** from both, under `tests/board_images/`, built in CI and run only under
   an approved board procedure.
4. A check that needs "some real application" (the boot checks, the consumer-boundary checks) uses a fixture
   application under `tests/`, not a sample, so a sample can change without moving a qualification baseline.

## 4. Starter samples

### Choice by platform concept

| Concept a new user needs | Proposed starter | What it shows | Runs without a board |
| --- | --- | --- | --- |
| A minimal consumer | **`samples/hello_crux`** | A Zephyr application that links one Crux target (`crux::time`), makes one public call (`crux_realtime_init`, then a read that prints "Time unset"), and prints a ready line. Its README walks through the workspace, the module, the target and the consumer boundary. A `host/` program builds the same `main` logic on Linux Host | yes, `native_sim` and Linux Host |
| Provider selection | **`samples/file/file_write_read`** | One source writes and reads back a file through `crux/file.h`; two scenarios pick the provider by Kconfig fragment only: the VFS simulator (`CONFIG_CRUX_FILE_SIMULATOR`) and FatFs on a RAM disk (`CONFIG_CRUX_FILE_FATFS_SIMULATOR`) | yes, `native_sim` |
| One source, two compositions | `hello_crux` covers it (the `host/` program); `time_shell` shows it at feature size | The same portable code under Zephyr and under Linux Host | yes |
| The product shape | No new sample: point to [`templates/product`](../../templates/product/README.md) | Application policy in `domain/`, platform mechanisms through Crux, the product as its own west manifest | `native_sim` |
| First board step | No Crux sample: Zephyr's `samples/basic/blinky` on the EVKB | That the board and probe work before Crux is involved | no |

Feature samples stay optional, minimal and generic:

| Feature sample | From | Shows |
| --- | --- | --- |
| `samples/time/time_shell` | today's `samples/time` | Time read, set and step from a shell, on `native_sim` and Linux Host |
| `samples/time/time_periodic_task` | the default scenario of `samples/controller` (if kept, [section 6](#6-samplescontroller-keep-slim-or-remove)) | A task released every 100 ms that reads Time |
| `samples/networking/tcp_udp_echo` | today's `samples/networking` | One TCP and one UDP echo exchange with a peer, on Linux Host and on the EVKB |

Not proposed as samples: configuration persistence across a restart (on `native_sim` it needs Reliance Edge from the
optional, GPL-licensed west group) and power-loss-safe file replacement. Both are platform verification and stay in
`tests/`. A generic configuration sample can be added when a provider exists that runs without the optional group.

### Limits of the starters

- `hello_crux` cannot print a Crux version: Crux has no version API, and adding one is a public interface
  ([D2](#9-decisions-for-the-owner)).
- Both File providers in `file_write_read` are marked Experimental in `zephyr/Kconfig` ("candidate"). The sample would
  be the first non-test consumer of them and must say so in its README ([D3](#9-decisions-for-the-owner)).
- `templates/product` is the product shape already; a second copy under `samples/` would drift.

### Lead example

Recommendation: `hello_crux` leads, `time_shell` is second. `hello_crux` is the smallest thing that proves the
workspace, the module and the link; Time is a good second step because it is the oldest, best-tested component and its
sample already runs on both compositions. Until `hello_crux` exists, Time stays the first-hour sample.

## 5. Proposed layout

### Rules

1. A folder under `samples/` is a sample only if it builds on its own, shows one thing, and has a `README.md` and a
   `sample.yaml` with a console regular expression or, for a Linux Host program, a CTest output check. A board sample
   names its board in `platform_allow` and its README.
2. Starter samples sit at the top of `samples/`. Feature samples sit under an area named after the Crux component they
   show: `samples/<component>/<name>/`. Board-only samples sit under `samples/boards/nxp/<board>/<name>/`.
3. Names say what the sample does and read well alone: `hello_crux`, `time_shell`, `tcp_udp_echo`, `file_write_read`.
4. A Linux Host program of a sample stays inside the sample as `host/`, as `samples/time/host/` does today.
5. Probe, power-cut and other board test images, and building blocks that only tests compile, move to `tests/`. Board
   test images go together under `tests/board_images/<name>/`; a building block moves into the test folder that
   compiles it.
6. Ids: `crux.sample.<area>.<name>[.<variant>]` for samples (Zephyr's form with the existing `crux.` prefix), and
   `crux.<area>.<name>` for tests, as most existing `tests/**/testcase.yaml` files already do (`tests/consumer_poc` uses `consumer_poc.periodic`).
7. No historical milestone names (`m1` ... `m8`, `poc`) in live paths, ids or symbols ([section 7](#7-old-milestone-names)).

### Mapping

| Old path | New path | New id or test name | Why |
| --- | --- | --- | --- |
| (new) | `samples/hello_crux/` with `host/` | `crux.sample.hello_crux`, CTest `Sample.HelloCruxHost` | Starter: minimal consumer |
| (new) | `samples/file/file_write_read/` | `crux.sample.file.file_write_read.simulator`, `.fatfs_ram_disk` | Starter: provider selection |
| `samples/time/` (Zephyr app, `host/`, `include/`, `src/`) | `samples/time/time_shell/` | `crux.sample.time.time_shell` (was `crux.sample.time.shell`); CTest `Sample.TimeHost` → `Sample.TimeShellHost` | Explicit name |
| `samples/controller/zephyr/` default and `samples/controller/host/` | `samples/time/time_periodic_task/` with `host/` (slim option) | `crux.sample.time.time_periodic_task` (was `crux.sample.controller.basic`); CTest `Sample.TimePeriodicTaskHost` (was `Controller.HostScenario`) | [Section 6](#6-samplescontroller-keep-slim-or-remove) |
| `samples/controller/core/`, `include/` | `samples/time/time_periodic_task/common/` (slim) or `tests/controller/` (remove) | library `crux_time_periodic_task_core` (was `crux_controller_core`) | Section 6 |
| `samples/controller/zephyr/` probe set: `m3_main.c`, `device_input.*`, `native_logger.*`, `network_*`, `mdio_completion.cmake`, `m3*.conf` | `tests/board_images/evkb_integration_probe/` | build folders `build/zephyr/evkb-integration-probe-<profile>` | Board probes test devices, network and health |
| `samples/controller/zephyr/CMakeLists.txt` | split: the default branch to the periodic sample, the probe branch (`CRUX_CONTROLLER_M3`, `CRUX_M3_SOURCE`) to the probe folder | | It builds both today |
| `samples/controller/zephyr/Kconfig` | to the probe folder only (all its symbols are probe symbols); the periodic sample needs none | | Kconfig names: [D16](#9-decisions-for-the-owner) |
| `samples/controller/zephyr/boards/*.conf` | copied to both folders, each trimmed to what its image uses | | The EVKB `.conf` serves the default image and the probes |
| `samples/controller/zephyr/m3-network.overlay` | `samples/boards/nxp/mimxrt1060_evk/common/network.overlay` | | Shared by the probes, the management image, the networking scripts and a private consumer ([D8](#9-decisions-for-the-owner)) |
| `samples/controller/system/` | `tests/system_consumer/scenario/` | | Only `tests/system_consumer` compiles it |
| `samples/controller/configuration/scenario.c` | `tests/configuration/controller_scenario.c` | CTest `Configuration.ControllerScenario` (unchanged) | Only `tests/configuration` compiles it |
| `samples/networking/` (`client.*`, `host/`, `zephyr/`) | `samples/networking/tcp_udp_echo/` (Zephyr app at the root, `host/`, `common/client.*`) | new `crux.sample.networking.tcp_udp_echo` (EVKB, console harness, run only with a peer); CTest `Sample.NetworkingHost` → `Sample.TcpUdpEchoHost` | Explicit name; one sample, two compositions |
| `samples/messaging/` | `tests/messaging_consumer/scenario/` | CTest `Messaging.ControllerConsumer` (unchanged) | Building block; `tests/consumer_poc` follows |
| `samples/logging/` | `tests/logging_consumer/scenario/` | | Building block |
| `samples/serial/` | `tests/serial_consumer/scenario/` | | Building block |
| `samples/web_project/` | `tests/web/project_sample/project/` | CTest `Web.project_sample` (unchanged) | Building block ([D10](#9-decisions-for-the-owner)) |
| `samples/web/angular/`, `samples/web/preact/` | unchanged | | Already `area/name`; moving them touches `.github/workflows/web.yml` and `web/` tooling for no reader gain. Preact gains a README |
| `samples/management_rt1060_mbed/` | `samples/boards/nxp/mimxrt1060_evk/https_management_mbedtls/` | `crux.sample.boards.mimxrt1060_evk.https_management_mbedtls` | A complete board image a product copies from |
| `samples/storage_emmc/` | `samples/boards/nxp/mimxrt1060_evk/file_on_emmc/` | `crux.sample.boards.mimxrt1060_evk.file_on_emmc` and `.start`, `.settings` | Board composition of File on eMMC |
| `samples/storage_sd/` | `samples/boards/nxp/mimxrt1060_evk/file_on_sd_card/` | `crux.sample.boards.mimxrt1060_evk.file_on_sd_card` and `.start` | Board composition of File on microSD; three test images reuse its sources |
| `samples/storage_sd_interrupt/` (with `host/`) | `tests/board_images/sd_card_power_cut_append/` | `crux.file.sd_card_power_cut_append` and `.test` | Power-cut test image |
| `samples/storage_sd_replace/` (with `host/`) | `tests/board_images/sd_card_power_cut_replace/` | `crux.file.sd_card_power_cut_replace` and `.test` | Power-cut test image |
| `samples/storage_sd_probe/` | `tests/board_images/sd_card_stack_removal_probe/` | `crux.file.sd_card_probe` and `.stack`, `.removal` | Physical-gate probes |
| `samples/storage_reliance_sd/` | `tests/board_images/reliance_sd_card_stage_a/` | `crux.file.reliance_sd_card` and its eight variants | Stage A images and rehearsal |
| `samples/flash_safety_poc/` | `tests/board_images/flash_safety_check/` | | Compile-only Flash safety image of a historical experiment, inspected by a script; never programmed |

Result: `samples/` holds `hello_crux`, `file/file_write_read`, `time/time_shell`, `time/time_periodic_task` (if
kept), `networking/tcp_udp_echo`, `web/angular`, `web/preact`, and
`boards/nxp/mimxrt1060_evk/{https_management_mbedtls,file_on_emmc,file_on_sd_card,common}`.

The power-cut and probe image names above say what each image does (for example `storage_sd_interrupt` appends
fixed records and is meant to be cut during the append, `sd_interrupt.h`). The PR that moves each image checks its name
against the image's source and README once more.

### Board probe configurations

The probe folder `tests/board_images/evkb_integration_probe/` gets explicit configuration names:

| Old | New | What it selects |
| --- | --- | --- |
| `m3.conf` | `device_health_probe.conf` | SW5 GPIO and critical-work supervision, with test commands |
| `m3-normal.conf` | `without_test_commands.conf` | Removes the shell and fault-injection commands |
| `m3-network.conf` | `network_probe.conf` | Bounded IPv4 TCP/UDP transactions |
| `m3-integrated.conf` | `integrated_controller.conf` | Time, SW5, network, diagnostics and health together |
| `m3-mdio-completion.conf` | `mdio_completion_fix.conf` | The ENET MDIO completion patch |
| `m3-mdio-trace.conf` | `mdio_failure_trace.conf` | MDIO failure tracing |
| `m3-phy-diagnostic.conf` | `phy_diagnostic.conf` | PHY diagnostics |
| `m3-deferred-output.conf` | `deferred_output.conf` | Deferred console output |
| `m3-native-output.conf` | `native_output.conf` | Native console output |
| `m3_main.c` | `probe_main.c` | The probe entry point |

## 6. `samples/controller`: keep, slim or remove

### What each part covers today

| Part | Coverage it gives | Run by |
| --- | --- | --- |
| `controller/host/` | Host composition of the periodic scenario, with ASan/UBSan under `host-sanitize` | CTest `Controller.HostScenario` (`scripts/check-controller.py`), `scripts/check-host.sh` |
| `controller/zephyr/` default | `native_sim` run of the same scenario, normal and missing-RTC, and the EVKB cross-build | `crux.sample.controller.basic`, `scripts/test-controller.sh` |
| `controller/zephyr/` default as boot application | The MCUboot application for the boot checks (sysbuild image name `zephyr`) | `scripts/check-boot-config.py`, `scripts/test-boot-composition.sh`, `tests/target/check_boot_images.sh`, `tests/target/check_boot_reproducibility.sh`, `tests/target/compare-mcuboot-crypto-backends.sh` |
| `controller/core/`, `include/` | Portable schedule advance and health/readiness logic, 13 GoogleTest cases | `tests/controller` |
| Probe set (`m3*`) | EVKB device, network, integrated and diagnostic images; their output oracles | `scripts/test-controller-integration.sh`, `scripts/test-m3-rt1170.sh`, `tests/controller_m3`, `tests/controller_integrated`, `tests/controller_network`, `tests/controller_network_stack`, `tests/native/*`, `tests/build/test_m3_*.py`, `tests/target/*m3*` |
| `controller/system/` | A System health consumer scenario | `tests/system_consumer`, `scripts/test-system.sh` |
| `controller/configuration/` | A Configuration consumer scenario | `tests/configuration` (`Configuration.ControllerScenario`) |

`AGENTS.md` names `scripts/test-controller.sh` ("execution/reference-controller checks") and
`scripts/test-controller-integration.sh` (validation list), and `README.md` names `scripts/test-controller.sh`.

### Options

| Option | What happens | What is lost | Protected changes |
| --- | --- | --- | --- |
| **Keep** | Rename only (`m3` names) | Nothing; the name clash with crux-controller and the mix of sample and probes stay | the probe scripts |
| **Slim** (recommended) | The periodic scenario becomes the feature sample `samples/time/time_periodic_task` (Host and `native_sim`); the core goes with it; probes, `system/` and `configuration/` move to `tests/` (section 5); the boot checks get their own fixture application under `tests/boot_fixture/` built from the same scenario; `scripts/test-controller.sh` becomes `scripts/test-time-periodic-task.sh` | Nothing; the folder name `controller` disappears | the scripts in [section 8](#8-impact-and-migration), `.github/workflows/host.yml`, `AGENTS.md` and `README.md` lines that name `scripts/test-controller.sh` |
| **Remove** | No periodic sample. The scenario and its core move to `tests/time_periodic/` as a test (its Host CTest and its `native_sim` console check both kept); the boot fixture as in Slim; probes and building blocks as in Slim | The documentation value of a periodic-task example | as Slim |

No option deletes a test. `tests/controller` keeps its 13 cases, moved with the code they test, in every option.

Recommendation: **Slim.** A periodic task that reads Time is a common first need for a controller product and is
generic; it is the one part of `samples/controller` that is a sample. Everything else is verification and moves to
`tests/`. Alternative: **Remove**, if the owner wants the starter set to stay at the five rows of section 4; the
coverage is kept in `tests/`.

## 7. Old milestone names

Searched with `git ls-files` for path parts `m<digit>` and `git grep` for `M<digit>` symbols, CTest names and Twister
ids, outside `docs/evidence/`, `docs/baseline.md` and `docs/history/`. Those three stay unchanged: the first two are
protected accepted evidence, the third is the history record. No CTest name carries a milestone name.

| Name | Where | Action |
| --- | --- | --- |
| `m3*.conf` (9), `m3-network.overlay`, `m3_main.c` | `samples/controller/zephyr/` | Rename (section 5) |
| Kconfig ([D16](#9-decisions-for-the-owner)) `CRUX_CONTROLLER_M3`, `CRUX_M3_TEST_COMMANDS`, `CRUX_M3_NETWORK_PROBE`, `CRUX_M3_PHY_DIAGNOSTIC`, `CRUX_M3_INTEGRATED`, `CRUX_M3_MDIO_COMPLETION_FIX`, `CRUX_M3_MDIO_FAILURE_TRACE`, `CRUX_M3_DEFERRED_OUTPUT`, `CRUX_M3_NATIVE_OUTPUT`; compile definition `CRUX_M3_SOURCE` | `samples/controller/zephyr/Kconfig`, `CMakeLists.txt`; 38 live files name them (`git grep -lE 'CRUX_(CONTROLLER_)?M3'` outside evidence and history, with `Kconfig` and `CMakeLists.txt`), incl. `tests/build/`, `tests/target/`, `tests/native/`, `tests/controller_integrated/`, `docs/porting-to-a-new-board.md`, `patches/zephyr/README.md`, `patches/zephyr/nxp-enet-mdio-completion.patch`, and the component `components/system/ports/zephyr/CMakeLists.txt:20` (refuses `CRUX_CONTROLLER_M3` as a conflicting watchdog owner) | Rename to `CRUX_EVKB_PROBE` and `CRUX_EVKB_PROBE_*`, including the component check. `patches/zephyr/nxp-enet-mdio-completion.patch` tests `CONFIG_CRUX_M3_MDIO_FAILURE_TRACE` in eight added `#ifdef` lines, so the patch changes too, and with it the expected hash `PATCHED_SHA256` that `tests/native/mdio_completion/test_driver.py` asserts. That assertion changes because the approved behaviour (the symbol name) changes; without the patch change the trace would compile out silently |
| C functions `controller_m3_arm_allowed`, `controller_m3_fault_allowed`, constant `M3_ARM_REJECTED` | `samples/controller/include/controller_health.h` and users | Rename to `probe_arm_allowed`, `probe_fault_allowed`, `PROBE_ARM_REJECTED` |
| `scripts/test-m3.sh` | alias that `exec`s `scripts/test-controller-integration.sh` | Delete, after docs name the maintained script |
| `scripts/test-m3-rt1170.sh` | RT1170 cross-build of the probe | Rename `scripts/test-integration-probe-rt1170.sh` |
| `scripts/test-m5-integrated-smoke.sh` | integrated smoke | Rename `scripts/test-integrated-smoke.sh` |
| Build folders `build/zephyr/m3-<profile>-evkb` | `scripts/test-controller-integration.sh` | `build/zephyr/evkb-integration-probe-<profile>` |
| `tests/controller_m3/` (project `crux_m3_native_tests`, option `M3_GPIO_SCENARIO`, binding `vnd,m3-fault-gpio`) and ids `crux.m3.gpio_health`, `crux.m3.missing_gpio`, `crux.m3.read_error` | Ztest on `native_sim` | Rename `tests/probe_device_health/`, ids `crux.probe.gpio_health`, `.missing_gpio`, `.read_error`; option `PROBE_GPIO_SCENARIO`; binding `vnd,probe-fault-gpio` |
| `tests/m5_integrated/` and id `crux.m5.integrated_smoke` | integrated smoke image | Rename `tests/integrated_smoke/`, id `crux.integrated.smoke` |
| `tests/build/test_m3_*.py` (16), `tests/build/test_m5_*.py` (25) | Python checks of probe and bench output | Rename by subject, for example `test_probe_network_oracle.py`, `test_bench_program.py` |
| `tests/target/*m3*`, `*m5*` (26) | capture, oracle and preparation tools | Rename by subject, for example `capture_probe_network.py`, `bench_series.py` |
| `tests/build/fixtures/m5-real-captures/`, `fixtures/programmer-split/run3-program-03-program-m5.log` | recorded captures used as fixtures | Rename the folder or file only; contents unchanged |
| `docs/m3-validation.md`, `docs/m2-physical-verification.md`, `docs/m5-pilot-validation-plan.md`, `docs/platform-m1-readiness.md`, `docs/plans/m5-messaging-implementation.md`, `docs/plans/m5-networking-implementation.md`, `docs/plans/m5-networking-proposal.md`, `docs/plans/pre-m8-investigation-plan.md` | records and finished plans | Move to `docs/history/` with names unchanged; fix the links |
| `docs/superpowers/plans/*m5*`, `*m6*` | execution plans | Leave: the folder is already archived in `doc-links.toml` |
| `samples/flash_safety_poc/` (`poc`) | | Rename (section 5) |

The renames under `tests/` are not protected; the scripts are. Tests change names only; no assertion changes.

## 8. Impact and migration

### Protected files to change

Every row needs explicit owner approval for that file (AGENTS.md, protected paths). Listed by the PR that changes them.

| PR | Protected files |
| --- | --- |
| P2 building blocks | `scripts/check-native-interfaces.py`, `scripts/test-messaging.sh`, `scripts/test-system.sh`; check whether `scripts/check-cli-session-commands.py`, `scripts/check-ssh-boundaries.py`, `scripts/check-web-routes.py`, `scripts/measure-tidy-coverage.py`, `scripts/tidy-sources.py` still scan the moved files |
| P3a overlay and P3b controller and probes | `scripts/test-controller.sh` (renamed), `scripts/test-controller-integration.sh`, `scripts/test-m3.sh` (deleted), `scripts/test-m3-rt1170.sh` (renamed), `scripts/test-m5-integrated-smoke.sh` (renamed), `scripts/test-networking.sh`, `scripts/test-networking-physical.sh`, `scripts/check-boot-config.py`, `scripts/test-boot-composition.sh`, `scripts/check-native-interfaces.py`, `scripts/measure-tidy-coverage.py` (probe and `tests/controller_m3`, `tests/m5_integrated` patterns), `scripts/check-controller.py` (renamed with its test, content unchanged), `.github/workflows/host.yml`, `.github/workflows/zephyr.yml` (runs `scripts/test-controller.sh`, `scripts/test-m3-rt1170.sh`, `scripts/test-m5-integrated-smoke.sh`), `AGENTS.md` (the two validation lines), `CONTRIBUTING.md` only if it names a renamed script |
| P4 networking | `scripts/check-native-interfaces.py`, `scripts/check-networking-dependencies.py`, `scripts/compile-networking-cpp-probe.py`, `scripts/run-host-sample.py`, `scripts/test-networking.sh` |
| P5 board samples and images | `scripts/test-management-mbed-rt1060.sh`, `scripts/test-file-emmc-compile.sh`, `scripts/test-storage-emmc.sh`, `scripts/test-file-rt1060-compile.sh`, `scripts/test-storage-simulators.sh`, `scripts/test-flash-poc.sh` (renamed `scripts/test-flash-safety-check.sh`), `scripts/measure-tidy-coverage.py` (the `samples/(storage_...|flash_safety_poc...)` pattern) |
| P6 Time shell | `scripts/build-debug-target.sh`, `scripts/build-target.sh`, `scripts/check-host-sample.sh`, `scripts/check-native-interfaces.py`, `scripts/measure-tidy-coverage.py`, `scripts/test-zephyr-time.sh` |
| P1 starters | none expected; new samples are added to the existing sample checks, which may need `.github/workflows/*.yml` lines |

No change to `CMakePresets.json`, `.claude/`, `CLAUDE.md` or `tools/` is expected. `docs/evidence/`,
`docs/baseline.md` and `docs/history/` content is not edited (P7 adds moved records to `docs/history/`).

### CTest and Twister changes

- CTest: `Sample.TimeHost` → `Sample.TimeShellHost`, `Controller.HostScenario` → `Sample.TimePeriodicTaskHost`,
  `Sample.NetworkingHost` → `Sample.TcpUdpEchoHost`; new `Sample.HelloCruxHost`. The `sample` label stays.
- Twister: `crux.sample.time.shell` → `crux.sample.time.time_shell`; `crux.sample.controller.basic` →
  `crux.sample.time.time_periodic_task`; `crux.m3.*` → `crux.probe.*`; `crux.m5.integrated_smoke` →
  `crux.integrated.smoke`; the board images become `crux.sample.boards.mimxrt1060_evk.*` (samples) or `crux.file.*`
  (test images); new `crux.sample.hello_crux`, `crux.sample.file.file_write_read.*`,
  `crux.sample.networking.tcp_udp_echo`.
- The `sample` tag keeps meaning "runnable on `native_sim`", so `west twister -T crux-pilot/samples -t sample` keeps
  working. The Reliance Edge `native` rehearsal entries leave `samples/`, so the untagged run no longer fails without
  the `crux-reliance` group.
- The root `CMakeLists.txt` option `CRUX_BUILD_REFERENCE_CONTROLLER` becomes `CRUX_BUILD_TIME_PERIODIC_TASK_SAMPLE`,
  with the old name as a deprecated alias ([D11](#9-decisions-for-the-owner)).

### Consumer repositories (read-only check, 2026-11-22)

| Repository | What references Crux sample paths | Effect |
| --- | --- | --- |
| Private consumer A (runtime integration, `main`) | Two CMake files build with `$ENV{ZEPHYR_BASE}/../crux-pilot/samples/controller/zephyr/m3-network.overlay`; one board `.conf` and one review document name it, and that review already lists the overlay as a reach-in to a Crux path that is no contract | **Build break** when the overlay moves. The consumer reads Crux at a pinned SHA, so the break appears at its next repin |
| crux-controller (`main`, `979fd1e`) | Comments only: `app/boards/s4.overlay` (`m3_main.c`), `app/conf/s3.conf` (`storage_sd/prj.conf`), `app/conf/s6.conf` (`management_rt1060_mbed`), five files under `docs/findings/` | No build effect; the text names "the pinned revision" and stays true, but goes stale at the next repin |
| Private consumer B | none found | none |
| A private planning repository | Plans name `crux-pilot/samples/controller` as the reference controller | Planning text only |

The consumer repositories were not changed.

### Company copy

Crux also reaches a company copy through an export whose rules live in a private plan outside this repository. Two
points matter for this proposal; the details belong in that plan:

- The company copy already renamed the `m3` probe files in its own way (for example `probe_main.c`). Any GitHub
  rename to other names makes the next export resolve those files by hand ([D7](#9-decisions-for-the-owner)).
- Accepted evidence that keeps old paths is not exported. Moves export as moves, and removing milestone names from live
  paths helps the export's own checks.

Recommendation: land the layout PRs on GitHub first, then do one export that carries all of them.

### Step order

The steps P1–P7 used above are regrouped into pull requests with disjoint file sets in
[section 10](#10-implementation-plan), which is the order to follow.

## 9. Decisions for the owner

Under the owner's delegation of 2026-11-22 (relayed by the Crux main session), the Recommendation column is the
implementation plan of [section 10](#10-implementation-plan) unless the Crux main session changes a row.

| # | Decision | Recommendation | Reason | Alternative |
| --- | --- | --- | --- | --- |
| D1 | Starter set | `hello_crux`, `file/file_write_read`, then the optional feature samples `time/time_shell`, `time/time_periodic_task`, `networking/tcp_udp_echo`; product shape via `templates/product`; first board step via Zephyr's `blinky` | Covers the platform concepts (consumer, provider selection, two compositions, product shape) with two new samples; feature samples stay small | Fewer: only `hello_crux` and `time_shell` as starters, everything else feature or test |
| D2 | What `hello_crux` prints | One existing public call (Time init and read) and a ready line; no version | A version print needs a new public API | Add a `crux_version()` API first, as its own interface decision |
| D3 | Provider-selection sample on Experimental providers | Build `file_write_read` on the two File simulator providers and say in its README that both are Experimental | They are the only pair of providers that run on `native_sim` without the optional group | Wait for a stable provider pair; no provider-selection sample until then |
| D4 | Lead example | `hello_crux` first, `time_shell` second; Time stays first until `hello_crux` exists | The smallest proof of workspace, module and link comes first | Keep Time first and add `hello_crux` as an aside |
| D5 | Sample names | The explicit names of section 5 (`time_shell`, `time_periodic_task`, `tcp_udp_echo`, `file_on_emmc` ...) | Each says what it does and reads well without its folder; `time_periodic_task` says the API (Time) and the pattern (a periodic task), where `periodic_time` reads as a kind of time | Shorter names inside area folders (`time/shell`, `time/periodic_task`, `networking/echo`) |
| D6 | `samples/controller` | Slim (section 6) | Keeps the one generic part as a sample and moves verification to `tests/` without losing coverage | Remove: the scenario becomes a test, the starter set stays at section 4 |
| D7 | Probe configuration names | The explicit names of section 5 (`device_health_probe.conf`, `network_probe.conf` ...) with `probe_main.c` | Each says what it selects | The names the company copy already uses: an easier export, but less explicit |
| D8 | The shared EVKB network overlay | Move to `samples/boards/nxp/mimxrt1060_evk/common/network.overlay`, documented as a sample file and not a contract; private consumer A takes its own copy into its reference application before P3a (its own rules give board choices to that application) | Ends a reach-in that the consumer itself already lists, without a new Crux public interface | Publish it as a supported Crux board overlay (for example a Zephyr snippet): a public interface, needs its own decision |
| D9 | Old milestone names | The rename and delete list of section 7; records move to `docs/history/`; evidence untouched | Removes `m1`–`m8` from every live path, id and symbol | Rename only `samples/` and `scripts/` names now, `tests/` names later |
| D10 | `web_project` | Move into `tests/web/project_sample/`; a runnable project page sample is a later follow-up. `scripts/check-web-routes.py` scans `samples/` for exactly this kind of project (Issue #220), so the move PR extends its scan to the new path | No image packages it today, so it is not a sample | Keep it in `samples/` as a documented exception |
| D11 | Build option `CRUX_BUILD_REFERENCE_CONTROLLER` | Rename, keep the old name as a deprecated alias until the first tag | External builds may set it | Rename with no alias |
| D12 | Twister id prefix | Keep `crux.` (`crux.sample.<area>.<name>`) | Separates Crux scenarios from Zephyr's in one Twister run; existing tags and scripts keep their filter | Zephyr's bare `sample.<area>.<name>` |
| D13 | Samples and verification policy | Section 3: samples are documentation with a smoke check, verification in `tests/`, board images in `tests/board_images/`, checks that need an application use a fixture under `tests/` | Matches Zephyr; a sample can change without moving a qualification baseline | Let samples double as verification fixtures, as the boot checks do today |
| D14 | Approval scope | Approve P1–P7 as one work package, with the protected files of section 8, merge per PR after reviewer PASS and green CI | Each PR is small; one approval avoids a question per PR | Approve per PR |
| D15 | Order against the company export | All layout PRs first, then one export | One 3-way merge of the moved tree | Export after each PR |
| D16 | Kconfig symbols `CRUX_CONTROLLER_M3` and `CRUX_M3_*` | Rename to `CRUX_EVKB_PROBE` and `CRUX_EVKB_PROBE_*` in P3b, together with the component check, the Zephyr patch's `#ifdef` lines and its expected hash, the patch README and the tests | They are configuration names that a component refers to; renaming them later costs more | Keep the symbol names and rename only files, ids and folders; `m3` then stays in `.config` files |

## 10. Implementation plan

Definite plan under the owner's delegation. Each PR is a Draft PR from its own branch, reviewed by the `reviewer`
agent, merged after reviewer PASS and green CI within the delegation. Within one wave no two PRs touch the same file,
so a wave's PRs can run in parallel sessions; a later wave starts from `main` after the earlier wave has merged.
`docs/evidence/`, `docs/baseline.md` and `docs/history/` content is never edited. `AGENTS.md`, `CLAUDE.md` and
`.github/` change only in the held PR H.

Common rules for every PR:

- Moves use `git mv`, so history follows. Every moved folder gets a README (and a `sample.yaml` if it stays a sample)
  in the same PR. A moved README names its old path once.
- No test is deleted or weakened. A test that moves keeps its assertions; only names and paths change. Section 6 and
  the "where the coverage goes" column below say where each check goes.
- A renamed script keeps its old name as a one-line `exec` alias until PR H has switched the workflows and PR 10
  removes the aliases, so CI keeps running the same checks.
- Checks per PR: the scripts it changes, the scripts that run the moved code, `scripts/check-host.sh` (Host CI),
  `python3 scripts/check_docs.py`, the affected `tests/build/` tests, and `git grep` for every old path, which must
  return only evidence, history and this proposal. Zephyr scripts that need the Dev Container run in CI on the Draft PR
  (the local disk is too small for new heavy Docker work).

| Wave | PR | Content | Exact file set | Protected files | Where the coverage goes | Depends on |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **PR 1 shared tables** | Path tables accept both the old and the new paths; Markdown links from shared docs to sample folders become code spans or links to `samples/README.md`, so later moves break no link | `scripts/check-native-interfaces.py`, `scripts/measure-tidy-coverage.py`, `scripts/check-web-routes.py`, `tests/build/test_native_interfaces.py`, `tests/build/test_web_routes.py`, `samples/README.md`, `docs/architecture.md`, `docs/execution-profile.md`, `tests/README.md` | the three scripts | unchanged; tables cover both paths | — |
| 1 | **PR 2 starters** | New `samples/hello_crux` (Zephyr app plus `host/` built as a standalone consumer project) and `samples/file/file_write_read` (scenarios `.simulator`, `.fatfs_ram_disk`), test first: their console checks are written and fail first | `samples/hello_crux/**`, `samples/file/file_write_read/**`, new `scripts/test-hello-crux.sh` | none (new script) | new coverage | — |
| 2 | **PR 3 building blocks** | `samples/{logging,serial,messaging,web_project}` and `samples/controller/{system,configuration}` move into the tests that compile them | the six source folders; `scripts/test-messaging.sh`, `scripts/test-system.sh`; `tests/{logging_consumer,serial_consumer,messaging_consumer,system_consumer,consumer_poc}/**`, `tests/logging/zephyr/consumers.cmake`, `tests/configuration/CMakeLists.txt`, `tests/web/project_sample/**`, `tests/build/test_project_sample.py`, `web/README.md`; `docs/{configuration-validation,e2e-native-220,messaging-validation,serial-validation,static-analysis-coverage}.md` | `scripts/test-messaging.sh`, `scripts/test-system.sh` | same tests, same CTest names | PR 1 |
| 2 | **PR 4 Time and networking samples** | `samples/time` → `samples/time/time_shell`; `samples/networking` → `samples/networking/tcp_udp_echo` with a new `sample.yaml`; CTest `Sample.TimeShellHost`, `Sample.TcpUdpEchoHost`; Twister `crux.sample.time.time_shell` | `samples/time/**`, `samples/networking/**`, root `CMakeLists.txt`, `.vscode/tasks.json`, `scripts/{build-debug-target,build-target,check-host-sample,test-zephyr-time,test-networking}.sh`, `scripts/{run-host-sample,check-networking-dependencies,compile-networking-cpp-probe}.py`, `tests/build/test_debug_target.py`, `tests/build/test_run_host_sample.py`, `tests/networking/CMakeLists.txt`, `tests/networking_zephyr/CMakeLists.txt`, `tests/time/zephyr/CMakeLists.txt`, `docs/{time-contract,networking-contract,implementation-status}.md` | the eight scripts | same programs and checks under new names | PR 1 |
| 3 | **PR 5 controller split** | Slim option of section 6: `samples/time/time_periodic_task` (default scenario, `host/`, `common/`), boot fixture `tests/boot_fixture/zephyr` (basename `zephyr` keeps the sysbuild image name), probes to `tests/board_images/evkb_integration_probe` with the configuration names of section 5, overlay to `samples/boards/nxp/mimxrt1060_evk/common/network.overlay`, `samples/management_rt1060_mbed` → `samples/boards/nxp/mimxrt1060_evk/https_management_mbedtls`, Kconfig and C names of section 7 (incl. the Zephyr patch and its hash), `scripts/test-controller.sh` → `scripts/test-time-periodic-task.sh`, `scripts/test-m3-rt1170.sh` → `scripts/test-integration-probe-rt1170.sh` (aliases kept) | `samples/controller/**` (except the two folders of PR 3), `samples/management_rt1060_mbed/**`, root `CMakeLists.txt`, `components/system/ports/zephyr/CMakeLists.txt`, `patches/zephyr/{README.md,nxp-enet-mdio-completion.patch}`; `scripts/{test-controller,test-controller-integration,test-m3-rt1170,test-boot-composition,test-management-mbed-rt1060,test-networking,test-networking-physical}.sh`, `scripts/{check-boot-config,check-controller}.py`; `tests/controller/**`, `tests/controller_integrated/**`, `tests/controller_network/**`, `tests/controller_network_stack/**`, `tests/networking_physical/CMakeLists.txt`, `tests/zephyr/management_rt1060_compile/CMakeLists.txt`, `tests/native/{integrated_output,logger_phase,network_output_burst,mdio_completion,deferred_output}/**`, `tests/target/{check_boot_images.sh,check_boot_reproducibility.sh,compare-mcuboot-crypto-backends.sh}`, the `tests/build/` tests that read controller or management paths (`test_check_boot_config`, `test_check_boot_images`, `test_dependencies`, `test_external_application`, `test_management_mbed_rt1060_image`, `test_psa_threading_provider`, `test_rt1170_composition`, `test_system_composition`, `test_bench_image_profile`, `test_bench_profile_wiring`, `test_device_control`), new `tests/boot_fixture/**`, `tests/board_images/evkb_integration_probe/**`; the docs that name controller, probe, boot or management paths and are not in PR 8's list (listed in the PR description) | all scripts listed | Host scenario and `native_sim` runs → `time_periodic_task`; boot checks → `tests/boot_fixture`; probes → `tests/board_images`; `tests/controller` keeps its 13 cases | PR 3, PR 4 |
| 3 | **PR 6 storage images** | `samples/storage_emmc`, `storage_sd` → `samples/boards/nxp/mimxrt1060_evk/{file_on_emmc,file_on_sd_card}`; `storage_sd_interrupt`, `storage_sd_replace`, `storage_sd_probe`, `storage_reliance_sd`, `flash_safety_poc` → `tests/board_images/{sd_card_power_cut_append,sd_card_power_cut_replace,sd_card_stack_removal_probe,reliance_sd_card_stage_a,flash_safety_check}`; ids of section 5; `scripts/test-flash-poc.sh` → `scripts/test-flash-safety-check.sh` (alias kept) | the seven source folders; `scripts/{test-file-emmc-compile,test-storage-emmc,test-file-rt1060-compile,test-storage-simulators,test-flash-poc}.sh`; `tests/native/{configuration_settings_reliance,file_emmc_composition,file_sd_check,file_sd_composition,file_sd_interrupt,file_sd_probe,file_sd_replace,file_sd_settings_recover,reliance_stage_a}/**`, `tests/build/test_file_reliance_edge_zephyr_public.py`, `tests/build/test_file_zephyr_public.py`, `tests/build/test_debug_target.py` (its `samples/storage_sd` example only); `docs/{credential-store,emmc-reliance-composition,emmc-reliance-file-service-assessment,emmc-reliance-physical-gate,file-composition-interface,flash-safety-poc,flash-xip-evidence,microsd-composition,microsd-physical-gate}.md` | the five scripts | same link checks and `native_sim` tests, new ids | PR 1, PR 4 (both edit `tests/build/test_debug_target.py`, in different waves) |
| 4 | **PR 7 milestone names in tests** | `tests/controller_m3` → `tests/probe_device_health` (ids `crux.probe.*`), `tests/m5_integrated` → `tests/integrated_smoke` (id `crux.integrated.smoke`), `tests/build/test_m3_*`/`test_m5_*`, `tests/target/*m3*`/`*m5*`, fixtures; `scripts/test-m5-integrated-smoke.sh` → `scripts/test-integrated-smoke.sh` (alias kept) | the files of the section 7 rows for `tests/` and that script | `scripts/test-m5-integrated-smoke.sh` | same checks under new names | PR 5 |
| 4 | **PR 8 docs** | Prose sweep of shared docs (`README.md`, `docs/README.md`, `docs/first-hour.md` with `hello_crux` first and `time_shell` second, `docs/build.md`, `docs/component-readiness.md`, `docs/secure-boot-board-test-procedure.md`, `docs/boot-porting-rt1062.md`, `docs/dependency-review-fatfs-r0.16.md`, `docs/native-interface-policy.md`, `docs/architecture.md`, `docs/execution-profile.md`, `tests/README.md`, `samples/README.md` with the new classification and a moved-paths table); records with milestone names move to `docs/history/` | those files and the moved records | none | — | PR 2–PR 6 |
| 5 | **PR 9 cleanup** | Old paths leave the shared tables of PR 1 | the five PR 1 code files | the three scripts | — | PR 7, PR 8 |
| held | **PR H** | `.github/workflows/zephyr.yml` and `host.yml` call the new script names and artifact paths; `AGENTS.md` validation lines name the new scripts | `.github/workflows/{zephyr,host}.yml`, `AGENTS.md`, `tests/build/test_ci_wiring.py` if it names a script | all | — | PR 5–PR 7; owner approval of the protected-rules files |
| after H | **PR 10 aliases** | Delete the alias scripts `scripts/test-controller.sh`, `test-m3.sh`, `test-m3-rt1170.sh`, `test-m5-integrated-smoke.sh`, `test-flash-poc.sh` | those five files | all five | the new scripts | PR H merged |

Files touched by two PRs are always in different waves: root `CMakeLists.txt` (PR 4, PR 5), `scripts/test-networking.sh`
(PR 4, PR 5), `tests/build/test_debug_target.py` (PR 4 for `samples/time`, PR 6 for `samples/storage_sd`), the PR 1 files (PR 1, PR 8 for
the docs, PR 9 for the code), and the alias scripts (PR 5–PR 7, PR 10).

Delete list (all other changes are moves or renames): the alias scripts in PR 10, of which `scripts/test-m3.sh` is
already only an alias today. No sample, test or check is deleted without its coverage moving as listed above.

## Review record

Author: Claude Code, model `claude-opus-5-5`, effort high. The independent review result is recorded in the Draft PR.
