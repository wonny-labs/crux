# Documentation guidelines

These rules decide what goes on each documentation page and how much detail it carries. They apply to every Markdown page under `docs/`, to the `README.md` files of samples, templates, tests, tools and the web folder, and to the repository README. Code comments and public API documentation follow the [coding guidelines](coding-guidelines.md) instead.

The rules have six parts: one page type per page, current state only, detail by reader, status in one place, a check that stops new drift, and one structure for onboarding and board pages.

## 1. One type per page

Every page has exactly one type. The type says who reads the page, what they want from it, and what it must leave to other pages.

| Type | The reader wants to | It holds | It leaves out |
| --- | --- | --- | --- |
| **Entry** (the repository README, the [documentation map](README.md), [Getting started](getting-started.md)) | Decide in five minutes whether Crux fits, and start | What Crux is and for whom, capabilities in plain words, a set-up path that works as written, links to read next | Internal component names, provider lists, lifecycle and evidence detail, history |
| **Tutorial** | Learn by doing, from nothing to a working result | Numbered steps, each with the command and the result to expect | Option comparisons, internals, alternatives, history |
| **How-to guide** | Finish one task they have already chosen | The procedure for that task, its preconditions and the result that shows it worked; links to background | Explanations longer than a sentence, reference tables that another page owns |
| **Reference** (contract, interface, policy, schema, glossary) | Look up an exact fact | Interfaces, behaviour, errors, limits, configuration options, a minimal example, and migration notes when the contract requires them | How it was decided, test results, open questions, usage walkthroughs, history |
| **Explanation** (architecture, design rationale, review guides) | Understand why and how the parts fit | Structure, reasons, alternatives and their trade-offs | Step-by-step procedures, option tables that a reference page owns |
| **Decision** (`docs/decisions/`) | Know what was decided and why | One ADR: context, options, decision, consequences | Procedures; later changes go into a new ADR |
| **Record** (investigations, qualification and validation records, feasibility reports, review records, research notes in `docs/research/`) | Know what one dated activity found | The question, the method, the results, the date and revision, the limits | Current guidance: a record is never the only home of a current fact |
| **Plan** (`docs/plans/`, `docs/superpowers/plans/`) | Know what is proposed or scheduled | Proposals, work packages, open choices | Current behaviour |
| **History** (`docs/history/`) | Know how the project got here | Superseded pages, milestone and run records, change narratives | Anything a current reader needs |
| **Evidence** (`docs/evidence/`, `docs/baseline.md`) | Check a claim | Logs, manifests and the files that back a record | Prose guidance |
| **Template** (files that a product copies, such as `templates/product/CONTRIBUTING.md`) | Start a product file | Text the product owns after copying | Crux history and status |

Entry, tutorial, how-to, reference and explanation pages are **current-state pages**. The other types are dated by nature and may describe the past.

### Which type is my page?

Answer the questions in order and stop at the first yes. If a later question would also be yes for a large part of the page, the page is mixed: record the split as a finding and move that part to a page of its own type.

| # | Question | Type |
| --- | --- | --- |
| 1 | Is it under `docs/decisions/`, `docs/plans/`, `docs/superpowers/plans/`, `docs/history/` or `docs/evidence/`? | The folder's type |
| 2 | Is the subject of the page one dated activity (a study, a run, a qualification, a review, the delivery of one issue) rather than a part of the platform? | Record |
| 3 | Is it a file that a product copies and then owns? | Template |
| 4 | Is it the repository README, the documentation map or Getting started? | Entry |
| 5 | Does a newcomer follow it from start to finish to learn, with an expected result for each step? | Tutorial |
| 6 | Does a reader who has chosen a task follow it to finish that task? | How-to guide |
| 7 | Does a reader look facts up in it rather than read it through? | Reference |
| 8 | Otherwise: does it explain structure, reasons or trade-offs? | Explanation |

A contract page whose subject is a component is a reference page even when it also carries test results; question 2 asks about the subject of the whole page, not about one section. The test results are then the mixed-in part that moves.

