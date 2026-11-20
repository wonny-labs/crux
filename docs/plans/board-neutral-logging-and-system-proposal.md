# Board-neutral Logging and System for the management services

Status: **Proposal, not adopted.** Nothing here changes code, a contract, a check or an image. The owner
decides D1 to D8 below; until then the bindings stay as they are.
Baseline: main `2c4a36c2`. Line numbers below are from that revision.
Direction: [ADR-0002](../decisions/0002-platform-direction-zephyr-execution-crux-services.md) and
[ADR-0003](../decisions/0003-p9-result-services-keep-narrow-thread-sync.md): Zephyr owns execution,
drivers, log backends and the reset and watchdog hardware; Crux owns service policy.

## 1. Problem

Three services that a product on any Zephyr board would want inherit one board's constraints:

- **Access** (and with it every management service) needs Crux Logging, and Crux Logging on Zephyr
  builds only with one deferred 115200 8N1 UART text log on an RT1062 LPUART or the `native_sim` UART
  emulator.
- **Management Status** and **Reboot** need Crux System, and Crux System on Zephyr builds only on
  `native_sim` or on an RT1062 whose `crux-watchdog0` alias is WDOG1 at `0x400b8000`.

Neither tie protects accepted physical evidence: both components are at **E3** (software and
`native_sim`), with physical acceptance still open
([readiness `logging` and `system` rows](../component-readiness.md), lines 56-57). The ties pin a
reviewed profile, not a qualified one.

## 2. Evidence

### 2.1 Logging

| Fact | Where |
| --- | --- |
| Access refuses an image without Logging, because security events write their records through it | `zephyr/CMakeLists.txt:197-200` |
| The security event drain writes each record with `crux_log_write()` and counts it delivered when that returns `CRUX_OK` | `components/security_event/src/security_event_drain.c:64-67`, `:86`; links `crux::logging` at `components/security_event/CMakeLists.txt:27` and `ports/zephyr/CMakeLists.txt:52` |
| The Zephyr provider is already a thin front end: it maps the four levels to `LOG_ERR/WRN/INF/DBG` | `components/logging/ports/zephyr/logging_zephyr.c:20-35` |
| But each write first requires the bound UART device to be ready | `logging_zephyr.c:15-17` |
| Deferred Zephyr logging gives no per-record acknowledgement | `logging_zephyr.c:18-19` |
| Required: `LOG`, deferred mode, process thread, UART backend with autostart, text output, visible level | `components/logging/ports/zephyr/CMakeLists.txt:11-16` |
| Forbidden: every other backend (RTT, net, FS, SWO, MQTT, semihost and others), the shell log backend, the log frontend, overflow mode, runtime filtering, async UART, custom header | `CMakeLists.txt:18-28` |
| Required: DEBUG source ceiling, no override level | `CMakeLists.txt:29-31` |
| EVK only at revision B | `CMakeLists.txt:3-5` |
| `zephyr,log-uart` chosen with exactly one enabled UART | `logging_binding.c:5-11` |
| Accepted UARTs: `native_sim` UART emulator; LPUART1 on the RT1060-EVK; any `nxp,lpuart` on another RT1062 board; nothing else | `logging_binding.c:12-31` |
| 115200 8N1, no flow control, single-wire or RS-485 | `logging_binding.c:32-38` |
| The console may share the log UART only on the RT1062 and only with Logging-only routing (`LOG_PRINTK` on; stdout console, console handler, console subsystem, early console and `SHELL` off); elsewhere sharing is refused | `logging_binding.c:41-54`, rule at `:46-50` |
| Shell, Crux Serial, UART mcumgr and Bluetooth HCI may not own the log UART | `logging_binding.c:55-69` |
| The contract records the same profile | [Logging contract](../logging-contract.md), lines 38-50 |
| Each rule has a rejection case | `tests/build/test_logging_composition.py:18-48` |

Two reasons sit behind the profile. First, accountability of security events: accepted decision E6 of the
[security events proposal](security-events-contract-proposal.md) requires the threshold at `INFO` or more
verbose because Logging reports a filtered call as `OK`; runtime filtering, overflow mode and extra
backends would add more silent paths. Second, one UART with known owners, so that log text never
interleaves with a shell or Serial stream. Neither reason needs an RT1062.

