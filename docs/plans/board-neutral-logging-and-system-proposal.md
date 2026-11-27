# Board-neutral Logging and System for the management services

Status: **Proposal, not adopted.** Nothing here changes code, a contract, a check or an image. The owner
decides D1 to D10 below; until then the bindings stay as they are.
Baseline: main `2c4a36c2`. Line numbers below are from that revision.
Direction: [ADR-0002](../decisions/0002-platform-direction-zephyr-execution-crux-services.md) adopts
Zephyr for execution and Crux for services (option O4), and
[ADR-0003](../decisions/0003-p9-result-services-keep-narrow-thread-sync.md) keeps the services narrow.
Reading that as "the product chooses log backends and reset and watchdog hardware through Zephyr, Crux
keeps the service policy" is this proposal's interpretation; neither ADR names those pieces.

## 1. Problem

Three services that a product on any Zephyr board would want inherit one board's constraints:

- **Access** (and with it every management service) needs Crux Logging, and Crux Logging on Zephyr
  builds only with one deferred 115200 8N1 UART text log on an RT1062 LPUART or the `native_sim` UART
  emulator.
- **Management Status** and **Reboot** need Crux System, and Crux System on Zephyr builds only on
  `native_sim` or on an RT1062 whose `crux-watchdog0` alias is WDOG1 at `0x400b8000`.

Neither tie protects accepted physical evidence: both components are at **E3** (an EVKB build that
compiles and links, nothing runs; also E1 and E2), with physical acceptance still open
([readiness `logging` and `system` rows](../component-readiness.md), lines 17 and 56-57). The ties pin a
reviewed profile, not a qualified one.

**Other ties that remain after this proposal.** Status and Reboot `depend on CRUX_ACCESS`
(`zephyr/Kconfig:611`, `:697`), and Access also refuses an image without the Mbed PSA profile
(`zephyr/CMakeLists.txt:184-186`) and without a Crux File provider (`:193-196`). Off the RT1062 and
`native_sim` the only File provider is `CRUX_FILE_RELIANCE_EDGE`, which needs the opt-in Reliance Edge
group (`zephyr/Kconfig:372-377`); PSA on a new board also needs an entropy source. Status also needs
Netif (`zephyr/CMakeLists.txt:225-228`). This proposal does not remove these; D9 asks how to treat them.

## 2. Evidence

### 2.1 Logging

| Fact | Where |
| --- | --- |
| Access refuses an image without Logging, because security events write their records through it | `zephyr/CMakeLists.txt:197-200` |
| The security event drain writes each record with `crux_log_write()` and counts it delivered when that returns `CRUX_OK`, otherwise as a log error | `components/security_event/src/security_event_drain.c:64-71`, `:86`; links `crux::logging` at `components/security_event/CMakeLists.txt:27` and `ports/zephyr/CMakeLists.txt:52` |
| The Zephyr provider is already a thin front end: it maps the four levels to `LOG_ERR/WRN/INF/DBG` | `components/logging/ports/zephyr/logging_zephyr.c:20-35` |
| But each write first requires the bound UART device to be ready, else `NOT_READY` | `logging_zephyr.c:15-17`; promised by the [Logging contract](../logging-contract.md), line 26 |
| Deferred Zephyr logging gives no per-record acknowledgement; the contract promises drop-new with the aggregate loss report, and no wait for capacity | `logging_zephyr.c:18-19`; contract lines 20-22 and 28-29 |
| Required: `LOG`, deferred mode, process thread, UART backend with autostart, text output, visible level | `components/logging/ports/zephyr/CMakeLists.txt:11-16` |
| Forbidden: every other backend (RTT, net, FS, SWO, MQTT, semihost and others), the shell log backend, the log frontend, overflow mode, blocking in thread, runtime filtering, async UART, custom header | `CMakeLists.txt:18-28` |
| Required: DEBUG source ceiling, no override level | `CMakeLists.txt:29-31` |
| EVK only at revision B | `CMakeLists.txt:3-5` |
| `zephyr,log-uart` chosen with exactly one enabled UART | `logging_binding.c:5-11` |
| Accepted UARTs: `native_sim` UART emulator; LPUART1 on the RT1060-EVK; any `nxp,lpuart` on another RT1062 board; nothing else | `logging_binding.c:12-31` |
| 115200 8N1, no flow control, single-wire or RS-485 | `logging_binding.c:32-38` |
| When `zephyr,console` is chosen with `CONFIG_UART_CONSOLE`, the console may share the log UART only on the RT1062 and only with Logging-only routing (`LOG_PRINTK` on; stdout console, console handler, console subsystem, early console and `SHELL` off); on other SoCs that sharing is refused | `logging_binding.c:41-54`, rule at `:46-50` |
| Shell, Crux Serial, UART mcumgr and Bluetooth HCI may not own the log UART | `logging_binding.c:55-69` |
| The contract records the same profile | [Logging contract](../logging-contract.md), lines 39-50; `zephyr/Kconfig:268` |
| Representative rejection cases; some rules have none (override level, frontend, blocking in thread, async UART, section strip, deferred mode, the mcumgr and Bluetooth owners, every named backend but `NATIVE_POSIX`) | `tests/build/test_logging_composition.py:21-74` |

