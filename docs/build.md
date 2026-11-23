# Build and Integration Guide

This guide describes the supported ways to build Crux and consume its capabilities from another application. It covers the Linux development Host, the Zephyr module and Linux source-tree integration. For component behaviour and test-specific acceptance evidence, use the linked contracts and [test guide](../tests/README.md).

## Choose a build path

| Use case | Entry point | Scope |
| --- | --- | --- |
| Develop and test Crux on Linux | The Dev Container, whose `scripts/bootstrap.sh` runs `scripts/bootstrap-host.sh`, and CMake presets | Current Linux amd64 development environment |
| Build a Zephyr application | `west` with Crux's `zephyr/module.yml` | Pinned Zephyr workspace, selected `native_sim` and EVKB configurations |
| Consume Crux from a separate Linux CMake project | Root `add_subdirectory()` | Source-tree integration in the supported Linux environment |
| Start a product repository on Crux | [Product Composition Guide](product-composition.md) | Zephyr only, no Crux release tag yet |
| Build an application with MCUboot (proposed) | [Boot composition](boot-composition.md) | Build only, RT1060-EVK Rev B, no boot result |

Linux Host is a development and test composition, **not** a qualified production Embedded Linux variant. The Zephyr EVKB cross-build proves that a selected firmware image compiles and links, not that it boots or operates correctly on hardware. Installed packages, `find_package(Crux)`, a binary SDK and arbitrary toolchain or board combinations are not supported by this guide.

## Development environment

**First set-up:** read [Getting started](getting-started.md) first. It covers the Git clone, the folder layout and the folder name the scripts require, Windows with WSL2, line endings, network and proxy access, and disk and memory.

