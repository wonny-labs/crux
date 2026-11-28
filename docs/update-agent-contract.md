# Update agent contract

For integrators and reviewers of `components/update_agent`. It says what the agent does, what the core needs from a composition, and what is verified.

The header carries `Status: Experimental` (row W4 of the [update agent design proposal](plans/update-agent-design-proposal.md)); what that tier means for your code, and what is verified, is in the [readiness table](component-readiness.md#readiness-table). This is pull request 2 of the U8 work package: the agent core, its Host fakes and the Host suites. No Zephyr provider, no attempt-record store on a medium, no PSA verify provider and no `native_sim` run exist yet. There is no board or power-fixture result.

Owner: `components/update_agent`. Public header `<crux/update_agent.h>`, usage target `crux::update_agent`, build option `CRUX_BUILD_UPDATE_AGENT` (needs `CRUX_BUILD_IMAGE_STATE`). The header includes `<stdbool.h>`, `<stddef.h>`, `<stdint.h>` and `<crux/image_state.h>` only.

## What it does

One attempt at a time, on the caller's thread. The agent never resets the device and never makes a permanent request.

| Call | Rows | What it does |
| --- | --- | --- |
| `crux_update_start()` | TR1 to TR5 | Starts the [image state contract](image-state-contract.md), loads the attempt record and classifies the outcome. Writes nothing. A failed contract start leaves the agent `UNAVAILABLE`. |
| `crux_update_begin()` | TR6 to TR13, TR16, TR17, TR19 | Checks the whole image, then stages it in the inactive slot and asks for a test boot. |
| `crux_update_cancel()` | TR16, TR19 | Stops a running attempt between two sector operations, before the request. |
| `crux_update_confirm()` | TR14 | Confirms the running image on trial. |
| `crux_update_acknowledge()` | TR15 | Clears the attempt record after an outcome or a failure. |
| `crux_update_status_get()` | | A consistent snapshot, readable from another thread during an attempt. |

The states, events and transitions are the table in section U1 of the proposal. The power-interruption cases are the table in section U5.

### Checks before the first erase or write

`crux_update_begin()` reads the source once, front to back, and refuses before any medium operation unless all of these hold. A refusal returns its code and leaves the state as it was.

| Gate | Rule | Result on refusal |
| --- | --- | --- |
| G1 | Header magic, and the header size the composition configures | `CRUX_UPDATE_ERR_FORMAT` |
| G2 | RAM-load flag set, and the composition's load address | `CRUX_UPDATE_ERR_LOAD_ADDRESS` |
| G3 | Header, body and both metadata areas add up to the source size exactly | `CRUX_UPDATE_ERR_LENGTH`, or `FORMAT` for a malformed area |
| G4 | The image, padded to the write block, ends before the slot trailer | `CRUX_UPDATE_ERR_TOO_LARGE` |
| G5 | Strictly newer than the running image on major, minor and revision; the build number is ignored (U3) | `CRUX_UPDATE_ERR_NOT_NEWER` |
| G6 | The SHA-256 entry matches the digest of header, body and protected area | `CRUX_UPDATE_ERR_HASH` |
| G7 | The ECDSA signature entry verifies over that digest. Required (W5). | `CRUX_UPDATE_ERR_SIGNATURE` |

### Staging order

1. Record `{slot, version, requested = false}` (TR8).
2. Erase every sector that is not blank, header sector first, then blank-check the whole slot, trailer included (TR9).
3. Write the body (TR10), then the header with the write block that holds the magic last (TR11).
4. Read the slot back: digest of every byte, version, and the contract's slot state `STAGED` (TR12).
5. Record `requested = true`, then call `crux_image_request_test()` (TR13).

A failure after the header was written erases the header sector and the trailer sector (TR16, best effort). If that erase fails, the status says `slot_staged`, and the bootloader erases the slot at the next reset.

## What a composition provides

The core includes `src/update_agent_port.h`, a private header that no usage target exports. A composition links one provider of each port.

| Port | Functions | Contract |
| --- | --- | --- |
| Slot | `crux_update_port_slot_*` | Uniform sectors, sector 0 holds the header, trailer at the end. Refuses a slot that is not the staging slot. |
| Record | `crux_update_port_record_*` | `store()` returns true only when the record is durable. After a cut, `load()` returns the new or the previous record, never a mixture (U2). |
| Verify | `crux_update_port_hash_*`, `crux_update_port_signature_verify()` | SHA-256 in two independent contexts. The public key is the provider's input. |
| Progress | `crux_update_port_progress()` | Called between sector operations, for example to feed a watchdog. May call `crux_update_cancel()` only. |
| Image state | `crux/image_state.h` | The public contract and one of its providers. |

The source is the caller's: a size and a random-access read. `crux_update_source_memory()` makes one over a buffer.

## Design choices and their sources

| Choice | Label | Source |
| --- | --- | --- |
| Test boot first, confirm by the application, revert by the bootloader | Standard (not verified here) | MCUboot's design, as the [image state contract proposal](plans/image-state-contract-proposal.md) records it. Not read again for this change. |
| Strictly newer version, checked by the application before any write | Project-specific workaround for a standard requirement (not verified here) | Proposal U3 and owner decisions 4 and 5. The planning record cites RFC 9019 and MCUboot's overwrite-only downgrade prevention; neither was read for this change. |
| Header and metadata layout: magic `0x96f3b83d`, RAM-load flag `0x20`, metadata magics `0x6907` and `0x6908`, entries of a 16-bit type and a 16-bit length, `SHA256` `0x10`, `ECDSA_SIG` `0x22` | Standard (MCUboot image format) | Verified on pinned source: MCUboot `6d3b3d2c`, `boot/bootutil/include/bootutil/image.h`. Restated in `src/update_agent_image.h`, not copied. |
| The signed range is header, body and protected area | Standard | Verified on pinned source for the pure-signature path: `boot/bootutil/src/image_validate.c` at `6d3b3d2c`. That the SHA-256 entry covers the same range on the hashed path is Inference (the hashing function was not read). |
| The agent looks for the SHA-256 and signature entries in the unprotected area only | Project-specific | The bootloader accepts the signature entry in either area (`image_validate.c`). An image that carries it in the protected area is refused, which is the safe side. |
| Header written last, magic block last within it | Project-specific | Proposal U4. Whether a real device tears a write as the Host model assumes is Not verified. |
| Seqlock for the status snapshot, try-lock for the calls | Not verified (no external source read) | The try-lock matches `crux/image_state.h`. A seqlock over atomics is a common reader-never-blocks-writer pattern; no external source was read for it here. |

## What is verified, and by what

**Verified by Host test** on the author's macOS arm64 machine with Apple clang, in a scratch CMake project that holds only the image state and update agent components and their tests. The sanitizer and Linux CI results are recorded in the pull request, not here.

| Suite | What it shows |
| --- | --- |
| `UpdateAgent.gates` | Every gate refuses with no medium operation and the state unchanged; the order of the staging writes; padding to the write block; a source that changes between its two reads is caught at TR12 |
| `UpdateAgent.table` | Every resting state against every event, the refused pairs included; re-entry from inside an attempt is busy; cancel at each phase; each step's failure; a concurrent status reader |
| `UpdateAgent.power_cut` | Rows PC0 to PC17 with their slot state, outcome and recovery, and a sweep that cuts every medium operation of an attempt as landed, torn and lost |
| `UpdateAgent.nodiscard`, `UpdateAgent.boundary` | An ignored result fails the build; the public header and the core name no Zephyr, bootloader, NVS or PSA facility |

The fakes are not real facilities. The digest is not SHA-256 and the signature is not ECDSA: they stand in for the verify port. The bootloader is the image state contract's hand model, not MCUboot. A pass shows that the agent follows its own tables over these fakes, and nothing more.

**Not verified:** the Zephyr providers, NVS as the record store, PSA verification with known-answer vectors, the real bootloader on `native_sim`, how a real device tears a header, magic or flag write, erase durations and watchdog behaviour, and any board or power-fixture case. These are pull request 3 of the work package and the board items listed in section U7 of the proposal.
