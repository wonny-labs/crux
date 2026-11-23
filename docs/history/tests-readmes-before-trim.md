# Test READMEs before the verbosity trim

Status: historical. Passages removed from READMEs under `tests/` in the November 2026 verbosity trim, moved word for word from revision 57f9142: authorship notes, test-run narratives, evidence results and local log names, and design commentary that the current READMEs no longer carry. The current READMEs are under [`tests/`](../../tests/). Measured results live in the records they cite.

## `tests/execution_runtime/README.md`

## Initial RED evidence

Before the public header was installed, a Linux-container C17 syntax probe of
`src/runtime_fixture.c` failed with:

```text
runtime_fixture.c:4:10: fatal error: crux/execution.h: No such file or directory
```

This establishes the missing public capability dependency, not behavioral failure
coverage. After the public header and Host target arrived, the independent Release
configuration succeeded and the fixture compiled warning-clean with C17, `-O3` and
`-DNDEBUG`. Linkage then failed at the expected unimplemented `crux_mutex_*` and
`crux_semaphore_*` symbols. The consumer compile command inherited only the public
execution/base include roots (plus its own fixture header directory). Full linkage
and runtime results must be recorded separately once synchronization providers are
available. No stub API was substituted.

## Host qualification result

After synchronization implementation became available, the independently configured
Release consumer rebuilt and linked successfully. `Execution.RuntimeConsumer` passed
under CTest (one test, zero failures), and a separate direct execution under a
60-second external deadline reported:

```text
runtime fixture: PASS (12 sessions, 4 bounded reservation cycles)
```

The Release configuration retains `-DNDEBUG`; fixture checks remain active. Logs
are retained locally under `build/evidence/m5-investigation/runtime-host-release-*`.
This records Linux Host behavior only; Zephyr and hardware evidence are separate.

## Independent Zephyr qualification result

The independently configured `native_sim/native/64` Twister scenario executed its
one ztest successfully: one configuration passed, one case passed, zero failures,
errors or warnings. The callable fixture ran the same twelve sessions and four
reservation cycles used on Host. The original run output is retained under
`build/evidence/m5-investigation/runtime-zephyr-independent-initial.log`; the
latest strict C17 rerun is in `runtime-zephyr-independent.log`. The portable
fixture compile command is retained in `runtime-zephyr-compile-command.json` in
the same evidence directory. It includes only its own fixture and public
execution/base header directories, with no native includes or requirements.

This is simulated Zephyr execution, not EVKB hardware evidence.

## `tests/execution_runtime/README.md`

Each of twelve sessions creates its own mutex and three bounded signal channels.
A worker first waits behind a gate, allowing its owner to check poll and finite
join timeout while retaining the task. The owner holds the shared-state mutex
while a handshake makes the worker check poll contention and finite lock expiry.
After another handshake, the worker changes the protected value and signals
progress. The owner joins before inspecting worker results and destroying objects.
Full/empty channels, token preservation and finite empty waits are also checked.
The timeout adapter distinguishes retry, deadline, capacity and other failure.

Four reservation cycles create gated tasks until capacity is rejected, then release
and join all of them. The fixture bounds its reservation array at eight entries and
expects the qualification profile's four thread slots. A composition with eight or
more slots requires an intentionally larger fixture bound. Subsequent sessions and
cycles verify reclamation, including after an unsuccessful create. Worker stack
requests are zero/default for reservations and 2048 bytes for session tasks; the
three priority classes are all exercised.

Checks print source lines and actual status values and remain active with NDEBUG.
On an error, cleanup releases the owner lock, permits cooperative progress and
attempts bounded joins. Objects still reachable by an unjoined worker are retained;
static argument/session storage preserves their lifetime. A failed call terminates
the qualification run: do not call the fixture again after failure. The fixture has
one caller and is not reentrant. This deliberately provides no cancellation policy.

The handshake determines unavailability; there is no public clock or native sleep.
These cases check timeout outcomes, not measured elapsed time or realtime latency.
The outer test deadline is only a liveness guard.

## `tests/execution_runtime/README.md`