Two reasons sit behind the profile. First, accountability of security events: accepted decision E6 of the
[security events proposal](security-events-contract-proposal.md) requires the threshold at `INFO` or more
verbose because Logging reports a filtered call as `OK`; runtime filtering, overflow mode and a capacity
wait would add silent loss or blocking that the contract does not allow. Second, one UART with known
owners, so that log text never interleaves with a shell or Serial stream. Only the second reason is
about a board, and neither needs an RT1062.

### 2.2 System

| Fact | Where |
| --- | --- |
| Host provider: watchdog simulation; reset, reset status and reset cause return `CRUX_ERR_NOT_SUPPORTED` | `components/system/ports/linux/system_linux.c:68-113`, `:121-129` |
| Zephyr provider uses Zephyr APIs only: `wdt_install_timeout`/`wdt_setup`/`wdt_feed`, `sys_reboot(SYS_REBOOT_COLD)`, `hwinfo` reset cause | `components/system/ports/zephyr/system_zephyr.c:58-94`, `:137-158` |
| Timeout range 500 to 64000 ms in steps of 500, which is WDOG1's; validated before the single start attempt | `system_zephyr.c:33-39`; `components/system/src/system.c:189` |
| Assumes channel zero and `WDT_OPT_PAUSE_HALTED_BY_DBG` | `system_zephyr.c:65-72` |
| A `NULL` watchdog device already means "not supported" | `system_zephyr.c:41-47` |
| `native_sim` binds no watchdog (`NULL`), or the test-only simulated one | `system_binding.c:9-36` |
| RT1062: `crux-watchdog0` must exist, be `wdog0`, `nxp,imx-wdog`, at `0x400b8000`; "running" is read through the vendor HAL `WDOG_GetStatusFlags` | `system_binding.c:37-64`: alias required at `:41-42`, assert at `:50-53`, HAL at `:62` |
| Any other SoC: `#error "Crux System unsupported SoC or watchdog resource"` | `system_binding.c:65-67` |
| Requires `WATCHDOG`, `HWINFO`, `REBOOT`; EVK at revision B only | `components/system/ports/zephyr/CMakeLists.txt:3-5`, `:13-17` |
| A failed probe that is not I/O and not after a start sets the lifecycle `UNAVAILABLE` and returns that error; reset still runs | `components/system/src/system.c:59-66`, `:161-176` |
| Status and Reboot need System, by Kconfig help and by configure error | `zephyr/Kconfig:609-621`, `:695-708`; `zephyr/CMakeLists.txt:220-229`, `:247-254` |
| Status reads System through one observer call. A non-OK watchdog result is reported as a failed item, so without a watchdog `system.watchdog_state` reads `not_supported` | `components/mgmt_status/src/source_system.c:6-9`; `mgmt_status.c:129-149`, `:245-256`; [native management composition](../native-management-composition.md), line 25 |
| Reboot resets only through `crux_system_reset()` | `components/reboot/src/reboot_system_reset.c:7-10` |
| Status's public target links `crux::system` | `components/mgmt_status/ports/zephyr/CMakeLists.txt:26` |
| Zephyr's watchdog API has setup, disable, install-timeout and feed, and no "is running" query | Zephyr `include/zephyr/drivers/watchdog.h` |

