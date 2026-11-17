# Contributing to <PRODUCT>

> **Template.** Copy this file to the root of a product repository as `CONTRIBUTING.md`, replace `<PRODUCT>`, `<product>` and every other `<placeholder>`, decide the open choices in the last section, and delete this note. It is adapted from the practices of Crux's own `CONTRIBUTING.md` and `AGENTS.md`, and it is a starting point: the product owns its copy and may change any rule. Crux does not enforce this file in a product repository, and the copy in `crux-pilot` is a separate, protected file.

## Purpose and scope

This guide says how changes to <PRODUCT> are made, checked and reviewed. It applies to source code, devicetree, Kconfig, board definitions, drivers, tests, documentation, build configuration and CI workflows in this repository. Where it is silent, follow the approved issue and the decisions recorded in this repository. A recorded decision stays in force until a new one replaces it, and it is not asked again unless new evidence changes it.

<PRODUCT> builds on Crux and on Zephyr. The code rules for adapters, devicetree, Kconfig and drivers are in Crux's [Zephyr and driver code in a product repository](https://github.com/wonny-labs/crux-pilot/blob/main/docs/coding-guidelines.md#zephyr-and-driver-code-in-a-product-repository). The checks that run from this repository's root are in [style/README.md](style/README.md).

## Making changes

