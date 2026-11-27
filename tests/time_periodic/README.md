# Periodic Time scenario (test)

A finite, product-neutral scenario that reads Time on a fixed 100 ms grid for 20 cycles and then prints a completion
line. It is a test, not a sample: it holds the Host program with ASan/UBSan coverage, the `native_sim` run (normal
and without an RTC) and the EVKB cross-build of the portable schedule and health logic. The 13 GoogleTest cases of
the portable core are in [`tests/controller`](../controller). For a first periodic task read Zephyr's `samples/basic/threads`; Crux's first
examples are in the [samples overview](../../samples/README.md).

| Folder | Content |
| --- | --- |
| `core/`, `include/` | Portable schedule advance and health/readiness logic. No OS headers. |
| `host/` | Linux Host composition; CTest `TimePeriodic.HostScenario` |
| `zephyr/` | Zephyr composition; Twister id `crux.time_periodic.scenario` on `native_sim` and the EVKB build |

The boot checks use their own fixture application, [`tests/boot_fixture/zephyr`](../boot_fixture/zephyr), which
compiles the same scenario. The EVKB device, network and integrated probe images are in
[`tests/board_images/integration_probe`](../board_images/integration_probe/README.md).

## The scenario

Cycles 0 and 1 observe unset Time. Cycle 2 explicitly sets `1792238400` UTC seconds and cycle 6 steps UTC back to
`1792234800`; these are scenario inputs, not a date or host synchronisation, and an unavailable result never shows a
numeric UTC. The composition selects the first future phase after work and skips elapsed releases without catch-up
bursts. The portable schedule tests cover deliberate overrun, invalid input and overflow rejection; the Time integration
tests cover failed initialisation and retry, unset, read failure and recovery. No latency or jitter limit is claimed, and
the 10-second runner and join limits are liveness bounds. Zephyr runs one pre-emptive priority 5 worker with a static
4096-byte stack and no kernel heap; Linux runs the same behaviour in its main thread with `CLOCK_MONOTONIC` absolute
sleeps. Both `native_sim` configurations must complete all 20 cycles with system realtime, and the finite host process
must exit successfully. The [execution investigation](../../docs/execution-profile.md) records the decision.

### Build and run without hardware

`scripts/check-host.sh` builds and tests the scenario with the other tests, and `CRUX_HOST_PRESET=host-sanitize scripts/check-host.sh`
adds ASan/UBSan. The Host program is `build/linux/debug/samples/controller/host/crux-time-periodic-host`. The scenario needs no RTC and writes none. `CRUX_BUILD_TIME_PERIODIC_SCENARIO` controls the host executable; its default follows
`CRUX_BUILD_HOST_SAMPLE`. CTest runs it as `TimePeriodic.HostScenario` through
[`scripts/check-time-periodic.py`](../../scripts/check-time-periodic.py).

`scripts/test-time-periodic.sh` builds and runs the normal and missing-RTC `native_sim` compositions and cross-builds
`mimxrt1060_evk@B//qspi`, with no hardware operation. Scenario logs are under
`build/zephyr/controller-{normal,missing-rtc}/scenario.log` and the EVKB build under `build/zephyr/controller-evkb/`.

### Run on `native_sim`

From the repository root (`/workspace/crux` in the Dev Container), after `scripts/bootstrap-zephyr.sh`:

```sh
west build -p always -b native_sim/native/64 -d build/time_periodic tests/time_periodic/zephyr -t run
```

The scenario prints one `cycle=` line per cycle and ends with `CONTROLLER_COMPLETE cycles=20`. The simulated kernel
keeps running after that line; stop it with Ctrl+C. Twister runs the same scenario from
[`zephyr/testcase.yaml`](zephyr/testcase.yaml) and stops at the completion line:

```sh
west twister -T tests/time_periodic/zephyr -p native_sim/native/64
```

The EVKB build (`-b 'mimxrt1060_evk@B//qspi'`) is a cross-build in this repository's checks.

Physical results for the basic scenario are in the [physical verification record](../../docs/m2-physical-verification.md); integrated device, network and watchdog results are in the [controller validation record](../../docs/m3-validation.md).