So the System contract and Status already handle "no watchdog" (`not_supported`, as on `native_sim`
today). The board tie is the binding's choice of device (`system_binding.c:37-67`) and two WDOG1 facts in
the provider (timeout range, "running" through the HAL).

## 3. Options for Logging

| Option | What changes | Cost: code | Cost: tests and evidence | Existing images |
| --- | --- | --- | --- | --- |
| **L1. Crux Logging becomes a thin front end over Zephyr logging** | Keep the four-level mapping. Drop the UART binding and the backend and UART-owner rules; the product composes any Zephyr backends (UART, RTT, net, FS) and owns their sharing. Keep the rules that hold the contract (D2): `LOG` on, DEBUG ceiling, no override level, no runtime filtering, deferred mode, no overflow mode, no blocking in thread. The `NOT_READY` path (`logging_zephyr.c:15-17`) goes, because no single device is bound: a write is `OK` whenever it is submitted, and the drain counts a record lost in a backend as delivered, not as a log error | Small: delete most of `logging_binding.c`, shrink `CMakeLists.txt`, drop the readiness check | Rejection cases move (5.2). Contract lines 20-29 and 39-50 are restated: `NOT_READY` no longer occurs on Zephyr. Add one cross-build with a non-UART backend | Build unchanged: their configuration passes the smaller rule set. Behaviour unchanged except that `NOT_READY` is never returned |
| **L2. Security events get their own sink port** | Add a private sink between the drain and Logging; default sink is `crux_log_write()`; a product may route events to a dedicated Zephyr log backend, a file or a remote collector. Access then needs a sink, not Logging | Medium: a port header, a default provider, a selection symbol, the drain change at `security_event_drain.c:64-86` | Host tests of the drain against a fake sink; a configure test that Access refuses an image with no sink. The `delivered` count must be restated per sink | None if the default sink is Logging |
| **L3. Keep the RT1062 binding as a bench profile** | L1, plus an opt-in Kconfig profile (illustrative `CRUX_LOGGING_UART_PROFILE`) that keeps today's UART, mode, owner and readiness checks for the bench and the EVKB images | Small on top of L1: move the current checks under the symbol | Today's rejection cases run under the symbol unchanged | Bench images set the symbol and keep their exact checks and `NOT_READY` |
| L0. Do nothing | Each new board adds an edit to `logging_binding.c` | One reviewed edit per SoC | One rejection case per SoC | Unchanged |

L2 alone does not remove the tie: the default sink is still Logging, so it complements L1.

## 4. Options for System

| Option | What changes | Cost: code | Cost: tests and evidence | Existing images |
| --- | --- | --- | --- | --- |
| **S-A. Devicetree-generic watchdog binding** | `crux-watchdog0`, if present, may be any enabled node with a Zephyr watchdog driver. Timeout range from Kconfig or devicetree, still validated before the start (testing at install would turn a bad value into a latched fault, `system.c:189`); accept any channel returned by `wdt_install_timeout`; treat `-ENOTSUP` from the pause option as "no pause". "Running at boot" has no Zephyr query: an optional per-SoC hook (the RT1062 keeps `WDOG_GetStatusFlags`), else not known | Medium: `system_binding.c` rewrite, `system_zephyr.c:33-39` and `:65-72` generalised, a "running unknown" case in the private probe | Configure cases for a generic node; a cross-build on one non-RT1062 board; a Host case for "running unknown". The RT1062 asserts become its profile | RT1062 images keep WDOG1 through the hook; behaviour unchanged |
| **S-B. System without a watchdog off the RT1062** | On a SoC other than the RT1062, with no `crux-watchdog0` alias, bind `NULL` as `native_sim` already does (`system_binding.c:24-35`). Watchdog calls return `CRUX_ERR_NOT_SUPPORTED`, Status reports `system.watchdog_state` as `not_supported`, reset is `sys_reboot`, reset cause is `hwinfo` (or `NOT_SUPPORTED` if the SoC has none). `CONFIG_WATCHDOG` is required only when the alias exists. **The RT1062 keeps its explicit-selection error** (`:41-42`), so an EVKB image cannot silently lose its watchdog (D6) | Small: replace the `#error` at `system_binding.c:65-67` with the `NULL` binding; make the `WATCHDOG` rule conditional (`CMakeLists.txt:13-17`) | Existing cases change as listed in 5.2. One configure case per path (alias absent, alias present); one non-RT1062 cross-build of System. No contract change | None on the RT1062 or `native_sim` |
| **S-C. Reset as a product adapter behind Reboot** | Reboot's reset port (`reboot_system_reset.c`) becomes a product-provided function; Reboot no longer needs System. Status reads System only if present (a `source_no_system.c` variant, like `source_no_credential.c`) | Medium: two selection symbols, a no-System status variant, configure rules | Host tests of the variant; consumer tests of the adapter. A product must test its own reset path | None if the default adapter stays `crux_system_reset()` |
| S0. Do nothing | Each new SoC adds a reviewed binding edit | One edit per SoC | One case per SoC | Unchanged |

