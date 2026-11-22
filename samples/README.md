# Samples

Each folder under `samples/` is one of five kinds. Only the first two run on their own on a development machine.

| Kind | What you can do with it |
| --- | --- |
| **Runnable Zephyr application** | `west build ... -t run` on `native_sim/native/64`, and `west twister` through its `sample.yaml` |
| **Runnable Linux Host program** | Built by the repository's root `CMakeLists.txt`; run the program, or `ctest --preset host-debug -L sample` |
| **Building block** | Source that a test or a check script compiles into its own build. It is not built or run by itself |
| **Board-only application** | A Zephyr image for the MIMXRT1060-EVKB. This repository's checks only cross-build or link it; running it needs a board and an approved procedure |
| **Web front end** | Browser code that a web image packages. It is built with npm and tested in a browser against `native_sim` |

The [first-hour guide](../docs/first-hour.md) walks through running them. Commands below run from the west workspace
root, `/workspaces/crux` in the Dev Container, where `crux-pilot` is this repository. The Crux module needs no extra
argument there, because the workspace's west manifest is this repository. Do not add `-DEXTRA_ZEPHYR_MODULES` pointing
at a second Crux checkout, such as a linked Git worktree, in that workspace: both copies are then built, and CMake
stops on duplicate targets. For a workspace that does not list Crux, the
[Build and Integration Guide](../docs/build.md#testing-a-consumer-application) gives the `EXTRA_ZEPHYR_MODULES`
form for `west build` and `west twister`.

## Classification

| Folder | Kind | Build and run, or what uses it |
| --- | --- | --- |
| `time/time_shell/` | Runnable Zephyr application | `west build -p always -b native_sim/native/64 -d build/time crux-pilot/samples/time/time_shell -t run`. Ready line `CRUX_TIME_READY composition=zephyr`, then a shell. Twister id `crux.sample.time.time_shell`. Cross-built for the EVKB by `scripts/test-zephyr-time.sh`. See its README |
| `time/time_shell/host/` | Runnable Linux Host program | `build/linux/debug/samples/time/time_shell/host/crux-time-host`, commands on stdin. CTest `Sample.TimeShellHost`; also `scripts/check-host-sample.sh` |
| `controller/zephyr/`, default `prj.conf` | Runnable Zephyr application | `west build -p always -b native_sim/native/64 -d build/controller crux-pilot/samples/controller/zephyr -t run`. Ends with `CONTROLLER_COMPLETE cycles=20`. Also `scripts/test-controller.sh` |
| `controller/zephyr/`, the `m3*.conf` and overlay configurations | Board-only application | Device, network and integrated board probes, cross-built by `scripts/test-controller-integration.sh` (also reached through its historical name `scripts/test-m3.sh`) and by `scripts/test-m3-rt1170.sh` for the RT1170. See `controller/README.md` |
| `controller/host/` | Runnable Linux Host program | `build/linux/debug/samples/controller/host/crux-controller-host`. CTest `Controller.HostScenario` (label `sample`) checks it with `scripts/check-controller.py` |
| `controller/core/`, `controller/include/` | Building block | The portable controller core. The two controller applications above and the Host test `tests/controller` compile it |
| `controller/system/` | Building block | A controller system-health scenario, compiled by `tests/system_consumer`, which `scripts/test-system.sh` runs |
| `controller/configuration/` | Building block | A controller configuration scenario, compiled by the Host test `tests/configuration`, which `scripts/check-host.sh` runs |
| `networking/tcp_udp_echo/host/` | Runnable Linux Host program | `build/linux/debug/samples/networking/tcp_udp_echo/host/crux-networking-host [numeric-ipv4]` exchanges one TCP and one UDP echo with a peer on ports 42420 and 42421 (default `127.0.0.1`). CTest `Sample.TcpUdpEchoHost` starts a local echo peer for it |
| `networking/tcp_udp_echo/` | Board-only application | The same exchange as an EVKB image, cross-built by `scripts/test-networking.sh`. It needs a board on an isolated network with a peer; Twister id `crux.sample.networking.tcp_udp_echo` runs it only with the `crux_echo_peer` fixture. See its README |
| `networking/tcp_udp_echo/common/` | Building block | The echo client (`client.c`, `client.h`) that both networking programs and the tests `tests/networking`, `tests/networking_zephyr` compile |
| `messaging/` | Building block | A bounded controller timing scenario. `scripts/test-messaging.sh` builds and runs it through `tests/messaging_consumer` |
| `logging/` | Building block | Compiled by `tests/logging_consumer`, which `scripts/test-logging.sh` runs; `scripts/check-native-interfaces.py` checks its includes |
| `serial/` | Building block | Compiled by `tests/serial_consumer`, which `scripts/test-serial.sh` runs; `scripts/check-native-interfaces.py` checks its includes |
| `flash_safety_poc/` | Board-only application | A compile-only Flash safety proof of concept for the EVKB. `scripts/test-flash-poc.sh` builds and inspects it and never programs it |
| `management_rt1060_mbed/` | Board-only application | The RT1060-EVKB management image on the Mbed TLS profile, built (never flashed) by `scripts/test-management-mbed-rt1060.sh`. See [the image page](../docs/rt1060-mbed-management-image.md) |
| `storage_emmc/` | Board-only application | eMMC composition, link only on the EVKB (`testcase.yaml`), by `scripts/test-file-emmc-compile.sh`. `scripts/test-storage-emmc.sh` compiles its sources into the `native_sim` tests `tests/native/file_emmc_composition` and `tests/native/configuration_settings_reliance` |
| `storage_reliance_sd/` | Board-only application | Reliance Edge microSD images, link only on the EVKB, by `scripts/test-file-emmc-compile.sh`. Its `native` scenarios are built for the rehearsal that `scripts/test-storage-emmc.sh` runs, and need the optional `crux-reliance` west group |
| `storage_sd/`, `storage_sd_interrupt/`, `storage_sd_probe/`, `storage_sd_replace/` | Board-only application | microSD compositions and power-cut tests, link only on the EVKB (`testcase.yaml`), by `scripts/test-file-rt1060-compile.sh`. `scripts/test-storage-simulators.sh` compiles their sources into `native_sim` tests under `tests/native/` |
| `web/angular/`, `web/preact/` | Web front end | Browser examples of the management API; the [web guide](../web/README.md) describes them. `scripts/test-native-composition.sh` builds them (Angular with `npm run build` in its folder, Preact with `node tools/build.ts` in `web/`) and runs browser tests against a `native_sim` image |
| `web_project/` | Building block | A project's own page and API route beside the management routes; no image packages it. The Host test `tests/web/project_sample` (CTest `Web.project_sample`, run by `scripts/check-host.sh`) compiles it, and `tests/build/test_project_sample.py` checks it |

## Run every runnable sample

```sh
# Zephyr: both runnable Zephyr applications on native_sim
west twister -T crux-pilot/samples -p native_sim/native/64 -t sample
# Linux Host: all three Host programs (run from crux-pilot after scripts/bootstrap-host.sh)
ctest --preset host-debug -L sample
```

The `sample` tag selects the entries of the runnable applications. Without it, Twister also selects the link-only
entries, and the Reliance Edge `native` entries fail in a workspace without the optional `crux-reliance` west group.
That failure is deliberate: Crux's Reliance Edge build stops when its source is missing rather than skipping.

## Adding a runnable sample

Give a Zephyr application a `sample.yaml` with the tag `sample`, `platform_allow` and `integration_platforms` for
`native_sim/native/64`, and a `harness: console` regular expression on a line that proves it ran. Give a Linux Host
program a CTest test with the label `sample`; [`scripts/run-host-sample.py`](../scripts/run-host-sample.py) feeds it
stdin and checks its output lines.
