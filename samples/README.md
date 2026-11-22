# Samples

Each folder under `samples/` is one of five kinds. Only the first two run on their own on a development machine.

| Kind | What you can do with it |
| --- | --- |
| **Runnable Zephyr application** | `west build ... -t run` on `native_sim/native/64`, and `west twister` through its `sample.yaml` |
| **Runnable Linux Host program** | Built by the repository's root `CMakeLists.txt`; run the program, or `ctest --preset host-debug -L sample`. `hello_crux/host/` is the exception: its own CMake project, as an external Linux application is |
| **Building block** | Source that a sample and a test both compile. It is not built or run by itself. A scenario that only a test compiles lives with that test under `tests/`, and the [test guide](../tests/README.md) describes it |
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
| `controller/zephyr/`, default `prj.conf` | Runnable Zephyr application | `west build -p always -b native_sim/native/64 -d build/controller crux-pilot/samples/controller/zephyr -t run`. Ends with `CONTROLLER_COMPLETE cycles=20`. Also `scripts/test-controller.sh` |
| `controller/zephyr/`, the `m3*.conf` and overlay configurations | Board-only application | Device, network and integrated board probes, cross-built by `scripts/test-controller-integration.sh` (also reached through its historical name `scripts/test-m3.sh`) and by `scripts/test-m3-rt1170.sh` for the RT1170. See `controller/README.md` |
| `controller/host/` | Runnable Linux Host program | `build/linux/debug/samples/controller/host/crux-controller-host`. CTest `Controller.HostScenario` (label `sample`) checks it with `scripts/check-controller.py` |
| `controller/core/`, `controller/include/` | Building block | The portable controller core. The two controller applications above and the Host test `tests/controller` compile it, and so does the system-health scenario of `tests/system_consumer` |
| `networking/echo_client/host/` | Runnable Linux Host program | `build/linux/debug/samples/networking/echo_client/host/crux-networking-host [numeric-ipv4]` exchanges one TCP and one UDP echo with a peer on ports 42420 and 42421 (default `127.0.0.1`). CTest `Sample.EchoClientHost` starts a local echo peer for it |
| `networking/echo_client/` | Board-only application | The same exchange as an EVKB image, cross-built by `scripts/test-networking.sh`. It needs a board on an isolated network with a peer; Twister id `crux.sample.networking.echo_client` runs it only with the `crux_echo_peer` fixture. See its README |
| `networking/echo_client/common/` | Building block | The echo client (`client.c`, `client.h`) that both networking programs and the tests `tests/networking`, `tests/networking_zephyr` compile |
| `flash_safety_poc/` | Board-only application | A compile-only Flash safety proof of concept for the EVKB. `scripts/test-flash-poc.sh` builds and inspects it and never programs it |
| `management_rt1060_mbed/` | Board-only application | The RT1060-EVKB management image on the Mbed TLS profile, built (never flashed) by `scripts/test-management-mbed-rt1060.sh`. See [the image page](../docs/rt1060-mbed-management-image.md) |
| `storage_emmc/` | Board-only application | eMMC composition, link only on the EVKB (`testcase.yaml`), by `scripts/test-file-emmc-compile.sh`. `scripts/test-storage-emmc.sh` compiles its sources into the `native_sim` tests `tests/native/file_emmc_composition` and `tests/native/configuration_settings_reliance` |
| `storage_reliance_sd/` | Board-only application | Reliance Edge microSD images, link only on the EVKB, by `scripts/test-file-emmc-compile.sh`. Its `native` scenarios are built for the rehearsal that `scripts/test-storage-emmc.sh` runs, and need the optional `crux-reliance` west group |
| `storage_sd/`, `storage_sd_interrupt/`, `storage_sd_probe/`, `storage_sd_replace/` | Board-only application | microSD compositions and power-cut tests, link only on the EVKB (`testcase.yaml`), by `scripts/test-file-rt1060-compile.sh`. `scripts/test-storage-simulators.sh` compiles their sources into `native_sim` tests under `tests/native/` |
| `web/angular/`, `web/preact/` | Web front end | Browser examples of the management API; the [web guide](../web/README.md) describes them. `scripts/test-native-composition.sh` builds them (Angular with `npm run build` in its folder, Preact with `node tools/build.ts` in `web/`) and runs browser tests against a `native_sim` image |

## Run every runnable sample

```sh
# Zephyr: the four runnable Zephyr applications (five test configurations) on native_sim
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