S-C moves the risk to the product without removing it: `sys_reboot` is already the Zephyr-native reset,
so an adapter adds a seam that the platform direction does not ask for.

## 5. Recommendation

**Logging: L1 with L3.** Crux Logging keeps the rules that hold its contract and E6, and stops choosing
backends, UARTs and their owners, which Zephyr and the product own. L3 keeps today's checks, unchanged,
for the bench images that want them. Defer L2: the drain already isolates its one call; a sink port is
worth adding when a product asks to route events away from the log.
*Alternative:* L2 first, if the owner prefers to keep Logging's UART profile and free only Access. It
frees Access but leaves every other Logging user tied to the RT1062.

**System: S-B now, S-A next.** S-B is a near-delete that uses results the contract and Status already
have (`not_supported`), and makes System, and after L1 Status and Reboot, buildable off the RT1062 with
`sys_reboot` and `hwinfo`. S-A then brings watchdog arming to other boards; its "running unknown" design
deserves its own review. *Alternative:* S-A alone, if the owner wants no board to ship Status without a
watchdog; it costs more and blocks Status on watchdog work.

**Why this order.** Each step removes a refusal without changing a public header, and each keeps the
EVKB and `native_sim` compositions building as they are today.

### 5.1 Order of changes

1. **S-B** (one PR): `NULL` binding off the RT1062 without the alias; conditional `WATCHDOG` rule; the
   case changes of 5.2; one non-RT1062 cross-build of **System alone** (Access cannot build there yet).
2. **L1 + L3** (one PR): split the Logging rules into contract rules (always) and the UART profile
   (opt-in); remove the readiness check outside the profile; move the rejection cases.
3. **Access, Status and Reboot cross-build** off the RT1062, once D9 settles the File provider, PSA and
   entropy for that board.
4. **Docs** (with each PR): [Logging contract](../logging-contract.md) lines 20-29 and 39-50,
   [porting guide](../porting-to-a-new-board.md) lines 74, 77, 81-82 and 115,
   [readiness](../component-readiness.md) rows 56-57, `zephyr/Kconfig:268` and `:281` help texts,
   [logging validation](../logging-validation.md), [system validation](../system-validation.md),
   [native management composition](../native-management-composition.md) lines 24-25, and
   [management in a product](../management-in-a-product.md) after PR #522 lands.
5. **S-A** (later, own proposal and review): generic watchdog, "running unknown", per-SoC hook.
6. **L2** (only on a product need).

### 5.2 Tests and evidence

