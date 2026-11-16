# Board-name refusals in Crux's Zephyr ports: inventory and options (proposal)

| Field | Value |
| --- | --- |
| Status | **Proposed.** Eight numbered decisions, each **Open (proposed)**. Nothing in this file is adopted, and no owner approval is recorded for any option. |
| Date | 16 November 2026 |
| Baseline | `origin/main` at `164b0428f56a7c35bcd6c24a90e09b136f2f2d00` |
| Author | Claude Code. First version by model `claude-sonnet-5-5`; revision after the independent review by model `claude-opus-5-5`. Independent review: `REVISE` at `cad54be0`, see the pull request |
| Origin | The owner approved a proposal only, on 16 November 2026 at 19:24:48 UTC in the Crux Pilot session chat ("추천안대로 진행", "proceed as recommended"). The change itself waits for the owner's decision after reading this file |
| Scope | Documentation only. This file adds no code, Kconfig symbol, CMake rule, test or script, edits no existing file, and needs no hardware, tag or new dependency. No build, Docker command or `west update` was run for it. `docs/plans/` is excluded from the link check as completed or historical (`doc-links.toml:20-22`), so the links of this file were checked by hand when it was written |

**Labels.** **Verified in source** means read in a file of this repository at the baseline, or in the local Zephyr `v4.4.0` tree (the repository pins v4.4.2; I did not compare the two). **Inference** is my reading of the code or of Zephyr's board model: nothing was configured or built. **Not verified** means no read or run exists. The evidence levels E1 to E4 are those of [Component readiness](../component-readiness.md#readiness-table): Host test, `native_sim`, EVKB build, physical board.

## Summary

- **Four Crux Zephyr ports key on the board name:** System, Logging, Serial and File on FatFs (inventory in section 3). A product whose board has its own name, even with the same SoC as the RT1060-EVK, stops at a `#error` in System, at a `BUILD_ASSERT` in Logging and Serial, and cannot select the FatFs symbols. GPIO, I2C, SPI, Time, Netif and the Reliance Edge File provider do not look at the board.
- **None of the checks tests hardware.** Each tests a name, and then devicetree labels and an address that come from the SoC file `nxp_rt10xx.dtsi` (`wdog0` at `0x400b8000`, `lpuart1`, `lpuart3`), which every RT10xx board includes. What the binding calls "qualified" is a SoC resource at build level (E3). Only File on the microSD has a physical run (E4, one board, one card).
- **The name check can be passed without the hardware.** A `board: extend:` variant keeps the existing board name, so `CONFIG_BOARD_MIMXRT1060_EVK` stays set and System, Logging and Serial accept it today (section 4). The refusal therefore gives an honest team trouble and gives no assurance about the hardware.
- **Recommendation: option A, in its narrow form.** Replace the board symbol by the SoC symbol `CONFIG_SOC_MIMXRT1062` plus the devicetree checks that already exist, for System and Logging only. For Logging, other RT1062 boards may use any enabled LPUART, while the EVKB stays at LPUART1 as reviewed (D3). Add no Kconfig symbol, rename none, leave Serial (frozen) and the FatFs microSD selections (E4 evidence of one board) alone. On the EVKB the preprocessor conditions evaluate as before, so the image and its configuration hash are expected to stay as they are. That expectation is checked by a before-and-after comparison and by the reference controller's own pin-move evidence (section 6).
- **Alternative: option B** (the product supplies its own binding) if the owner prefers that each product carries its own claim. It adds public composition interfaces and, for Logging, changes the S2 configuration hash by construction (section 6). **Option C** (document only) leaves the `extend` route as the only way and must say what it costs.
- **Decisions needed:** D1 to D8 in section 8.

## 1. The problem and who it blocks