This original C17 fixture models a small runtime task/session adapter. It is not
production runtime integration or evidence of compatibility with any proprietary
runtime. Its author used the approved execution contract, public declaration shapes
and public build integration instructions; provider source, private headers and
portable conformance tests were not consulted.

## `tests/native/logger_phase/README.md`

First, a semaphore holds one actual backend invocation for at most 100 ms. The
main thread observes one buffered message while processing is in flight, then
zero after release/completion. Setup and teardown drain loops are bounded at two
seconds; they never select an acceptance sample.

The finite workload has main/worker/network/logger priorities 0/5/6/14. Worker
reports recur every 1000 ms; the independent network idle reports recur every
1001 ms with a 1 ms initial offset. Main takes four fixed samples, with offsets
0/1/2/4 ms modelling the previously observed relative-loop drift. The corrected
case adds the production source's fixed 50 ms initial offset; the control adds
zero. Each sample enqueues the real observer/stack/logger formats afterwards.
The last two reports add twelve explicitly synthetic analyser lines, exercising
recurring post-report volume. These synthetic resource/health payloads are not
physical controller or watchdog evidence. Native logger identity/count/stack
observations themselves come from the kernel, but Cortex stack criteria do not
apply to this native mechanism fixture.

The verifier checks every expected production-format record and per-owner
sequence, raw grammar, native configuration, held-message mechanism, fixed
sample times and original first-three initial queue policy. The corrected case
must pass; the unshifted case must exhibit an in-flight initial count and fail
that same policy. It retains the actual pre-report byte budgets and observed
sample stamps. Mutations of the actual capture must reject nonzero first samples
even with later zeros, missing/duplicate/reordered/partial/ANSI records, late
samples and loss markers. No polling for queue zero or favourable resampling is
used in the qualifying sample path.

A one-time offset is not a phase lock. Relative loop/report cost and independent
network cadence can drift. This bounded model supports a physical hypothesis;
it proves neither Cortex UART latency nor continuous zero queue, worst-case
execution time, stack sufficiency or platform scheduling guarantees. Every new
physical capture must retain all logger observations and the unchanged initial
idle criteria. Armed reports may enqueue a watchdog-feed record before sampling;
zero queue is required at the initial idle checkpoint only.

## `tests/native/logger_phase/README.md`

The existing `scripts/test-m3.sh` runs

## `tests/native/integrated_output/README.md`

All functional, stack and fault/boot payload values except the logger resource
query are synthetic. This fixture does not access Time, GPIO, sockets or watchdog
hardware, and its boot payload does not represent a physical reset. Native logger
stack observations are checked against their native allocation, without applying
Cortex-M high-water claims to the host. This is output-path and bounded workload
stream evidence; the original integrated target oracles and physical runs remain
required. It does not establish WCET, physical service rate or M5 qualification.

## `tests/board_images/integration_probe/README.md`

Outputs are
under `build/zephyr/twister-m3`, `m3-probe-evkb`, `m3-normal-evkb` and
`m3-network-evkb`; frozen inputs
are retained at `build/evidence/m3-inputs.json`. This command performs no hardware
operation. Host checks

## `tests/board_images/integration_probe/README.md`

`M3_WORK` reports input read status and an unset/valid Time status. The standalone
health probe retains its `M3_PENDING` diagnostic and is not the qualified integrated
composition. The accepted physical results combine actual SW5, Ethernet and integrated-
controller evidence. See [the validation record](../../../docs/m3-validation.md)
for identified firmware, tests, previous failures and support limits.

## `tests/board_images/integration_probe/README.md`

`M3_NET_STATE` distinguishes carrier, configured address and service success.
Restored carrier alone cannot restore service readiness: a complete successful
explicit round is required. `M3_NET_RESOURCE` reports application ownership and
native context/pkt/buffer availability. These observations do not establish
leak-free operation beyond the tested conditions. Qualified network and integrated
controller results are recorded in [the validation record](../../../docs/m3-validation.md).

## `tests/board_images/integration_probe/README.md`

The tested integrated scenario combines actual SW5 GPIO observations, serialised
Time access, bounded IPv4 TCP/UDP exchanges, UART diagnostics, service-readiness
observations and health supervision of the critical Time/GPIO and network owners.
The network window, fault injection and watchdog arming are deliberate development
test operations, not automatic startup behaviour. The normal configuration disables
test Shell commands and leaves watchdog arming and network traffic off at boot.

