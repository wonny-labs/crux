# Secure boot verification ladder: what each level can prove

> **Status:** Orientation and review page. It decides nothing and approves no hardware operation, key, fuse operation, purchase or merge. The decisions are in the pages it points to.
> **Verified:** Only what the cited pages record: build and host results of the boot work (by build and by command), and what the repository's records say about the simulators. This page runs no build, no test and no hardware, and uses no document under a non-disclosure agreement.
> **Not verified:** Every boot, refusal, confirm, revert, update, power-cut, recovery, HAB and eMMC claim on a board. **No boot experiment has run on any board** (see the [boot overview](boot-overview.md)), so every board row below is Not verified.
> **Read this first / then:** the [boot overview](boot-overview.md) and the [secure boot and update review](secure-boot-and-update-review.md), then this page. A product team that brings up its own board keeps its board-specific checklist with its own documentation.

Labels are those of the boot records: **Verified by build**, **Verified by command** (a host test, a `native_sim` run, a model run or a tool run), **Verified on pinned source**, **Verified by public vendor document**, **Verified in repository**, **Inference**, **Not verified**. A build proves that something configures, builds and signs. It never proves that a board boots. A statement without a label points to a page that carries the label.

## 1. Why this page exists

Secure boot and update for an i.MX RT1060 product cannot be verified in one place. Some properties can be shown on a laptop, some only on an evaluation board, and some only on the product's own board with its own eMMC. The project will build the base code, the tests, the infrastructure and the documentation here and in the reference product repository, and a product team will do the final eMMC verification on real product boards. This page says, for each capability, **the lowest level at which it can be proven, how far it has got, who runs the next step, and what a pass at that level still leaves unproven**. It is a map for planning and for reading evidence, so that an EVKB result is not read as an eMMC result and a build is not read as a boot.

Two scales are used and must both be declared with a result:

- The **verification level** (L0 to L5, section 2) says where a claim was tested.
- The **trust level** (T0 to T3, [plan, section 3](plans/secure-boot-development-plan.md)) says which security property holds. A result at a high level can still be T0.

## 2. The levels

