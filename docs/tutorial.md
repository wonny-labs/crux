# Tutorial: your first build and sample

This tutorial takes you from a working Dev Container to running Crux samples, changing a build, and running a sample on
your board. It is one path: Part A runs on the Linux Host, Part B on Zephyr's `native_sim`, and Part C on a board. Parts
A and B need no board.
Parts A and B use only the standard Zephyr and CMake tools: `west build`, `west twister`, `cmake` and `ctest`. Each step says
what you should see. The [Build and Integration Guide](build.md) explains everything in more depth.

Part A runs on the Linux Host and gives a first result in minutes, before the long Zephyr download. Products target
Zephyr, so Part B is the main body of the tutorial.

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

### 2. Run Crux samples on the Linux Host

Step 1 built three Linux Host programs. From `/workspace/crux-pilot`:

```sh
build/linux/debug/samples/time/clock_shell/host/crux-time-host
```

It prints `CRUX_TIME_READY composition=host-simulation` and reads Time commands from stdin; end with Ctrl+D. Its
clock is controlled and does not advance on its own. The other two are
`build/linux/debug/samples/controller/host/crux-controller-host`, the same 20-cycle controller scenario, and
`build/linux/debug/samples/networking/echo_client/host/crux-networking-host`, which needs an echo peer on `127.0.0.1` ports 42420
and 42421 (CTest starts one for it, see the next step).

### 3. Run every Host sample with CTest

CTest runs each Linux Host sample once and checks its output. From `/workspace/crux-pilot`:

```sh
ctest --preset host-debug -L sample
```

It runs `Sample.ClockShellHost`, `Sample.EchoClientHost` and `Controller.HostScenario`. Without `-L sample`, the same
command runs every Host test of the repository.

### 4. Change a Host build

CMake options configure the build itself. The Linux Host build selects Crux components and samples with `CRUX_BUILD_*` options. From
`/workspace/crux-pilot`:

```sh
cmake -LH build/linux/debug | grep -B1 '^CRUX_'                       # list the options and their help
cmake --preset host-debug -DCRUX_BUILD_REFERENCE_CONTROLLER=OFF
cmake --build --preset host-debug
ctest --preset host-debug -L sample                                    # now two sample tests
cmake --preset host-debug -DCRUX_BUILD_REFERENCE_CONTROLLER=ON         # back to the default
```

The [capability and provider selection](build.md#capability-and-provider-selection) section lists the options that
matter for products.

## Part B. Zephyr

### 5. Bootstrap the Zephyr workspace

Run the Zephyr samples row of [Setup commands](getting-started.md#6-setup-commands) from `/workspace/crux-pilot`. It creates the west workspace and installs the Zephyr SDK. The west checkouts and the SDK are large downloads, and they are the longest part of this tutorial.

The script turns `/workspace` into a west
workspace whose manifest is this repository's [`west.yml`](../west.yml), so every `west build` in it finds the Crux
Zephyr module by itself.

### 6. Run Zephyr's own Hello World

From `/workspace`:

```sh
west build -p always -b native_sim/native/64 -d build/hello zephyr/samples/hello_world -t run
```

You should see:

```text
*** Booting Zephyr OS build v4.4.2 ***
Hello World! native_sim/native/64
```

`native_sim/native/64` builds Zephyr as a Linux program, so `-t run` runs it on your machine. The simulated kernel
keeps running after `main()` returns: stop it with Ctrl+C. `-p always` starts from a clean build directory, and
`-d` names it, so that several builds can sit side by side under `build/`.

### 7. Run Crux samples on `native_sim`

The same command runs a Crux sample. The Time sample is a Zephyr shell with Crux Time commands:

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

The reference controller runs a fixed 20-cycle scenario and ends with `CONTROLLER_COMPLETE cycles=20`:

```sh
west build -p always -b native_sim/native/64 -d build/controller crux-pilot/samples/controller/zephyr -t run
```

[Samples](../samples/README.md) lists every sample folder, which ones run on their own, and which scripts use the
others.

### 8. Run every Zephyr sample with Twister

Twister builds each runnable Zephyr sample, runs it, and checks its output against the regular expression in its
`sample.yaml`. From `/workspace`:

```sh
west twister -T crux-pilot/samples -p native_sim/native/64 -t sample
```

Twister runs every runnable Zephyr sample that [Samples](../samples/README.md#classification) lists, and its summary
line reports how many test configurations passed. Its output and logs are under `twister-out/`. The tag
`-t sample` leaves out the link-only board images under `samples/`; the [samples page](../samples/README.md#run-every-runnable-sample)
says why.

### 9. Change a Zephyr build

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
`-DEXTRA_DTC_OVERLAY_FILE=<file>` adds one from anywhere. For example, run the controller with the simulated RTC
disabled:

```sh
west build -p always -b native_sim/native/64 -d build/controller crux-pilot/samples/controller/zephyr -t run \
  -- -DEXTRA_DTC_OVERLAY_FILE=$PWD/crux-pilot/tests/time/zephyr/boards/native_sim_no_rtc.overlay
grep -A3 'rtc: rtc' build/controller/zephyr/zephyr.dts
```

The scenario still ends with `CONTROLLER_COMPLETE cycles=20`, because the controller uses system realtime, not the
RTC. `build/<dir>/zephyr/zephyr.dts` is the final Devicetree, with the file and line that set each property: it shows
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

### 10. Build a sample for your board

The board route builds and flashes the Time sample of step 7. `samples/hello_crux` is built and run on `native_sim`
only. In the Dev Container, from `/workspace/crux-pilot`, pass the board's `-b` target:

```sh
scripts/build-debug-target.sh 'mimxrt1060_evk@B//qspi'
```

The script prints the build directory, `build/zephyr/mimxrt1060_evk_B_qspi`, before it builds and the ELF path when it
finishes.

### 11. Flash it

On the Mac, from the repository checkout (not the Dev Container), start the GDB Server and leave it running:

```sh
bash scripts/macos/start-jlink-gdbserver.command
```

Open the board's console, the DAPLink serial port, at 115200 baud, 8-N-1, in a serial terminal. Then, in VS Code in
the Dev Container, start the debug configuration **EVKB QSPI: Flash**. It runs the build of step 10, resets the board
and downloads the image. The debugger then stops at the reset entry (`reset.S`); press Continue (F5) to start the
image.

### 12. See it run

The console shows the Zephyr boot banner, then:

```text
CRUX_TIME_READY composition=zephyr
```

This line is recorded on the board after a download and a reset; the board guide's
[Flash and debug](boards/mimxrt1060_evkb.md#flash-and-debug) section says which records back each step.

When you are done, stop the debugger and stop the GDB Server with Ctrl-C.

## Next steps

- [Samples](../samples/README.md): what each sample folder is for.
- [Boards](boards/README.md): every board page.
- [Choosing an API](choosing-an-api.md): where each kind of product code goes.
- [Test guide](../tests/README.md): every suite and the checks to run before a pull request.
- [Documentation map](README.md): every other page, by task.