`scripts/test-controller-integration.sh` runs the applicable Twister/native
simulation and build-only
checks, including the integrated EVKB probe and normal profiles. This script does
not flash, reset or communicate with hardware. It produces images under
`build/zephyr/m3-integrated-{probe,normal}-evkb/`. Physical operation requires a
separately authorised procedure, verified firmware/configuration and the isolated
network fixture. See [M3 validation and final acceptance](../../../docs/m3-validation.md)
for the tested composition, required settings, results and restrictions.

The target evidence covers the identified RT1062 EVKB revision B/QSPI, its SW5
path and isolated Ethernet peer. It does not qualify other GPIO/I2C/SPI/EEPROM
paths, production networking, worst-case resource/timing behaviour or
long-duration concurrent-load scenarios. The Linux host continues to exercise the portable
scenario and shared health logic, not the EVKB-specific device/network composition.

The qualified integrated build explicitly selects the
[opt-in native MDIO correction](../../../patches/zephyr/README.md). Its pinned-source
and RT1062 composition limits remain applicable; the ordinary uncorrected network
probe build is not qualified by the corrected profile's physical results.

## `tests/time_periodic/README.md`

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

## `tests/time_periodic/README.md`

### Build and run without hardware

In the documented Linux environment, `scripts/check-host.sh` builds and tests the scenario
alongside the other tests. Run `build/linux/debug/samples/controller/host/crux-time-periodic-host` (the build folder keeps its historical name until the CI workflow that uploads its log is switched)
for its output. `CRUX_HOST_PRESET=host-sanitize scripts/check-host.sh` exercises the same
scenario with ASan/UBSan. `CRUX_BUILD_TIME_PERIODIC_SCENARIO` controls the host executable (the old name
`CRUX_BUILD_REFERENCE_CONTROLLER` still works as an alias); its default follows
`CRUX_BUILD_HOST_SAMPLE`, preserving the library-only setup. CTest runs it as `TimePeriodic.HostScenario`
through [`scripts/check-time-periodic.py`](../../scripts/check-time-periodic.py).

`scripts/test-time-periodic.sh` (alias `scripts/test-controller.sh` until the CI workflows switch) builds/runs normal and missing-RTC `native_sim` compositions
and cross-builds `mimxrt1060_evk@B//qspi`. It performs no hardware operations. Scenario logs
are under `build/zephyr/controller-{normal,missing-rtc}/scenario.log`; the EVKB build is
under `build/zephyr/controller-evkb/`. Existing host/Zephyr workflows run these paths and
retain reports/configuration/artefacts for 14 days.

## `tests/time_periodic/README.md`

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

## `tests/consumer_system/README.md`

Status: **Experimental** (the symbol it uses is Experimental, ADR-0001 Decision 4). A simulated watchdog is **not
hardware evidence**: a pass says that a product calls System in the right order and handles the answers in simulated
kernel time, and says nothing about a board.

## `tests/consumer_system/README.md`

In the Host test, each variant is also run with only the check function it relies on (`header_violations`,
`link_violations`, `wrap_violations` or `conf_violations`) replaced by one that finds nothing, and the variant is then
accepted. So each refusal is that function's. The include variant needs a build, so it has no such control on the
Host; its function is tested on a hand-made compile command, and CI runs the variant. Non-vacuity of the whole
fixture also rests on the clean-fixture test (the fixture passes every check) and on the message that each variant
must produce.

## `tests/web/project_sample/project/README.md`

The small example project of [Issue #220](https://github.com/wonny-labs/crux-pilot/issues/220). A product

## `tests/web/project_sample/project/README.md`

## Evidence

| State | Here |
| --- | --- |
| Mock | Not applicable: the mock serves the management API only |
| Host | `Web.project_sample`, on the real web core and the fake transport: the folder packaged by the real packager under the strict setting, the route behind a session lookup, and no fallback. `tests/build/test_project_sample.py` checks that the sources include no native header and the page has no inline content. |
| `native_sim` | Not run: the image check of the services image allows only the components' routes, so this route would need its own image |
| Physical | Not run |

