# Secure boot development plan

| Field | Value |
| --- | --- |
| Status | **Proposed.** A plan for the owner. It adopts nothing beyond the decisions it cites. Statements the cited records do not support carry the label Inference or Not verified. State on 15 November 2026: work package WP1a of Phase 1 is merged (#339, #340, #437) and is build-only; no boot experiment has been run on a board. |
| Date | 14 November 2026 |
| Milestones | M8 "Boot platform foundation and verified boot" ([#296](https://github.com/wonny-labs/crux-pilot/issues/296)) and M9 "Secure firmware update and recovery" ([#297](https://github.com/wonny-labs/crux-pilot/issues/297)); the eMMC medium work cross-references M14 "Transactional storage on eMMC". No new milestone is proposed (section 5). |
| Records it builds on | [Boot and update investigation](../boot-update-investigation.md) (#141), [eMMC boot and update feasibility](../boot-emmc-investigation.md) (#298), [Updating or recovering a deployed bootloader](../boot-bootloader-update-investigation.md) (#299), the [boot composition page](../boot-composition.md) (WP1a, merged in [#340](https://github.com/wonny-labs/crux-pilot/pull/340) and [#437](https://github.com/wonny-labs/crux-pilot/pull/437)), [ADR-0002](../decisions/0002-platform-direction-zephyr-execution-crux-services.md) to [ADR-0004](../decisions/0004-product-composition-of-management-services.md) and [ADR-0006](../decisions/0006-cryptographic-dependency-policy.md) |

Labels follow the boot records: Verified on pinned source, Verified by build, Verified by public vendor
document, Inference, Not verified. A statement without a label is a proposal of this plan or a
citation of a decision record.

## 1. Purpose and scope

Crux needs a boot chain that runs only firmware the product owner signed, for two kinds of
products on NXP i.MX RT1060-class MCUs:

- **NOR products** boot from a FlexSPI serial NOR, like the RT1060-EVKB evaluation board.
- **eMMC products** boot from an eMMC and execute the application from SDRAM, the case #298
  investigates. No eMMC-bearing RT1060 target for M8 and M9 validation exists yet (owner
  confirmation of 7 November 2026, as recorded in #310). The device parameters that decide the
  slot layout and the provisioning profile (capacity, boot partition size, erase and write-protect
  group sizes, cache behaviour, timeouts) are inputs from the product (D8). They are Not verified
  here and are not recorded in this repository.

The plan covers the bootloader, image signing, the update path, the eMMC media path, the hardware
root of trust and the decisions that stay with the product owner. It keeps each phase independently
verifiable and does not claim any result that has not been shown on hardware.

Out of scope: fuse programming on any board, production keys, a field-updatable bootloader (service
recovery is accepted for M8 and M9, #299), and product-specific runtime integration (`AGENTS.md`).

## 2. What is already decided

| Decision | Source |
| --- | --- |
| RAM load into SDRAM is the M8 reference execution model; the reference composition changes at the start of M8, after M7 target validation | #141 owner decision 3 (7 November 2026) |
| The constraint is accepted for M8 that no stock mode avoids NOR writes during XIP with test, confirm and recovery; bootloader customisation (variant b) is a separate scope that is not started | #141 owner decision 1 (7 November 2026) |
| The application rejects an older image (major, minor, revision) before any NOR write | #141 owner decision 4 (7 November 2026) |
| Network-facing update requires authenticated and authorised requests and an application-side check before any NOR write | #141 owner decision 5 (7 November 2026) |
| M8 test images are signed with `--pad`; the application-driven path is designed in M9, where application code that marks the inactive slot is preferred | #141 owner decision 13 (2 November 2026) |
| The MCUboot FlexSPI write-path closure failure is a blocker for any bootloader NOR write on hardware; its remediation is #165 | #141 owner decision 16 (2 November 2026), #165 |
| BEE stays out of M8 | #141 owner decision 10 (7 November 2026) |
| A later HAB event read in open configuration, without fuse writes, is allowed only as a separately approved hardware task, which may share a session with the ROM serial downloader check (#309) | #141 owner decision 8 (7 November 2026) |
| Service recovery through the boot ROM serial downloader for M8 and M9: a single bootloader copy that is not field-updatable. M9 declares the bootloader's update and recovery level and carries the bootloader version in the boot-result record | #297 and #299, owner decision of 7 November 2026 |
| Composition files live in the Crux module, in the folder `zephyr/boot/boards/<board>/` | Owner decision of 9 November 2026, option B, as recorded in the description of PR #340. The RT1060-EVK Rev B files are in place since PR #437 |
| The microSD staging path (variant a) is deferred | #141 owner decision 6 (7 November 2026) |
| `storage` stays declared with no owner and no writer in M8; slots stay 3 MiB until a whole-slot erase has been timed; boundaries stay 64 KiB aligned | #141 owner decision 17 (2 November 2026) |
| "No eMMC backend work starts. It waits for a target and a scope decision." "eMMC adds no M8 or M9 exit criterion." The software-only replay of MCUboot trailer sequences is #310, low priority and without a milestone. No eMMC-bearing RT1060 or RT1062 target exists yet | Owner decisions of 7 November 2026, as recorded in the closing comment of #298 and in #310 |
| **Revision of the first of those, 14 November 2026.** The owner chose a read/write prototype of the eMMC flash-API driver in the Crux module, tested on the `native_sim` eMMC simulator, as a Draft PR that is not merged, with adoption left to a later owner decision. The owner also chose merging #310 after the reviewer PASS and green CI. The 7 November decision that eMMC adds no M8 or M9 exit criterion is not revised. The validation target is still missing | Project owner's decision of 14 November 2026 about 21:55 UTC. Asked how far to take a prototype of the eMMC MCUboot backend (a Zephyr driver that exposes eMMC through the flash API), the owner chose a read/write Draft PR, as recommended; for #310, the owner chose merging after PASS and green CI, as recommended. No repository record of it exists yet |
| Service recovery for M8 and M9 is decided again after #165, #298 and the M8 hardware results | #299 closing summary |

Recommended in #141 but not a decision row, so not adopted by this plan: stock MCUboot at the Zephyr
pin built with sysbuild and ECDSA P-256 with tinycrypt, and the update-mode ranking (rank 1 RAM load
with revert), which A3 does not cover (#141 "Recommendations and decisions"). WP1a builds rank 1
(PR #340) under the owner's WP1a approvals of 7 and 8 November 2026 as quoted in the bodies of PRs
#339 and #340 (plan, early start, MCUboot fetched outside the repository, the public test key for
build-only signing, and the files of Tasks 1 and 2). Those approvals cover the WP1a work, not the
ranking. The choice of MCUboot's crypto backend is D9.

## 3. Architecture

```
Boot ROM ──HAB──▶ First stage: MCUboot ──ECDSA P-256──▶ Application (SDRAM) ──▶ Update agent
  (closed: enforced;   NOR: FlexSPI boot header          slots: NOR partitions or         (M9: size, header, version,
   open: logged only)  eMMC: boot area, IVT offset 0x400  raw eMMC user-area slots         signature checked before
                                                          through the flash map            the image is written)
```

- **One bootloader configuration for both media.** MCUboot reads and writes slots only through
  Zephyr's flash map (#298 section 2, Verified on pinned source). NOR products use the FlexSPI flash
  device. eMMC products would use a flash-API driver over the MMC disk, selected in devicetree. No
  such driver exists in the pinned tree, and whether the MCUboot port works with slots on eMMC and the
  bootloader elsewhere is Not verified (#298 section 2). The aim is that the application and the
  update agent see the same image-state behaviour on both media.
- **Raw slots, not files, on eMMC.** Slots would sit in the eMMC user area outside any file-system
  volume (#298 section 2 says this is possible in principle). A file-system store does not test
  MCUboot's trailer ordering (#298 section 5), and a bootloader that reads a file system would need a
  file system inside the bootloader.
- **The first stage on eMMC is a separate image.** The ROM reads the boot partition named by
  `BOOT_PARTITION_ENABLE` (or the user area) and copies the image to the destination in its boot data;
  the first 4 KB must hold the IVT, DCD and boot data (#298 section 1, Verified by public vendor
  document, third-party copy of the manual). The manual gives the IVT offset `0x400` for SD and eMMC.
  Whether `0x400` counts from the start of a boot partition is Not verified, and so is whether the ROM
  accepts a Zephyr-laid-out header on eMMC. Pinned Zephyr has no SD or eMMC boot-device option.
- **SDRAM start-up is a DCD matter in Zephyr today.** Zephyr does not initialise the SEMC in software,
  and the DCD in the boot header brings SDRAM up (#298 section 4, Verified on pinned source). That the
  ROM runs the DCD before it copies the image is an Inference from the manual's order. A first stage
  linked into on-chip RAM would not depend on that order for its own placement (#298 section 4,
  Inference). It would still need SDRAM before it loads an application into SDRAM, through the DCD or
  through new SEMC initialisation code. Which one works on eMMC boot is Not verified and needs a board.
- **Two signing roots.** The boot ROM authenticates the first stage with HAB keys; the RT1060 manual
  lists RSA 1024, 2048, 3072 and 4096 (#299 row B-61). MCUboot verifies the application with an ECDSA
  P-256 key. The keys would be separate (a proposal of this plan). Keys stay outside the repository and
  only development keys are used before a product decision (#296 boundaries and #141 out of scope:
  no production keys; #141 owner decision 18 for development-key handling). The key size is D6.
- **Trust levels are declared per phase**, never implied. T0 to T3 are labels defined by this plan;
  #296 and #297 require each result to declare the level it reached.

| Level | What holds | Phase |
| --- | --- | --- |
| T0 | MCUboot verifies the application with a development key on every boot. No hardware root of trust: whoever can write the boot medium can replace the bootloader and its key (#141 "Trust level without fuse programming"). | M8 |
| T1 | T0 plus the application-side version policy and test, confirm and revert. | M9 |
| T2 | T1 plus a HAB-signed first stage in open configuration. HAB errors are logged and the image runs (#298 section 1). With blank SRK hash fuses, open configuration can at best show that a CSF was processed and which checks failed, not a passing authentication (Not verified for the RT1060, #141 Stage 3 A13). T2 adds checking and reporting, no root of trust (#299 row B-69, Inference). | Phase 4 |
| T3 | Closed configuration: the ROM aborts to the serial downloader on an authentication error. Debug, serial download and recovery follow the product's fuse plan; optional image confidentiality and hardware anti-rollback. Product decision. | Phase 5 |

## 4. Phases and work items

| Phase | Work | Where | State on 14 November 2026 |
| --- | --- | --- | --- |
| 0 | Investigations #141, #298, #299 | records above | Done (desk and build-only) |
| 1 | M8 on RT1060-EVKB NOR: MCUboot in the manifest (PR #339), composition recipe (PR #340), board composition files and a build check, development-key signing, a non-destructive recovery path proved before any physical boot experiment (#296; the ROM serial downloader check #309 is planned, and the recovery steps it documents can be reused for this path), board evidence that signed images boot and unsigned, wrong-key and modified images do not, RT1170 build-only evidence | M8 #296 | State on 15 November 2026: MCUboot in the manifest (#339), the composition page (#340), and the four RT1060-EVK Rev B board files with a CI check that builds and signs with the public test key, build-only (#437), are merged. RT1170 build-only evidence, the recovery path and all board evidence are not started |
| 2 | M9 update path: image-state contract decision (#297 proposes deciding whether to adopt a public contract at the start of this work), update agent with an explicit state machine, application-side version policy, boot-result record (running slot, confirmed or reverted, bootloader version), declared recovery and power-interruption cases (power fixture and separate approval) | M9 #297 | Not started |
| 3 | eMMC media path. Started now: trailer replay on the eMMC simulator (#310, low priority, no milestone) and a read/write flash-API driver over the MMC disk in the Crux module as a Draft prototype tested on the simulator, not merged (owner choice of 14 November 2026, section 2). Everything beyond these waits for a validation target (D3) and the adoption decision (D2): eMMC first-stage image (separate boot image, IVT offset 0x400, size budget against the boot partition of the chosen part), eMMC provisioning profile as a decision record, validation target decision | proposed issues A to E (section 5), cross-referenced to M14 | #310 open, no driver exists, issues A to E not created |
| 4 | HAB in open configuration: offline HAB signing and structure check of the first stage for NOR and eMMC layouts; HAB event read on the EVKB as a separately approved hardware task | M8 #296 (NOR layout, which already names a HAB-signed bootloader build path); eMMC layout proposed as issue C | Not started |
| 5 | Closed configuration and production: fuse plan, key custody and signing ceremony, SRK rotation and revocation, debug lockdown, serial-download and recovery policy, hardware anti-rollback counter, image confidentiality, manufacturing provisioning | product decision; no Crux milestone yet | Not started |

Order and dependencies:

- Phase 1 and the started part of Phase 3 (#310 and the Draft prototype) can run in parallel. Neither needs the other's hardware. The rest of Phase 3 waits for D3 and D2.
- Phase 2 needs Phase 1's composition (#297 depends on #296 being merged). Any eMMC case would need an adopted driver and a target.
- Phase 4 needs a signing tool decision (section 7) and, for eMMC, Phase 3's first-stage image.
- Phase 5 needs the owner's decisions in section 6 and boards that may be locked (#141 decision 11 defers a dedicated board for closed-configuration work).

## 5. eMMC work items under the existing milestones

M8 and M9 already cover verified boot and update, and M14 covers eMMC as a medium, so this plan
proposes to track the eMMC boot work as issues under M8, with cross-references to M14 and #298,
instead of a new milestone. Whether a separate milestone is wanted is an owner question (D10).
The owner decided on 7 November 2026 that eMMC adds no M8 or M9 exit criterion. Issues under M8
would add tracked work but no exit criterion; M8's exit criteria stay on the RT1060-EVKB. Beyond
#310 and the Draft prototype, the work waits for a target (D3) and the adoption decision (D2). None
of the issues exists yet and none is created without the owner's approval.

Proposed issues (generic wording, no product or part names):

| Issue | Milestone | Purpose |
| --- | --- | --- |
| A | M8 | Flash-API backend over the MMC disk for MCUboot slots: tests on the eMMC simulator, decisions on location, upstreaming, read-only or full, slot layout and size budget (#298 open question 2) |
| B | M8 | First-stage boot image for an eMMC boot partition: RAM-resident MCUboot, boot header with the IVT at offset 0x400, SDRAM bring-up (DCD or software), size budget, build path |
| C | M8 | HAB signing for the eMMC first-stage layout (open configuration only), offline structure check |
| D | M8 | eMMC validation target decision: an eMMC on the EVKB microSD socket for the stack and slots, a product-class board for ROM boot from the boot partition (#298 "Hardware needed") |
| E | M8 | eMMC provisioning profile as a decision record: boot partition enable and boot bus settings, boot-area write protection, reset pin function, and any other one-time-programmable field (#298 sections 3 and 5) |

eMMC update and power-cut cases (slots on eMMC through the driver, power cuts on the user area) do
not join M9's exit criteria unless the owner revises the 7 November 2026 decision. Once a driver is
adopted and a target exists they would be recorded as cases outside the exit criteria.

## 6. Decisions the owner needs to make

| # | Decision | Recommendation | Needed before |
| --- | --- | --- | --- |
| D1 | Will products use the closed security configuration, and when? | Plan for it in production, keep development and the EVKB open. Without it there is no hardware root of trust: the level stops at T1 and T2 only adds reporting (#299 row B-69). | Phase 5; it also decides whether image confidentiality is worth planning |
| D2 | Adopt an eMMC flash-API driver, and where it lives (Crux module, upstream Zephyr, out of tree; #298 open question 2) | The Draft prototype is chosen (section 2). If adopted, Crux module first behind an off-by-default option, upstream later (adoption needs its own scope decision, #298) | Phase 3 code beyond the prototype |
| D3 | eMMC validation hardware | EVKB with an eMMC adapter for software, a product-class board for ROM boot (#298 "Hardware needed"). #298 did not recommend third-party adapters, because none was shown to work with the RT1060; recommending one departs from it, for software-only testing of the stack and the user area with no ROM-boot claim | Issue D |
| D4 | Hardware anti-rollback source, if any (a fuse-backed counter is the option #141 names; other sources are Not verified here) | Application-side check only until D1; then pick by board features | Phase 5 |
| D5 | Recovery versus lockdown in production (serial download, boot-mode pins, service port) | Keep a signed-only recovery path; decide with D1. In closed configuration the serial downloader needs a flashloader signed under the device's SRK (#299 row B-19, Inference) | Phase 5 |
| D6 | HAB key algorithm and size, key custody | RSA-3072 or larger, offline keys in an HSM, up to four SRK slots (#299 row B-61). RSA-2048 is generally rated at 112-bit strength (NIST SP 800-57, not re-read for this plan). Which slots are revocable on the RT1060 is Not verified (#299 row B-62) | Phase 4 |
| D7 | Field-updatable bootloader | Keep service recovery; #299 records that it is decided again after #165, #298 and the M8 hardware results, and it is revisited after any eMMC first-stage results. Two boot partitions could hold two bootloader copies, but the ROM has no fallback between them in the manual text read, so software would switch the selector (Inference, #298 section 3). The two-stage design stays the candidate if the requirement is confirmed (#299) | After Phase 3 |
| D8 | Inputs from the product: eMMC I/O voltage and bus width, reset pin wiring, capacity and boot partition size, erase and write-protect group sizes, cache behaviour and timeouts, and the EXT_CSD state of units already in service, if any (several fields are one-time-programmable, #298 evidence E10) | Collect before the slot layout and provisioning profile are fixed | Issue E |
| D9 | MCUboot's crypto backend (MCUboot's bundled tinycrypt as in #141, or Zephyr's Mbed TLS / PSA Crypto at the pinned revisions) under the crypto dependency policy | Decide under [ADR-0006](../decisions/0006-cryptographic-dependency-policy.md), with a size and boot-time build comparison. ADR-0006 section 5 lists MCUboot (pinned by PR #339) among the dependencies that would need the same review, undecided and each a decision for the owner; including it is this plan's proposal. #141 records that the sysbuild default RSA needs Zephyr's Mbed TLS | Before M8 board evidence |
| D10 | A separate milestone for verified boot from eMMC | No: track under M8 and M9 with cross-references to M14, as tracked work without an M8 or M9 exit criterion, as decided on 7 November 2026 (this plan's recommendation) | Any time |

## 7. Tooling

Rows cite the #141, #298 and #299 evidence (public sources read 1 to 7 November 2026). No tool was installed
or run for this plan. Each row still needs a hands-on check before it is relied on.

| Purpose | Tool | Licence and CI use |
| --- | --- | --- |
| Application image signing (M8, M9) | MCUboot `imgtool` through Zephyr sysbuild | Apache-2.0. Used in the #141 trial builds and in the WP1a builds and CI check (#340, #437) |
| HAB image build, signing and offline structure check | NXP SPSDK `nxpimage hab` (`export`, `parse`), described as the successor of the legacy elftosb and CST tools (#141 Stage 3 B6) | BSD-3-Clause on PyPI (3.12.0 at the time of reading); binary dependency licences not checked. A CI use with a pinned version and throw-away test keys is a proposal. The SPSDK download was approved under #141 A2 and has not been used. Whether SPSDK accepts a Zephyr image that already has an FCB and IVT, and whether it fully replaces CST for RT1060 HAB, are Not verified (#141 Stage 3 B6) |
| ROM serial download and flash/eMMC programming | SPSDK `sdphost` and `blhost` with NXP's flashloader | SPSDK BSD-3-Clause. Where the flashloader binary comes from and under what licence is Not verified (#299 evidence, item 7), so it stays outside the repository and CI until that is read |
| Fuse programming (production only) | An NXP fuse tool; tool names are Not verified in the repository records | Never on development boards without an owner decision |
| eMMC EXT_CSD set-up (boot partition enable, boot bus, write protection) | Linux `mmc-utils` on a host with an MMC-capable controller | Several fields are one-time-programmable (#298 evidence E10). Whether NXP's flashloader programs an eMMC on the RT1060 is Not verified (#298 X6). Whether a USB card reader passes eMMC commands is not shown |
| GUI front end | MCUXpresso Secure Provisioning Tool, a GUI over SPSDK (#141 Stage 3 B10 to B12) | Download needs an NXP account; the licence name was not shown. Not in CI or the repository; not a reproducibility path |
| Legacy signing | NXP Code Signing Tool | Click-through licence LA_OPT36 (#141 Stage 3 B13); superseded by SPSDK. Fallback only if SPSDK output does not boot; it needs its own licence review and approval, which A2 does not cover, and #141 recommended no CST |
| SDRAM DCD data | The board's DCD, as in Zephyr's EVK board files (#298 P10 to P12) | A DCD for another board's SDRAM is Not verified and needs the SDRAM part's data; the source of such data is not recorded |

Pinned Zephyr has no SD or eMMC boot-device option and sets the IVT offset default only for FlexSPI
and SEMC NOR (`0x1000`) and for NAND (`0x400`) boot devices (#298 rows P1, P2, P8), so the eMMC
first-stage header is a Crux composition or post-build step (issue B). A Zephyr-built image carries
no CSF (#298 row P5). No HAB signing step for the MCUboot image was found in the files read (absence
limited to those files; #141 Stage 3 A7 and A9); a post-build `nxpimage hab` step is the candidate (issue C).

A CI step for SPSDK or a build check would touch protected paths (`.github/`, `scripts/`) and follows
`AGENTS.md`: a new check script may be added within a task, and an edit to an existing workflow needs
an explicit human approval.

## 8. Constraints from other decisions

- [ADR-0002](../decisions/0002-platform-direction-zephyr-execution-crux-services.md) and [ADR-0003](../decisions/0003-p9-result-services-keep-narrow-thread-sync.md): product code uses Zephyr-native APIs in product adapters, and Thread, Sync, Queue and Serial are frozen for new product code (ADR-0002 P2, kept by ADR-0003). Whether the update agent and image-state code count as product code is Inference; if they do, they follow this.
- [ADR-0004](../decisions/0004-product-composition-of-management-services.md): the HTTPS and SFTP update routes (#191 in M11, #196 in M12) would follow the management composition (Inference; the ADR concerns how a product composes the management services).
- [ADR-0006](../decisions/0006-cryptographic-dependency-policy.md): the crypto policy covers Crux's own crypto pins. this plan proposes that MCUboot's crypto backend stays consistent with it (D9); the ADR does not require this.
- Boot composition files live in the Crux module (owner decision of 9 November 2026, option B); the folder is `zephyr/boot/boards/<board>/` (PR #340, files in PR #437). Where the boot code's Kconfig and CMake hooks go is Not decided here.
- Reliance Edge stays in its own opt-in group (GPLv2, `crux-reliance`, ADR-0006 and the M14 design); the bootloader is not planned to contain a file system.
- Any bench image follows the [freeze and capture design](../rt1060-bench-freeze-and-capture-design.md). No board or hardware step runs without the owner's task-specific approval (`AGENTS.md`), and the eMMC physical gate of M14 ([procedure](../emmc-reliance-physical-gate.md)) needs its own approval.

## 9. Validation and evidence

- Evidence labels follow the boot records. Board results are recorded separately and are never
  implied by build results.
- Every hardware step needs its own approval, a saved image of the boot medium and a proved recovery
  path first (#296 requires the recovery path before any physical boot experiment; #309 is the planned
  check, and its documented steps can be reused for that path).
- Closed-configuration behaviour is shown only on boards that may be locked. The EVKB stays open.
- Power-interruption tests need a controllable power fixture and their own approval (#297).
- The signed `--pad` images of owner decision 13 and the confirmed image that the v4.4.2 build also
  writes need a follow-up: the #141 rows saying RAM load with revert does not imply a confirmed image
  describe v4.4.0 (the boot composition page says so), and how MCUboot treats the v4.4.2 confirmed
  image is Not verified.

## 10. Confidentiality boundary

This repository is public. Vendor documents under NDA, product names, eMMC part numbers and
product board support stay out of it. Records here cite public sources or say "Not verified".
Private findings are kept outside the repository and inform the owner's decisions only.

## 11. Risks

| Risk | Mitigation |
| --- | --- |
| The eMMC first stage cannot bring SDRAM up without a DCD, or the ROM does not run the DCD before the copy | Decide between a DCD and software SEMC set-up from a board test; do not rely on either before it (Inference, #298 section 4) |
| The eMMC cache may reorder writes, and the pinned stack's disk sync did not flush it (#298 E17; a build-local correction is on `main`) | Flush at every ordering point MCUboot relies on; replay MCUboot's trailer sequences on the simulator (#310), which is a simulator result only. Whether the cache preserves order without a flush is Not verified (#298 E16) |
| Erase and write-protect group sizes and write atomicity of the product's eMMC are unknown | Take them from the product (D8) before fixing the slot layout; assume a single-sector write is not atomic, as the M14 design does (#298 section 5) |
| Bootloader NOR writes during XIP | #165 before any bootloader NOR write on hardware |
| Trust level overstated | Each result declares T0 to T3 and what was not shown |
| Vendor tool licences block CI use | Use only redistributable tools in CI; keep licensed tools on signing hosts. The flashloader and SEC licences are Not verified |
