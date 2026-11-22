# Your first hour with Crux

This page takes a new team member from a fresh clone to running Crux samples and changing a build, with no board.
It uses only the standard Zephyr and CMake tools: `west build`, `west twister`, `cmake` and `ctest`. Each step says
what you should see. The [Build and Integration Guide](build.md) explains everything in more depth.

Plan for the downloads in step 2 to take most of the hour. After that, each build takes about a minute.

## 1. Open the Dev Container

Follow [Getting started](getting-started.md) for the clone, the folder layout (the repository folder must be named
`crux-pilot`, inside an otherwise empty parent folder), Windows with WSL2, proxies and disk space. Then open the
repository folder in VS Code and choose **Dev Containers: Reopen in Container**.

Inside the container there are two folders you work from:

| Folder | What it is | Run from here |
| --- | --- | --- |
| `/workspaces/crux` | The west workspace: `zephyr/`, `modules/` and this repository side by side | `west build`, `west twister` |
| `/workspaces/crux/crux-pilot` | This repository | `scripts/...`, `cmake --preset`, `ctest --preset` |

## 2. Bootstrap the workspace

From `/workspaces/crux/crux-pilot`:

```sh
scripts/bootstrap-host.sh                    # Linux Host build and tests, and the GoogleTest cache
scripts/bootstrap-zephyr.sh --install-sdk    # west workspace at the pinned Zephyr, and the Zephyr SDK
```

The first command ends with the CTest summary, `100% tests passed`. The second turns `/workspaces/crux` into a west
workspace whose manifest is this repository's [`west.yml`](../west.yml), so every `west build` in it finds the Crux
Zephyr module by itself.

## 3. Run Zephyr's own Hello World

From `/workspaces/crux`:

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

## 4. Run Crux samples on `native_sim`

The same command runs a Crux sample. The Time sample is a Zephyr shell with Crux Time commands:

```sh
west build -p always -b native_sim/native/64 -d build/time crux-pilot/samples/time -t run
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

## 5. Run Crux samples on the Linux Host

Step 2 also built three Linux Host programs. From `/workspaces/crux/crux-pilot`:

```sh
build/linux/debug/samples/time/host/crux-time-host
```

It prints `CRUX_TIME_READY composition=host-simulation` and reads Time commands from stdin; end with Ctrl+D. Its
clock is controlled and does not advance on its own. The other two are
`build/linux/debug/samples/controller/host/crux-controller-host`, the same 20-cycle controller scenario, and
`build/linux/debug/samples/networking/host/crux-networking-host`, which needs an echo peer on `127.0.0.1` ports 42420
and 42421 (CTest starts one for it, see the next step).

## 6. Run every sample with Twister and CTest

Twister builds each runnable Zephyr sample, runs it, and checks its output against the regular expression in its
`sample.yaml`. From `/workspaces/crux`:

```sh
west twister -T crux-pilot/samples -p native_sim/native/64 -t sample
```

It ends with `2 of 2 executed test configurations passed`. Its output and logs are under `twister-out/`. The tag
`-t sample` leaves out the link-only board images under `samples/`; the [samples page](../samples/README.md#run-every-runnable-sample)
says why.

CTest runs each Linux Host sample once and checks its output. From `/workspaces/crux/crux-pilot`:

```sh
ctest --preset host-debug -L sample
```

It runs `Sample.TimeHost`, `Sample.NetworkingHost` and `Controller.HostScenario`. Without `-L sample`, the same
command runs every Host test of the repository.

## 7. Change a build

Every change in this step is a standard Zephyr or CMake mechanism. Options after `--` on a `west build` command line
go to CMake. They stay in the build directory's cache, so use `-p always` when you drop one again.

### Kconfig

Kconfig options (`CONFIG_...`) select features and values. A build merges them from, in order:

| Source | Where | Use it for |
| --- | --- | --- |
| `prj.conf` | The application folder | The application's own settings |
| Board file | `boards/<board>.conf` in the application folder, for example `samples/time/boards/native_sim.conf` | Settings for one board |
| Extra files | `-DEXTRA_CONF_FILE=<file>[;<file>...]` | A variant without editing the application, for example a debug profile |
| One option | `-DCONFIG_<NAME>=<value>` | A quick experiment |

For example, turn off Zephyr's boot banner for one build:

```sh
west build -p always -b native_sim/native/64 -d build/time crux-pilot/samples/time -- -DCONFIG_BOOT_BANNER=n
grep CONFIG_BOOT_BANNER build/time/zephyr/.config
build/time/zephyr/zephyr.exe -uart_stdinout
```

The `grep` prints `# CONFIG_BOOT_BANNER is not set`, and the program starts without the `*** Booting Zephyr OS ***`
line. The same setting in a file has the same effect:

```sh
printf 'CONFIG_BOOT_BANNER=n\n' > no-banner.conf
west build -p always -b native_sim/native/64 -d build/time crux-pilot/samples/time -- -DEXTRA_CONF_FILE=$PWD/no-banner.conf
```

`build/<dir>/zephyr/.config` is the final, merged result: check it whenever an option seems to have no effect,
because Kconfig drops a value whose dependencies are not met and only warns. To browse and change options
interactively, run `west build -d build/time -t menuconfig` (or `-t guiconfig`). It saves into that `.config`, which
the next pristine build replaces, so copy a setting you want to keep into `prj.conf` or a `.conf` file.

### Devicetree overlays

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

### CMake options

CMake options configure the build itself rather than the image's features. On a Zephyr build they go after `--`.
For example, `-DCRUX_REQUIRE_VERIFIED_ZEPHYR=ON` makes a build stop, instead of warning, when the workspace's Zephyr
is not the release Crux was verified on.

The Linux Host build selects Crux components and samples with `CRUX_BUILD_*` options. From
`/workspaces/crux/crux-pilot`:

```sh
cmake -LH build/linux/debug | grep -B1 '^CRUX_'                       # list the options and their help
cmake --preset host-debug -DCRUX_BUILD_REFERENCE_CONTROLLER=OFF
cmake --build --preset host-debug
ctest --preset host-debug -L sample                                    # now two sample tests
cmake --preset host-debug -DCRUX_BUILD_REFERENCE_CONTROLLER=ON         # back to the default
```

The [capability and provider selection](build.md#capability-and-provider-selection) section lists the options that
matter for products.

## 8. Boards

Building for, programming and debugging a physical board is described in the
[Build and Integration Guide](build.md). This page does not cover it.

## Next steps

- [Samples](../samples/README.md): what each sample folder is for.
- [Choosing an API](choosing-an-api.md): where each kind of product code goes.
- [Test guide](../tests/README.md): every suite and the checks to run before a pull request.
- [Documentation map](README.md): every other page, by task.