The type of each page outside the typed folders is recorded in [`tests/build/fixtures/docs_page_types.json`](../tests/build/fixtures/docs_page_types.json). Add a new page there with its type; a page that is not listed is checked as a reference page.

### Examples

- The [tutorial](tutorial.md) gives one command per step and the line to expect, such as `CONTROLLER_COMPLETE cycles=20`. It does not compare Twister with CTest; the [test guide](../tests/README.md) does that.
- A contract page that opens with `Status: merged in PR #210 for Issue #177` mixes a record into a reference page. The pull request already holds that provenance, and [Component readiness](component-readiness.md) holds the evidence level. The contract keeps the interface.
- A section called "Decisions for review" or "What is built, faked and untested" on a contract page is a record or a plan. It belongs in the issue, the pull request, a record page or `docs/plans/`.
- An architecture page that contains a proposal "not adopted, for the owner's decision" mixes a plan into an explanation. The proposal belongs in `docs/plans/` until it is adopted.

## 2. Current state only

A current-state page describes what is true at the revision it is read from. It does not narrate change. Phrases such as `was removed`, `previously`, `no longer`, `formerly`, `moved from`, `will be frozen`, `renamed from`, a date on which something changed, and `merged in PR #N` are markers of change history or provenance.

Each kind of change text has its own home:

| Change text | Home |
| --- | --- |
| What changed in a release, including removals and renames | The release notes, or the CHANGELOG once one exists |
| What a consumer must do to move from an old interface to a new one | A "Migration notes" section of that interface's contract page, when the contract requires one |
| Why and when the project changed direction | The ADR that decided it, and [`docs/history/`](history/README.md) for the narrative |
| Which pull request or issue delivered a page or a feature | The pull request and the issue |

