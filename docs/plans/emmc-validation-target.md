# eMMC validation target for boot and update

> **Status:** Draft decision record. It records the owner's decision D3 of 15 November 2026 as the secure boot plan records it, compares the options, and lists what stays open. It makes no eMMC support claim, adds no M8, M9 or M14 exit criterion, and authorises no purchase, hardware operation or fuse operation.
> **Verified:** Documents of this repository only (the #298 record and its evidence, the secure boot development plan, the issues #441 and #476). Nothing was built, programmed or run.
> **Not verified:** That any eMMC adapter works with the RT1060, that the boot ROM boots an eMMC from the EVKB microSD socket, the signalling level of that socket, and anything on a board.
> **Read this first / then:** [eMMC boot and update feasibility](../boot-emmc-investigation.md) ("Hardware needed" and section 3), then the [secure boot development plan](secure-boot-development-plan.md) (sections 5 and 6, decisions D3 and D8), then the [provisioning profile record](emmc-provisioning-profile.md).

| Field | Value |
| --- | --- |
| Issue | [#441](https://github.com/wonny-labs/crux-pilot/issues/441) "Decide the eMMC validation target for boot and update" (plan section 5, issue D; decision D3; milestone M8) |
| Date | 15 November 2026 |
| Status | **Draft.** D3 is decided as the plan records it (see [the owner's decision](#the-owners-decision)). Items below it are open. |
| Records it builds on | #298 ([boot-emmc-investigation.md](../boot-emmc-investigation.md), section "Hardware needed", and its [evidence rows H1 to H7](../evidence/boot-emmc/emmc-semantics-and-hardware.md)), the [secure boot development plan](secure-boot-development-plan.md), the [eMMC physical gate of M14](../emmc-reliance-physical-gate.md) |
| Sibling record | [emmc-provisioning-profile.md](emmc-provisioning-profile.md) (#476). It waits for this decision and for the product inputs of D8. |
| Author model | `claude-sonnet-5-5` (tool: Claude Code). Independent review: see the pull request. |

## Purpose and scope

No eMMC-bearing RT1060 or RT1062 target exists yet (owner confirmation of 7 November 2026, #298 and #310). The RT1060-EVKB has an SD slot on its first uSDHC and no eMMC ([#298](../boot-emmc-investigation.md#hardware-needed), rows H1 to H4). Until a target exists, eMMC boot and update stay unvalidated and the NOR results on the RT1060-EVKB remain the only evidence. This record compares the ways to get a target, says what each can and cannot show, and records what the owner decided.

Not in scope, as in the issue: buying or operating hardware, naming products or parts, and any eMMC support claim. The eMMC physical gate of M14 needs its own approval and is not changed by this record.

## Evidence labels

Labels follow [#298](../boot-emmc-investigation.md#evidence-labels): Verified on pinned source, Verified by public vendor document, Verified in repository, Inference, Not verified. A statement without a label is a proposal of this record or a citation of a decision record.

## The options

Each option is a way to answer different questions. The columns say what a result from it **would** show and **would not** show, and what it needs.

| | Option 1: the EVKB with an eMMC adapter on its microSD socket | Option 2: a product-class board with an eMMC on a controller the ROM can select | Option 3: both, in the order 1 then 2 |
| --- | --- | --- | --- |
| Question it answers | Does Crux's MMC stack, slot layout and user-area handling work against a real eMMC? | Does the ROM boot the first stage from the boot partition, and what do HAB and the first stage do there? | Option 1 first as a partial step, option 2 for the ROM questions |
| Would show | The Zephyr MMC stack and uSDHC driver bringing up a real eMMC on a four-bit bus (if the adapter and the stack work together, Not verified). EXT_CSD reads. The eMMC cache and flush behaviour of the M14 correction, with a device instead of the simulator. Raw slot access through the Draft flash-API driver, if it is later adopted (D2). Timing, DMA and cache-alignment behaviour of the existing stack. User-area power cuts, **only** with a power fixture and its own approval. | ROM boot from a boot partition of a real eMMC, including where the first stage sits in the partition (whether the IVT offset `0x400` counts from its start, #298 X1). Whether the ROM accepts the first-stage header. SDRAM bring-up by DCD on that boot path. The state of the card when the image starts (#298 X5). HAB behaviour on an SD or eMMC image in open configuration, with a path that needs no fuse writes if one exists. The provisioning settings of the [profile record](emmc-provisioning-profile.md) on the product's own wiring. | The union, in that order. Software results are available before the product-class board exists. |
| Would **not** show | **ROM boot from the boot partition.** Whether the ROM boots an eMMC from that socket, with what fuse or pin settings, is not established (#298 H5, H6: Not verified). It could not show any property that depends on the product's wiring: the 8-bit bus, the I/O voltage, the reset pin, the supply handling. It shows nothing about HAB. It shows nothing about a particular product part unless that part is on the adapter. | The software questions of option 1 are answered on that board too, but a product-class board is slower to obtain and its support stays outside this repository. It shows nothing about other board revisions. | The limits of each remain. |
| Needs (all Not available or Not established today, #298 "Hardware needed") | An adapter that presents an eMMC to a microSD socket. Its working with the RT1060 is not shown by any source read. The socket's signalling level is not established. Switchable eMMC power under test control is not available on the EVKB for an eMMC. An independent way to read EXT_CSD and the raw partitions. Sacrificial eMMC parts if any OTP field is touched. | A board with an eMMC on a uSDHC the ROM can select (USDHC-1 or USDHC-2), the boot fuses or GPIO overrides settable, the reset pin available, and the board support outside this repository. Switchable power for both eMMC supplies, sacrificial parts, independent EXT_CSD access, signal observation and a debug probe independent of eMMC power. | Both lists. |
| Cost to the repository | Software-only evidence, plus a hardware task with its own approval | No board support in this repository (the issue: "Board support stays outside this repository") | Both |

A note on what the EVKB socket might do. Whether the ROM can boot an eMMC from the microSD socket is **not known**: the ROM selects a card type and bus width by fuses or pin overrides (R5), and no source read says what the socket supports. If it could, using it would need fuse or pin settings, and **no fuse operation is approved**. This record therefore claims no ROM boot from option 1.

## Recommendation

**Option 3, both, with the adapter as the first and partial step.** This is the plan's recommendation for D3 and the one #298 names as the first, partial step. Reason: the adapter is the only route to real-device results for the MMC stack, the cache and the slot handling while no product-class board exists, and it needs no board support in this repository. It cannot answer the ROM and HAB questions, so the product-class board stays the target for those. Choosing option 1 alone would leave the ROM boot path unvalidated for good, and choosing option 2 alone would delay every device result until a board exists.

An alternative that this record does not recommend: **option 2 alone**, if the owner prefers to spend no effort on an adapter whose working with the RT1060 is not shown. The cost is that no real-device result exists until the board does, and the Draft driver prototype (#435) and the replay results stay simulator-only until then.

## Departure from #298 on adapters

#298 did not recommend third-party adapters, because none was shown to work with the RT1060 ([#298](../boot-emmc-investigation.md#hardware-needed), row H6: listed without recommendation). **Recommending the adapter route, even for software-only testing of the stack and the user area with no ROM-boot claim, departs from #298.** The departure is limited as follows.

- It recommends a **route**, not a product. No adapter or part is named, recommended or shown to work. The repository holds no part names.
- An adapter result would show how Crux's stack and a device behave on a four-bit bus through that adapter. It would **not** show ROM boot, HAB, the 8-bit bus, the product's I/O voltage, the product's reset wiring or the product's supply handling, and it would not show that the stack works on the product's board.
- A failure on an adapter would be a finding about the adapter, the socket's signalling and the stack together, and could not be attributed to one of them without more evidence (Inference).
- Buying an adapter is the owner's, as D3 says, and every physical task needs its own approval.

## The owner's decision

The decision is recorded in the secure boot development plan, section 6, decision D3. The row is copied below unchanged, in the plan's own table form:

| # | Decision | Recommendation | Needed before |
| --- | --- | --- | --- |
| D3 | eMMC validation hardware | EVKB with an eMMC adapter for software, a product-class board for ROM boot (#298 "Hardware needed"). #298 did not recommend third-party adapters, because none was shown to work with the RT1060; recommending one departs from it, for software-only testing of the stack and the user area with no ROM-boot claim | Issue D **Owner, 15 November 2026: approved as recommended. No claim that an adapter works with the RT1060 is made, and buying hardware is the owner's.** |

The plan records how the owner's answer reached it: the owner answered "5~11번도 추천대로 승인" (approved as recommended, for the items numbered 5 to 11 in the secure boot session's list) at about 17:29 UTC on 15 November 2026, and the secure boot session mapped those numbers to D1 and D3 to D8. The answer was relayed second-hand to the session that edited the plan's table. The plan states that each answer approves the recommendation as the table words it, and nothing more: **no hardware purchase or operation, no key, no fuse operation and no tag is approved by any row.** This record adds no decision of its own.

What the decision covers, and what it does not. The left column keeps to the D3 wording above. Framing that comes from #441 and #298 and is not part of that wording is listed after the table.

| Covered by the D3 wording | Not covered |
| --- | --- |
| An eMMC adapter on the EVKB for software-only testing of the stack and the user area, and a product-class board for ROM boot | Which adapter or part is bought, and when |
| No ROM-boot claim for the adapter route, and no claim that an adapter works with the RT1060 | The adoption of the flash-API driver (D2, not adopted) |
| Buying hardware is the owner's | Any hardware task, power fixture, fuse operation or physical gate (each needs its own approval) |

Framing from other records, **not part of the D3 wording**: the order "adapter first, product-class board second" is #441 Scope item 3 and the "Option for a first, partial step" of #298, which the plan's recommendation text points to. That this issue is the D3 decision and does not wait for D2 is #441 "Dependencies".

## What remains open

| # | Open item | Who decides or provides | State |
| --- | --- | --- | --- |
| 1 | **Adapter parts.** Which adapter, if any, and whether it works with the RT1060 and the EVKB socket. Requirements a candidate would have to meet: it presents the eMMC clock, command and four data lines to the microSD socket, it handles the eMMC's two supplies from the socket's supply, it lets the reset pin and the supplies be controlled or at least observed, and it can be read independently of the unit under test. None of these is shown for any adapter. | The owner (buying is the owner's, D3) | Open. No part is named or shown. |
| 2 | **Voltage.** The socket's signalling level and the supply the adapter receives, against the eMMC's I/O and core voltages. | The EVKB schematic (not retrieved, #298 H4) and the product's inputs (D8) | Open. Not verified. |
| 3 | **Switchable eMMC power** under test control, for any user-area power cut. Not available on the EVKB for an eMMC (#298). Power cuts need a controllable power fixture and their own approval (plan, validation section). | The owner, with a task-specific approval | Open |
| 4 | **Who provides the product-class board**, and where its board support lives. The issue says board support stays outside this repository. | The owner | Open. No board is named and none is available to this repository. |
| 5 | **Independent access to EXT_CSD and raw partitions**, for example a host with an MMC-capable controller and `mmc-utils`. Whether a USB card reader passes eMMC commands is not shown. | The owner | Open. Not established. |
| 6 | **Sacrificial eMMC parts**, if any OTP field is ever written (see the [profile record](emmc-provisioning-profile.md)). | The owner | Open |
| 7 | **Board custody.** The RT1060-EVKB Rev B is the single physical validation board of M8. No task may use it without the owner's explicit authorisation for **that task** (`AGENTS.md`, safety and workspace boundaries), and past approvals do not carry over. Work packages that need the same board, such as the M8 boot evidence and the secure management board tests ([secure boot test procedure](../secure-boot-board-test-procedure.md), [secure management test procedure](../history/secure-management-board-test-procedure.md)), have to be sequenced so that only one holds it at a time. An adapter test would be one more such task. The sequencing and any hand-over are the owner's and are not decided here. | The owner | Open. The board is not available to any task without the owner's go. |
| 8 | **Product inputs (D8)** that fix the slot layout and the provisioning profile: I/O voltage and bus width wiring, reset pin wiring, capacity and boot partition size, erase and write-protect group sizes, cache behaviour and timeouts, and the EXT_CSD state of units in service. The table is in the [profile record](emmc-provisioning-profile.md#product-inputs-still-needed-plan-d8). | The product | Not provided. Nothing is requested now (D8). |
| 9 | **The flash-API driver** (D2) that would let MCUboot reach the eMMC. Not adopted. The Draft PR [#435](https://github.com/wonny-labs/crux-pilot/pull/435) stays Draft. | The owner, later | Open |
| 10 | **Whether the ROM boots an eMMC from the EVKB socket**, with which settings, and whether anything of that kind should be tried at all. It would need fuse or pin settings, which are not approved. | The owner, per task | Open. Not verified. |

## Dependencies

- Issue #476 (the provisioning profile record) waits for this decision, and records every setting as deferred until the D8 inputs.
- Issues A, B and C of the plan wait for this decision and for D2 before work beyond the Draft prototype. D2 is not adopted.
- This record adds no M8, M9 or M14 exit criterion. M8's exit criteria stay on the RT1060-EVKB, and the 7 November 2026 decision that eMMC adds no M8 or M9 exit criterion is not revised.

## Method

| Item | How it was done |
| --- | --- |
| Sources | `gh issue view 441` and `gh issue view 476`, the #298 record and its evidence files, `docs/plans/secure-boot-development-plan.md` at `6c246d13` (sections 2, 5, 6, 8 and 9), `docs/boot-composition.md`, `docs/plans/emmc-reliance-design.md` and `docs/emmc-reliance-physical-gate.md`. |
| Builds, tools, hardware | None. No vendor, part or product name was used. |

This record does not claim that an eMMC adapter works with the RT1060 or the EVKB socket, that the ROM boots an eMMC from that socket, that any hardware option is available, that any board will be provided, or that any M8, M9 or M14 criterion is met.
