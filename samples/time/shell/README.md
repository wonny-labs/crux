# Time shell

## Overview

Sets and reads the Crux clock (UTC) from shell commands: a Zephyr shell with the Crux Time commands (`time get`,
`time set <UTC>`, `time help`), and the same commands as a Linux Host program that reads them from stdin. The
[Time contract](../../../docs/time-contract.md) defines what the commands may report.

| Part | Folder | Runs on |
| --- | --- | --- |
| Zephyr application | [`zephyr/`](zephyr/CMakeLists.txt) (`CMakeLists.txt`, `prj.conf`, `src/`, `boards/`, `sample.yaml`) | `native_sim/native/64`; cross-built for `mimxrt1060_evk@B//qspi` |
| Linux Host program | [`linux/`](linux/main.c), built by the repository's root `CMakeLists.txt` | The Linux Host build |
| Command handler | [`common/`](common/crux_time_command.h) | Compiled by both parts and by the Time tests on Host and `native_sim` |

## Requirements

- Zephyr: the west workspace from `scripts/bootstrap-zephyr.sh` (`/workspace` in the Dev Container).
- Linux Host: the Host build from `scripts/bootstrap-host.sh` or `scripts/check-host.sh`.

## Building and running on `native_sim`

From the repository root (`/workspace/crux` in the Dev Container):

```sh
west build -p always -b native_sim/native/64 -d build/time samples/time/shell/zephyr -t run
```

It prints `CRUX_TIME_READY composition=zephyr`, and the shell then waits on a pseudo-terminal that the first output
line names, such as `/dev/pts/3`. Connect a terminal program to it from a second terminal, for example
`screen /dev/pts/3`, as the
[`native_sim` board guide](https://docs.zephyrproject.org/latest/boards/native/native_sim/doc/index.html) uses. The
Dev Container image does not install `screen`; add it with `sudo apt-get update && sudo apt-get install -y screen`.
Tab then completes commands and subcommands (`ti` to `time`, `time g` to `time get`), and the Up and Down keys recall
earlier commands. Stop the program with Ctrl+C in the first terminal. For simple scripted input, start the built
program with its UART on stdin and stdout instead. Tab and the arrow keys do not work there, because the terminal
passes each line to the shell only after Enter:

```sh
build/time/zephyr/zephyr.exe -uart_stdinout
```

`native_sim` keeps a simulated clock, so `time get` advances with simulated uptime after `time set`, not with the
Host's wall clock. This sample does not slow the simulation to real time, so the second `time get` can show a later
time than the example below. Twister runs this sample from [`zephyr/sample.yaml`](zephyr/sample.yaml) (id
`crux.sample.time.shell`) and stops it after the ready line:

```sh
west twister -T samples/time/shell -p native_sim/native/64
```

The EVKB build (`-b 'mimxrt1060_evk@B//qspi'`) is a cross-build in this repository's checks
(`scripts/test-zephyr-time.sh`). To put a sample on the board, see
[Part C of the Tutorial](../../../docs/tutorial.md#part-c-run-on-your-board).

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

The Host build produces `build/linux/debug/samples/time/shell/linux/crux-time-host`. Run it, type commands, and
end with Ctrl+D:

```sh
build/linux/debug/samples/time/shell/linux/crux-time-host
```

The Host program uses a controlled clock that does not advance on its own. `ctest --preset host-debug -L sample` runs
it once with a fixed command sequence and checks the output (CTest `Sample.TimeShellHost`);
`scripts/check-host-sample.sh` runs a longer sequence.
