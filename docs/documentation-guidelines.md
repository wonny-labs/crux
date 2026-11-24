# Documentation guidelines

Every documentation change in Crux passes this standard: what goes on each page, where each fact lives and how much detail it carries. It covers the Markdown under `docs/` and every `README.md`. Code comments and public API documentation follow the [coding guidelines](coding-guidelines.md). Links, the link checker and document versions follow [CONTRIBUTING.md](../CONTRIBUTING.md#documentation).

## 1. Review checklist

Apply these tests in order to each page, section and sentence that a change adds or keeps. Act on the first test that fails.

| # | Test | If it fails |
| --- | --- | --- |
| 1 | The page type fits the reader's task ([section 2](#2-one-purpose-per-page)). | Move the text to a page of the type that fits. |
| 2 | The text serves the heading it sits under. | Move it under the heading it serves. |
| 3 | The fact has no other home ([section 3](#3-one-home-per-fact)). | Keep it in its home and link there. |
| 4 | The reader of this page would fail or be confused without it ([section 4](#4-only-what-the-reader-needs)). | Move it to a page whose reader needs it, such as a record, the issue or the pull request, or cut it if no reader does. |
| 5 | It holds no history, status or measurement ([section 5](#5-current-state-only)). | Move it to its home in section 3. |

Never delete a fact that a reader needs and that has no other home: move it to a page whose type fits.

## 2. One purpose per page

Each page has one type and one purpose. Its title names the subject, and its first paragraph says what the page is for and who reads it.

| Type | The reader wants to | It holds |
| --- | --- | --- |
| **Entry**: the repository README, the [documentation map](README.md), [Getting started](getting-started.md) | Decide quickly whether Crux fits, and start | What Crux is and for whom, capabilities in plain words (no component names, Kconfig symbols or decision codes), a set-up path, links to the detail |
| **Tutorial** | Learn by doing | Numbered steps, each with its command and the result to expect; background is one sentence and a link |
| **How-to guide** | Finish one task they have chosen | Preconditions, the procedure and the result that shows it worked; background is one sentence and a link |
| **Reference**: contract, interface, policy, schema, glossary | Look up an exact fact | Every interface, behaviour, error, limit and option, exactly; a minimal example; migration notes when the contract requires them |
| **Explanation**: architecture, design rationale | Understand why the parts fit | Structure, reasons, alternatives and trade-offs, not procedures or option lists |
| **Dated**: record (one investigation, run, qualification or review; `docs/research/`), decision (`docs/decisions/`), plan (`docs/plans/`, `docs/superpowers/plans/`), history (`docs/history/`), evidence (`docs/evidence/`, `docs/baseline.md`) | Know what one activity found, decided, proposed or produced | That activity with its date, revision and limits. Never the only home of a current fact |
| **Template**: a file that a product copies and then owns, such as `templates/product/CONTRIBUTING.md` | Start a product file | Text the product owns after copying, without Crux history or status |

The first five types are **current-state pages**. Sections 4 and 5 apply to them.

### Which type is my page?

Take the first match: the dated folder's type; a record if the whole page is about one dated activity; a template; one of the three entry pages. Otherwise the reader's task decides: learning by doing (tutorial), doing a chosen task (how-to guide), looking facts up (reference), understanding (explanation). If a large part of the page fits another type, move that part to a page of its own type.

Record the specific type (`record`, `how-to` and so on) of each page outside the dated folders in [`tests/build/fixtures/docs_page_types.json`](../tests/build/fixtures/docs_page_types.json). A page that is not listed is checked as a reference page.

## 3. One home per fact

Each fact, table, command and status lives on one page: the page whose type it belongs to. An option belongs to a reference page, a procedure to a how-to guide, a reason to an explanation or an ADR. Other pages link to it. Two exceptions keep pages usable: a tutorial or an entry page may repeat a command that it runs, exactly as its home writes it, with a link for the options; a how-to guide may repeat one configuration line in context.

Some content has a fixed home:

| Content | Home |
| --- | --- |
| A component's stability tier, planned removal, tested environments, evidence level and board testing | [Component readiness](component-readiness.md); [ADR-0001](decisions/0001-application-boundary-and-api-stability.md#decision-4-api-stability-and-change-policy) defines the tiers |
| What changed in a release | The release notes |
| What a consumer changes to move to a new interface | The "Migration notes" section of that interface's contract |
| Why the project changed direction | The ADR that decided it; the narrative goes to [`docs/history/`](history/README.md) |
| Which pull request or issue delivered something, and who ran or reported what | The pull request and the issue |
| The results of a run: measured durations and sizes, logs, what was and was not verified | A record page, the pull request or `docs/evidence/` |
| Proposals and open choices | `docs/plans/` or the issue |

A contract page may say in one sentence what a component's status means for the reader's code, such as `new product code does not use this header`, and link the readiness row.

## 4. Only what the reader needs

Each page carries the detail that its type in section 2 names, and no more. Lead with what the reader needs most; prefer a link to a paragraph of background.

The reader of a guideline, a plan or an ADR needs the practice behind it: link the industry practice the page follows and say where it departs.

### Paragraphs and line breaks

Break text so that each block carries one idea, as the [Google developer documentation style guide](https://developers.google.com/style/paragraph-structure) and the [Microsoft Writing Style Guide](https://learn.microsoft.com/en-us/style-guide/scannable-content/) recommend.

- A paragraph covers one idea and stays short, about five sentences at most.
- Three or more parallel items become a list, and steps are numbered.
- Comparisons go in a table.
- A long paragraph of options or limits is split by topic.

Markdown ignores single newlines, so source line breaks do not change what readers see.
New or edited text puts one sentence on each line ([semantic line breaks](https://sembr.org/)), so that a diff shows which sentence changed.
Do not reflow text that a change does not otherwise touch.

## 5. Current state only

A current-state page states what is true at the revision it is read from. Outside the Migration notes section of a reference page, it holds none of the following; section 3 gives each its home.

- **Change narrative**: `was removed`, `previously`, `no longer`, `moved from`, `is now`, `since`, `will be removed`.
- **Dates and provenance**: the date of a change, `merged in PR #N`, who reported a result.
- **Verification trails**: `ran once on`, `has not been run yet`, `not yet verified`, `as reported by`.
- **Measurements of a run**: durations, sizes and timings from a run. A limit or guarantee that a contract makes is a fact, not a measurement.
- **Status lines**: only dated pages carry one at the top, such as `Proposal, not adopted`.
- **Routes that have not been run**: a procedure appears as steps only after it has been run. Until then the issue or a record holds it, and a known-limits note states the supported routes as a current fact.

Write the current rule instead of the change:

| Not this | This |
| --- | --- |
| `Crux Queue was removed in November; use k_msgq.` | `Use Zephyr k_msgq for queues.` The removal goes into the messaging contract's migration notes. |
| `The handle is no longer valid after close.` | `The handle is invalid after close.` |

## 6. Onboarding and board pages

Onboarding follows the structure of [Zephyr's Getting Started Guide](https://docs.zephyrproject.org/latest/develop/getting_started/index.html): one path in which the board is a parameter (`-b <board>`), ending with a build and flash for the reader's board; `native_sim` is one more target. The structure is the rule for Crux and for the product repositories built on it, such as crux-controller and crux-codesys.

| Page | Holds | Leaves out |
| --- | --- | --- |
| [Getting started](getting-started.md) | The Dev Container, a first build and one short "If you use a board" section with the one-time probe steps | Any step specific to one board |
| [Tutorial](tutorial.md) | One path: Part A on the Linux Host, Part B on `native_sim`, Part C on your board with the table of supported boards | Board detail, and status (it links [Component readiness](component-readiness.md)) |
| Board pages: `docs/boards/<board>.md`, indexed by [`docs/boards/README.md`](boards/README.md) | Everything specific to one board, in the sections Board target, Switches and jumpers, Probe and connection, Flash and debug, Recovery, Board image profiles, Known limits | Anything not specific to that board |

Only the Crux board pages describe a board that Crux supports. A product repository links them and keeps only its own board steps, such as its image, wiring or fixtures. Adding a board is one board page, one row in the board index and one row in the tutorial's board table.

## Checks

| Check | What it enforces |
| --- | --- |
| [`test_docs_page_types.py`](../tests/build/test_docs_page_types.py) | Current-state pages hold no more change, provenance or status markers than their allowlist entry in the fixture. Lower or remove an entry when you fix a page; never raise one. Raise a false positive in review. |
| [`test_docs_onboarding.py`](../tests/build/test_docs_onboarding.py) | The structure of section 6 |
| [`test_readme_scope.py`](../tests/build/test_readme_scope.py) | No history or lifecycle markers in the repository README |
| `scripts/check_docs.py` | Local links and anchors, as [CONTRIBUTING.md](../CONTRIBUTING.md#documentation) describes |

The checks match text and structure only. Review applies the checklist in section 1 to everything else.

## Sources

[Diátaxis](https://diataxis.fr/) and its [compass](https://diataxis.fr/compass/); Google [timeless documentation](https://developers.google.com/style/timeless-documentation) and [future features](https://developers.google.com/style/future); Google [paragraph structure](https://developers.google.com/style/paragraph-structure); Microsoft [top 10 tips](https://learn.microsoft.com/en-us/style-guide/top-10-tips-style-voice) and [scannable content](https://learn.microsoft.com/en-us/style-guide/scannable-content/); [semantic line breaks](https://sembr.org/); Write the Docs [principles](https://www.writethedocs.org/guide/writing/docs-principles/) and [docs as code](https://www.writethedocs.org/guide/docs-as-code/); Kubernetes [content guide](https://kubernetes.io/docs/contribute/style/content-guide/) and [page content types](https://kubernetes.io/docs/contribute/style/page-content-types/); GitLab [documentation style guide](https://docs.gitlab.com/development/documentation/styleguide/); [Zephyr Getting Started](https://docs.zephyrproject.org/latest/develop/getting_started/index.html). Crux departs from GitLab and Kubernetes on two points: version notes and per-page feature status stay out of current pages and go to release notes, migration notes and Component readiness.
