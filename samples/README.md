# Samples

Each folder under `samples/` is one of five kinds. Only the first two run on their own on a development machine.

| Kind | What you can do with it |
| --- | --- |
| **Runnable Zephyr application** | `west build ... -t run` on `native_sim/native/64`, and `west twister` through its `sample.yaml` |
| **Runnable Linux Host program** | Built by the repository's root `CMakeLists.txt`; run the program, or `ctest --preset host-debug -L sample`. `hello_crux/linux/` is the exception: its own CMake project, as an external Linux application is |
| **Building block** | Source that a sample and a test both compile. It is not built or run by itself. A scenario that only a test compiles lives with that test under `tests/` (see below) |
| **Board-only application** | A Zephyr image for the MIMXRT1060-EVKB. This repository's checks only cross-build or link it; running it needs a board and an approved procedure |
| **Web front end** | Browser code that a web image packages. It is built with npm and tested in a browser against `native_sim` |

Commands run from the repository root, `/workspace/crux-pilot` in the Dev Container. Do not add `-DEXTRA_ZEPHYR_MODULES` for a second Crux checkout in that workspace: both copies are built, and CMake stops on duplicate targets. For a workspace that does not list Crux, see the [Build and Integration Guide](../docs/build.md#testing-a-consumer-application).

## Where to start

Start with the [Tutorial](../docs/tutorial.md). Threads and synchronization have no Crux sample; use Zephyr's `samples/basic/threads` and `samples/synchronization`. The periodic Time scenario is [`tests/time_periodic`](../tests/time_periodic/README.md).

## Classification

| Folder | Kind | Build and run, or what uses it |
| --- | --- | --- |
| `hello_crux/zephyr/` | Runnable Zephyr application | The smallest application that uses Crux. See its [README](hello_crux/README.md) |
| `hello_crux/linux/` | Runnable Linux Host program | The same program on the Linux Host, as its own CMake project that consumes Crux from its source tree. See the [sample's README](hello_crux/README.md) |
| `file/basic/zephyr/` | Runnable Zephyr application | Writes a file through the Crux File API and reads it back, with the provider chosen by configuration. See its [README](file/basic/README.md) |
| `file/basic/common/` | Building block | The application part (`basic.c`, `basic.h`), checked as a portable consumer |
| `time/shell/zephyr/` | Runnable Zephyr application | A shell on Crux Time. See its [README](time/shell/README.md) |
| `time/shell/linux/` | Runnable Linux Host program | The same commands, read from stdin. See the [sample's README](time/shell/README.md) |
| `time/shell/common/` | Building block | The command handler (`time_command.c`, `crux_time_command.h`) that both programs and the Time tests compile |
| `networking/echo_client/linux/` | Runnable Linux Host program | One TCP and one UDP echo with a peer; CTest starts a local peer. See the [sample's README](networking/echo_client/README.md) |
| `networking/echo_client/zephyr/` | Board-only application | The same exchange as an EVKB image; it needs an isolated network with a peer. See its [README](networking/echo_client/README.md) |
| `networking/echo_client/common/` | Building block | The echo client (`client.c`, `client.h`) that both networking programs and the tests `tests/networking` and `tests/networking_zephyr` compile |
| `boards/nxp/mimxrt1060_evk/web_management/` | Board-only application | The RT1060-EVKB management image on the Mbed TLS profile. See [the image page](../docs/rt1060-mbed-management-image.md) |
| `boards/nxp/mimxrt1060_evk/emmc_file/` | Board-only application | Files on an eMMC through the Crux File API, with Reliance Edge (optional `crux-reliance` west group). Link only. See its [README](boards/nxp/mimxrt1060_evk/emmc_file/README.md) |
| `boards/nxp/mimxrt1060_evk/sd_card_file/` | Board-only application | Files on the board's microSD card through the Crux File API, with FatFs. Link only. See its [README](boards/nxp/mimxrt1060_evk/sd_card_file/README.md) |
| `web/angular/`, `web/preact/` | Web front end | Browser examples of the management API ([Preact](web/preact/README.md), [Angular](web/angular/README.md)); the [web guide](../web/README.md) describes them |

## Files inside a sample

A sample is one folder, `samples/<name>` or `samples/<family>/<name>`. Its root holds only `README.md` and these folders:

| Folder | Holds | Compiled by | May include |
| --- | --- | --- | --- |
| `zephyr/` | A standard Zephyr application: `CMakeLists.txt`, `prj.conf`, `sample.yaml`, `Kconfig`, `boards/`, overlays, and its sources in `src/` | Zephyr only | What a Zephyr application may use; no Crux private or `ports/` path |
| `linux/` | A Linux program: `CMakeLists.txt` and its sources. The Linux Host build compiles it | Linux only | C library, POSIX and public Crux headers |
| `common/` | Code that both `zephyr/` and `linux/` compile (or one of them and a test of the other), and code checked with `crux_assert_portable_consumer` | Both | ISO C, public `<crux/NAME.h>` headers other than `thread.h`, `sync.h`, `serial.h` and the `_zephyr`/`_linux` composition headers, the Sockets profile where `scripts/check-native-interfaces.py` allows it, and its own headers. No platform test such as `CONFIG_` or `__ZEPHYR__` |

A sample has only the OS folders it runs on.
No sample has an `include/`: headers sit beside their sources.
`linux/` and `common/` are flat: their files sit at the folder's top level, with no `src/`.
Give `linux/` a `src/` only when it must hold files other than sources and build files, and then in every sample in the same change.
No build names another OS folder.
`common/` follows the include rule of the product template's `domain/`.

Exceptions, each by tree: `samples/boards/<vendor>/<board>/<name>/` is a Zephyr image for that board with the application at its own root, and `samples/boards/<vendor>/<board>/common/` holds board files those images share.
`samples/web/` holds browser code built by its own tools.

Build a Zephyr sample with `west build -b <board> samples/<name>/zephyr`.
`west twister -T samples` finds every `sample.yaml`.
`scripts/check-native-interfaces.py` and `tests/build/test_sample_layout.py` check these rules.

## Test-only scenarios

Scenarios that only a test compiles, and the board test images, live under `tests/`: see [Test-only scenarios and board test images](../tests/README.md#test-only-scenarios-and-board-test-images).

## Run every runnable sample

```sh
# Zephyr: every runnable Zephyr application on native_sim
west twister -T samples -p native_sim/native/64 -t sample
# Linux Host: all Host programs (after scripts/bootstrap-host.sh)
ctest --preset host-debug -L sample
```

The `sample` tag selects the entries of the runnable applications. The board-only samples allow only the EVKB, so
`-p native_sim/native/64` skips them with or without the tag.

## Adding a runnable sample

Follow [Files inside a sample](#files-inside-a-sample). Give the `zephyr/` application a `sample.yaml` with the tag `sample`, `platform_allow` and `integration_platforms` for
`native_sim/native/64`, and a `harness: console` regular expression on a line that proves it ran. Give the `linux/`
program a CTest test with the label `sample`; [`scripts/run-host-sample.py`](../scripts/run-host-sample.py) feeds it
stdin and checks its output lines.