### 2.2 System

| Fact | Where |
| --- | --- |
| Host provider: watchdog simulation; reset, reset status and reset cause return `CRUX_ERR_NOT_SUPPORTED` | `components/system/ports/linux/system_linux.c:68-113`, `:121-129` |
| Zephyr provider uses Zephyr APIs only: `wdt_install_timeout`/`wdt_setup`/`wdt_feed`, `sys_reboot(SYS_REBOOT_COLD)`, `hwinfo` reset cause | `components/system/ports/zephyr/system_zephyr.c:58-94`, `:137-158` |
| Timeout range 500 to 64000 ms in steps of 500, which is WDOG1's | `system_zephyr.c:33-39` |
| Assumes channel zero and `WDT_OPT_PAUSE_HALTED_BY_DBG` | `system_zephyr.c:65-72` |
| A `NULL` watchdog device already means "not supported" | `system_zephyr.c:41-47` |
| `native_sim` binds no watchdog (`NULL`), or the test-only simulated one | `system_binding.c:9-36` |
| RT1062: `crux-watchdog0` must be `wdog0`, `nxp,imx-wdog`, at `0x400b8000`; "running" is read through the vendor HAL `WDOG_GetStatusFlags` | `system_binding.c:37-64`, assert at `:50-53`, HAL at `:62` |
| Any other SoC: `#error "Crux System unsupported SoC or watchdog resource"` | `system_binding.c:65-67` |
| Requires `WATCHDOG`, `HWINFO`, `REBOOT`; EVK at revision B only | `components/system/ports/zephyr/CMakeLists.txt:3-5`, `:13-17` |
| A failed probe that is not I/O and not after a start leaves the lifecycle `UNAVAILABLE`; reset still runs | `components/system/src/system.c:59-66`, `:161-176` |
| Status and Reboot need System, by Kconfig help and by configure error | `zephyr/Kconfig:609-621`, `:695-708`; `zephyr/CMakeLists.txt:220-229`, `:247-254` |
| Status reads System only through one observer call and already renders `unavailable` | `components/mgmt_status/src/source_system.c:6-9`; `mgmt_status.c:62-63`, `:129-148` |
| Reboot resets only through `crux_system_reset()` | `components/reboot/src/reboot_system_reset.c:7-10` |
| Status's public target links `crux::system` | `components/mgmt_status/ports/zephyr/CMakeLists.txt:26` |

So the System contract already models "no watchdog" and the services already render it. The board tie is
two things only: the binding's choice of device (`system_binding.c:37-67`) and two WDOG1 facts in the
provider (timeout range, "running" through the HAL).

## 3. Options for Logging

| Option | What changes | Cost: code | Cost: tests and evidence | Existing images |
| --- | --- | --- | --- | --- |
| **L1. Crux Logging becomes a thin front end over Zephyr logging** | Keep the four-level mapping. Drop the UART binding and `device_is_ready` check; drop the backend and UART rules. Keep only the rules that protect Crux semantics: `LOG` on, DEBUG ceiling, no override level, no runtime filtering (E6). The product composes any Zephyr backends (UART, RTT, net, FS) and owns their UART sharing | Small: delete most of `logging_binding.c`, shrink `CMakeLists.txt`, keep `logging_zephyr.c` minus the readiness check | Rejection cases of `test_logging_composition.py` move: UART and backend cases go, semantic cases stay. Add one non-RT1062, non-`native_sim` cross-build (for example a Zephyr `qemu_cortex_m3` or another in-tree board). `native_sim` keeps its UART emulator as one composition | Build unchanged: their configuration still passes the smaller rule set. Behaviour unchanged |
| **L2. Security events get their own sink port** | Add a private sink between the drain and Logging; default sink is `crux_log_write()`; a product may route events to a dedicated Zephyr log backend, a file or a remote collector. Access then needs a sink, not Logging | Medium: a port header, a default provider, a selection symbol, the drain change at `security_event_drain.c:64-86` | Host tests of the drain against a fake sink; a configure test that Access refuses an image with no sink. The `delivered` count meaning must be restated per sink | None if the default sink is Logging |
| **L3. Keep the RT1062 binding as a bench profile** | L1, plus an opt-in Kconfig profile (illustrative `CRUX_LOGGING_UART_PROFILE`) that keeps today's UART, mode and owner checks for the bench and the EVKB images | Small on top of L1: move the current checks under the symbol | Today's rejection cases run under the symbol unchanged | Bench images set the symbol and keep their exact checks |
| L0. Do nothing | Each new board adds an edit to `logging_binding.c` | One reviewed edit per SoC | One rejection case per SoC | Unchanged |

