# Secure boot: product board hand-off checklist

> **Status:** A checklist for the team that brings up secure boot and update on a product board with an i.MX RT1062. Current on 16 November 2026. It is guidance. It decides nothing and **approves no hardware operation, key, fuse or one-time-programmable write, purchase or merge**. It is a plan for the work, not a record that any of it was done.
> **Verified:** That the inputs, steps and rules below follow the repository's own records (the [eMMC validation target](plans/emmc-validation-target.md), the [eMMC provisioning profile](plans/emmc-provisioning-profile.md), the [porting guide](boot-porting-rt1062.md), the [board test procedure](secure-boot-board-test-procedure.md) and [`AGENTS.md`](../AGENTS.md)), read on 16 November 2026. Nothing in this page was run.
> **Not verified:** Every board step. **No boot experiment has run on any board, and no product board or eMMC has been used with Crux.** The order of steps for an eMMC product is a proposal, with parts that no record has tested.
> **Read this first / then:** the [verification ladder](secure-boot-verification-ladder.md), which says what each level can prove and what stays unproven, then the [boot overview](boot-overview.md) and the [porting guide](boot-porting-rt1062.md), then this page.

Labels are those of the boot records: **Verified by build**, **Verified by command**, **Verified on pinned source**, **Verified by public vendor document**, **Verified in repository**, **Inference**, **Not verified**. "INPUT" means the board owner supplies the value.

## 1. Purpose and boundary

Crux and its reference product repository build the base code, the tests, the infrastructure and the documentation. The product team does the final verification on real product boards, including the eMMC. This page tells that team **what to supply, what Crux provides, in what order to work, which approvals and stop conditions apply, how to return results, and what must never be committed**.

Boundaries that apply to every step:

- This repository is public. **Product names, board support, part numbers, schematics and device parameter values stay in the product's private repository** ([plan, section 10](plans/secure-boot-development-plan.md); the plan records no device parameter value, section 1). In every shared text, say "product board".
- Documents under a non-disclosure agreement never enter this repository, and no page here is derived from one. Where a fact needs such a document, say "Not verified" instead of guessing ([HAB status](boot-hab-status.md)).
- Physical programming, reset, EXT_CSD writes, fuse writes and every other hardware operation need **explicit approval for the current task**, a verified target, probe and setup, and a safe execution setup. Past approvals do not carry over ([`AGENTS.md`](../AGENTS.md)). This page is not an approval.
- A review PASS or a green CI never replaces a board approval.

## 2. Who does what

| Role | Does | Does not |
| --- | --- | --- |
| **Board owner** | Owns the board under test, supplies the inputs of section 3, approves each hardware step in a written task record, holds custody of the board, and stops work when a stop condition of section 6 holds. For an EVKB bench task this is the Crux bench owner; for a product board it is the product's board owner. | Delegate a hardware approval to a document, a tool flag or a review verdict. |
| **Product team** | Writes the product's board files, first-stage image, provisioning plan and key plan in the private repository, runs the product-board steps, and returns results as section 7 says. | Put keys, product names or device parameter values into the public repository. |
| **Crux maintainers and sessions** | Provide the composition, checkers, tools and procedures of section 4, review the product's procedure and results, and own the public records. | Hold the product's board, keys or eMMC data, or approve a hardware step. |
| **crux-controller** (separate reference repository) | Holds an integration consumer on the EVKB, which is a second consumer of the image-state contract, and the update transports and reboot policy (**Inference**, see the [ladder, section 3](secure-boot-verification-ladder.md)). A product team may read it as an example of composing Crux. | Stand in for a product's own composition. |

## 3. Inputs the board owner must supply

Take the full list and the reasons from the [validation target record](plans/emmc-validation-target.md) (open items 1 to 10), the [provisioning profile record](plans/emmc-provisioning-profile.md) (the table of product inputs) and the [porting guide, sections 3 and 4](boot-porting-rt1062.md). Nothing is requested by the plan now (decision D8); this list is what the product team collects before the slot layout and the provisioning profile are fixed. **Record the values in the product's private repository.** The public records name the inputs and never hold the values.

