# Update agent design proposal

Status: **Proposed, for the owner. Nothing here is adopted, and implementation is not approved.** This record is documentation only. It changes no code, check, contract or protected path, and the acceptance criteria of [#297](https://github.com/wonny-labs/crux-pilot/issues/297) (milestone M9) are unchanged. Every decision row below is **Open (proposed)**. The work package in U8 is a proposal: it needs its own scope approval before any of it starts. Baseline: main `6c246d13`, Zephyr v4.4.2 `dccb095`, MCUboot `6d3b3d2c` (the revision named by Zephyr's own `west.yml`). The upstream sources were read outside the repository, and none of them is copied.

It builds on the [image state contract proposal](image-state-contract-proposal.md) (read at `6c246d13`: rows I1, I4 and I7 are approved there, rows I2, I3, I5, I6, I8 and I9 are still open, and the pull request that records an approval of I2, I3, I5 and I6, [#481](https://github.com/wonny-labs/crux-pilot/pull/481), was open when this was written). Where this proposal relies on an open row, it says so. If the owner changes such a row, the dependent part of this proposal changes with it. The proposal does not edit the image-state record and only links to it. It also builds on the [secure boot development plan](secure-boot-development-plan.md) (sections 2, 3, 4 and 8, Phase 2), the [boot and update investigation](../boot-update-investigation.md), the [bootloader update investigation](../boot-bootloader-update-investigation.md), the [Reboot service](../reboot-service.md), the [file service proposal](file-service-contract-proposal.md), the [status and configuration services proposal](status-configuration-contract-proposal.md), the [secure management design](secure-management-design.md) and [ADR-0002](../decisions/0002-platform-direction-zephyr-execution-crux-services.md).

## Evidence labels

Labels follow the image-state record. `Z:` means Zephyr `dccb095`, read as `git show dccb095:<path>` in a Zephyr checkout outside the repository.

| Label | Meaning |
| --- | --- |
| Verified on pinned source | Read at the cited file of the pinned revision. Shows what the code allows, not what a board does. |
| Verified in repository | Read from a crux-pilot file at `6c246d13`. |
| Inference | Reasoned from the rows named. The reasoning is stated. |
| Not verified | Not read, not run, or needs a board or a power fixture. |

## Decisions

Every row is the author's recommendation for the owner and is **open**. "Alternative" is the option that was weighed and not recommended. Details follow in the section of the same number.

| ID | Decision | Recommendation | Reason | Alternative | State |
| --- | --- | --- | --- | --- | --- |
| U1 | State machine of the update agent | A table of resting states, events and transitions that names every medium write. One attempt at a time, run on the caller's thread, and a start that writes nothing. The agent never resets and never makes a permanent request. | Every write point gets a name, so the table can be tested exhaustively on Host and each power cut can be mapped to a row. The reset stays with the Reboot service, whose policy may refuse. | An event-driven machine with its own worker thread. It adds a thread and more states. ADR-0002 P2 freezes the Crux Thread header for new product code, which does not forbid a Crux service from owning a thread, so this is a cost and not a rule. | Open (proposed) |
| U2 | Where the attempt record lives, and how it stays consistent across a power cut (open question Q2 of the image-state record) | A reserved flash area behind a narrow record port. The Zephyr provider uses Zephyr NVS on a dedicated partition. | It is readable at start without any volume, it uses the flash-area path that the staging writes use anyway, and a torn write leaves the previous record (Inference, not tested). | The File service, behind the same port, for a product whose volume is always present and transactional. The Configuration service is rejected. | Open (proposed) |
| U3 | Application-side version policy | One pure rule, strictly newer on major, minor and revision, applied on the header **before any erase or write** and again inside `crux_image_request_test()`. | Owner decision 4 requires the older-image check, and owner decision 5 requires it before any NOR write. The second check covers what is in flash. | Apply it only at the request. It wastes an erase and a write, and it leaves a staged slot for the bootloader to erase. | Open (proposed) |
| U4 | Staging path: who erases and writes, the precondition, and the input path | The agent erases and writes the staging slot through a slot port. The image is verified (header gates, version, hash, signature) before the first erase. The header is written last. A read-back of the slot closes the check. The input is a random-access source, so the transport stays generic. | #297 asks for the check before the staging write. A header written last keeps a half-written image invisible to the bootloader. A source with random access serves a network buffer and a file alike. | Stream the image into the slot from offset 0 and verify afterwards. It needs less RAM, but it writes before the signature is checked and leaves a valid-header partial image. | Open (proposed) |
| U5 | Power-interruption cases | Declare the cut points of the table in U5 as the M9 power-interruption cases. Keep the record order of I3, and accept its stated window. | The table maps every cut point to a slot state, an outcome and a recovery, and no cut point loses the running image. | A three-valued request marker that removes the window. It needs a change to the attempt type of I3. | Open (proposed) |
| U6 | Declared recovery, and what stays service recovery | Declare the five recoveries of U6. Keep service recovery for the bootloader and for a device with no valid image (owner decision D7). | It declares what the update path does by itself and nothing more. | A field-updatable bootloader. D7 says to decide it again after Phase 3. | Open (proposed) |
| U7 | Test strategy | Host tests with fault injection and a hand model of the bootloader, then `native_sim` over the real bootutil on a flash simulator. List board and power-fixture cases, and do not plan to run them. | It makes the table of U5 executable before any hardware exists, and it keeps the claim to what software shows. | Run MCUboot's own simulator in CI. It was not assessed (Not verified, as in I8). | Open (proposed) |
| U8 | A work package for `crux/image_state.h` and the update agent | A proposal in three Draft pull requests under one scope approval: the contract and its Host double, the agent core with its fakes, then the Zephyr providers and `native_sim` tests. Hardware and transports are excluded. | The image-state contract is the agent's only consumer. Building them together tests them together, and the review stays in small pieces. | Approve only the first pull request now, and decide the rest after it. | Open (proposed) |

## The question and the short answer

#297 asks for an update agent "that writes a received image to the staging slot only after checking size, header, version and signature, with an explicit state machine", with test, confirm and revert, rejection of an older image, a boot-result record, and declared recovery and power-interruption cases. The image-state record leaves the attempt record, the staging write and erase, and the order of the steps to this proposal.

**Recommendation.** One agent core in portable C, driven by a transition table, behind five narrow ports (source, slot, record, verify, image state). The record sits in a reserved flash area. The agent verifies the whole image before it erases anything, writes the header last, reads the slot back, and only then records `requested` and asks the bootloader for a test boot. It never resets by itself.

The two points that decide the design are in the image-state record, not here:

- A newer image that is staged and not requested does not survive a reset. The bootloader erases the whole slot, and it does that while it executes from NOR, which [#165](https://github.com/wonny-labs/crux-pilot/issues/165) blocks on hardware. The agent therefore keeps the window between "header written" and "request made" as short as it can, and invalidates the slot itself when an attempt fails after that point.
- "Reverted" is derived. Nothing in flash says an update was attempted and undone, so the attempt record is the only thing that can say it, and its writes must be ordered against the slot writes.

## What exists, and what this proposal assumes

- **At this head no code calls the image-state functions** (Verified in repository, as the image-state record says for its own head). A host prototype of the image state exists as a Draft, [#462](https://github.com/wonny-labs/crux-pilot/pull/462), not for merge. This proposal does not depend on it.
- **The bootloader behaviour** is the table in [What the bootloader leaves behind](image-state-contract-proposal.md#what-the-bootloader-leaves-behind), and the outcome rules are the seven cases of [Boot record and outcome](image-state-contract-proposal.md#boot-record-and-outcome). This proposal cites them by name and case number. No board has run any of it (Not verified).
- **The signatures** of the image-state header are illustrative in that record. This proposal uses the names `crux_image_start()`, `crux_image_boot_record_get()`, `crux_image_slot_get()`, `crux_image_request_test()`, `crux_image_confirm()`, `crux_image_version_compare()` and `crux_image_outcome()` and the slot states and outcome cases as that record gives them.
- **The composition** is RAM load with revert on RT1060-EVK Rev B ([boot composition](../boot-composition.md)): one image, two slots of 3 MiB, the application executes from SDRAM, and the build writes both an unconfirmed signed image and a padded, confirmed one. The agent must stage the unconfirmed one (see the gates in U4).
- **Access control is not in the agent.** A management adapter checks access before it calls the agent (owner decision 5, [boot and update investigation](../boot-update-investigation.md#owner-decisions-needed), and the firmware service of the [secure management design](secure-management-design.md), which enforces `firmware.upgrade`). The agent trusts its caller, as the image-state contract does.
- **Transports are out of scope.** mcumgr is Q3 of the image-state record and is not in M9. HTTPS and SFTP delivery are [#191](https://github.com/wonny-labs/crux-pilot/issues/191) and [#196](https://github.com/wonny-labs/crux-pilot/issues/196).

### Parts and ports

The agent core is portable C with no Zephyr, board or bootutil header. Zephyr facilities sit in providers, as ADR-0002 P1 asks of a Crux service. Whether the agent counts as a Crux service or as product code is Inference (plan section 8). This proposal treats it as a Crux service with a narrow public header, which is part of what U8 asks the owner to confirm.

| Port | What it does | Zephyr provider | Host fake |
| --- | --- | --- | --- |
| Source | The candidate image: its size and `read(offset, buffer, length)` with random access. | A memory source over an SDRAM buffer that a transport filled, or a File-service source. Both are supplied by the caller. | In-memory bytes, with a hook that changes them between two reads |
| Slot | Capacity, blank check, erase, write and read of the staging slot. It refuses any slot but the inactive one. | `flash_area_*` on the slot partition. Capacity is the slot size minus the trailer area. | A flash fake with fault injection at the n-th operation |
| Record | Load and store of the attempt record, with the guarantee in U2. | NVS on a reserved partition | In-memory, with fault injection |
| Verify | SHA-256 and ECDSA P-256 over the image, following MCUboot's trailing metadata layout, with a public key supplied by the composition. | PSA Crypto ([PSA Crypto qualification](../psa-crypto-qualification.md): ECDSA P-256 verify is a qualified case, and on RT1060 the qualification matrix is compile-only, with one recorded board run of the TF-PSA-Crypto conformance image on 7 November 2026. ECDSA verify inside an update flow has not run on a board) | Known-answer vectors |
| Image state | The `crux_image_*` contract. | Its Zephyr provider over bootutil | Its Host double |
| Progress | Called between sector operations, so a composition can feed a watchdog and a status read can show progress. | The composition | A recorder |

The Reboot service is not a port. The agent does not reset: `crux_image_request_test()` does not reset either, and a reset goes through the [Reboot service](../reboot-service.md), whose policy may refuse it.

## U1. State machine

The machine has **resting states**. A transition is an operation that starts in a resting state, performs the writes it names, and ends in the next resting state or in `FAILED`. A medium write is marked ▲. A state that is not resting (an operation in progress) does not exist as a state, so a power cut during an operation is read off the table as "the writes of that row, partly done".

### States

| State | Meaning | Persistent facts it corresponds to |
| --- | --- | --- |
| `NOT_STARTED` | `crux_update_start()` was not called, or has not finished. | |
| `UNAVAILABLE` | `crux_image_start()` failed (fail closed, I6). Every request returns not ready. | Shared boot data missing, or the running slot is not in an expected state |
| `IDLE` | No attempt in flight. | No record, an acknowledged record, or a stale one |
| `OUTCOME` | A previous attempt has an outcome (`CONFIRMED`, `REVERTED` or `NOT_BOOTED`) that was not acknowledged. | Record present, classifier result as named |
| `TESTING` | The running image is on trial. Confirm is offered. | `running_confirmed` is false. A record may or may not exist: an image booted by a development tool is on trial with no record. |
| `CHECKED` | A source passed every check. Nothing is written. | None |
| `RECORDED` | Record written with `requested` false. | Record `{slot X, version, requested = false}` |
| `ERASED` | Slot X reads as the erased value in every byte, trailer included. | Slot `EMPTY` |
| `BODY_WRITTEN` | The image without its header is in slot X. | Slot `EMPTY` (header blank) |
| `STAGED` | The header is written. The slot holds the whole image and no trailer. | Slot `STAGED` |
| `VERIFIED` | The read-back of slot X equals the verified hash. | Slot `STAGED` |
| `WAITING_RESET` | The request is made. A reset boots the image. | Record `requested = true`, slot `PENDING_TEST` |
| `FAILED` | The attempt ended without a requested image. It carries a reason. | Record `requested = false`, or `requested = true` when the request failed after the record was set (TR17). Slot invalidated or still staged. |

### Events

`START` (the call that starts the agent), `BEGIN(source)`, `NEXT` (an internal continuation: the run goes from one resting state to the next on the caller's thread without another call), `CANCEL` (honoured between sector operations), `CONFIRM`, `ACK`. A reset is not an event of the table. It ends the run, and the next boot's `START` derives the state again from persistent facts (see U5).

### Transition table

Every pair that is not listed is refused with a result code and changes nothing. `UNAVAILABLE` refuses everything except a status read.

| # | From | Event | Guard | Operation | Medium writes | On success to | On failure to |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TR1 | `NOT_STARTED` | `START` | `crux_image_start()` fails | none | none | `UNAVAILABLE` | |
| TR2 | `NOT_STARTED` | `START` | Started, `running_confirmed` is false | Load the record, classify | **none** | `TESTING` | |
| TR3 | `NOT_STARTED` | `START` | Started, running image confirmed, `crux_image_outcome()` is `CONFIRMED`, `REVERTED` or `NOT_BOOTED` | Load the record, classify | **none** | `OUTCOME` | |
| TR4 | `NOT_STARTED` | `START` | Started, running image confirmed, outcome `NONE` or no record | Load the record, classify | **none** | `IDLE` | |
| TR5 | `NOT_STARTED` | `START` | Record unreadable (both units invalid, or a read error) | Treat as no record. Set `record_lost`. | none | `IDLE` (or `TESTING` by TR2) | |
| TR6 | `IDLE`, `OUTCOME`, `FAILED` | `BEGIN` | Not busy. From `OUTCOME` or `FAILED`, a successful check acknowledges the old record: TR8 replaces it. | Read the header, apply the gates and the version policy (U3, U4), hash the whole source, verify the signature | none | `CHECKED` | The state it came from, with a refusal code. Nothing was written. |
| TR7 | `TESTING`, `WAITING_RESET`, any state of an attempt | `BEGIN` | | Refuse with `BUSY` or `NOT_CONFIRMED` | none | unchanged | |
| TR8 | `CHECKED` | `NEXT` | | Store the record `{X, version, requested = false}` | ▲ record | `RECORDED` | `FAILED(record)`. The previous record is intact (U2). |
| TR9 | `RECORDED` | `NEXT` | | Erase every sector of slot X that is not blank, header sector first, and blank-check the whole slot, trailer included | ▲ slot erase | `ERASED` | `FAILED(erase)`, slot dirty |
| TR10 | `ERASED` | `NEXT` | | Write the image body, in order, without its header | ▲ slot write | `BODY_WRITTEN` | `FAILED(write)`, slot dirty |
| TR11 | `BODY_WRITTEN` | `NEXT` | | Write the header | ▲ slot write | `STAGED` | `FAILED(write)`, slot dirty |
| TR12 | `STAGED` | `NEXT` | | Read the slot back, compare its hash with the verified hash, read the version again, check that `crux_image_slot_get(X)` says `STAGED` | none | `VERIFIED` | `FAILED(verify)` and TR16 |
| TR13 | `VERIFIED` | `NEXT` | | Store the record `{X, version, requested = true}`, then call `crux_image_request_test(X)` | ▲ record, then ▲ trailer (magic, then swap info, written by bootutil) | `WAITING_RESET` | See TR17 |
| TR14 | `TESTING` | `CONFIRM` | The running image is on trial | `crux_image_confirm()` | ▲ trailer (`image_ok` of the running slot) | `OUTCOME` with `CONFIRMED` | `TESTING` with the error. A retry is allowed. |
| TR15 | `OUTCOME`, `FAILED` | `ACK` | | Clear the record | ▲ record | `IDLE` | Unchanged, with the error. A stale record is harmless (cases 3 and 4 of the classifier). |
| TR16 | `STAGED`, `VERIFIED`, or a failure after TR11 | A failure, or `CANCEL` | The slot may hold a valid header | **Invalidate the slot:** erase the header sector and the trailer sector of X | ▲ slot erase (best effort) | `FAILED(reason)` | `FAILED(reason)` with `slot_staged`: the bootloader erases it at the next reset |
| TR17 | `VERIFIED` | a failure in TR13 | A refused or failed request | Read the live slot state. `PENDING_TEST`: go on as success. Anything else: TR16. | ▲ as TR16 | `WAITING_RESET` or `FAILED` | `FAILED` |
| TR18 | `WAITING_RESET` | a reset (not an event) | | The bootloader selects the slot, or erases or refuses it | bootloader writes | Next `START`: `TESTING`, or `OUTCOME` (`REVERTED`, or `NOT_BOOTED` if the request was not consumed, case 6) | |
| TR19 | `CHECKED`, `RECORDED`, `ERASED`, `BODY_WRITTEN` | `CANCEL` or a failure in TR8 to TR11 | The slot has no valid header | none (the header is still blank, or the slot is untouched) | none | `IDLE` from `CHECKED`, otherwise `FAILED(reason)` | |

Properties the table fixes:

- **`START` writes nothing** (TR2 to TR5). A power cut during start changes nothing, and start can be repeated.
- **The record is written before the first change to the slot** (TR8 before TR9), and **`requested` is set before the request** (TR13), as the image-state record orders them.
- **No state has a way to `crux_image_request_test()` except through `VERIFIED`.** The version policy and the read-back therefore both ran.
- **TR16 is the only erase outside TR9.** It exists so that an attempt that fails after the header was written does not leave the bootloader to erase 3 MiB while it executes from NOR. It is best effort: if it fails, the slot stays `STAGED` and the bootloader does the erase as the image-state record describes. Whether an erase of the header sector alone makes the slot invisible to the bootloader is Inference from "a slot is available if its header is valid" (`M:boot/bootutil/src/loader.c`:2066-2105, as the image-state record cites it). What "valid" includes was not read here (Not verified).
- **A failed attempt leaves the running image alone.** No transition writes to the running slot except TR14.
- **The agent runs on the caller's thread.** TR6 to TR13 run to completion in one call, which blocks for the length of the erase and writes (not measured). A status read from another thread takes a short lock and copies a snapshot, like the Configuration service ([concurrency](status-configuration-contract-proposal.md#concurrency)). The progress port lets the composition feed a watchdog between sector operations. Erase duration and watchdog behaviour on the board are Not verified ([boot and update investigation](../boot-update-investigation.md#flash-writes-during-xip)).
- **No withdraw.** There is no transition that cancels a request after TR13. A request that was made is withdrawn only by not confirming: the image is erased at the first reset after its test boot. A withdraw would erase the trailer sector of a pending slot. It is not proposed.

## U2. The attempt record

### What it holds and what it must survive

The record is the image-state attempt type (slot, version, `requested`), plus the integrity fields of its own store (a format version, a sequence number and a CRC-32). It is small, about 16 bytes. It must satisfy three things:

1. After a power cut at any point of a store, a load returns **the new record or the previous one, never a mixture and never nothing** if a record existed. A torn store must be detected, not accepted.
2. It is readable at start, before any other service, with no dependency on a volume being mounted.
3. A store has returned only when the record is durable on the medium as far as the driver can report. The record must be durable before the trailer writes of TR13. For NOR the program returns after the cell is written (Inference, not tested). For eMMC it needs the cache flush that [#298](https://github.com/wonny-labs/crux-pilot/issues/298) and M14 describe, which the write path of the [eMMC investigation](../boot-emmc-investigation.md) lists as a driver requirement (Not verified on a board).

There is **no transaction across the record and the slot**, and none is proposed. The classifier of the image-state record is designed to tolerate the windows between the two media, and U5 lists them.

### Options compared

| | A. File service | B. Configuration service | C. Reserved flash area, with Zephyr NVS (recommended) | D. Retained RAM |
| --- | --- | --- | --- | --- |
| Consistency across a power cut | Replacement is **not atomic**. `crux_file_rename` refuses an existing destination, so replacement is remove then rename, and a cut between them leaves no target. On a card, the earlier run left no settings file in 29 of 100 cuts. (Verified in repository: [file service proposal](file-service-contract-proposal.md#replacement-and-power-loss), [eMMC design](emmc-reliance-design.md), finding F9.) Two files used as an A/B pair, each rewritten in place with its own CRC, would tolerate a cut (Inference, not tested). Reliance Edge documents an atomic rename. No physical evidence exists. | Save acknowledges "this parameter's encoded bytes", with no whole-schema atomicity, and a failed save "may already have changed stored bytes" (Verified in repository: [Configuration contract](../configuration-contract.md), failure table). A record of three fields is three parameters. | NVS writes the data and then an 8-byte metadata entry with a CRC, and initialisation ignores data without valid metadata (Verified on pinned source: `Z:doc/services/storage/nvs/nvs.rst`, `Z:subsys/kvss/nvs/nvs.c`:521-565). The documentation says each used id keeps at least one pair in flash at all times. That a cut during a new write leaves the previous pair readable is Inference from this, not tested. | Lost at a power cut. A power cut during the test boot is exactly when the record is needed. |
| Available at start with no other service | No. It needs a mounted volume and a started File service. A removable card may be absent (Inference). The Pilot's File path is microSD (Verified in repository: M4 decision, [file service](file-service-contract-proposal.md)). | No. It needs the service table, and **no target provider exists at this head**: an image that uses Configuration on the target fails to link, and the no-provider port returns `NOT_SUPPORTED` (Verified in repository: [status and configuration proposal, Target provider gap](status-configuration-contract-proposal.md#target-provider-gap)). | Yes. It needs the flash device and a partition. | Yes |
| Exposure to management | A record root is not declared as an area, as the credential store's roots are not (Verified in repository). | The table is management-visible by design: listing, permissions, read and update through the service. An attempt record is not a setting. | None. Nothing outside the agent opens the partition. | None |
| Layout cost | A root on the volume | None | A partition. The `storage` partition has "no owner and no writer in M8" (owner decision 17, [boot and update investigation](../boot-update-investigation.md#owner-decisions-needed)), so using it **revises that row**. A new partition changes the layout, which the boot composition fixes with 64 KiB aligned boundaries. | None |
| Fit to the platform rule | A Crux service, so a Crux dependency | A Crux service, so a Crux dependency | A Zephyr-native facility, used inside a provider ([ADR-0002](../decisions/0002-platform-direction-zephyr-execution-crux-services.md), P1) | |
| eMMC | The File root over Reliance Edge, if the product has one | Same limit | A raw reserved area outside any file system, like the slots. NVS needs the flash-API driver to report a page layout. That it does for the eMMC driver, and with a 512-byte write block, is **Not verified**. | |
| Main risk | Dependence on a volume that may be missing or corrupt | Not usable at this head | New partition decision. NVS on the eMMC driver is unproven. | Wrong outcome after a power cycle |

### Recommendation and how it stays consistent

Recommend **C**: a reserved flash area behind a narrow record port, with the Zephyr provider on NVS. NVS was weighed against a hand-written two-unit A/B record (a CRC-32 over each record and a sequence number, one erase unit written at a time). NVS is the Zephyr-native facility that already does this (AGENTS.md: use Zephyr-native storage facilities when suitable), and it brings its own garbage collection. The hand-written record would be about as small, but it is new storage code to test. If the work package's native_sim runs show that NVS does not fit (for example on the eMMC driver), the A/B record is the fallback behind the same port. The record also carries its own CRC-32, so the store does not rely on NVS's CRC-8 alone.

The consistency rules, all of them testable on Host:

1. **Store contract.** `store()` returns `OK` only after the record is durable. `load()` returns the latest complete record, or the previous one if the last store was cut, or "none". A record with a bad CRC is "none", never data.
2. **Order against the slot.** TR8 before TR9. TR13's record write before its trailer writes. An acknowledgement (TR15) clears the record only after the outcome was reported.
3. **The classifier absorbs the windows.** Where the record and the slot can disagree after a cut, the image-state classifier gives an answer on the safe side (U5, cases PC7 and PC8).
4. **A lost record is not fatal.** If both units are invalid, the outcome is unknown (`record_lost`), the image state is untouched, and the agent still works (TR5). The cost is that a revert is reported as nothing.
5. **A stale record is harmless.** Cases 3 and 4 of the classifier give `NONE` for a slot that was reused, or that holds a confirmed image. The record is replaced by the next attempt and cleared by an acknowledgement. It is not required to clear it.

The alternative (A) is for a product that always has a transactional volume and does not want a reserved area. The port allows it, and the work package would not build it.

## U3. Version policy

The rule is I4 and I5 of the image-state record: **strictly newer** than the running image, compared on major, minor and revision, and the build number is carried and never compared. It is the pure function `crux_image_version_compare()`, and the agent adds no second rule.

| Check | Input | Where it runs | Refusal |
| --- | --- | --- | --- |
| VP1 | The candidate's header version against `running_version` of the boot record. `running_version` is read from the running slot's header in flash, not from a compiled-in constant, as the image-state record requires. | TR6, **before any erase or write** (owner decisions 4 and 5) | `NOT_NEWER` for equal or older |
| VP2 | The version in the slot's header against `running_version` | TR12 (read-back) | `FAILED(verify)` |
| VP3 | The same compare, on what is in flash | Inside `crux_image_request_test()` (TR13), the last check before the bootloader decides | `ERR_NOT_NEWER` |
| VP4 | One attempt at a time. `BEGIN` is refused while the state is `TESTING` or any state of an attempt. `crux_image_request_test()` also refuses while the running image is on trial (`ERR_NOT_CONFIRMED`). | TR6, TR7 | `BUSY`, `NOT_CONFIRMED` |

Consequences:

- The policy compares with the **running** image, not with the standby one. A candidate that is older than the standby image and newer than the running image is accepted.
- There is **no force path** in the agent. A reflash of the same version uses a development tool, as M8 does under owner decision 13.
- The policy gives **no hardware anti-rollback**. It prevents an installed downgrade through this path only. A device that was set back by a development tool, or by service, compares against whatever runs. Hardware-backed rollback protection is owner decision D4, answered as "application-side check only until D1", and M9 declares the level it reaches.
- A persisted "highest confirmed version" floor is a possible addition. It would catch a device that was rolled back outside this path. It is not proposed, because D4 keeps the application-side check as the level until the owner decides on the closed configuration.
- The vectors (major, minor and revision boundaries, the 16-bit revision, equal, and a build number that differs) are table cases V1 and V2 of the image-state conformance list. The agent adds the checks VP1 to VP4 as cases of its own.

## U4. The staging path

### Who erases and writes

The **update agent** erases and writes the staging slot, through the slot port. The image-state contract does neither (I2). The agent chooses the slot: it is `inactive_slot` of the boot record, and the slot port refuses any other. Nothing in the agent writes the running slot except TR14, through `crux_image_confirm()`.

### The precondition

Before the first image byte is written, **every byte of slot X, trailer included, reads as the erased value**. A stale trailer with good magic and `image_ok` set makes an image look confirmed to the bootloader (Inference, [image-state record](image-state-contract-proposal.md#behaviour)). TR9 therefore erases only the sectors that are not blank, header sector first, and ends with a blank check of the whole slot, with the erased value taken from `flash_area_erased_val()` (`Z:include/zephyr/storage/flash_map.h`:352, Verified on pinned source). This keeps the precondition and avoids a whole-slot erase when the slot is already mostly blank. Erase time of a 3 MiB slot has not been measured, and owner decision 17 keeps the 3 MiB slot until it has (Not verified).

The header sector is erased first so that a cut during the erase leaves a slot whose header is blank, which the table of slot states reads as `EMPTY` whatever the trailer holds (Inference, from the slot-state table of the image-state record).

### Input path

The agent takes a **source** with a known size and random access. It does not name a transport, a file system or a protocol.

- A network adapter receives the whole image into an SDRAM buffer and hands the agent a memory source. This is variant (c) of the investigation: receive, check, then write NOR in one bounded phase ([staging medium](../boot-update-investigation.md#staging-medium)). The SDRAM is 32 MiB and a slot is 3 MiB (Verified in repository). The buffer must not overlap the application's own footprint in SDRAM, which is a composition matter.
- A File-service source reads an image file from a volume. The agent reads it twice, once to verify and once to write. Because the second read can differ from the first (another writer, a changed card), the read-back at TR12 compares the hash of **the slot's bytes** with the hash that the signature check used. A change between the two reads is caught there.
- A test source serves bytes from memory, and can change them between reads.

mcumgr is not an input of this proposal (Q3 of the image-state record).

### Gates, and what is verified before the first erase

TR6 reads the source once, front to back, and refuses unless all of these hold. Gates G1 to G7 are the agent's own sanity limits. What the bootloader itself checks of them was not read here (Not verified), and the agent does not rely on the bootloader for any of them.

| Gate | Rule | Why |
| --- | --- | --- |
| G1 | The header magic is the image magic, and the header size equals the composition's configured header size (the trial used `--header-size 0x400`, Verified by build in the boot investigation). | A wrong file is refused before any write. |
| G2 | The header flags mark a RAM-load image, and its load address equals the composition's configured SDRAM address. | A mismatch would be copied to a wrong address by the bootloader (Inference). |
| G3 | The total length from the header and the image's trailing metadata equals the source size, with no extra bytes. | An image that carries a trailer, as the padded, confirmed image does, is refused. |
| G4 | The total length is at most the slot capacity (the slot size minus the trailer area, reported by the slot port). | The image must not reach the trailer. |
| G5 | The version policy VP1 of U3. | Owner decisions 4 and 5. |
| G6 | The SHA-256 of the image matches the hash in its metadata. | Integrity. |
| G7 | The signature in its metadata verifies over that hash with the composition's public key (ECDSA P-256, through PSA Crypto). | #297 asks for it before the staging write. |

The build writes an unconfirmed signed image and a padded, confirmed one ([boot composition](../boot-composition.md)). G3 and G4 refuse the padded one, because it is the slot size and carries the trailer. The agent stages only the unconfirmed one.

Three notes on what these gates leave open:

- **A public key must be supplied.** The composition passes the public half of the signing key, or its hash, to the verify provider. How the key reaches the application is a composition input that is not decided here. Only a development key exists before a product decision (plan section 3). No private key is involved.
- **The check duplicates, and does not replace, the bootloader's.** The bootloader verifies the signature at every boot (T0 in the plan). The agent's check refuses a bad image early, before an erase, a write and a reset. If the agent had no verify provider, the safety of the device would not change: a bad image is refused at validation and reverted. The cost would be the cycle of erase, write and reset. #297 nevertheless asks for the signature check, so the verify port is required in this proposal.
- **MCUboot's own validation function is not used.** Linking bootutil's image validation into the application would bring the bootloader's crypto configuration into it. D9 keeps MCUboot's bundled tinycrypt, and the application verifies with PSA under ADR-0006. This is Inference, and the work package's first step is to confirm that the metadata layout can be parsed with a small reader. The alternative is to call bootutil's validation function in the provider.

### Write order

1. **Body first, header last** (TR10, TR11). A half-written image has a blank header and reads `EMPTY`, so the bootloader has nothing to erase. With the header first, a cut at any point leaves a slot with a valid header and no trailer, which is `STAGED`: the bootloader erases all of it at the next reset, during its own execution from NOR, and #165 blocks that on hardware. Header-last turns that case into the narrow window between TR11 and TR13. Whether the header's first field is the magic, and whether a torn header can look valid, were not read at the pin (Not verified). A torn magic is invalid, and a torn rest of the header can only matter if the magic is whole, which is written last in the header (Inference). The `native_sim` and board cases of U7 test it.
2. **Read-back** (TR12): the hash of the slot's bytes, the version, and `crux_image_slot_get(X)`.
3. **Record and request** (TR13).

A write that is not a multiple of the flash write block is padded with the erased value (Inference, from `flash_area_align()`, `Z:include/zephyr/storage/flash_map.h`:264). The trial build reports a write alignment of 1 for NOR (Verified by build, [boot investigation](../boot-update-investigation.md#mcuboot-against-the-adoption-criteria)). A 512-byte write block on eMMC is a driver matter that is Not verified.

The staging slot while an attempt runs has **no standby image**: TR9 erased it. The running image is intact and confirmed, so the device keeps a bootable image. The standby copy of the previous image is lost until the next successful confirm, and the declared recovery says so (U6).

## U5. Power-interruption cases

`R` is the running slot, confirmed, with version `v_old`. `X` is the inactive slot. The candidate is `v_new`, strictly newer. Before the attempt, `X` is normally `EMPTY` or `STANDBY_CONFIRMED` (an older image). After an earlier attempt it can also be `TRIED`, `PENDING_TEST` or `STAGED`. From the header erase of TR9 on, the outcomes below hold for these as well, because TR9 erases whatever is there. For the earlier cut points (PC0 to PC3, before that erase), a prior `TRIED` slot or a newer `STAGED` slot is erased whole by the bootloader at that reset, which is a bootloader erase from NOR (#165), and ends `EMPTY`. A prior `PENDING_TEST` slot may be selected again and boot on trial: the agent then starts in `TESTING`, and the classifier gives case 3 (`NONE`) because the record names another version. The rows PC0 to PC3 describe the usual case, where X is `EMPTY` or `STANDBY_CONFIRMED`. A power cut is a reset: the bootloader runs first, then the agent starts and TR2 to TR5 derive the state. "Case n" is the numbered case of the outcome table in [Boot record and outcome](image-state-contract-proposal.md#boot-record-and-outcome). All results are Inference from that record and from the transition table above. **None has been run on a board or a power fixture** (Not verified).

| ID | Cut point | Slot X and record before the restart | What the bootloader does at the reset | At the next start: slot X, outcome | Recovers by itself? |
| --- | --- | --- | --- | --- | --- |
| PC0 | During the checks of TR6, or before `BEGIN` | Unchanged | Nothing | Unchanged. The previous record gives its own outcome or `NONE`. | Yes. The caller sends the image again. |
| PC1 | During the record write of TR8 | Slot unchanged. The torn record is rejected, so the previous record stands. | Nothing | Unchanged | Yes, provided the store contract of U2 holds |
| PC2 | After TR8, before the erase | Slot unchanged. Record `{X, v_new, requested = false}`. | Nothing. A standby image is older than `R` and is not selected. | `STANDBY_CONFIRMED` gives `NONE` (case 4). `EMPTY` gives `NOT_BOOTED` (case 5). | Yes |
| PC3 | During the erase of TR9 | Header sector erased first, so the header is blank (`EMPTY`). A cut before the header sector is erased leaves the old image whole (`STANDBY_CONFIRMED`) or the slot `EMPTY`. A torn erase of the header sector is covered by the torn-header assumption (Not verified). Record as PC2. | Nothing. An older image is not selected, so it is not erased. | `NOT_BOOTED` (case 5), or `NONE` (case 4) if the old image is whole | Yes. The next attempt's TR9 erases what is left and blank-checks the trailer. |
| PC4 | During the body write of TR10 | Header blank: `EMPTY`. Record `requested = false`. | Nothing | `NOT_BOOTED` (case 5) | Yes. The attempt is repeated from TR6. |
| PC5 | During the header write of TR11 | A torn header: `EMPTY` (Inference). Record `requested = false`. | Nothing | `NOT_BOOTED` (case 5) | Yes |
| PC6 | After TR11, during TR12 or TR16, before the record write of TR13 | `STAGED`, a complete image with no trailer. Record `requested = false`. | **Erases the whole slot X** in its own execution from NOR, because the image is newer and the magic is not good. #165 blocks this on hardware. | `EMPTY`. `NOT_BOOTED` (case 5). | Yes. The received image is lost and must be received again. |
| PC7 | After the record write of TR13, before the request writes | `STAGED`. Record `requested = true`. | Erases the whole slot X, as in PC6 | `EMPTY`, and the record says `requested`: **`REVERTED` (case 7) for an image that never ran.** This is the window that the image-state record states. The error is on the safe side: the agent offers a retry. | Yes. The report is wrong in this window. |
| PC8 | During the magic write of the request (TR13) | Torn magic, so the slot's trailer is bad. Record `requested = true`. | Magic not good, so it erases the whole slot X | `EMPTY`. `REVERTED` (case 7), as PC7. | Yes |
| PC9 | After the magic, before the swap information (TR13) | `PENDING_TEST` (R8 of the image-state conformance list). Whether the swap information matters for RAM load was not read (Not verified). Record `requested = true`. | Selects X, writes `copy_done`, loads and validates it | Running slot is X. `TESTING` (case 2). | Yes. The agent starts in `TESTING`. |
| PC10 | After TR13, in `WAITING_RESET`, before the reset (or a reset by anything else) | `PENDING_TEST`. Record `requested = true`. | As PC9 | `TESTING` (case 2) | Yes |
| PC11 | During the bootloader's `copy_done` write | The write is logged and ignored if it fails (image-state record). The slot stays `PENDING_TEST`, or `copy_done` is set. | Loads and validates the image | `TESTING`. The slot-state row "running, `copy_done` unset" is treated as on trial. | Yes |
| PC12 | The bootloader refuses the image (validation fails). This is not a power cut. | `TRIED`: magic good, `copy_done` set, no `image_ok`. The previous image runs. | Does not erase it in this boot. It erases the slot at the **next** reset. | `TRIED`, then `EMPTY`. `REVERTED` (case 7). | Yes. The outcome is reported. A retry needs the next reset first, or TR9 erases it. |
| PC13 | A cut or a reset in `TESTING`, before the confirm | X has `copy_done` set and no `image_ok` | Erases the whole slot X and runs `R` | `EMPTY`. `REVERTED` (case 7). | Yes. The previous image runs. |
| PC14 | During the bootloader's erase of X (PC6, PC7, PC8, PC13) | The bootloader's erase order was not read (Not verified). If the header sector goes first, X reads `EMPTY`. If another sector goes first, X keeps a valid header with a bad magic. Part of the old image remains either way. | `EMPTY`: not selected. Otherwise: erased again at the next reset, for the same reason as the first erase | `EMPTY`. Outcome as in the row that led here. | Yes. TR9 of a later attempt erases what remains. |
| PC15 | During the confirm write of TR14 | `image_ok` is set, not set, or torn. How the bootloader reads a torn flag was not read (Not verified). Inference: a flag that is not set is not confirmed. | Confirmed: runs X. Not confirmed: erases X and runs `R`. | `CONFIRMED` (case 2), or `REVERTED` (case 7) | Yes. A healthy image that lost its confirm is reverted, and the attempt is repeated. |
| PC16 | After the confirm, before TR15, or during the record clear of TR15 | Record unchanged, or the previous record stands | Nothing | `CONFIRMED` (case 2) each start, until acknowledged or replaced | Yes. Reported again, harmlessly. |
| PC17 | A request that failed in TR13 after the record was set to `requested = true`, then TR17 and TR16 (or a cut or reset during TR16) | Slot invalidated (`EMPTY`), or still `STAGED` or `INVALID`. Record `requested = true`. | If the slot is not `EMPTY`, erases the whole slot X, as in PC6 | `EMPTY`. **`REVERTED` (case 7) for an image that never ran**, at every start until acknowledged or replaced. In the same boot the caller already got `FAILED`. The reporting caveat is that of PC7. | Yes. The report is wrong in this window. |

What the table says in short:

- **No cut point loses the running image or leaves the device without a bootable image.** The running slot is written only by TR14, and a torn confirm falls back to the previous image.
- **Cut points PC6, PC7, PC8, PC13, PC14 and, when the slot is not `EMPTY`, PC17 involve a bootloader erase of up to 3 MiB while it executes from NOR.** Hardware evidence for them needs #165 first.
- **A staged image does not survive any reset** (PC6, PC7). A product that wants to stage now and reboot later must request the test boot right away and hold only the reboot. Any reset in between then boots the image on trial.
- **One outcome is wrong by design:** PC7 reports `REVERTED` for an image that never ran.
- **The reversed order (request first, record second) is not better.** A cut between the two leaves `PENDING_TEST` and a record with `requested` false. The image boots, and while it runs the classifier reports it correctly (case 2). If it then reverts, the classifier reports `NOT_BOOTED` (case 5) for an image that ran, which is less useful than the `REVERTED` of the recommended order.
- **A three-valued marker removes PC7.** Write "requesting" before the request and "requested" after, and let the classifier read the slot. It needs a change to the attempt type of I3 and an extra record write. It is not proposed now.

The agent recovers by itself in every row, in the sense that the next start derives a consistent state and the next attempt can begin. In rows PC6, PC7, PC8 and PC13 the effect of the interrupted attempt is the loss of the staged or tested image.

Cases that remain with the board and the power fixture: whether a torn write of the header, the magic or a flag reads as assumed; whether the eMMC cache keeps these writes in order; and the real duration of each erase. U7 lists them.

## U6. Declared recovery

M9 declares what the update path recovers by itself, and what it leaves to service. This is a declaration, not new scope. Each row is software-derived (Inference) until a board run (Not verified).

| Situation | What recovers it | Where it is evidenced |
| --- | --- | --- |
| A failed update before the request (a bad image, a failed erase or write, a failed read-back) | The agent ends in `FAILED`, invalidates the slot if it can (TR16), and the running image is untouched. A new attempt starts from `BEGIN`. | PC0 to PC6, and PC17 for a request that failed after the record was set (reported later as `REVERTED`), Host and `native_sim` |
| A corrupted or wrongly signed image after the request | The bootloader refuses it at validation and the previous image runs. The next reset erases the slot. The agent reports `REVERTED`. | PC12 |
| An image that boots and is not confirmed, including a crash loop of the new image | The next reset erases it and the previous image runs. One attempt gives one revert, never a loop. | PC13 |
| Repeated reboots without a confirm | As above. Each reset after the first finds the previous image. | PC13 |
| A lost or torn attempt record | The agent starts with no record. The image state is untouched. A revert is then reported as nothing. | PC1, TR5 |

What stays **service recovery** (owner decision D7: keep it, and decide again after Phase 3):

- A damaged bootloader, and a device that has no valid image in either slot: the boot ROM serial downloader, by service. The bootloader is a single copy that is not field-updatable (#299, and the owner's decision of 7 November 2026).
- Corruption of the running image in flash while the other slot is empty. The bootloader's validation then fails on every boot. A standby image would save the device, and during an attempt there is none (U4).
- A development key or a key change. No key operation is proposed.

M9 also declares the levels the issue asks for: single bootloader copy and recovery by service, software-only anti-rollback (D4), and the root-of-trust level T1 of the plan, with the verification state of each. The bootloader version enters the boot record as I9 says. This proposal adds nothing to those declarations.

## U7. Test strategy

Three levels, as in I8. Only the first two are planned. The third is listed so the owner can see what software cannot show, and needs **separate approval** for each hardware task (AGENTS.md).

| Level | What it shows | How |
| --- | --- | --- |
| Host | The transition table: every state and event pair, including the refused ones. The gates and the version policy, with vectors (the build number ignored). The record port's store contract, with a cut at every operation. | Fakes of the ports. A flash fake counts operations and cuts at the n-th. The hand model of the bootloader is the table of [what the bootloader leaves behind](image-state-contract-proposal.md#what-the-bootloader-leaves-behind), run between restarts. For every cut point every cut point of U5, PC0 to PC17,, the suite checks the resulting slot state, the outcome and the recovery against U5. Verify cases use known-answer vectors with public test keys. A source that changes between two reads must give `FAILED(verify)`. An image that reaches the trailer must be refused. |
| `native_sim` | The same table over the real bootutil functions on a flash simulator, the real NVS provider, the real PSA verify provider, and the image-state provider. | A full update, a refused image and a revert, end to end, with the hand model between resets. That the Zephyr flash simulator can inject a cut at the n-th operation was not checked (Not verified). If it cannot, a thin layer in the test image does it. |
| Board and power fixture | See the list below. | Not planned. Each needs its own approval, a saved image of the boot medium, and a proved recovery path first ([plan, section 9](secure-boot-development-plan.md#9-validation-and-evidence)). |

`native_sim` results are software evidence only (ADR-0005). They say nothing about the board.

**Board and power-fixture items** (listed, not planned):

- The shared boot data reaching the SDRAM-loaded image (T4 of the image-state list), and the bootloader version in the record (T5).
- Test, confirm, reboot, revert and the refused image, on the real bootloader (T1 to T3), including the second-reset erase.
- Every cut point of U5 with a controllable power fixture, in particular PC3 to PC8, PC13 and PC15, and the torn header, magic and flag assumptions.
- Whether an erase of the header sector alone makes the slot invisible to the bootloader, and the order in which the bootloader erases a slot.
- The duration of a 3 MiB erase and of the application's NOR writes, the watchdog behaviour, and the bus-master and cache items of the investigation (network and DMA activity while the agent writes).
- The bootloader's erase under execution from NOR ([#165](https://github.com/wonny-labs/crux-pilot/issues/165)) before any step in which the bootloader writes.
- NVS on the flash device of the board, and the record medium's behaviour for eMMC: the flush ordering, the 512-byte write block and the trailer alignment (T7, after the eMMC driver and a target exist).

## U8. Proposed work package

**This is a proposal. Implementation is not approved.** Publishing it, or an issue for it, authorises nothing (AGENTS.md). It would need its own scope approval, and the owner decisions below.

### Title and goal

Image state contract and update agent, Host and `native_sim`: `crux/image_state.h` with its Host double and Zephyr provider, and the update agent of U1 to U6 with its fakes and providers. It serves #297 (M9) and the plan's Phase 2. It targets the #297 criteria on conformance cases and the software part of the boot-result record. It does **not** meet the criteria that need a board.

### Scope

1. **`components/image_state/`.** The public header `crux/image_state.h` (target `crux::image_state`), the pure functions (version compare and the outcome classifier), a Host provider as a test double with its controls outside the public header, a Zephyr provider over bootutil, and the conformance suite of the image-state record (S, B, R, C, V and O cases, and N1 on `native_sim`). Experimental, as I7 says.
2. **`components/update_agent/`.** The transition table and its driver, the version policy and the gates, the five ports with Host fakes, the record port with an NVS provider (and the A/B fallback if NVS does not fit), the slot port over `flash_area_*`, a verify provider over PSA Crypto, memory and test sources, and a status snapshot. The public header name `crux/update_agent.h` and target `crux::update_agent` are proposals. They are unique among the headers at this head (checked against the component list in `CMakeLists.txt`). Experimental.
3. **Tests, test-first** (AGENTS.md): U7's Host and `native_sim` levels, build checks that keep bootutil headers private to the provider, and usage-target checks like those of the other components.
4. **Documents:** the component's contract text, and an evidence record under `docs/evidence/` for the results, as a new file.

### Exclusions

- No transport: not mcumgr, HTTPS, SFTP or the firmware service, and no access check (#191, #196, the firmware service of the management design).
- No permanent request, no bootloader update, no withdraw, no multi-image and no more than two slots.
- No eMMC provider and no eMMC case. They wait for the driver decision (plan D2) and a target.
- No hardware: no flash, no reset, no power fixture, no board run. No key, no fuse, no tag. A development public key may be used only as a test vector, as the build check already does with the public test key.
- No change to the M8 composition files except the inputs the Zephyr provider needs (data sharing, retention, the bootloader information node), listed in the image-state record. Accepted evidence stays unchanged. The composition files are kept identical to `docs/evidence/boot-update/trial-inputs/` by `tests/build/test_boot_composition.py` ([boot composition](../boot-composition.md)), so a change to them, or a new record partition (W3), would need that evidence and its test addressed first. The package would stop and ask.
- No adoption of the contract as Unstable. I7 sets the condition: the agent and one more consumer, and the M9 target evidence.

### Dependencies

| Dependency | State at this head |
| --- | --- |
| #296 (M8 composition) | #297 lists it as "merged". Parts of WP1a are merged, and no board evidence exists. The Host and `native_sim` work needs only the composition inputs that exist. Whether to start before #296 closes is decision W2. |
| #297 | The issue. Its criteria on board evidence stay open after this package. |
| #165 | Needed before any step in which the bootloader writes NOR on hardware. Not needed for Host or `native_sim`. |
| #142 (PSA Crypto) | Qualified on Host and `native_sim`. Compile-only on RT1060 ([qualification record](../psa-crypto-qualification.md)). |
| I2, I3, I5, I6 of the image-state record | Open at this head. The package follows them, and a change to a row changes the package. |
| ADR-0002, 0003, 0004, 0005, 0006 | Accepted. The agent owns no thread and uses no frozen header. Its lock is the narrow internal one. It adds no crypto dependency beyond the pinned PSA providers. |

### Acceptance criteria

The package is done when all of these hold, and the results are recorded against the revision:

1. The conformance cases of the image-state record (S1 to S12, B1 to B4, R1 to R7, C1 to C3, V1, O1 to O8) pass on Host, and the cases marked `native_sim` (including N1 and V2) pass on `native_sim`. R8 passes with its Host fault injection.
2. The transition table is tested for every state and event pair. Every cut point of U5 has a case that runs on Host and, where the simulator allows, on `native_sim`, with the expected slot state, outcome and recovery.
3. The version policy refuses equal and older images before the first erase or write, and the agent refuses an image that reaches the trailer, one with bytes after its end, one with a wrong load address, and one whose signature or hash does not verify. Each leaves slot X untouched.
4. A source that changes between the two reads is caught at TR12.
5. The record port satisfies its store contract with a cut at every operation, for the NVS provider and for the A/B fallback if it is built.
6. The public headers pass the existing checks (format, analysis, dependency boundaries), include no Zephyr, MCUboot or bootutil header, and carry the Doxygen contract that CONTRIBUTING.md requires.
7. The evidence record states, for each #297 criterion, whether it is met by Host, `native_sim`, or not at all. It says that no board, power-fixture or eMMC result exists.
8. No claim of boot, revert or power-cut behaviour on hardware is made.

### Protected paths it would touch

None is certain. The following are the candidates, and each needs the owner's explicit approval of that change (AGENTS.md, protected paths). A new check script and a new evidence record may be added within the task. Accepted evidence is not changed.

| Path | Why it might change |
| --- | --- |
| `scripts/` | A new runner for the new suites (a new script is allowed). AGENTS.md says an approved work package also covers edits to "the test runner of a component that it changes", as long as no suite, board, build option or warning flag is removed. |
| `.github/workflows/` | A job for the `native_sim` suites, if the existing jobs do not run them. An edit of an existing workflow needs explicit approval. |
| `CMakePresets.json` | Only if a preset must be added. The package would try not to. |
| `docs/evidence/` | A new record. No edit to an accepted one. |
| `AGENTS.md`, `CLAUDE.md`, `.claude/`, `CONTRIBUTING.md`, `tools/`, `doc-links.toml`, `lychee.toml`, `cmake/CruxConsumerBoundary.cmake`, `docs/baseline.md`, `.clang-format`, `.clang-tidy` | **Not expected.** The package would stop and ask if one turned out to be needed. |

The pull request would list every changed protected file from `git diff --name-only --no-renames origin/main...HEAD`, with the approval, as AGENTS.md requires.

### Review plan

Three Draft pull requests in order, each with its own review: (1) the contract, the pure functions, the Host double and the suite; (2) the agent core, the table, the fakes and the Host cut-point suite; (3) the Zephyr providers, the record provider, the verify provider and the `native_sim` suite. Each is reviewed by the `reviewer` agent (a read-only model that did not author it) on the exact head, with the base and head SHAs, the diff, the acceptance criteria and the check results, and each gets one fix round and one independent re-check if the verdict is `REVISE`. `ESCALATE` stops the work. A reviewer `PASS` satisfies only that review gate. It is not merge approval: merging needs the owner's explicit authorisation (Gate 2) for each pull request, as AGENTS.md requires. CI runs the full Host checks, because a local emulated run took hours. Independent material review applies to any protected-path change.

### Decisions the owner needs to make for it

Every row is a recommendation. None is decided.

| ID | Decision | Recommendation | Reason | Alternative |
| --- | --- | --- | --- | --- |
| W1 | Approve the scope of U8 as a bounded work package: the three Draft pull requests, with the exclusions above. | Approve, after the owner decides U1 to U7 | The design decisions fix the scope. Without them the package would decide them itself. | Approve only the first pull request now |
| W2 | Start the Host and `native_sim` work before #296 is closed. | Yes. It needs only composition inputs that exist, and it produces no board claim. | The contract and the table are the longest part, and none of them needs a board. | Wait for #296. It delays M9 behind board evidence that is not started. |
| W3 | Reserved record area: revise owner decision 17 for the `storage` partition, or add a partition. | Add a small dedicated partition, and leave `storage` as it is. | `storage` has no owner by decision. A new partition leaves that row intact and keeps the record separate. | Use `storage`. It saves a partition and needs the row revised. |
| W4 | Public headers: `crux/image_state.h` and `crux/update_agent.h` as Experimental. | Yes, both, with the I7 condition for folding the contract into the agent | A public header is what the firmware service of #191 and #196 would call. | Make the agent internal to a firmware service, and keep only `image_state.h` public |
| W5 | The agent's signature check is required, and its public key comes from the composition. | Required, as #297 states | #297 says the image is written only after the check. | Make the verify port optional and rely on the bootloader. It is safe, and it costs a failed cycle for a bad image. |
| W6 | Record medium for products whose volume is always present: allow a File provider behind the record port later. | Not now. Decide it with the first such product. | Nothing needs it yet, and the port keeps the door open. | Build the File provider in the same package |
| W7 | The attempt type of I3 keeps its boolean `requested`, and PC7 stays a stated window. | Yes | A three-valued marker changes an open row for a window that is a few writes wide and on the safe side. | Change I3 to a three-valued marker now |

## Consistency with the accepted decisions

- **[ADR-0002](../decisions/0002-platform-direction-zephyr-execution-crux-services.md) and [ADR-0003](../decisions/0003-p9-result-services-keep-narrow-thread-sync.md).** The agent core has no Zephyr, board or bootutil header and owns no thread. Flash areas, NVS and PSA sit in providers. It uses none of the frozen Thread, Sync, Queue and Serial headers. Its one lock, around the status snapshot, is the narrow internal one that ADR-0003 keeps inside Crux services.
- **[ADR-0004](../decisions/0004-product-composition-of-management-services.md).** A product reaches the agent through a public `crux::` target. The management adapters check access first, and no access check lives in the agent.
- **[ADR-0005](../decisions/0005-native-sim-test-watchdog-for-system-consumers.md).** `native_sim` cases are software evidence only.
- **[ADR-0006](../decisions/0006-cryptographic-dependency-policy.md).** The agent adds no cryptographic dependency. Its verify provider uses the pinned PSA providers. D9 keeps MCUboot's bundled tinycrypt in the bootloader, and the two are separate.
- **[Image state record](image-state-contract-proposal.md).** This proposal keeps its order of the record and the request, its slot states and its seven outcome cases. It adds no operation to the contract: the slot port's capacity and the staging writes belong to the agent.

## Limits and Not verified

- Every result about the bootloader is what the code allows, not what a board does. No board, power fixture or eMMC result exists.
- The Zephyr tree read was a checkout outside the repository, with the commit `dccb095` read by `git show`. MCUboot's sources were read for the image-state record and not again here. What the bootloader's header check includes, how it reads a torn flag, and whether the swap information matters for RAM load are Not verified.
- NVS was read in its documentation and one source file, not run. NVS on the board's flash and on the eMMC driver is not shown.
- Erase and write durations, and the watchdog behaviour during them, are not measured.
- Whether the header sector's erase hides a slot from the bootloader, and header-last ordering on a real device, are Not verified.
- The path by which the application obtains a signature public key is not decided.
- Multi-image and more than two slots are out of scope.
- The image-state rows I2, I3, I5, I6, I8 and I9 are open at the base. This proposal changes if the owner changes them.

## Open questions

| # | Question | Recommendation |
| --- | --- | --- |
| Q1 | Does the agent count as a Crux service or as product code (plan section 8)? | A Crux service with a narrow public header (W4) |
| Q2 | Does NVS fit the board's flash and the eMMC driver? | Answer it in the work package's `native_sim` run and a later board run, with the A/B record as the fallback |
| Q3 | How does the application obtain the public key for the signature check? | A composition input. Decide it with the first product composition. |
| Q4 | Should an erase of the header sector be treated as enough to hide a slot? | Test it on a board before relying on it. TR16 is best effort until then. |
| Q5 | Is a withdraw of a requested image needed? | No. Not confirming reverts it. |

## Process record

- Author: Claude Code, model `claude-sonnet-5-5`. No code was written and no tool was installed. The review result and the checks are recorded in the pull request description.
- Search first: no package or tool was added. The only existing facility considered for the record is Zephyr NVS, read in its documentation and one source file at the pin. No file was written under `docs/adr/`.
- Sources read: the documents linked above, the issue text of #297, and the Zephyr files named in the text, through `git show dccb095:<path>` in a checkout outside the repository. None is copied.
- No other file of the repository was changed. The image-state record is only linked.
