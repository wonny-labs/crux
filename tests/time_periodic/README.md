# Periodic Time scenario (test)

A finite, product-neutral scenario that reads Time on a fixed 100 ms grid for 20 cycles and then prints a completion
line. It is a test, not a sample: it holds the Host program with ASan/UBSan coverage, the `native_sim` run (normal
and without an RTC) and the EVKB cross-build of the portable schedule and health logic. The 13 GoogleTest cases of
the portable core are in [`tests/controller`](../controller). It used to sit in `samples/controller`. For a first periodic task read Zephyr's `samples/basic/threads`; Crux's first
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

Conditions defined before the first controller run: 20 observations on a 100 ms monotonic
phase grid, normal unloaded composition, one execution owner. Cycles 0–1 observe unset
Time. Cycle 2 explicitly sets `1792238400` UTC seconds and cycle 6 explicitly steps UTC
back to `1792234800`. These are deterministic scenario inputs, not an implicit date or
synchronisation to the host. Unavailable/error results never display a numeric UTC.
The Host Time store remains deterministic; Zephyr system realtime progresses with
uptime after explicit setting. RTC is not required or written by this scenario.

The composition selects the first future phase after work, skipping elapsed releases
rather than generating catch-up bursts. The portable schedule tests include deliberate
overrun, invalid input and overflow rejection; Time integration tests include failed
initialisation/retry, unset, read failure and recovery. No latency/jitter upper limit is
claimed. The 10-second runner and native join limits are test liveness bounds, not
real-time guarantees. The [execution investigation](../../docs/execution-profile.md)
records the independent decision and native/POSIX limitations.

Zephyr uses one pre-emptive priority 5 worker with a static 4096-byte stack and no configured
kernel heap. Linux invokes the same portable behaviour in its main thread with
`CLOCK_MONOTONIC` absolute sleeps. Clock/sleep errors stop the host scenario; Time init/set
failure stops either composition. Both normal and RTC-absent `native_sim`
configurations must complete all 20 cycles with system realtime. The simulation runner terminates the idle kernel after the
final success/failure marker; it does not claim a Zephyr kernel shutdown API. The finite
host process must exit successfully, allowing sanitizer shutdown diagnostics to fail it.

### Build and run without hardware

In the documented Linux environment, `scripts/check-host.sh` builds and tests the scenario
alongside the other tests. Run `build/linux/debug/tests/time_periodic/host/crux-time-periodic-host`
for its output. `CRUX_HOST_PRESET=host-sanitize scripts/check-host.sh` exercises the same
scenario with ASan/UBSan. `CRUX_BUILD_TIME_PERIODIC_SCENARIO` controls the host executable (the old name
`CRUX_BUILD_REFERENCE_CONTROLLER` still works as an alias); its default follows
`CRUX_BUILD_HOST_SAMPLE`, preserving the library-only setup. CTest runs it as `TimePeriodic.HostScenario`
through [`scripts/check-time-periodic.py`](../../scripts/check-time-periodic.py).

`scripts/test-time-periodic.sh` (alias `scripts/test-time-periodic.sh` until the CI workflows switch) builds/runs normal and missing-RTC `native_sim` compositions
and cross-builds `mimxrt1060_evk@B//qspi`. It performs no hardware operations. Scenario logs
are under `build/zephyr/controller-{normal,missing-rtc}/scenario.log`; the EVKB build is
under `build/zephyr/controller-evkb/`. Existing host/Zephyr workflows run these paths and
retain reports/configuration/artefacts for 14 days.

### Run on `native_sim`

From the west workspace root (`/workspace` in the Dev Container), after `scripts/bootstrap-zephyr.sh`:

```sh
west build -p always -b native_sim/native/64 -d build/time_periodic crux-pilot/tests/time_periodic/zephyr -t run
```

The scenario prints one `cycle=` line per cycle and ends with `CONTROLLER_COMPLETE cycles=20`. The simulated kernel
keeps running after that line; stop it with Ctrl+C. Twister runs the same scenario from
[`zephyr/testcase.yaml`](zephyr/testcase.yaml) and stops at the completion line:

```sh
west twister -T crux-pilot/tests/time_periodic/zephyr -p native_sim/native/64
```

The EVKB build (`-b 'mimxrt1060_evk@B//qspi'`) is a cross-build in this repository's checks.

### Physical verification — bounded evidence

These measurements refer to the recorded earlier RTC-backed implementation.
They do not qualify the redesigned system realtime or optional RTC adapter.

[Authorised physical verification](../../docs/m2-physical-verification.md) ran the identified
controller three times on EVKB B/QSPI: 20 cycles each, expected unset/valid Time and backward
UTC step, independent monotonic phase, joined completion. Observed intervals were 100 ms at
uptime resolution, with zero recorded millisecond lateness and no skipped phases in this
normal unloaded scenario. Native execution probes separately exercise deliberate overrun,
lifecycle, synchronisation, timeouts and bounded messages on the target.

The requested usable worker stack is 4096 bytes; this ARM configuration allocates 4160
including a 64-byte MPU guard. Physical controller high-water accounting observed 408 used /
3688 untouched bytes, exceeding the predeclared 1024-byte short-run headroom objective.
Simulator accounting is not used as a Cortex-M measurement. Configured heap zero and static
Flash/RAM allocation are distinct from measured worker use or system worst-case sufficiency.

The evidence retains the first rejected capture, observer correction and programmer
post-disconnect diagnostic. The earlier sanitizer exit-timeout cause is still unresolved.
Physical POSIX, long-duration/concurrent-load behaviour and worst-case timing/resource
qualification are not established. The scoped M2 result was accepted and merged through
[PR #9](https://github.com/wonny-labs/crux-pilot/pull/9) as commit
[`540ea7f`](https://github.com/wonny-labs/crux-pilot/commit/540ea7f934987989e429ae3767352b153fb2e747),
and M2 issues [#6](https://github.com/wonny-labs/crux-pilot/issues/6) and
[#7](https://github.com/wonny-labs/crux-pilot/issues/7) are closed. These results apply
only to the basic periodic scenario. Integrated device, network and watchdog
verification is documented separately in the [controller validation record](../../docs/m3-validation.md).