A product team that starts a repository for its own board (a custom board with an i.MX RT1062 and its own board name) meets this before it writes a driver. The porting guide says so in plain words: the System, Serial, Logging and FatFs rows "refuse your board with a compile error until the source changes" and a change to any of them is "a design change to Crux" ([guide, 3.3](../porting-to-a-new-board.md#33-kconfig-and-devicetree), lines 77-84). So today the team has three choices: ask for a Crux change for each component, replace the port outside Crux, or use `board: extend:` and inherit the EVKB's claims (section 4).

Who is blocked: any product that has its own board name and wants Crux System (watchdog and reset cause) or Crux Logging. A second case already exists in the repository: the [RT1170 review](../rt1170-evk-a1-feasibility.md#crux-integration-gaps) found that System "rejects every board other than RT1060-EVK and native_sim outright with a build error, before any watchdog address check". The owner set the RT1170 aside, so that case never needed a decision. This proposal is limited to boards with the SoC that Crux was built for (`SOC_MIMXRT1062`), and it does not widen to other SoCs.

## 2. What the refusals protect

Five kinds of check sit behind the symbol, and the right option differs for each:

| Code | Meaning |
| --- | --- |
| Q | A **qualified resource claim**: the binding was reviewed and built for this resource, and says so |
| S | A **safety property** of the composition: single owner of a UART, an explicit watchdog selection, no unqualified provider in an image |
| M | A **missing abstraction**: the code needs something that Zephyr's own API does not give, so it uses a vendor HAL call tied to one IP |
| T | A **test-only guard**: a test setting that must never reach a real board |
| D | **Data keyed to a board**: files that carry one board's addresses |

## 3. Inventory

### 3.1 Refusals and constraints that name a board or a board resource

"Custom board" means: a board with a name that is not `mimxrt1060_evk`, the SoC `mimxrt1062`, and the aliases and chosen nodes that the component asks for. Every cell in that column is an **Inference** from the code: I did not configure such a board. Of the 14 checks, 11 refuse or constrain a board or a board resource. I2, I6 and I14 refuse no board; they are listed because they sit in the same code and stay under every option.

| # | File:line | What it checks | Protects | Custom board, same SoC, own name | In the guide's table? |
| --- | --- | --- | --- | --- | --- |
| I1 | [`system_binding.c:37`, `:62-63`](../../components/system/ports/zephyr/system_binding.c) | `CONFIG_BOARD_MIMXRT1060_EVK` selects the one hardware branch. Any other board that is not `native_sim` reaches `#error "Crux System unsupported Zephyr board"` | Q | Stops at the `#error` before any alias is read | Yes (row at line 81) |
| I2 | `system_binding.c:38-41` | The `crux-watchdog0` alias exists and is enabled | S | Would pass if reached. The rule does not depend on the board | Partly: the paragraph at line 112 names the alias, the table does not |
| I3 | `system_binding.c:43`, `:47-50`, `:59` | The alias is the node labelled `wdog0`, compatible `nxp,imx-wdog`, `reg` `0x400b8000`. The running state is read with the vendor HAL (`fsl_wdog.h`, `WDOG_GetStatusFlags` on the register address) | Q for WDOG1 and M for the read (Zephyr's watchdog API has no running-state query: **Inference** from the API as I know it; the RT1170 review says the Zephyr driver itself uses the same HAL call) | Would pass. The label, the compatible and the address come from `dts/arm/nxp/imxrt/nxp_rt10xx.dtsi:1001-1003` of the Zephyr tree (**Verified in source**), shared by RT1010 to RT1064. The assert does not tell an RT1062 from an RT1064 | Yes |
| I4 | [`system/.../CMakeLists.txt:1-3`](../../components/system/ports/zephyr/CMakeLists.txt) | Configure error when the board is the EVK and `BOARD_REVISION` is not `B` | Q (revision B is the one built) | Never fires: the symbol is false | The row says "on Rev B". The Logging twin (I8) is not listed |
| I5 | [`logging_binding.c:12-21`](../../components/logging/ports/zephyr/logging_binding.c) | The log UART is `lpuart1`, compatible `nxp,lpuart`, and the board is the EVK (`TARGET_UART`). Otherwise `BUILD_ASSERT` "Crux Logging unsupported UART resource" | Q | The assert fails, even when the log UART is `lpuart1` | Yes (line 74 and the "As above" row) |
| I6 | `logging_binding.c:22-29` | 115200 baud, no parity, one stop bit, 8 data bits, no flow control, no single-wire or RS-485 mode, no enabled child node | S | Decided by the board's devicetree, not by its name. Board-neutral | Partly: line 74 lists the mode |
| I7 | `logging_binding.c:31-43` | If `zephyr,console` is set and `CONFIG_UART_CONSOLE` is on: on the EVK the log UART may be the console UART when Logging-only routing holds (the comment gives the reason, the native UART backend needs `UART_CONSOLE`); on any other board the console UART must not be the log UART (`REJECT_OWNER`, "conflicts with UART Console") | S (one owner per UART) | Still refuses after I5 is relaxed, for the usual case that the console and the log UART are the same node | Partly: line 74 says the RT1060 "may share". It does not say that every other board is refused |
| I8 | [`logging/.../CMakeLists.txt:2-4`](../../components/logging/ports/zephyr/CMakeLists.txt) | As I4, for Logging | Q | Never fires | **No** |
| I9 | [`serial_binding.c:10-20`](../../components/serial/ports/zephyr/serial_binding.c) | The Serial UART is `lpuart3`, compatible `nxp,lpuart`, and the board is the EVK. Otherwise "Crux Serial unsupported UART resource" | Q | The assert fails | Yes (line 75) |
| I10 | `serial_binding.c:53-57` | `#error "LPUART3 Serial pins conflict with enabled EVKB CSI"` when the Serial node is `lpuart3` and the node labelled `csi` is enabled | S, from an EVKB pin conflict | Keyed on SoC labels, not on the board. It would fire on any board that enables `csi` and puts Serial on `lpuart3`, whether or not the pins collide there | **No** |
| I11 | [`file_native.c:25-33`](../../components/file/ports/zephyr/file_native.c), [`file/.../CMakeLists.txt:78-85`](../../components/file/ports/zephyr/CMakeLists.txt), [`zephyr/Kconfig:334-337`](../../zephyr/Kconfig) | The RAM-disk selection `CRUX_FILE_FATFS_RT1060_RAM_DISK` needs the EVK, `SOC_MIMXRT1062`, the target symbol `BOARD_MIMXRT1060_EVK_MIMXRT1062_QSPI`, `BOARD_REVISION_B`, and the disk-driver settings | Q (the bench image) | The Kconfig symbol is not offered. A line that sets it is dropped, which Zephyr reports as an error (**Inference** from Zephyr's Kconfig step) | Yes (line 83) |
| I12 | `file_native.c:35-41`, `CMakeLists.txt:25-34`, `:60-62`, `zephyr/Kconfig:314-317`, `:351-354` | The same board, SoC, qualifier and revision symbols for the microSD provider `CRUX_FILE_FATFS_RT1060` and its compile check | Q: the one physical slice (E4: one board, one card), and the Kconfig help says it "qualifies neither the board, the card" nor the Settings backend | As I11 | Yes (line 83) |
| I13 | `file_native.c:42-45`, `CMakeLists.txt:127-130` | With no File selection that is a simulator, a real board gets `#error "File provider requires an approved simulator composition"` | S (no unqualified native provider in an image) | The same stop for a board that selects nothing | Partly: line 83 names the simulator selections |
| I14 | `file_native.c:46-53` | `CONFIG_SDHC` with `CONFIG_DCACHE` needs `SDHC_BUFFER_ALIGNMENT` of at least the cache line | S (DMA and D-cache) | Board-neutral (symbols only). Not a refusal of a board | Not listed, and need not be |

### 3.2 Guards that refuse a test setting on every real board (T)

These use `CONFIG_BOARD_NATIVE_SIM` to keep a test setting out of a real image. They do not stand in the way of a custom board and no option changes them: `CRUX_SYSTEM_NATIVE_SIM_WATCHDOG` (`zephyr/Kconfig:284`, `native_sim_watchdog.cmake`, `system_binding.c:5-7`, `system_sim_watchdog.c:10-11`); `CRUX_FILE_SIMULATOR` and `CRUX_FILE_FATFS_SIMULATOR` (`zephyr/Kconfig:297-306`); `CRUX_WEB_PLAIN_HTTP_FOR_TESTS` (`zephyr/Kconfig:490-492`, `web_session.c:410-411`); the Settings simulator rule (`configuration_settings.c:19-21`); the test random generator rule of the four PSA ports (`credential_psa.c:20`, `access_psa.c:16`, `web_session_psa.c:14`, `tls_certificate_psa.c:19`); `CRUX_EMMC_FLUSH_CONTROL` (`zephyr/fs/reliance_edge/CMakeLists.txt:13`); `CRUX_SETTINGS_FILE_CONTROL` (`zephyr/CMakeLists.txt:150-151`, "a native_sim test fixture setting"); and `CRUX_PSA_THREADING_TEST_COUNTER` (`zephyr/psa_threading/CMakeLists.txt:19-20`).

How the list was found: a search of `components/` and `zephyr/` for `BOARD_NATIVE_SIM` and `CONFIG_BOARD_`, read case by case. `tests/`, `samples/`, `templates/` and `cmake/` were not searched for guards, so the list is complete for those two folders only.

### 3.3 Board data that is not a refusal (D)

`zephyr/boot/boards/mimxrt1060_evk_mimxrt1062_qspi_B/` holds the four boot files with the RT1060's addresses (`0x2027ff00`, `0x80000000`). Nothing refuses another board: the directory name is passed on the command line, and [`scripts/test-boot-composition.sh:24`](../../scripts/test-boot-composition.sh) hard-codes it. The guide covers it in [section 3.5, item 2](../porting-to-a-new-board.md#35-secure-boot-composition): a product keeps its own four files. No option here touches it.

### 3.4 Ports that already accept any board

- **GPIO, I2C, SPI** select their resource by an alias (`crux-gpio0`, `crux-i2c0`, `crux-spi0`) and check status and properties: `gpio_binding.c:10-25`, `i2c_port_zephyr.c:9-17`, `spi_port_zephyr.c:8-24`. This is the pattern of option A, already in the repository.
- **File on Reliance Edge** has no board check: `file/.../CMakeLists.txt:101-125` and the help text of `CRUX_FILE_RELIANCE_EDGE` (`zephyr/Kconfig:371-373`, "works on any board that has the file system").
- **Time** (RTC through the `rtc` alias, `time_rtc_zephyr.c:35-40`; busy wait through properties of the timer, `time/.../CMakeLists.txt:49-54`), **Netif** (`netif_zephyr.c`, nothing board-specific), Thread, Sync, Queue, `service_priority`, CLI and SSH test properties of the configuration, not the board.

### 3.5 Gaps in the porting guide

1. The table does not list the revision refusal of Logging (I8) or the CSI `#error` of Serial (I10). Its "Logging, Serial: As above" row hides both.
2. It does not say that Logging refuses console sharing on every board other than the EVK (I7).
3. It does not mention `board: extend:` at all (a search of the tree outside `.git` and `.claude` finds no use of the word, `extend:`, or a board extension). Section 4 says why it should.

## 4. The `board: extend:` route, which exists today

Zephyr's board model lets a repository extend an existing board with a new variant. The extension keeps the existing board name ([`doc/hardware/porting/board_porting.rst:943-960`](https://github.com/zephyrproject-rtos/zephyr/blob/v4.4.0/doc/hardware/porting/board_porting.rst) at `v4.4.0`: the skeleton is `extend: <existing-board-name>`, and "Replace `plank` with the real name of the board you extend", **Verified in source**). Zephyr defines the Kconfig symbol `BOARD_<BOARD>` from the board name that the build uses, and `BOARD_<BOARD>_<QUALIFIERS>` from the full target (`boards/Kconfig.v2:5-13`, **Verified in source**). So, **by inference**, a build for a variant of `mimxrt1060_evk` has `CONFIG_BOARD_MIMXRT1060_EVK=y`, and:

| Component | Result on an extended EVK board (Inference) |
| --- | --- |
| System | Accepted, if the alias selects `wdog0` and the revision is `B`. The EVK's default revision is `C` (`boards/nxp/mimxrt1060_evk/board.yml`, **Verified in source**), so the team has to ask for `@B`. At `C` the System and Logging CMake rules stop (I4, I8). By choosing `@B` the team takes on the claim "Rev B" for hardware that is not an EVKB |
| Logging | Accepted for `lpuart1`, and the console-sharing exception of I7 applies |
| Serial | Accepted for `lpuart3` |
| File on FatFs | Still refused. The target symbol `BOARD_MIMXRT1060_EVK_MIMXRT1062_QSPI` is not the symbol of a variant target, which carries one more qualifier segment, so I11 and I12 fail. A team could still define that symbol in the extension's own `Kconfig`, which Zephyr allows (`board_porting.rst`, the list of optional extension files). The board symbols are names, and a name can be defined |
| File on Reliance Edge | Accepted, as on any board |

**The risk.** An extension does not carry a signal that the hardware differs from the EVKB. The team inherits, without anyone deciding it, the claims that Crux attaches to the EVKB: the "qualified RT1060 WDOG1 resource" (I3), the "qualified" LPUART1 and LPUART3 resources (I5, I9), the LPUART1 console-sharing exception (I7) and Rev B (I4, I8). The EVK's `Kconfig.defconfig` applies as well, and the variant's devicetree normally builds on the EVK's (**Inference**). Those claims may not be true for the team's board: the UART's pins and driver chip, how the watchdog reset reaches the rest of the board, the flash part and the boot header, the memory map. Crux's own evidence for these three components is E3, so the claims are already build-level. The risk is not that a physical result is lost. It is that readers of the guide, the readiness table and the error messages will take "accepted" for "this board is qualified", on hardware that nobody compared with an EVKB.

This route exists today and is independent of the options below. Whatever the owner decides, the porting guide should name it, say that it inherits the EVKB's claims and that it is no route to a qualification (D6).

## 5. Options

### Option A. Accept a board by its SoC and its devicetree, keep the qualification asserts for known silicon

**What changes.** In the System and Logging bindings, the condition `defined(CONFIG_BOARD_MIMXRT1060_EVK)` becomes `defined(CONFIG_SOC_MIMXRT1062)` (the symbol that `zephyr/Kconfig:316` already uses). The devicetree assertions stay: for System, label `wdog0`, compatible `nxp,imx-wdog`, address `0x400b8000`; for Logging, compatible `nxp,lpuart`, the mode checks of I6 and every owner-conflict check. The two `CMakeLists.txt` revision checks stay keyed to the EVK, where they are true today: a custom board has no EVK revision to check. The error text says what is checked, "unsupported SoC or watchdog resource" in place of "unsupported Zephyr board". The existing diagnostics that tests match on stay unchanged for the cases that exist today.

Three sub-choices, each its own decision:

- **A1, same resources, any board (System: WDOG1; Logging: `lpuart1`).** Narrowest. It unblocks a board that logs on LPUART1 and refuses one that logs elsewhere. A real RT1062 board in Zephyr does not: `mimxrt1062_fmurt6` (own name, SoC `mimxrt1062`) has its console on `lpuart7` (`boards/nxp/mimxrt1062_fmurt6/mimxrt1062_fmurt6.dts:37`, **Verified in the local v4.4.0 tree**, not at the pin).
- **A2, for Logging the resource class (any enabled `nxp,lpuart` node on that SoC).** The checks in I6 and the owner rules are properties of a node, so they apply to any LPUART as they do to LPUART1. Two things are not covered by them:
  1. **A2 also widens what the EVKB accepts.** On the EVKB, Logging would then build on any enabled LPUART, not only on the reviewed `lpuart1`.
  2. **Pin conflicts are board facts, not node properties.** The only pin rule in these ports is Serial's: `serial_binding.c:53-57` refuses `lpuart3` when `csi` is enabled ("LPUART3 Serial pins conflict with enabled EVKB CSI"). Logging has no such rule. Under plain A2, Logging on `lpuart3` with `csi` enabled would build on the EVKB, while Serial refuses the same pins.

  So A2 comes in two forms. **A2a:** carry the CSI rule into Logging, and accept any LPUART on every RT1062 board, the EVKB included. It covers the one EVKB pin conflict that a review found; no review looked at the EVKB pins of the other LPUARTs. **A2b:** keep the EVKB at `lpuart1`, as reviewed, and apply A2 to other RT1062 boards only. The board symbol then only narrows the EVKB, and refuses no other board. On a product's board, pin conflicts are the product's to review in its own devicetree, and the guide says that Crux checks none. **Recommended: A2b** (D3), because it changes nothing that the EVKB accepts and needs no new review of EVKB pins. On either form the claim stays E3, and no physical output has been seen on any LPUART ("Physical output unverified", [readiness table](../component-readiness.md#readiness-table)).
- **A-wide, any SoC with the compatible.** Not recommended. The System read uses `fsl_wdog.h` and an address, and another vendor needs another read (M).

The console-sharing exception (I7) is keyed in the same way: on the SoC, with the conditions that already stand in the file (`LOG_PRINTK` on, `STDOUT_CONSOLE`, `CONSOLE_HANDLER`, `CONSOLE_SUBSYS`, `EARLY_CONSOLE` and `SHELL` off). Those conditions are about the Console's inertness, not the board. That the pinned UART backend and Console behave the same for another RT1062 board is an **Inference** (D4).

**Left alone, on purpose.** Serial (I9, I10) is frozen for new product code ([Choosing an API](../choosing-an-api.md#frozen-for-new-product-code-thread-sync-queue-and-serial)): accepting more boards would be a new feature on a frozen component. File on FatFs (I11, I12) stays named after the EVKB: its evidence is one board and one card, and a custom board needs no `CRUX_FILE_FATFS_RT1060*` symbol when Reliance Edge, which already accepts any board, is its medium.

**Effect on the EVKB path.** The conditions are preprocessor text in two translation units. On the EVKB they evaluate to the same truth values, and the `BUILD_ASSERT`s produce no code. There is no new Kconfig symbol. Expected: the image bytes and the configuration hash do not change. That is an expectation, to be shown (section 6).

**Interface and tier.** No new Kconfig symbol, alias or header. System and Logging are Experimental in the provisional readiness table ([ADR-0001, 4.1](../decisions/0001-application-boundary-and-api-stability.md#41-tiers): "may change in any release, listed in the release notes"). The change rules of ADR-0001 4.2 apply to Unstable and Stable interfaces; an Experimental one needs only a release-note entry, which today means its PR, since no release exists. Rules 1 and 4 are applied here by analogy: accepting more boards adds and takes nothing away (rule 1, add, do not change), and since the guide documents the refusal, "a change to a documented guarantee is a change even when the signature stays" (rule 4). The Kconfig symbols and aliases that exist keep their names and meanings. The error text is not interface, and the binding source is Internal (ports are Internal in the ADR).

**Tests needed (red at the base).**
1. A compile-only build test with a **fictional board that has its own name**, in the style of `tests/build/test_system_composition.py`: `west build --cmake-only` against the test application, then `cmake --build --target crux_system_zephyr` (and the Logging library). The fixture is an out-of-tree board root under `tests/`: `board.yml`, `Kconfig.<name>`, a devicetree that includes the SoC file, a defconfig, and the aliases and chosen nodes, about five small files, copied down from the EVK's directory (**Inference**: not built; the EVK directory lists these files, plus `dcd/`, `xip/` and `board.cmake`, which a configure-only test may not need). At the base the test is red: System stops at the `#error` of I1, Logging at the assert of I5. After the change it is green.
2. Negative cases on the same board stay red after the change: the alias on `wdog1` (the existing `evkb_wrong` case, run on the fictional board), a log UART whose compatible is not `nxp,lpuart`, a flow-control property, a second owner of the UART, and a board with another SoC. For the last, the in-tree `mimxrt1064_evk` is a ready witness (**Inference**: that its `--cmake-only` configure works with the aliases added is not shown). The in-tree RT1062 board `mimxrt1062_fmurt6` can be a second positive witness, on top of the fictional one and not instead of it, under A2 only (its UARTs are not `lpuart1`). It needs overlays: its console, shell and `zephyr,uart-mcumgr` are all on `lpuart7` (`mimxrt1062_fmurt6.dts:33`, `:37`, `:38`), so Logging on `lpuart7` meets the owner rules unless the test moves those chosen nodes or leaves their Kconfig options off. It is in the local v4.4.0 tree only, as far as I checked.
3. Every existing case of `test_system_composition.py`, `test_logging_composition.py` and `test_serial_composition.py` stays as it is and stays green.
4. The identity comparison of section 6.

**Documentation changes.** The guide's table and bullets (section 3.3 of the guide) for System, Logging and Serial, with the gaps of section 3.5 closed; the `extend` paragraph of section 4 (also needed by C and B); the help of `CRUX_SYSTEM` and `CRUX_LOGGING` if they name the board; the readiness rows if they name "RT1060" where they now mean the SoC. Wording rule: **accepted is not qualified**. A custom board that passes the compile check has E3 for a fictional board and nothing else.

**Effort.** M. Two bindings of a few lines each, the fixture board and its test (the larger share), the guide and the readiness rows, and the identity comparison. A2 adds a small test case. The change touches no protected path in `AGENTS.md` except where the new test is wired in: a test-runner edit is covered by the approved work package, a workflow step needs its own approval (D8).

**Risks.**
- A custom board passes a build and runs on hardware where nothing was checked. The claim stays E3, and the guide has to say so (the wording rule above).
- The SoC symbol is as coarse as the board symbol was fine. `SOC_MIMXRT1062` covers every RT1062 board, including ones whose watchdog reset is not wired as on the EVKB. The assert on the WDOG1 address cannot see that. This is the same blindness as the `extend` route, with less ceremony.
- A2 admits LPUARTs that no one has seen output on. Under A2a it also admits them on the EVKB, where only the CSI conflict of `lpuart3` was ever reviewed; under A2b the EVKB stays as it is.
- On a product's board, Crux checks no pin conflict under any form of A. A UART that shares pins with another enabled peripheral builds. The guide has to say that pinmux review is the product's.
- The hidden dependency of I7: if the UART backend or Console differs for another board's driver configuration, the exception could allow dual ownership. The retained conditions are the guard.

### Option B. Keep the refusal, and let the product supply the port

**What changes.** The seam already exists privately: `crux_watchdog_zephyr_device()` and `crux_watchdog_zephyr_running()` for System, `crux_log_zephyr_device()` for Logging, `crux_serial_zephyr_device()` for Serial. The System source says that tests already substitute at that seam (`system_binding.c:24-25`). Option B makes it a supported one: a new Kconfig symbol per component that selects "the binding comes from the product" and leaves out `system_binding.c` and `logging_binding.c`, and a public composition header that declares the functions, in the way of `crux::file_zephyr` ([ADR-0001, Decision 2](../decisions/0001-application-boundary-and-api-stability.md#decision-2-where-zephyr-is-allowed-and-how-that-is-enforced)). The product then writes the binding for its own board, and with it the claim.

**The cost that is easy to miss.** The owner-conflict checks of Logging (I6, I7 and the rules at `logging_binding.c:29-58`) live in the same file as the board check. If the product replaces the file, those checks go with it. B therefore needs them split out into a shared file that both routes compile, which is a refactor of the file that S2 compiles.

**Effect on the EVKB path.** The default stays the in-tree binding. A new Kconfig symbol that depends on `CRUX_LOGGING` is visible in an image that selects Logging, and the firmware identity of S2 includes the hash of the normalised `.config`, which keeps `# CONFIG_X is not set` lines (`scripts/record-build-provenance.py:170-190`, **Verified in source**). So **B changes the S2 configuration hash by construction**, even when `zephyr.bin` does not change. A symbol that is hidden may not appear in the file: I did not check. B therefore needs a new S2 identity as evidence, or a symbol shape that I would have to confirm by a build.

**Interface and tier.** New Kconfig symbols and one composition header per component, each a new public interface (Experimental, ADR-0001: Kconfig symbols are interface). More surface than A. ADR-0001 points both ways, and both should be weighed:
- **For B.** Decision 2 makes the composition interface "the one formal way for composition code to reach a Crux provider", and says that "a missing composition interface is a Crux gap". [Decision 3](../decisions/0001-application-boundary-and-api-stability.md#decision-3-what-crux-will-and-will-not-abstract) lists composition interfaces among what Crux will provide. A product that must bind its own watchdog or UART to System or Logging has no formal route today, and B gives it one.
- **For A.** Decision 3 lists "Board support" under what Crux will not provide, with "Zephyr boards and the product's overlays" instead. A binding that knows a board is board support inside Crux. A removes that knowledge and leaves the selection to the product's devicetree, through the aliases and chosen nodes that exist.

**Tests needed (red at the base).** The fictional-board build test of A, with the product-supplied binding in the fixture: red at the base, because the symbol does not exist. A test that the shared owner-conflict checks still run when the product supplies the binding. The EVKB cases unchanged.

**Documentation changes.** A new guide section for the seam, what the product must check, and what Crux then claims (nothing about the board). The `extend` paragraph. Table rows.

**Effort.** L. Three seams, a split of the Logging file, new symbols and headers, tests, guide.

**Risks.** The product owns the safety property that the check protected, and a wrong binding is silent. A second public surface to keep. The S2 identity changes.

### Option C. Keep as it is, and document it

**What changes.** Nothing in source. The guide gets the three corrections of section 3.5 and the `extend` paragraph, with the inherited-claims risk, and says what a team does: ask for a Crux change per component, or replace the port outside Crux.

**Effect on the EVKB path.** None.

**Interface and tier.** None.

**Tests needed.** A documentation check only. The existing `check_docs.py` covers links, and nothing tests the guide's statements.

**Effort.** S.

**Risks.** The product stays blocked on a design change that this repository has already reasoned through. The pressure to use `extend` grows, and with it the quiet inheritance of claims. The guide would become the only guard.

## 6. R1: the reference controller's S2 image must keep its identity on the EVKB

**What the evidence is.** The S2 identity is the SHA-256 of the image plus a firmware identity computed from the normalised configuration (`docs/board-image-profiles.md` [lines 85-93 and 104-106](../board-image-profiles.md#the-s2-profile-and-module-discovery)). The recorder hashes the resolved `.config` with comments dropped and the `# CONFIG_X is not set` lines kept (`scripts/record-build-provenance.py:170-190`). The S2 profile names Crux Logging, in deferred mode, among the things it checks. Whether System or Serial is compiled into any controller image I did not check, because this task reads no other repository; the profile refuses `WATCHDOG`, which suggests that the S2 image has no System.

**What every option already costs.** The controller pins crux-pilot, and the S2 profile in this repository accepts exactly one crux-pilot commit (`S2_MODULES`, `board-image-profiles.md:91`). So any crux-pilot change that the controller takes needs a pin move and, with it, an `S2_MODULES` change in crux-pilot, and that is independent of this proposal. The profile expects `37c92b18` at the baseline, and the controller's own pin is not examined here.

**What each option does to the identity.**

| Option | Image bytes | Configuration hash | Evidence that changes |
| --- | --- | --- | --- |
| A | Expected unchanged: only preprocessor conditions change, with the same truth values on the EVKB, and the asserts leave no code. A shift of `__LINE__` would matter only if the files used it in code that is built, which I did not check | Expected unchanged: no new symbol, no changed default or dependency on the EVKB | None, if the comparison below confirms it. The usual pin-move evidence |
| B | Expected unchanged | **Changes** if the new symbol is visible in the S2 image (see above) | A new S2 identity digest and manifest, an owner decision |
| C | Unchanged | Unchanged | None |

**How identity is kept or shown (A).**
1. On the crux-pilot side, before the change merges: build an existing EVKB image that composes Logging (and one that composes System), at the base and at the head, in the same Dev Container, with the same command. Run `scripts/record-build-provenance.py` on each, and compare `image_sha256` and `configuration_sha256`. The two must be equal. This is a one-off record in the PR, not a standing check, and it needs a Linux build, which CI or the Dev Container provides (it was not run for this proposal).
2. On the controller side: the pin-move PR that takes the change shows the S2 SHA-256 and the firmware identity unchanged, as the controller's rules already require for a pin move. If either differs, the change is not byte-identical and goes back to the owner.
3. The change must add no Kconfig symbol and no default, and it must not rename a symbol. A rule for the review: the diff of `zephyr/Kconfig` is empty, or contains help text only.

## 7. Comparison and recommendation

| | A (narrow) | B | C |
| --- | --- | --- | --- |
| Unblocks a custom RT1062 board | System and Logging, yes. Serial and FatFs, no (by choice) | Yes, for what the product writes | No. `extend` only |
| EVKB identity | Expected unchanged, shown by comparison | S2 configuration hash changes | Unchanged |
| New interface | None | Symbols and headers per component | None |
| What Crux claims about a custom board | E3 on a fictional board, stated as such | Nothing | Nothing, but silent inheritance through `extend` |
| Protects owner-conflict checks | Yes, same files | Only if split out | Yes |
| Effort | M | L | S |
| Protected paths in the change | Only test wiring (D8) | Same | None |

**Recommendation: A, narrow, with A2b for Logging** (other RT1062 boards may log on any enabled LPUART; the EVKB stays at `lpuart1`). Reasons:
1. The checks that matter on a custom board are devicetree properties and owner rules, and A keeps all of them. What it drops is the one test that never looked at hardware: the name.
2. It adds no interface. The S2 image and configuration hash are expected to stay unchanged, to be shown by the comparison and the pin-move evidence of section 6, rather than changed by construction as under B.
3. The pattern is already in the repository (GPIO, I2C and SPI by alias; Reliance Edge on any board). A follows it and keeps board knowledge out of Crux (Decision 3, "Board support"). B answers a real point of Decision 2, the missing composition interface, at the cost of a new public surface for each component; that point stays open under A and can be decided on its own if a product needs it.
4. It does not make the `extend` route worse and it makes it unnecessary for System and Logging.

**Alternative: B**, if the owner wants each product to own its claim and accepts the larger surface and a new S2 identity. **C** is the choice if nothing should move before the controller's next pin work; the guide corrections of section 3.5 are worth making in any case.

## 8. Decisions the owner needs to make

All are **Open (proposed)**. Each says what I recommend.

| ID | Decision | Recommendation | Alternative |
| --- | --- | --- | --- |
| D1 | Which option: A, B or C? | **A, narrow** (section 7) | B, or C |
| D2 | Scope of A | System and Logging only. Serial stays (frozen). FatFs microSD and RAM-disk selections stay named after the EVKB. Reliance Edge is the medium for a board that needs a File provider | Also key FatFs on the SoC and the devicetree (not recommended: its evidence is one board and one card) |
| D3 | The silicon key and the resource scope | Key on `CONFIG_SOC_MIMXRT1062`. System: WDOG1 only. Logging: A2b, any enabled `nxp,lpuart` node on other RT1062 boards, the EVKB kept at `lpuart1` as reviewed. The guide says that Crux checks no pin conflict on a product's board | A2a: any LPUART on every RT1062 board, the EVKB included, with Serial's CSI rule carried into Logging. Or A1, `lpuart1` only, which refuses boards that log elsewhere (a real RT1062 board in Zephyr consoles on `lpuart7`) |
| D4 | The Logging console-sharing exception (I7) | Key it on the SoC with the conditions that stand in the file | Keep it EVK-only. A custom board whose console and log UART are the same node then has to use another UART or turn the Console off |
| D5 | Wording: "accepted is not qualified" | Change the error text and the guide, keep every diagnostic that an existing test matches | Keep the old text for System and Logging |
| D6 | Name the `board: extend:` route in the guide, with the inherited-claims risk, whichever option is chosen | Yes, in the same documentation change | Leave it unmentioned |
| D7 | The identity evidence | Accept "expected unchanged", shown by the base-and-head comparison and the controller's pin-move evidence, and fold the change into the next planned pin move | Require a mechanical byte-identity check in CI first (needs a workflow change, `.github/` is protected) |
| D8 | Protected paths for the change itself | Source, Kconfig, tests, a new script and docs touch none. Extending the test runner of a changed component (`scripts/test-system.sh`, `scripts/test-logging.sh`) is covered by the approved work package under `AGENTS.md:88-90`, as long as nothing is removed. Only a step in `.github/workflows/` needs a separate approval, if the new test must run in CI. Both are listed in the PR, the workflow step with the approval quoted | Run the new test by hand and record the result, with no workflow edit |

## 9. What I could not verify

- **No build.** Every statement about what a custom board hits is an Inference from the code. No fictional board was written, no `west build --cmake-only` ran, and no image was compared. The statement that `CONFIG_BOARD_MIMXRT1060_EVK` stays set under `board: extend:` rests on `boards/Kconfig.v2` and `board_porting.rst` at `v4.4.0`; I did not run an extension.
- **Zephyr at the pin.** I read the local `v4.4.0` tree. The repository pins `v4.4.2`. That `mimxrt1062_fmurt6` and `mimxrt1064_evk` exist at the pin, and that the SoC dtsi lines I cite are unchanged, is not verified.
- **Kconfig behaviour.** That an assigned-but-dropped symbol stops a Zephyr configure, and whether a symbol with no prompt appears as a `# CONFIG_X is not set` line, are from my knowledge of Zephyr and kconfiglib, not from a run.
- **Which controller images compile which binding.** Only the S2 profile text in this repository was read. The controller repository was not.
- **`__LINE__` and file-name use.** Whether any built Crux source of these two files embeds a line number or a path in the image is not checked. The expectation of an unchanged image depends on it.
- **Hardware.** No board was used. How a custom board's UART, watchdog reset and flash are wired is outside this repository and was not assumed.
- **Review.** An independent review returned `REVISE` at `cad54be0`. This revision addresses its findings and has not been re-checked.

## 10. If the owner approves

Nothing below is authorised by this file. For option A, a work package would run in this order: the fictional board and the red build test first; then the two binding edits; the guide, readiness and help text; the base-and-head comparison recorded in the PR; the pin-move evidence from the controller session when it takes the change. Each protected path touched, if any, is listed in the PR with the owner's approval quoted, as [`AGENTS.md`](../../AGENTS.md#protected-paths) requires.
