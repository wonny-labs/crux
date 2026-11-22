# Samples

Each folder under `samples/` is one of five kinds. Only the first two run on their own on a development machine.

| Kind | What you can do with it |
| --- | --- |
| **Runnable Zephyr application** | `west build ... -t run` on `native_sim/native/64`, and `west twister` through its `sample.yaml` |
| **Runnable Linux Host program** | Built by the repository's root `CMakeLists.txt`; run the program, or `ctest --preset host-debug -L sample`. `hello_crux/host/` is the exception: its own CMake project, as an external Linux application is |
| **Building block** | Source that a sample and a test both compile. It is not built or run by itself. A scenario that only a test compiles lives with that test under `tests/` (see below) |
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
| `hello_crux/` | Runnable Zephyr application | The smallest application that uses Crux. `west build -p always -b native_sim/native/64 -d build/hello_crux crux-pilot/samples/hello_crux -t run`. Ready line `CRUX_HELLO_READY composition=zephyr`. Twister id `crux.sample.hello_crux`. See its README |
| `hello_crux/host/` | Runnable Linux Host program | The same source on the Linux Host, built as its own CMake project that consumes Crux from its source tree. Not part of the root build or of CTest; `scripts/test-hello-crux.sh --host` builds and runs it. See the sample's README |
| `file/write_read/` | Runnable Zephyr application | Writes a file through the Crux File API and reads it back. `west build -p always -b native_sim/native/64 -d build/write_read crux-pilot/samples/file/write_read -t run`. Ends with `CRUX_FILE_WRITE_READ_OK provider=simulator`. Twister ids `crux.sample.file.write_read.simulator` and `crux.sample.file.write_read.fatfs_ram_disk` (the second selects FatFs on a RAM disk by configuration alone). See its README |
| `time/clock_shell/` | Runnable Zephyr application | `west build -p always -b native_sim/native/64 -d build/time crux-pilot/samples/time/clock_shell -t run`. Ready line `CRUX_TIME_READY composition=zephyr`, then a shell. Twister id `crux.sample.time.clock_shell`. Cross-built for the EVKB by `scripts/test-zephyr-time.sh`. See its README |
| `time/clock_shell/host/` | Runnable Linux Host program | `build/linux/debug/samples/time/clock_shell/host/crux-time-host`, commands on stdin. CTest `Sample.ClockShellHost`; also `scripts/check-host-sample.sh` |
| `networking/echo_client/host/` | Runnable Linux Host program | `build/linux/debug/samples/networking/echo_client/host/crux-networking-host [numeric-ipv4]` exchanges one TCP and one UDP echo with a peer on ports 42420 and 42421 (default `127.0.0.1`). CTest `Sample.EchoClientHost` starts a local echo peer for it |
| `networking/echo_client/` | Board-only application | The same exchange as an EVKB image, cross-built by `scripts/test-networking.sh`. It needs a board on an isolated network with a peer; Twister id `crux.sample.networking.echo_client` runs it only with the `crux_echo_peer` fixture. See its README |
| `networking/echo_client/common/` | Building block | The echo client (`client.c`, `client.h`) that both networking programs and the tests `tests/networking`, `tests/networking_zephyr` compile |
| `boards/nxp/mimxrt1060_evk/web_management/` | Board-only application | The RT1060-EVKB management image on the Mbed TLS profile, built (never flashed) by `scripts/test-management-mbed-rt1060.sh`. See [the image page](../docs/rt1060-mbed-management-image.md) |
| `boards/nxp/mimxrt1060_evk/emmc_file/` | Board-only application | Files on an eMMC through the Crux File API, with Reliance Edge (optional `crux-reliance` west group), built for the EVKB. Link only, because the EVKB has no eMMC: `scripts/test-file-emmc-compile.sh` links its three scenarios (Twister ids `crux.sample.boards.mimxrt1060_evk.emmc_file`, `.start`, `.settings`). `scripts/test-storage-emmc.sh` compiles its sources into the `native_sim` tests `tests/native/file_emmc_composition` and `tests/native/configuration_settings_reliance`. See its README |
| `boards/nxp/mimxrt1060_evk/sd_card_file/` | Board-only application | Files on the board's microSD card through the Crux File API, with FatFs. Link only: `scripts/test-file-rt1060-compile.sh` links its two scenarios (Twister ids `crux.sample.boards.mimxrt1060_evk.sd_card_file`, `.start`). `scripts/test-storage-simulators.sh` compiles its sources into `native_sim` tests under `tests/native/`, and the microSD board test images under `tests/board_images/` reuse them. See its README |
| `web/angular/`, `web/preact/` | Web front end | Browser examples of the management API; the [web guide](../web/README.md) describes them. `scripts/test-native-composition.sh` builds them (Angular with `npm run build` in its folder, Preact with `node tools/build.ts` in `web/`) and runs browser tests against a `native_sim` image |

Scenarios that only a test compiles live with that test, not under `samples/`:

