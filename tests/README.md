# Test organisation

This guide maps each area of Crux to the script that runs its tests and the document that states its results. Apart from the physical suites under `target/` (`scripts/test-target.sh` and the `capture_m3*.py` runners), which reset a flashed EVKB through J-Link and need a separately authorised hardware run, no suite here operates hardware. A Host, `native_sim` or simulator result is not board evidence, and a cross-build shows only that an image links. Other physical runs go through the [device-control tool](../tools/device_control/README.md).

| Test purpose | Runner or harness | Environment |
| --- | --- | --- |
| Portable components and controller logic | CTest with GoogleTest suites and standalone C/C++ tests | Linux Host |
| Zephyr components and integration | Twister with Ztest, console or the default harness | Zephyr `native_sim` |
| Basic periodic controller scenarios | Python runner through `scripts/test-time-periodic.sh` | Zephyr `native_sim` |
| Build tools and validation oracles | Python `unittest` | Linux host |
| Physical Time/RTC functional tests | Standalone pytest through `scripts/test-target.sh` | macOS, EVKB and J-Link |
| Physical device, network and integrated watchdog tests | Dedicated Python CLI capture runners | EVKB and a controlled peer setup on macOS |
| Out-of-tree consumer, all software levels | Python `unittest`; its Zephyr levels are opt-in | Linux host and Zephyr `native_sim` |
| Device-control tool | Python `unittest` with fake transports | Linux and macOS hosts |
| Power-cut wrapper `scripts/power_cut.py` | Python `unittest` with fake commands (`python3 -m unittest discover -s tests/power_cut -v`); no hub, probe or board | Linux host |

## Before you open a pull request

Run these in the Dev Container, from the repository root. Choose the ones that fit the change.

| Change | Command |
| --- | --- |
| Any code change | `scripts/check-host.sh` |
| Any code change, memory and undefined behaviour | `CRUX_HOST_PRESET=host-sanitize scripts/check-host.sh` |
| Any code change | `scripts/check-format.sh` |
| Any code change | `scripts/analyze-host.sh` |
| Any code change | `scripts/check-dependencies.sh` |
| Documentation | `python3 scripts/check_docs.py` (Python 3.11 or later; the first run needs `python3 scripts/check_docs.py --install` for the pinned link checker) |
| Zephyr changes | `scripts/check-zephyr-smoke.sh`, and the `scripts/test-<component>.sh` of the component you changed (see the sections below) |

`scripts/check-host.sh` needs one earlier run of `scripts/bootstrap-host.sh`, because it works without network access. The container has 2 CPUs and 4 GiB, so full Zephyr suites are slow there. CI runs most of these checks; [`scripts/ci/checks.toml`](../scripts/ci/checks.toml) lists them and [Continuous integration](../docs/ci.md) says which tier runs each. Some runners named in [Component readiness](../docs/component-readiness.md) run locally only. Push the branch to a draft pull request to see the fast tier's results, mark it ready for the full tier, and say in the pull request which checks you did not run.

## Board input

The Zephyr scripts take the board from `CRUX_BOARD_TARGET`, a `west build -b` board target such as `mimxrt1060_evk@B//qspi`. It does for these scripts what west's `build.board` option does for `west build` ([Setting a Default Board](https://docs.zephyrproject.org/latest/develop/west/build-flash-debug.html#setting-a-default-board)). Unset, each script builds the board it always built. `scripts/lib/board.sh` holds the rules.

