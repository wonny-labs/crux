# Tutorial: your first build and sample

This tutorial takes you from a working Dev Container to running Crux samples, changing a build, and running a sample on
your board. It is one path: Part A runs on the Linux Host, Part B on Zephyr's `native_sim`, and Part C on a board. Parts
A and B need no board.
Parts A and B use only the standard Zephyr and CMake tools: `west build`, `west twister`, `cmake` and `ctest`. Each step says
what you should see. The [Build and Integration Guide](build.md) explains everything in more depth.

Part A runs on the Linux Host and gives a first result in minutes, before the long Zephyr download. Products target
Zephyr, so Part B is the main body of the tutorial. The same first example, `hello_crux`, runs in all three parts:
on the Host, on `native_sim` and on the board. Between them come one example per Crux idea: a networking client
(`networking/echo_client`, Host), a shell (`time/clock_shell`) and provider selection by configuration
(`file/write_read`). If a step fails for a reason that is not about Crux, [Troubleshooting](#troubleshooting) uses
Zephyr's own `hello_world` and `blinky` to check the Zephyr install and the board.

The Zephyr downloads at the start of Part B are the long part. No durations have been measured yet.

## Prerequisites and the Dev Container

Complete the prerequisites and the clone in [Getting started](getting-started.md), then open the repository folder in VS Code and choose **Dev Containers: Reopen in Container**.

Inside the container there are two folders you work from:

| Folder | What it is | Run from here |
| --- | --- | --- |
| `/workspace` | The west workspace: `zephyr/`, `modules/` and this repository side by side | `west build`, `west twister` |
| `/workspace/crux-pilot` | This repository | `scripts/...`, `cmake --preset`, `ctest --preset` |

## Part A. Linux Host

### 1. Bootstrap the Host build

Run the Host tests row of [Setup commands](getting-started.md#6-setup-commands) from `/workspace/crux-pilot`. It runs the Host build and tests.

The Host script ends with the CTest summary, `100% tests passed`.

### 2. Run Hello Crux on the Linux Host

`samples/hello_crux` is the smallest application that uses Crux. Its Host program is a separate CMake project that
consumes Crux the way an external application does, so it is built on its own. From `/workspace/crux-pilot`:

```sh
cmake -S samples/hello_crux/host -B build/samples/hello_crux_host -G Ninja -DCRUX_SOURCE_DIR="$PWD"
cmake --build build/samples/hello_crux_host
build/samples/hello_crux_host/hello-crux-host
```

It prints `Hello from Crux on host`, `Crux Time: unset` and `CRUX_HELLO_READY composition=host`. The clock is unset
because Crux never invents a time of day. [Its README](../samples/hello_crux/README.md) explains what the sample shows.

### 3. Run the networking sample on the Host

`samples/networking/echo_client` exchanges one TCP and one UDP echo with a peer. Its Host program,
`build/linux/debug/samples/networking/echo_client/host/crux-networking-host`, needs an echo peer on `127.0.0.1` ports
42420 and 42421, so run it through CTest, which starts a local peer for it. From `/workspace/crux-pilot`:

```sh
ctest --preset host-debug -R Sample.EchoClientHost --output-on-failure
```

You should see `100% tests passed`. The sample's Zephyr image is for a board with an isolated network and a peer; its
[README](../samples/networking/echo_client/README.md) describes it.

### 4. Run every Host sample with CTest

CTest runs each Host sample of the root build once and checks its output. From `/workspace/crux-pilot`:

```sh
ctest --preset host-debug -L sample
```

It runs `Sample.ClockShellHost`, the Time shell on the Host, and `Sample.EchoClientHost`. (`hello_crux` is its own CMake
project, so step 2 builds it, and CTest does not.) Without `-L sample`, the same command runs every Host test of the
repository, including the periodic Time scenario `TimePeriodic.HostScenario`.

### 5. Change a Host build

CMake options configure the build itself. The Linux Host build selects Crux components and samples with `CRUX_BUILD_*` options. From
`/workspace/crux-pilot`:

```sh
cmake -LH build/linux/debug | grep -B1 '^CRUX_'                       # list the options and their help
cmake --preset host-debug -DCRUX_BUILD_TIME_PERIODIC_SCENARIO=OFF
cmake --build --preset host-debug
ctest --preset host-debug -R TimePeriodic -N                           # the scenario test is gone
cmake --preset host-debug -DCRUX_BUILD_TIME_PERIODIC_SCENARIO=ON       # back to the default
```

The [capability and provider selection](build.md#capability-and-provider-selection) section lists the options that
matter for products.

## Part B. Zephyr

### 6. Bootstrap the Zephyr workspace

Run the Zephyr samples row of [Setup commands](getting-started.md#6-setup-commands) from `/workspace/crux-pilot`. It creates the west workspace and installs the Zephyr SDK. The west checkouts and the SDK are large downloads, and they are the longest part of this tutorial.

The script turns `/workspace` into a west
workspace whose manifest is this repository's [`west.yml`](../west.yml), so every `west build` in it finds the Crux
Zephyr module by itself.

### 7. Run Hello Crux

This is the Zephyr form of step 2. It proves that the Crux module, a Kconfig symbol, a public target and a public
header work together, and that the application keeps to the consumer boundary. From `/workspace`:

```sh
west build -p always -b native_sim/native/64 -d build/hello_crux crux-pilot/samples/hello_crux -t run
```

You should see, after the boot banner:

```text
Hello from Crux on zephyr
Crux Time: unset
CRUX_HELLO_READY composition=zephyr
```

Stop it with Ctrl+C. Three things made this build a Crux application, and none names a Crux source file: the west
workspace lists Crux as a Zephyr module, `CONFIG_CRUX_TIME=y` in the sample's `prj.conf` selects the component, and its
`CMakeLists.txt` links the public target `crux::time` and the source includes `<crux/time.h>`. The sample's
[README](../samples/hello_crux/README.md) goes through them.

### 8. Run the Time shell

The Time sample is a Zephyr shell with Crux Time commands:

```sh
west build -p always -b native_sim/native/64 -d build/time crux-pilot/samples/time/clock_shell -t run
```

It prints `CRUX_TIME_READY composition=zephyr` and then waits. Its shell is on a pseudo-terminal, as the first output
line says. To type commands in your own terminal, stop it with Ctrl+C and start the built program with its UART on
stdin and stdout:

```sh
build/time/zephyr/zephyr.exe -uart_stdinout
```

Type `time get` (`ERR NOT_SET`), then `time set 2026-10-16T14:30:00` (`OK`), then `time get` again. Stop with Ctrl+C.

### 9. Select a provider by configuration

`samples/file/write_read` writes a file through the Crux File API and reads it back. The application source does not
know where the file lives: the Kconfig fragment and the devicetree overlay of the build choose the File provider. The
default build uses LittleFS on the flash simulator:

```sh
west build -p always -b native_sim/native/64 -d build/write_read crux-pilot/samples/file/write_read -t run
```

It ends with `CRUX_FILE_WRITE_READ_OK provider=simulator`. The same source, built with another fragment and overlay,
uses FatFs on a RAM disk:

```sh
west build -p always -b native_sim/native/64 -d build/write_read_fatfs \
    crux-pilot/samples/file/write_read -t run -- \
    -DEXTRA_CONF_FILE=fatfs_ram_disk.conf -DEXTRA_DTC_OVERLAY_FILE=fatfs_ram_disk.overlay
```

and ends with `CRUX_FILE_WRITE_READ_OK provider=fatfs_ram_disk`. Both providers are experimental and exist for
software-only checks on `native_sim`; the sample's [README](../samples/file/write_read/README.md) says so. Step 12
explains the two options after `--`.

Two more samples are not part of this path. The `networking/echo_client` image is for the board only. Threads and
synchronization have no Crux sample: read Zephyr's own `zephyr/samples/basic/threads` and
`zephyr/samples/synchronization`. [Samples](../samples/README.md) lists every sample folder, which ones run on their
own, and which scripts use the others.

### 10. Run every Zephyr sample with Twister

Twister builds each runnable Zephyr sample, runs it, and checks its output against the regular expression in its
`sample.yaml`. From `/workspace`:

```sh
west twister -T crux-pilot/samples -p native_sim/native/64 -t sample
```

Twister runs every runnable Zephyr sample that [Samples](../samples/README.md#classification) lists, and its summary
line reports how many test configurations passed. Its output and logs are under `twister-out/`. The tag
`-t sample` leaves out the link-only board images under `samples/`; the [samples page](../samples/README.md#run-every-runnable-sample)
says why.

### 11. Change a Zephyr build

Every change in this step is a standard Zephyr or CMake mechanism. Options after `--` on a `west build` command line
go to CMake. They stay in the build directory's cache, so use `-p always` when you drop one again.

#### Kconfig

Kconfig options (`CONFIG_...`) select features and values. A build merges them from, in order:

| Source | Where | Use it for |
| --- | --- | --- |
| `prj.conf` | The application folder | The application's own settings |
| Board file | `boards/<board>.conf` in the application folder, for example `samples/time/clock_shell/boards/native_sim.conf` | Settings for one board |
| Extra files | `-DEXTRA_CONF_FILE=<file>[;<file>...]` | A variant without editing the application, for example a debug profile |
| One option | `-DCONFIG_<NAME>=<value>` | A quick experiment |

For example, turn off Zephyr's boot banner for one build:

```sh
west build -p always -b native_sim/native/64 -d build/time crux-pilot/samples/time/clock_shell -- -DCONFIG_BOOT_BANNER=n
grep CONFIG_BOOT_BANNER build/time/zephyr/.config
build/time/zephyr/zephyr.exe -uart_stdinout
```

The `grep` prints `# CONFIG_BOOT_BANNER is not set`, and the program starts without the `*** Booting Zephyr OS ***`
line. The same setting in a file has the same effect:

```sh
printf 'CONFIG_BOOT_BANNER=n\n' > no-banner.conf
west build -p always -b native_sim/native/64 -d build/time crux-pilot/samples/time/clock_shell -- -DEXTRA_CONF_FILE=$PWD/no-banner.conf
```

`build/<dir>/zephyr/.config` is the final, merged result: check it whenever an option seems to have no effect,
because Kconfig drops a value whose dependencies are not met and only warns. To browse and change options
interactively, run `west build -d build/time -t menuconfig` (or `-t guiconfig`). It saves into that `.config`, which
the next pristine build replaces, so copy a setting you want to keep into `prj.conf` or a `.conf` file.

#### Devicetree overlays

Devicetree describes the hardware: which devices exist and how they are wired. An overlay changes it for one build.
Zephyr picks up `app.overlay` or `boards/<board>.overlay` from the application folder by itself, and
`-DEXTRA_DTC_OVERLAY_FILE=<file>` adds one from anywhere. For example, build the Time sample with the simulated RTC
disabled:

```sh
west build -p always -b native_sim/native/64 -d build/time crux-pilot/samples/time/clock_shell \
  -- -DEXTRA_DTC_OVERLAY_FILE=$PWD/crux-pilot/tests/time/zephyr/boards/native_sim_no_rtc.overlay
grep -A3 'rtc: rtc' build/time/zephyr/zephyr.dts
```

`build/<dir>/zephyr/zephyr.dts` is the final Devicetree, with the file and line that set each property: it shows
`status = "disabled"` from the overlay.

#### CMake options

CMake options configure the build itself rather than the image's features. On a Zephyr build they go after `--`.
For example, `-DCRUX_REQUIRE_VERIFIED_ZEPHYR=ON` makes a build stop, instead of warning, when the workspace's Zephyr
is not the release Crux was verified on.

## Part C. Run on your board

No board? Parts A and B run every sample and test.

The board is a parameter: the same build takes the board's `-b` target, and each board has a guide with its switches,
probe, connections and recovery. Pick your board:

| Board | `-b` target | Probe | Board guide |
| --- | --- | --- | --- |
| NXP MIMXRT1060-EVKB, revision B | `mimxrt1060_evk@B//qspi` | SEGGER J-Link on J2; console on the DAPLink USB serial port | [MIMXRT1060-EVKB](boards/mimxrt1060_evkb.md) |

Which components have evidence on each board is recorded in [Component readiness](component-readiness.md). Set the
board up as its guide says before you start. Any operation on a board, such as connecting a probe, a reset or a
download, needs approval for your task.

The steps below use the one board route that has been used: the J-Link GDB Server on a Mac and the build in the Dev
Container. The Linux and WSL2 route is described on the board page once it has been verified. The commands are those
of the board guide's [Flash and debug](boards/mimxrt1060_evkb.md#flash-and-debug) section, which gives their options.

### 12. Check the J-Link connection

On the Mac, from the repository checkout (not the Dev Container), start the GDB Server and leave it running:

```sh
bash scripts/macos/start-jlink-gdbserver.command
```

Open the board's console, the DAPLink serial port, at 115200 baud, 8-N-1, in a serial terminal. The GDB Server should
report that it is connected to the target. If it does not, use the board guide's recovery section before you go on.
If the board then does nothing in step 14, [Troubleshooting](#troubleshooting) checks board and probe with Zephyr's
`blinky`.

### 13. Flash Hello Crux

The first Crux image on the board is the one from step 7. In the Dev Container, from `/workspace/crux-pilot`:

```sh
scripts/build-debug-target.sh 'mimxrt1060_evk@B//qspi' --app samples/hello_crux
```

The build directory is `build/zephyr/mimxrt1060_evk_B_qspi--samples_hello_crux`. **No board result is recorded for
this image.** CI only cross-builds it. The repository's **EVKB QSPI: Flash** profile builds and downloads the Time
sample only, so it does not download this image, and the board guide describes no download route for it; agree the route for your
task before you download it.

### 14. See the console line

Once the image is running, the console shows the Zephyr boot banner and then the three lines of step 7, ending with
`CRUX_HELLO_READY composition=zephyr`. The Time sample, `samples/time/clock_shell`, is the image that the **EVKB QSPI: Flash** profile
builds and downloads (`scripts/build-debug-target.sh 'mimxrt1060_evk@B//qspi'` is its build). It is the one image with
a recorded board result: a download, a reset and the console line `CRUX_TIME_READY composition=zephyr`, as the board
guide's
[Flash and debug](boards/mimxrt1060_evkb.md#flash-and-debug) section records.

When you are done, stop the debugger and stop the GDB Server with Ctrl-C.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `hello_crux` fails at configure or build on `native_sim` | Build Zephyr's own `hello_world`, from `/workspace`: `west build -p always -b native_sim/native/64 -d build/hello zephyr/samples/hello_world -t run`. You should see `Hello World! native_sim/native/64`. If this fails too, the Zephyr install is the problem (rerun the Zephyr bootstrap of step 6); if only `hello_crux` fails, the problem is in the Crux module or its configuration |
| The board does nothing after a download | Build Zephyr's `blinky` for the board, from `/workspace`: `west build -p always -b 'mimxrt1060_evk@B//qspi' -d build/blinky zephyr/samples/basic/blinky`, and download it the way Zephyr's page for the board describes. The user LED should blink. If it does, the board and probe work and the problem is in the image; if not, use the board guide's recovery section. This repository records no run of `blinky` on the board |

## Next steps

- [Samples](../samples/README.md): what each sample folder is for.
- [Boards](boards/README.md): every board page.
- [Choosing an API](choosing-an-api.md): where each kind of product code goes.
- [Test guide](../tests/README.md): every suite and the checks to run before a pull request.
- [Documentation map](README.md): every other page, by task.