- Keep each change to one coherent purpose. Separate unrelated changes where that helps review and testing.
- Keep the three layers apart: product logic in `domain/` as plain C, Zephyr code in the adapters and drivers, and Crux services behind a port the product owns. [Choosing an API](https://github.com/wonny-labs/crux-pilot/blob/main/docs/choosing-an-api.md) says where each kind of code goes.
- Reuse Zephyr's drivers and subsystems before writing a driver or a wrapper. Do not add a layer for a capability that has one consumer.
- Name product code with the product's own prefix: `<product>_` for functions and types, `<PRODUCT>_` for macros and enum constants, `CONFIG_<PRODUCT>_` for Kconfig symbols. Never use `crux_`, `CRUX_` or `CONFIG_CRUX_`: Crux reserves them. Do not rename Zephyr, vendor or third-party identifiers.
- Add or change tests with the behaviour. The default is to write the test first and see it fail for the right reason. When that is impractical, the pull request says why and gives other verification. Change an existing assertion only when the approved behaviour changes. Never weaken or delete a test to make a check pass.
- A new file carries an `SPDX-License-Identifier` line. Use original work and appropriately licensed upstream material only. Record the source and licence of third-party code. Do not add employer-owned or other confidential code, documents, credentials or restricted assets. Keep secrets and personal paths out of the repository.
- A change of the Crux or Zephyr revision in `west.yml` is its own pull request and records the result of `west crux-pins` (see the Crux [Product Composition Guide](https://github.com/wonny-labs/crux-pilot/blob/main/docs/product-composition.md)).
- A driver, with its binding, Kconfig and tests, is reviewed against Crux's [driver review checklist](https://github.com/wonny-labs/crux-pilot/blob/main/docs/driver-review-checklist.md). Copy its list into the pull request.

## Commit messages

Use a small subset of [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

~~~text
<type>: <short summary>

[explanation when needed]

[optional footers]
~~~

Types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`, `chore`, `revert`. Begin the summary with a lowercase imperative verb, keep proper names and acronyms as they are written, omit the final full stop, and stay under 72 characters including the type. Describe the change, not the work done. For a substantial change the body says why, including trade-offs. Put detailed results in the pull request. An intentional incompatible change carries a `BREAKING CHANGE:` footer. Scopes are optional. Use an existing module or directory name, and do not invent scopes from file names or issue numbers.

## Pull requests

Use a short-lived branch from the current default branch, and open a pull request for review. Do not push to the default branch. A substantive pull request says **what changed, why it is needed and how it was validated**, and it says which relevant check was not run and why. It includes, where they matter:

- **Impact:** affected modules, boards, environments, compatibility and known limits.
- **Risks and dependencies:** open uncertainty, follow-up work, changes needed for integration.
- **Validation context:** toolchain, configuration, board and Crux and Zephyr revisions.
- **Protected files:** every changed file on the [protected list](#protected-paths) with the approval that covers it.

Inspect the complete diff, remove temporary changes and confirm the reported results before asking for review. Squash-merge a reviewed pull request that is one coherent change, with the commit message above. Keep separate commits only when each one is meaningful and buildable.

## Checks

Run the checks that fit the change, and do not rerun costly unrelated ones without a reason.

| Check | Command or note |
| --- | --- |
| Format | `style/check-format.sh` |
| Patch style | `ZEPHYR_BASE=<zephyr checkout> style/check-patch.sh origin/main HEAD` |
| Crux include rules | `style/check-includes.sh` |
| Host tests of the domain | <command> |
| `native_sim` tests | <command, for example `west twister -p native_sim -T tests`> |
| Board cross-build | <command, one per board> |
| Static analysis of target code (advisory) | `style/check_target_tidy.py build`. Findings inform the review and do not fail a run |

A passing host test, a passing `native_sim` run, green CI, a successful cross-build and physical-board evidence are five different things, and none implies another. Record the revision, the commands, the configurations, the failures and the skipped checks in the pull request. Never report a check that was not run, or that was blocked, as passing.

## Review

A material change gets an independent review by someone who did not author it or its implementation. Changes to a protected path, a driver, a binding, a public interface, a security-relevant design or a hardware-facing procedure are material. The reviewer reads the requirements, the actual sources, the configuration, the tests and the retained evidence, and does not rely on the author's summary. The reviewer records one decision with reasons, limits and open findings:

- `PASS`: no blocking finding.
- `REVISE`: blocking findings that the author can fix inside the approved scope. The author fixes them and gets one independent re-check.
- `ESCALATE`: a finding needs a human decision, a material disagreement remains, or a blocking finding remains after the re-check.

A blocking finding is an unmet acceptance criterion, a broken rule of this file or of the approved scope, or a factual error. Record other findings in the issue, the pull request or a follow-up issue and decide them there, without starting another review round. A `PASS` satisfies the review gate and nothing else: it does not grant new scope, hardware access, a merge or the closing of an issue, and green CI does not replace it.

Merging needs explicit authorisation from <the human owner or role>. A review `PASS` and green CI do not constitute that authorisation.

## Protected paths

These paths hold the rules, the check definitions and the recorded evidence that reviews depend on. Edit the list to match the repository.

- `CONTRIBUTING.md`, `AGENTS.md` and any other agent instruction file
- `.github/`, which defines CI
- `style/`, `.clang-format`, `.clang-tidy`, `target.clang-tidy`, `scripts/` and the product-side include check, which define the checks
- `docs/evidence/` and any other recorded verification evidence
- `tools/` or wherever the hardware safety gates of a device-control tool live

Change an existing file on these paths only within an explicit human approval that covers that change. A new check script or evidence record may be added within the task. Keep accepted evidence unchanged. The pull request description lists each changed protected file, taken from `git diff --name-only --no-renames origin/<default>...HEAD`, with a link to the approval or, when it was given in a conversation, a quote with its time and place. Get a material independent review. Nothing enforces this list until the repository's settings do, so a reviewer checks it.

## Hardware

Physical programming, reset and other hardware operations need explicit per-task authorisation (for the current task), a verified target, probe and flash configuration, and a safe setup. An approval for an earlier task does not carry over. CI builds a hardware scenario and does not run it. A run goes through <the product's device-control route>, with its approval and the evidence recorded in the pull request.

## What this file does not decide

The product chooses these and writes the choice here:

- Whether commits need a `Signed-off-by` line (Zephyr's `Identity` compliance check requires one, so a product that does not adopt sign-off should not run that check).
- A scope convention, branch names and the merge method.
- Who may merge, the repository's branch protection and required review settings, and a code owners file.
- The licence of the product's own code, and its release and tag process.
- Whether the product adopts a safety or security standard. Crux treats MISRA C as advisory only, and a product that needs a certification chooses the rule set and the tool itself.
- Where an AI agent's instructions live. If agents work in the repository, give them an `AGENTS.md` with these same boundaries, and do not let it widen the approvals above.
