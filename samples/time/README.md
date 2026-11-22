# Crux Time sample

A Zephyr shell with the Crux Time commands (`time get`, `time set <UTC>`, `time help`), and the same commands as a
Linux Host program that reads them from stdin. The [Time contract](../../docs/time-contract.md) defines what the
commands may report.

| Part | Folder | Runs on |
| --- | --- | --- |
| Zephyr application | this folder (`CMakeLists.txt`, `prj.conf`, `src/`, `boards/`, `sample.yaml`) | `native_sim/native/64`; cross-built for `mimxrt1060_evk@B//qspi` |
| Linux Host program | [`host/`](host/main.c), built by the repository's root `CMakeLists.txt` | The Linux Host build |

## Zephyr on `native_sim`

From the west workspace root (`/workspace` in the Dev Container), after `scripts/bootstrap-zephyr.sh`:

```sh
west build -p always -b native_sim/native/64 -d build/time crux-pilot/samples/time -t run
```

It prints `CRUX_TIME_READY composition=zephyr`, and the shell then waits on a pseudo-terminal that the first output
line names. Stop it with Ctrl+C. To type commands in the same terminal, start the built program with its UART on
stdin and stdout instead:

```sh
build/time/zephyr/zephyr.exe -uart_stdinout
```

```text
uart:~$ time get
ERR NOT_SET
uart:~$ time set 2026-10-16T14:30:00
OK
uart:~$ time get
2026-10-16T14:30:00 UTC
```

`native_sim` keeps a simulated clock, so `time get` advances with simulated uptime after `time set`, not with the
Host's wall clock. This sample does not slow the simulation to real time, so the second `time get` can show a later
time than the example. Twister runs this sample from [`sample.yaml`](sample.yaml) and stops it after the ready line:

```sh
west twister -T crux-pilot/samples/time -p native_sim/native/64
```

The EVKB build (`-b 'mimxrt1060_evk@B//qspi'`) is a cross-build in this repository's checks. Programming a board is
a separate, approved procedure: see the [Build and Integration Guide](../../docs/build.md).

## Linux Host

`scripts/bootstrap-host.sh` (or `scripts/check-host.sh`) builds `build/linux/debug/samples/time/host/crux-time-host`.
Run it, type commands, and end with Ctrl+D:

```sh
build/linux/debug/samples/time/host/crux-time-host
```

The Host program uses a controlled clock that does not advance on its own. `ctest --preset host-debug -L sample` runs
it once with a fixed command sequence and checks the output.