L2 alone does not remove the tie: the default sink is still Logging, so it is a complement to L1, not an
alternative.

## 4. Options for System

| Option | What changes | Cost: code | Cost: tests and evidence | Existing images |
| --- | --- | --- | --- | --- |
| **S-A. Devicetree-generic watchdog binding** | Replace the per-SoC branch with: `crux-watchdog0` alias, if present, is any enabled node with a Zephyr watchdog driver. Timeout range from Kconfig or tried at install; accept any channel returned by `wdt_install_timeout`; treat `-ENOTSUP` from the pause option as "no pause". The "running at boot" probe has no Zephyr API: report it from an optional per-SoC hook (the RT1062 keeps `WDOG_GetStatusFlags`), else as not known | Medium: `system_binding.c` rewrite, `system_zephyr.c:33-39` and `:65-72` generalised, a "running unknown" case in the private probe | New configure cases for a generic watchdog node; a cross-build on one non-RT1062 board; the System Host suite gains the "running unknown" case. The RT1062 assert becomes a profile | RT1062 images keep WDOG1 through the hook; behaviour unchanged |
| **S-B. System without a watchdog** | If no `crux-watchdog0` alias, bind `NULL` on any board, as `native_sim` already does (`system_binding.c:24-35`). Watchdog calls return `CRUX_ERR_NOT_SUPPORTED`, status shows `unavailable`, reset is `sys_reboot`, reset cause is `hwinfo` (or `NOT_SUPPORTED` if the SoC has none) | Small: replace the `#error` at `system_binding.c:65-67` with the `NULL` binding; make `CONFIG_WATCHDOG` required only when the alias exists (`CMakeLists.txt:13-17`) | One configure case per path (alias absent, alias present); one non-RT1062 cross-build of Status and Reboot. No contract change: `UNAVAILABLE` already exists | None |
| **S-C. Reset as a product adapter behind Reboot** | Reboot's reset port (`reboot_system_reset.c`) becomes a product-provided function; Reboot no longer needs System. Status reads System only if present (a `source_no_system.c` variant, like `source_no_credential.c`) | Medium: two selection symbols, a no-System status variant, configure rules | Host tests of the variant; consumer tests of the adapter. A product must test its own reset path | None if the default adapter stays `crux_system_reset()` |
| S0. Do nothing | Each new SoC adds a reviewed binding edit | One edit per SoC | One case per SoC | Unchanged |

S-C moves the risk to the product without removing it: `sys_reboot` is already the Zephyr-native reset,
so an adapter adds a seam that ADR-0002 does not ask for.

## 5. Recommendation

**Logging: L1 with L3.** Crux Logging keeps the policy that matters to Crux (four levels, DEBUG ceiling,
no override, no runtime filtering for E6) and stops choosing backends, UARTs and their owners, which
Zephyr and the product own under ADR-0002. L3 keeps today's checks, unchanged, for the bench images that
want them. Defer L2: the drain already isolates its one call; a sink port is worth adding when a product
asks to route events away from the log.
*Alternative:* L2 first, if the owner prefers to keep Logging's UART profile and free only Access. It
frees Access but leaves every other Logging user tied to the RT1062.

**System: S-B now, S-A next.** S-B is a near-delete that uses semantics the contract and Status already
have, and makes Status and Reboot buildable on any Zephyr board with `sys_reboot` and `hwinfo`. S-A then
brings watchdog arming to other boards; it needs the "running unknown" design, which deserves its own
review. *Alternative:* S-A alone, if the owner wants no board to ship Status without a watchdog; it costs
more and blocks Status on watchdog work.

**Why this order.** Each step removes a refusal without changing a public header, and each keeps the
EVKB and `native_sim` compositions building as they are today.