Use the repository's [Dev Container](../.devcontainer/devcontainer.json) with Docker and VS Code's Dev Containers extension. Its pinned Ubuntu 24.04 amd64 environment includes Clang 18 and installs CMake 3.28.4, Ninja 1.11.1, west 1.4.0 (with bash Tab completion for its commands inside the west workspace) and the documented Python tools. The container is configured for 2 CPUs and 4 GiB of memory. After it is created it runs `scripts/bootstrap.sh`, which installs those tools into a Python environment in the cache volume, builds and tests the Host preset and sets up the west workspace and the Zephyr SDK, skipping what is already done ([The Dev Container sets itself up](getting-started.md#6-the-dev-container-sets-itself-up)). The same container serves a board: it can reach a USB debug probe and installs the J-Link software when its package is given ([J-Link board route](board-jlink-usbipd.md)).

**Apple silicon and other arm64 hosts.** The Dev Container is pinned to `linux/amd64` (`--platform=linux/amd64` in `devcontainer.json`). On an arm64 machine, such as an Apple-silicon Mac, Docker runs it under emulation, which is slow. Running the full Host and Zephyr suites that way is impractical. CI is the supported way to run them in full: push the branch to a (Draft) pull request, or start the workflow manually, and read the results of the `host-foundation` and `zephyr-software` workflows (the Zephyr workflow ignores changes that touch only Markdown or `docs/`). Use a local run for the narrow checks of the code you changed. This guide gives no time estimate. For disk and memory, see [Disk and memory](getting-started.md#5-disk-and-memory) in Getting started, and confirm the available disk space before the SDK installation (see [Zephyr build and module integration](#zephyr-build-and-module-integration)).

Open `crux-pilot/` in VS Code and choose **Dev Containers: Reopen in Container**. The container mounts the repository's parent directory, with this layout:

~~~text
/workspace/
  crux-pilot/    # This Git repository
  .west/         # Created by west init
  zephyr/        # Pinned upstream checkout
  modules/       # Selected Zephyr dependencies
~~~

Run the commands below from `/workspace/crux-pilot` inside the container unless a different working directory is specified. The container supplies `CRUX_WORKSPACE=/workspace` and uses an external cache. Keep generated builds under `build/` and the west workspace, SDK and dependencies outside the Crux Git source tree.

## Linux Host build

**What the Linux Host providers are used for.** They run the Host tests (CTest with GoogleTest suites and standalone C/C++ tests, see the [test guide](../tests/README.md)). The `host-sanitize` preset builds them with AddressSanitizer and UndefinedBehaviorSanitizer, through `CRUX_HOST_PRESET=host-sanitize scripts/check-host.sh` and several `scripts/test-*.sh` runners. `scripts/test-mgmt-services.sh` and `tests/ssh/cli/test-thread-sanitizer.sh` run selected suites under ThreadSanitizer. In this repository these sanitizer builds run on Linux Host, while Zephyr `native_sim` runs Ztest. The Host providers also serve source-tree consumers, as in [External Linux application using Crux source](#external-linux-application-using-crux-source), [`tests/consumer_poc`](../tests/consumer_poc/README.md) and `tests/external_application`. This is not Embedded Linux support.

The source root uses [CMake presets](../CMakePresets.json) named `host-debug` and `host-sanitize`. The initial build, dependency acquisition and Host CTest run are the host step of `scripts/bootstrap.sh`, which the Dev Container runs after it is created; by hand:

~~~sh
scripts/bootstrap-host.sh
~~~

For repeatable subsequent builds and tests with network dependency resolution disabled:

~~~sh
scripts/check-host.sh
~~~

To run the sanitizer configuration (AddressSanitizer and UndefinedBehaviorSanitizer), after initial dependency setup:

~~~sh
CRUX_HOST_PRESET=host-sanitize scripts/check-host.sh
~~~

The scripts configure, build and run CTest using the selected preset. Output is written under `build/linux/debug/` or `build/linux/sanitize/`, including `ctest-junit.xml`. To build or test an existing configured preset directly:

~~~sh
cmake --build --preset host-debug
ctest --preset host-debug
~~~

The root build enables Crux's development components and samples by default. `CRUX_BUILD_TESTS` initially follows the root project's `BUILD_TESTING` setting. Disabling internal tests also avoids the Crux GoogleTest/C++ test setup. The test and sample options are independent, so set `CRUX_BUILD_HOST_SAMPLE=OFF` and `CRUX_BUILD_TIME_PERIODIC_SCENARIO=OFF` as well when the corresponding development targets are not wanted. Component-specific options are described below.

For the complete quality checks and component-specific runners, use the [test guide](../tests/README.md). `scripts/check-format.sh`, `scripts/analyze-host.sh` and `scripts/check-dependencies.sh` validate formatting, configured analysis and dependency boundaries. Analysis uses the configured compiler database and can report existing upstream or suppressed diagnostics, so a successful run does not imply zero warnings. The list of sources that clang-tidy analyses is moving from hand-written paths to a list generated from the compile databases (`scripts/tidy-sources.py`); [static-analysis coverage](static-analysis-coverage.md) gives the measurement, the stages and their status.

## Zephyr build and module integration

Zephyr is integrated through [zephyr/module.yml](../zephyr/module.yml), [zephyr/CMakeLists.txt](../zephyr/CMakeLists.txt) and [zephyr/Kconfig](../zephyr/Kconfig), **not** through the Linux Host root CMake entry point. The [west manifest](../west.yml) pins the Zephyr revision and selected CMSIS/NXP modules.

The zephyr step of `scripts/bootstrap.sh`, which the Dev Container runs after it is created, initialises or updates the separate west workspace and installs the pinned Zephyr SDK and Arm toolchain. By hand:

~~~sh
scripts/bootstrap-zephyr.sh --install-sdk
~~~

The bootstrap uses `west init -l` when needed, updates the pinned dependencies and installs SDK v1.0.1 with `arm-zephyr-eabi` support. Confirm available disk space before SDK installation.

Run a documented reference-controller scenario on Zephyr `native_sim` and cross-build its EVKB firmware:

~~~sh
scripts/test-time-periodic.sh
~~~

For the Time capability's Twister tests, `native_sim` sample build and EVKB cross-build:

~~~sh
scripts/test-zephyr-time.sh 'mimxrt1060_evk@B//qspi'
~~~

Both commands use the module from this checkout. The current EVKB target is `mimxrt1060_evk@B//qspi`, limited to its documented configuration.

The Crux module compares the Zephyr release in use with the one Crux was verified on. On another release, every build that enables the module warns and continues without Crux evidence. `-DCRUX_REQUIRE_VERIFIED_ZEPHYR=ON` stops such a build instead. `west crux-pins` compares the workspace's project commits with the ones Crux pins and fails on an undeclared difference; see [its description](product-composition.md#west-crux-pins).

For another Zephyr application in the west workspace, prefer `EXTRA_ZEPHYR_MODULES` to add Crux while retaining the modules discovered through west. Existing Crux scripts also use the supported older spelling `ZEPHYR_EXTRA_MODULES`. By contrast, `ZEPHYR_MODULES` replaces automatic discovery and must list **all** required modules, not just Crux. For example, the following command builds the existing controller application on `native_sim` without hardware operations:

~~~sh
repo="$PWD"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
export ZEPHYR_BASE="$workspace/zephyr"
(cd "$workspace" && west build -p always -b native_sim/native/64 \
    -d "$repo/build/zephyr/controller-example" \
    "$repo/tests/time_periodic/zephyr" -- -DEXTRA_ZEPHYR_MODULES="$repo")
~~~

**Applications with MCUboot (build only).** The sysbuild route of `scripts/test-boot-composition.sh` passes Crux with the older spelling, `-DZEPHYR_EXTRA_MODULES=<crux>`. MCUboot itself is not added as a module: it is the plain west project `mcuboot` in the optional group `crux-boot`, which the script enables with `west config manifest.group-filter` and fetches with `west update mcuboot`. Do not pass MCUboot through the module flags. The signing step needs packages that the Zephyr requirements do not list; the script installs them with `python3 -m pip install -r <workspace>/bootloader/mcuboot/scripts/requirements.txt` after the fetch. Run it by hand the same way if you build outside the script. The [boot composition](boot-composition.md) page gives the argument set and its status.

Select the required `CONFIG_CRUX_*` Kconfig capabilities and supply board/project Devicetree and hardware-resource bindings where the component requires them. Follow the applicable capability contract and an existing tested Zephyr fixture instead of copying Linux provider settings.

Do not infer that every Linux Host capability has an equivalent Zephyr provider. Serial and Logging require explicitly supported UART resources and ownership settings, while Time's Zephyr system clock needs no RTC; optional RTC storage is separate from Linux system or development-memory realtime. The full [Zephyr test commands](../tests/README.md) and [architecture overview](architecture.md#build-and-platform-composition) describe the supported profiles and their limits. None of the build scripts above flashes, resets or operates the physical EVKB.


## RT1060-EVKB debugging

The board procedures for the RT1060-EVKB, including the J-Link GDB Server, the VS Code debug profiles, debug builds of other applications and what the platform provides for build and debug, are on the [MIMXRT1060-EVKB board page](boards/mimxrt1060_evkb.md#flash-and-debug).

## External Linux application using Crux source

The verified external-consumer contract uses the **root** `add_subdirectory()` entry point. When included as a dependency, Crux selects **Base only** by default. The parent project's `BUILD_TESTING`, enabled languages and language-standard settings remain its own. Crux's tests and samples default OFF in this mode.

Enable only the needed capabilities before inclusion with `CRUX_BUILD_<COMPONENT>`. The available choices are `TIME`, `THREAD`, `SYNC`, `NETIF`, `SOCKETS`, `CONFIGURATION`, `FILE`, `GPIO`, `SERIAL`, `LOGGING`, `SYSTEM`, `I2C`, `SPI`, `ACCESS`, `FILE_SERVICE`, `CREDENTIAL`, `SECURITY_EVENT`, `CONFIG_SERVICE`, `MGMT_STATUS`, `CLI`, `NETWORK_SETTINGS`, `REBOOT`, `IMAGE_STATE`, `WEB` and `TLS_CERTIFICATE`. Base is always available. Some choices require others, and the [capability and provider table](#capability-and-provider-selection) lists the requirements.

### Complete Time and Thread example

This example shows how an external consumer selects components and links their
targets. It is not a model for new product code: Thread, Sync and Serial are
frozen for new product code, so a new product uses Zephyr threads and message queues
in its own Zephyr code (see [Choosing an API](choosing-an-api.md)). Existing users
keep working, and the build mechanics below are unchanged. Crux Queue was removed on
20 November 2026; a message queue is Zephyr's `k_msgq` (see the
[messaging contract](messaging-contract.md) for the migration note).

Create an application directory outside the Crux source tree. Add the following
three files; the example follows the [tested external fixture](../tests/external_application/CMakeLists.txt)
and selects Time and Thread. The portable logic reads the monotonic clock and waits
for an already reached deadline.

`logic.c`:

~~~c
#include <crux/time.h>
#include <crux/thread.h>

int controller_run(void) {
    crux_monotonic_time_t now = {0};
    return crux_monotonic_now(&now) != CRUX_OK || crux_thread_sleep_until(now) != CRUX_OK;
}
~~~

`main.c`:

~~~c
int controller_run(void);
int main(void) {
    return controller_run();
}
~~~

`CMakeLists.txt`:

~~~cmake
cmake_minimum_required(VERSION 3.28)
project(my_controller LANGUAGES C)

set(CRUX_BUILD_TIME ON CACHE BOOL "Use Crux typed clocks")
set(CRUX_TIME_PROVIDER memory CACHE STRING "Controlled development realtime")
set(CRUX_BUILD_THREAD ON CACHE BOOL "Use Crux absolute sleep")
add_subdirectory("${CRUX_SOURCE_DIR}" crux)

add_library(controller_logic STATIC logic.c)
set_target_properties(controller_logic PROPERTIES
    C_STANDARD 17 C_STANDARD_REQUIRED ON C_EXTENSIONS OFF)
target_link_libraries(controller_logic PRIVATE crux::time crux::thread)
crux_assert_portable_consumer(controller_logic)

add_executable(my_controller main.c)
target_link_libraries(my_controller PRIVATE
    controller_logic
    crux::time crux::thread)
~~~

From the **external application's directory**, configure and build with an absolute Crux source path:

~~~sh
cmake -S . -B build -G Ninja -DCRUX_SOURCE_DIR=/absolute/path/to/crux-pilot
cmake --build build
./build/my_controller
~~~

The executable exits with status zero on success. Its portable logic is compiled
against the public facades; the final executable declares the capabilities it uses,
and their public targets connect the current Linux providers. No tests, samples or unrelated Crux capabilities are selected
by this example, and it does not access a physical device.

Portable source targets use public headers (for example, `<crux/time.h>`), link the public `crux::` capability targets and can call `crux_assert_portable_consumer()` to reject native/private requirements. They must not include Crux's `src/` or `ports/` directories or link Linux-specific composition targets. The final executable explicitly links its used public capabilities and selects OS-specific implementations required by that composition. The consumer boundary checker validates the documented build graph, not arbitrary application architecture.

The external application tests also cover C++17, independently selected Thread/Sync, Serial/Logging/System consumers, parent-test isolation and invalid compositions. For a concise entry point to all build paths, see the [README](../README.md#quick-start).

## Capability and provider selection

| Capability or group | Linux source-tree composition rule |
| --- | --- |
| Base | `crux::base` always exists |
| Time | Set `CRUX_BUILD_TIME=ON` and explicitly select `CRUX_TIME_PROVIDER=memory` (controlled development) or `linux` (system realtime). Controlled Host samples require memory; Linux native writes need explicit application authority. Neither implies production qualification |
| Time CPU Busy-wait | Select `CRUX_TIME_BUSY_WAIT=ON` and Time with an explicit provider; link `crux::time`. Zephyr requires `CONFIG_CRUX_TIME=y` plus `CONFIG_CRUX_TIME_BUSY_WAIT=y`, without RTC. Disabled Busy-wait remains linkable and returns NOT_SUPPORTED for positive durations. See [limits and verified scope](time-busy-wait.md) |
| Thread, Sync | Select independently through `CRUX_BUILD_THREAD` and `CRUX_BUILD_SYNC`. Thread also requires `CRUX_BUILD_TIME=ON` and an explicit Time provider (`memory` for the current controlled Host composition). Their public targets connect the current Linux implementation |
| Access | Select `CRUX_BUILD_ACCESS=ON`, which requires `CRUX_BUILD_SYNC=ON`. `crux::access` links no port provider. The root build has no provider for derivation, random and keyed hash, because it has no PSA. It defines targets for the clock and the events (object targets) and the store (a static library) when those components are built. A composition links them and lists the PSA sources, and an image that calls Access without them does not link. The [Access contract](access-contract.md) records the current state. |
| Command line | Select `CRUX_BUILD_CLI=ON`, which requires `CRUX_BUILD_ACCESS=ON`. `crux::cli` holds command tables and handlers. Its event port needs a provider: a composition links the object target `crux_cli_security_events`, or an image that calls it does not link. Only Crux's own test compositions link it so far, among them the [`native_sim` services image](native-composition-242.md), and no product composition does. The [command line contract](cli-contract.md) records the current state. On Zephyr, `CONFIG_CRUX_CLI=y` and the shell rule there apply: without `CONFIG_CRUX_DEVELOPMENT_IMAGE`, such an image has no Zephyr shell. |
| File service | Select `CRUX_BUILD_FILE_SERVICE=ON`, which requires `CRUX_BUILD_ACCESS=ON`, `CRUX_BUILD_FILE=ON` and `CRUX_BUILD_SYNC=ON`. Its event port needs a provider: a composition links the object target `crux_file_service_security_events`, or an image that calls it does not link. Only Crux's own test compositions link it so far, among them the [`native_sim` services image](native-composition-242.md), and no product composition does. The [File service contract](file-service-contract.md) holds its rules and limits |
| Credential store | Select `CRUX_BUILD_CREDENTIAL=ON`, which requires `CRUX_BUILD_SYNC=ON` and `CRUX_BUILD_FILE=ON`. The root build has no protection provider, because it has no PSA. A composition lists the PSA provider's sources in `components/credential/ports/psa`, and an image that calls the public target without a provider does not link. A product build refuses the test-only ports at start. The [credential store](credential-store.md) records the current state. |
| Security events | Select `CRUX_BUILD_SECURITY_EVENT=ON`, which requires Access, Logging, Sync, Thread and Time. A final link adds the object target `crux_security_event_access_port`, or it does not link. A composition sets `CRUX_SECURITY_EVENT_RING`, `_RESERVE`, `_DRAIN_BURST` and `_DRAIN_PAUSE_MS` to suit its log buffer, and keeps the Logging threshold at INFO or more verbose. See the [Security event contract](security-event-contract.md). |
| Configuration | Select `CRUX_BUILD_CONFIGURATION=ON`. A composition with no provider links `crux_configuration_no_provider`, and a load or save then returns `NOT_SUPPORTED`. `CRUX_CONFIG_STRING_MAX` changes the longest string for every user of the header. See the [contract](configuration-contract.md) |
| Configuration service | Select `CRUX_BUILD_CONFIG_SERVICE=ON`, which requires `CRUX_BUILD_ACCESS=ON` and `CRUX_BUILD_CONFIGURATION=ON`. A composition links its event provider, the object target `crux_config_service_security_events`, and an image that calls it without one does not link. The [services contract](status-configuration-services.md) holds its rules and limits |
| Status service | Select `CRUX_BUILD_MGMT_STATUS=ON`, which requires Access, System, and Configuration for its library `crux_configuration_text`. A composition links `crux_mgmt_status_sources` and `crux_mgmt_status_no_security`, or its own providers. The [services contract](status-configuration-services.md) holds its rules and limits |
| Network settings | Select `CRUX_BUILD_NETWORK_SETTINGS=ON`, which requires Access, Configuration, the Configuration service, Sync and Thread. The root build refuses a configuration that lacks one. See the [network settings service](network-settings-service.md) |
| Reboot | Select `CRUX_BUILD_REBOOT=ON`, which requires Access, Configuration (for its character rule), Sync and Thread. The root build refuses a configuration that lacks one. See the [reboot service](reboot-service.md) |
| Image state | Select `CRUX_BUILD_IMAGE_STATE=ON`. `crux::image_state` holds the public header, the pure functions and the portable core. It links no provider: the Host double exists only when Crux builds its own tests. Experimental, with no bootloader provider and no board result. See the [image state contract](image-state-contract.md) |
| TLS certificate | Select `CRUX_BUILD_TLS_CERTIFICATE=ON`, which requires Access and the Credential store. The root build refuses a configuration that lacks one. See the [TLS certificate service](tls-certificate.md) |
| Web | Select `CRUX_BUILD_WEB=ON`, which requires Access. Name the sources that hold routes with `crux_web_routes` from `cmake/CruxWebRoutes.cmake`. On Zephyr select `CONFIG_CRUX_WEB`, and a composition supplies Access and starts the server. To serve a built frontend folder from firmware, call `crux_web_assets` from `cmake/CruxWebAssets.cmake` before `crux_web_routes`: see [web assets](web-assets.md). See the [web contract](web-contract.md). |
| Serial | Select `CRUX_BUILD_SERIAL=ON`. The existing Linux provider value is `CRUX_SERIAL_PROVIDER=host` and TTY binding belongs to platform composition |
| GPIO | Select `CRUX_BUILD_GPIO=ON`; the Host provider is an in-memory test simulation, and `host` is the only `CRUX_GPIO_PROVIDER` value in the root build. On Zephyr, `CONFIG_CRUX_GPIO=y` builds the native provider, and the application binds `crux-gpio0` to a node with a `gpios` property. See the [GPIO contract](gpio-contract.md) |
| I2C | Select `CRUX_BUILD_I2C=ON`; the Host provider is a deterministic loopback fixture for portable consumer tests. Zephyr applications compile the native provider and bind `crux-i2c0` to a selected controller |
| SPI | Select `CRUX_BUILD_SPI=ON`; the Host provider is a deterministic loopback fixture. Zephyr applications compile the native provider and bind `crux-spi0` to a selected peripheral |
| Logging | Select `CRUX_BUILD_LOGGING=ON`. The existing Linux provider value is `CRUX_LOGGING_PROVIDER=host` |
| System | Select `CRUX_BUILD_SYSTEM=ON` and use `crux::system`; the Linux provider value is `CRUX_SYSTEM_PROVIDER=host`. Host watchdog observation is emulated; normal Host reset/reset-cause operations are unsupported. See the [System validation and limits](system-validation.md) |
| Netif, File, Configuration | Select the required `CRUX_BUILD_*` option and use the public capability target. Linux Netif's primary interface uses `CRUX_NETIF_HOST_INTERFACE` (default `lo`) |
| Sockets | Select `CRUX_BUILD_SOCKETS=ON` and link `crux::sockets` for the specifically qualified standard IPv4 socket profile. It is not a Crux socket-wrapper implementation |

No capability exposes a Linux composition-only target since Crux Queue and its `crux::queue_linux` alias were removed (20 November 2026); setting `CRUX_BUILD_QUEUE` stops the configure with a pointer to Zephyr `k_msgq`. Providers have different internal linkage patterns. Do not link undocumented concrete implementation targets or infer a common provider framework. Names ending in `_linux` identify an implementation environment, not product qualification.

The final application executable must directly declare the public capabilities it uses for the documented compatible-provider checks. Detection through arbitrary static-library private-only forwarding graphs is **not** part of the current contract. For Zephyr, Kconfig, the module entry point and platform composition select implementations instead of `CRUX_BUILD_*` Host options. See the [native consumer policy](native-interface-policy.md#external-source-tree-application-composition) for the exact supported enforcement boundary.

## Validation and troubleshooting

For the focused external-application integration suite, from the Crux source root on Linux:

~~~sh
python3 -m unittest discover -s tests/build -p test_external_application.py -v
~~~

For all existing Python build checks, use `python3 -m unittest discover -s tests/build -v`. Independent Host consumers and Zephyr composition runners are listed in the [test guide](../tests/README.md). CI runs most of these on pull requests in a Host part and a Zephyr part; the Zephyr part skips a pull request that changes only documentation and runs in parallel jobs, described in [Zephyr CI shards](ci-zephyr-shards.md). Run tests appropriate to the claimed change rather than assuming Host success qualifies Zephyr or hardware behaviour.

| Symptom | Check |
| --- | --- |
| Unknown `crux::...` CMake target | Enable the matching `CRUX_BUILD_*` option **before** `add_subdirectory()`. For Zephyr, use the correct Kconfig/module path |
| Unwanted GoogleTest, C++ or sample targets in an external project | Check cached `CRUX_BUILD_TESTS`, `CRUX_BUILD_HOST_SAMPLE` and `CRUX_BUILD_TIME_PERIODIC_SCENARIO` settings. Use an isolated build directory |
| Missing or unsupported Time provider | An external Linux Time build requires explicit `CRUX_TIME_PROVIDER=memory` or `linux`. Zephyr system realtime uses Kconfig; optional RTC storage is separate |
| Serial/Logging provider conflict or unsupported selection | Review the existing `host`/`zephyr` provider contract and the selected build entry point. Do not mix Host and Zephyr providers |
| `CRUX_BUILD_QUEUE is obsolete` from CMake | Crux Queue was removed. Remove the option (`-UCRUX_BUILD_QUEUE` clears a cached value) and move the queue to Zephyr `k_msgq` in the product's Zephyr code ([migration note](messaging-contract.md)) |
| `native consumer requirement` from CMake | Remove private/native targets, headers or flags from the portable consumer. Keep platform composition separate |
| Zephyr module or device selection failure | Verify west bootstrap, pinned SDK, selected module checkout, Kconfig prerequisites and board/Devicetree resource ownership |
| Offline Host check cannot resolve GoogleTest | Run `scripts/bootstrap-host.sh` once to populate the dependency cache before `scripts/check-host.sh` |

## Testing a consumer application

Applications own their tests. Crux adds no test target, Kconfig symbol or public header for them, and it ships no mock per API: write doubles at your application's own port. A passing level implies nothing about another, and `native_sim` is not hardware evidence.

| Level | Entry point | Example in the [out-of-tree consumer](../tests/consumer_poc/README.md) |
| --- | --- | --- |
| Unit | Your own CTest. Portable logic behind your own port needs no Crux target | `host/test_periodic.c` |
| Host integration | The [root `add_subdirectory()` entry point](#external-linux-application-using-crux-source), with `crux_assert_portable_consumer()` on portable targets | `host/test_integration.c` |
| `native_sim` | `west build` or `west twister` with `EXTRA_ZEPHYR_MODULES`, in a west workspace | `zephyr_test/` |
| Functional | Standalone `pytest-twister-harness` on a `native_sim` build | `zephyr/`, `functional/` |
| Hardware | No supported entry point. The internal [device-control tool](../tools/device_control/README.md) is untested on hardware, and any reset or flash needs authorisation for the current task | None |

~~~sh
west build -b native_sim/native/64 -d <build> <application> -- -DEXTRA_ZEPHYR_MODULES=<crux>
west twister -p native_sim/native/64 -T <ztest-application> --extra-args=EXTRA_ZEPHYR_MODULES=<crux>
PYTHONPATH="$ZEPHYR_BASE/scripts/pylib/pytest-twister-harness/src" python3 -m pytest \
  -p twister_harness.plugin --twister-harness --device-type=native --build-dir=<build> <tests>
~~~

> **Warning: `EXTRA_ZEPHYR_MODULES` is skipped when there is no west workspace.** With only `ZEPHYR_BASE` set, Zephyr clears `WEST` and processes no modules. The failure is a missing `kconfig_module_dirs.cmake`, then undefined `CRUX_*` symbols, and neither names the cause. Run from a west workspace, whose manifest does not need to list Crux. Without a workspace, `ZEPHYR_MODULES=<crux>` has been shown to configure; that is the only part of it that has been run.

- `zephyr/module.yml` names the module `crux`, so its generated names are `ZEPHYR_CRUX_MODULE_DIR` and `CONFIG_ZEPHYR_CRUX_MODULE` in any checkout folder. See [Module name](product-composition.md#module-name).
- The harness is upstream code at Alpha status with no version promise, and `west.yml` fixes its revision. It needs `ZEPHYR_BASE` set, plus `pyyaml` and `pykwalify`, which it does not declare.
- Do not use the harness's `hardware` device type behind a safety claim: it flashes on every launch. The [proposal](test-foundation-proposal.md#pytest-twister-harness-findings) records this and the other gaps.

The proposal's [current state](test-foundation-proposal.md#current-state) lists what has run at each level and what has not.

### Hardware integration tests

The table above says hardware has no supported entry point. This section says what exists and what each source says, so that nothing is read into it. No hardware was operated for it, and nothing here qualifies a physical board.

**What CI can do: a fixture-gated scenario that is built and not run.** A Twister scenario whose `testcase.yaml` sets `harness_config: fixture: <name>` runs only when Twister is told that the fixture exists, with `--fixture` or a hardware map. Without it Twister builds the scenario and does not run it (read in `testsuite_runnable` of Zephyr v4.4.0 `testinstance.py` and in the [fixtures section](https://docs.zephyrproject.org/latest/develop/test/twister.html#fixtures) of the Twister guide; not run here). A product with a part wired to its board writes its wired-part scenario this way. CI then builds it on every change, so it cannot rot, and the image it builds is what an operator would load. Keep the pass or fail oracle in the application's console output, so that it does not depend on the route that runs it. Do not give CI the fixture name or a hardware map.

**The run is a hardware operation, and it is not a Twister run.** The sources say:

- **This guide:** hardware has "No supported entry point" (table above).
- **Decision 5** of the [accepted test-foundation decisions](test-foundation-proposal.md#decisions) routes hardware through a small Crux tool, the [device-control tool](../tools/device_control/README.md), and not through the Twister harness's `hardware` device type, because gating, evidence and locking would all sit outside the harness anyway.
- **Flashing:** the harness's `--device-type=hardware` flashes on every launch ([findings](test-foundation-proposal.md#pytest-twister-harness-findings)). The [device-control rule](test-foundation-proposal.md#device-control-contract) is the opposite: flashing is an explicit step, never performed by a fixture or on launch, and refused without `--allow-flash=<approval reference>`. Twister's own `--device-testing` also loads the image, with `west flash` or a custom flash command, to run a scenario. This guide therefore does not offer `--device-testing`, a hardware map or `--device-type=hardware` as a route, and Twister gives no safe way to run a scenario on a board. Allowing it would revisit Decision 5, with its own gate design.
- **Approval:** the device-control tool's step 5, its use from the first real consumer, is not started in this repository and needs its own approval ([recommended order](test-foundation-proposal.md#recommended-order)). Until then the tool has run against fake transports and scripted tools, with locking across real processes, and real pyserial on one disposable pseudo-terminal; never on a real serial port, probe, reset or flash ([current state](test-foundation-proposal.md#current-state)).

**What exists today** serves Crux's own images and is not a consumer interface: the physical runner `tests/target`, which never flashes and runs against an image that is already loaded ([test guide](../tests/README.md#physical-uart-target)), and the program and restore driver with its safety gates and registered image profiles ([image profiles](board-image-profiles.md)). A new image needs its own profile, which is a reviewed change.

Whatever the route, a reset, a flash or any other board operation needs explicit authorisation for the current task ([AGENTS.md](../AGENTS.md), and [support and safety boundaries](#support-and-safety-boundaries) below).

## Support and safety boundaries

A successful Linux Host test proves behaviour only for the tested Host setup. Zephyr `native_sim` validates selected simulated integration. EVKB cross-builds do not prove Flash layout safety, UART electrical operation, timing, peripheral access or physical persistence. Firmware download, reset, Flash write/erase and physical validation require separate task-specific approval and verified hardware/provenance.

Treat unmerged branches, experimental storage targets and candidate writable images as separate gated work. Selecting System does not automatically arm a watchdog; Zephyr System requires explicit platform composition for watchdog, reset and hardware-information resources. Consult the relevant [capability contracts](architecture.md#current-capability-integration) and [validation records](../tests/README.md) before claiming support or running a physical operation.
