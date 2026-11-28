# Image state contract proposal

Status: **Adopted as Experimental by the owner: rows I1 to I7 on 15 November 2026** (I1, I4 and I7 at about 17:25 UTC; I2, I3, I5 and I6 after about 20:00 UTC), **rows I8 and I9 on 28 November 2026** (see [Decisions](#decisions)). This record is documentation only. It changes no code, check, contract or protected path, and #297's acceptance criteria are unchanged. Nothing here approves an implementation: `crux/image_state.h` and its providers need their own work package and scope approval. Issue: [#297](https://github.com/wonny-labs/crux-pilot/issues/297), milestone M9. Baseline: main `7e0a31a4`, Zephyr v4.4.2 `dccb095`, MCUboot `6d3b3d2c38ab20c242e5b9abb04d050086383eb2` (the revision in Zephyr's own `west.yml`, lines 337 to 341). The crux-pilot `west.yml` at this head does not import `mcuboot` (its Zephyr import allow-list names `cmsis`, `cmsis_6`, `hal_nxp`, `littlefs` and `fatfs`), so how MCUboot enters the workspace is a matter for the M8 composition [#296](https://github.com/wonny-labs/crux-pilot/issues/296). This proposal read the upstream sources outside the repository and copies none of them.

It builds on [the boot and update investigation](../boot-update-investigation.md) (rank 1 RAM load with revert, owner decisions 4, 5 and 13, rows B63, B63a and B64), [the bootloader update investigation](../boot-bootloader-update-investigation.md) (boot-result record, bootloader version) and [the eMMC investigation](../boot-emmc-investigation.md) (slots behind a flash-API driver). The platform rule it applies is [Choosing an API](../choosing-an-api.md) and [ADR-0002](../decisions/0002-platform-direction-zephyr-execution-crux-services.md).

## Evidence labels

Labels follow the boot records. `Z:` means Zephyr `dccb095`, `M:` means MCUboot `6d3b3d2c`, both paths under the upstream repository root.

| Label | Meaning |
| --- | --- |
| Verified on pinned source | Read at the cited file and line of the pinned revision. Shows what the code allows, not what a board does. |
| Verified in repository | Read from a crux-pilot file at `7e0a31a4`. |
| Verified by public document | A public specification or vendor page says so. The author's statement, not a Crux result. Read through a search summary, not as a full read. |
| Inference | Reasoned from the rows named. The reasoning is stated. |
| Not verified | Not read, not run, or needs a board. |

## Decisions

On 15 November 2026 the owner approved rows I1, I4 and I7 as recommended, and later the same day rows I2, I3, I5 and I6 as recommended (quotes in [Owner approval](#owner-approval)). On 28 November 2026 the owner approved rows I8 and I9 as recommended, Experimental. The "State" column says which rows are decided. "Impact if rejected" says what the owner takes on. I1 adopts the contract whose three operations, attempt record and fail-closed rule are rows I2, I3 and I6, and I4 compares versions on the basis of I5 (major, minor, revision). All of those rows are now approved, so the adopted decision is the narrow Experimental contract those rows describe. Approving the decisions does not approve any code: see [Owner approval](#owner-approval).

| ID | Decision | Recommendation | Impact if rejected | State |
| --- | --- | --- | --- | --- |
| I1 | Adopt a narrow public image-state contract, header `crux/image_state.h`, with a Linux Host provider and a Zephyr provider. It starts as **Experimental**. | Adopt | Use the slot-aware stock call in each product adapter (Option 2 below). #297's acceptance criterion and the M9 exit evidence for Linux Host and Zephyr conformance cases are revised explicitly, and #191 is revised with them. Every product writes the same adapter and meets the same silent no-ops. | Approved 15 Nov 2026 |
| I2 | The contract has three operations on state: query, request a **test** boot, confirm. It has no permanent request, no staging write or erase, no bootloader update and no events. | Accept | A permanent request skips the application's confirm and gives up the revert. Staging writes belong to the update agent, which needs its own proposal. | Approved 15 Nov 2026 |
| I3 | "Reverted" is an **outcome**, not a slot state. It is derived from the boot record plus an attempt record (slot, version, and whether the request was made) that the update agent persists around the request. The contract defines the attempt type and a pure classifier, and stores nothing. | Accept | The stock shared data and trailers cannot say that an update was attempted and undone (see [what the bootloader leaves behind](#what-the-bootloader-leaves-behind)). Without an attempt record the record can only say "running image, confirmed or not". | Approved 15 Nov 2026 |
| I4 | A test request is refused unless the image in the slot is **strictly newer** than the running image, compared on major, minor and revision. Equal and older are refused. | Accept | Owner decision 4 rejects older. With equal versions the slot number decides, and an equal image in slot 1 is never selected, so the request is a silent no-op (see [version rules](#version-rules)). Accepting equal keeps a no-op case in the update path. | Approved 15 Nov 2026 |
| I5 | The version basis is major, minor, revision. The build number is ignored. A composition must not build MCUboot with the build-number comparison option. | Accept | If the bootloader compares the build number and the application does not, the two can disagree about which image is newer. | Approved 15 Nov 2026 |
| I6 | The provider **fails closed**. If the shared boot data is absent, or the running slot or the running image's trailer is not in an expected state, `crux_image_start()` fails and `crux_image_confirm()` and `crux_image_request_test()` return `CRUX_IMAGE_ERR_NOT_READY`. It never guesses the running slot. | Accept | A guessed slot can confirm the wrong slot. The running image then stays unconfirmed and the next reset erases it. | Approved 15 Nov 2026 |
| I7 | The contract is **Experimental** at adoption. It becomes Unstable only when the update agent and one more consumer use it and the M9 target evidence passes. If no second consumer exists by the end of M9, it is folded into the update agent as an internal interface. | Accept | Unstable at once would promise a one-release notice for a contract that has one provider and no consumer. | Approved 15 Nov 2026 |
| I8 | Test strategy: Host conformance against a controllable provider, `native_sim` conformance with the real bootutil over a flash simulator plus a hand model of the bootloader's select and erase rules, and target evidence for what only a board shows. The Host provider is a test double, not a copy of MCUboot. | Accept | A Host copy of MCUboot's logic would test the copy. Running MCUboot's own simulator in CI was not assessed (Not verified). | Approved 28 Nov 2026 |
| I9 | The bootloader version in the boot record is the version that the **bootloader build** reports, with an explicit "not known" flag. M9's results declare it next to the single-copy, service-recovery level. A product that patches MCUboot sets its own version in the bootloader build. | Accept | The shared value is the build's application version. By default it comes from MCUboot's own `boot/zephyr/VERSION` (2.4.0.0 at the pin, Verified on pinned source; that the build takes its version from that file is Inference), so an unpatched build reports the upstream release number, and a patched one reports the same number unless it sets its own. A record that reads as a product identity would then be wrong. | Approved 28 Nov 2026 |

### Owner approval

**Rows I1, I4 and I7.** The owner approved these in chat with the secure boot session on 15 November 2026 at about 17:25 UTC. The question asked was whether to approve that session's list of four recommendations as recommended, and the answer was "추천대로 승인" (approved as recommended). The secure boot session relayed this to the session that edited this record. The same answer covers rows D2 and D9 of the [secure boot development plan](secure-boot-development-plan.md#6-decisions-the-owner-needs-to-make).

**Rows I2, I3, I5 and I6.** The owner approved these in chat with the secure boot session on 15 November 2026, after about 20:00 UTC (after the change that recorded D9 was merged), as recommended. The answer, as the secure boot session quoted it, was "I2, I3, I5, I6도 추천대로 승인" (I2, I3, I5 and I6 also approved as recommended). The secure boot session relayed this to the session that edited this record. The approved rows, with the open questions and cases of this record that bear on them, say:

- **I2.** The contract has three operations on state: query, request a test boot, confirm. It has no permanent request. The secure boot session's relayed recommendation is to add one only when a consumer needs it. Factory images are permanent through `--pad --confirm` (Q7).
- **I3.** "Reverted" is an outcome derived from the boot record plus an attempt record. The contract defines the attempt type and a pure classifier and stores nothing. Where the attempt record lives stays with the update agent's design (Q2, still open). The known limit stays: a power cut after `requested` was set and before the request writes land reports `REVERTED` for an image that never ran (case O8 of the [conformance cases](#conformance-cases)).
- **I5.** The version basis is major, minor, revision, and the build number is ignored. The composition must not enable the build-number comparison option (the Kconfig option `CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER`, and the macro `MCUBOOT_VERSION_CMP_USE_BUILD_NUMBER` that it sets). How that is enforced is **Not verified** and stays open. No check at this head names the option (Verified in repository).
- **I6.** The provider fails closed (`CRUX_IMAGE_ERR_NOT_READY`) as the row words it. The board case T4 (is the retained shared data intact after the jump, Q4) must run before any other use of the record.

**Rows I8 and I9.** The owner approved these on 28 November 2026 with the answer "추천대로" (as recommended), to a question that recommended accepting both as proposed, Experimental. The answer was given in chat with the coordinating session and relayed to the session that edited this record. The same answer approved rows U1 to U7 and W1 to W7 of the [update agent design proposal](update-agent-design-proposal.md#owner-decisions).

**What the approvals cover.** Each answer covers only the rows marked Approved, as the table words them. Together they approve rows I1 to I9. The answers of 15 November 2026 do not approve any implementation, a change to #297's acceptance criteria or a change to a protected path. Implementing `crux/image_state.h` and its providers needs its own work package and scope approval. No hardware operation is approved. The Draft host prototype (#462) stays as it is. This record reads the approval as covering the decisions, not the exact signatures in [Proposed contract](#proposed-contract), which stay illustrative. The owner's words do not address signatures.

## The question and the short answer

#297 asks whether to adopt a narrow, bootloader-neutral image-state contract (query state, request a test boot, confirm; running, pending, confirmed, reverted) with Linux Host and Zephyr conformance cases, or to use Zephyr's own interfaces directly.

**Recommendation.** Adopt the contract, narrowly and as Experimental. The reason is not neutrality. Only one bootloader and one provider exist, so neutrality stays an untested claim. The reason is that three things the update path needs exist in no Zephyr or MCUboot interface at the pin: a request that marks the **inactive** slot and refuses instead of doing nothing, a boot-result record that includes "reverted", and a pure version rule that the update agent and the bootloader share. Because the Zephyr provider has to contain the slot-aware calls anyway, the contract adds a header, a Host double and the conformance suite, which is what the M9 exit evidence asks for.

The alternative the owner may prefer, to follow ADR-0002 as strictly as possible, is Option 2: no Crux interface, the slot-aware call in a product-owned adapter. It is workable. It moves the conformance cases to each product and revises #297 and #191.

### How this fits ADR-0002

[Choosing an API](../choosing-an-api.md) asks three questions. Image state is not an OS or hardware facility (question 1), so it is not Zephyr-only by that rule. It is a platform service with policy: version rules, confirm timing and the authorised request path (question 2). A product's domain may not call Zephyr, so without a Crux contract each product must define its own port (question 3) and write its own adapter. ADR-0002 keeps narrow Crux interfaces "only where portable consumers need them". **At this head no code in the repository calls any of the functions named here** (Verified in repository: a search outside `docs/` finds none). The consumers are planned, not existing: the update agent of #297, the authorised request path of #191 and #196, and management status. This is the weakest point of the recommendation, and I7 limits the commitment because of it.

## What #297 asks for, and where this record answers

| #297 scope item | Section |
| --- | --- |
| Compare stock `boot_set_next()` with a slot-aware caller and the Zephyr DFU interfaces | [Evidence](#evidence-at-the-pinned-source) and [Options compared](#options-compared) |
| Image identity and image state (running, pending, confirmed, reverted) | [Slot states](#slot-states) and [Boot record and outcome](#boot-record-and-outcome) |
| Rejection of an older image, comparison basis | [Version rules](#version-rules) |
| Boot-result record derived at start, with what the stock shared data carries | [What the shared data carries](#what-the-shared-data-carries) |
| Bootloader version in the record | I9 and the shared-data table |
| Linux Host and Zephyr conformance cases | [Conformance cases](#conformance-cases) |

## Evidence at the pinned source

### The stock calls, for RAM load with revert

RAM load with revert is `CONFIG_MCUBOOT_BOOTLOADER_MODE_RAM_LOAD_WITH_REVERT` (`Z:modules/Kconfig.mcuboot`:270). It does not select `MCUBOOT_BOOTUTIL_LIB_FOR_DIRECT_XIP`, which only direct-XIP with revert selects (`Z:modules/Kconfig.mcuboot`:309-310). The application therefore links the **swap variant** of `boot_set_next()` (`M:boot/bootutil/src/bootutil_public.c`:527-593). In this mode the running slot comes from the shared data, not from the address of the code (`Z:subsys/dfu/boot/mcuboot.c`:76-84 and 111-118).

| Call | Slot it touches | Right for RAM load with revert? | Evidence |
| --- | --- | --- | --- |
| `boot_request_upgrade(permanent)` | Slot 1, always | Only while running from slot 0. From slot 1 it reads slot 1's trailer, finds `magic` good, and `boot_set_next()` writes nothing and returns 0. | Verified on pinned source: `Z:subsys/dfu/boot/mcuboot.c`:405-416, `M:bootutil_public.c`:690-709 and 527-560. The effect is Inference (row B63a of #141, re-read at this pin). |
| `boot_request_upgrade_multi(i, permanent)` | Secondary slot of image `i`, which is slot 1 | Same | `Z:subsys/dfu/boot/mcuboot.c`:418-427 |
| `boot_write_img_confirmed()` | Running slot, from the shared data | Yes. It writes `image_ok` through `boot_set_next(fa, true, true)`. | `Z:subsys/dfu/boot/mcuboot.c`:457-471 |
| `boot_write_img_confirmed_multi(i)` | Primary slot, which is slot 0 | No, when running from slot 1. It confirms slot 0. | `Z:subsys/dfu/boot/mcuboot.c`:473-483, `M:bootutil_public.c`:735-752. Effect Inference. |
| `boot_is_img_confirmed()` | Running slot. A slot without trailer magic counts as confirmed. | Yes. Under revert the bootloader erases a slot whose magic is not good, so the quirk should not arise (Inference). | `Z:subsys/dfu/boot/mcuboot.c`:429-455, `M:loader.c`:2181-2235 |
| `mcuboot_swap_type()` and `_multi` | Reads slot 0 and slot 1 trailers and matches swap tables | Meaning for RAM load not established. The tables describe swap operations. | `Z:subsys/dfu/boot/mcuboot.c`:390-403, `M:bootutil_public.c`:105-150 and 425-492. Inference. |
| `boot_fetch_active_slot()` | Running slot from `BLINFO_RUNNING_SLOT`. Returns 255 if the key is missing. | Yes, if the shared data reaches the application | `Z:subsys/dfu/boot/mcuboot.c`:111-118 |
| `boot_read_bank_header(area, ...)` | Header of the named area: size and version (major, minor, revision, build) | Yes | `Z:subsys/dfu/boot/mcuboot.c`:300-388 |
| `boot_set_next(fa, active, confirm)` (bootutil, declared in `bootutil_public.h`) | The slot `fa` names | **Yes, with `fa` set to the inactive slot for a test request**, and `active` true for a confirm | `M:bootutil_public.c`:527-593 |

`boot_set_next()` on an inactive slot with `active` false and `confirm` false: if the trailer magic is unset it writes the magic, then the swap info with the test type, and writes no `image_ok`. If the magic is already good it writes nothing and returns 0, whatever the other flags say. If the magic is bad it returns `BOOT_EBADIMAGE` (`M:bootutil_public.c`:527-593). The silent success in the middle case is why the contract checks the trailer before it calls.

### What the bootloader does with the result

RAM load with revert, in `M:boot/bootutil/src/loader.c`:

| Step | Behaviour | Lines |
| --- | --- | --- |
| Slots that count | A slot is available if its header is valid. The trailer is not consulted yet. | 2066-2105 |
| Choice | The available slot with the highest version. A later slot replaces the candidate only if strictly greater, so on equal versions the lower slot number wins. | 2115-2140 |
| Version order | Major, then minor, then revision. The build number counts only with `MCUBOOT_VERSION_CMP_USE_BUILD_NUMBER`. | `M:bootutil_loader.c`:200-232 |
| Select or erase | If the magic is not good, or `copy_done` is set and `image_ok` is not, the whole slot is erased and the next slot is tried. Otherwise `copy_done` is written (a failed write is logged and ignored). This runs **before** the image is loaded or validated. | 2169-2235, called at 2295 |
| Load and validate | The image is copied to SRAM and validated there. A load failure removes the image from flash. A validation failure only marks the slot unavailable for this boot. | 2304-2329 |
| Shared data | Written after a valid image is chosen, with the slot number of the chosen slot. | 2443, in `context_boot_go` (2392-2466) |

Source for the same code in this mode: the macro set in `M:boot/zephyr/include/mcuboot_config/mcuboot_config.h`:108-110 and 113.

### What the bootloader leaves behind

All rows are Inference from the table above unless stated.

| Event | Trailer and slot afterwards |
| --- | --- |
| Test request written | Inactive slot: magic good, `copy_done` unset, `image_ok` unset |
| Newer image staged, never requested, reset | The slot counts as available on its header alone and the bootloader selects the highest version. `boot_select_or_erase` then finds the magic not good and erases the **whole slot** (`M:loader.c`:2089-2090, 2115-2140, 2199-2211). The previous image runs. The staged image does not survive the reset, and the slot reads `EMPTY`. |
| Reset, image selected | `copy_done` set before validation |
| Validation fails | The slot is not erased in this boot. It keeps magic good, `copy_done` set, `image_ok` unset, and the previous image runs. The **next** reset finds `copy_done` set without `image_ok` and erases the slot. |
| Booted, never confirmed, reset | The next reset erases the whole slot. The previous confirmed image runs. |
| Confirmed | `image_ok` set on the running slot |
| After an erase | The header and trailer are gone. A slot erased after a revert looks the same as a slot that never held an image. |

**Consequence.** After a revert, or after a power cut that leaves a newer image staged without a request, nothing in flash says an update was attempted, and the two cases look alike. "Reverted" cannot be read from the trailers or the shared data. It needs a record that the application wrote before it requested the test, and a marker for whether the request was made. That is I3.

### What the shared data carries

`boot_save_shared_data()` writes these keys when `MCUBOOT_DATA_SHARING_BOOTINFO` is set (`M:boot/bootutil/src/boot_record.c`:241-399, key numbers in `M:boot/bootutil/include/bootutil/boot_status.h`:111-126). The application reads them with `blinfo_lookup()` (`Z:include/zephyr/retention/blinfo.h`:36-49), which exists only with the output-function option.

| Key | Value | Note | Label |
| --- | --- | --- | --- |
| `BLINFO_MODE` | Operating mode | RAM load with revert reports `MCUBOOT_MODE_RAM_LOAD`. The mode chain has no revert variant for RAM load, so the application cannot tell RAM load from RAM load with revert (`boot_record.c`:270-271). | Verified on pinned source |
| `BLINFO_SIGNATURE_TYPE` | None, RSA, ECDSA P-256, Ed25519 | Usable for the root-of-trust declaration | Verified on pinned source |
| `BLINFO_RECOVERY` | None, serial recovery, DFU | MCUboot's own recovery, not the ROM downloader | Verified on pinned source |
| `BLINFO_RUNNING_SLOT` | Slot number of the chosen slot | The key the contract needs | Verified on pinned source |
| `BLINFO_BOOTLOADER_VERSION` | `APP_VERSION` of the MCUboot **build**, as a four-field version | Present only when data sharing is on and the Zephyr version header is available (`mcuboot_config.h`:431-436). A build without a `VERSION` file gives the Zephyr default (not read). | Verified on pinned source. Default value Not verified. |
| `BLINFO_MAX_APPLICATION_SIZE` and image variants | Largest image the bootloader can load | Not needed by the contract | Verified on pinned source |
| `BLINFO_SECURITY_COUNTER_IMAGE_n` | Security counter | Only with hardware rollback protection, which the Zephyr port does not have at the pin (#141) | Verified on pinned source |

**Not carried:** whether the running image is confirmed, whether a test was requested, and whether an image was reverted. The record derives the first from the running slot's trailer. The other two need the attempt record.

The retention backend, the retained region and the `zephyr,bootloader-info` node were configured and linked in the M8 trial, and never exercised ([#141 row B64](../boot-update-investigation.md#ranked-candidate-modes)). Whether the data survives the jump to the SDRAM-loaded image is **Not verified** (needs a board).

### mcumgr image management

| Point | Finding | Label |
| --- | --- | --- |
| Test request | State write calls `img_mgmt_set_next_boot_slot()`, which is slot-aware: `boot_set_next(fa, slot == active_slot, confirm)` | Verified on pinned source: `Z:subsys/mgmt/mcumgr/grp/img_mgmt/src/img_mgmt_state.c`:630-640, 677-763, 848 |
| Older call path | `img_mgmt_write_pending()` accepts only slot 1 (or slot 3 with two images) and calls the `_multi` request on the secondary slot | `Z:.../zephyr_img_mgmt.c`:418-433 |
| Active slot | `img_mgmt_active_slot()` queries the bootloader only under `CONFIG_MCUBOOT_BOOTLOADER_MODE_RAM_LOAD`. The `RAM_LOAD_WITH_REVERT` mode is not in that condition and falls to the default branch. | Verified on pinned source: `Z:.../img_mgmt.c`:236-266. How the default branch behaves for a RAM-loaded image was not read. |
| Upload target | For one image, the first of slots 0 and 1 whose `img_mgmt_slot_in_use()` is 0. In this mode that function returns "is the active slot", so the target is "not the active slot". | Verified on pinned source: `Z:.../zephyr_img_mgmt.c`:282-330, `Z:.../img_mgmt_state.c`:361-391 |
| Consequence | If `img_mgmt_active_slot()` reports slot 0 while the image runs from slot 1: an **upload** is aimed at slot 1, which overwrites the running image's flash copy and the confirmed fallback (`img_mgmt_slot_in_use()` says slot 1 is free). A **confirm** of the running slot is refused by default (`Z:.../img_mgmt_state.c`:713-717, `IMG_MGMT_ERR_IMAGE_CONFIRMATION_DENIED`), or, without a hash, confirms slot 0 instead (`img_mgmt_state.c`:820-822). With `CONFIG_MCUMGR_GRP_IMG_ALLOW_CONFIRM_NON_ACTIVE_SLOT` it reaches `boot_set_next(fa(slot 1), false, true)`, which writes nothing for a good-magic slot. In each case the confirm is lost and the next reset erases the running image. | Inference. Not run. Conformance cases for any product that links mcumgr image management in this mode. |
| Image state flags | Built from `mcuboot_swap_type_multi()`, the swap-table read above | Inference: no established meaning for RAM load |

mcumgr is a protocol for an external client. A Crux update agent that runs in the application calls bootutil directly. mcumgr is not an alternative provider for the contract, and a product may leave it out.

### An existing neutral interface: PSA Firmware Update

The Arm PSA Certified Firmware Update API is a bootloader-neutral interface with query, install, request-reboot, accept and reject operations on components, with states such as staged, trial and rejected. In TF-M's MCUboot-based implementation `psa_fwu_query()` fills the implementation information only for a component in the candidate state (Verified by public document: [PSA Firmware Update API 1.0, programming model](https://arm-software.github.io/psa-api/fwu/1.0/overview/programming-model.html), [TF-M firmware update service](https://trustedfirmware-m.readthedocs.io/en/latest/design_docs/services/tfm_fwu_service.html), read as search summaries only). Zephyr v4.4.0 mentions `psa_fwu_accept()` once, in a migration guide about TF-M, and has no API source for it in the tree searched (checked at `684c9e8`, v4.4.0, not at the v4.4.2 pin: Not verified for v4.4.2).

Not adopted, for two reasons. It is built for a secure-partition service in TF-M, and the RT1060 plan does not use TF-M (Inference from the M8 composition, which composes stock MCUboot and Zephyr). Its component model carries more than one image and one slot pair, where the M9 case is one image and two slots. Whether it can report "reverted" after a power cycle was not established from the summaries read (Not verified). It is used here as a check on the contract's state names, not as a dependency.

## Options compared

| | Option 1: stock `boot_request_upgrade()` and `boot_write_img_confirmed()` | Option 2: slot-aware caller, `boot_set_next()` on the inactive slot, in a product adapter | Option 3: Option 2 behind a Crux contract (recommended) | Option 4: mcumgr image management |
| --- | --- | --- | --- | --- |
| RAM load with revert on NOR | Request fails silently from slot 1 (B63a). Confirm is right. | Works from either slot. Silent no-op remains when the trailer is not erased. | Works from either slot. The trailer is checked, and a no-op becomes an error. | Depends on the active-slot detection above. Not verified. |
| On eMMC slots | Same calls over `flash_area`, so the same behaviour. Trailer alignment and write ordering depend on the driver (see [Fit with NOR and eMMC](#fit-with-nor-and-emmc)). | Same | Same, with the driver rules written as provider requirements | Same, plus the protocol transport |
| Boot-result record (running slot, confirmed, reverted, bootloader version) | Running slot and confirmed only. No version. No "reverted". | Each product derives it differently | One record, one classifier, one place to test | Not provided. A client reads image state flags. |
| Older-image rejection | Bootloader compares only to choose. No application rule. | A product writes its own | One pure rule, shared with the request check | The upload path compares versions only under its own options (not read in full) |
| Linux Host testability | A product needs its own fake | Each product writes a fake of its port | One Host double and one conformance suite | Needs a protocol client |
| `native_sim` testability | Possible with a flash simulator (Inference) | Same | Same, once for all products | Not assessed |
| Fit to ADR-0002 | Zephyr-native | Zephyr-native, product-owned | A narrow Crux interface with a stated consumer set | A protocol, not an API |
| Cost | None | One adapter per product | Header, Host double and suite, on top of the adapter that Option 2 also needs | Not considered further |
| Main risk | Silent loss of an update | The risk repeats in every product | One provider only, so neutrality is unproven | An unconfirmed image after a lost confirm |

Option 1 is rejected because it fails on the first update from slot 1. Option 4 is not an option for an application-side update agent. The decision is between Options 2 and 3, and their code is the same in the provider. Option 3 differs by the public header, the Host double, the suite and the commitment.

An option that writes the trailer bytes in Crux, bypassing bootutil, is rejected: it copies a trailer layout that depends on `BOOT_MAX_ALIGN` and the write block (`M:bootutil_public.c`:60-95, 303-374) and has to follow every MCUboot change.

## Proposed contract

The decisions I1 to I9 are adopted. This section describes the contract as proposed, and the signatures stay illustrative (this record reads the approval as covering the decisions, not the exact signatures, and no implementation is approved).

### Component and header

A new component `components/image_state/` with the public header `components/image_state/include/crux/image_state.h`. The path is unique among the headers that exist at this head (checked against `components/*/include/crux/`). Names follow [CONTRIBUTING.md](../../CONTRIBUTING.md): `crux_` for functions and types, `CRUX_` for macros, enum constants and the header guard `CRUX_IMAGE_STATE_H`. The Zephyr provider sits in a Zephyr composition directory, and the Host provider in the component. Which directory is decided with the owner of the boot composition work. Test controls for the Host double live outside the public header, as CONTRIBUTING requires.

No Zephyr, MCUboot or bootutil type appears in the header. It depends on `<stdbool.h>`, `<stddef.h>` and `<stdint.h>` only.

### Illustrative signatures

```c
#define CRUX_IMAGE_SLOT_COUNT 2u /* one image, two slots: no multi-image */

typedef uint8_t crux_image_slot_t; /* 0 or 1; equal to the bootloader's slot number */

typedef struct {
    uint8_t major;
    uint8_t minor;
    uint16_t revision;
    uint32_t build; /* carried, never compared */
} crux_image_version_t;

typedef enum {
    CRUX_IMAGE_SLOT_EMPTY = 0,        /* no valid header */
    CRUX_IMAGE_SLOT_STAGED = 1,       /* valid header, no trailer: written, not requested; a newer one is erased at the next reset */
    CRUX_IMAGE_SLOT_PENDING_TEST = 2, /* requested; boots on the next reset if selected */
    CRUX_IMAGE_SLOT_PENDING_PERMANENT = 3, /* reported only; this contract never creates it */
    CRUX_IMAGE_SLOT_RUNNING_CONFIRMED = 4,
    CRUX_IMAGE_SLOT_RUNNING_TESTING = 5,   /* on trial: confirm, or the next reset erases it */
    CRUX_IMAGE_SLOT_STANDBY_CONFIRMED = 6, /* valid, confirmed, not running: the fallback */
    CRUX_IMAGE_SLOT_TRIED = 7,        /* selected by the bootloader, not running; erased at next reset */
    CRUX_IMAGE_SLOT_INVALID = 8       /* trailer holds a value outside the defined ones */
} crux_image_slot_state_t;

typedef struct {
    crux_image_slot_state_t state;
    crux_image_version_t version; /* meaningful unless state is EMPTY or INVALID */
} crux_image_slot_info_t;

typedef struct {
    crux_image_slot_t running_slot;
    bool running_confirmed;            /* false: on trial */
    crux_image_version_t running_version;
    crux_image_slot_t inactive_slot;   /* where the next image is written and requested */
    bool bootloader_version_known;
    crux_image_version_t bootloader_version;
    crux_image_slot_state_t slot_state_at_start[CRUX_IMAGE_SLOT_COUNT];
} crux_image_boot_record_t;

typedef struct { /* written by the update agent, cleared by it after the outcome is handled */
    crux_image_slot_t slot;
    crux_image_version_t version;
    bool requested; /* false while staging; set true just before crux_image_request_test() */
} crux_image_attempt_t;

typedef enum {
    CRUX_IMAGE_OUTCOME_NONE = 0,       /* no attempt, or a stale one */
    CRUX_IMAGE_OUTCOME_TESTING = 1,    /* the attempted image runs, unconfirmed */
    CRUX_IMAGE_OUTCOME_CONFIRMED = 2,  /* the attempted image runs, confirmed */
    CRUX_IMAGE_OUTCOME_NOT_BOOTED = 3, /* the request is still pending or was never made */
    CRUX_IMAGE_OUTCOME_REVERTED = 4    /* the attempted image is gone or refused; the previous image runs */
} crux_image_outcome_t;

typedef enum {
    CRUX_IMAGE_OK = 0,
    CRUX_IMAGE_ERR_INVALID_ARGUMENT = -1,
    CRUX_IMAGE_ERR_NOT_READY = -2,      /* not started, or start failed */
    CRUX_IMAGE_ERR_NO_BOOT_DATA = -3,   /* shared data or a needed key is missing */
    CRUX_IMAGE_ERR_BOOT_STATE = -4,     /* running trailer or mode is not one this contract supports */
    CRUX_IMAGE_ERR_IO = -5,
    CRUX_IMAGE_ERR_ACTIVE_SLOT = -6,    /* the request names the running slot */
    CRUX_IMAGE_ERR_NO_IMAGE = -7,       /* no valid header in the slot */
    CRUX_IMAGE_ERR_NOT_NEWER = -8,      /* the slot's version is not strictly newer than the running one */
    CRUX_IMAGE_ERR_SLOT_STATE = -9,     /* the slot is not STAGED, or PENDING_TEST for an idempotent repeat */
    CRUX_IMAGE_ERR_NOT_CONFIRMED = -10, /* the running image is on trial */
    CRUX_IMAGE_ERR_BUSY = -11
} crux_image_result_t;

crux_image_result_t crux_image_start(void);
crux_image_result_t crux_image_boot_record_get(crux_image_boot_record_t *record);
crux_image_result_t crux_image_slot_get(crux_image_slot_t slot, crux_image_slot_info_t *info);
crux_image_result_t crux_image_request_test(crux_image_slot_t slot);
crux_image_result_t crux_image_confirm(void);

/* Pure functions. No provider, no state. */
int crux_image_version_compare(const crux_image_version_t *a, const crux_image_version_t *b);
crux_image_outcome_t crux_image_outcome(const crux_image_boot_record_t *record,
                                        const crux_image_attempt_t *attempt /* may be NULL */);
```

`crux_image_version_compare()` returns -1, 0 or 1 on major, minor, revision, in that order. These signatures are a proposal. The full Doxygen contract (ownership, lifetime, context) is written in the implementation change, as CONTRIBUTING requires.

### Mapping to the four words of #297

| #297 word | Where it appears |
| --- | --- |
| Running | `RUNNING_CONFIRMED`, `RUNNING_TESTING`, and `running_slot` in the record |
| Pending | `PENDING_TEST` (and `PENDING_PERMANENT`, reported only), `NOT_BOOTED` as an outcome |
| Confirmed | `RUNNING_CONFIRMED`, `STANDBY_CONFIRMED`, `running_confirmed`, outcome `CONFIRMED` |
| Reverted | Outcome `REVERTED` only. A reverted image no longer exists in its slot. |

### Slot states

The provider derives a slot's state from the header and the trailer. `R` is the running slot from the shared data.

| Slot | Header | `magic` | `image_ok` | `copy_done` | State |
| --- | --- | --- | --- | --- | --- |
| Any | Invalid or erased | any | any | any | `EMPTY` |
| Not `R` | Valid | Unset | | | `STAGED` |
| Not `R` | Valid | Good | Unset | Unset | `PENDING_TEST` |
| Not `R` | Valid | Good | Set | Unset | `PENDING_PERMANENT` |
| Not `R` | Valid | Good | Unset | Set | `TRIED` |
| Not `R` | Valid | Good | Set | Set | `STANDBY_CONFIRMED` |
| `R` | Valid | Good | Set | any | `RUNNING_CONFIRMED` |
| `R` | Valid | Good | Unset | Set | `RUNNING_TESTING` |
| `R` | Valid | Good | Unset | Unset | `RUNNING_TESTING` (the bootloader's `copy_done` write failed, which it only logs; treated as on trial) |
| `R` | Valid | Unset or bad | | | Start fails with `ERR_BOOT_STATE`. Under revert the bootloader erases such a slot, so it cannot be the running one. |
| Not `R` | Valid | Bad, or a flag outside set and unset | | | `INVALID` |

All rows are Inference from `M:boot_select_or_erase` and `M:boot_set_next`, and the flag decoding in `M:bootutil_public.c`:155-163 and 243-284. The table is checked by conformance cases S1 to S12.

### Boot record and outcome

`crux_image_start()` derives the record once, at start, from the shared data (`BLINFO_RUNNING_SLOT`, `BLINFO_BOOTLOADER_VERSION`, and `BLINFO_MODE` as a sanity check), the running slot's trailer and header, and the other slot's state. It caches the record. Calling it again returns `CRUX_IMAGE_OK` and changes nothing. A missing running-slot key gives `ERR_NO_BOOT_DATA`. A mode other than `MCUBOOT_MODE_RAM_LOAD` gives `ERR_BOOT_STATE`. A missing version key gives `bootloader_version_known = false`, and the start still succeeds.

`crux_image_outcome()` is a pure function. `A` is the attempt, `S` the state of `A.slot` at start.

| Case | `A` (first match wins, top to bottom) | Result |
| --- | --- | --- |
| 1 | NULL | `NONE` |
| 2 | `A.slot` is the running slot and `A.version` equals the running version on major, minor and revision | `CONFIRMED` if `running_confirmed`, else `TESTING` |
| 3 | `A.slot` is the running slot and the versions differ | `NONE` (stale: the slot was reused) |
| 4 | `A.slot` is not running and `S` is `STANDBY_CONFIRMED` | `NONE` (stale: the slot holds a confirmed image) |
| 5 | `A.slot` is not running and `A.requested` is false | `NOT_BOOTED` (the agent never asked for a boot. The slot may read `EMPTY`, because the bootloader erases a newer image that was staged and not requested.) |
| 6 | `A.slot` is not running, `A.requested` is true and `S` is `PENDING_TEST`, `PENDING_PERMANENT` or `STAGED` | `NOT_BOOTED` (the request was not consumed. For `PENDING_*` this is reachable only after a failed `copy_done` write together with a failed validation, and for `STAGED` only if the request writes did not complete.) |
| 7 | `A.slot` is not running, `A.requested` is true and `S` is `EMPTY`, `TRIED` or `INVALID` | `REVERTED` |

`TRIED` and `EMPTY` both give `REVERTED` because the application cannot tell a refused image (validation failed, erased at the second reset) from an unconfirmed one (erased at the first). A caller that needs the difference reads `slot_state_at_start`. The attempt record is persisted by the update agent in its own storage. Where it lives is part of the update agent's design, not this contract. The order is: write the attempt with `requested` false when staging starts, set `requested` true just before `crux_image_request_test()`, and clear the record after the outcome is handled. A power cut during staging gives case 5 (`NOT_BOOTED`, accurate). A power cut after `requested` was set and before the request writes landed gives case 7: the newer image is erased at the next reset, and the record reports `REVERTED` for an image that never ran. That error is on the safe side (the agent retries) and the window is a few writes wide. It is a stated limit, not a fixed one.

### Behaviour

- **Context.** Thread context only. `crux_image_request_test()` and `crux_image_confirm()` write storage and can block for the length of a medium write, so a control thread must not call them. `crux_image_boot_record_get()` copies the cached record and does not block after start. One internal lock serialises request and confirm. A second caller gets `ERR_BUSY` after a bounded wait.
- **`crux_image_request_test(slot)`** requires, in this order: started; `slot` is valid and not the running slot (`ERR_ACTIVE_SLOT`); the running image is confirmed (`ERR_NOT_CONFIRMED`); the slot holds a valid header (`ERR_NO_IMAGE`); its version is strictly newer than the running version (`ERR_NOT_NEWER`); its state is `STAGED`, or `PENDING_TEST`, which returns `CRUX_IMAGE_OK` without writing (`ERR_SLOT_STATE` for any other state). It then calls the slot-aware bootutil request. It returns success only after the writes return success. It does not reset. A reset goes through the Reboot service, whose policy may refuse ([reboot service](../reboot-service.md)).
- **Live and cached state.** `crux_image_boot_record_get()` returns the snapshot taken at start, which never changes. `crux_image_slot_get()` and the checks inside `crux_image_request_test()` and `crux_image_confirm()` read the live trailers. After a confirm in this boot, `crux_image_slot_get()` on the running slot reports `RUNNING_CONFIRMED` and a later request passes the not-confirmed check, while the record still says `running_confirmed` is false.
- **`crux_image_confirm()`** writes `image_ok` on the running slot only. If the running image is already confirmed it returns `CRUX_IMAGE_OK` without writing. It never names a slot, so it cannot confirm the wrong one.
- **Staging precondition.** The update agent erases the whole staging slot, trailer included, before it writes an image. A stale trailer with good magic and `image_ok` set makes an unvalidated-in-test image look confirmed to the bootloader (Inference from `boot_select_or_erase`). The contract turns that case into `ERR_SLOT_STATE`, because the slot is not `STAGED`.
- **No authorisation.** The contract checks no permission. A management adapter checks access before it calls the update agent (owner decision 5). The caller is trusted code.
- **Durability.** A successful return means the write reached the medium as far as the flash driver can report. For eMMC, flushing the card's write cache at MCUboot's ordering points is a requirement on the driver (see below). It is **Not verified**.
- **Providers.** One is selected at link time, as for the other contracts: the Zephyr provider over bootutil, and a Host provider in the component. The Host provider is a test double with its controls outside the public header. A product image never links it.

### Version rules

Owner decision 4 requires an application-side check that rejects an older image, compared on major, minor and revision. The bootloader gives none in this mode: the option can be set but has no effect (#141 rows B14, B21, B60), and a version comparison only chooses which slot to boot (`M:loader.c`:2115-2140).

The comparison order is major, minor, revision (`M:bootutil_loader.c`:200-232). mcumgr uses the same order and adds the build number only under its own option (`Z:.../zephyr_img_mgmt.c`:349-378). The contract compares exactly those three, and ignores the build number (I5).

Strictly newer (I4) goes beyond "reject older". With equal versions the lower slot number wins (`loader.c`:2115-2140). Running from slot 0 with version 1.2.3, an equal image in slot 1 is never chosen, and it stays pending without ever being erased, since it is never selected. The request would return success and do nothing. Running from slot 1, an equal image in slot 0 would be chosen. The behaviour then depends on the slot, which is the kind of dependence this contract exists to remove. The cost: a reflash of the same version through the update path is refused. A product that needs that case uses a development tool, as M8 does under owner decision 13.

The update agent applies the same rule on the header it receives, before any NOR write, as owner decision 5 requires. `crux_image_request_test()` applies it again on what is in flash, because it is the last check before the bootloader decides. The running image's version is read from its own header in flash through the running slot, not from the application's compiled-in version, so that the two cannot drift.

## Conformance cases

Three levels. The Host and `native_sim` cases are what M9 asks for as "Linux Host and Zephyr conformance cases". The third level is the target evidence that M9 lists separately, under its own hardware approval.

| ID | Case | Host | `native_sim` | Target |
| --- | --- | --- | --- | --- |
| S1-S12 | Each row of the slot-state table maps to the stated state (12 cases, including the two running-slot rows with a failed `copy_done` write and with magic not good) | Yes | Yes | |
| B1 | Start with the running-slot key missing gives `ERR_NO_BOOT_DATA` and a later confirm gives `ERR_NOT_READY` | Yes | Yes | |
| B2 | Start with a mode other than RAM load gives `ERR_BOOT_STATE` | Yes | Yes | |
| B3 | Bootloader version present, absent, and present with zero fields | Yes | Yes | |
| B4 | Start twice returns the same record | Yes | Yes | |
| R1 | Request from slot 0 for slot 1 and from slot 1 for slot 0 both write the inactive slot (the B63a regression) | Yes | Yes | Yes |
| R2 | Request naming the running slot gives `ERR_ACTIVE_SLOT` and writes nothing | Yes | Yes | |
| R3 | Request while the running image is on trial gives `ERR_NOT_CONFIRMED` | Yes | Yes | |
| R4 | Request for an empty slot gives `ERR_NO_IMAGE` | Yes | Yes | |
| R5 | Request for an older and for an equal version gives `ERR_NOT_NEWER`, and for a newer version succeeds | Yes | Yes | |
| R6 | Request for a slot with a stale confirmed trailer gives `ERR_SLOT_STATE` (the silent-success case of `boot_set_next()`) | Yes | Yes | |
| R7 | Second request for a pending slot returns OK and writes nothing | Yes | Yes | |
| R8 | Writes happen in the stock order (magic, then swap info), and a failure after the magic leaves the slot `PENDING_TEST` | Yes (fake injects the failure) | Yes | Power fixture case |
| C1 | Confirm on trial writes `image_ok` on the running slot, and on a second call writes nothing | Yes | Yes | Yes |
| C2 | Confirm when running from slot 1 changes slot 1 and not slot 0 | Yes | Yes | Yes |
| C3 | Confirm with a write failure returns `ERR_IO` and the state stays `RUNNING_TESTING` | Yes | Yes | |
| V1 | Version compare: major, minor, revision order, equal, and the build number ignored (table of vectors) | Yes | Yes | |
| V2 | The compare agrees with a hand model of `boot_compare_version` for the same vectors | | Yes | |
| O1-O7 | Each row of the outcome table, with each slot state | Yes | | |
| O8 | Power cut during staging (`requested` false) gives `NOT_BOOTED`, and after `requested` was set but before the request writes gives `REVERTED` (the stated limit). A newer staged slot reads `EMPTY` after a reset. | Yes | Yes | |
| N1 | The `native_sim` provider runs the real bootutil functions over a flash simulator. A hand model of the bootloader's select and erase rules (the table above) runs between resets. A full update, a revert and a refused image play out end to end. | | Yes | |
| T1 | Test, confirm, reboot: the new image stays | | | Yes |
| T2 | Test, no confirm, reboot: the previous image runs, and the outcome is `REVERTED` | | | Yes |
| T3 | A corrupted staged image is refused, the previous image runs, and the slot reads `TRIED` then `EMPTY` | | | Yes |
| T4 | Shared data present at application start in the SDRAM-loaded image (B64) | | | Yes |
| T5 | Bootloader version in the record equals the built value | | | Yes |
| T6 | Repeated reboots without confirm, and the declared power-interruption cases | | | Fixture and approval |
| T7 | The same suite on eMMC slots | | | After the eMMC driver and board exist |

What the first two levels cannot prove: that the real bootloader behaves like the hand model, that the shared data survives the jump, and anything about cache ordering. Those are the target cases.

## Fit with NOR and eMMC

- **NOR.** Slots are `fixed-partitions` of the FlexSPI device, and bootutil reads and writes them through `flash_area_*`. The writes to the inactive slot happen while the application runs from SDRAM, so they do not stall the running code. The bootloader's own writes (`copy_done`, the erase of a refused slot) happen during its XIP, and #165 covers closing that path (#141 owner decision 16).
- **eMMC through a flash-API driver over the MMC disk.** The contract is slot-indexed and medium-neutral because bootutil reaches every slot through `flash_area_*`. MCUboot's port reads slots only through the flash API (`boot-emmc-investigation.md`, section 2). What changes is the trailer, and it is the driver's affair, not the contract's:
  - The trailer offsets depend on `BOOT_MAX_ALIGN`. A trailer flag write is padded to the larger of the flash write unit and the flag size, and it fails (an assertion and a return of -1) if that exceeds `BOOT_MAX_ALIGN` (`M:bootutil_public.c`:345-374). The alignment cap of 8 to 32 applies to swap modes (`M:bootutil_public.h`:79-90). Whether it applies to RAM load with a 512-byte write block was not read in full. **Not verified.**
  - The request writes (magic, then `image_ok` only for a permanent request, then swap info, in that order: `M:bootutil_public.c`:558-572) land in separate write blocks on a medium with a 512-byte block. The magic write is the point at which the slot becomes a pending request (Inference from `boot_select_or_erase`). Their order must hold on the medium. A write cache that reorders them is a driver requirement. The eMMC record and #310 are where that is examined.
  - Slot offsets must lie outside any file system on the same medium (`boot-emmc-investigation.md`, section 2).
- **Same suite, two media.** Cases S, R, C, O and V do not depend on the medium. Case T7 repeats T1 to T3 on eMMC. Until a board exists, the eMMC simulator of #310 is the nearest software check, and it tests trailer sequences, not the contract.

## What stays Zephyr-native in product adapters

- Slot definitions in the devicetree (`slot0_partition`, `slot1_partition`), the flash-API device, and the eMMC driver and its node.
- Opening, erasing and writing the staging slot (`flash_area_*`) and the transfer of image bytes. The update agent's port to this is a separate proposal.
- MCUboot configuration, sysbuild, `imgtool` signing and keys, the retention node and `zephyr,bootloader-info`, and the data-sharing options.
- The reset after a request, through the Reboot service or a product-owned call.
- The product's own confirm criteria and timing. The contract offers the mechanism. A confirm-after-healthy timer is product policy.
- Any use of mcumgr image management, which a product may keep for factory or service use. It has the cases listed above if it is linked in this mode.
- Direct calls of `boot_*` outside the Crux provider. The provider is the only Crux code that includes the bootutil headers.

## Limits and Not verified

- No board result exists for any claim about the bootloader's behaviour. Everything about `boot_select_or_erase` is what the code allows.
- Which Kconfig options expose the bootutil headers to an application, and which options the provider needs beyond the shared-data and retention settings of #141, are composition details for #296. **Not verified.**
- The bootloader version of a build that overrides MCUboot's `VERSION` file, and the Zephyr default for a build with none, were not read. The upstream file at the pin says 2.4.0.
- The MCUboot revision here (`6d3b3d2c`) is newer than the one that #141 used (`ee39e2d`). The rows of #141 that this proposal relies on (B14, B21, B60, B63, B63a, B64) were re-read at the new revision for the functions named above, and the others were not.
- The PSA specification and TF-M pages were read as search summaries.
- Multi-image setups and more than two slots are out of scope. mcumgr's source says multi-image does not support RAM load (`Z:.../img_mgmt.c`:236-266, comment at 240).
- Hardware-backed anti-rollback: the record carries no security counter, because the Zephyr port has no counter backend at the pin. M9 declares the level achieved.

## Open questions

| # | Question | Recommendation |
| --- | --- | --- |
| Q1 | Equal versions: refuse (I4), or accept and document the slot-order case? | Refuse. Decided by the owner's approval of I4 on 15 November 2026. |
| Q2 | Where does the attempt record live, and how does the update agent keep it consistent across a power cut? | In the update agent's design, with the File or Configuration service. Decide with its proposal. |
| Q3 | Does a product link mcumgr image management in RAM load with revert mode? | Not in M9. If yes, run the upload and confirm cases first: a misreported active slot can aim an upload at the running image's slot. |
| Q4 | Is the retained shared data intact at start on the RT1060 board after the jump? | Target case T4, before any other use of the record |
| Q5 | Does a 512-byte write unit work with the trailer alignment rules in RAM load, and what must the eMMC driver guarantee about ordering? | Answer in the eMMC driver work and #310, then restate as provider requirements |
| Q6 | Which component and directory hold the Zephyr provider? | With the boot composition owner |
| Q7 | A permanent request: needed later for factory images? | Not in this contract. Images signed with `--pad --confirm`, or built with `MCUBOOT_GENERATE_CONFIRMED_IMAGE`, are permanent. `--pad` alone is a test request (owner decision 13). |
| Q8 | Should the contract report the signature type and recovery key of the shared data, for the root-of-trust and recovery declarations of M9? | No. M9's results can read them through the native call. Add them only if a consumer needs them. |
| Q9 | `BLINFO_MODE` reports RAM load for a bootloader built without revert too, so the start check cannot catch it, and test requests would never be reverted. | A build-time check in the M8 composition that both images are built for RAM load with revert, and target case T2 |

## Consistency with the accepted decisions

- **[ADR-0002](../decisions/0002-platform-direction-zephyr-execution-crux-services.md) and [ADR-0003](../decisions/0003-p9-result-services-keep-narrow-thread-sync.md).** The contract owns no thread and no priority setting, and its header includes neither `<crux/thread.h>`, `<crux/sync.h>`, `<crux/queue.h>` nor `<crux/serial.h>`. Product code reaches none of them through it. The one internal lock of the request and confirm path is an implementation detail: the Zephyr provider may use a Zephyr lock, which ADR-0001 allows in a Crux provider, and the Host provider uses the narrow internal Sync that ADR-0003 keeps inside Crux services. Which of the two is settled in the implementation change.
- **[ADR-0004](../decisions/0004-product-composition-of-management-services.md).** A product reaches the contract through a public `crux::` target and the public header, never through a private header, and the bootutil headers stay private to the provider. `crux_image_start()` takes no Zephyr handle, so a composition interface under the [six rules](../composition-interfaces.md) is probably not needed (Inference). This proposal adds no composition route of its own. The Zephyr module's build integration follows the route ADR-0004 fixes for services.
- **[ADR-0005](../decisions/0005-native-sim-test-watchdog-for-system-consumers.md).** The `native_sim` cases are software evidence only, as ADR-0005 says of its own case. They say nothing about the board.
- **[ADR-0006](../decisions/0006-cryptographic-dependency-policy.md).** The contract adds no cryptographic dependency and selects no backend. It verifies no signature: the bootloader does, and so does the update agent before it writes (with PSA Crypto, under the pin policy of ADR-0006). The #141 trial built MCUboot with ECDSA P-256 on its own bundled tinycrypt, outside Crux's `mbedtls` pins ([boot and update investigation](../boot-update-investigation.md#mcuboot-against-the-adoption-criteria)). ADR-0006 names MCUboot as a candidate for a dependency review that it does not decide. The M8 composition's crypto backend should go through that review, and nothing here chooses it.

## Changes other documents would need if adopted

None are made here. Each bullet is a need that follows from an approved row, and recording the approval does not make or approve any of them.

- M9 milestone text and #297: no change, because I1 is approved (15 November 2026). If I1 is rejected, the acceptance criterion on image-state conformance cases, the milestone's exit evidence and #191 are revised explicitly.
- The M8 composition: the data-sharing, retention and `zephyr,bootloader-info` settings become required inputs of the Zephyr provider, and the build-number comparison option must stay off (I5).
- A new component entry in the architecture overview and the component readiness table, as Experimental.
- Update agent proposal: the attempt record, the staging write and erase, and the order of the steps.

## Process record

- Search first: the PSA Firmware Update API is the one existing bootloader-neutral interface found. It is not adopted (see above). No package, tool or wrapper was installed.
- Decision format: the table above follows the repository's decision tables, with the alternatives in [Options compared](#options-compared). No file was written under `docs/adr/`.
- Upstream sources were fetched into a scratchpad outside the repository and read there. None is copied.
- Owner approval of I1, I4 and I7 on 15 November 2026 was recorded in a later documentation change (status line, decision table and [Owner approval](#owner-approval)), and the approval of I2, I3, I5 and I6 of the same day in another. The review of each change is recorded in its own pull request.
- Independent review (by the independent reviewer): first round REVISE with four blocking findings (an erased staged image and the power-cut outcome, the mcumgr confirm and upload paths, and a wrong reading of owner decision 13), fixed in this revision. The re-check and the CI results are recorded in the pull request.
