# eMMC provisioning profile for verified boot

> **Status:** Draft decision record. Recommendations for the project owner. It adopts nothing beyond the owner decisions it cites, makes no eMMC support claim, and adds no M8, M9 or M14 exit criterion.
> **Verified:** Source only. The EXT_CSD field numbers and bit values come from public Linux and mmc-utils source, read on 15 November 2026 (see [Method](#method)). The JEDEC eMMC standard (JESD84) was not read.
> **Not verified:** Every behaviour on a device or a board. The standard's meaning for any field, and the effect of a write under power loss. Nothing was programmed, built or run.
> **Read this first / then:** [eMMC boot and update feasibility](../boot-emmc-investigation.md) (#298) sections 1 and 3, then the [secure boot development plan](secure-boot-development-plan.md) sections 5 and 6 (issue E, decision D8), then the [validation target record](emmc-validation-target.md).

| Field | Value |
| --- | --- |
| Issue | [#476](https://github.com/wonny-labs/crux-pilot/issues/476) "Record an eMMC provisioning profile for verified boot" (plan section 5, issue E; milestone M8) |
| Date | 15 November 2026 |
| Status | **Draft.** Every setting below is **deferred until the product inputs of D8** are known. The record asks for no input now, as D8 says. |
| Records it builds on | #298 ([boot-emmc-investigation.md](../boot-emmc-investigation.md) and its [evidence](../evidence/boot-emmc/README.md)), #299 ([boot-bootloader-update-investigation.md](../boot-bootloader-update-investigation.md)), the [secure boot development plan](secure-boot-development-plan.md), the [boot composition page](../boot-composition.md) |
| Sibling record | [emmc-validation-target.md](emmc-validation-target.md) (#441, plan D3, the validation target). Any step that touches a device waits for that target. |
| Author model | `claude-sonnet-5-5` (tool: Claude Code). Independent review: see the pull request. |

## Purpose and scope

A product that boots from an eMMC and verifies what it boots needs the card configured in a defined way before the boot ROM, the first stage and the update path can rely on it. This record lists each setting of that kind, what it does, whether it can be reversed, what Crux recommends, and where the owner's decision stands. It is a planning record for the plan's issue E.

Not in scope, as in the issue: programming any device, writing any field on any board, hardware operation, fuse operation, vendor or part names, and device parameter values. The repository is public, so "the candidate devices" below means the eMMC parts a product may use, unnamed.

Boundaries that apply to every row. Publishing this record authorises no investigation, implementation, hardware operation, fuse operation or merge. **Writing a one-time-programmable (OTP) field is irreversible and needs a separate owner approval for each task** (issue #476, Boundaries). A recommendation here is never an approval.

## Evidence labels

Labels follow [#298](../boot-emmc-investigation.md#evidence-labels), with one addition for this record.

| Label | Meaning |
| --- | --- |
| Verified on source | Read in the public source of Linux, mmc-utils or U-Boot at a stated revision. It says what that code does and which field it names, not what the standard requires and not what a device does. |
| Verified by public document | A public vendor page or datasheet says so (an eMMC datasheet that restates the standard counts as a restatement, not as the standard). |
| Verified in repository | Read from a committed document of this repository. |
| Inference | Reasoned from rows named. |
| Not verified | Not retrieved, not stated by any source read, or needs hardware or the standard. |

## Summary

| # | Setting | EXT_CSD field or command | Reversible? | Recommendation (short) | Owner decision |
| --- | --- | --- | --- | --- | --- |
| S1 | Boot partition enable and acknowledge | `PARTITION_CONFIG` byte 179, bits 5:3 and bit 6 | Yes, by source (volatility of the sub-fields Not verified) | Enable one boot partition (`boot0`), acknowledge off | Deferred (D8) |
| S2 | Boot bus width and boot timing | `BOOT_BUS_CONDITIONS` byte 177 | Yes, by a datasheet restatement | Match the ROM's bus width setting, backward-compatible timing | Deferred (D8) |
| S3 | Boot-area write protection (power-on, permanent, disable bits, per-area selection) | `BOOT_WP` byte 173, `BOOT_WP_STATUS` byte 174 | Power-on: until the next power cycle. Permanent and disable bits: **no (OTP)** | No permanent protection now. Power-on protection is the candidate for production | Deferred (D8) |
| S4 | RPMB and boot configuration protection | RPMB key (`rpmb write-key`), `BOOT_CONFIG_PROT` byte 178 | RPMB key: **no (OTP)**. `BOOT_CONFIG_PROT`: Not verified | Do not use either in the boot profile | Deferred (D8) |
| S5 | Reset pin function | `RST_n_FUNCTION` byte 162 | **No (OTP)** | Leave at the shipped value until the wiring is known | Deferred (D8) |
| S6 | Enhanced (SLC) area versus default user area | `PARTITION_SETTING_COMPLETED` byte 155 and the enhanced and general-purpose fields | **No (OTP)** | Default user area throughout, until an endurance need is shown | Deferred (D8) |
| S7 | Other OTP fields the record identifies | write reliability, manual background operations, permanent user-area protection | **No (OTP)** | Set none | Deferred (D8) |
| S8 | When to program: before or after soldering | process, not a field | Not applicable | Partition settings, if any, before soldering. The rest after soldering through the proved recovery path | Deferred (D8) |

**Nothing is decided by the owner for S1 to S8.** What the plan records and this record relies on: the service recovery for M8 and M9 is a single bootloader copy that is not field-updatable (#299, owner decision of 7 November 2026), D7 (field-updatable bootloader) is approved as recommended, D8 collects the inputs before the profile and the slot layout are fixed and requests nothing now, and no hardware, key, fuse or tag operation is approved by any decision row.

## The settings

Field numbers are EXT_CSD byte indices as the public sources name them (Linux `include/linux/mmc/mmc.h` v6.12 and the mmc-utils headers). A field's behaviour on a device is Not verified for every row unless a row says otherwise.

### S1. Boot partition enable and acknowledge

| Item | Content |
| --- | --- |
| What it is | The card has two boot partitions and a user area. The ROM reads `BOOT_PARTITION_ENABLE` and selects the named boot partition with a switch command, or boots from the user area if none is named ([#298](../boot-emmc-investigation.md#1-what-the-rom-loads-from-the-boot-area-and-authentication), rows R1 and R2: Verified by public vendor document, third-party copy of the reference manual). The acknowledge bit asks the card to send an acknowledgement pattern when a boot operation begins. Whether the ROM's boot path uses or needs it is Not verified: the manual text read describes a switch command, not the card's alternative boot operation (Inference). |
| Field or command | `PARTITION_CONFIG`, EXT_CSD byte 179. Bits 5:3 are `BOOT_PARTITION_ENABLE` (0 none, 1 `boot0`, 2 `boot1`, 7 user area), bit 6 is the boot acknowledge, bits 2:0 are `PARTITION_ACCESS`. Verified on source: mmc-utils `mmc_cmds.c` `do_write_boot_en` and `mmc.h`; Linux `mmc.h`. The same byte also holds `PARTITION_ACCESS`, so a write must read the byte first and change only its own bits, as mmc-utils does. Candidate tool: mmc-utils `bootpart enable`. |
| Size of the boot partition | `BOOT_SIZE_MULT` (byte 226, read-only): Linux sizes `boot0` and `boot1` as that value times 128 KiB (E1 in [#298](../evidence/boot-emmc/emmc-semantics-and-hardware.md)). The value is a device parameter and an input of D8. |
| Reversible? | **Yes by source.** mmc-utils and U-Boot write the field repeatedly and refuse nothing on their own. A datasheet restatement lists the enable field as non-volatile and `PARTITION_ACCESS` as volatile (E7, E9: the assignment of sub-fields is an Inference). Whether a protection setting (S4, `BOOT_CONFIG_PROT`) can freeze it is Not verified. Whether a CMD6 write of this byte is atomic under power loss is Not verified (E12). |
| Recommendation | Enable **one** boot partition (`boot0`) with the bootloader image in it, and leave the acknowledge off. Reason: the plan's service recovery is a single bootloader copy (#299), so a second copy in `boot1` adds a selector that software, not the ROM, would have to switch (#298 section 3, Inference), and the ROM text read needs no acknowledge (Inference). The first stage must fit the boot partition, and whether the IVT offset `0x400` counts from the start of a boot partition is Not verified (#298 X1), so the choice of partition and the slot layout stay open until a board shows it. |
| Alternative | Boot from the user area (value 7, no boot partition used). It avoids the boot partition mechanism but puts the first stage in the user area next to the slots and the file system, and removes the possibility of protecting it separately (S3). Or enable the acknowledge if a board bring-up shows that the ROM or a tool expects it. |
| Owner decision | **Deferred until product inputs (D8):** which boot partition size the part offers, and whether units in service already have a boot partition enabled. |

### S2. Boot bus width and boot timing against the ROM's settings

| Item | Content |
| --- | --- |
| What it is | The ROM takes the uSDHC port, MMC boot, the bus width and other boot parameters from fuses, with GPIO overrides when `BT_FUSE_SEL` is 0 (R5). It resets the host, identifies the card at about 400 kHz, sends CMD0, switches to the wider bus and higher frequency, then selects the boot partition (R6). The card also has its own boot bus setting. Whether the ROM reads it is Not verified: the manual text read names the fuse-selected width, not byte 177 (Inference). |
| Field or command | `BOOT_BUS_CONDITIONS`, EXT_CSD byte 177. Bits 1:0 are the boot bus width (0 x1, 1 x4, 2 x8), bit 2 says whether the bus condition is retained after the boot operation, bits 4:3 are the boot mode (0 single data rate with backward-compatible timing, 1 single data rate high speed, 2 dual data rate). Verified on source: mmc-utils `mmc_cmds.c` `do_boot_bus_conditions_set`. Candidate tool: mmc-utils `bootbus set`. |
| Reversible? | **Yes by a datasheet restatement.** The restatement lists the field as persistent across power failure, reset and CMD0 and rewritable (E7: "R/W/E"). The standard was not read. The ROM-side half is separate: the bus width and port fuses are fuse operations, irreversible once burned, and **no fuse operation is approved** (plan section 6). On a board that allows GPIO overrides they are not fuse operations (R5). |
| Recommendation | Once the wiring is known, set the card's boot bus width to the width the product wires and the ROM is configured for, with the backward-compatible single-data-rate timing, and let the bus condition reset to x1 after boot (the ROM identifies the card at a low frequency before it switches to a wider bus, R6, so x1 is probably the state it starts from: Inference). Reason: the card and the ROM should agree, and the slowest timing probably has the fewest signal-integrity assumptions (Inference). The first stage must not depend on this state, because the stack resets the card at initialisation (#298 section 4, E18). |
| Alternative | Retain the bus condition after boot, or a faster mode, if a board shows that boot time matters and the signal quality allows it. A wider bus than wired, or a 1.8 V timing mode, needs the I/O voltage (D8) and is not recommended before it is known. |
| Owner decision | **Deferred until product inputs (D8):** the bus width wiring, the I/O voltage, which uSDHC the product uses, and the product board's fuse or pin boot settings. |

### S3. Boot-area write protection

| Item | Content |
| --- | --- |
| What it is | A boot partition can be protected against writes. The variants differ in how long the protection lasts and whether it can be undone. Linux marks the boot partitions read-only by default in the host, which is a host flag and sends nothing to the card (E1, E2). |
| Field or command | `BOOT_WP`, byte 173, and the read-only `BOOT_WP_STATUS`, byte 174. Verified on source (mmc-utils `mmc.h`, Linux `mmc.h`): bit 0 power-on protection enable, bit 2 permanent protection enable, bit 6 and bit 4 the bits that disable power-on and permanent protection, bit 7, bit 1 and bit 3 a selector that applies the protection to one boot area instead of both, and in the status byte one power-on and one permanent bit per area. The meaning of the disable bits and of the selector bits in the standard is Not verified. Candidate tools: mmc-utils `writeprotect boot set` (power-on protection by default, permanent protection only when built with `DANGEROUS_COMMANDS_ENABLED`, E3), Linux `ro_lock_until_next_power_on` (E1). |

| Variant | What it does | Reversible? | Label |
| --- | --- | --- | --- |
| None (shipped state) | The boot partitions can be written | Not applicable | Verified on source for the tools. The shipped state of any device is an input of D8. |
| Power-on protection | Read-only until the next power-on. Linux describes it as read-only until the next power-on (E1), and a datasheet restatement says a hardware reset disables it (E8); that a power cycle releases it follows from E1 and is an Inference for a board (E9). A plain CMD0 probably does not release it, but no source states it (E9). | **Yes, by power cycle.** It must be set again after every power-on. | Verified by public document (restatement) for the release. CMD0 Not verified. |
| Permanent protection | Read-only for the life of the device | **No (OTP).** mmc-utils compiles it in only behind a build flag and calls it one-time-programmable and unreversible (E3). | Verified on source |
| Disable bits for power-on and permanent protection | Their meaning is Not verified. By their names they would stop the corresponding protection from being set, which would make them irreversible too (Inference). | **No (OTP)** in every source read (E10) | Semantics Not verified |
| Per-area selector | Applies the protection to one of the two boot areas | Follows the variant it selects | Field names Verified on source. Meaning in the standard Not verified. |

| Item | Content |
| --- | --- |
| Constraint from the plan | A bootloader update from the application needs the boot partition writable at that time. Permanent protection would end any bootloader update and any in-field recovery of that partition (#298 section 3). Service recovery for M8 and M9 is a single copy that is not field-updatable (#299), and that is decided again after #165, #298 and the M8 hardware results. Zephyr's MMC stack has no access to `BOOT_WP` (E19), so setting power-on protection from the product is a software gap that needs separate scope. |
| Recommendation | **Do not set permanent protection or any disable bit now.** For development units keep the boot partitions unprotected, so a unit stays rewritable and sacrificial. For production, plan **power-on protection**, set by the first stage or a service tool after each power-on, as the candidate: it keeps the application from overwriting the first stage and is undone by a power cycle. Reason: it gives most of the protection of the permanent form without removing the recovery path that D5 wants to keep. Permanent protection is a per-unit decision to take only after the first stage and the recovery path are proved on the product's board. |
| Alternative | Permanent protection of the boot partition holding the bootloader, set at the end of a proved manufacturing flow, if the product accepts that the bootloader can never be updated on that unit and the plan's decision D7 stays at "service recovery". It is the strongest protection and the only one that cannot be removed by a power cycle. |
| Owner decision | **Deferred until product inputs (D8):** the shipped protection state of units in service, and the product's requirement on field update of the bootloader (D7). Each protection write needs its own approval. |

### S4. RPMB and boot configuration protection

| Item | Content |
| --- | --- |
| What it is | The replay-protected memory block (RPMB) is a third area of the card, accessed with an authenticated protocol after a key is programmed. `BOOT_CONFIG_PROT` is a protection register for the boot configuration. |
| Field or command | RPMB: `RPMB_SIZE_MULT`, byte 168, read-only (Linux `mmc.h`); key programming with mmc-utils `rpmb write-key`, whose help text calls it one-time-programmable and unreversible (Verified on source). `BOOT_CONFIG_PROT`: byte 178, which mmc-utils only prints and Linux and U-Boot do not reference in the files read (E12). |
| Reversible? | RPMB key: **no (OTP)** by the mmc-utils help text. `BOOT_CONFIG_PROT`: Not verified. A datasheet restatement lists it as R/W and R/W/C_P (E7), which would make part of it OTP and part cleared by power failure, but its bit assignment is not recorded (Not verified). |
| Recommendation | Leave both out of the boot profile. Reason: the boot path does not use RPMB (the ROM reads partitions, #298 section 1), Zephyr's stack has no RPMB path (E19), and a key is irreversible. RPMB might be a source for a hardware anti-rollback counter (Inference; decision D4 says sources other than a fuse-backed counter are Not verified), so the question comes back with D4 and D1, not here. Do not set a boot configuration protection that freezes S1 or S2 until a board has shown that the values work. |
| Alternative | Program an RPMB key at manufacturing if D4 later selects it as the counter source. Needs its own key custody decision (D6 covers HAB keys, not this one) and approval. |
| Owner decision | **Deferred until product inputs (D8)** and D4. |

### S5. Reset pin function

| Item | Content |
| --- | --- |
| What it is | The card's reset input (RST_n) can be enabled as a hardware reset. A hardware reset puts the card into its Pre-Idle state and releases power-on write protection (E8, a datasheet restatement). It is also one of the ways the card returns to boot mode (E8). |
| Field or command | `RST_n_FUNCTION`, EXT_CSD byte 162, bits 1:0. By mmc-utils source: 1 is permanently enabled, 2 is permanently disabled, and mmc-utils refuses to change the field once it holds 1 or 2. Candidate tools: mmc-utils `hwreset enable` and `hwreset disable`, U-Boot `mmc rst-function` (E4, E5). Linux uses the hardware reset only when the field is 1 (E5). |
| Reversible? | **No (OTP)** in every source read (E5, E10). |
| Why it matters here | An MCU reset does not remove eMMC power (#298 H7). A way to reset the card without cutting its supply is useful after an update and for the power-on protection of S3 (E8). The RT1062 pad data shows a `RESET_B` pad on the second uSDHC (#298 H3), but whether a product wires it, and whether the ROM drives it, is Not verified. |
| Recommendation | **Leave the field at the shipped value until the product's reset wiring is known.** If the product wires RST_n to a signal that the processor or a reset supervisor controls, enable it permanently on that product's units, and only then. Reason: enabling it on a card whose pin is not connected, or is connected to something else, is permanent. Disabling it permanently has no benefit that outweighs losing the option and is not recommended. |
| Alternative | Leave it unset on all units. The cost is that the card can be reset only by removing its power, which a product may or may not be able to do. |
| Owner decision | **Deferred until product inputs (D8):** whether the reset pin is connected, and to what. |

### S6. Enhanced (SLC) general-purpose area versus the default user area

| Item | Content |
| --- | --- |
| What it is | If the device supports partitioning, part of the user area or general-purpose partitions can be given the "enhanced" attribute, which mmc-utils names the enhanced attribute (`EXT_CSD_ENH_USR`, `EXT_CSD_ENH_ATTRIBUTE_EN` in its `mmc.h` and `mmc_cmds.c`, Verified on source). What the attribute means in the standard, whether a device implements it as a lower-density, higher-endurance ("SLC") mode, and what it costs in capacity are **Not verified** here: the standard was not read and no source read says. |
| Field or command | `PARTITION_SUPPORT` byte 160 (read-only, whether partitioning is supported), `MAX_ENH_SIZE_MULT` bytes 159 to 157 (read-only), `ENH_START_ADDR` bytes 139 to 136, `ENH_SIZE_MULT` bytes 142 to 140, `GP_SIZE_MULT` from byte 143, `PARTITIONS_ATTRIBUTE` byte 156, and `PARTITION_SETTING_COMPLETED` byte 155. Verified on source: mmc-utils `mmc_cmds.c` (`enh_area set`, `create gp partition`, and the limit it computes from the maximum enhanced size and the erase and write-protect group sizes, bytes 224 and 221) and `mmc.h`. mmc-utils rounds the enhanced start and size to a unit derived from bytes 221 and 224 and does not refuse an unaligned request (`do_enh_area_set`, `do_create_gp_partition`); whether the standard requires alignment is Not verified. Candidate tools: mmc-utils `enh_area set` and `gp create`. |
| Reversible? | **No (OTP).** mmc-utils calls both commands one-time-programmable and unreversible. They refuse to run once `PARTITION_SETTING_COMPLETED` is set, and that byte is written once. mmc-utils says that a power cycle is needed for the settings to take effect (Verified on source). |
| Effect on the Crux design | The slot layout is raw offsets in the user area ([plan](secure-boot-development-plan.md) section 3), and the M14 design allows its volume at a sector offset ([emmc-reliance-design.md](emmc-reliance-design.md)). Partition settings change the capacity and the address map of the user area, so they must be fixed before the slot layout is, and a mistake cannot be undone. |
| Recommendation | **Default user area throughout** as the baseline, with no OTP step. Reason: no evidence shows that the product's write load needs the enhanced attribute (the M14 workloads and the trailer replay are simulator results, not device endurance results), and the setting is permanent, costs capacity by an amount that is Not verified, and fixes the slot layout. Revisit when D8 gives the maximum enhanced size, the group sizes and the product's write load. |
| Alternative | Give an enhanced attribute to the part of the user area that takes frequent small writes, for example the file-system volume and the regions with image-state writes, sized and aligned to the write-protect group. It trades capacity for endurance that no result of this repository has measured. |
| Owner decision | **Deferred until product inputs (D8):** whether the device supports partitioning, the maximum enhanced size, the group sizes, the capacity budget of the product and its write load. |

### S7. Other OTP fields the record identifies

Each one is a one-time-programmable write by mmc-utils help text. None is recommended for the boot profile, and each would need its own approval.

| Field | Command (candidate) | What it does | Recommendation |
| --- | --- | --- | --- |
| Write reliability per partition | mmc-utils `write_reliability set` | Marks a partition as one where writes are reliable (the standard's reliable write mode) | Do not set. Zephyr's stack issues writes without the reliable-write bit (E19), and the M14 design assumes that a single-sector write is not atomic. Revisit with a stack change. |
| Manual background operations | mmc-utils `bkops_en manual` | Enables manual background operations. The automatic form is not one-time-programmable by the same help text, and needs a device that supports it. | Do not set. No Crux code starts or tracks background operations (E19). |
| Permanent user-area write protection | mmc-utils `writeprotect user set perm` | Permanently protects a user-area range | Do not set in the boot profile. It would fix part of the slot layout for the life of the unit. |
| `PARTITION_SETTING_COMPLETED` | part of S6 | Seals the partition settings | Only with S6. |
| Fields the standard defines that no source read names | not applicable | The standard may define more OTP fields. The list above is the commands whose mmc-utils help text calls the change one-time-programmable. Two further mmc-utils commands change write behaviour without that wording: `rpmb secure-wp-mode-on`, after which the access to the write-protection fields depends on a secure mode setting (the help text says so), and a command that disables 512-byte emulation (a 4 KB native sector, relevant to the 512-byte sector assumption). Their reversibility is Not verified. | The completeness of this list is **Not verified** until JESD84 is read. |

### S8. Programming before or after soldering

| Item | Content |
| --- | --- |
| What it is | A BGA eMMC is soldered to the board before it can be reached in circuit. The settings can be written in a programming socket or by the supplier before soldering, or in circuit after it. |
| Ways to write, with their Not verified points | **A host with an MMC-capable controller and mmc-utils**, in a socket or on a board that exposes the card to that host: the candidate named in the plan ([section 7](secure-boot-development-plan.md#7-tooling)). Whether a USB card reader passes eMMC commands is not shown by any source read. **The ROM serial downloader with NXP's flashloader**, which the vendor's guide uses to program SD and eMMC images (#298 V9, V10): whether the current flashloader programs an eMMC on the RT1060, and whether it can write EXT_CSD at all, is Not verified (#298 X6). **Programming by the supplier** before delivery: possible in principle, and what a supplier offers is an input of D8. |
| Reflow | Whether data and configuration written before soldering survive the reflow profile is a question for the device's datasheet and its supplier. **Not verified** for the candidate devices, and no source read answers it. |
| Recommendation | Split by reversibility. **Before soldering**, write only the OTP partition settings of S6 if the owner chooses them, on a programmer, where a mistake costs one part and nothing is soldered. **After soldering**, write the boot partition content and the reversible fields (S1, S2), through the recovery path that #296 requires before any physical boot experiment, so the settings are tested on the path the product uses. Write the protection and OTP fields of S3 to S5 and S7 last and only after a test unit has booted. Reason: a reversible field can be corrected on the board, an OTP field cannot, and a bootloader written in the socket would not exercise the in-circuit path. |
| Alternative | Write everything, including the bootloader image, before soldering, if the supplier confirms retention through reflow and no in-circuit path exists. It shortens the line but leaves the in-circuit path untested. |
| Owner decision | **Deferred until product inputs (D8):** the product's manufacturing flow, whether units arrive pre-programmed, and the supplier's reflow statement. |

## Product inputs still needed (plan D8)

The table lists what the profile needs. It records **no device parameter value**, and nothing is requested now (D8, owner decision of 15 November 2026: "Collect before the slot layout and provisioning profile are fixed").

| Input | Needed for | Source | State |
| --- | --- | --- | --- |
| I/O voltage and core supply of the eMMC, and whether both can be switched under test control | S2 (timing mode), the validation target, any power-cut case | The product's schematic | Not provided |
| Bus width wired (1, 4 or 8 bit) and which uSDHC carries it | S2, the ROM's width fuse or pin setting | The product's schematic | Not provided |
| Reset pin connected (yes or no), and to what | S5 | The product's schematic | Not provided |
| EXT_CSD state of units already in service, if any: boot partition enable, boot bus conditions, boot and user write-protection state, reset pin function, partition settings completed, enhanced areas | S1 to S7, and which writes are still possible | Reading EXT_CSD of a deployed unit, which is a hardware task with its own approval | Not provided. Whether any unit is in service is unknown to this record. |
| Capacity, boot partition size, whether partitioning is supported and the maximum enhanced size | S1, S6, the slot layout and the size budget of the first stage | The device datasheet | Not provided |
| Erase and write-protect group sizes | S3, S6 (alignment), the slot layout | The device datasheet | Not provided |
| Cache behaviour, reliable-write support and timeouts | S7, the flush policy of the backend | The device datasheet | Not provided |
| The product board's ROM boot settings (fuses or pin overrides) | S2 | The product's boot plan | Not provided |
| Manufacturing flow: socket, supplier programming, in-circuit | S8 | The product's process | Not provided |
| Reflow data retention statement of the supplier | S8 | The supplier | Not provided |
| Whether the bootloader must be field-updatable | S3 | Plan D7, the product requirement | Not provided |

## Dependencies and order

- The profile and the slot layout wait for these inputs and for the [validation target](emmc-validation-target.md). Work beyond planning waits for a validation target (D3 chose the route; **no target exists yet**) and the adoption decision (D2, not adopted), as the issue says.
- If the owner later chooses any OTP write, the order this record proposes is: partition settings (S6) and a power cycle, then the boot partition content and S1 and S2, then a boot test, then S3 to S5 and S7. This is a proposal, not a procedure, and each write needs its own approval.

## Not verified

| Item | Needs |
| --- | --- |
| The standard's text for every field above, including bit meanings, the reset behaviour of each byte and the disable bits | JESD84 (the owner's copy, if any) |
| Whether the ROM uses `BOOT_BUS_CONDITIONS` or the acknowledge bit | A board, or the full reference manual |
| Whether a CMD6 write of `PARTITION_CONFIG` or `BOOT_WP` is atomic under power loss, and whether CMD0 releases power-on protection | The standard, or a device test |
| The semantics of `BOOT_CONFIG_PROT` and of the write-protect disable bits | The standard |
| Whether a USB card reader or the flashloader can write EXT_CSD of an eMMC, and which MMC-capable host controller the project would use | A hands-on check, which needs approval |
| Reflow retention, the capacity cost of the enhanced attribute and the shipped state of any device | The device datasheet and its supplier (D8) |
| Whether a unit in service exists | The product owner |

## Method

| Item | How it was done |
| --- | --- |
| Field numbers and bit values | Read on 15 November 2026 from the public files `include/linux/mmc/mmc.h` and `Documentation/driver-api/mmc/mmc-dev-parts.rst` (Linux v6.12), and `mmc.h`, `mmc.c` and `mmc_cmds.c` of the mmc-utils repository (the default branch at the read, not tied to the revision pinned in #298's evidence). Only the header constants, the command help texts and the code that composes the byte values were used. |
| Other evidence | Rows E1 to E19, R1 to R12 and X1 to X8 are cited from [#298's evidence](../evidence/boot-emmc/README.md) as written there, and not re-derived. |
| Plan and issues | `gh issue view 476` and `gh issue view 441`, and the secure boot development plan at `6c246d13`. |
| Builds, tools, hardware | None. The standard was not read. No vendor, part or product name was used. |

This record does not claim that any eMMC boots on any board, that a setting works on a device, that a tool can write a field on the RT1060 platform, that a field is OTP in the standard (only that the tool says so), that permanent protection or any OTP write is advisable, or that any M8, M9 or M14 criterion is met.
