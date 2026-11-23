# Development history

Status: **historical.** This folder holds the project's development history: how Crux was built and checked while this repository was its development and architecture-validation Pilot. It keeps milestone and run records, evidence tables with their row identifiers, investigation narratives, superseded proposals and the process text that once sat in the main documents. Nothing here is current guidance, with one exception: the [open questions of the first secure boot bench session](secure-boot-first-bench-session-notes.md#open-questions-for-the-first-bench-session) are still open, and the maintained procedure and bench kit link them as such.

For current behaviour start at the [repository README](../../README.md) and the [documentation map](../README.md).

## In this folder

| File | What it is |
| --- | --- |
| [`pilot-readme.md`](pilot-readme.md) | Passages of the repository README of the Pilot period, moved word for word |
| [`pilot-docs-index.md`](pilot-docs-index.md) | The full documentation index of the Pilot period, with its reading orders, current/historical page table and milestone notes |
| [`secure-boot-product-board-handoff.md`](secure-boot-product-board-handoff.md) | An example product-board hand-off checklist for secure boot. A product team keeps its own |
| [`secure-management-board-test-procedure.md`](secure-management-board-test-procedure.md) | An unrun bench procedure for the management services |
| [`secure-boot-first-bench-session-notes.md`](secure-boot-first-bench-session-notes.md) | Open questions and one-board observations removed from the secure boot board test procedure |
| [`adr-0001-record.md`](adr-0001-record.md), [`adr-0002-record.md`](adr-0002-record.md), [`adr-0003-record.md`](adr-0003-record.md), [`adr-0005-record.md`](adr-0005-record.md) | Drafting narration, measurements, open questions and approval records of ADR-0001, 0002, 0003 and 0005 |
| [`component-readiness-record.md`](component-readiness-record.md) | The readiness table with its provenance, run records and progress markers |
| [`secure-boot-verification-ladder-record.md`](secure-boot-verification-ladder-record.md) | The verification ladder with its dated status, open points and method |
| [`rt1060-bench-freeze-and-capture-record.md`](rt1060-bench-freeze-and-capture-record.md) | The bench freeze and capture design as proposed: facts, options not taken, owner questions, order of work |
| [`management-in-a-product-record.md`](management-in-a-product-record.md) | Owner-decision logistics and run notes of the secure management product guide |
| [`restructure-edited-lines.md`](restructure-edited-lines.md) | The original wording of lines edited in place in the main documents during the restructure |
| [`tests-readme-before-trim.md`](tests-readme-before-trim.md) | The test guide before it was cut to an index: per-suite case counts, replay methods, mutation controls, dated notes and one-board procedures |
| [`tests-readmes-before-trim.md`](tests-readmes-before-trim.md) | Passages removed from the READMEs under `tests/`: authorship notes, run narratives, evidence results and design commentary |
| [`patches-web-readmes-before-trim.md`](patches-web-readmes-before-trim.md) | Passages removed from the Zephyr patches README and the web READMEs: the MDIO first-failure diary, the wolfSSL derivation and licence narrative, owner-decision dates, and the flow and evidence tables |
| [`execution-contract-proposal.md`](execution-contract-proposal.md), [`execution-validation.md`](execution-validation.md) | Superseded execution proposal and validation snapshot; current behaviour is in the [Thread and Sync contract](../thread-sync.md) |

## Historical records elsewhere in `docs/`

These records stay at their paths because other pages and checks name them:

| Page or folder | What it is |
| --- | --- |
| [`implementation-status.md`](../implementation-status.md) | Acceptance and execution status of the Time Pilot milestones M0 to M5 |
| [`baseline.md`](../baseline.md) | Frozen build and physical evidence of the original Time Pilot, with exact commands and results |
| [`m2-physical-verification.md`](../m2-physical-verification.md), [`m3-validation.md`](../m3-validation.md), [`m5-pilot-validation-plan.md`](../m5-pilot-validation-plan.md) | Records of early platform milestones M2, M3 and M5 |
| [`platform-m1-readiness.md`](../platform-m1-readiness.md) | Record of early platform milestone M1 |
| [`execution-profile.md`](../execution-profile.md) | Investigation that selected the reference controller's execution model |
| [`physical-verification-plan.md`](../physical-verification-plan.md) | Unexecuted plan, never an approval, for physical checks of GPIO, I2C and SPI |
| [`flash-safety-poc.md`](../flash-safety-poc.md) | Isolated proof of concept for Flash safety |
| [`storage-pilot-software-handoff.md`](../storage-pilot-software-handoff.md) | Storage handoff of the Pilot, superseded as the storage direction |
| [`plans/`](../plans/README.md) | Plans, designs and proposals; read each file's own status line |
| `evidence/` | Frozen validation records and review artefacts |
| `superpowers/plans/` | Execution plans of earlier work |

## Terms of the development history

| Term | Meaning |
| --- | --- |
| **The Pilot** | The original Time Pilot, the first phase of this repository, and later the name of the repository as the development and architecture-validation Pilot of Crux |
| **Pilot milestones M0 to M5** | Milestones of the original Time Pilot plan. Their acceptance identifiers, such as `M5-03`, appear in `baseline.md`, `implementation-status.md` and the Pilot plans |
| **Platform milestones** | The GitHub milestones of this repository, for example M4 for storage and configuration services, M8 for the boot platform and M11 for HTTPS web management. They reuse some numbers of the Pilot milestones: a page that cites `baseline.md` or a Pilot plan means the Pilot milestone, and a page that cites issue numbers means the platform milestone |
| **Build A and Build B** | The two builds of the phase 1 experiment in ADR-0001 (decision D10): Build A uses plain Zephyr, Build B uses Crux with an adapter |
| **WP1a** | The first work package of milestone M8 (boot platform), tasks 0 to 7 of issue #296 |
| **Evidence row identifiers** (E12, B65, F8, D165 ...) | A letter and a number that name one row of an evidence table, a findings list or a decision list in a record. They identify the row in that record only |
| **Draft PR, reviewer PASS** | Substantive changes arrive as Draft pull requests with recorded validation evidence and an independent review. A review PASS does not authorise a merge |