| Level | Name | What runs | Who runs it | Approval needed |
| --- | --- | --- | --- | --- |
| L0 | Host | Host builds and tests, CI builds that sign and verify but boot nothing, offline checkers on files, Python models. Includes the build-only check of the [boot composition](boot-composition.md). | Automation (CI and local runs) | The task's approval |
| L1 | `native_sim` | Zephyr code compiled as a host process, including the eMMC simulator and the replays built on it. A real-MCUboot run on `native_sim` is proposed ([update agent proposal](plans/update-agent-design-proposal.md)) and not built. | Automation | The task's approval |
| L2 | Simulator | A model of a medium or a device behaviour (cache orderings, torn writes, power cuts) driven from Host or `native_sim`. A result is a result about the model. A replay on the eMMC simulator is counted at L2 for what it says about the model, and at L1 only for the Zephyr code that runs in it. | Automation | The task's approval |
| L3 | EVKB with NOR | The RT1060-EVK Rev B (EVKB) with its 8 MiB QSPI NOR, in open configuration, through a probe and the serial console. | The board owner, task by task | Explicit approval for the current task, a recovery path first, and a recorded decision on the FlexSPI write-path finding ([issue #165](https://github.com/wonny-labs/crux-pilot/issues/165)), or an approval to run with it open, before any bootloader NOR write ([board test procedure](secure-boot-board-test-procedure.md), section 2) |
| L4 | EVKB with eMMC on a microSD adapter | The EVKB with an eMMC presented to its microSD socket by an adapter, for software-only tests of the stack and the user area. **Not available:** no adapter is chosen, and that any adapter works with the RT1060 is not shown ([validation target](plans/emmc-validation-target.md)). | The board owner, once an adapter is chosen, bought and approved | Task approval, plus a separate approval for any power-cut fixture or fuse or pin setting |
| L5 | Product-class board with eMMC | A product board with an eMMC on a controller the boot ROM can select, with the product's wiring, supply and reset. Board support stays outside this repository. | The product team | The board owner's and product's approvals; any fuse or one-time-programmable write needs its own |

What exists at each level (Verified in repository):

| Level | Reached |
| --- | --- |
| L0 | Yes: the composition builds, signs and verifies with the public test key in CI (**Verified by build**). Offline checkers exist: the [image inspector](boot-image-inspection.md), the [HAB structure checker](boot-hab-status.md), the [reproducibility comparison](boot-reproducibility.md) and the boot configuration check. The checkers have run on synthetic inputs only. |
| L1 | Partly: the eMMC simulator and the FatFs and Reliance Edge power-cut replays run on `native_sim` (**Verified by command**). No MCUboot code has run on `native_sim`. |
| L2 | Yes, for MCUboot's trailer sequences on modelled cache behaviours: all 566,692 cases kept the safety properties when slots sit on native-unit boundaries (**Verified by command, models only**; [replay record](evidence/boot-emmc/trailer-replay/README.md)). |
| L3 | **No boot result.** Earlier physical work on the EVKB ran other images, not MCUboot ([baseline](baseline.md)). A first bench session is prepared in the [board test procedure](secure-boot-board-test-procedure.md) and the [bench session kit](secure-boot-bench-session.md) and has not been run. |
| L4 | No. No adapter, no target, no result. |
| L5 | No. No product-class board is available to this repository. |

## 3. The three tiers of the structure

The work is split over three kinds of repository. A result belongs to the tier that owns the thing tested.

| Tier | Owns | Tests and evidence it can produce | Label of this description |
| --- | --- | --- | --- |
| **Crux** (this repository, public) | Platform mechanisms: the boot composition recipe and the EVKB board files, the porting guide, the image checkers, the device-control tool, the eMMC simulator, replays and an unmerged driver prototype, the Experimental image-state contract with its Host test double, and the proposal for the update agent. | Levels L0 to L2 in full, and L3 for the EVKB bench cases when the board owner runs them. Never a product-board result. | **Verified in repository** for the ownership ([architecture overview](architecture.md), [boot overview](boot-overview.md), [porting guide](boot-porting-rt1062.md)); the image-state code is on `main` (Host double only), while the driver prototype and the update agent are not on `main` as code |
| **crux-controller** (separate repository, out-of-tree product-shaped reference) | An integration consumer of Crux on the EVKB. It is the intended second consumer of the image-state contract, which the contract needs before it can leave Experimental (the [contract proposal](plans/image-state-contract-proposal.md) also needs the update agent and target evidence), and it holds the update transports and the reboot policy. | Integration results on the EVKB: a transport receiving an image, an authorised request, a reboot decision. Software evidence on L0 to L1 and board evidence on L3 only. | That it is a separate out-of-tree reference: **Verified in repository** ([architecture overview](architecture.md)). That it is the second consumer and holds transports and the reboot policy: **Inference**, not recorded in a decision of this repository. Crux's [Reboot service](reboot-service.md) is the mechanism, and [ADR-0004](decisions/0004-product-composition-of-management-services.md) puts composition choices with the product. |
| **Product repositories** (private, outside this repository) | Board support and board files, the eMMC first-stage image, eMMC provisioning, the HAB keys, the signing hosts and the fuse plan, the manufacturing flow. | The L5 results: ROM boot from the eMMC, closed configuration, product wiring, power cuts on the product's supply. | **Verified in repository** for the boundary (plan, section 10: product board support, product names and part numbers stay out of this public repository; [boot overview](boot-overview.md), section 1: keys are the product's business) |

Crux gives a product team the tools and the checks. It does not hold the product's board, keys or eMMC data, and it cannot report their results.

## 4. The ladder, capability by capability

Summary first. "Next" is who runs the next step: **automation** (CI and local runs), the **board owner** (the person who owns the board under test and approves each hardware step on it), or the **product team**. The highest label is the best result so far at any level.

| # | Capability | Lowest level that can prove it | Best label so far | Next step by |
| --- | --- | --- | --- | --- |
| C1 | Signature verification | L0 for the signing tool; L3 for MCUboot on a target (L1 once a real-MCUboot run exists) | Verified by build (signing tool only) | Board owner |
| C2 | Boot refusal of bad images | L3 (the tool-level refusals are L0) | Verified by build (tool); the boot refusal is Not verified | Board owner |
| C3 | Anti-rollback and version policy | L0 for the rule; L3 for bootloader selection; L5 for a hardware counter | Verified on pinned source; design only | Automation, then the product team |
| C4 | Test request, confirm and revert | L0 for the logic; L1 for real bootutil; L3 for real flash | Verified by command (models only) | Automation, then the board owner |
| C5 | Power-cut safety | L2 for ordering; L3 for real NOR; L4 or L5 for eMMC | Verified by command (models only) | Automation, then the board owner |
| C6 | Recovery path | L3 | Not verified | Board owner; product team for the product |
| C7 | HAB, open configuration | L0 for structure; L3 for ROM behaviour on NOR; L5 for the eMMC layout | Verified by command (structure checker, synthetic images) | Approval for keys and a tool run first, then automation |
| C8 | HAB, closed configuration | L5, on a board that may be locked | Not verified (not started) | Product team |
| C9a | eMMC software: slots, flush, flash API | L2 for the stack logic; L4 for a real device | Verified by command (models only) | Automation; board owner for L4 |
| C9b | eMMC boot from the boot partition, provisioning | L5 | Not verified (not started) | Product team |
| C10 | Update transport | L0 or L1 for request handling; L3 for a flash write while running; L5 for the product network | Not verified (not started) | Automation and the reference product repository, then the board owner |

### C1. Signature verification

| Item | Content |
| --- | --- |
| Lowest level | Two questions. Does the signing tool accept what the build signs? **L0.** Does MCUboot check the signature and key hash of the image it boots? **L3.** A run of the real MCUboot code on `native_sim` (L1) is proposed and not built, and would test the logic, not the ROM, the memory map or the timing. |
| Current state | The signing tool: **Verified by build.** The CI check signs the application with MCUboot's public test key and `imgtool verify` passes. MCUboot's check on every boot in RAM load: **Verified on pinned source**; **Not verified** by any run. |
| Evidence | [Boot composition](boot-composition.md), [`scripts/test-boot-composition.sh`](../scripts/test-boot-composition.sh), [review, section 9](secure-boot-and-update-review.md). |
| Next step | The board owner runs T1 of the [board test procedure](secure-boot-board-test-procedure.md) with a private development key, after the approvals of its section 2. An L1 run needs an approved work package ([update agent proposal](plans/update-agent-design-proposal.md), Proposed). |
| Stays unproven at L0 | That MCUboot accepts the signature, that the ROM starts MCUboot, the verification time on the target and the cost of MCUboot's crypto backend (the bundled tinycrypt is kept; boot time was not measured). The public test key must never reach a board, so this CI pass says nothing about a key a product would use. |
| Stays unproven at L3 | Production key custody and rotation ([plan](plans/secure-boot-development-plan.md)), and anything on eMMC. |

### C2. Boot refusal of bad images

| Item | Content |
| --- | --- |
| Lowest level | **L3** for MCUboot refusing an unsigned image, an image signed with another key and an image changed after signing (cases T2 to T4). The refusals of the signing tool and the check that an image fits its slot are L0. In open configuration the ROM refuses nothing, so a ROM refusal can only be shown on a board that may be closed (C8). |
| Current state | The signing tool refuses a key of another type and a changed byte: **Verified by build.** The inspector's `fit` decision on synthetic images: **Verified by command** (a model decision). The check of the CI-built images against the inspector and `imgtool` is wired into the composition check, and no result of it on a real build is recorded: **Not verified**. MCUboot's refusal on a board: **Not verified**. |
| Evidence | [Boot image inspection](boot-image-inspection.md), [boot composition](boot-composition.md), [board test procedure](secure-boot-board-test-procedure.md), cases T2 to T4. |
| Next step | Automation reads a CI run of the image check on a real build. The board owner runs T2 to T4 after T1. |
| Stays unproven at L0 | That MCUboot, not the tool, refuses the image, and that the ROM or the bootloader cannot be replaced by someone with flash or debug access (T0 has no hardware root of trust). |

### C3. Anti-rollback and version policy

| Item | Content |
| --- | --- |
| Lowest level | **L0** for the application-side rule (strictly newer on major, minor and revision, before any NOR write). **L3** for what the bootloader selects (the highest version, the slot number on equal versions). **L5** for a hardware counter, because it is expected to need a fuse-backed source on a board that may be locked (the [plan](plans/secure-boot-development-plan.md) names that option; other sources are Not verified). |
| Current state | The rule is decided as a design and adopted as Experimental in the [image-state contract proposal](plans/image-state-contract-proposal.md). The first code (the version compare and outcome functions among others, with a Host test double) is on `main` and tested on Host in CI; see the [image state contract](image-state-contract.md). It has no bootloader provider and no `native_sim` or board result. RAM load has no bootloader rejection of an older image (**Verified on pinned source**), so the application's check is the only one. The check that the build does not compare build numbers is in [`scripts/check-boot-config.py`](../scripts/check-boot-config.py), called by the composition check. A hardware counter: not started. |
| Evidence | [Image-state contract proposal](plans/image-state-contract-proposal.md), [update agent proposal](plans/update-agent-design-proposal.md), [review, section 8](secure-boot-and-update-review.md). |
| Next step | Automation, for the bootloader provider and the rest of the contract, each change with its own review. The board owner for selection cases on the EVKB. The product team for a counter: an application-side check only until the product's closed-configuration plan is turned into a fuse plan. |
| Stays unproven at L0 | That the bootloader picks the slot the rule expects, and any resistance to an attacker who can write flash: at T0 and T1 an older signed image can be written in place of a newer one (**Inference**). |

### C4. Test request, confirm and revert

| Item | Content |
| --- | --- |
| Lowest level | **L0** for the state logic and the attempt record, against a Host double. **L1** for the real bootutil code on a flash simulator (proposed). **L3** for real NOR, the trailer writes and the whole-slot erase at revert. |
| Current state | The selection, confirm and revert rules: **Verified on pinned source.** MCUboot's trailer sequences on the eMMC simulator's models: **Verified by command, models only** (see L2 above). The contract is Experimental, its first code (Host test double only) is on `main`, and the update agent is a Proposed design. Nothing ran on a board. Which file a bench revert test uses is open (cases T5a and T5c), and how MCUboot treats the padded confirmed image that Zephyr v4.4.2 also writes is **Not verified**. |
| Evidence | [Review, sections 4 and 5](secure-boot-and-update-review.md), [trailer replay](evidence/boot-emmc/trailer-replay/README.md), [update agent proposal](plans/update-agent-design-proposal.md). |
| Next step | Automation for L0 and L1 once work packages are approved. The board owner for T1 and T5; the update cases T7 need the update agent first. |
| Stays unproven at L0 and L1 | The stock test request being a silent no-op when the application runs from slot 1, the whole-slot erase time, the survival of the retained boot information across the jump to SDRAM, and every eMMC property (alignment, flush) that a NOR run does not exercise. |

### C5. Power-cut safety

| Item | Content |
| --- | --- |
| Lowest level | **L2** for ordering properties (models, and Host fault injection once it exists). **L3** for real NOR, with a controllable power fixture and its own approval (T6). **L4** only if the eMMC's supplies can be switched under test control, which the EVKB cannot do for an eMMC; otherwise **L5**. |
| Current state | **Verified by command, models only:** MCUboot trailer sequences, and power-cut replays of FatFs and Reliance Edge on the eMMC simulator. Bootloader NOR writes on hardware wait for a recorded decision on the FlexSPI write-path finding ([issue #165](https://github.com/wonny-labs/crux-pilot/issues/165)), or an approval to run with it open: the write path failed a data-closure check ([flash XIP evidence](flash-xip-evidence.md)), and no fix is merged. On a board: **Not verified.** |
| Evidence | [Trailer replay](evidence/boot-emmc/trailer-replay/README.md), [replay record](evidence/emmc-reliance/replay-reliance/README.md), [flash XIP evidence](flash-xip-evidence.md), [board test procedure](secure-boot-board-test-procedure.md) (T6). |
| Next step | Automation keeps the replays current. The board owner runs T6 after T1 to T5, with the fixture of its section 3, once the decision on the FlexSPI write-path finding is recorded. The product team runs eMMC cuts on the product's supply. |
| Stays unproven at L2 | Real device behaviour. A replay shows an ordering of writes in a model. Whether an eMMC cache keeps write order without a flush is Not verified, and a cut inside a NOR write while executing from that NOR is the open FlexSPI question. |

### C6. Recovery path

| Item | Content |
| --- | --- |
| Lowest level | **L3** on the EVKB: restoring a known good image through the probe, and the ROM serial downloader. A product board needs its own proof at **L5**. Nothing below L3 can show it. |
| Current state | **Not verified.** The restore flow of section 6 of the board test procedure is written and has not been run with that procedure. A serial downloader check is planned and has not run. The accepted level is service recovery through the ROM serial downloader with a single bootloader copy. |
| Evidence | [Review, section 6](secure-boot-and-update-review.md), [bootloader update investigation](boot-bootloader-update-investigation.md), [board test procedure](secure-boot-board-test-procedure.md), section 6. |
| Next step | The board owner, with an approval for that task; the serial downloader check may share a session with a HAB event read. The product team for the product. |
| Stays unproven at L3 | That a product can be recovered: it may have no probe access, no boot-mode pins or a serial downloader disabled by fuse. Whether a corrupt first sector falls through to the serial downloader, where the flashloader comes from and under what licence, and whether it programs an eMMC on the RT1060 are all Not verified. In closed configuration the flashloader must be signed under the device's key (Inference). |

### C7. HAB, open configuration

| Item | Content |
| --- | --- |
| Lowest level | **L0** for the structure of a signed first-stage image: offline signing with throwaway keys, then a structure check. **L3** for what the ROM reports on the NOR layout, as a separately approved task. **L5** for the eMMC layout, because the CSF placement for an SD or eMMC image is not established. |
| Current state | The structure checker is on `main` and **Verified by command** on synthetic images only ([HAB status](boot-hab-status.md)); it has never run on an image from a vendor tool. The signing step, any key, any tool run and any board result do not exist. The [HAB open-configuration plan](plans/hab-open-configuration-plan.md) is Proposed. No HAB signing test is on `main`. |
| Evidence | [HAB status](boot-hab-status.md), [HAB open-configuration plan](plans/hab-open-configuration-plan.md). |
| Next step | An explicit approval for throwaway keys and a pinned tool run, then automation. A HAB event read on the EVKB is a separate hardware approval for the board owner. |
| Stays unproven at that level | In open configuration the ROM runs the image even when authentication fails (**Verified by public vendor document**), so a boot proves nothing about a signature, and a signed first stage adds reporting and no root of trust (Inference). Whether SPSDK accepts a Zephyr image that already has an FCB and an IVT is Not verified. |

### C8. HAB, closed configuration

| Item | Content |
| --- | --- |
| Lowest level | **L5**, on a board that may be locked. No lower level proves it, and the EVKB stays open (the [boot and update investigation](boot-update-investigation.md) defers a dedicated board). |
| Current state | **Not verified, not started.** No key and no fuse operation is approved, and no fuse operation on the EVKB is recorded. |
| Evidence | [Plan, section 6](plans/secure-boot-development-plan.md), [HAB status](boot-hab-status.md). |
| Next step | The product team, after decisions on the fuse plan, key custody and the signing ceremony. Crux contributes the structure checks and the documentation. |
| Stays unproven | Everything: the ROM's abort to the serial downloader on a failed authentication, which key slots can be revoked (Not verified), a signed flashloader, hardware anti-rollback, debug lockdown. Fuse writes cannot be undone. |

### C9a. eMMC software: slots, flush and the flash API

| Item | Content |
| --- | --- |
| Lowest level | **L2** for the stack logic and the trailer ordering. **L4** for a real eMMC on a four-bit bus through the Zephyr MMC stack. |
| Current state | **Verified by command, models only:** the eMMC simulator, the trailer replay and the power-cut replays. The cache flush correction is merged and off by default ([`patches/zephyr/mmc-cache-flush.patch`](../patches/zephyr/mmc-cache-flush.patch)). The flash-API driver over the MMC disk, which MCUboot needs to reach eMMC slots, exists only as an unmerged prototype, and its adoption is not decided. L4 does not exist: no adapter, and no adapter is shown to work with the RT1060. |
| Evidence | [Validation target](plans/emmc-validation-target.md), [eMMC investigation](boot-emmc-investigation.md), [trailer replay](evidence/boot-emmc/trailer-replay/README.md). |
| Next step | Automation keeps the simulator work; the driver stays a prototype until its adoption is decided. An adapter has to be chosen and bought first, and the board owner runs L4 cases under their own approval. |
| Stays unproven at L4 | ROM boot from the boot partition, HAB, the eight-bit bus, the product's I/O voltage, reset wiring and supply handling. A failure on an adapter cannot be attributed to the adapter, the socket's signalling or the stack alone (Inference, [validation target](plans/emmc-validation-target.md)). An EVKB NOR pass says nothing about eMMC. |

### C9b. eMMC boot from the boot partition, and provisioning

| Item | Content |
| --- | --- |
| Lowest level | **L5.** Whether the ROM boots an eMMC from the EVKB microSD socket is not known and would need fuse or pin settings that are not approved, so no claim of ROM boot is made below L5. |
| Current state | **Not verified, not started.** No first-stage image for eMMC exists, no boot header for it is built, and no target exists. Whether the image vector table offset `0x400` counts from the start of a boot partition, whether the ROM accepts a Zephyr-laid-out header, and the card state at hand-over are Not verified. The provisioning settings of the [profile record](plans/emmc-provisioning-profile.md) (boot partition enable, boot bus, write protection, reset pin function, partition settings) are all deferred until the product's inputs; several are one-time-programmable. |
| Evidence | [eMMC investigation](boot-emmc-investigation.md), [provisioning profile](plans/emmc-provisioning-profile.md), [porting guide, section 4](boot-porting-rt1062.md). |
| Next step | The product team on the product board, after the board owner supplies the inputs its own board bring-up checklist needs, and once the eMMC flash-API driver is adopted and a first-stage image for eMMC exists. Crux supplies the checkers, the porting guide and the simulator results. |
| Stays unproven | All of it. The profile's order is a proposal: partition settings, then content and reversible fields, then a boot test, then protection and one-time-programmable fields, each write with its own approval. |

### C10. Update transport

| Item | Content |
| --- | --- |
| Lowest level | **L0 or L1** for request handling, authentication and the application-side checks before any NOR write. **L3** for a flash write while the application runs on the target (case T7). **L5** for the product's network and supply. |
| Current state | **Not verified, not started.** No update agent and no bootloader provider exist. The only related code is the image-state contract with its Host test double (see C4); the controller sample links no flash driver and makes no update, confirm or request call. The update agent design is Proposed ([update agent proposal](plans/update-agent-design-proposal.md)); the transports (HTTPS and SFTP) would follow the product composition of the management services (Inference, [ADR-0004](decisions/0004-product-composition-of-management-services.md)). |
| Evidence | [Update agent proposal](plans/update-agent-design-proposal.md), [review, section 4](secure-boot-and-update-review.md). |
| Next step | Automation, once the work package of the proposal is approved. The reference product repository for the transport on the EVKB. The board owner for T7 once the agent exists. |
| Stays unproven at L0 and L1 | A flash write while running from the target, the EVKB's network against the product's, the product's authentication and authorisation policy, and the reboot decision, which belongs to the product's reboot policy. |

## 5. Rules for reading a result

1. **A build is not a boot.** CI that builds, signs and verifies shows the build and the signing tool.
2. **A checker pass is a pass of the checker.** The offline checkers have run on synthetic images only. A first run on a real image is a result about the checker as much as the image.
3. **A simulator or model result is a result about the model.** It supports a design and finds ordering errors. It does not show device behaviour.
4. **An EVKB pass is not an eMMC pass.** The EVKB boots from QSPI NOR. NOR and eMMC differ in the write path, erase unit, trailer alignment, cache and boot ROM path.
5. **An eMMC on an adapter (L4) is not ROM boot.** It shows the stack against a device on a four-bit bus, and nothing about the boot ROM, HAB or the product's wiring.
6. **Open configuration is not closed configuration.** The EVKB is open. A closed-configuration property is shown only on a board that may be locked.
7. **One product board is not every unit.** Units in service may carry other one-time-programmable settings. Record the state of the unit tested.
8. **A review PASS and a green CI are not board evidence and not approval.** They satisfy their own gates ([`AGENTS.md`](../AGENTS.md)).
9. **Declare the level.** Every result states its verification level, its trust level and what was not shown.

## 6. What stays for the product team

The product team's final verification covers what only L5 proves: ROM boot of the first stage from the eMMC boot partition, the eMMC provisioning on the product's wiring, HAB in closed configuration with the product's keys and fuses, hardware anti-rollback, power cuts on the product's supply, the product's recovery path and the update over the product's network. The product team's own bring-up checklist lists what to supply and the order to work in; an earlier example checklist is kept in the [project history](history/secure-boot-product-board-handoff.md).

The earlier text of this page, with its dated status lines, tracking references, open points and drafting method, is in [history/secure-boot-verification-ladder-record.md](history/secure-boot-verification-ladder-record.md).
