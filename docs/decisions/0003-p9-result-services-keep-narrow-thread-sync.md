# ADR-0003: P9 result: services keep a narrow Crux Thread and Sync

Status: **Accepted**. It decides P9 of [ADR-0002](0002-platform-direction-zephyr-execution-crux-services.md) and gives P8 new wording, so it **amends ADR-0002** as [What this amends](#what-this-amends-in-adr-0002) lists. The decided outcomes are under [Decided](#decided).

Each change that this record puts into effect is its own reviewed change, listed under [Follow-up changes](#follow-up-changes).

## Context

P9 of ADR-0002 left the internals choice open until evidence existed: keep a slim internal Crux Thread and Sync (O4), or move the services to Zephyr kernel objects (O2). The rule was fixed before the runs. A pilot on the `reboot` service supplied the evidence: its 79 cases ran on `native_sim` over the unchanged Crux providers, and a move of the service to `k_mutex`, `k_sem`, `k_thread` and `k_msleep` was trialled on a pilot branch that passed the flake bar and was not merged. The service on `main` keeps Crux Sync (R1).

O2 needs every criterion of the rule to hold, and four fail, two of them (M4 and M6) on one suite. The criteria M1 to M7 are those of the [reboot pilot results](../research/reboot-native-sim-stage-a.md#results), and B1 to B4 are the blockers that pilot left without an answer ([history record](../history/adr-0003-record.md)):

- **M2.** On the same suites, the `native_sim` run takes about 19 to 23 times the Host `host-sanitize` run, against a limit of 2.
- **M4 and M6, narrowly.** The 9 checks of `sleep_provider` no longer run.
- **Blockers B1 to B4** have no answer.

The figures are local runs, not CI runs. The ThreadSanitizer suites (B4) and any physical board were not measured. Neither the Host nor the `native_sim` build has a race detector for these suites, so neither shows a data race.

## Decisions

Reasons and alternatives are taken from the pilot records, ADR-0002 and the [platform direction review](../research/platform-direction-review.md).

| # | Decision | Reason | Alternative |
| --- | --- | --- | --- |
| R1 | O4: keep a narrow Crux Thread and Sync inside the services | O2's criteria do not all hold (above), and the service swap itself was small and passed the flake bar | O2: move the services to Zephyr kernel objects |
| R2 | State the rule for both OSes, with Crux's services using the narrow Thread and Sync | It is P1 with the services' inside named, so product code sees no change under O4 | Leave P1 as it is, which does not say what the services use |
| R3 | Thread and Sync become internal later, in a separate approved change, after the migrations | The switch is the owner's call, and the consumers must move first. P2 already freezes new use | Decide deprecation now, which ADR-0002's P9 rejected as untested option c |
| R4 | Record `ssh`'s native threads as a known exception | It is the current state, and the review lists it (F7) | None |
| R5 | Embedded Linux is expected and designed at the service boundary when its first product is defined, with no date | The owner expects the integration, and the service boundary is where ADR-0002 already placed it | ADR-0002's P8 wording, "not planned for the foreseeable future" |
| R6 | Record the POSIX subset as candidate O5, evaluated when a Linux product is defined | The review evaluated it and it lost at the recorded pin (F18), and it stays an option for a consumer whose evidence differs | Drop O5, or adopt it now without a Linux product |

1. **R1. P9 result: O4.** Crux's services keep a narrow Crux Thread and Sync internally, with Zephyr and Linux providers. The services do not move to Zephyr kernel objects (O2).
2. **R2. Principle.** Product code uses the OS natively: Zephyr products call Zephyr, Linux products call Linux. Crux's services use the narrow Crux Thread and Sync. Other OS facilities (drivers, networking, storage) are used natively in adapters. This is P1 with the services' inside named.
3. **R3. Target state.** Crux Thread and Sync become internal to Crux. That switch is a later, separate pull request. It needs the owner's approval, and it comes after the PLC runtime port, `crux-controller` and the samples have migrated. Queue and Serial are decided separately, because `cli` uses Serial. Deprecating and removing the public headers is part of that later decision. The P2 freeze stays until then. **Queue was decided on 20 November 2026:** the owner removed Crux Queue (header, targets, `CONFIG_CRUX_QUEUE`, tests and runners); Zephyr `k_msgq` replaces it, as the [messaging contract](../messaging-contract.md) records.
4. **R4. Known exception.** `ssh` uses native threads.
5. **R5. P8, new wording.** An Embedded Linux integration is expected. It will be designed at the service boundary when its first product is defined. No date is set. The Linux providers remain test providers (P7) until then. The text of the README and `:37` follows this wording in its own change.
6. **R6. O5, candidate.** Moving the services' internals to a documented POSIX subset is evaluated when a Linux product is defined. Known blocker: Zephyr's POSIX layer needs picolibc or newlib, and the workspace has neither. That evaluation must also check that the PLC runtime's timing needs are met: distinct run-time priorities and sub-millisecond waits.

## What this amends in ADR-0002

- **P8** is replaced by R5. ADR-0002 words it as "not planned for the foreseeable future".
- **P9** is decided by R1 and R3. Its deprecation rule, which depended on Build B', is not applied here. Deprecation and removal are part of R3's later decision.
- **P7** is kept, and R5 repeats it.
- **P1 to P6 and P10** are kept. P2's freeze stays.

## Consequences

- Product code keeps the one rule of P1 under O4, and R2 states it for both OSes.
- `crux-controller` keeps working. Its threads and queue stay on the frozen headers until it migrates.
- Crux's Thread and Sync providers keep their Host and Zephyr tests. No service is rewritten.
- Embedded Linux is expected but not scheduled, so nothing about it is built or promised now.

## Follow-up changes

None of these is part of this ADR. Each is its own reviewed change.

1. Documentation that still says P9 is undecided or that Embedded Linux is not planned: the README, `docs/architecture.md`, `docs/thread-sync.md` (its freeze notice and the remark at `:150` that workers may become native threads under P9), and the freeze notices of `docs/messaging-contract.md` and `docs/serial-contract.md`.
2. The switch that makes Thread and Sync internal, with the decision for Queue and Serial. It needs the owner's approval and follows the migrations in R3.
3. The O5 evaluation, when a Linux product is defined.

<a id="the-owners-decision"></a>

## Decided

R1 to R6 are decided as stated under [Decisions](#decisions). The statement that an Embedded Linux integration is expected is the owner's. The switch to internal-only (R3), hardware, tags and merging are outside this decision.

The drafting record, measurements and approval history are in [history/adr-0003-record.md](../history/adr-0003-record.md).
