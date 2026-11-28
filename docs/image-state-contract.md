# Image state contract

Status: **Experimental.** The first piece of the contract's implementation: the public header, the pure functions, the portable core and a Host test double. No bootloader provider exists, and nothing here ran on a board, in a bootloader or on `native_sim`. The decisions are rows I1 to I7 of the [image state contract proposal](plans/image-state-contract-proposal.md), which the owner approved as Experimental on 15 November 2026. The owner approved the implementation scope of this first piece on 16 November 2026. Rows I8 and I9 are approved too (see the proposal's [Decisions](plans/image-state-contract-proposal.md#decisions)). The first consumer is the [update agent](update-agent-contract.md), on the Host only. The Zephyr provider and the `native_sim` cases are pull request 3 of the [update agent work package](plans/update-agent-design-proposal.md#owner-decisions), approved but not started.

Owner: `components/image_state`. Public header `<crux/image_state.h>`, usage target `crux::image_state`. The header includes `<stdbool.h>`, `<stddef.h>` and `<stdint.h>` only. No Zephyr, MCUboot or bootutil header or type is part of it.

## What it is

A narrow contract for one image in two slots, numbered like the bootloader numbers them. It has three operations on state and no others:

| Operation | Function | What it does |
| --- | --- | --- |
| Query | `crux_image_boot_record_get()`, `crux_image_slot_get()` | The boot record taken once at start, and one slot's live state |
| Test request | `crux_image_request_test()` | Asks the bootloader to boot the other slot once as a test. It refuses unless the image there is strictly newer. |
| Confirm | `crux_image_confirm()` | Confirms the running image, and the running slot only |

`crux_image_start()` derives the boot record. It **fails closed**: with no boot data, no running slot or an unsupported running trailer it fails, and every other call then returns `CRUX_IMAGE_ERR_NOT_READY`. It never guesses the running slot.

Two pure functions need no provider: `crux_image_version_compare()` (major, minor, revision, the build number ignored) and `crux_image_outcome()`. "Reverted" is an outcome that the second function derives from the boot record and an attempt record of slot, version and whether the request was made. The contract stores nothing, and the update agent that will keep the attempt record is a separate design.

There is no permanent request, no staging write or erase, no bootloader update and no events.

## Layout

| Part | Where | Role |
| --- | --- | --- |
| Public header | `components/image_state/include/crux/image_state.h` | The contract, with its Doxygen text |
| Pure functions | `src/image_state_pure.c` | Version compare and outcome classifier |
| Slot-state table | `src/image_state_slot.c` | A slot's state from its header and trailer. Pure. |
| Service | `src/image_state.c` | Start, queries, request and confirm, over the private port |
| Private port | `src/image_state_port.h` | The medium: boot data, slot header and trailer, three writes. Carries no bootloader type. |
| Host double | `ports/host/image_state_host.c` | Memory slots, a write log, failure injection, and a hand model of the bootloader's select and erase rules |
| Double's controls | `ports/host/image_state_host.h` | Not under `include/`. Only the targets that test the contract name this directory. |

A product image never links the Host double. A provider over a real bootloader will implement the private port, and Q6 of the record (which directory holds it) stays open.

## What is Verified, and by what

**Verified by Host test:** the cases below passed against the Host double on the author's macOS arm64 machine with clang, in a scratch CMake project that holds only this component and its tests, also under the address and undefined-behaviour sanitizers. The Linux CI result at the reviewed revision is recorded in the pull request when it exists, and is not claimed here. The suites are `ImageState.pure`, `ImageState.provider`, `ImageState.scenarios`, `ImageState.nodiscard` and `ImageState.boundary` under `tests/image_state/`. The Host double is a hand-written model of the rules that the record tabulates, not a copy of MCUboot. A pass shows that the contract's logic follows its own table over that model, and nothing more.

| Cases of the record | Covered on Host | Notes |
| --- | --- | --- |
| S1 to S12 | Yes | S1 to S6 and S11, S12 for the slot that is not running. S7 to S10 for the running slot, including a failed `copy_done` write and a magic that is not good. Three further cases (S2b, S10b, S11b) pin where the table is silent: see below. |
| B1 to B4 | Yes | Plus a failed start that can be repeated, an unreadable slot, argument checks and running from slot 1 |
| R1 to R8 | Yes | R1 covers both directions (the B63a regression). R8 is the failure injection of the double. |
| C1 to C3 | Yes | |
| V1 | Yes | A table of vectors, including the build number being ignored |
| O1 to O7 | Yes | Each row of the outcome table, with each slot state |
| O8 | Yes | A cut during staging gives `NOT_BOOTED`. A cut after `requested` was set and before the writes landed gives `REVERTED`. |
| Scenarios | Yes | Stage, request, reset, start, classify: a full update, an update left unconfirmed, a refused image, and an update from slot 1 |

**Not run, and why:**

- **V2 and N1** are `native_sim` cases. No `native_sim` result exists. They need the Zephyr provider over the real bootutil, which is not built.
- The `native_sim` column of every other case is not run for the same reason.
- **T1 to T7** are target cases. They need a board, the real bootloader, the retained shared data and, for T6 and T7, a power fixture and the eMMC driver. No board, bootloader or target result exists.
- That the hand model matches the real bootloader, that the shared data survives the jump into the SDRAM-loaded image, and anything about cache ordering are **Not verified**.

**The build checks:** the usage target `crux::image_state` carries no native include directory, definition or link requirement (the repository's consumer boundary check, on a C and a C++17 consumer), a discarded result warns, and `ImageState.boundary` reads the sources and fails if the public header includes anything beyond the three standard headers or if the header, the portable core or the private port names a Zephyr, MCUboot, bootutil or flash-area facility in code.

## Choices where the record is silent

The record fixes the decisions and leaves some details open. The implementation took the cautious reading in each case, tested it, and lists it here for the owner. Each is easy to change, and none changes a decision.

| Point | Choice |
| --- | --- |
| A running slot with no valid header, an `image_ok` flag outside set and unset, or, while `image_ok` is unset, a `copy_done` flag outside set and unset | `crux_image_start()` fails with `CRUX_IMAGE_ERR_BOOT_STATE` (fail closed, row I6). The table only says that a running slot with a magic that is not good fails. With `image_ok` set the table says `copy_done` is "any", so the slot is `RUNNING_CONFIRMED` whatever `copy_done` holds (case S7). |
| A slot that is not running, with the magic unset and a stale flag | `INVALID`, not `STAGED`. A request on `STAGED` with `image_ok` set would create a permanent request, which row I2 excludes, and with `copy_done` set the slot would be erased at the next reset. `STAGED` needs an erased trailer. |
| A slot that is not running, with a magic other than good, unset or bad (a value the port should never report) | `INVALID` (case S11b), so `crux_image_request_test()` refuses it with `ERR_SLOT_STATE` and writes nothing. Before, such a value was read as good and could yield `PENDING_TEST`, whose repeat request returns `OK` without writing. |
| A missing mode key, or a running slot above 1 | A missing mode key is `ERR_NO_BOOT_DATA`. A mode other than RAM load, or a running slot above 1, is `ERR_BOOT_STATE`. |
| Unreadable slot at start | `ERR_IO`. The start caches nothing and may be repeated. |
| `ERR_BUSY` | One try-lock serialises start, request and confirm. A caller that finds it taken gets `ERR_BUSY` at once: the bounded wait of the record is zero. The record's text sets no bound. |
| Order of the request checks | As the record lists them. A pending slot whose version is no longer strictly newer gives `ERR_NOT_NEWER`, not an idempotent `OK`, and a stale confirmed trailer under an older image gives `ERR_NOT_NEWER`, not `ERR_SLOT_STATE`. |
| A live running trailer that stops being supported after start | `crux_image_slot_get()` reports `INVALID`. `crux_image_confirm()` and `crux_image_request_test()` return `ERR_BOOT_STATE`. |
| Outcome inputs outside the table | A missing record and an attempt on a slot that does not exist give `NONE`. A requested attempt on a slot that was in a running state at start gives `NONE`. A request that was never made gives `NOT_BOOTED` first (rule 5). |

## Known limits

- A power cut after `requested` was set and before the request writes landed reports `REVERTED` for an image that never ran: the newer image is erased at the next reset and the record cannot tell the cases apart. The error is on the safe side (the agent retries). Case O8 pins it.
- A request that fails after the magic write leaves the slot `PENDING_TEST`, and a repeat returns `OK` without writing. Whether a slot without the swap information boots as a test is a property of the real bootloader and is **Not verified**. The Host model does not read the swap information.
- The Host model does not erase an image whose load fails, as the real loader does. It models a validation failure only.
- The contract checks no permission. A management adapter checks access before the update agent calls it.
- Where the attempt record lives and how it survives a power cut is the update agent's design (Q2 of the record, open).
