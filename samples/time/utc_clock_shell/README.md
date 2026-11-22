# UTC clock shell

## Overview

Reads and sets the Crux UTC clock from shell commands: a Zephyr shell with the Crux Time commands (`time get`,
`time set <UTC>`, `time help`), and the same commands as a Linux Host program that reads them from stdin. The
[Time contract](../../../docs/time-contract.md) defines what the commands may report. This sample was at
`samples/time/` before the samples layout change.

| Part | Folder | Runs on |
| --- | --- | --- |
| Zephyr application | this folder (`CMakeLists.txt`, `prj.conf`, `src/`, `boards/`, `sample.yaml`) | `native_sim/native/64`; cross-built for `mimxrt1060_evk@B//qspi` |
| Linux Host program | [`host/`](host/main.c), built by the repository's root `CMakeLists.txt` | The Linux Host build |

## Requirements

- Zephyr: the west workspace from `scripts/bootstrap-zephyr.sh` (`/workspace` in the Dev Container).
- Linux Host: the Host build from `scripts/bootstrap-host.sh` or `scripts/check-host.sh`.

## Building and running on `native_sim`

From the west workspace root:

```sh
west build -p always -b native_sim/native/64 -d build/time crux-pilot/samples/time/utc_clock_shell -t run
```

It prints `CRUX_TIME_READY composition=zephyr`, and the shell then waits on a pseudo-terminal that the first output
line names. Stop it with Ctrl+C. To type commands in the same terminal, start the built program with its UART on
stdin and stdout instead:

```sh
build/time/zephyr/zephyr.exe -uart_stdinout
```

`native_sim` keeps a simulated clock, so `time get` advances with simulated uptime after `time set`, not with the
Host's wall clock. This sample does not slow the simulation to real time, so the second `time get` can show a later
time than the example below. Twister runs this sample from [`sample.yaml`](sample.yaml) (id
`crux.sample.time.utc_clock_shell`) and stops it after the ready line:

```sh
west twister -T crux-pilot/samples/time/utc_clock_shell -p native_sim/native/64
```

The EVKB build (`-b 'mimxrt1060_evk@B//qspi'`) is a cross-build in this repository's checks
(`scripts/test-zephyr-time.sh`). Programming a board is a separate, approved procedure: see the
[Build and Integration Guide](../../../docs/build.md).

## Sample output

```text
uart:~$ time get
ERR NOT_SET
uart:~$ time set 2026-10-16T14:30:00
OK
uart:~$ time get
2026-10-16T14:30:00 UTC
```

## Linux Host

The Host build produces `build/linux/debug/samples/time/utc_clock_shell/host/crux-time-host`. Run it, type commands, and
end with Ctrl+D:

```sh
build/linux/debug/samples/time/utc_clock_shell/host/crux-time-host
```

The Host program uses a controlled clock that does not advance on its own. `ctest --preset host-debug -L sample` runs
it once with a fixed command sequence and checks the output (CTest `Sample.UtcClockShellHost`);
`scripts/check-host-sample.sh` runs a longer sequence.