| Scripts | Board |
| --- | --- |
| `test-time-periodic.sh`, `test-time-busy-wait.sh`, `test-execution.sh`, `test-portable-execution.sh`, `test-integrated-smoke.sh`, `test-serial.sh`, `test-logging.sh`, `test-system.sh`; `test-zephyr-time.sh`, which also takes it as its argument | `CRUX_BOARD_TARGET`, default `mimxrt1060_evk@B//qspi`. The application decides whether it supports the board: one without an overlay for it fails at configuration. These scripts list the NXP HAL modules, so a board of another vendor also needs its HAL module added |
| `check-zephyr-smoke.sh` | `CRUX_BOARD_TARGET`; without it the board build is skipped |
| `build-target.sh`, `build-debug-target.sh`, `test-product-template.sh` | Their argument (CI passes `CRUX_BOARD_TARGET`) |
| `test-integration-probe-rt1170.sh` | RT1170-EVK Rev A CM7 only |
| `test-networking.sh`, `test-networking-physical.sh`, `test-controller-integration.sh`, `test-flash-safety-check.sh`, `test-boot-composition.sh`, `test-file-rt1060-compile.sh`, `test-file-emmc-compile.sh`, `test-storage-emmc.sh`, `test-management-mbed-rt1060.sh`, and the target modes of `test-web.sh`, `test-psa-crypto.sh`, `test-native-composition.sh`, `test-ssh-provider.sh`, `test-ssh-wolf-settings.sh` and `test-ssh-sftp-compile.sh` | RT1060-EVKB Rev B only |
| VS Code **Board:** tasks and profiles | `crux.board`, `crux.boardKey` and `crux.jlinkDevice` in `.vscode/settings.json`, default the RT1060-EVKB Rev B ([build guide](../docs/build.md#native_sim-and-the-board-in-vs-code)) |
| `test-gpio.sh`, `test-i2c.sh`, `test-spi.sh` | Every board with an overlay in the test; `CRUX_BOARD_TARGET` is not read |

A one-board script given another board stops with one line before it builds. The board-generic scripts build in `build/zephyr/<purpose>-<board>`, as west's `build.dir-fmt` names folders after `{board}` ([west configuration](https://docs.zephyrproject.org/latest/develop/west/build-flash-debug.html#configuration-options)). `<board>` is `evkb` for the RT1060-EVKB Rev B and `rt1170` for the RT1170-EVK Rev A CM7, the names these folders already had, and for any other board its full target with every run of other characters replaced by `_`, such as `mimxrt1180_evk_mimxrt1189_cm33` for `mimxrt1180_evk/mimxrt1189/cm33` or `mimxrt1180_evk//cm33`. A board with more than one core needs the core in the target, as `west build` does. `build-target.sh` and `build-debug-target.sh` use `build/zephyr/<board target with _>`.

## Host: `time/` and `controller/`

GoogleTest/CTest exercises the C17 Time implementation, calendar conversion and the portable command handler against the controlled host backend. The C++ tests include the public C headers and call the C17 implementation; the build does not recompile production `.c` sources as C++. The controller Host tests cover portable scheduling, readiness, freshness, recovery and joint owner-health logic. CTest applies a 30-second limit to each Time host test.

`BUILD_TESTING` sets the initial default of `CRUX_BUILD_TESTS`, which controls Crux's internal tests and the GoogleTest/C++ setup. In an existing build directory, set `CRUX_BUILD_TESTS=OFF` explicitly to disable them. A library-only build also sets `CRUX_BUILD_HOST_SAMPLE=OFF` and `CRUX_BUILD_TIME_PERIODIC_SCENARIO=OFF`. See the [build guide](../docs/build.md#linux-host-build).

## Zephyr: `time/zephyr/`

Twister builds and runs the C17 Ztest application on three `native_sim/native/64` configurations: RTC emulator, absent RTC and a controlled fake RTC driver. The tests cover system realtime, authority and snapshot consistency, ISR rejection, explicit RTC storage, failure isolation, the shared command handler and the Zephyr Shell adapter on the dummy Shell backend. Host tests own portable behaviour; Ztest covers native integration and the Shell boundary.

```sh
scripts/test-zephyr-time.sh 'mimxrt1060_evk@B//qspi'
```

This runs the `native_sim` Ztests, builds the clock shell sample (`samples/time/shell`) for simulation and cross-builds its EVKB image.

## Build tools: `build/`

Python `unittest` checks the build and validation tooling. Run it on Linux; host CI runs it too:

```sh
python3 -m unittest discover -s tests/build -v
```

Install `west` and `pyyaml` (the host CI job pins `west==1.4.0` and `pyyaml==6.0.3`) and set `CLANG_TIDY` to a clang-tidy 18 binary, or the manifest, workspace and real-tool cases skip. A skipped case passes, so a run without them says less. Two product style cases skip even in CI, because they need a Zephyr tree (`ZEPHYR_BASE`). `tests/build/test_ci_wiring.py` fails if the sanitizer preset stops aborting on undefined behaviour, or if a workflow stops running the File service checks, the Zephyr smoke check, those installs or the `CLANG_TIDY` setting.

Each tool has a `tests/build/test_<tool>.py` that runs on throwaway repositories, synthetic images or fixture files and needs no network, key, board or west workspace unless the file says so:

| Tool | Where it is described |
| --- | --- |
| Crux pin bot scripts | [Keeping the Crux pin current](../docs/product-composition.md#keeping-the-crux-pin-current) |
| `scripts/gen-compat-table.py` | [Compatibility table](../docs/compatibility-table.md) |
| `scripts/check-release-bundle.py` | [Release bundle checker](../docs/release-bundle-checker.md) |
| `tests/target/inspect_boot_image.py` | [Boot image inspection](../docs/boot-image-inspection.md) |
| `tests/target/check_hab_structure.py` | [HAB status](../docs/boot-hab-status.md) |
| `tests/target/compare_boot_builds.py`, `check_boot_reproducibility.sh` | [Boot reproducibility](../docs/boot-reproducibility.md) |
| `scripts/check-boot-config.py` | [Boot composition](../docs/boot-composition.md) |
| `tests/target/compare-mcuboot-crypto-backends.sh` | [Comparison record](../docs/plans/mcuboot-crypto-backend-comparison.md) |

### Boot composition: `scripts/test-boot-composition.sh`

This script builds, signs and checks the MCUboot RAM-load composition of [boot composition](../docs/boot-composition.md) for the RT1060-EVK Rev B. It is build only: it programs, boots, debugs and resets nothing, and it signs with MCUboot's published public test key, so its images must never be programmed to a board. It needs the Linux Dev Container and a workspace made by `scripts/bootstrap-zephyr.sh`. CI runs it in the `runtime` shard. It calls `tests/target/check_boot_images.sh` and `scripts/check-boot-config.py` on its own build; the approval of that wiring is recorded in the header of each of those two scripts.

Outside CI it changes your local workspace:

- It adds `+crux-boot` to `manifest.group-filter` with `west config` (keeping any filter already set) and runs `west update mcuboot`. The group filter stays on afterwards.
- It runs `pip install -r bootloader/mcuboot/scripts/requirements.txt` into the Python given by `CRUX_PYTHON` (`python3` by default), because imgtool imports packages that the Zephyr requirements do not list.
- It writes under `build/zephyr/boot-composition/`.

It checks the bootloader and application configuration, that the signed image verifies with the public key, that a key of another type and images changed after signing are refused, the padded confirmed image size and the image inspector. It also prints a report-only FlexSPI closure listing that never fails the run. Use a throw-away workspace or virtual environment to keep the group filter and the pip installs out of your main one.

## Physical UART: `target/`

`scripts/test-target.sh` runs a pytest suite on macOS against the already flashed EVKB QSPI sample, and exits on any other system. It never flashes. Its fixture validates the ELF against a provenance manifest and requires a retained GDB download and section-comparison log for that image. Stop VS Code debugging, J-Link GDB Server and all serial monitors first. The suite supports only the verified EVKB QSPI setup.

```sh
python3 -m venv build/tools/m4-venv
build/tools/m4-venv/bin/python -m pip install -r tests/target/requirements.txt
scripts/test-target.sh \
  --uart <serial device> \
  --elf <verified-zephyr.elf> --manifest <matching-provenance.json> \
  --flash-log <gdb-download-and-compare.log> \
  --probe <J-Link serial> --board 'mimxrt1060_evk@B//qspi' \
  --evidence build/evidence/m4/<new-run-directory> \
  -v --junitxml=build/evidence/m4/<new-run>.junit.xml
```

The evidence directory must be new, so failed evidence is not overwritten. A run retains the raw and timestamped bytes, the transaction results, the firmware and source identity, and the reset output. The retained `reset.jlink` script only resets, starts and disconnects, and the final reset leaves the sample running at a fixed test date, not the host clock.

## Execution and reference controller

`tests/execution` compares the pinned native Zephyr/POSIX subset; its POSIX cases also run on Linux. `tests/controller` verifies sample-owned Time observations, recovery and monotonic phase logic. The boundary-negative and host-runner failure checks are under `tests/build`. Host CTest includes the finite controller scenario. `scripts/test-time-periodic.sh` validates normal and RTC-absent `native_sim` compositions and cross-builds EVKB; its conditions are in [`tests/time_periodic/README.md`](time_periodic/README.md).

`scripts/test-controller-integration.sh` runs the device, networking and integrated-controller Zephyr scenarios and EVKB cross-builds, with Python validators on the captured simulation output. Physical device, network and integrated-controller evidence comes from the `tests/target/capture_m3*.py` command-line runners on a controlled setup; they are not pytest tests and GitHub Actions does not run them. The [controller validation record](../docs/m3-validation.md) holds the fixtures, commands, firmware identities and results.

`tests/native/deferred_output` runs the pinned Zephyr raw printk queue and UART backend on `native_sim`, including 64-bit output and a deliberately overflowing buffer. `verify_output.py` checks the handler logs and requires the shared loss validator to reject the real overflow marker.

## External application build boundary

```sh
python3 -m unittest discover -s tests/build -p test_external_application.py -v
```

The test copies `tests/external_application/` outside the Crux tree, then configures, builds and runs independent C17/C++17 parent projects that select Base/Time, Busy-wait, Thread/Time, Sync-only, Serial-only, Logging-only, System-only and Base-only. It checks that parent targets and tests stay functional, that compile commands and final ELF symbols match the selected components, and that missing, unsupported or conflicting provider selections fail. Copied Serial and Logging consumers run their PTY and policy scenarios under a parent with its own tests. The fixture uses public capabilities in portable targets and declares platform composition separately. See the [external application example](../docs/build.md#external-linux-application-using-crux-source).

## Testing a consumer application

Applications own their tests; the [build guide](../docs/build.md#testing-a-consumer-application) gives the entry point for each level. `consumer_poc/` is a worked example, kept working by `build/test_consumer_poc.py`:

```sh
python3 -m unittest discover -s tests/build -p test_consumer_poc.py -v
```

The test copies the consumer outside the Crux tree and builds and runs its unit and Host integration levels. It checks which components are built, that the unit level links no Crux target, and that a controlled policy defect (`-DCONSUMER_DEFECT_REBASE=ON`) fails both levels. These Host cases need no west workspace. The `native_sim` and functional levels are opt-in, and the `zephyr-software` workflow runs them. To run them yourself, use a west workspace with pytest installed:

```sh
CRUX_CONSUMER_POC_ZEPHYR_TESTS=1 python3 -m unittest discover -s tests/build -p test_consumer_poc.py -v
```

Hardware tests have no supported entry point. A wired-part scenario is built in CI and not run. [Hardware integration tests](../docs/build.md#hardware-integration-tests) says what each source says.

## Device-control tool

`build/test_device_control.py` tests [`tools/device_control`](../tools/device_control/README.md) with fake transports and scripted tools: its reset and flash gates, manifest checks, evidence retention and board lock. One test runs real `sudo` where it needs no password. No test uses hardware or a serial port. Host CI runs them on Linux; manual macOS runs are in the [recorded runs](../docs/evidence/test-foundation-tool/README.md).

## Product template

`tests/build/test_product_template.py` checks `templates/product`: its C file and CMake use only public Crux names, and its manifest pins nothing Crux pins. It runs `check_domain_includes.py` on the shipped domain and on mutated copies, builds the domain on the Host with a fake port and `-Wpedantic`, and checks the shared-state example. Real west takes the template through `west init -l`, `west update` and `west crux-pins` against local repositories with no network, and runs the frozen-manifest flow and the routes of the guide. These cases skip without west or PyYAML. `scripts/test-product-template.sh <board>` runs them with `tests/build/test_crux_pins.py`, runs `west crux-pins` on Crux's own workspace, and cross-builds the application there. The Zephyr CI job runs it. See the [Product Composition Guide](../docs/product-composition.md).

`tests/build/test_product_style.py` checks the [style kit](../templates/product/style/README.md) and the guidance that names it. `tests/build/test_product_standards.py` checks the advisory target-code analysis of the same kit, the product [contribution guide template](../templates/product/CONTRIBUTING.md) and the [driver review checklist](../docs/driver-review-checklist.md). Both run with stand-ins for clang-format, checkpatch and clang-tidy. Set `CLANG_FORMAT`, `ZEPHYR_BASE` or `CLANG_TIDY` to run the real tools instead of skipping those cases. The host CI job runs both.

## Frozen header warning

`tests/build/test_frozen_header_guard.py` checks the opt-in `#warning` of `<crux/thread.h>`, `<crux/sync.h>`, `<crux/serial.h>`, `<crux/gpio.h>`, `<crux/i2c.h>` and `<crux/spi.h>`. The headers are silent by default, even under `-Werror`. `CRUX_WARN_FROZEN_HEADERS` makes each warn once and name itself and `docs/choosing-an-api.md`, and `CRUX_INTERNAL_BUILD` silences it. On Linux the test configures Crux as a subdirectory and reads `compile_commands.json`: Crux's own sources carry `-DCRUX_INTERNAL_BUILD`, the consumer's do not, and no usage requirement exports it.

## Portable execution capability

`scripts/test-portable-execution.sh --host-only` runs separately configured C/C++ Thread-only and Sync-only consumers, firmware and runtime-shaped consumers, and their execution boundary checks. Final ELF symbol and compile-command checks reject the unselected provider. The full script also runs Zephyr `native_sim` and EVKB cross-builds for the combined and the two standalone configurations. It includes:

- `tests/thread/zephyr`: RTC-disabled Ztests of typed monotonic and sleep behaviour.
- `tests/sync/zephyr`: mutex priority inheritance, timeouts during other Sync calls, deferred wake-ups, thread switches after the native unlock, destroy while a wake-up is returning, and every mutex slot at the default and the largest pool.
- `tests/service_priority/zephyr`: the per-service priorities of Crux's service workers, at their defaults and moved. Its static half, `tests/service_priority/check_placement.py`, runs in the Host CTest set as `ServicePriority.*` (see [Priority map of Crux threads](../docs/thread-sync.md#priority-map-of-crux-threads)).

Common conformance and Host failure regressions run in the standard Host debug and sanitizer checks. See the [Thread/Sync contract](../docs/thread-sync.md) for semantics and provider limits.

`tests/time/busy_wait/` holds the Busy-wait tests: common and native error handling, counter conversion, unsupported-profile shims and a Linux integration. `scripts/test-time-busy-wait.sh` runs normal-ISR and IRQ-delivery Ztests on `native_sim` and cross-builds EVKB. See the [Time Busy-wait contract](../docs/time-busy-wait.md).

## Portable networking software slice

The [networking contract](../docs/networking-contract.md) defines the IPv4 client-only profile. `scripts/check-host.sh` includes deterministic and real Linux loopback tests. Run `scripts/bootstrap-networking-tests.sh` once to fetch Zephyr's pinned Picolibc test module into the external cache, then `scripts/test-networking.sh` for independent C/C++ consumers, real Zephyr loopback qualification and an RT1060 cross-build. The native fixture requires the embedded libc, so it cannot silently test Linux sockets. Its fixture servers use standard APIs outside the public client profile and are not consumer examples.

`scripts/test-networking-physical.sh` runs the private runner and oracle tests, the embedded-libc Zephyr instrumentation tests and a dedicated RT1060 cross-build; `--freeze` requires clean committed inputs and writes commit-specific image, provenance and ABI manifests. Neither mode accesses hardware. See [the preparation procedure](../docs/networking-physical-preparation.md).

## Portable Configuration software checks

The Host debug and sanitizer CTests include `Configuration.Conformance` (with the string cases of `string_conformance.c`), `Configuration.NoProvider` and `Configuration.ControllerScenario`. Build-tool discovery runs the independent C17/C++17 consumer build. The storage gate runs the same cases on `native_sim` from `tests/configuration/zephyr`, and a string case on each of the two Settings backends. See [Configuration qualification](../docs/configuration-validation.md) for the manual `native_sim` and Settings source-wrapper probes.

## Status and configuration services

`scripts/test-mgmt-services.sh` runs the services on Host with and without sanitizers, their thread suites under ThreadSanitizer, their clang-tidy selection, a C and C++ consumer built from public headers, and `scripts/check-mgmt-services-boundary.py`. `ConfigService.*` and `MgmtStatus.*` run on the real Access core with fake ports and fault injection per status source. `MgmtStatus.openapi_schema` holds the service's JSON to the status schema in `web/api/openapi.yaml`; `MgmtStatus.source_mapping` and `MgmtStatus.real_sources` cover the thin providers against stand-ins and the real System, Time and Netif on Linux. The storage gate also runs `tests/native/mgmt_services` on `native_sim` with the real System, Time and Sync. See the [services contract](../docs/status-configuration-services.md).

## Web contract and HTTP adapter

| Command | What it runs |
| --- | --- |
| `scripts/test-web.sh host` | `Web.*` on the real web and Access cores with a fake transport, the boundary, generator and route review checks, and the `Web.*` Host suites below |
| `scripts/test-web.sh native` | The adapter on the real Zephyr server on `native_sim`, over plain HTTP on loopback |
| `scripts/test-web.sh target` | A compile for RT1060 on the TLS profiles; Mbed TLS runs in the PSA workflow, wolfSSL does not |
| `scripts/test-web.sh https` | The native suite over TLS on the management composition, with `tests/native/web_https`, on each profile: Mbed in the PSA workflow, Wolf locally |
| `scripts/test-web-session.sh native` | Login and sessions on the management composition over plain HTTP on `native_sim`, with the real Access core on its PSA ports; CI runs it in the PSA workflow |

See the [web contract](../docs/web-contract.md), the [HTTPS composition](../docs/https-composition.md) and [web login and sessions](../docs/web-session.md). Session entropy in these tests is test-only.

Each route group has Host suites on the real Access core and services, with fake ports. An `*_openapi` suite holds the real answers to the schemas of `web/api/openapi.yaml`.

| Suites | Route group | Runner | Contract |
| --- | --- | --- | --- |
| `Web.session_*` | login and sessions | `scripts/test-web.sh host` | [Web login and sessions](../docs/web-session.md) |
| `Web.management_*` | status, configuration, account | `scripts/test-web.sh host` | [Web management APIs](../docs/web-management-apis.md) |
| `NetworkSettings.*`, `Web.network_*` | `GET` and `PUT /api/v1/network` | `scripts/test-network-settings.sh` (both presets with clang-tidy) | [Network settings service](../docs/network-settings-service.md) |
| `Reboot.*`, `Web.reboot_*` | `GET` and `POST /api/v1/system/reboot` | `scripts/test-reboot.sh` (both presets with clang-tidy) | [Reboot service](../docs/reboot-service.md) |

`tests/network_settings/validation-vectors.tsv` holds the firmware's checks and the TypeScript client's to the same lines. The reboot sleep is virtual, so the delay and the bounded wait are exact. `Reboot.pending` runs the wait against the real network settings and configuration saves, and `Reboot.start_faults` shows that a failed start gives back the mutex it created. `Web.reboot_no_service` shows that a composition without the service has no reboot route.

`tests/reboot/zephyr` builds the Host sources of the reboot and `Web.reboot_*` suites for `native_sim/native/64` over the Crux Thread and Sync Zephyr providers, with ASan and UBSan. `scripts/test-reboot-native.sh [--plain]` builds six images and runs them once per case, because Zephyr has no `fork()`; it fails if a suite lists a different number of cases from the Host source. `native_sim` runs one Zephyr thread at a time and has no ThreadSanitizer, so this is not a Host result; `Reboot.nodiscard` and the C++ header check stay Host only. See [the record](../docs/research/reboot-native-sim-stage-a.md).

## Packaged web assets

`scripts/test-web-assets.sh host` runs the packager's tests (`tests/build/test_web_assets.py`), `Web.assets_*` on the real web core for both content policies, clang-tidy, and the route review and boundary checks. `scripts/test-web-assets.sh native` builds `tests/native/web_assets` and runs its driver against the real Zephyr server on `native_sim`. The full Host build and `unittest discover tests/build` pick up the Host cases, and `zephyr.yml`, shard `io`, runs the `native_sim` image. See [web assets](../docs/web-assets.md).

## Portable File software slice

The [File contract](../docs/file-contract.md) and [qualification record](../docs/file-validation.md) cover the Linux Host provider. Host CTest includes `File.file_fault` and `File.file_host`, which uses an isolated temporary root. Public-only C17/C++17 consumers build with:

```sh
cmake -S tests/file_consumer -B build/file-consumers -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build/file-consumers
ctest --test-dir build/file-consumers --output-on-failure
```

`tests/file/conformance.c` holds the cases that the Linux provider (`File.file_conformance_linux`), the in-memory fake (`File.file_conformance_fake`) and the simulator suites below run. `File.file_fake_faults` walks a power cut across each mutation of a sequence under the fake's own model.

[Root byte limits](../docs/file-contract.md#root-byte-limits) are in the shared cases too (`crux_file_conformance_limit`), so they run on the Linux provider, the fake, FatFs (`file_roots`), LittleFS on a block device (`file_littlefs_blk`) and Reliance Edge (`file_reliance`, under `scripts/test-storage-emmc.sh`). `File.file_limit` adds the fake-only cases: rounding and saturation, a root found above its limit, provider failures, and the count after a power cut and a new binding. `File.file_limit_linux` runs two writers and a creating and removing caller on one limited root of the Linux provider. `file_littlefs_blk` also fills a limited application root and then saves Configuration and a File in another root on the same volume, and `credential_littlefs` does the same and then saves a credential record and makes a key. No ThreadSanitizer run covers the limit, and the provider's unbind after a failed volume query or listing is tested on the fake only.

`scripts/test-file-service.sh` runs the file service on Host with and without sanitizers and builds a C and C++ consumer from its public headers; the host CI job runs it. `FileService.default` and `FileService.small_table` use the fake File provider and walk a power cut across every mutation of a commit and of the rename that recovery finishes. `FileService.with_access` runs it on the real Access core with fake ports.

`scripts/test-storage-simulators.sh` runs the VFS/LittleFS and FatFs File suites on 32/64-bit `native_sim` (the LittleFS ones on a flash simulator, `tests/native/file_littlefs`, and on a RAM disk, [below](#littlefs-block-device-file-on-native_sim)), the Settings/NVS Configuration suite on 64-bit `native_sim`, and the Configuration source-staging regressions. It needs the pinned west workspace with LittleFS and FatFs and a Host compiler with 32-bit development libraries. The Zephyr CI workflow runs it.

### LittleFS block device File on `native_sim`

| Suite | Runner | What it shows | Record |
| --- | --- | --- | --- |
| `tests/native/file_littlefs_blk` | storage gate | `CONFIG_CRUX_FILE_LITTLEFS_BLK_DEV` on a RAM disk: the File contract and additions, a failed handle that closes with its error, a mount that never formats a blank or damaged disk (and a control that does), and Configuration saving on the same volume, with the removal of the settings files | [File contract](../docs/file-contract.md#littlefs-block-device-mapping) |
| `tests/native/credential_littlefs` | storage gate | The credential store's contract on that provider, with the test-only protection | [Credential store](../docs/credential-store.md#tests) |
| `tests/native/emmc_powercut`, workloads W4, W5, W8 and W8C with `--fs littlefs` | storage gate | Power-cut replay on the eMMC simulator: Settings saves, File appends and File replaces, with controls that must fail. Model results, not device evidence | [Evidence plan](../docs/plans/littlefs-power-cut-evidence-plan.md) |
| `tests/zephyr/file_littlefs_link` | `scripts/test-file-rt1060-compile.sh` | The provider and Configuration link for the RT1060-EVKB microSD disk; the image is never flashed | [File contract](../docs/file-contract.md#littlefs-block-device-mapping) |

The storage gate is `scripts/test-storage-simulators.sh`. A remount inside one process is not persistence evidence.

### FatFs File on `native_sim`

| Suite | Runner | What it shows | Record |
| --- | --- | --- | --- |
| `tests/native/file_fatfs`, `file_roots` | `scripts/test-storage-simulators.sh` | The File contract and the roots, stat, size, rename and listing additions on real FatFs over a RAM disk, including corrupted media that is never formatted | [File validation](../docs/file-validation.md) |
| `tests/native/file_fatfs_persist` | `scripts/test-file-persistence.sh` (not in CI) | Separate processes on a `zephyr,flash-disk` backed by a host file: acknowledged files survive the next process and a `SIGKILL` between updates, and a deliberate acknowledge-before-durable defect is reported | [File validation](../docs/file-validation.md) |
| `tests/zephyr/file_fatfs_compile` | `scripts/test-file-rt1060-compile.sh` | The SD card FatFs composition compiles for `mimxrt1060_evk@B//qspi`, Rev C and the hyperflash variant; it is refused when the `zephyr,sdmmc-disk` node is disabled; the File object compiles on the fictional RT1062 board `tests/zephyr/board_fixture` | [microSD composition](../docs/microsd-composition.md) |
| `tests/native/file_sd_composition`, `file_sd_check` | storage gate | The microSD mount sequence and the write/read/restart check of `samples/boards/nxp/mimxrt1060_evk/sd_card_file` on a RAM disk named `SD` | [microSD physical runs](../docs/evidence/microsd-physical/README.md) |
| `tests/native/file_sd_probe`, `file_sd_interrupt`, `file_sd_replace`, `file_sd_settings_recover` | storage gate | The logic and host scripts of the physical-gate board images `tests/board_images/sd_card_*`, and the Settings File recovery step, against scripted boards and a RAM disk; the images are only linked in CI | [power cut](../docs/evidence/microsd-power-cut/README.md), [replace cut](../docs/evidence/microsd-replace-cut/README.md) |
| `tests/native/configuration_settings_file` | storage gate | The Zephyr Settings File backend on a FatFs RAM disk with injected I/O faults, on build-local corrected copies of three backend sources; a control on the unpatched backend must fail the cases that expose its defects | [Configuration qualification](../docs/configuration-validation.md) |

A remount inside one process and a simulated cut are not persistence or power-loss evidence about a card.
The sample that these suites cover is in the [samples overview](../samples/README.md), and the board images are in [Test-only scenarios and board test images](#test-only-scenarios-and-board-test-images).

### eMMC simulator on `native_sim`

`tests/support/emmc_sim` is a `native_sim` SD host driver that behaves as one eMMC device, so that the unmodified `drivers/disk/mmc_subsys.c` and `subsys/sd` run without hardware. It cannot be selected on a target. The simulator is a model written from the stack's needs: it has no timing and no wear model, and a process exit is not a power loss. Results show how the stack behaves against that model, not how an eMMC device behaves. `scripts/test-storage-emmc.sh` runs the suites below, except where a row names another runner, and requires the executed cases of each scenario; the Zephyr CI workflow runs it and `scripts/test-file-emmc-compile.sh`, each after enabling the `crux-reliance` group ([shards](../docs/ci-zephyr-shards.md#shards)).

| Suite | What it shows | Record |
| --- | --- | --- |
| `tests/native/emmc_stack` | Initialisation, geometry, reads and writes, unaligned buffers, bounds, injected faults, and the cache flush correction `CRUX_MMC_CACHE_FLUSH` of [`patches/zephyr`](../patches/zephyr/README.md); a sync flushes only when the option is on | [Composition](../docs/emmc-reliance-composition.md) |
| `tests/native/emmc_restart` | Separate processes on the host file: data on the medium outlives the process and cached data does not | [Composition](../docs/emmc-reliance-composition.md) |
| `tests/native/file_reliance` | Reliance Edge behind the Zephyr VFS on a RAM disk `MMC`: the adapter, and the File contract and additions at offset 0 and at an offset volume | [Composition](../docs/emmc-reliance-composition.md) |
| `tests/native/file_emmc_composition` | The mount sequence of `samples/boards/nxp/mimxrt1060_evk/emmc_file`: unchanged-medium and blank-medium checks, fail-closed start, a sync reaches the persistent image | [Composition](../docs/emmc-reliance-composition.md) |
| `tests/native/configuration_settings_reliance` | The Settings File suite on Reliance Edge over a RAM disk, with the real provider and a control on the unpatched backend | [Composition](../docs/emmc-reliance-composition.md) |
| `tests/native/configuration_settings_littlefs` (run by `scripts/test-storage-simulators.sh`, in CI) | The same suite on LittleFS over a block device, with the real provider and a control on the unpatched backend | [Composition](../docs/emmc-reliance-composition.md) |
| `tests/native/emmc_powercut` | Power-cut replay on FatFs and Reliance Edge for workloads W1 to W4 and W8 (a file replaced through the Crux File provider), at chosen cut points under four models, with controls that must fail; the LittleFS replays (W4, W5, W8) run from `scripts/test-storage-simulators.sh` | [FatFs](../docs/evidence/emmc-reliance/replay-fatfs/README.md), [Reliance Edge](../docs/evidence/emmc-reliance/replay-reliance/README.md), [Settings](../docs/evidence/emmc-reliance/replay-settings/README.md), [File replace](../docs/evidence/emmc-reliance/replay-file-w8/README.md) |
| `tests/native/reliance_stage_a` | The five Stage A images of the [eMMC physical gate](../docs/emmc-reliance-physical-gate.md) on the simulator with the disk named `SD`; it exercises application logic, the File provider and Reliance Edge, not the SD host driver or a card | [Physical gate](../docs/emmc-reliance-physical-gate.md) |

`scripts/test-file-emmc-compile.sh` links `samples/boards/nxp/mimxrt1060_evk/emmc_file` and the `tests/board_images/sd_card_power_cut_sequence` images for the RT1060-EVKB, reads each generated `.config`, and checks which drivers, the formatter and the entry points are linked. Configurations without the cache flush, with the fixture-only controls or in the wrong place must fail at CMake. It needs the optional west group `crux-reliance`, builds no image that is kept, and runs nothing; the sizes are in the [link record](../docs/evidence/emmc-reliance/rt1060-link/README.md).

## Monotonic timing

Time owns typed monotonic observation and deadlines, and Thread owns sleep. Their common and Linux error, rounding, overflow and early-wake tests run with the Host checks, including `Thread.TypedLinuxIntegration`. Native 128-Hz deadline and ISR checks are in `tests/thread/zephyr_fractional`, which `scripts/test-messaging.sh` runs with the controller timing consumer in `tests/messaging_consumer`. `tests/build/test_consumer_boundary.py` checks that the Queue targets are absent. See the [messaging contract](../docs/messaging-contract.md).

## GPIO

`GPIO.Host` runs a native-free input consumer against an in-memory provider; `GPIO.NativeStatus` maps native driver results to Crux statuses. A `native_sim` Ztest uses Zephyr GPIO emulation for logical state, Devicetree active-low inversion, argument errors and interrupt-context rejection. `tests/gpio/zephyr_failure` reaches native driver failures through the emulator with Zephyr assertions disabled. `scripts/test-gpio.sh` rejects missing, disabled and malformed Devicetree selections and an unsupported provider, and cross-builds the portable consumer for RT1060-EVKB (user button, and Arduino header D2 from `tests/gpio/evkb/compositions`) and RT1170-EVK revision A. A controller that is not ready cannot be induced with the emulator. See the [GPIO contract](../docs/gpio-contract.md).

## I2C

`I2c.HostContract`, `I2c.PortableFaults` and `I2c.NativeStatus` cover the loopback provider, the portable layer against a register-device provider with injected failures, and the native-result mapping. A `native_sim` Ztest uses Zephyr's I2C emulation for repeated-start shape, error mapping and interrupt-context rejection. `tests/build/test_i2c_composition.py` rejects a missing alias, a disabled selection and an unsupported provider. The consumer `tests/i2c/consumer/tmp117.c` runs against a model of the sensor's registers (`I2c.Tmp117Consumer`) and on `native_sim` (`tests/i2c_consumer_zephyr`). The model is written from the data sheet; no part has been used. `scripts/test-i2c.sh` runs these and cross-builds `tests/i2c/evkb` for both boards. See the [I2C contract](../docs/i2c-contract.md).

## SPI

`Spi.HostContract`, `Spi.PortableFaults` and `Spi.NativeStatus` cover the loopback provider, the portable layer with injected failures, and the native-result mapping. A `native_sim` Ztest uses Zephyr's SPI emulation for full-duplex data, Devicetree transfer settings, error mapping and interrupt-context rejection. `tests/build/test_spi_composition.py` rejects a missing alias, a disabled selection, a peripheral that holds chip select, half-duplex, TI frame format and an unsupported provider. The consumer `tests/spi/consumer/spi_flash_id.c` reads a JEDEC identification as one full-duplex exchange (`Spi.FlashIdConsumer`, and `tests/spi_consumer_zephyr` on `native_sim`). The flash model follows data sheets; no part has been used, and chip-select behaviour is the Crux contract, not observable on `native_sim`. `scripts/test-spi.sh` runs these and cross-builds `tests/spi/evkb` for both boards. See the [SPI contract](../docs/spi-contract.md).

## Portable Serial

`scripts/test-serial.sh --host-only` runs independently authored public C17/C++17 consumers and the controller against disposable PTYs. The default command also runs UART-emulator and native ownership suites and cross-builds the EVKB fixture. The Host consumer selects `CRUX_BUILD_SERIAL` and `CRUX_BUILD_TIME` with an explicit Time provider through the root entry point. The composition test also compiles Serial on the fictional RT1062 board of `tests/zephyr/board_fixture` (LPUART3), where the mode, owner and resource checks still refuse. See [Serial qualification](../docs/serial-validation.md).

The Serial, Settings (`tests/native/configuration_settings`) and NVS startup (`tests/native/nvs_startup`) fixtures wrap a device in a proxy whose API table is outside the linker section that Zephyr checks with `CONFIG_DEVICE_API_ASSERT`. They build with it off, so they do not exercise that check.

## Portable Logging

`scripts/test-logging.sh --host-only` runs the independent C17/C++17 consumer and controller checks. The full script also checks rejected native compositions, UART-emulator output and the revision-B EVKB cross-build. Its composition test compiles Logging on `tests/zephyr/board_fixture` (LPUART2, next to Serial on LPUART3). Logging-only external profiles verify public usage and the exclusion of unrelated components. Root Host tests include `Logging.*`. See [Logging validation](../docs/logging-validation.md).

## Portable System Health and Reset

The root Host suite includes the common lifecycle and real Linux monotonic-provider tests. `scripts/test-system.sh --host-only` runs independent C17/C++17 consumers and controller policy checks; the full script adds native ownership and configuration, `native_sim` mappings and the revision-B EVKB cross-build. Its composition test compiles System on `tests/zephyr/board_fixture` with WDOG1 and on an RT1064 board, and checks that a watchdog node of another driver is refused. Normal Host reset and reset-cause services are unsupported. See [System validation](../docs/system-validation.md).

`tests/system/zephyr/native_sim_watchdog` is a console-harness scenario that restarts its own process on a missed feed and shows the boot cause, a feed cycle, a missed feed and the second boot with the cause SOFTWARE. `tests/consumer_system` runs the same scenario as an out-of-tree product; `scripts/test-consumer-system.sh` builds, checks and runs it, and `scripts/test-system.sh` calls it. See its [README](consumer_system/README.md).

## Portable Access control

The root Host suite runs `tests/access` as `Access.*` with fake ports, a controllable clock and fault injection. The fakes exist only when Crux builds its own tests. `scripts/test-access.sh` also runs them under the sanitizer preset, runs clang-tidy and runs `scripts/check-access-boundary.py`, which builds `tests/access_consumer` in both directions: a project cannot reach the adapter header, and a service that links the adapter target privately is accepted. No real provider exists, so none of this covers entropy, storage or timing on a target. See the [Access contract](../docs/access-contract.md).

`tests/bench_first_account` runs `BenchFirstAccount.provision` on the same fake ports for the [first account of the RT1060-EVKB bench image](../docs/rt1060-bench-first-account.md). The password file rules and the scan for the password in build outputs are Python tests (`tests/build/test_bench_first_account_file.py`, `test_bench_first_account_build.py`) that make every password at run time.

## Portable command line

The root Host suite runs `tests/cli` as `Cli.*` with a scripted transport, a recording event port, a scripted Serial, and either a scripted access control or the real `crux_access` on its fake ports. `scripts/test-cli.sh` also runs them under the sanitizer preset, runs clang-tidy, `scripts/check-cli-boundary.py` (which builds `tests/cli_consumer` both ways) and `scripts/check-cli-session-commands.py`, and the shell rule's Host tests in `tests/build/test_management_shell.py`. `scripts/test-cli.sh --zephyr`, in the Zephyr CI job, runs `tests/build/test_cli_composition.py`: refused compositions, accepted ones built on `native_sim`, and `tests/zephyr/cli_serial_compile` linked for the RT1060-EVKB with LPUART3. See the [command line contract](../docs/cli-contract.md).

## Command line over SSH

`Ssh.cli_*` in the root Host suite run the entry points in `tests/ssh/cli`. `Ssh.cli_session` compares them through the fake provider with the real serial console byte for byte, `Ssh.cli_real_access` runs them on the real `crux_access` core, `Ssh.cli_concurrency` shows one stuck client holding only itself, and `Ssh.cli_entry_symbols` reads what the object files can reach. `tests/ssh/cli/test-compile.sh`, in the Zephyr CI job, compiles them for `native_sim` and the RT1060-EVKB with no wolfSSH. `tests/ssh/cli/test-openssh.sh` runs them on the wolfSSH provider against a real OpenSSH client on `native_sim`; it needs the optional stacks, so no default workflow runs it. See [the CLI over SSH](../docs/cli-over-ssh.md).

## Portable credential store

The root Host suite runs `tests/credential` as `Credential.*`, on the File fake and on the Linux File provider. The protection in these suites is **test only** (a CRC in place of a tag and a keystream that is not encryption), exists only in a test composition, and `Credential.credential_production_refuses` shows a product build refusing it. The fault suites cut power before each File operation, each sector and each byte of every save, on a medium model. `scripts/test-credential.sh` also runs the sanitizer preset, clang-tidy and `scripts/check-credential-boundary.py`. `tests/native/credential_fatfs` and `credential_littlefs` run the conformance cases on real FatFs and on LittleFS over a RAM disk under `scripts/test-storage-simulators.sh`. See the [credential store](../docs/credential-store.md).

## Portable Security events

The root Host suite runs `tests/security_event` as `SecurityEvent.*`. Most suites control the clocks and the log through linker wraps; `rejections`, `read`, `waits` and `secrets` use the real Access core and provider, and `integration` links the product cores with real Logging, Thread, Sync and Time. `crux_security_event_fake` is a recording fake of the public contract for consumers' Host tests. `scripts/test-security-event.sh` also runs the sanitizer preset, clang-tidy and `scripts/check-security-event-boundary.py`. On `native_sim` the events run in `tests/native/management_composition` and `tests/native/management_services` (see [Management composition on `native_sim`](#management-composition-on-native_sim)). See the [Security event contract](../docs/security-event-contract.md).

## TLS certificate

The root Host suite runs `tests/tls_certificate` as `TlsCertificate.*`: a stateless parser suite, service suites on the real Access core with fake credential, hash, signature and random ports, and `tls_certificate_store` on the real credential store. `scripts/test-tls-certificate.sh host` also runs the sanitizer preset and clang-tidy. Where CMake finds OpenSSL's headers, `tls_certificate_differential` holds the parser to OpenSSL's decoder on 300,000 seeded mutations. `scripts/test-tls-certificate.sh psa` builds `tests/tls_certificate/psa` on TF-PSA-Crypto and checks a real key's certificate, request and PKCS #8 key with OpenSSL, including a TLS 1.3 handshake; CI does not run it. On `native_sim`, the image `tests/native/management_services` generates a certificate at first boot and loads it at the second. See the [TLS certificate design](../docs/tls-certificate.md).

## Web frontend

The web frontend has its own tools under `web/` and needs Node.js. Its commands, including the checks and browser tests that `.github/workflows/web.yml` runs, are in the [web guide](../web/README.md). The specification lint is `scripts/check-management-api.sh` with `python3 -m unittest discover -s tests/management_api`.

## SSH provider

The standard Host CTest includes `Ssh.ProviderConformance` (the cases in `tests/ssh/conformance.c` against a fake provider), `Ssh.ConformanceCatchesDefects` (each deliberate defect must fail its named case), `Ssh.Boundaries` (`scripts/check-ssh-boundaries.py`, with `tests/build/test_ssh_boundaries.py` showing it rejects each violation), `Ssh.FakeProvider`, `Ssh.AttachmentDouble` and `Ssh.CallbackTable`. The fake runs every callback on the calling thread, so it shows no concurrency, timing or protocol behaviour.

The runners below need the optional `crux-secure-management` west group, and no default workflow runs them:

| Runner | What it shows |
| --- | --- |
| `scripts/test-ssh-wolf-settings.sh` | `tests/zephyr/ssh_wolf_probe` compiles for `mimxrt1060_evk@B//qspi` and `native_sim/native/64`, with negative controls; its file port refuses every operation. See [the SSH provider contract](../docs/ssh-provider-contract.md) |
| `scripts/test-ssh-sftp-openssh.sh` | OpenSSH against the unedited wolfSSH SFTP handlers on Linux, through the real port and file service, replaying the requests of WinSCP |
| `scripts/test-ssh-sftp-native.sh` | The same cases on `native_sim` through the wolfSSH provider, the real file service and FatFs; `scripts/test-ssh-sftp-compile.sh` compiles the real operations for the target. See [the SFTP design](../docs/sftp-design.md) |
| `scripts/test-ssh-provider.sh` | The wolfSSH provider: conformance with a scripted client, a real OpenSSH client over the native socket offload, repeated boots with the host key from the credential store on its PSA ports, resource use, an RT1060 compile, and a refusal of the Mbed profile. `Ssh.wire` and `Ssh.wire_mutations` check client input with seeded mutations against an oracle. See [the wolfSSH provider](../docs/ssh-wolf-provider.md) |

`Ssh.sftp` runs the SFTP operations through the fake provider on the real file service and Access core, and `Ssh.sftp_port_shape` calls the port's macros as wolfSSH does.

## PSA Crypto qualification

`tests/psa_crypto` holds provider-neutral PSA Crypto conformance cases, a standalone Linux Host project, a `native_sim` Ztest app and two stub providers that prove the cases can fail. `provider_declarations.cmake` states what each provider does not support or fails, and the harnesses compare it with the run in both directions. `scripts/test-psa-crypto.sh [host|zephyr|target|all]` needs the optional `crux-secure-management` group. `host` runs the controls and both providers with and without sanitizers, `zephyr` runs Twister on `native_sim/native/64`, and `target` compiles both providers for `mimxrt1060_evk@B//qspi`. The `psa-crypto` workflow runs all three with `tf-psa-crypto` as the second argument, because a default workflow must not select the GPL stacks; wolfPSA runs locally only. See the [qualification record](../docs/psa-crypto-qualification.md) and the [design](../docs/psa-crypto-design.md).

`tests/psa_entropy` shows what Zephyr's Mbed TLS glue does when the entropy device fails, on a `native_sim` application over a test entropy device, in three Twister configurations that `scripts/test-psa-crypto.sh zephyr` runs. See [Entropy failure](../docs/psa-crypto-qualification.md#entropy-failure).

`tests/native/tcp_isn` shows what Zephyr's TCP stack does when the key read or the PSA hash of the initial sequence number fails, with the Crux module (refused) and without it (the negative control on upstream `tcp.c`). `scripts/test-tcp-isn.sh` runs both and a drift check, and the `psa-crypto` workflow runs it. See [patches/zephyr](../patches/zephyr/README.md#default-images-at-the-pin).

## Management composition on `native_sim`

| Directory | What it runs |
| --- | --- |
| `tests/management_providers` | Host `ManagementProviders.*`: the event providers, status sources and the Access clock, each against a controlled answer |
| `tests/psa_ports` | The PSA providers' cases on Host and `native_sim`; `tests/psa_ports/suites` runs the Access and credential suites on them with `-DCRUX_TEST_SUITES_ON_PSA=ON` |
| `tests/native/tls_offload_probe` | A TLS socket over the native socket offload with a client on the host |
| `tests/native/management_composition` | The services together on real providers |
| `tests/native/management_services` | Every other management service on the same providers behind HTTPS, driven over TLS by `driver.py`; see [every management service on `native_sim`](../docs/native-composition-242.md) |
| `tests/native/management_services/e2e`, `tests/web/project_sample` | The built Preact or Angular example packaged into the same image, and the small example project on Host; see [the web examples end to end](../docs/e2e-native-220.md) |
| `tests/native/management_ssh` | The services image with the wolfSSH provider beside the HTTPS listener (Wolf profile only), driven by OpenSSH and curl; see [the integrated image](../docs/ssh-integrated-image.md) |

`scripts/test-tls-offload-probe.sh [all|mbed|wolf]` and `scripts/test-native-composition.sh [host|mbed|wolf|target-mbed|target-wolf|all]` run them; `e2e-mbed` and `e2e-wolf` run `server_checks.py` and the browser cases of `web/e2e`. `mbed` needs the `mbedtls` and `tf-psa-crypto` projects, and the `psa-crypto` workflow runs it. `wolf` needs the `crux-secure-management` group and runs locally. `mbed` and `wolf` also build the services image and check it with `scripts/check-composition-image.py --services`. `target-*` only compiles. `scripts/test-ssh-integrated.sh [guards|build|controls|run|all]` builds and drives the SSH image and needs the same group. See the [composition](../docs/native-management-composition.md).

## Test-only scenarios and board test images

A scenario that only a test compiles lives with that test, not under `samples/`:

| Folder | What compiles and runs it |
| --- | --- |
| `tests/system_consumer/scenario/` | A controller system-health scenario, compiled by `tests/system_consumer`, which `scripts/test-system.sh` runs |
| `tests/configuration/controller_scenario.c` | A controller configuration scenario, compiled by the Host test `tests/configuration`, which `scripts/check-host.sh` runs |
| `tests/messaging_consumer/scenario/` | A bounded controller timing scenario, built and run by `scripts/test-messaging.sh` through `tests/messaging_consumer` |
| `tests/logging_consumer/scenario/`, `tests/serial_consumer/scenario/` | Compiled by `tests/logging_consumer` and `tests/serial_consumer`, which `scripts/test-logging.sh` and `scripts/test-serial.sh` run; `scripts/check-native-interfaces.py` checks their includes |
| `tests/web/project_sample/project/` | A project's own page and API route beside the management routes. The Host test `tests/web/project_sample` (CTest `Web.project_sample`, run by `scripts/check-host.sh`) compiles it, and `tests/build/test_project_sample.py` checks it |

Probe, power-cut and Flash safety images test a board or a procedure.
They teach no single thing, so they live under `tests/board_images/`, not under `samples/`:

| Folder | Twister ids |
| --- | --- |
| [`tests/board_images/sd_card_power_cut_append/`](board_images/sd_card_power_cut_append/README.md) | `crux.file.sd_card_power_cut_append` and `.test` |
| [`tests/board_images/sd_card_power_cut_replace/`](board_images/sd_card_power_cut_replace/README.md) | `crux.file.sd_card_power_cut_replace` and `.test` |
| [`tests/board_images/sd_card_probe/`](board_images/sd_card_probe/README.md) | `crux.file.sd_card_probe` and `.stack`, `.removal` |
| [`tests/board_images/sd_card_power_cut_sequence/`](board_images/sd_card_power_cut_sequence/README.md) | `crux.file.sd_card_power_cut_sequence` and `.start`, `.append`, `.replace`, `.format`, `.native`, `.native.start`, `.native.append`, `.native.replace`, `.native.format` |
| [`tests/board_images/flash_safety_check/`](board_images/flash_safety_check/README.md) | none: `scripts/test-flash-safety-check.sh` builds and inspects it and never programs it |
| [`tests/board_images/integration_probe/`](board_images/integration_probe/README.md) | The EVKB device, network and integrated images; see its README |

## Advisory test coverage

The [`coverage.yml`](../.github/workflows/coverage.yml) workflow measures how many lines and branches of `components/` the tests execute. It is advisory: no threshold, badge or required status exists, and nothing is uploaded outside GitHub. It runs by hand (`workflow_dispatch`), weekly and on each push to `main` that changes more than documentation.

| Part | Script | What runs |
| --- | --- | --- |
| Host | `scripts/coverage-host.sh run` then `report` | The root CMake tree with `--coverage` added (the `host-debug` settings otherwise) and its CTest set, built with Clang 18 and read with `llvm-cov gcov` through gcovr |
| `native_sim` | `scripts/coverage-native-sim.sh run` then `report` | The Time, Logging, System and FatFs File Twister suites on `native_sim/native/64`, through gcovr |

The instrumented Host run skips `Ssh.cli_entry_symbols` by name, because `--coverage` adds `llvm_gcda_*` and `llvm_gcov_init` references that the test rejects; it runs in the normal Host job. Each job writes a per-component table to the run summary and uploads an HTML report, `coverage.json`, a text report and `summary.md` as an artifact. `scripts/coverage-summary.py` builds the table; `tests/build/test_coverage_summary.py` and `tests/build/test_coverage_workflow.py` test it and keep the workflow advisory. To run the report step locally, install gcovr 8.3 and LLVM 18 (`llvm-cov-18`) by hand; the Dev Container has neither. A build or test failure fails the job; a report-step tool failure only leaves a warning.

Not measured: hardware runs, the Python and shell checks, suites outside the list above, consumer suites that `host.yml` builds in separate trees, test sources, and Zephyr, kernel, vendor and fetched library code. The figures show which code the tests execute, not whether the tests check it.
