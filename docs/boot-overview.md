# Boot overview: secure boot and update for Crux

> **Status:** Orientation page, current on 15 November 2026. It decides nothing. Decisions are in the pages it points to, each with its status.
> **Verified:** What is merged and built (section 4), by build in CI; the evidence is in the [boot composition](boot-composition.md) page and the [WP1a evidence record](evidence/boot-composition/wp1a-evidence.md).
> **Not verified:** Everything that needs a board. No boot experiment has run on any board: no signed image has been booted, no unsigned, wrong-key or modified image has been shown to be refused by the boot ROM or MCUboot, and no confirm, revert or update has run.
> **Read this first / then:** this page, then the [secure boot and update review](secure-boot-and-update-review.md) for what exists and what is open, the [boot composition](boot-composition.md) page for the current recipe, the [secure boot development plan](plans/secure-boot-development-plan.md) for phases and open decisions, and the [board test procedure](secure-boot-board-test-procedure.md) before any bench work. To take the composition to another i.MX RT1062 board, read [boot-porting-rt1062.md](boot-porting-rt1062.md).

## 1. What this means for Crux

A product built on Crux should start only an image whose signature a bootloader has checked, should be able to take a new signed image, and should come back from a failed update. Crux uses the open-source bootloader MCUboot for this, built together with the application by Zephyr's sysbuild.

- **Secure boot** here means a bootloader that checks the signature of the application image before it runs it.
- **Update** means replacing the application image in the field with a new signed one and being able to revert it if it is not confirmed.
- **Recovery** means a way back when the bootloader or the image is damaged.
- **Keys** are the product's business. This repository holds no signing key. Builds in CI sign with MCUboot's published public test key, only to prove the build works. Images signed with it must never be programmed to a board.

The first board is the NXP RT1060-EVK Rev B with 8 MiB of QSPI NOR flash. The RT1170-EVK was planned as a later, build-only target; the project owner set it aside for now on 15 November 2026, so the RT1060 path comes first. eMMC as the image medium is an investigation, not a feature.

## 2. The stages