- [ ] **I/O voltage and core supply of the eMMC**, and whether both supplies can be switched under test control (needed for the signalling mode and for any power cut).
- [ ] **Bus width as wired** (1, 4 or 8 bit) and **which uSDHC** carries it.
- [ ] **Reset pin connection:** is the eMMC reset input connected, and to what (a processor pin, a reset supervisor or nothing). The reset pin function is one-time-programmable.
- [ ] **EXT_CSD state of deployed units**, if any are in service: boot partition enable, boot bus conditions, boot and user write-protection state, reset pin function, partition settings completed, enhanced areas. Reading it is a hardware task with its own approval. Whether any unit is in service is not known to this repository.
- [ ] **Capacity, boot partition size, whether partitioning is supported and the maximum enhanced size.**
- [ ] **Erase and write-protect group sizes.**
- [ ] **Cache behaviour, reliable-write support and timeouts** from the device datasheet.
- [ ] **The ROM's boot settings for the product board:** the fuses or pin overrides that select the port, the bus width and fast boot.
- [ ] **Flash part (NOR products):** size, JEDEC ID, erase and write units, and its flash configuration block; **SDRAM part** and its device configuration data. An eMMC-only product has no NOR.
- [ ] **Memory map:** SDRAM size and window, OCRAM use, FlexRAM split.
- [ ] **Probe and console details:** the debug connector, the probe and its device name, the flash algorithm that matches the product's flash, the console UART and its speed, and whether the console port resets the board when opened.
- [ ] **Boot mode access:** whether boot-mode pins are reachable, whether the serial downloader can be selected, and whether the product's fuse plan removes it.
- [ ] **Power fixture:** how the board is powered, how power can be cut under control, hold-up time and brown-out behaviour.
- [ ] **Manufacturing flow:** programming in a socket, by the supplier or in circuit, and the supplier's statement on data retention through reflow.
- [ ] **Whether the bootloader must be field-updatable** (plan decision D7).
- [ ] **Key plan, by reference only:** algorithm, custody and who signs (plan decision D6). The keys themselves never leave the product's key custody.
- [ ] **Board custody:** who holds the board, who approves each task, and how a hand-over is recorded.
- [ ] **Sacrificial units:** at least one unit for any one-time-programmable write, before a unit that is to be kept.

## 4. What Crux provides

