# Samples

Each folder under `samples/` is one of five kinds. Only the first two run on their own on a development machine.

| Kind | What you can do with it |
| --- | --- |
| **Runnable Zephyr application** | `west build ... -t run` on `native_sim/native/64`, and `west twister` through its `sample.yaml` |
| **Runnable Linux Host program** | Built by the repository's root `CMakeLists.txt`; run the program, or `ctest --preset host-debug -L sample` |
| **Building block** | Source that a test or a check script compiles into its own build. It is not built or run by itself |
| **Board-only application** | A Zephyr image for the MIMXRT1060-EVKB. This repository's checks only cross-build or link it; running it needs a board and an approved procedure |
| **Web front end** | Browser code that a web image packages. It is built with npm and tested in a browser against `native_sim` |

The [Tutorial](../docs/tutorial.md) walks through running them. Commands below run from the west workspace
root, `/workspace` in the Dev Container, where `crux-pilot` is this repository. The Crux module needs no extra
argument there, because the workspace's west manifest is this repository. Do not add `-DEXTRA_ZEPHYR_MODULES` pointing
at a second Crux checkout, such as a linked Git worktree, in that workspace: both copies are then built, and CMake
stops on duplicate targets. For a workspace that does not list Crux, the
[Build and Integration Guide](../docs/build.md#testing-a-consumer-application) gives the `EXTRA_ZEPHYR_MODULES`
form for `west build` and `west twister`.

## Classification

| Folder | Kind | Build and run, or what uses it |
| --- | --- | --- |
| `time/clock_shell/` | Runnable Zephyr application | `west build -p always -b native_sim/native/64 -d build/time crux-pilot/samples/time/clock_shell -t run`. Ready line `CRUX_TIME_READY composition=zephyr`, then a shell. Twister id `crux.sample.time.clock_shell`. Cross-built for the EVKB by `scripts/test-zephyr-time.sh`. See its README |
| `time/clock_shell/host/` | Runnable Linux Host program | `build/linux/debug/samples/time/clock_shell/host/crux-time-host`, commands on stdin. CTest `Sample.ClockShellHost`; also `scripts/check-host-sample.sh` |
| `networking/echo_client/host/` | Runnable Linux Host program | `build/linux/debug/samples/networking/echo_client/host/crux-networking-host [numeric-ipv4]` exchanges one TCP and one UDP echo with a peer on ports 42420 and 42421 (default `127.0.0.1`). CTest `Sample.EchoClientHost` starts a local echo peer for it |
| `networking/echo_client/` | Board-only application | The same exchange as an EVKB image, cross-built by `scripts/test-networking.sh`. It needs a board on an isolated network with a peer; Twister id `crux.sample.networking.echo_client` runs it only with the `crux_echo_peer` fixture. See its README |
| `networking/echo_client/common/` | Building block | The echo client (`client.c`, `client.h`) that both networking programs and the tests `tests/networking`, `tests/networking_zephyr` compile |
| `messaging/` | Building block | A bounded controller timing scenario. `scripts/test-messaging.sh` builds and runs it through `tests/messaging_consumer` |
| `logging/` | Building block | Compiled by `tests/logging_consumer`, which `scripts/test-logging.sh` runs; `scripts/check-native-interfaces.py` checks its includes |
| `serial/` | Building block | Compiled by `tests/serial_consumer`, which `scripts/test-serial.sh` runs; `scripts/check-native-interfaces.py` checks its includes |
| `flash_safety_poc/` | Board-only application | A compile-only Flash safety proof of concept for the EVKB. `scripts/test-flash-poc.sh` builds and inspects it and never programs it |
| `boards/nxp/mimxrt1060_evk/web_management/` | Board-only application | The RT1060-EVKB management image on the Mbed TLS profile, built (never flashed) by `scripts/test-management-mbed-rt1060.sh`. See [the image page](../docs/rt1060-mbed-management-image.md) |
| `storage_emmc/` | Board-only application | eMMC composition, link only on the EVKB (`testcase.yaml`), by `scripts/test-file-emmc-compile.sh`. `scripts/test-storage-emmc.sh` compiles its sources into the `native_sim` tests `tests/native/file_emmc_composition` and `tests/native/configuration_settings_reliance` |
| `storage_reliance_sd/` | Board-only application | Reliance Edge microSD images, link only on the EVKB, by `scripts/test-file-emmc-compile.sh`. Its `native` scenarios are built for the rehearsal that `scripts/test-storage-emmc.sh` runs, and need the optional `crux-reliance` west group |
| `storage_sd/`, `storage_sd_interrupt/`, `storage_sd_probe/`, `storage_sd_replace/` | Board-only application | microSD compositions and power-cut tests, link only on the EVKB (`testcase.yaml`), by `scripts/test-file-rt1060-compile.sh`. `scripts/test-storage-simulators.sh` compiles their sources into `native_sim` tests under `tests/native/` |
| `web/angular/`, `web/preact/` | Web front end | Browser examples of the management API; the [web guide](../web/README.md) describes them. `scripts/test-native-composition.sh` builds them (Angular with `npm run build` in its folder, Preact with `node tools/build.ts` in `web/`) and runs browser tests against a `native_sim` image |
| `web_project/` | Building block | A project's own page and API route beside the management routes; no image packages it. The Host test `tests/web/project_sample` (CTest `Web.project_sample`, run by `scripts/check-host.sh`) compiles it, and `tests/build/test_project_sample.py` checks it |

### Where the reference controller went

The reference controller is not a sample, because a sample that mixes a periodic task, board
probes and network images teaches no single thing. Its checks are kept: the periodic scenario with its Host
(ASan/UBSan), `native_sim` and EVKB checks is [`tests/time_periodic`](../tests/time_periodic/README.md); the boot
fixture is [`tests/boot_fixture`](../tests/boot_fixture/README.md); the EVKB device, network and integrated images
are [`tests/board_images/integration_probe`](../tests/board_images/integration_probe/README.md); the shared EVKB
network overlay is `boards/nxp/mimxrt1060_evk/common/network.overlay`. For a first periodic task read Zephyr's
`samples/basic/threads`; threads and synchronization are not Crux samples.

## Run every runnable sample

```sh
# Zephyr: the runnable Zephyr applications on native_sim
west twister -T crux-pilot/samples -p native_sim/native/64 -t sample
# Linux Host: all Host programs (run from crux-pilot after scripts/bootstrap-host.sh)
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