### 5.1 Order of changes

1. **S-B** (one PR): `NULL` binding on any board without the alias; `CONFIG_WATCHDOG` conditional;
   configure cases; one non-RT1062 cross-build of System, Status and Reboot in CI.
2. **L1 + L3** (one PR): split the Logging rules into "Crux semantics" (always) and "UART profile"
   (opt-in); remove the readiness check; move the rejection cases; non-RT1062 cross-build of Access.
3. **Docs** (with each PR): Logging contract lines 38-50, [porting guide](../porting-to-a-new-board.md)
   lines 74, 77, 81-82 and 115, [readiness](../component-readiness.md) rows 56-57,
   [management in a product](../management-in-a-product.md) once its parallel change has landed.
4. **S-A** (later, own proposal or review): generic watchdog, "running unknown", per-SoC hook.
5. **L2** (only on a product need).

### 5.2 Tests and evidence

| Item | Moves or is added |
| --- | --- |
| `tests/build/test_logging_composition.py:18-48` | UART, mode, owner and backend cases move under the L3 symbol; semantic cases (`filter`, `ceiling`) stay unconditional, and an override-level case is added; add "Logging builds with a non-UART backend" |
| `tests/build/test_system_composition.py` | Add: no alias on a non-RT1062 board builds; alias to a generic node is still refused until S-A |
| New cross-build | One in-tree non-RT1062 Zephyr board building Access, Status and Reboot; compile-only, recorded as E3 for that board |
| `tests/system`, `tests/mgmt_status` Host suites | No change for S-B (the `UNAVAILABLE` path exists); S-A adds "running unknown" |
| `scripts/test-*.sh` runners | Touched only to add the cross-build, without removing a suite, board or flag; a change to an existing script is a protected-path change and needs its own approval |
| Physical evidence | None exists to move: both components are E3. A new board stays "accepted, not qualified" |

### 5.3 Compatibility

- **EVKB and other RT1062 images:** build unchanged. With L3 they set the profile symbol and keep every
  current check; without it they keep working with the smaller rule set.
- **`native_sim` images:** unchanged; the UART emulator remains one valid Logging composition, and the
  test-only simulated watchdog (ADR-0005) is untouched.
- **Bench:** no board operation is needed for any step. Nothing in the bench procedure changes.
- **Public API:** no header changes in S-B or L1. S-A adds no public field if "running unknown" stays
  inside the private probe.
- **Behaviour on new boards:** a product that selects Status without a watchdog sees
  `system.watchdog_state = unavailable`; the docs must say this is not a failure.

## 6. Owner decisions

| ID | Decision | Recommendation | Impact if rejected |
| --- | --- | --- | --- |
| D1 | Crux Logging on Zephyr stops choosing backends and UARTs (L1) | **Yes** | Every new board needs a reviewed `logging_binding.c` edit, and Access stays tied to it |
| D2 | Which Logging rules stay unconditional: LOG on, DEBUG ceiling, no override level, no runtime filtering | **Those four** | Fewer rules weaken E6; more rules keep backend choice in Crux |
| D3 | Keep today's UART profile as an opt-in Kconfig symbol for bench images (L3) | **Yes** | Bench images lose their owner and mode checks, or keep a second binding |
| D4 | Defer the security event sink port (L2) until a product asks | **Defer** | Adopting it now adds a port and a `delivered` redefinition with no consumer |
| D5 | Crux System builds on any Zephyr board without a watchdog alias, with the watchdog `unavailable` (S-B) | **Yes** | Status and Reboot stay RT1062 and `native_sim` only |
| D6 | Generic watchdog binding (S-A) as a separate, later proposal | **Yes, later** | Doing it now blocks D5 on the "running unknown" design |
| D7 | Reject the reset adapter (S-C) | **Reject** | Adds a product seam for a reset that Zephyr already provides |
| D8 | Which in-tree non-RT1062 board carries the cross-build evidence | **Owner to choose; author suggests a Cortex-M board already in the west workspace** | Without one, "any board" stays a claim without a build |

Each implementation step after these decisions follows `AGENTS.md`: TDD, the protected-path rule for
any existing `scripts/` or `.github/` file, independent review and a Draft PR.
