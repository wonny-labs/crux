# Layout of `samples/`: proposal

Status: **proposal, for review in a Draft PR. Not adopted.** Nothing here is moved or renamed. It changes no protected
path, no CTest name and no Twister id. Every move it describes waits for the owner's decisions in
[section 5](#5-decisions-for-the-owner).

Baseline: `main` at `2d8553e2`. The Zephyr readings below were made in a local checkout at
`684c9e8f32e4373a21098559f748f06915f950c9` (v4.4.0). `west.yml` pins v4.4.2; the sample rules quoted are documentation
and Twister naming rules, which should be rechecked at the pin before they are relied on.

## Problem

`samples/` mixes five kinds of folder (the classification table in [`samples/README.md`](../../samples/README.md)), and
only some of them are samples in the sense a reader expects: something that builds and runs on its own and shows one
thing. The main cases:

- **`samples/controller`** has the same name as the product repository `crux-controller`, but its default
  configuration is a finite 20-cycle Time observation on a 100 ms periodic schedule. It is not a controller product.
- The same folder holds the board-only probes: nine `m3*.conf` files, `m3-network.overlay` and `m3_main.c` with its
  sources. `M3` is a
  historical Pilot milestone name, and the probes test devices, networking and health on the EVKB; they are tests,
  not samples.
- `controller/core`, `controller/include`, `controller/system` and `controller/configuration` are building blocks that
  only tests or the two controller programs compile.
- Of the 16 top-level folders, 4 are building blocks as a whole (`logging`, `serial`, `messaging`, `web_project`), and
  `controller` and `networking` contain more. 8 are board-only images as a whole, most of them probe, power-cut or
  formatter test images.
- Only `time/` and `controller/zephyr/` have a `sample.yaml`. Seven board-only folders have a `testcase.yaml` with
  `crux.sample.*` ids. Four top-level folders have a README.

## 1. Current inventory

Counted with `git grep -l -E "samples/<folder>([/\"' )\`]|$)"` on the baseline, excluding the folder itself and
`package-lock.json`. "Evidence" means files under `docs/evidence/` or `docs/baseline.md`: protected accepted records,
which stay unchanged and keep naming the old paths. "Protected (live)" lists the other files on the protected paths of
[`AGENTS.md`](../../AGENTS.md#protected-paths) that would have to change. "Other" counts the remaining files
(source, CMake, tests, docs, `web/`).

| Folder | Kind (from `samples/README.md`) | Evidence | Protected (live) | Other |
| --- | --- | --- | --- | --- |
| `time/` (Zephyr app) and `time/host/` | Runnable Zephyr application; runnable Linux Host program | 18 | `scripts/build-debug-target.sh`, `scripts/build-target.sh`, `scripts/check-host-sample.sh`, `scripts/check-native-interfaces.py`, `scripts/measure-tidy-coverage.py`, `scripts/test-zephyr-time.sh` | 17, incl. root `CMakeLists.txt`, `.vscode/tasks.json`, `tests/time/zephyr/CMakeLists.txt`, three `tests/build/` tests |
| `controller/zephyr/`, default `prj.conf` | Runnable Zephyr application | 106 for the whole folder | `.github/workflows/host.yml`, `scripts/test-controller.sh`, `scripts/check-boot-config.py`, `scripts/test-boot-composition.sh` | 64 for the whole folder, incl. root `CMakeLists.txt`, `tests/target/check_boot_images.sh`, `tests/target/check_boot_reproducibility.sh`, `tests/target/compare-mcuboot-crypto-backends.sh` (the boot checks build the default controller as their application) |
| `controller/zephyr/`, `m3*.conf`, `m3-network.overlay`, `m3_main.c` and the probe sources | Board-only application | (in the 106) | `scripts/test-controller-integration.sh`, `scripts/test-m3.sh` (historical alias that `exec`s the former), `scripts/test-m3-rt1170.sh`, `scripts/test-networking.sh`, `scripts/test-networking-physical.sh` | `tests/controller_m3`, `tests/controller_integrated`, `tests/controller_network`, `tests/controller_network_stack`, `tests/native/{integrated_output,logger_phase,network_output_burst,mdio_completion}`, `tests/networking_physical`, `tests/zephyr/management_rt1060_compile`, `samples/management_rt1060_mbed/CMakeLists.txt`, `tests/build/test_m3_*.py`, `tests/target/capture_m3_integrated.py` |
| `controller/host/` | Runnable Linux Host program | (in the 106) | `.github/workflows/host.yml` (uploads `build/linux/debug/samples/controller/host/controller.log`) | root `CMakeLists.txt` (`CRUX_BUILD_REFERENCE_CONTROLLER`), `docs/first-hour.md` |
| `controller/core/`, `controller/include/` | Building block | (in the 106) | `scripts/check-native-interfaces.py` | root `CMakeLists.txt` (`crux_controller_core`), `tests/controller` |
| `controller/system/` | Building block | (in the 106) | `scripts/test-system.sh`, `scripts/check-native-interfaces.py` | `tests/system_consumer/` (3 files), `tests/build/test_system_composition.py` |
| `controller/configuration/` | Building block | (in the 106) | `scripts/check-native-interfaces.py` | `tests/configuration/CMakeLists.txt` |
| `networking/host/`, `networking/zephyr/`, `networking/client.*` | Runnable Linux Host program; board-only application; building block | 15 | `scripts/check-native-interfaces.py`, `scripts/check-networking-dependencies.py`, `scripts/compile-networking-cpp-probe.py`, `scripts/run-host-sample.py`, `scripts/test-networking.sh` | 15, incl. root `CMakeLists.txt`, `tests/networking`, `tests/networking_zephyr` |
| `messaging/` | Building block | 2 | `scripts/check-native-interfaces.py`, `scripts/test-messaging.sh` | 7, incl. `tests/messaging_consumer`, `tests/consumer_poc` |
| `logging/` | Building block | 1 | `scripts/check-native-interfaces.py` | 5, incl. `tests/logging_consumer`, `tests/logging/zephyr/consumers.cmake` |
| `serial/` | Building block | 8 | `scripts/check-native-interfaces.py` | 6, incl. `tests/serial_consumer` |
| `flash_safety_poc/` | Board-only application | 3 | `scripts/test-flash-poc.sh` | 1 (`docs/flash-safety-poc.md`) |
| `management_rt1060_mbed/` | Board-only application | 0 | `scripts/test-management-mbed-rt1060.sh` | 9, incl. two `tests/build/` tests |
| `storage_emmc/` | Board-only application | 2 | `scripts/test-file-emmc-compile.sh` | 21, incl. `tests/native/file_emmc_composition`, `tests/native/configuration_settings_reliance`, `samples/storage_reliance_sd/CMakeLists.txt` |
| `storage_reliance_sd/` | Board-only application | 1 | `scripts/test-file-emmc-compile.sh`, `scripts/test-storage-emmc.sh` | 11, incl. `tests/native/reliance_stage_a/run_rehearsal.py` |
| `storage_sd/` | Board-only application | 3 | `scripts/test-file-rt1060-compile.sh` | 25, incl. the three other `storage_sd_*` CMake files, seven `tests/native/file_sd_*` folders |
| `storage_sd_interrupt/` | Board-only application (power-cut test image) | 3 | `scripts/test-file-rt1060-compile.sh`, `scripts/test-storage-simulators.sh` | 13, incl. `tests/native/reliance_stage_a/test_rehearsal.py` (imports its `host/` capture script) |
| `storage_sd_probe/` | Board-only application (physical-gate probes) | 1 | `scripts/test-file-rt1060-compile.sh` | 7 |
| `storage_sd_replace/` | Board-only application (power-cut test image) | 2 | `scripts/test-file-rt1060-compile.sh`, `scripts/test-storage-simulators.sh` | 11 |
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

### What Crux takes from them

Zephyr's rules fit Crux directly, because Crux samples are Zephyr applications and Twister already runs them. From the
NXP SDK, Crux takes one idea only: board-specific images live under a board folder, apart from portable examples.
Zephyr's `samples/boards/<vendor>/<board>/` already expresses that, so no NXP-style top-level categories are proposed.

## 3. Proposed layout

### Rules

1. A folder under `samples/` is a sample only if it builds on its own, shows one thing, and has a `README.md` and a
   `sample.yaml`. A runnable sample runs on `native_sim/native/64` with a console regular expression; a board sample
   names its board in `platform_allow` and the README, and is built by Twister (it runs only under an approved board
   procedure).
2. Portable samples sit under an area named after the Crux component they show: `samples/<component>/<name>/`.
   Board-only samples sit under `samples/boards/nxp/<board>/<name>/`.
3. A Linux Host program of a sample stays inside the sample as `host/`, as `samples/time/host/` does today.
4. Probe, power-cut and other board test images, and building blocks that only tests compile, move to `tests/`.
   Board test images go together under `tests/board_images/<name>/`; a building block moves into the test folder that
   compiles it.
5. Ids: `crux.sample.<area>.<name>[.<variant>]` for samples (Zephyr's form with the existing `crux.` prefix), and
   `crux.<area>.<name>` for tests, as the existing `tests/**/testcase.yaml` files already do.
6. No historical milestone names (`m3`, `m5`, `poc`) in new paths or ids. Accepted evidence keeps the old names.

### Mapping

| Old path | New path | New id or test name | Why |
| --- | --- | --- | --- |
| `samples/time/` (Zephyr app, `host/`, `include/`, `src/`) | `samples/time/shell/` (same inside) | `crux.sample.time.shell` (unchanged), CTest `Sample.TimeHost` (unchanged) | Already a sample; the folder becomes the `time` area |
| `samples/controller/zephyr/` default (`main.c`, `prj.conf`, `boards/`, `Kconfig`, `sample.yaml`, `README.md`) | `samples/time/periodic_task/` | `crux.sample.time.periodic_task` (was `crux.sample.controller.basic`) | Says what it shows: a periodic task on a 100 ms grid that reads Time ([D2](#5-decisions-for-the-owner)) |
| `samples/controller/host/` | `samples/time/periodic_task/host/` | CTest `Sample.PeriodicTaskHost` (was `Controller.HostScenario`), program `crux-periodic-task-host` | Same scenario, Host composition |
| `samples/controller/core/`, `samples/controller/include/` | `samples/time/periodic_task/common/` | library `crux_periodic_task_core` (was `crux_controller_core`) | Shared by the sample's two programs; `tests/controller` and the probes keep compiling it from there |
| `samples/controller/zephyr/` probe set: `m3_main.c`, `device_input.*`, `native_logger.*`, `network_*`, `mdio_completion.cmake`, `m3*.conf`, `m3-network.overlay` | `tests/board_images/controller_probe/` | build folders `build/zephyr/controller-probe-<profile>-evkb` | Board probes test devices, network and health; not samples ([D3](#5-decisions-for-the-owner)) |
| `m3.conf`, `m3-normal.conf`, `m3-integrated.conf`, `m3-network.conf`, `m3-mdio-completion.conf`, `m3-mdio-trace.conf`, `m3-phy-diagnostic.conf`, `m3-deferred-output.conf`, `m3-native-output.conf` | `probe.conf`, `normal.conf`, `integrated.conf`, `network.conf`, `mdio-completion.conf`, `mdio-trace.conf`, `phy-diagnostic.conf`, `deferred-output.conf`, `native-output.conf` in that folder; `m3_main.c` → `probe_main.c` | | The folder name already says "controller probe"; see [D4](#5-decisions-for-the-owner) for the company copy's names |
| `samples/controller/zephyr/m3-network.overlay` | `samples/boards/nxp/mimxrt1060_evk/common/network.overlay` | | Used by the probes, the management image, `scripts/test-networking*.sh`, `tests/zephyr/management_rt1060_compile` and two crux-codesys files: it is a board network overlay, not a probe file ([D5](#5-decisions-for-the-owner)) |
| `samples/controller/system/` | `tests/system_consumer/scenario/` | | Only `tests/system_consumer` compiles it |
| `samples/controller/configuration/scenario.c` | `tests/configuration/controller_scenario.c` | CTest `Configuration.ControllerScenario` (unchanged) | Only `tests/configuration` compiles it |
| `samples/controller/README.md`, `samples/controller/zephyr/README.md` | split into `samples/time/periodic_task/README.md` and `tests/board_images/controller_probe/README.md` | | Physical-verification text moves with the probes or to `docs/history/` |
| `samples/networking/` (`client.*`, `host/`, `zephyr/`) | `samples/networking/echo_client/` (Zephyr app at the root, `host/`, `common/client.*`) | new `sample.yaml` id `crux.sample.networking.echo_client` (EVKB, console harness skipped without a peer); CTest `Sample.NetworkingHost` (unchanged) | One sample, two compositions, as `time/shell` |
| `samples/messaging/` | `tests/messaging_consumer/scenario/` | CTest `Messaging.ControllerConsumer` (unchanged) | Building block of that test only; `tests/consumer_poc` follows |
| `samples/logging/` | `tests/logging_consumer/scenario/` | | Building block |
| `samples/serial/` | `tests/serial_consumer/scenario/` | | Building block |
| `samples/web_project/` | `tests/web/project_sample/project/` | CTest `Web.project_sample` (unchanged) | Building block; a runnable project page sample is a follow-up ([D7](#5-decisions-for-the-owner)) |
| `samples/web/angular/`, `samples/web/preact/` | unchanged | | Already `area/name`; moving them touches `.github/workflows/web.yml` and `web/` tooling for no reader gain. Preact gains a README |
| `samples/management_rt1060_mbed/` | `samples/boards/nxp/mimxrt1060_evk/management_mbedtls/` | `crux.sample.boards.mimxrt1060_evk.management_mbedtls` | A complete board image a product copies from (crux-controller does) |
| `samples/storage_emmc/` | `samples/boards/nxp/mimxrt1060_evk/file_emmc/` | `crux.sample.boards.mimxrt1060_evk.file_emmc` and `.start`, `.settings` | Board composition of File on eMMC |
| `samples/storage_sd/` | `samples/boards/nxp/mimxrt1060_evk/file_sd/` | `crux.sample.boards.mimxrt1060_evk.file_sd` and `.start` | Board composition of File on microSD; the three test images below reuse its sources |
| `samples/storage_sd_interrupt/` (with `host/`) | `tests/board_images/file_sd_interrupt/` | `crux.file.sd_interrupt` and `.test` | Power-cut test image |
| `samples/storage_sd_replace/` (with `host/`) | `tests/board_images/file_sd_replace/` | `crux.file.sd_replace` and `.test` | Power-cut test image |
| `samples/storage_sd_probe/` | `tests/board_images/file_sd_probe/` | `crux.file.sd_probe` and `.stack`, `.removal` | Physical-gate probes |
| `samples/storage_reliance_sd/` | `tests/board_images/file_reliance_sd/` | `crux.file.reliance_sd` and its eight variants | Stage A test images and rehearsal; mostly power-cut and formatter modes |
| `samples/flash_safety_poc/` | `tests/board_images/flash_safety/` | | Compile-only safety check image, inspected by a script |

Result: `samples/` holds `time/shell`, `time/periodic_task`, `networking/echo_client`, `web/angular`, `web/preact`,
and `boards/nxp/mimxrt1060_evk/{management_mbedtls,file_emmc,file_sd,common}`. Each has a README and a `sample.yaml`
(the web front ends excepted: they are npm projects, and the web guide describes them).

### The controller default scenario: name

| Candidate | For | Against |
| --- | --- | --- |
| **`time/periodic_task`** (recommended) | The area says Time, the name says what the code does: one task released on a fixed period. Short, Zephyr-like (`threads`, `blinky`) | Does not say "observes Time"; the README does |
| `time/periodic` | Shortest | An adjective; unclear what is periodic |
| `time/time_periodic` | Self-contained if read without the area | Repeats the area |
| `basic/periodic_task` | Zephyr's `basic/` is the first-stop area | Crux has one other first-hour sample (`time/shell`), which would then need a `basic/` home too |
| `execution/periodic_task` | Scheduling is the execution topic | Crux has no `execution` component folder; ADR-0002 assigns execution to Zephyr |

### The historical `m3` names

- New paths, configuration files, build folders and scripts carry no `m3`.
- `scripts/test-m3.sh` is already only an alias for `scripts/test-controller-integration.sh`. Proposal: remove it in
  the probe PR, after the docs that name it point at the maintained script.
- `scripts/test-m3-rt1170.sh` is renamed `scripts/test-controller-probe-rt1170.sh`, the name the company copy already
  uses.
- `scripts/test-controller-integration.sh` keeps its name: it is the maintained runner, and the name already fits.
- Out of scope here, listed for a later PR: `m3`/`m5` names outside `samples/` (`tests/controller_m3`,
  `tests/m5_integrated`, `tests/build/test_m3_*.py`, `tests/target/capture_m3*.py`, `docs/m3-validation.md`).
- Accepted evidence and `docs/history/` keep the old paths. Each moved README states its old path once, as
  [`templates/product/README.md`](../../templates/product/README.md) does for its move from `samples/product_template`.

## 4. Impact and migration

### Protected files to change

Every row needs explicit owner approval for that file (AGENTS.md, protected paths). Listed by the PR that changes them.

| PR | Protected files |
| --- | --- |
| P2 building blocks | `scripts/check-native-interfaces.py`, `scripts/test-messaging.sh`, `scripts/test-system.sh`; check whether `scripts/check-cli-session-commands.py`, `scripts/check-ssh-boundaries.py`, `scripts/check-web-routes.py`, `scripts/measure-tidy-coverage.py`, `scripts/tidy-sources.py` still scan the moved files |
| P3 controller split | `scripts/test-controller.sh`, `scripts/test-controller-integration.sh`, `scripts/test-m3.sh` (removed), `scripts/test-m3-rt1170.sh` (renamed), `scripts/test-networking.sh`, `scripts/test-networking-physical.sh`, `scripts/check-boot-config.py`, `scripts/test-boot-composition.sh`, `scripts/check-native-interfaces.py`, `.github/workflows/host.yml` |
| P4 networking | `scripts/check-native-interfaces.py`, `scripts/check-networking-dependencies.py`, `scripts/compile-networking-cpp-probe.py`, `scripts/run-host-sample.py`, `scripts/test-networking.sh` |
| P5 board samples and images | `scripts/test-management-mbed-rt1060.sh`, `scripts/test-file-emmc-compile.sh`, `scripts/test-storage-emmc.sh`, `scripts/test-file-rt1060-compile.sh`, `scripts/test-storage-simulators.sh`, `scripts/test-flash-poc.sh` |
| P6 Time shell | `scripts/build-debug-target.sh`, `scripts/build-target.sh`, `scripts/check-host-sample.sh`, `scripts/check-native-interfaces.py`, `scripts/measure-tidy-coverage.py`, `scripts/test-zephyr-time.sh` |

No change to `CMakePresets.json`, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.claude/` or `tools/` is expected.
`docs/evidence/` and `docs/baseline.md` are not edited.

### CTest and Twister changes

- CTest: only `Controller.HostScenario` → `Sample.PeriodicTaskHost`. The `sample` label stays. The others keep their
  names.
- Twister: `crux.sample.controller.basic` → `crux.sample.time.periodic_task`; `crux.sample.time.shell` unchanged;
  `crux.sample.management_rt1060_mbed`, `crux.sample.storage_emmc*`, `crux.sample.storage_sd` and `.start` move under
  `crux.sample.boards.mimxrt1060_evk.*`; the test images become `crux.file.*`; `crux.sample.networking.echo_client` is
  new.
- The `sample` tag keeps meaning "runnable on `native_sim`", so `west twister -T crux-pilot/samples -t sample` keeps
  working. The Reliance Edge `native` rehearsal entries leave `samples/`, so the untagged run no longer fails without
  the `crux-reliance` group.
- The root `CMakeLists.txt` option `CRUX_BUILD_REFERENCE_CONTROLLER` is a cache variable that build scripts and docs
  name. Proposal: add `CRUX_BUILD_PERIODIC_TASK_SAMPLE` and keep the old name as a deprecated alias for one release
  ([D6](#5-decisions-for-the-owner)).

### Consumer repositories (read-only check, 2026-11-22)

| Repository | What references Crux sample paths | Effect |
| --- | --- | --- |
| crux-codesys (`origin/main`) | `samples/evkb/CMakeLists.txt:11` and `tests/sys_socket/CMakeLists.txt:6` build with `$ENV{ZEPHYR_BASE}/../crux-pilot/samples/controller/zephyr/m3-network.overlay`; `tests/sys_socket/boards/...qspi_B.conf` and `docs/dependency-release-review.md` (finding F5, "reach-ins into Crux paths that are no contract") name it | **Build break** when the overlay moves. crux-codesys reads Crux at a pinned SHA, so the break appears at its next repin |
| crux-controller (`main`, `979fd1e`) | Comments only: `app/boards/s4.overlay` (`m3_main.c`), `app/conf/s3.conf` (`storage_sd/prj.conf`), `app/conf/s6.conf` (`management_rt1060_mbed`), five files under `docs/findings/` | No build effect; the text names "the pinned revision" and stays true, but goes stale at the next repin |
| crux-straton (`p0-foundation`) | none found | none |
| crux-platform (`main`) | Plans name `crux-pilot/samples/controller` as the reference controller (`docs/plans/crux-controller-skeleton-plan.md`, `docs/records/secure-boot-update-direction-proposal.md`) | Planning text only |

The consumer repositories were not changed.

### Company copy

The export rules (in the private plan outside this repository) carry Crux to the company copy as new commits made by
a 3-way merge, because the company copy has diverged. Two findings matter here:

- The company copy **already renamed** the probe files inside `samples/controller/zephyr/`: `m3*.conf` →
  `controller*.conf` (for example `controller-network.conf`, `controller-network.overlay`), `m3_main.c` →
  `probe_main.c`, and `scripts/test-m3*.sh` → `scripts/test-controller-probe*.sh`. A GitHub rename to different names
  makes the next merge resolve every probe file by hand. [D4](#5-decisions-for-the-owner) chooses between aligning
  with those names and replacing them.
- The company copy has no `docs/evidence/`, so evidence that keeps old paths does not reach it. Moves export as moves;
  the export check (no historical milestone names, no repository names) should pass more easily after this work,
  because `m3` leaves live paths.

Recommendation: run the layout PRs on GitHub first, then do one export that carries all of them, rather than
exporting after each PR.

### Step order

Each step is one PR, reviewed by the `reviewer` agent, with protected-file approval where the table above lists
files. Each move PR runs the checks of the scripts it changes, plus `scripts/check-host.sh`, `python3
scripts/check_docs.py` and the affected `tests/build/` tests, and shows `git grep` for the old path returning only
evidence and history.

| Step | Content | Protected | Depends on |
| --- | --- | --- | --- |
| P0 | This proposal | no | — |
| P1 | READMEs and `sample.yaml` where missing, at the current paths; classification table updated; no moves | no | owner decisions |
| P2 | Building blocks into `tests/` (`logging`, `serial`, `messaging`, `controller/system`, `controller/configuration`, `web_project`) | yes | P1 |
| P3a | Board network overlay to `samples/boards/nxp/mimxrt1060_evk/common/`; crux-codesys gets its own copy or a new path first ([D5](#5-decisions-for-the-owner)) | yes | crux-codesys change |
| P3b | Controller split: `time/periodic_task` and `tests/board_images/controller_probe`, `m3` names removed, CTest and Twister renames | yes | P2, P3a |
| P4 | `networking/echo_client` | yes | P1 |
| P5 | Board samples and board test images (`management_mbedtls`, `file_emmc`, `file_sd`, `tests/board_images/file_*`, `flash_safety`) | yes | P1 |
| P6 | `time/` → `time/shell/` | yes | P3b (shares `samples/time/` and first-hour docs) |
| P7 | Docs sweep: `docs/first-hour.md`, `docs/build.md`, `tests/README.md`, `samples/README.md`; a short "moved paths" table in `samples/README.md` | no | P2–P6 |

P2, P4 and P5 are independent of each other and can run in parallel sessions. P3b and P6 change the first-hour path,
so they should not overlap with other work on `docs/first-hour.md` or `samples/README.md`.

## 5. Decisions for the owner

| # | Decision | Recommendation | Reason | Alternative |
| --- | --- | --- | --- | --- |
| D1 | Area folders | `samples/<component>/<name>/` plus `samples/boards/nxp/<board>/<name>/` | Crux components are the subsystems a reader looks for; one level less than Zephyr | Zephyr's literal `samples/basic/`, `samples/subsys/<component>/`; closer to Zephyr, deeper paths |
| D2 | Name of the controller default scenario | `samples/time/periodic_task`, id `crux.sample.time.periodic_task`, CTest `Sample.PeriodicTaskHost` | Says what it does; no clash with crux-controller | `samples/basic/periodic_task` or `samples/time/periodic` |
| D3 | Home of board probes and power-cut images | `tests/board_images/<name>/`, ids `crux.<area>.<name>` | Zephyr's rule that samples do not test; one place for images that need a board procedure | Keep them as board samples under `samples/boards/nxp/mimxrt1060_evk/` with a `test` tag; fewer moves, but samples keep testing |
| D4 | Probe configuration names | Short names inside `tests/board_images/controller_probe/` (`probe.conf`, `network.conf` ...) and `probe_main.c` | The folder already says "controller probe"; `probe_main.c` and `test-controller-probe-rt1170.sh` match the company copy | The company copy's names (`controller.conf`, `controller-network.conf` ...): easier 3-way merge, but "controller" repeats the folder |
| D5 | The shared EVKB network overlay that crux-codesys builds with | Move it to `samples/boards/nxp/mimxrt1060_evk/common/network.overlay`, documented as a sample file and not a contract; crux-codesys takes its own copy into `samples/evkb/` before P3a merges (its rules say the reference application owns board choices) | Ends a reach-in that crux-codesys already lists as finding F5, without a new Crux public interface | Publish it as a supported Crux board overlay (for example a Zephyr snippet). That is a public interface and needs its own decision |
| D6 | Build option `CRUX_BUILD_REFERENCE_CONTROLLER` | New name `CRUX_BUILD_PERIODIC_TASK_SAMPLE`, old name kept as a deprecated alias with a warning until the first tag | External builds may set it; a silent removal breaks them | Rename with no alias; simpler, one break |
| D7 | `web_project` | Move into `tests/web/project_sample/`; a runnable project page sample (a `native_sim` web image) is a separate follow-up | Today no image packages it, so it is not a sample | Keep it in `samples/` as a documented exception |
| D8 | `scripts/test-m3.sh` | Remove it in P3b, after docs point at `scripts/test-controller-integration.sh` | It is a one-line alias for a historical name | Keep the alias one more release |
| D9 | Twister id prefix | Keep `crux.` (`crux.sample.<area>.<name>`) | Separates Crux scenarios from Zephyr's in one Twister run; existing tags and scripts keep their filter | Zephyr's bare `sample.<area>.<name>` |
| D10 | Approval scope | Approve P1–P7 as one work package, with the protected files in the table above, merge per PR after reviewer PASS and green CI | Each PR is small and mechanical; one approval avoids a question per PR | Approve per PR |
| D11 | Order against the company export | All layout PRs first, then one export | One 3-way merge of the moved tree instead of several | Export after each PR |

## Review record

Author: Claude Code, model `claude-opus-5-5`, effort high. The independent review result is recorded in the Draft PR.