Move such text to its home; never delete information that has no other home. When a fact is only true for a while, such as "no release tag exists yet", state it once on the page that owns it (here the [Product Composition Guide](product-composition.md#versions)) and link to it.

Write the current rule instead of the change:

| Not this | This |
| --- | --- |
| `Crux Queue was removed on 20 November 2026; use k_msgq.` | `Use Zephyr k_msgq for queues.` The removal goes into the messaging contract's migration notes |
| `This template moved from samples/product_template to templates/product.` | `The product template is templates/product.` |
| `The handle is no longer valid after close.` | `The handle is invalid after close.` |

## 3. Detail by reader and layer

Detail grows from the entry pages to the reference pages:

- **Entry pages** let a newcomer decide in five minutes. They name capabilities in plain words, not components, providers, Kconfig symbols or decision codes, and they link to the pages that hold the detail.
- **Tutorials and how-to guides** give enough to finish their one task and no more. Background is one sentence and a link.
- **Reference pages** are complete and exact: every option, every error, every limit. They are the most detailed layer.
- **Explanation pages** go deep on reasons, not on procedures or option lists.

**Single source.** Each fact, table or command lives on one page; other pages link to it. Two exceptions keep pages usable:

- A tutorial or an entry page may repeat a command that it runs as one of its steps, as long as the command is written exactly as on the page that owns it and the step links that page for options.
- A how-to guide may repeat one configuration line in context; the table of all options stays on the reference page.

The owner of a fact is the page of the type that the fact belongs to: an option belongs to a reference page, a procedure to a how-to guide, a reason to an explanation or an ADR.

## 4. Status and evidence in one place

The lifecycle and verification status of each component lives only in [Component readiness](component-readiness.md): its tier (`Experimental`, `Unstable` and so on), a freeze or a planned removal, the environments where it is tested, the evidence level it has reached, and whether it has been tested on a board. The stability tiers themselves are defined by [ADR-0001](decisions/0001-application-boundary-and-api-stability.md#decision-4-api-stability-and-change-policy).

Other current-state pages link to the readiness row instead of restating the status. A contract page may say in one sentence what a status means for the reader's code, such as `new product code does not use this header`, with the link. A record page states the status of what it tested at its date, because that is its result.

A page may carry a document status at its top only when its type is not current-state (for example `Record of the investigation for issue #141, 7 November 2026` or `Proposal, not adopted`). A current-state page is current by being in the tree; it carries no status line.

## 5. The check

[`tests/build/test_docs_page_types.py`](../tests/build/test_docs_page_types.py) scans the current-state pages for three groups of lexical markers:

| Rule | Markers | Waived on |
| --- | --- | --- |
| `history` (any case) | `was`, `were`, `has been`, `have been`, `is now` or `are now` followed by `removed`, `renamed`, `replaced`, `dropped` or `deleted`; `moved from`, `renamed from`, `previously`, `no longer`, `formerly`; `will be` followed by `frozen`, `removed` or `deprecated` | On a reference page, any section whose heading contains `migration` (any case), up to the next heading of the same or a higher level |
| `provenance` (any case) | `merged in PR` or `merged in pull request`, `for review in a Draft PR`, and `on`, `since` or `until` followed by a written date such as `on 9 November 2026` | None |
| `status` (all case-sensitive) | `Experimental`, `Unstable`, `frozen` (not `frozen manifest`, `frozen lock`, `frozen-style` and similar release terms), `to be removed`, `deprecated`, and `ran`, `run`, `been run` or `executed` followed by `on a`, `on the` or `on any` and `board`, with an optional `real` or `physical` before `board` | [Component readiness](component-readiness.md) |

It skips fenced code blocks, text in code spans, pages of the other types, and the repository README, which [`test_readme_scope.py`](../tests/build/test_readme_scope.py) guards on its own.

The pages that break these rules today are recorded in the fixture's allowlist, with the number of markers per rule, as found by the [documentation audit](plans/documentation-audit-2026-11.md). The test fails when a page has more markers than its allowlist entry, so new drift fails while existing text does not block unrelated work. When you fix a page, lower or remove its entry; never raise one. If a marker is a false positive that cannot be reworded, raise it in review rather than in the allowlist.

The check is lexical and narrow. It does not judge page types, duplication or the level of detail: review does that against sections 1 to 4.

## 6. Onboarding and board pages

Onboarding follows Zephyr's getting-started structure: one path, in which the board is a parameter (`-b <board>`), the last part builds a sample for the reader's board and flashes it, and `native_sim` is one more target. This structure is the rule for Crux and for the product repositories built on it, such as crux-controller and crux-codesys.

| Page | Holds | Leaves out |
| --- | --- | --- |
| Getting started ([`getting-started.md`](getting-started.md)) | The environment and a first working build: opening the one Dev Container, what it sets up by itself and how to rerun it. One short "If you use a board" section: the probe, the USB connection, a link to the board pages, and the one-time steps that give the Dev Container a probe, which are the same for every board (on WSL2 the three `usbipd` commands, `scripts/bootstrap.sh board-host` and the probe software package), with a link to the probe's route guide | Every procedure specific to one board |
| Tutorial ([`tutorial.md`](tutorial.md)) | One path in three parts: A on the Linux Host, B on `native_sim`, C on your board. Part C opens with "No board? Parts A and B run every sample and test.", then a table of supported boards (board, `-b` target, probe, board guide link, and no status words: it links [Component readiness](component-readiness.md) for status), then build, flash and the console line to expect | Board switches, jumpers, recovery and other board detail; a procedure that has not been run |
| Board pages (`docs/boards/<board>.md`, indexed by [`docs/boards/README.md`](boards/README.md)) | Everything specific to one board, in fixed sections: Board target, Switches and jumpers, Probe and connection, Flash and debug, Recovery, Board image profiles, Known limits | Anything that is not specific to that board |

- **Board details live in Crux.** Only `docs/boards/<board>.md` in Crux describes a board that Crux supports. A product repository links the Crux board page and keeps only its product-specific board steps, such as its own image, wiring or fixtures.
- **Adding a board** is one new board page, one row in `docs/boards/README.md` and one row in the tutorial's board table.
- **Only run procedures.** A board page and Part C describe a route only after it has been run, and they say on which host. A route that has not been run is named in one sentence, not written as steps.
- [`tests/build/test_docs_onboarding.py`](../tests/build/test_docs_onboarding.py) checks this structure in Crux.