| Item | Moves or is added |
| --- | --- |
| `tests/build/test_logging_composition.py:21-74` | UART, mode, owner and backend cases move under the L3 symbol and keep their outcomes there. `filter`, `ceiling`, `overflow` and the deferred-mode rule stay unconditional; add cases for override level and blocking in thread, which have none today; add "Logging builds with a non-UART backend" |
| `tests/build/test_system_composition.py` `no_watchdog` (`:23`) | On `native_sim`, `CONFIG_WATCHDOG=n` with no alias would now build: the expected outcome changes from refusal to success, an approved behaviour change |
| `sim_watchdog_no_watchdog` (`:35-36`) | Still refused: the simulated watchdog keeps requiring `WATCHDOG` |
| `evkb_missing` (`:28`), `custom_missing` (`:41-42`) | Unchanged: the RT1062 keeps the explicit-selection error |
| New System cases | Non-RT1062 board without alias builds; non-RT1062 alias to a generic node is still refused until S-A |
| New cross-builds | System on one in-tree non-RT1062 Zephyr board (step 1); Access, Status and Reboot there after D9 (step 3). Compile-only, recorded as a build of that board, not E3 (E3 is the EVKB build) |
| `tests/system`, `tests/mgmt_status` Host suites | No change for S-B (the `not_supported` path exists); S-A adds "running unknown" |
| `scripts/test-*.sh` runners | Touched only to add the cross-builds, without removing a suite, board or flag; a change to an existing script is a protected-path change and needs its own approval |
| Physical evidence | None exists to move: both components are E3. A new board stays "accepted, not qualified" |

### 5.3 Compatibility

- **EVKB and other RT1062 images:** build unchanged. System keeps its explicit watchdog selection. With
  L3 the images keep every current Logging check; without it they work with the smaller rule set and lose
  only `NOT_READY`.
- **`native_sim` images:** unchanged; the UART emulator remains one valid Logging composition, and the
  test-only simulated watchdog (ADR-0005) is untouched.
- **Bench:** no board operation is needed for any step. Nothing in the bench procedure changes.
- **Public API:** no header changes in S-B or L1; the Logging contract loses the `NOT_READY` case on
  Zephyr outside L3. S-A adds no public field if "running unknown" stays inside the private probe.
- **Behaviour on new boards:** a product that selects Status without a watchdog sees
  `system.watchdog_state` as `not_supported`, as `native_sim` does today; the docs must say this is not a
  failure.

## 6. Owner decisions

| ID | Decision | Recommendation | Impact if rejected |
| --- | --- | --- | --- |
| D1 | Crux Logging on Zephyr stops choosing backends and UARTs (L1) | **Yes** | Every new board needs a reviewed `logging_binding.c` edit, and Access stays tied to it |
| D2 | Which Logging rules stay unconditional | **`LOG` on, DEBUG ceiling, no override level, no runtime filtering, deferred mode, no overflow mode, no blocking in thread** | Fewer rules weaken E6 and the drop-new and no-wait promises; more keep backend choice in Crux |
| D3 | Drop `NOT_READY` from the Zephyr Logging contract outside the UART profile | **Yes** | Keeping it needs a product-named device to check, which brings back a binding |
| D4 | Keep today's UART profile as an opt-in Kconfig symbol for bench images (L3) | **Yes** | Bench images lose their owner and mode checks, or keep a second binding |
| D5 | Defer the security event sink port (L2) until a product asks | **Defer** | Adopting it now adds a port and a `delivered` redefinition with no consumer |
| D6 | Crux System builds off the RT1062 without a watchdog alias, watchdog `not_supported` (S-B), while the RT1062 keeps its explicit-selection error | **Yes, both parts** | Without S-B, Status and Reboot stay RT1062 and `native_sim` only; dropping the RT1062 rule lets a bench image lose its watchdog silently |
| D7 | Generic watchdog binding (S-A) as a separate, later proposal | **Yes, later** | Doing it now blocks D6 on the "running unknown" design |
| D8 | Reject the reset adapter (S-C) | **Reject** | Adds a product seam for a reset that Zephyr already provides |
| D9 | The remaining Access ties off the RT1062 (File provider, PSA, entropy; Netif for Status) | **Out of scope here; record them as a known limit and take them up in their own proposal** | Taking them in now widens this change into storage and crypto composition |
| D10 | Which in-tree non-RT1062 board carries the cross-build evidence | **Owner to choose; it must have a watchdog-less path for step 1 and, for step 3, a File provider and an entropy source** | Without one, "any board" stays a claim without a build |

Each implementation step after these decisions follows `AGENTS.md`: TDD, the protected-path rule for
any existing `scripts/` or `.github/` file, independent review and a Draft PR.
