# ADR-0005: How a consumer composes the Crux System service on native_sim with a test watchdog

Status: **Accepted**, as recommended: S1 to S9, listed under [Decided](#the-owners-decisions). The T4 row of section 4 was later amended in place to match the S6 guard rule. Route A and the Crux-side follow-ups are implemented, see [Follow-up changes](#follow-up-changes).

This record decides how a consumer composes the System service on `native_sim` with a test watchdog. Each change that it put forward is its own reviewed change, listed under [Follow-up changes](#follow-up-changes).

**Labels.** **Verified** means read at the record's baseline revision and cited as `path:line`, or run as stated. **Reported** means a named document or note says it and it was not re-checked. **Inference** is a reading of the sources. **Not verified** means no run or read exists. No Zephyr build, `native_sim` run or hardware command ran for this record.

## In brief

- On `native_sim` the System binding returned no watchdog device, so a consumer outside this repository had no public way to start, feed or miss a feed of the watchdog. Crux's own tests filled that seam with a link-time wrap of two private symbols.
- **Route A** is adopted: a `native_sim`-only simulated watchdog that the Zephyr module provides and one Kconfig symbol selects, with a configure error on any other board. It adds one Experimental Kconfig symbol, no header, no target and no function. Route C (Zephyr's counter watchdog) and route B (a public test seam) are not adopted.
- `native_sim` can show the boot cause line, a feed cycle and a missed feed that restarts the simulated process. It cannot show the `CRUX_RESET_CAUSE_WATCHDOG` bit, and it is not hardware evidence.
- The consumer guard refuses a link-time wrap of any `crux_` symbol (S6).
- The reset loop is the product's to decide. Crux System keeps no stop, no rearm and no boot journal.

## Context

[ADR-0001](0001-application-boundary-and-api-stability.md) (Decision 2, adopted as the owner's item D3, and Decision 4, adopted as item D5) adopted the [composition interface rules](../composition-interfaces.md) and the stability tiers. [ADR-0002](0002-platform-direction-zephyr-execution-crux-services.md) and [ADR-0003](0003-p9-result-services-keep-narrow-thread-sync.md) decided that product code uses the OS natively. ADR-0004 decided how a product composes the management services and named the System service in its scope, and its boundary-test fixture is the model here.

The Crux Controller product adopted the System service: the reset cause is logged at boot, the watchdog is fed by the workload's producer thread, and the policy is plain C (**Reported**). Its acceptance criterion "a `native_sim` scenario shows the reset cause line and a feed cycle, and a missed feed is observed as the Crux contract describes" could not be met by a product (**Reported**, its issue #41 and its findings note `docs/findings/s4-system-composition.md`, friction 1 and 7). The Crux side is re-checked below.

## 1. Current state

| # | Fact | Evidence | Status |
| --- | --- | --- | --- |
| 1 | Under `CONFIG_BOARD_NATIVE_SIM`, `crux_watchdog_zephyr_device()` returns `NULL` and `crux_watchdog_zephyr_running()` returns `false`. The comment says tests substitute a native driver object at this private binding seam | `system_binding.c:5-17` | Verified |
| 2 | The RT1060-EVKB branch needs the alias `crux-watchdog0` (`#error` at `:20`, `:22`) and pins the node to `wdog0` at `0x400b8000` (`BUILD_ASSERT` at `:28-30`). Any other board stops with `#error "Crux System unsupported Zephyr board"` | `system_binding.c:18-45` | Verified |
| 3 | A NULL device makes the start, the provider's feed and the status probe return `CRUX_ERR_NOT_SUPPORTED` | `system_zephyr.c:40-46` (`watchdog_ready`), `:48-55` (probe) | Verified |
| 4 | The provider requires `CONFIG_WATCHDOG`, `CONFIG_HWINFO` and `CONFIG_REBOOT`, and refuses four other native owners, on `native_sim` too | `components/system/ports/zephyr/CMakeLists.txt:9-20` | Verified |
| 5 | `crux_watchdog_is_emulated()` returns `false` in the Zephyr provider. `refresh()` moves to `EXPIRED` on "emulated" only when the probe reports `expired`, and `crux_watchdog_feed` only when the provider's feed returns `CRUX_ERR_TIMEOUT`. The Zephyr probe always reports `expired = false` and the Zephyr feed returns only OK, NOT_SUPPORTED, NOT_READY or IO | `system_zephyr.c:27-29`, `:52`, `:74-82`, `system.c:69`, `:243` | Verified |
| 6 | Crux's own tests substitute the device by linking with `-Wl,--wrap=crux_watchdog_zephyr_device` and `--wrap=crux_watchdog_zephyr_running`, and define a fixture device with `DEVICE_DEFINE` | `tests/system/zephyr/CMakeLists.txt:8-12`, `tests/system/zephyr/src/main.c:59-68` | Verified |
| 7 | On `native_sim` the integrated test expects `watchdog_status == CRUX_ERR_NOT_SUPPORTED` and `CRUX_WATCHDOG_UNAVAILABLE`. The System consumer on `native_sim` only observes (cause is POR) and never starts the watchdog | `tests/integrated_smoke/zephyr/main.c:425-431`, `tests/system_consumer/zephyr/main.c` | Verified |
| 8 | `tests/system_consumer` is a Crux-owned application in this repository, not an out-of-tree consumer | path | Verified |
| 9 | `crux-watchdog0` is named in no user-facing document. It appears in the System design spec, a feasibility record (`docs/rt1170-evk-a1-feasibility.md:68`), the binding, and tests and overlays | `grep` of tracked `*.md`, `*.overlay`, `*.c`, `*.txt`, `*.yml`, `*.py` outside `docs/evidence` | Verified |
| 10 | `<crux/system.h>` includes only `<crux/status.h>`, `<stdbool.h>` and `<stdint.h>`. It carries no `Status:` tier line, and no tier table exists yet | `components/system/include/crux/system.h:11-13`, `docs/compatibility-table.md` (a revision table, not a tier table) | Verified |
| 11 | `CONFIG_CRUX_SYSTEM` depends on `CRUX_PILOT_MODULE && MULTITHREADING` and the module adds its subdirectory under that symbol. The Zephyr provider links `crux_system_api` (and through it `crux::base`), `zephyr_interface` and `crux_interrupt`, and none of them links a Thread, Sync, Queue or Serial target as read from the sources. System needs no frozen Thread, Sync, Queue or Serial symbol | `zephyr/Kconfig:223-228`, `zephyr/CMakeLists.txt:108-111`, `components/system/ports/zephyr/CMakeLists.txt` last two lines | Verified |

**Existing precedents for a `native_sim`-only switch.** `CRUX_FILE_SIMULATOR` depends on `BOARD_NATIVE_SIM` (`zephyr/Kconfig:230-234`). `CRUX_WEB_PLAIN_HTTP_FOR_TESTS` depends on `BOARD_NATIVE_SIM` and says "no other board can select it" (`zephyr/Kconfig:420-424`). `CRUX_SETTINGS_FILE_CONTROL` is a CMake variable that stops the configure step on any other board (`zephyr/CMakeLists.txt:142-146`). All three are **Verified** by reading.

**What the System contract says about this** (the accepted design, [System health design](../design/system-health-design.md)):

- `native_sim` "uses the real Zephyr kernel/device watchdog dispatch with a controlled fixture device and controlled reset/fault hooks where needed", reuses the native HWINFO for the POR and SOFTWARE path, and "never call an actual machine reset" (`:301-305`).
- `EXPIRED` is observable only in the Host simulation. On real hardware an expiry can reset the processor before any status call (`:170-172`).
- No stop, no rearm, no multi-channel, and tokens do not survive a reboot (`:173-176`). There is no persistent boot journal (`:201`).
- The initial boot diagnostic owner reads the cause, keeps its copy, then may clear (`:213`).

### 1.1 The Zephyr side on `native_sim` (read at the manifest pin)

The manifest pins Zephyr `dccb09599635bdff17633fa7e9dab014b91dce90` (`west.yml:19`, v4.4.2). The facts below were read at that pin.

| Fact | File at the pin | Status |
| --- | --- | --- |
| The native HWINFO reports `RESET_POR \| RESET_SOFTWARE` as supported, starts with POR, and takes SOFTWARE only if the host environment variable `NATIVE_SIM_RESET_CAUSE` equals `SOFTWARE` (any other value falls back to POR with a warning) | `drivers/hwinfo/hwinfo_native.c:45-47`, `:85-111` | Verified |
| With `CONFIG_NATIVE_SIM_REBOOT=y`, `sys_reboot` ends in `sys_arch_reboot`, which marks "reboot on exit" and calls `posix_exit(0)`. At exit the board code sets `NATIVE_SIM_RESET_CAUSE=SOFTWARE`, prints a warning and re-executes `/proc/self/exe` with the same arguments. The symbol depends on `REBOOT`, defaults to off, and `native_sim_defconfig` does not set it | `boards/native/native_sim/Kconfig:31-34`, `CMakeLists.txt:14-17`, `reboot.c`, `reboot_bottom.c` (`maybe_reboot`) | Verified |
| **Without** that symbol, `sys_arch_reboot` is a weak stub that prints a warning and calls `posix_exit(1)`: the process ends with status 1 and does not restart. No file in this repository sets `CONFIG_NATIVE_SIM_REBOOT` | `arch/posix/core/cpuhalt.c:55-64`; `grep` of this repository | Verified |
| Zephyr has a counter-based watchdog (`zephyr,counter-watchdog`) that supports `WDT_FLAG_RESET_SOC` and, on expiry, calls `LOG_PANIC()` and then `sys_arch_reboot(0)` directly (not `sys_reboot`) | `drivers/watchdog/wdt_counter.c:14`, `:63-66` | Verified |
| That driver's `setup` returns `-ENOTSUP` when `WDT_OPT_PAUSE_HALTED_BY_DBG` or `WDT_OPT_PAUSE_IN_SLEEP` is set. The System provider always passes `WDT_OPT_PAUSE_HALTED_BY_DBG` (`system_zephyr.c:71`), and any non-zero result becomes `CRUX_ERR_IO` and a faulted lifecycle (`system.c:217`) | `wdt_counter.c:36-38` | Verified |
| That driver's `install_timeout` returns the channel number it allocated, counting down from `CONFIG_WDT_COUNTER_CH_COUNT` (default 4, range 1 to 255). The System provider treats any non-zero return as `CRUX_ERR_IO` (`system_zephyr.c:68-70`), so the first install returns 3 and fails unless the count is 1. The starting count is the smaller of the counter's channels and that setting (`wdt_counter.c:168-170`), and the native-sim counter defaults to 4 channels (`drivers/counter/Kconfig.native_sim:14-16`) | `wdt_counter.c:125-137`, `drivers/watchdog/Kconfig:73-77` | Verified |
| `native_sim` defines `counter0` with `zephyr,native-sim-counter` | `boards/native/native_sim/native_sim.dts:177-180` | Verified |
| The counter watchdog runs on the native-sim counter at this pin once the provider's call sequence is adapted (counter alarms, tick range, the native-sim counter's channel count) | no build or run | **Not verified** |
| A `native_sim` process re-exec keeps its console output in one Twister harness stream | no run | **Not verified** |

### 1.2 What the boundary guard did before the S6 rule

`crux_assert_portable_consumer` (`cmake/CruxConsumerBoundary.cmake`) inspects a consumer target's own include directories, link options and the rest. Before the S6 rule, probes against the guard showed that a consumer adding `components/system/ports/zephyr` or `components/system/src` was refused and the public include root accepted. A wrap of `crux_watchdog_zephyr_device` or `crux_watchdog_zephyr_running` was refused only by the token `zephyr` in the name, and a wrap of `z_impl_hwinfo_get_reset_cause` or `sys_reboot` was accepted: the guard had no rule about link-time wraps. The guard is a function that a consumer's CMake must call, so whether a given consumer calls it is the consumer's choice.

## 2. Routes

**Route A: a Kconfig-selected simulated watchdog in the Zephyr module.** A private source file under `components/system/ports/zephyr/`, built only when one new Kconfig symbol is set, defines a Zephyr watchdog device with `DEVICE_DEFINE`, the way the test fixture does (`tests/system/zephyr/src/main.c:59`). It implements `install_timeout` (one channel, minimum window 0, flag `RESET_SOC` only), `setup`, `feed`, and an expiry handler that prints one line and calls `sys_reboot`. Zephyr's counter watchdog calls `LOG_PANIC()` and `sys_arch_reboot(0)` instead (`wdt_counter.c:63-66`); the choice between the two is S5. The device accepts the provider's call sequence as it is: window minimum 0, `WDT_OPT_PAUSE_HALTED_BY_DBG`, channel 0. This is a simulated device in the sense of ADR-0001 Decision 3's "Zephyr emulators" (a Zephyr device object for a test); it is not a Crux device or driver model, and no Crux API exposes it. The `native_sim` branch of the binding returns that device and its running state when the symbol is set, and `NULL` and `false` otherwise, so every existing expectation stays. The product sets the symbol in its `native_sim`-only configuration fragment. No header, target or devicetree node is added. Whether the symbol should also `select NATIVE_SIM_REBOOT`, so that an expiry restarts the process and does not end it, is S5.

*Fail closed.* A `depends on BOARD_NATIVE_SIM` line alone is not enough. On another board the symbol would be hidden, and **Reported** by ADR-0004 and by the Controller note (friction 6) that an unmet dependency only warns and the symbol becomes `n`. I did not re-check this at the pinned Zephyr. Worse, a CMake check cannot see a hidden symbol. **Inference:** declare the symbol without a board dependency, stop with `message(FATAL_ERROR)` in the component's CMake file when it is set on any board other than `native_sim` (the `CRUX_SETTINGS_FILE_CONTROL` precedent), and keep an `#error` in the binding as the second line. The negative tests of section 4 assert a non-zero exit and the symbol name in the message, whichever line fires first.

**Route B: a public test seam.** A composition interface `<crux/system_zephyr.h>` with an INTERFACE target, so a product can hand a Zephyr watchdog device to System. Two shapes: B1, publish the two existing declarations (`system_zephyr.h` today) as functions that **the product implements**; B2, a new bind function. B1 turns a module-implemented getter into a product-implemented port. That is the shape of ADR-0004 C3, which the six rules do not cover. B2 adds a function, which rule 4 does not allow without a decision (ADR-0004, A2 reading). Either way the header names `const struct device *` (rule 5 allows it), and it would have to be refused at compile time on every board but `native_sim`, so a product cannot bind a non-hardware device as its watchdog on the board. The target name must differ from the existing STATIC provider `crux_system_zephyr` (`components/system/ports/zephyr/CMakeLists.txt`), as File uses `crux_file_zephyr_composition`.

**Route C: the `crux-watchdog0` alias on `native_sim`.** The binding's `native_sim` branch uses `DT_ALIAS(crux_watchdog0)` when the node exists, and `NULL` otherwise (the EVKB branch stops with `#error` when its alias is missing, `system_binding.c:19-20`, so this is a new, more lenient shape). The product's overlay declares a `zephyr,counter-watchdog` node on `counter0` and the alias, and sets `CONFIG_WDT_COUNTER=y`. No Crux symbol and no Crux device code, and Zephyr's own driver is reused (AGENTS.md prefers Zephyr-native facilities when suitable). The costs are larger than they first look. **The shared provider must change**: Zephyr's counter watchdog refuses the `WDT_OPT_PAUSE_HALTED_BY_DBG` option that the provider always passes, and returns a non-zero channel number that the provider treats as an error (section 1.1, both **Verified**). So the `native_sim` build would pass different setup options and accept a non-negative channel, in code that the RT1060 build shares and whose comment says the pinned RT1060 driver has exactly channel zero (`system_zephyr.c:66-67`), and the product would have to set `CONFIG_WDT_COUNTER_CH_COUNT=1` or the provider would have to accept channel 3 and store it for the feed, which today always feeds channel 0 (`system_zephyr.c:81`). The running state has no source (the counter watchdog has no status call), so the provider would keep a private flag set when `setup` succeeds, which loses detection of an already-running owner on the simulator. `watchdog_emulated` can only be derived from the node's compatible. The alias, now spanning two boards, becomes a wider public interface. The counter watchdog's behaviour on the native-sim counter is **Not verified**.

**Route D: accept the gap.** The feed cycle and the missed feed stay covered by the Controller's Host test and the EVKB build. Issue #41's criterion is then amended on the Controller side. Nothing changes in Crux.

| Question | A | B | C | D |
| --- | --- | --- | --- | --- |
| New public symbol under Decision 4 | One Kconfig symbol, **Experimental** (a test provider with no Zephyr composition outside tests; Decision 4 lists Kconfig symbols as interface) | A header, an INTERFACE target, one or two functions, probably a symbol; tier for each | The alias meaning widens to `native_sim` (Decision 4 lists devicetree aliases as interface); no symbol | none |
| Six rules (`composition-interfaces.md`) | **Do not apply.** No composition interface is published. Rule 2 itself says Kconfig selects providers | Apply: 1 placement and name, 2 INTERFACE target, 3 guard and negative test, 4 binds a device (B1 inverts direction, B2 adds a function), 5 `const struct device *` allowed, 6 tier. B1 is outside the rules, as C3 was | Do not apply | Do not apply |
| Fail closed on other boards | CMake `FATAL_ERROR` plus `#error` (inference above) | A compile-time refusal in the header and the binding | The existing per-board `#error` and `BUILD_ASSERT` (`system_binding.c:20-30, 44`) already refuse another node on the EVKB | n/a |
| What the product writes | One line in a `native_sim`-only fragment | A Zephyr watchdog driver in its own tree. The Controller note reports its check refuses `<zephyr/drivers/watchdog.h>` everywhere (**Reported**) | An overlay of about six lines and two fragment lines (`CONFIG_WDT_COUNTER`, `CONFIG_WDT_COUNTER_CH_COUNT=1`) | nothing |
| What Crux maintains | About one source file, plus tests | A public header, target, tier, guard rule, tests | A binding branch and `native_sim`-specific setup in the shared provider, plus tests | nothing |
| Depends on an unverified fact | no | no | **yes**: the counter watchdog on the native-sim counter, after the provider change | no |
| Closes issue #41's criterion | yes | yes, but the product cannot use it | yes if the spike passes | no |

**Decision: A (S1).** It is the smallest public cost that works for the product that asked, it follows three existing `native_sim`-only precedents, it needs no devicetree and no product-written driver, and it does not rest on an unverified Zephyr behaviour. It also lets the provider know at compile time that the device is a simulation, which section 3 uses. Its weak point is that Crux owns a small simulated device where Zephyr already has a counter watchdog; but that driver cannot take the provider's call sequence as it is (section 1.1), so reusing it moves the simulator's special cases into the shared provider instead of removing them. **Alternative considered: C**, for zero new Crux symbols and upstream reuse. C's first step would be a CI-only spike that shows the counter watchdog running on the native-sim counter with the changed setup options and a channel count of 1; the answer decides C. The two do not exclude each other: the A device can be dropped later if C proves out. **Against B:** it is the most public surface for the least gain, it inverts a provider getter into a product port, and the requesting product could not use it.

## 3. What the consumer scenario can show

The consumer is an application outside this repository that links `crux::system`, includes only `<crux/system.h>`, `<crux/status.h>` and `<crux/logging.h>`, and sets the three native facilities and the A symbol in a `native_sim` fragment. The expected observations, with route A:

| Observation | Shown on `native_sim`? | How, and the limit |
| --- | --- | --- |
| Reset cause line at boot | Yes, already today | First boot reads POR from the native HWINFO (`hwinfo_native.c:85-96`). The product reads, logs, then clears once |
| Start succeeds and the state is active | Yes | `crux_watchdog_start(2000, &token)` returns `CRUX_OK`, status shows `CRUX_WATCHDOG_ACTIVE` and `watchdog_timeout_ms == 2000`. The provider's range and step (500 to 64000 ms, 500 ms steps, `system_zephyr.c:32-37`) apply unchanged, because the validation is in the shared provider |
| A feed cycle | Yes | Repeated `crux_watchdog_feed` returns `CRUX_OK` and no restart follows within several intervals. `CRUX_OK` means native acceptance (`system.h`), so the observation is "accepted and no expiry", not hardware health |
| A missed feed and its reset | Yes. With `CONFIG_NATIVE_SIM_REBOOT=y` as a restart of the simulated process, without it as the end of the process with status 1 (section 1.1) | No feed for one interval. The simulated device prints its line and calls `sys_reboot`. The contract says a Zephyr expiry is seen as a reset, never as `EXPIRED` (`spec:170-172`), so the scenario must expect the restart or the exit, not a status value |
| The second boot | Only with `CONFIG_NATIVE_SIM_REBOOT=y` | A fresh System state (idle, token gone), and the cause line reads **SOFTWARE**, not WATCHDOG |
| The WATCHDOG cause bit | **No** | The simulator's supported mask is POR and SOFTWARE (`hwinfo_native.c:45-47`), and the restart sets SOFTWARE. The product's "warning for a watchdog reset" path stays covered by its Host test with injected causes only |
| Whether the simulation is marked as one | Needs a decision | `watchdog_emulated` is `false` in the Zephyr provider (`system_zephyr.c:27-29`). The contract defines it as "a development/test simulation" (`spec` status table). See S3 |
| Hardware timer independence, WDOG1 resolution, debug pause, flag accumulation, power loss | **No** | Nothing on `native_sim` models them. A simulated expiry runs in simulated kernel time. Whether a thread that never yields still lets the timer fire was not checked (**Not verified**) |

**A simulated watchdog is not hardware evidence.** A `native_sim` pass says the product calls System in the right order and handles the answers. It makes no claim about the RT1060-EVKB, its watchdog, its reset or its reset-cause register, and no board result may cite it.

**The process restart.** The spec says "never call an actual machine reset" for `native_sim` tests (`:305`). A re-exec of a simulated target is not a reset of the host machine, but the sentence was written when the plan was a controlled fixture. S4 decides that the restart is within its intent.

## 4. Boundary test plan

The model is `tests/build/test_file_zephyr_boundary.py` (a small CMake project run against the real guard and against a weakened copy, so a rejection is not vacuous) and ADR-0004's out-of-tree fixture ([ADR-0004 section 5](0004-product-composition-of-management-services.md#5-boundary-test-plan)). The fail-closed cases follow `tests/build/test_system_composition.py`, which is environment-gated and runs `west build --cmake-only` per case.

**T1, Host, no Zephyr SDK: a consumer cannot reach the private seam.** On the model of the boundary guard of section 1.2 (its full table is in the [history record](../history/adr-0005-record.md)), fixed as a test: a consumer target that adds `components/system/ports/zephyr` or `components/system/src` is refused, and the public include root is accepted. This part passes at the baseline (**Verified** by the probe) and runs on macOS. It needs no change to the guard.

**T2, Host: the link-time wrap is refused.** The probes of section 1.2 show that only the two seam names are refused, by accident. A wrap of `z_impl_hwinfo_get_reset_cause` or `sys_reboot` is accepted. So a test that says "a link-time wrap of a System seam is refused" passes for two symbols and fails for the rest. Two options: (i) extend the guard with a narrow rule that refuses `-Wl,--wrap=` of any symbol that begins with `crux_` or `__wrap_crux_`, which catches the seam by identity and leaves a product's own wraps of Zephyr symbols alone; (ii) refuse every wrap on a consumer target, which is simple and may flag Crux's own fixtures (`tests/system_consumer/consumers.cmake:15` calls the guard on its consumer targets, `tests/system/zephyr` does not, and the rest was not traced: **Not verified**). The guard is a protected path, so it is a separate approved change (S6). Each case also runs against a weakened guard and must then pass, as the File test does.

**T3, native_sim, Zephyr shard: an out-of-tree consumer shows the three behaviours.** A fixture project copied outside the repository (as `tests/build/test_external_application.py:19` asserts with `assertNotIn(REPO, source.parents)`), built with `-DZEPHYR_EXTRA_MODULES=<repo>` as `scripts/test-product-template.sh` does for the template. It uses public targets only. Build assertions: every `-I` of its sources is a public include root; the generated `.config` has the A symbol, `CONFIG_BOARD_NATIVE_SIM` and `CONFIG_NATIVE_SIM_REBOOT`; the ELF contains the simulated device only when the symbol is set. Run assertions, in order, on the console: the cause line (POR), the start line, several feeds, the simulator's expiry line and the host's restart warning, then the cause line again with SOFTWARE and a fresh active state. Twister's handling of a re-exec is **Not verified**; if it does not hold, the fixture runs the binary directly and the fixture script reads its output.

**T4, negative cases that must fail** (configure or compile, with a message):

| Variant | Must fail because |
| --- | --- |
| The A symbol set for `mimxrt1060_evk@B//qspi` | the configure error of the component, or the `#error` of the binding |
| The A symbol set for another board that System does not support | the configure error, before the existing "unsupported Zephyr board" `#error` |
| The A symbol set with `CONFIG_WATCHDOG=n`, or with a refused native owner such as `WDT_SHELL` | the existing checks (`CMakeLists.txt:9-20`) still fire first |
| The fixture adds `-I components/system/ports/zephyr`, or includes `system_zephyr.h` | a private header (T1 refuses the path; without the path the header is not found) |
| The fixture adds `-Wl,--wrap=crux_watchdog_zephyr_device` | T2 (refused today by the name) |
| The fixture adds `-Wl,--wrap=crux_system_probe` (any `crux_` symbol) | T2 once the guard rule of S6 exists. A wrap of a Zephyr symbol such as `sys_reboot` is accepted on purpose (S6 leaves a product's own wraps alone) |
| The A symbol is set and `CONFIG_NATIVE_SIM_REBOOT` is forced off (only if S5 chooses the select) | the Kconfig assignment mismatch. If it does not fail, the run-time case below ends with status 1 and the scenario reports it |

On a board other than `native_sim`, a symbol that the A symbol selects (`NATIVE_SIM_REBOOT` exists only inside the native_sim Kconfig, **Inference** from the pin's `boards/native/native_sim/Kconfig`) may raise a Kconfig warning before the configure error fires. The tests assert the failure and the symbol name, not which line fired first.

**T5, provider absent by default.** On `native_sim` with the symbol off, the binding returns `NULL` and the System status is `CRUX_ERR_NOT_SUPPORTED` and `CRUX_WATCHDOG_UNAVAILABLE`, as `tests/integrated_smoke/zephyr/main.c:425-431` expects; no simulated device appears in the ELF. This keeps every existing test unchanged (**Inference**: the symbol is off in them, and their link-time wraps of the two binding functions are untouched because they are in a separate translation unit from the callers).

**Where it runs.** T1 and T2 in the Host job. T3 to T5 in a Zephyr shard next to the System run in `.github/workflows/zephyr.yml` (`./scripts/test-system.sh`, the runtime shard). The Zephyr parts run in CI.

## 5. The possible reset loop

Controller's note (friction 7, **Reported**): the watchdog is armed before the workload starts. If the workload start fails, or the producer thread exits on a clock error, nothing feeds, the board resets, and because the policy never stops the start after a watchdog reset, it arms again and keeps resetting.

What Crux guarantees, **Verified**: one activation per boot, a failed or uncertain start cannot be retried (`system.c:196-203`), and there is no stop or rearm (`system.h:22`). There is no boot journal (`spec:201`). On the RT1060 the cause flags may accumulate across resets (the spec says "Multiple flags may accumulate across resets", `:197`, as a general statement; I found no RT1060-specific source for it, and M3 physical evidence at `:19` records only a watchdog cause of `0x10` (**Reported**)). Nothing here ran on a board, and this record runs none.

| Option | What it does | Cost |
| --- | --- | --- |
| L1, accept and bound | Any board run is supervised and time-limited, with the operator able to cut power. The product documents the loop | No code. The loop stays possible in the field |
| L2, arm after the workload has started | A start that fails never arms | A short unprotected window at boot. It does not cover a workload that dies after arming |
| L3, a product-side loop guard | The product counts watchdog-cause boots in its own storage and, above a limit, does not arm and enters a safe state | The product needs persistence and a safe-state design. This is product policy. `native_sim` can test it, because the simulated flash disk keeps its contents across the process restart (`zephyr/Kconfig`, `CRUX_FILE_FATFS_SIMULATOR` help) |
| L4, a Crux boot journal or a disarm call | Crux breaks the loop | Contradicts the accepted contract (single activation, no stop, no journal) and adds public API. Not proposed |

**Decision: L1 now, and L2 with L3 as product decisions** that the consumer records. Crux changes nothing in code. A docs-only note in the System documentation states that arming order and loop policy belong to the product (S7). **Alternative considered:** L2 alone, with no persistence in the product. On `native_sim` the scenario of section 3 shows the loop with no extra work: a fixture that never feeds restarts forever until the test timeout. The scenario must therefore tell the second boot apart (by the SOFTWARE cause) and feed on it, or the test never ends.

## 6. Interaction with ADR-0004 and the frozen headers

- **Phasing.** ADR-0004's phase 0 integrates the service cores into the module under Kconfig. System is already integrated (`zephyr/Kconfig:223`, `zephyr/CMakeLists.txt:108-111`), so this proposal does not wait for phase 0 and blocks none of phases 1a to 3. It is independent of ADR-0004's decisions C1 to C9. **Inference:** it can land as its own small change.
- **The fixture.** ADR-0004's T3 fixture is an out-of-tree `native_sim` consumer built like the product template. The System scenario should reuse that mechanism (S8). It needs none of the web, credential or Access targets, so it can ship first and ADR-0004's fixture can absorb it later.
- **Frozen headers.** `<crux/system.h>` includes none of `crux/thread.h`, `crux/sync.h`, `crux/queue.h` or `crux/serial.h` (**Verified**, section 1, row 10), and the System component needs none of their Kconfig symbols (row 11). Route A adds no header. Route B would add one, and it would have to stay free of them. The consumer scenario's own check (the template's `check_domain_includes.py --product`, **Reported** by ADR-0004) would still refuse them.
- **Related.** The reboot service reaches the System reset through `crux::system` (ADR-0004, hook table). A `native_sim` restart that works would let a later reboot scenario run there too (**Inference**; not part of this proposal).

## Follow-up changes

None is part of this record. Each is its own reviewed change, and a change on a protected path needs approval of that change (S9). Items 1 to 6 are done: the Kconfig symbol `CRUX_SYSTEM_NATIVE_SIM_WATCHDOG` with the simulated device (item 2), `watchdog_emulated` for that symbol (item 3), the guard rule and its tests (item 4), the out-of-tree fixture with `scripts/test-consumer-system.sh` (item 5) and the note in [System validation](../system-validation.md) (item 6). Item 7 belongs to the consumer.

1. This record's acceptance or rejection, and the `docs/decisions/README.md` row. **Protected:** none.
2. Route A: the Kconfig symbol in `zephyr/Kconfig`, the CMake check, the private simulated device and the binding branch under `components/system/ports/zephyr/`, with T5 and the unit tests first. **Protected:** none expected (`zephyr/` and `components/` are not on the list).
3. The `watchdog_emulated` change, if S3 is accepted: it changes two existing assertions (`tests/system/zephyr/src/main.c:188` and the `m5_integrated` expectation) only for the new symbol. Needs the owner's explicit yes.
4. T1, T2 and T4 as Host and configure tests under `tests/build/` (not protected). The guard rule of S6 in `cmake/CruxConsumerBoundary.cmake` (**protected**).
5. The out-of-tree fixture and T3: new files under `tests/` and a Zephyr shard entry in `.github/workflows/zephyr.yml` (**protected**) or a new script `scripts/test-consumer-system.sh` (a new check script may be added within the task).
6. A docs note on arming order and loop policy (S7). **Protected:** none.
7. On the Controller side, a pin move to a Crux revision that holds the change, and the scenario that closes issue #41. Those are the Controller's decisions, not Crux's.

<a id="the-owners-decisions"></a>

## Decided

| # | Decision |
| --- | --- |
| S1 | Route A: a `native_sim`-only simulated watchdog that the Zephyr module provides and one Kconfig symbol selects, with a configure error on any other board |
| S2 | Crux adds one Kconfig symbol for it, at tier Experimental, with a name that says `native_sim` and test only: `CRUX_SYSTEM_NATIVE_SIM_WATCHDOG` |
| S3 | `watchdog_emulated` is `true` only when the simulated device of the A symbol is bound |
| S4 | The `native_sim` process restart on a missed feed is allowed under the System spec's "never call an actual machine reset" |
| S5 | The simulated device prints one line and then calls `sys_reboot`, and the A symbol selects `NATIVE_SIM_REBOOT` |
| S6 | A narrow rule in the consumer guard refuses `--wrap` of `crux_`-prefixed symbols, as its own protected-path change |
| S7 | A docs-only note says that arming order and loop policy belong to the product |
| S8 | The System scenario uses the out-of-tree fixture mechanism of ADR-0004 and ships first on its own |
| S9 | Protected-path changes are approved per follow-up change |

This record authorises no hardware operation. Each follow-up under [Follow-up changes](#follow-up-changes) is its own reviewed change, including for every protected path that it touches ([the convention](README.md#convention)).

The drafting record, measurements and approval history are in [history/adr-0005-record.md](../history/adr-0005-record.md).
