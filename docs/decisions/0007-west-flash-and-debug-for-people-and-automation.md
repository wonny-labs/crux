# ADR-0007: Zephyr's west flash and west debug for people and automation

Status: **Accepted** by the maintainer on 21 November 2026: W0, people and agents or automation may use `west flash` and `west debug`. W1 to W3 keep existing rules and W4 to W6 put W0 into practice; all six were recommended with the decision and are confirmed by the maintainer's approval of this record's pull request. Baseline: `origin/main` at `37643805cf7d33914fca43f668b0cd53a348cf50`. Zephyr files were read in a v4.4.0 checkout; `git diff v4.4.0 v4.4.2` is empty for each file cited, so the facts hold for the pinned v4.4.2. Author: Claude Code, model `claude-opus-5-5`.

This record decides who may use Zephyr's standard `west flash` and `west debug` commands, and under which conditions. It adds documentation, an optional board Dev Container and checks that its files parse. Nothing in it has been run on hardware, on Windows or with usbipd. The route it documents is in the [board guide](../board-jlink-usbipd.md).

**Labels.** **Verified** means read at the baseline revision, or in the pinned Zephyr v4.4.2 source, and cited. **Reported** means the maintainer reported it and it was not re-checked here. **Not verified** means no run exists.

## Context

| Fact | Evidence | Status |
| --- | --- | --- |
| The only debug and physical-test host that has been used is macOS. The GDB Server launcher and the physical test script exit on any other system | [Build guide, RT1060-EVKB debugging](../build.md#rt1060-evkb-debugging) at the baseline | Verified |
| The build guide listed "a general flash or debug wrapper over `west flash` and `west debug`" as not provided, and kept the split between a host GDB Server and the container's GDB because the container had no J-Link software | `docs/build.md` at the baseline, section "What the platform provides for build and debug" | Verified |
| A first check from a Windows PC with WSL2 and Docker Engine in WSL2 worked only with the J-Link GDB Server on Windows opened to remote connections, a firewall rule for the WSL subnet and a host name mapping in the container. It is too many steps and too much network exposure for a team default | The maintainer, 21 November 2026 | Reported |
| In that run a read-only `compare-sections` against the Time sample ELF matched all sections, through the GDB Server route | The maintainer, 21 November 2026 | Reported |
| The recorded SWD speed on the EVKB is 400 kHz, and 100 kHz on a first connection | `docs/baseline.md`, sections "M4 SWD connection after J9/J10 correction" (100 kHz) and "M4 J-Link GDB transport check" (400 kHz) | Verified |
| On one board a connection at 4000 kHz, J-Link's usual default, also worked | The maintainer, 21 November 2026 | Reported |
| A common practice on WSL2 is to attach the probe to the WSL2 distribution with usbipd-win and run the J-Link software inside the Dev Container. Some setups use `--privileged` for USB access | The maintainer, 21 November 2026 | Reported |
| For `mimxrt1060_evk`, Zephyr's default flash and debug runner is LinkServer, because the board includes `linkserver.board.cmake` before `jlink.board.cmake` and the first one sets the default. The J-Link runner has to be selected with `-r jlink` | `boards/nxp/mimxrt1060_evk/board.cmake`, `boards/common/linkserver.board.cmake`, `boards/common/jlink.board.cmake` in Zephyr v4.4.2 | Verified |
| The board passes `--device=MIMXRT1062xxx6A` and, for QSPI or revision B, `--loader=BankAddr=0x60000000&Loader=QSPI` to the J-Link runner | `boards/nxp/mimxrt1060_evk/board.cmake` in Zephyr v4.4.2 | Verified |
| `west debug` with the J-Link runner halts, resets and runs GDB `load`, so it writes the image to flash. `west attach` adds no halt, reset or load command, but the GDB Server is started without `-nohalt`, so the target halts while attached | `scripts/west_commands/runners/jlink.py` in Zephyr v4.4.2, `do_run` | Verified |
| `AGENTS.md` requires explicit authorisation for the current task for physical programming, reset and other hardware operations, and forbids unattended operations based on past approvals | `AGENTS.md`, "Safety and workspace boundaries" | Verified |
| The device-control tool under `tools/` has its own gates, including `--allow-flash=<approval reference>`, and has never run against real hardware | `docs/build.md`, "Hardware integration tests" | Verified |

## Options

### W0: who may use `west flash` and `west debug`

| Option | What it means | Trade-offs |
| --- | --- | --- |
| A. Nobody, keep only the host GDB Server route | No change | Every non-macOS developer repeats the remote GDB Server set-up. Agents cannot use the standard Zephyr commands at all |
| **B. People and agents or automation, under the existing rules (recommended)** | The standard commands are a supported route. Each physical operation still needs the authorisation that `AGENTS.md` requires | Standard and documented upstream. Needs the J-Link software and USB access in the container |
| C. People only | Agents may not run them even when the task authorises a board operation | Keeps agents on the GDB Server route, which has the most steps and the most exposure |
| D. A Crux wrapper over `west flash` | A script that adds checks in front of the commands | Duplicates Zephyr and the device-control tool. `AGENTS.md` (Engineering approach) rules out pass-through wrappers for native APIs, as ADR-0001 also cites |

### USB access in the container

| Option | Trade-offs |
| --- | --- |
| **usbipd-win to WSL2, then a bind mount of `/dev/bus/usb` with a device cgroup rule for USB character devices only (major 189) (recommended)** | No `--privileged`. A re-enumerated probe, after a reset or a new attach, stays reachable. Needs usbipd-win on Windows and a udev rule on the WSL2 side |
| `--privileged` | Simplest, but gives the container every device and capability on the host |
| Pass one device node with `--device` | Breaks when the probe re-enumerates and gets a new node |
| J-Link GDB Server on the Windows host, opened to remote connections | Works and is kept as a fallback, but needs a firewall rule and opens a debug port to the network |

## Decisions

| Code | Decision |
| --- | --- |
| W0 | Option B. People and agents or automation may use Zephyr's standard `west flash` and `west debug`, and `west attach` for a read-only connection, for the RT1060-EVKB QSPI target |
| W1 | Each physical operation still needs explicit authorisation for the current task, as `AGENTS.md` says. Flashing, resetting, attaching and starting a debug session are physical operations. This record is not that authorisation and changes nothing in `AGENTS.md` |
| W2 | No unattended flashing in CI. No workflow flashes, resets or attaches to a board, and Twister's `--device-testing` stays outside the supported routes, as the [build guide](../build.md#hardware-integration-tests) says |
| W3 | The device-control tool and its gates under `tools/` stay unchanged. They remain the route for test fixtures, and `west flash` does not replace or bypass them |
| W4 | The documented route is usbipd-win on Windows (none on native Linux) and an optional board Dev Container that installs the J-Link software from a package the developer downloaded. It uses no `--privileged`. The default Dev Container does not mount USB devices and installs no J-Link software |
| W5 | The host-side J-Link GDB Server route with the existing VS Code profiles stays documented as a fallback |
| W6 | Crux adds no wrapper script of its own over `west flash` or `west debug` (option D rejected) |

## Consequences

- The build guide no longer lists a flash or debug route over `west` as not provided. It names the standard commands, the J-Link runner and the conditions above, and it still lists unattended programming as not provided.
- An agent may run `west flash`, `west debug` or `west attach` only inside a task whose approval names that board operation. A read-only `west attach` with `compare-sections` is still a physical operation: it may halt the target.
- Images that run from SDRAM need a J-Link script that sets up SDRAM before loading. It can be passed to the J-Link runner with `--tool-opt`. That is not in this record's scope and has not been tried.

## What was not verified

No step of the board route has run: not usbipd-win, not the board Dev Container build, not the udev rule, not `lsusb` in the container, not `west attach`, `west debug` or `west flash` through the J-Link runner. The default Dev Container was not rebuilt. CI can only check that the files parse and that existing builds and tests still pass. The [board guide](../board-jlink-usbipd.md#6-first-check-on-a-windows-pc) holds the first check to run on a Windows PC.

## Record

| Item | Value |
| --- | --- |
| Baseline | `37643805cf7d33914fca43f668b0cd53a348cf50` |
| Acceptance | Accepted by the maintainer on 21 November 2026 (W0). W1 to W6 were recommended with it and are confirmed by the approval of this record's pull request |
| Model | `claude-opus-5-5`, Claude Code |
| Independent review | The `reviewer` agent, verdict in the pull request |