| Item | Where | State |
| --- | --- | --- |
| Composition recipe and the EVKB composition files (the model for a product's four files) | [boot composition](boot-composition.md), `zephyr/boot/boards/mimxrt1060_evk_mimxrt1062_qspi_B/` | **Verified by build** (CI, EVKB only). A product writes its own four files in its own repository. |
| Porting guide: what carries over, what to re-derive per board, the eMMC variant, a twelve-step checklist | [boot-porting-rt1062.md](boot-porting-rt1062.md) | Guidance. No product board was built. The check script is wired to the EVKB; a product board needs a second or a parameterised script. |
| Bench procedure for the EVKB, as the model of a product's procedure | [secure boot board test procedure](secure-boot-board-test-procedure.md) | Written and **not yet run**. Every expected result is a prediction. |
| Bench runbook and kit | Pull request #492 (open, not merged) | Not on `main`. Not relied on here. |
| Device-control tool: one lock per board, gated reset and flash, raw console, an evidence directory per run | [`tools/device_control/README.md`](../tools/device_control/README.md), [board image profiles](board-image-profiles.md) | Internal, never run against hardware. A new board needs a profile and a target identity, and none exists for a product board. Its flags record a reference and are not authority. |
| Image checkers: MCUboot image inspector with the `fit` decision, the HAB structure checker, the boot configuration check, the two-build reproducibility comparison | [boot image inspection](boot-image-inspection.md), [HAB status](boot-hab-status.md), [`scripts/check-boot-config.py`](../scripts/check-boot-config.py), [boot reproducibility](boot-reproducibility.md) | **Verified by command** on synthetic inputs only; never run on a real image of a product. Not interfaces. |
| Evidence format | [Board test procedure, sections 8 and 9](secure-boot-board-test-procedure.md), section 7 below | Described, not used yet. |
| eMMC records: validation target, provisioning profile (settings S1 to S8 with their reversibility), the feasibility study | [validation target](plans/emmc-validation-target.md), [provisioning profile](plans/emmc-provisioning-profile.md), [eMMC investigation](boot-emmc-investigation.md) | Draft decision records and a desk study. No eMMC support claim. |
| eMMC simulator, trailer replay and power-cut replays | [trailer replay](evidence/boot-emmc/trailer-replay/README.md), [replay record](evidence/emmc-reliance/replay-reliance/README.md) | **Verified by command, models only.** |
| The flash write path finding and its scope question | [flash XIP evidence](flash-xip-evidence.md); #165 (decision before any bootloader NOR write), with a proposal and a candidate in #491 and #493 (open) | Open. |
| HAB status and the open-configuration plan | [HAB status](boot-hab-status.md), [HAB open-configuration plan](plans/hab-open-configuration-plan.md) | No HAB result of any kind exists. |
| The update agent and image-state designs | [update agent proposal](plans/update-agent-design-proposal.md), [image-state contract proposal](plans/image-state-contract-proposal.md) | Proposals. No update code exists. |

What Crux does **not** provide: board support for a product, eMMC part data, signing keys, the NXP flashloader, a HAB signing run or an eMMC first-stage image. A first-stage image for eMMC (plan issue B) is not built.

## 5. The order of steps

Steps 1 to 4 need no hardware. Do not start a step before the one above it has its record. Each step ends with a record in the product's repository, and a result is returned as section 7 says.

1. **Agree the scope and the custody.**
   - [ ] Name the variant (NOR or eMMC), the board owner, the approver, the board's custody and where results are returned.
   - [ ] Read the [ladder](secure-boot-verification-ladder.md) so that every result is declared at its level (L3 to L5) and its trust level.
2. **Collect the inputs of section 3** in the private repository. Open items stay open and are named in the record.
3. **Prepare the build, board-free.**
   - [ ] Write the board devicetree, the flash configuration block and the device configuration data, the four composition files and the partition table from a measured signed image ([porting guide, section 6, steps 1 to 5](boot-porting-rt1062.md)).
   - [ ] Build and sign with the **public test key only**, and record what was built, never that it boots. An image signed with that key is never programmed.
   - [ ] Run the image checkers on the build output. A pass is a pass of the checker ([ladder, section 5](secure-boot-verification-ladder.md)).
4. **Write the product's bench procedure** by adapting the [EVKB procedure](secure-boot-board-test-procedure.md): the probe and flash algorithm, the backup range and the no-touch ranges from the product's flash size and contents, the boot-mode access, the power fixture and the stop conditions. For an eMMC product no procedure exists: write one and have the Crux maintainers review it **before** any hardware step. An independent reviewer, not its author, checks the procedure.
5. **Record the approvals** (section 6) in a task record for each hardware step, with the board custody and the stop rule.
6. **Preflight, read only.**
   - [ ] Identify the board and the probe, check the target voltage, and connect (retry once at a slower speed and record both).
   - [ ] Back up the boot medium read twice and compare the copies. Exclude any range of unknown content or unreadable range.
   - [ ] eMMC: read EXT_CSD of a unit from an independent host, read only, on a sacrificial unit first. Compare it with the inputs of section 3 and stop on a difference you cannot explain.
7. **Prove a recovery path before any boot experiment.** This is a rule of the plan (milestone M8). Restore a known good image from the backup, and check the serial downloader route if the product keeps it. The EVKB routes are written and not run (#309), so a product's route is **Not verified** until it is run.
8. **Run the boot cases in order** (NOR products: the cases of the EVKB procedure, adapted; T1 to T5, then T6 power cuts with the fixture).
   - [ ] Bootloader NOR writes need the decision on #165 recorded first.
   - [ ] eMMC products: software cases through the MMC stack first (the eMMC variant has no EVKB-like procedure yet), then the first stage from the boot partition. The boot partition steps need the eMMC flash-API driver decision (D2) and a first-stage image that does not exist yet.
9. **Provisioning, last and in this order,** each write with its own approval, sacrificial units first ([provisioning profile, dependencies and order](plans/emmc-provisioning-profile.md)): partition settings and a power cycle; the boot partition content and the reversible boot settings; a boot test; then protection, reset pin function and other one-time-programmable fields. The profile recommends none of the one-time-programmable writes now.
10. **HAB.** Open configuration (a signed first stage and an event read) only after the owner's separate approvals for keys, tool runs and the hardware task. Closed configuration, fuses and key custody are the product's own decisions (D1, D5, D6) and need a board that may be locked. Never on an EVKB.
11. **Return the results** (section 7) and declare the level and trust level reached.

## 6. Approvals and stop conditions

**Approvals** (each recorded in the task record before the step, each for the current task only):

| Step | Approval needed |
| --- | --- |
| Any hardware use of the board | The board owner's, in writing, naming the task, the board, the probe and the flash ranges |
| Programming, reset, erase | Explicit approval for the current task, with the verified target and the safe setup |
| Bootloader NOR writes | The decision on #165, or an approval to run with it open |
| Reading EXT_CSD of a deployed unit | A separate hardware task approval |
| Writing any EXT_CSD field, boot partition content or protection | A separate approval per write; one-time-programmable fields need their own and are irreversible |
| Power cuts | A checked power fixture and an approval of its own |
| Generating keys, installing and running a signing tool, a HAB event read | A separate owner approval each (none is given by this page or by decision D6) |
| Fuse writes, closed configuration | Never approved by any record; a product decision with its own approval on a board that may be locked |

**Stop** and ask the board owner and the Crux maintainers when any of the following holds. Record the state first, and power down only if a step says so.

- [ ] A step would write a fuse, a one-time-programmable field or a protection setting that is not approved.
- [ ] A read-back differs from its backup or image, or the probe or board identity differs from the record.
- [ ] A step would touch a range of unknown content, an unreadable range or a range outside the approved ranges.
- [ ] The measured voltage or supply does not match the inputs, or the supply is unstable.
- [ ] EXT_CSD of a unit differs from the inputs in a way you cannot explain, for example a protection or reset setting already made permanent.
- [ ] A unit that is to be kept would receive its first write of a new kind.
- [ ] The console shows a fault, a restart loop or nothing after a restore, and the recovery order has been used up.
- [ ] A command runs longer than its stated limit, or another tool holds the probe or the port.
- [ ] A checker and a tool disagree about an image, or an input is missing.
- [ ] An approval is missing, out of date or for a different task.
- [ ] A key, a vendor document under a non-disclosure agreement or a product name is about to leave its private place.

## 7. How results come back as evidence

Return a result for each case, kept together in one directory per run, and **a table of results**. The folder layout of the [board test procedure, section 8](secure-boot-board-test-procedure.md) applies to a product board:

| Item | Content |
| --- | --- |
| Console | Raw bytes from the tool or the terminal, never retyped |
| Tool record | The whole device-control run directory, if the tool is used |
| Probe and host logs | The full output of each command, with the command file used |
| Artefacts | SHA-256 of every file programmed and of the build outputs, the inspector's output for each image, the signing arguments |
| Identity | Board identity and photographs of switches by eye, probe serial, tool versions, the console port |
| Session | UTC date, who ran it, host, the Crux and product revisions, the Zephyr and MCUboot revisions and the approval references |
| Observations | What differed from the prediction, in words, next to the raw files |

Result record, one per case (copy and fill in):

```text
Case:               <name from the product procedure>
Level / trust:      <L3 | L4 | L5> / <T0 | T1 | T2 | T3>
Revisions:          crux <sha>, product <sha>, zephyr <sha>, mcuboot <sha>
Approval reference: <task record>
Expected:           <prediction, copied before the run>
Observed:           <what happened>
Pass / fail:        <result>
Not shown:          <what this result does not show>
Evidence:           <directory, file hashes>
```

**Rules for the return.**

- Say "product board". Give the level and trust level and what was not shown. A pass on one unit is not a pass for every unit ([ladder, section 5](secure-boot-verification-ladder.md)).
- Give the evidence directory to the Crux maintainers. **Do not commit results under `docs/evidence/`, and do not edit `docs/baseline.md`:** they are protected paths and need an explicit human approval and a material independent review ([`AGENTS.md`](../AGENTS.md)). The maintainers decide what becomes a public record, and in what words.
- Scrub before sharing: product and customer names, part numbers, serial numbers, device parameter values, absolute personal paths and anything of section 8. If a result cannot be stated without them, keep it private and share only its outcome and level.
- Record failures, skipped steps and blocked cases as such. Do not report an unexecuted case as passing, and do not interpret a build as a boot.

## 8. What must never be committed

To this public repository, to a pull request description, an issue or a comment:

- [ ] **Any key or key material:** signing keys, development keys, HAB keys, SRK tables and their sources, certificates with private parts, RPMB keys, tokens and credentials. Keys stay in the product's key custody ([boot overview](boot-overview.md): this repository holds no signing key).
- [ ] **Any image signed with MCUboot's public test key that is meant for a board.** Such an image is never programmed ([boot composition](boot-composition.md)).
- [ ] **Anything from a document under a non-disclosure agreement,** including quotes, tables, register or fuse details and screenshots, and notes derived from one. Write "Not verified" instead.
- [ ] **Product, customer, board and project names,** and eMMC or NOR part numbers beyond those the repository already uses for the EVKB.
- [ ] **Device parameter values and unit data:** capacity, group sizes, timeouts, EXT_CSD dumps, serial numbers and the state of deployed units.
- [ ] **Product schematics, board files and the product's first-stage image.**
- [ ] **Vendor binaries whose licence is not read,** including the flashloader ([plan, section 7](plans/secure-boot-development-plan.md)).
- [ ] **Personal paths, host names and account details,** and a user home or Docker socket mounted into a build ([`AGENTS.md`](../AGENTS.md)).
- [ ] **Results written into protected paths** (`docs/evidence/`, `docs/baseline.md`, `tools/`, `scripts/`, `.github/`) without the approval of [`AGENTS.md`](../AGENTS.md).

When in doubt, keep it in the private repository and ask.

## 9. Who to ask

Open questions about the procedures, checkers and records go to the Crux maintainers through the repository's issues (the [secure boot milestone M8, #296](https://github.com/wonny-labs/crux-pilot/issues/296), and its sibling issues for eMMC and HAB). Approvals are the board owner's and the project owner's; a question about a hardware approval is not answered by this page. Anything that would need a private detail goes to the project owner outside this repository.

## 10. Not verified

- That any step of this checklist works on a product board: nothing was run, and no product board has been used with Crux.
- That the EVKB procedure's steps carry over to a product's probe, flash and supply, and that an eMMC product's procedure, which does not exist, can follow the same shape.
- That the boot ROM boots an eMMC with a Zephyr-laid-out header, where the first stage sits in a boot partition, and that a flashloader programs an eMMC on the RT1060.
- Any claim about a one-time-programmable field beyond what the public tool sources say; the JEDEC eMMC standard was not read.
- That the pull requests named by number (#491 and #493 for issue #165, and #492) have the state given here: it is the state known on 16 November 2026, not re-read.

## Method

Written from the pages linked above, read on 16 November 2026. No build, tool or hardware was run. No vendor, product or part name was used, and no document under a non-disclosure agreement was used. This page does not claim that any product board boots, that any eMMC works with the RT1060, or that any approval exists.