The [plan](plans/secure-boot-development-plan.md) has six phases. Two Crux milestones carry them: M8 "Boot platform foundation and verified boot" ([#296](https://github.com/wonny-labs/crux-pilot/issues/296)) and M9 "Secure firmware update and recovery" ([#297](https://github.com/wonny-labs/crux-pilot/issues/297)). eMMC work cross-references M14 "Transactional storage on eMMC".

| Phase | What | Where it stands on 15 November 2026 |
| --- | --- | --- |
| 0 | Investigations of boot and update, eMMC, and bootloader update | Done, as desk results and build-only trial builds |
| 1 | M8 on the RT1060-EVK Rev B: MCUboot in the manifest, composition recipe, board files, a build check, then board evidence | The merged parts of WP1a are listed below. Board evidence is not started. A design note on recovery options is a Draft (#459, not merged). RT1170 build-only evidence is set aside: its design note (#445) and starting files (#460, Draft) are not merged |
| 2 | M9 update path: image-state contract, update agent, version policy, boot-result record | Not started. A host prototype of the image state exists as a Draft (#462, not for merge) |
| 3 | eMMC media path | The MCUboot trailer replay on the eMMC simulator is merged. A flash-API driver exists only as a Draft prototype that is not merged. Nothing runs on eMMC hardware |
| 4 | HAB signing structure in the open (unlocked) configuration | Not started: no signing step, key, tool run or board result exists. A software-only structure checker on synthetic images is the only code; see the [HAB status page](boot-hab-status.md) and the [HAB open-configuration plan](plans/hab-open-configuration-plan.md) (Proposed) |
| 5 | Closed configuration and production: fuses, key custody, lockdown | Not started. Needs owner decisions first |

**WP1a** is the first work package of M8 (tasks 0 to 7 of #296). Merged so far: the re-baseline, MCUboot in the manifest, the layout of the composition files and the baseline of the M7 reference configurations (the checks that existing controller builds do not change), recorded in [the WP1a evidence record](evidence/boot-composition/wp1a-evidence.md), and then the four board files and the CI build check, described in the boot composition page. Rejection of an oversized or misaligned image by `imgtool` and MCUboot, and reproducibility of the build, are Not verified; the inspector's `fit` decision on synthetic images is Verified by command ([boot image inspection](boot-image-inspection.md)). **No WP1b is defined in this repository**, and the later tasks of #296 are not yet split into numbered work packages.

## 3. Which page answers which question

| Question | Page |
| --- | --- |
| I review secure boot and update for a product: what exists, what is verified, what is open? | [Secure boot and update review](secure-boot-and-update-review.md) |
| I run the bench tests on a board: how, with which expected results? | [Secure boot board test procedure](secure-boot-board-test-procedure.md) (not yet run) |
| How do I build an image with MCUboot for the RT1060-EVK Rev B, and what does CI check? | [Boot composition](boot-composition.md) |
| I take the composition to another i.MX RT1062 board (QSPI NOR or eMMC): what carries over, and what do I check or supply? | [Boot composition on an RT1062 product board](boot-porting-rt1062.md) |
| Do two builds of the composition reproduce, and how would that be checked? | [Boot composition reproducibility](boot-reproducibility.md) (prepared, not run) |
| Why RAM load with revert, which update modes exist, what did the trial builds show? | [Boot and update investigation](boot-update-investigation.md) |
| Can the bootloader itself be updated or recovered in the field? | [Updating or recovering a deployed bootloader](boot-bootloader-update-investigation.md) |
| What would booting and updating from eMMC need? | [eMMC boot and update feasibility](boot-emmc-investigation.md), with the M14 design in [emmc-reliance-design.md](plans/emmc-reliance-design.md) |
| What is planned, in which order, and what must the owner decide? | [Secure boot development plan](plans/secure-boot-development-plan.md) |
| How does a product add MCUboot to its manifest? | [Product composition guide](product-composition.md) |
| What may Crux depend on for cryptography? | [ADR-0006](decisions/0006-cryptographic-dependency-policy.md) |

## 4. What is merged and what is not (15 November 2026)

Merged:

- MCUboot as an optional west group, `crux-boot`, in `west.yml`. It is fetched only when a workspace turns the group on.
- The [boot composition](boot-composition.md) page, the four board files for the RT1060-EVK Rev B in `zephyr/boot/boards/mimxrt1060_evk_mimxrt1062_qspi_B/`, and a CI step that builds MCUboot and the controller sample with sysbuild, signs the application with the public test key and checks the signature with `imgtool verify`. It also checks that a key of another type and an image changed after signing are refused by the signing tool.
- The three investigation records and the plan, as records. They adopt only the owner decisions they list.
- The trailer replay of MCUboot sequences on the eMMC simulator.
- Software-only tools for the RT1060 path: the [boot image inspector](boot-image-inspection.md) with its `fit` decision for oversized or misaligned images (#466, #472), a check of the CI-built images against it that the composition script calls (approved by the owner on 2026-11-16, #489) and that has never run on a real build (#467), and the [porting guide](boot-porting-rt1062.md) for another i.MX RT1062 board (#468).

Not merged or not started:

- The eMMC flash-API driver prototype (Draft, not for merge without an owner decision).
- Any run on a board: boot, refusal of bad images, confirm, revert, update, power loss.
- RT1170-EVK build-only evidence (set aside for now), the recovery path (a Draft note only), HAB signing, closed configuration.
- A choice of MCUboot's cryptographic backend. It is an owner decision under ADR-0006.

## 5. Rules that apply to this work

- The documents label evidence: **Verified by build**, **Verified by command**, **Verified on pinned source**, **Verified by public vendor document**, **Verified in repository**, **Inference**, **Not verified**. A build proves that something configures, builds and signs. It never proves that a board boots.
- Hardware work (programming, reset, fuses) needs explicit approval for that task. None is part of the merged work.
- Documents under a non-disclosure agreement never enter this repository (see the plan, section 10). Statements about the boot ROM, HAB and fuses come from public sources and carry their label. Many are Inference or Not verified.
- Public interface or architecture choices (the image-state contract, the bootloader update policy, the crypto backend) go through the owner as decisions, not through a pull request alone.