| Folder | What compiles and runs it |
| --- | --- |
| `tests/system_consumer/scenario/` | A controller system-health scenario, compiled by `tests/system_consumer`, which `scripts/test-system.sh` runs |
| `tests/configuration/controller_scenario.c` | A controller configuration scenario, compiled by the Host test `tests/configuration`, which `scripts/check-host.sh` runs |
| `tests/messaging_consumer/scenario/` | A bounded controller timing scenario, built and run by `scripts/test-messaging.sh` through `tests/messaging_consumer` |
| `tests/logging_consumer/scenario/`, `tests/serial_consumer/scenario/` | Compiled by `tests/logging_consumer` and `tests/serial_consumer`, which `scripts/test-logging.sh` and `scripts/test-serial.sh` run; `scripts/check-native-interfaces.py` checks their includes |
| `tests/web/project_sample/project/` | A project's own page and API route beside the management routes. The Host test `tests/web/project_sample` (CTest `Web.project_sample`, run by `scripts/check-host.sh`) compiles it, and `tests/build/test_project_sample.py` checks it |

### Moved board test images

Probe, power-cut and Flash safety images test a board or a procedure; they teach no single thing, so they are not
samples. They moved to `tests/board_images/` with the same checks under new Twister ids, and the two board
compositions moved under `boards/`:

| Old path | New path | Twister ids |
| --- | --- | --- |
| `samples/storage_emmc/` | `samples/boards/nxp/mimxrt1060_evk/emmc_file/` | `crux.sample.boards.mimxrt1060_evk.emmc_file` and `.start`, `.settings` |
| `samples/storage_sd/` | `samples/boards/nxp/mimxrt1060_evk/sd_card_file/` | `crux.sample.boards.mimxrt1060_evk.sd_card_file` and `.start` |
| `samples/storage_sd_interrupt/` | [`tests/board_images/sd_card_power_cut_append/`](../tests/board_images/sd_card_power_cut_append/README.md) | `crux.file.sd_card_power_cut_append` and `.test` |
| `samples/storage_sd_replace/` | [`tests/board_images/sd_card_power_cut_replace/`](../tests/board_images/sd_card_power_cut_replace/README.md) | `crux.file.sd_card_power_cut_replace` and `.test` |
| `samples/storage_sd_probe/` | [`tests/board_images/sd_card_probe/`](../tests/board_images/sd_card_probe/README.md) | `crux.file.sd_card_probe` and `.stack`, `.removal` |
| `samples/storage_reliance_sd/` | [`tests/board_images/sd_card_power_cut_sequence/`](../tests/board_images/sd_card_power_cut_sequence/README.md) | `crux.file.sd_card_power_cut_sequence` and `.start`, `.append`, `.replace`, `.format`, `.native`, `.native.start`, `.native.append`, `.native.replace`, `.native.format` |
| `samples/flash_safety_poc/` | [`tests/board_images/flash_safety_check/`](../tests/board_images/flash_safety_check/README.md) | none: `scripts/test-flash-safety-check.sh` builds and inspects it (old name `scripts/test-flash-poc.sh` kept as an alias) and never programs it |

### Where the reference controller went

The reference controller is not a sample, because a sample that mixes a periodic task, board probes and network images
teaches no single thing. Its checks are kept: the periodic scenario with its Host (ASan/UBSan), `native_sim` and EVKB
checks is [`tests/time_periodic`](../tests/time_periodic/README.md); the boot fixture is
[`tests/boot_fixture`](../tests/boot_fixture/README.md); the EVKB device, network and integrated images are
[`tests/board_images/integration_probe`](../tests/board_images/integration_probe/README.md); the shared EVKB network
overlay is `boards/nxp/mimxrt1060_evk/common/network.overlay`. For a first periodic task read Zephyr's
`samples/basic/threads`; threads and synchronization are not Crux samples.

## Run every runnable sample

```sh
# Zephyr: every runnable Zephyr application on native_sim
west twister -T crux-pilot/samples -p native_sim/native/64 -t sample
# Linux Host: all Host programs (run from crux-pilot after scripts/bootstrap-host.sh)
ctest --preset host-debug -L sample
```

The `sample` tag selects the entries of the runnable applications. The board-only samples allow only the EVKB, so
`-p native_sim/native/64` skips them with or without the tag. `emmc_file` links Reliance Edge: built for the EVKB in a
workspace without the optional `crux-reliance` west group, it stops on purpose, because Crux's Reliance Edge build
stops when its source is missing rather than skipping.

## Adding a runnable sample

Give a Zephyr application a `sample.yaml` with the tag `sample`, `platform_allow` and `integration_platforms` for
`native_sim/native/64`, and a `harness: console` regular expression on a line that proves it ran. Give a Linux Host
program a CTest test with the label `sample`; [`scripts/run-host-sample.py`](../scripts/run-host-sample.py) feeds it
stdin and checks its output lines.
