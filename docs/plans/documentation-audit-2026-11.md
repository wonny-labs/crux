# Documentation audit, November 2026

Record of an audit of every documentation page against the [documentation guidelines](../documentation-guidelines.md), 22 November 2026. It reports findings and proposes where each one goes. It changes no page; the fixes come later in the batches at the end, which the owner chooses.

## Scope and method

**Pages.** All 308 Markdown pages under `docs/`, the repository `README.md`, the 27 other `README.md` files of samples, templates, tests, tools, patches and the web folder, and the two product-template pages `templates/product/CONTRIBUTING.md` and `templates/product/RELEASE.md`. `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.claude/` and test fixtures are governance or test files and are out of scope.

**Revisions.** `origin/main` at `2c017f68`. Six pages that the open README pull request #543 changes (`README.md`, `docs/README.md`, `docs/architecture.md`, `docs/component-readiness.md`, `docs/getting-started.md`, `docs/porting-to-a-new-board.md`) were audited as on its head `3f8b8614`, and their line numbers below are from that head. The `layout-quickstart` branch (head `07604924`, stacked on #543) will change `README.md`, `docs/getting-started.md`, `docs/build.md`, `docs/first-hour.md` (renamed to `docs/tutorial.md`) and three sample READMEs again; findings on those pages should be re-checked after it merges.

**How the findings were found.**

- Groups (b) and (d) come from the lexical scan of [`tests/build/test_docs_page_types.py`](../../tests/build/test_docs_page_types.py), run over the current-state pages, and were then read by hand. Each row is one page; the example is the first marker on it. The scan does not see history or status written without its marker words, so a few hand-found rows follow each table.
- Groups (a), (c) and (e) were found by reading: the headings of every current-state page (a search for sections such as "Decisions", "Results", "What is untested" and "proposal"), the fenced commands that appear on more than one page, and the entry and product-guide pages in full.
- Quotes are short excerpts, under 15 words, with Markdown removed.

**Counts.**

| Group | Findings | Notes |
| --- | --- | --- |
| (a) Type unclear or mixed | 16 | A1 alone covers 22 contract and composition pages |
| (b) History or migration text in a current-state page | 59 | 56 pages from the scan (146 markers: 49 history, 97 provenance), 3 hand-found; one more scanned row is a false positive |
| (c) Duplicated facts or commands | 13 | |
| (d) Status or lifecycle restated outside readiness | 60 | 57 pages from the scan (234 markers), 3 hand-found; one more scanned row is a false positive |
| (e) Detail level wrong for the page type | 12 | |

The 380 scanned markers, false positives included, are the allowlist in [`tests/build/fixtures/docs_page_types.json`](../../tests/build/fixtures/docs_page_types.json). The allowlist takes, for each page, the larger count of `main`, #543's head and the `layout-quickstart` head, so that neither open branch fails the new check when it merges.

## Classification

The type of every page outside the typed folders is recorded in the fixture above; this is the same list. Question 2 of [Which type is my page?](../documentation-guidelines.md#which-type-is-my-page) decided most borderline cases: a page whose subject is one investigation, run, qualification or review is a record, even when it sits beside the contracts.

**By folder.** `docs/decisions/` (7): decision. `docs/plans/` (32) and `docs/superpowers/plans/` (22): plan. `docs/history/` (17): history. `docs/evidence/` (99) and `docs/baseline.md`: evidence. `docs/research/` (3): record. The repository `README.md` is an entry page, guarded by `test_readme_scope.py` from #543.

**Entry** (2): `docs/README.md`, `docs/getting-started.md`

**Tutorial** (2): `docs/first-hour.md`, `docs/tutorial.md` (on the layout branch)

**How-to guide** (33): `docs/boot-image-inspection.md`, `docs/boot-porting-rt1062.md`, `docs/boot-reproducibility.md`, `docs/build.md`, `docs/ci-zephyr-shards.md`, `docs/dependency-review.md`, `docs/driver-review-checklist.md`, `docs/e2e-native-220.md`, `docs/emmc-reliance-physical-gate.md`, `docs/management-in-a-product.md`, `docs/microsd-physical-gate.md`, `docs/porting-to-a-new-board.md`, `docs/product-composition.md`, `docs/secure-boot-bench-session.md`, `docs/secure-boot-board-test-procedure.md`, `docs/shared-hardware-modules.md`, `docs/vendor-kits.md`, `docs/writing-a-product-driver.md`, `samples/README.md`, `samples/controller/README.md`, `samples/controller/zephyr/README.md`, `samples/messaging/README.md`, `samples/time/README.md`, `samples/web/angular/README.md`, `samples/web_project/README.md`, `templates/hardware-module/README.md`, `templates/kit-module/README.md`, `templates/organisation-manifest/README.md`, `templates/product/README.md`, `templates/product/drivers/README.md`, `templates/product/style/README.md`, `tests/target/boot-bench/README.md`, `web/README.md`

**Reference** (62): `docs/access-contract.md`, `docs/board-image-profiles.md`, `docs/boot-composition.md`, `docs/choosing-an-api.md`, `docs/cli-contract.md`, `docs/cli-over-ssh.md`, `docs/coding-guidelines.md`, `docs/compatibility-table.md`, `docs/component-readiness.md`, `docs/composition-interfaces.md`, `docs/configuration-contract.md`, `docs/credential-store.md`, `docs/documentation-guidelines.md`, `docs/emmc-reliance-composition.md`, `docs/file-composition-interface.md`, `docs/file-contract.md`, `docs/file-service-contract.md`, `docs/gpio-contract.md`, `docs/https-composition.md`, `docs/i2c-contract.md`, `docs/image-state-contract.md`, `docs/logging-contract.md`, `docs/management-glossary.md`, `docs/messaging-contract.md`, `docs/native-composition-242.md`, `docs/native-interface-policy.md`, `docs/native-management-composition.md`, `docs/network-settings-service.md`, `docs/networking-contract.md`, `docs/reboot-service.md`, `docs/release-bundle-checker.md`, `docs/security-event-contract.md`, `docs/serial-contract.md`, `docs/spi-contract.md`, `docs/ssh-integrated-image.md`, `docs/ssh-provider-contract.md`, `docs/ssh-wolf-provider.md`, `docs/status-configuration-services.md`, `docs/superpowers/specs/2026-10-24-logging-design.md`, `docs/superpowers/specs/2026-10-24-serial-design.md`, `docs/superpowers/specs/2026-10-24-system-health-design.md`, `docs/superpowers/specs/2026-10-25-time-redesign.md`, `docs/thread-sync.md`, `docs/time-busy-wait.md`, `docs/time-contract.md`, `docs/tls-certificate.md`, `docs/web-assets.md`, `docs/web-contract.md`, `docs/web-management-apis.md`, `docs/web-session.md`, `patches/zephyr/README.md`, `tests/README.md`, `tests/consumer_poc/README.md`, `tests/consumer_system/README.md`, `tests/controller_network_stack/README.md`, `tests/execution_runtime/README.md`, `tests/messaging_consumer/README.md`, `tests/native/integrated_output/README.md`, `tests/native/logger_phase/README.md`, `tests/native/tls_offload_probe/credentials/README.md`, `tools/device_control/README.md`, `web/api/README.md`

**Explanation** (7): `docs/architecture.md`, `docs/boot-overview.md`, `docs/psa-crypto-design.md`, `docs/secure-boot-and-update-review.md`, `docs/secure-boot-verification-ladder.md`, `docs/secure-management-review.md`, `docs/sftp-design.md`

**Record** (50): `docs/boot-bootloader-update-investigation.md`, `docs/boot-emmc-investigation.md`, `docs/boot-hab-status.md`, `docs/boot-update-investigation.md`, `docs/configuration-native-validation.md`, `docs/configuration-validation.md`, `docs/dependency-review-fatfs-r0.16.md`, `docs/dependency-review-mbed-tls-4.1.1.md`, `docs/dependency-review-wolf-pins.md`, `docs/emmc-reliance-file-service-assessment.md`, `docs/execution-profile.md`, `docs/file-native-validation.md`, `docs/file-validation.md`, `docs/flash-safety-acceptance.md`, `docs/flash-safety-poc.md`, `docs/flash-xip-evidence.md`, `docs/implementation-status.md`, `docs/logging-validation.md`, `docs/m2-physical-verification.md`, `docs/m3-validation.md`, `docs/m5-pilot-validation-plan.md`, `docs/messaging-validation.md`, `docs/microsd-composition.md`, `docs/networking-physical-preparation.md`, `docs/nvs-capacity-investigation.md`, `docs/nvs-startup-read-investigation.md`, `docs/physical-verification-plan.md`, `docs/platform-m1-readiness.md`, `docs/psa-crypto-qualification.md`, `docs/rt1060-bench-file-backend.md`, `docs/rt1060-bench-first-account.md`, `docs/rt1060-bench-freeze-and-capture-design.md`, `docs/rt1060-bench-image-plan.md`, `docs/rt1060-bench-network-buffers.md`, `docs/rt1060-bench-trim-rsa.md`, `docs/rt1060-isn-fail-closed.md`, `docs/rt1060-management-image-feasibility.md`, `docs/rt1060-mbed-management-image.md`, `docs/rt1060-wolf-entropy.md`, `docs/rt1170-evk-a1-feasibility.md`, `docs/serial-validation.md`, `docs/settings-error-investigation.md`, `docs/static-analysis-coverage.md`, `docs/storage-configuration-assessment.md`, `docs/storage-pilot-software-handoff.md`, `docs/system-validation.md`, `docs/test-foundation-proposal.md`, `docs/upstream-reuse.md`, `docs/web-advanced-flows.md`, `docs/web-config-flow.md`

**Template** (2): `templates/product/CONTRIBUTING.md`, `templates/product/RELEASE.md`

Classification notes:

- `docs/getting-started.md` is an entry page, not a tutorial: it is the set-up path that the README points to, and the tutorial starts after it.
- The four `docs/superpowers/specs/` designs are classified as reference because the documentation map calls them current contracts (`docs/README.md:103`); each also carries design alternatives (finding A10).
- `docs/board-image-profiles.md`, `docs/test-foundation-proposal.md`, `docs/static-analysis-coverage.md` and `docs/e2e-native-220.md` were the closest calls; findings A3, A4 and A11 say why.
- 50 record pages sit at the top of `docs/` beside the current pages (finding A8).

## Findings

### (a) Type unclear or mixed

| # | File and line | Quote | Finding | Proposed target |
| --- | --- | --- | --- | --- |
| A1 | 22 pages, line 3: `access-contract`, `cli-contract`, `cli-over-ssh`, `credential-store`, `e2e-native-220`, `file-service-contract`, `https-composition`, `native-composition-242`, `native-management-composition`, `network-settings-service`, `reboot-service`, `security-event-contract`, `sftp-design`, `ssh-integrated-image`, `ssh-provider-contract`, `ssh-wolf-provider`, `status-configuration-services`, `tls-certificate`, `web-assets`, `web-contract`, `web-management-apis`, `web-session` | “Status: merged in PR #210 for Issue #177” (`access-contract.md:3`) | The management-stack pages share a delivery template: a provenance status line, "What is built, faked and untested", "Results" and "Decisions for review" or "Decisions taken without an answer" sections (for example `web-session.md:9`, `:262`, `:289`; `reboot-service.md:16`, `:447`, `:469`; `tls-certificate.md:30`, `:425`, `:462`, `:473`). A contract and a delivery record share one page | Interface, behaviour and limits stay. Provenance goes to the PR and issue; evidence level to readiness; results to a record page; open decisions to the issue or `docs/plans/` |
| A2 | `docs/architecture.md:170`, `:243`, `:305` | “Layout and naming of samples (proposal, not adopted)” | Two proposals and the status of a move inside the explanation page | `docs/plans/` until adopted |
| A3 | `docs/board-image-profiles.md:3`, `:126`, `:219`, `:312`, `:354` | “Status: proposed, software only.” | A reference for the image profiles carries decisions, blockers and open questions for the owner | Profile reference stays; decisions and blockers to a record or `docs/plans/` |
| A4 | `docs/test-foundation-proposal.md:58`; linked from `tools/device_control/README.md:4` and `docs/README.md:19` | “Device-control contract” | A live contract (the device-control tool's) lives in a record of accepted proposals, and the documentation map's product path links the record | Contract to a reference page (for example `tools/device_control/README.md`); the proposal stays a record |
| A5 | `docs/management-in-a-product.md:20`, `:369`, `:392` | “Decided and open” | The product how-to also holds what is not built, the decision list and an evidence index | Readiness, the issue and `docs/plans/`; the guide links them |
| A6 | `tests/README.md:372`, `:449`, `:757` | “M5 physical qualification preparation” | The test guide (reference) keeps sections about past milestones, a pilot stage and a removed component | `docs/history/` or the suite's own README |
| A7 | `tests/execution_runtime/README.md:84`, `:102`, `:117` | “Initial RED evidence” | A suite README records its qualification history | A record or `docs/history/` |
| A8 | 50 pages at the top of `docs/` (the record list above) | “Status: historical investigation.” (`execution-profile.md:3`) | Records sit beside current pages with no folder that marks them, so a reader finds them by title alone | Owner decision: a `docs/records/` folder, or `docs/history/` for the superseded ones; in either case the documentation map lists them apart |
| A9 | `docs/product-composition.md:7`–`:552` | “Status: adopted practice, 2026-11-04.” | One page holds a how-to (start, pin, release), reference (version table `:327`, release bundle `:468`) and explanation (soft forks `:282`) | Split into a how-to and a reference page; reasons to explanation or ADR-0004 |
| A10 | `docs/superpowers/specs/2026-10-24-logging-design.md:30`, `…serial-design.md:9`, `…system-health-design.md:23`, `2026-10-25-time-redesign.md:105`; `docs/README.md:103` | “Alternatives and selected direction” | Designs act as current contracts and still hold alternatives and migration evidence, under a folder named after a tool | Contract text to the component's contract page; alternatives to explanation or an ADR |
| A11 | `docs/ci-zephyr-shards.md:70`, `:92` | “Options measured and not adopted” | A how-to for adding a check also holds measurements and rejected options | Measurements to a record; the how-to keeps the procedure |
| A12 | `samples/controller/README.md:67`; `web/README.md:37`; `samples/web_project/README.md:32` | “Physical verification — bounded evidence” | Sample and web how-to pages carry evidence sections, one of them for an earlier implementation | Readiness and records |
| A13 | `docs/access-contract.md:30`, `docs/cli-contract.md:310`, `docs/credential-store.md:186` | “Changes to what the proposal states” | Contracts compare themselves with the proposal they came from | The proposal in `docs/plans/`, or `docs/history/` |
| A14 | `docs/thread-sync.md:341`, `:370`; `docs/messaging-contract.md:23`, `:33`, `:86`, `:116` | “Implementation and TDD verification proposal” | Contracts hold design alternatives, an implementation proposal and validation traceability | Alternatives to an ADR or explanation; validation to the validation record |
| A15 | `docs/configuration-contract.md:9`, `docs/file-contract.md:7` | “Recommendation and alternatives” | The first section of each contract is the selection study | Explanation or the matching record |
| A16 | `docs/static-analysis-coverage.md:3` | “Status (re-read 2026-11-18): stages 1 and 2 are merged” | Coverage facts (reference) and the staged delivery (record) are one page | Coverage reference, plus a record of the stages |

### (b) History or migration text in a current-state page

| Page | Type | Markers | Lines | Example (line) | Target |
| --- | --- | --- | --- | --- | --- |
| [docs/README.md](../README.md) | entry | 3 | 121, 133 | 121: “… was frozen too and was removed on 20 November 2026), and gpio …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/boot-porting-rt1062.md](../boot-porting-rt1062.md) | how-to | 2 | 3 | 3: “Status: Guidance, current on 15 November 2026, with the image-state statements …” | The PR and issue (drop from the page) |
| [docs/build.md](../build.md) | how-to | 3 | 167, 267, 287 | 167: “… are unchanged. Crux Queue was removed on” | Contract migration notes, release notes or `docs/history/` |
| [docs/ci-zephyr-shards.md](../ci-zephyr-shards.md) | how-to | 1 | 88 | 88: “… is that a run no longer waits on the mirror. The times …” | Contract migration notes, release notes or `docs/history/` |
| [docs/e2e-native-220.md](../e2e-native-220.md) | how-to | 3 | 3, 291, 357 | 3: “Status: merged in PR #293 for Issue #220. …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/emmc-reliance-physical-gate.md](../emmc-reliance-physical-gate.md) | how-to | 2 | 36, 114 | 36: “… and the supply check. On 5 November 2026 the owner reported that …” | The PR and issue (drop from the page) |
| [docs/microsd-physical-gate.md](../microsd-physical-gate.md) | how-to | 1 | 50 | 50: “… photo check recorded afterwards, on 3 November 2026 at 16:33 UTC, as …” | The PR and issue (drop from the page) |
| [docs/porting-to-a-new-board.md](../porting-to-a-new-board.md) | how-to | 1 | 28 | 28: “… code, and Crux Queue was removed in favour of Zephyr k_msgq .” | Contract migration notes, release notes or `docs/history/` |
| [docs/product-composition.md](../product-composition.md) | how-to | 2 | 174, 178 | 174: “It was renamed from” the module switch's former name (quote shortened) | Contract migration notes, release notes or `docs/history/` |
| [docs/secure-boot-board-test-procedure.md](../secure-boot-board-test-procedure.md) | how-to | 2 | 460 | 460: “… and without a cause: on 5 November 2026 a port cut left …” | The PR and issue (drop from the page) |
| [docs/shared-hardware-modules.md](../shared-hardware-modules.md) | how-to | 1 | 96 | 96: “… since the board-name refusals were removed (crux-pilot pull request #503, merge commit …” | Contract migration notes, release notes or `docs/history/` |
| [docs/vendor-kits.md](../vendor-kits.md) | how-to | 1 | 92 | 92: “… at that tag would no longer equal the delivery's list, and the …” | Contract migration notes, release notes or `docs/history/` |
| [templates/product/README.md](../../templates/product/README.md) | how-to | 4 | 3, 55, 90 | 3: “This template moved from samples/product_template to templates/product on 9 November …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/access-contract.md](../access-contract.md) | reference | 2 | 3, 78 | 3: “Status: merged in PR #210 for Issue #177, …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/choosing-an-api.md](../choosing-an-api.md) | reference | 4 | 3, 26, 30 | 3: “… approved by the owner on 13 November 2026 (decisions P1 and P2 …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/cli-contract.md](../cli-contract.md) | reference | 1 | 3 | 3: “Status: merged in PR #238 for Issue #181, …” | The PR and issue (drop from the page) |
| [docs/cli-over-ssh.md](../cli-over-ssh.md) | reference | 3 | 3, 11, 112 | 3: “Status: merged in PR #267 for Issue #193, …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/compatibility-table.md](../compatibility-table.md) | reference | 1 | 5 | 5: “… against. The owner decided on 8 November 2026 that Crux's own release …” | The PR and issue (drop from the page) |
| [docs/component-readiness.md](../component-readiness.md) | reference | 2 | 36, 46 | 36: “… was frozen too and is now removed, see its row): no new …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/composition-interfaces.md](../composition-interfaces.md) | reference | 4 | 3, 7, 43 | 3: “… owner's acceptance of ADR-0001 on 12 November 2026 (D3), and written down …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/configuration-contract.md](../configuration-contract.md) | reference | 2 | 3, 99 | 3: “… Architecture and API Review on 23 October 2026. Production backend/layout adoption, upstream/native …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/credential-store.md](../credential-store.md) | reference | 2 | 3, 243 | 3: “Status: merged in PR #235 for Issue #178, …” | The PR and issue (drop from the page) |
| [docs/file-composition-interface.md](../file-composition-interface.md) | reference | 6 | 3, 42, 53, 75, 88 | 3: “Status: implemented , software only. The target and …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/file-contract.md](../file-contract.md) | reference | 2 | 3 | 3: “… Architecture and API Review on 23 October 2026. Production backend/layout adoption, upstream/native …” | The PR and issue (drop from the page) |
| [docs/file-service-contract.md](../file-service-contract.md) | reference | 2 | 3 | 3: “Status: merged in PR #232, implemented on Host …” | The PR and issue (drop from the page) |
| [docs/https-composition.md](../https-composition.md) | reference | 1 | 3 | 3: “Status: merged in PR #277 for Issue #185. …” | The PR and issue (drop from the page) |
| [docs/image-state-contract.md](../image-state-contract.md) | reference | 3 | 3, 73 | 3: “… owner approved as Experimental on 15 November 2026. The owner approved the …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/logging-contract.md](../logging-contract.md) | reference | 1 | 38 | 38: “… caller's mask and any previously pending SIGPIPE. It does” | False positive: "previously pending SIGPIPE" is signal behaviour, not history |
| [docs/messaging-contract.md](../messaging-contract.md) | reference | 1 | 13 | 13: “… paths name code that no longer exists.” | Contract migration notes, release notes or `docs/history/` |
| [docs/native-interface-policy.md](../native-interface-policy.md) | reference | 4 | 4, 33, 38 | 4: “and merged in PR #39.” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/native-management-composition.md](../native-management-composition.md) | reference | 1 | 3 | 3: “Status: merged in PR #263, the first part …” | The PR and issue (drop from the page) |
| [docs/network-settings-service.md](../network-settings-service.md) | reference | 1 | 3 | 3: “Status: merged in PR #287 for Issue #213. …” | The PR and issue (drop from the page) |
| [docs/networking-contract.md](../networking-contract.md) | reference | 1 | 3 | 3: “… approved by the user on 22 October 2026 for” | The PR and issue (drop from the page) |
| [docs/reboot-service.md](../reboot-service.md) | reference | 2 | 3, 156 | 3: “Status: merged in PR #290 for Issue #214. …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/release-bundle-checker.md](../release-bundle-checker.md) | reference | 3 | 3, 56, 59 | 3: “… a first shape , for review in a Draft PR. Refs #301, …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/security-event-contract.md](../security-event-contract.md) | reference | 1 | 3 | 3: “Status: merged in PR #234 for Issue #182, …” | The PR and issue (drop from the page) |
| [docs/ssh-integrated-image.md](../ssh-integrated-image.md) | reference | 1 | 3 | 3: “Status: merged in PR #313, the first part …” | The PR and issue (drop from the page) |
| [docs/ssh-provider-contract.md](../ssh-provider-contract.md) | reference | 3 | 3, 61, 345 | 3: “Status: merged in PR #239 for Issue #205, …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/ssh-wolf-provider.md](../ssh-wolf-provider.md) | reference | 4 | 3, 209, 224, 404 | 3: “Status: merged in PR #265 and PR #292 …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/status-configuration-services.md](../status-configuration-services.md) | reference | 3 | 3 | 3: “Status: implemented on Host with fakes for Issue …” | The PR and issue (drop from the page) |
| [docs/superpowers/specs/2026-10-24-logging-design.md](../superpowers/specs/2026-10-24-logging-design.md) | reference | 2 | 3, 180 | 3: “… implementation by the user on 24 October 2026, at” | The PR and issue (drop from the page) |
| [docs/superpowers/specs/2026-10-24-serial-design.md](../superpowers/specs/2026-10-24-serial-design.md) | reference | 2 | 3, 173 | 3: “… implementation by the user on 24 October 2026” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/superpowers/specs/2026-10-24-system-health-design.md](../superpowers/specs/2026-10-24-system-health-design.md) | reference | 2 | 3, 236 | 3: “… implementation by the user on 24 October 2026 at” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/thread-sync.md](../thread-sync.md) | reference | 3 | 7, 259, 296 | 7: “… and the ownership split merged in PR #52, with typed monotonic” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/tls-certificate.md](../tls-certificate.md) | reference | 2 | 3, 341 | 3: “Status: merged in PR #284 for Issue #190, …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/web-assets.md](../web-assets.md) | reference | 1 | 3 | 3: “Status: merged in PR #283 for Issue #189. …” | The PR and issue (drop from the page) |
| [docs/web-contract.md](../web-contract.md) | reference | 3 | 3, 249, 347 | 3: “Status: merged in PR #266 for Issue #184. …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/web-management-apis.md](../web-management-apis.md) | reference | 1 | 3 | 3: “Status: merged in PR #281 for Issue #187. …” | The PR and issue (drop from the page) |
| [docs/web-session.md](../web-session.md) | reference | 1 | 3 | 3: “Status: merged in PR #278 for Issue #186. …” | The PR and issue (drop from the page) |
| [tests/README.md](../../tests/README.md) | reference | 3 | 759, 761 | 759: “Crux Queue was removed on 20 November 2026 (see the …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [tests/messaging_consumer/README.md](../../tests/messaging_consumer/README.md) | reference | 1 | 20 | 20: “Crux Queue was removed (see the messaging contract). This” | Contract migration notes, release notes or `docs/history/` |
| [tests/native/logger_phase/README.md](../../tests/native/logger_phase/README.md) | reference | 1 | 18 | 18: “0/1/2/4 ms modelling the previously observed relative-loop drift. The corrected” | Contract migration notes, release notes or `docs/history/` |
| [tools/device_control/README.md](../../tools/device_control/README.md) | reference | 1 | 122 | 122: “… or the lock release no longer skips the rest. One that lands …” | Contract migration notes, release notes or `docs/history/` |
| [docs/architecture.md](../architecture.md) | explanation | 17 | 53, 65, 82, 119, 121, 154, 172, 177, 221, 227, 232, 245, 254, 297 | 53: “… which the owner accepted on 12 November 2026 (D1 to D3). It …” | Contract migration notes, release notes or `docs/history/`; The PR and issue (drop from the page) |
| [docs/boot-overview.md](../boot-overview.md) | explanation | 3 | 3, 17 | 3: “Status: Orientation page, current on 15 November 2026, with the image-state rows …” | The PR and issue (drop from the page) |
| [docs/secure-boot-and-update-review.md](../secure-boot-and-update-review.md) | explanation | 13 | 3, 64, 78, 80, 95, 116, 129, 133, 202, 206, 208 | 3: “… A review package, current on 15 November 2026, with the image-state statements …” | The PR and issue (drop from the page) |
| [docs/sftp-design.md](../sftp-design.md) | explanation | 3 | 3, 285, 452 | 3: “Status: merged in PR #264, with the WinSCP …” | The PR and issue (drop from the page) |

Hand-found, without a marker word:

| Page | Line | Quote | Target |
| --- | --- | --- | --- |
| `docs/getting-started.md` | 90 | “Builds were smaller then, so treat the 10 GiB drop as a lower bound.” | A measured figure or `docs/history/` |
| `docs/README.md` | 101 | “still carry the word "proposal", a leftover of their drafting.” | `docs/decisions/README.md` only (it already says so) |
| `docs/README.md` | 103 | “a folder named after the development tool that produced its first files” | `docs/history/`; see A10 |

### (c) Duplicated facts or commands

| # | Fact or command | Locations | Proposed single source |
| --- | --- | --- | --- |
| C1 | The three first commands (`bootstrap-host`, `bootstrap-zephyr --install-sdk`, `test-controller`) | `README.md:26`–`28`, `docs/getting-started.md:99`–`101`, `docs/first-hour.md:27`–`28` | README quick start; getting started links it; the tutorial may repeat its step under the tutorial exception. The `layout-quickstart` branch reorders these pages |
| C2 | Crux Queue is removed; use `k_msgq` | `docs/README.md:121`, `:133`; `docs/choosing-an-api.md:26`; `docs/build.md:167`, `:267`, `:287`; `docs/architecture.md:227`; `docs/porting-to-a-new-board.md:28`; `docs/native-interface-policy.md:127`, `:255`; `tests/README.md:757`–`759`; `docs/component-readiness.md:36`, `:46` | Migration note in `docs/messaging-contract.md:3`; the rule "queues use `k_msgq`" in `docs/choosing-an-api.md` |
| C3 | Thread, Sync and Serial frozen; GPIO, I2C and SPI frozen and to be removed | `docs/README.md:38`, `:42`, `:121`, `:133`, `:135`; `docs/architecture.md:152`, `:324`–`335`; `docs/build.md:165`; `docs/choosing-an-api.md:32`, `:42`, `:74`, `:75`; `docs/native-interface-policy.md:38`; `docs/porting-to-a-new-board.md:75`, `:83`; `samples/messaging/README.md:6` | Status: `docs/component-readiness.md:36`. Rule for product code: `docs/choosing-an-api.md` |
| C4 | The table of stability tiers | `docs/README.md:110`–`121` | ADR-0001 Decision 4 (`docs/decisions/0001-application-boundary-and-api-stability.md:226`) |
| C5 | No Crux release or tag exists | `README.md:49`; `docs/README.md:17`, `:158`; `docs/product-composition.md:3`, `:59`, `:331`; `docs/compatibility-table.md:3`, `:96`–`98`; `docs/porting-to-a-new-board.md:65`; `templates/product/README.md:7`; `docs/component-readiness.md:75` | `docs/product-composition.md:331` (Versions) |
| C6 | The MCUboot sysbuild command line | `docs/boot-composition.md:29`–`37`, `docs/secure-boot-board-test-procedure.md:107`–`116` | `docs/boot-composition.md` |
| C7 | The device-control configuration file | `tools/device_control/README.md:42`–`61`, `docs/secure-boot-board-test-procedure.md:285`–`303` | `tools/device_control/README.md` |
| C8 | The management Kconfig table | `docs/management-in-a-product.md:134`–`167`; the same symbols on each contract page (for example `docs/web-session.md`) | One reference table; the how-to links it |
| C9 | Suite commands | `docs/build.md:91` and `tests/README.md:74`; `docs/build.md:276` and `tests/README.md:227` | `tests/README.md` |
| C10 | The SDK download with `CRUX_GITHUB_TOKEN` | `docs/getting-started.md:78`–`79`, `docs/build.md:77` | `docs/getting-started.md` |
| C11 | Supported environments and their verification limits | `docs/getting-started.md:112`–`122`, `docs/architecture.md:7`, `docs/component-readiness.md` | Readiness for verification; getting started for the list of environments |
| C12 | The west manifest example | `docs/product-composition.md:55`–`57`, `:94`, `:117`; `docs/vendor-kits.md:144`–`150` | `templates/product/west.yml`; the guides show only the lines they change |
| C13 | Nothing has run on a board, for the management stack | `README.md:11`, `docs/README.md:47`, `:158`, `docs/management-in-a-product.md:7`, every A1 page | `docs/component-readiness.md` |

### (d) Status or lifecycle restated outside readiness

| Page | Type | Markers | Lines | Example (line) | Target |
| --- | --- | --- | --- | --- | --- |
| [docs/README.md](../README.md) | entry | 24 | 20, 22, 38, 42, 43, 47, 63, 69, 93, 116, 117, 121, 133, 135 | 20: “… repositories (a recommended convention, Experimental).” | A link to the [readiness](../component-readiness.md) row |
| [docs/boot-image-inspection.md](../boot-image-inspection.md) | how-to | 1 | 66 | 66: “… proposal is adopted as Experimental for rows I1 to I7 only and …” | A link to the [readiness](../component-readiness.md) row |
| [docs/boot-porting-rt1062.md](../boot-porting-rt1062.md) | how-to | 1 | 120 | 120: “… contract is adopted as Experimental for rows I1 to I7 (15 November …” | A link to the [readiness](../component-readiness.md) row |
| [docs/build.md](../build.md) | how-to | 2 | 165, 255 | 165: “frozen for new product code, so a new …” | A link to the [readiness](../component-readiness.md) row |
| [docs/driver-review-checklist.md](../driver-review-checklist.md) | how-to | 2 | 20, 146 | 20: “… style/check-includes.sh rejects the three frozen headers and the removed <crux/queue.h anywhere in …” | A link to the [readiness](../component-readiness.md) row |
| [docs/e2e-native-220.md](../e2e-native-220.md) | how-to | 1 | 4 | 4: “… evidence only. Nothing here ran on a board, and nothing here is …” | A link to the [readiness](../component-readiness.md) row |
| [docs/emmc-reliance-physical-gate.md](../emmc-reliance-physical-gate.md) | how-to | 1 | 162 | 162: “… see the W4 record), run on the board by images that do …” | A link to the [readiness](../component-readiness.md) row |
| [docs/management-in-a-product.md](../management-in-a-product.md) | how-to | 22 | 7, 33, 46, 59, 140, 154, 155, 156, 157, 158, 159, 160, 161, 162 and 7 more | 7: “… in this guide has run on a board. Every result is Host, …” | A link to the [readiness](../component-readiness.md) row |
| [docs/porting-to-a-new-board.md](../porting-to-a-new-board.md) | how-to | 8 | 28, 65, 75, 83, 119 | 28: “… , serial ) are frozen for new product code, and Crux Queue …” | A link to the [readiness](../component-readiness.md) row |
| [docs/product-composition.md](../product-composition.md) | how-to | 4 | 3, 18, 472, 532 | 3: “… bundle. They are not frozen, and no product release has been made …” | A link to the [readiness](../component-readiness.md) row |
| [docs/secure-boot-bench-session.md](../secure-boot-bench-session.md) | how-to | 1 | 3 | 3: “… this page has been executed on a board. Every duration is an …” | A link to the [readiness](../component-readiness.md) row |
| [docs/secure-boot-board-test-procedure.md](../secure-boot-board-test-procedure.md) | how-to | 1 | 3 | 3: “… this procedure has been executed on a board. Every expected result below …” | A link to the [readiness](../component-readiness.md) row |
| [docs/vendor-kits.md](../vendor-kits.md) | how-to | 2 | 3, 124 | 3: “Status: Experimental, a recommended convention, 2026-11-17. Not adopted as …” | A link to the [readiness](../component-readiness.md) row |
| [docs/writing-a-product-driver.md](../writing-a-product-driver.md) | how-to | 3 | 5, 168, 174 | 5: “… of the kit has run on a board. The example part is …” | A link to the [readiness](../component-readiness.md) row |
| [samples/messaging/README.md](../../samples/messaging/README.md) | how-to | 1 | 6 | 6: “Thread is frozen for new product code (see” | A link to the [readiness](../component-readiness.md) row |
| [templates/hardware-module/README.md](../../templates/hardware-module/README.md) | how-to | 1 | 7 | 7: “… and nothing here has run on a board or on native_sim . …” | A link to the [readiness](../component-readiness.md) row |
| [templates/kit-module/README.md](../../templates/kit-module/README.md) | how-to | 1 | 3 | 3: “… recommended convention that is Experimental. The kit kit-a , the variable KIT_A_PATH …” | A link to the [readiness](../component-readiness.md) row |
| [templates/product/README.md](../../templates/product/README.md) | how-to | 8 | 46, 55, 74, 80, 86, 90 | 46: “… contracts that are not frozen (Time, Logging, File and so on) and …” | A link to the [readiness](../component-readiness.md) row |
| [docs/access-contract.md](../access-contract.md) | reference | 2 | 121 | 121: “… whose Status: line reads Experimental (ADR-0001 decision 4), and the readiness table …” | A link to the [readiness](../component-readiness.md) row |
| [docs/board-image-profiles.md](../board-image-profiles.md) | reference | 14 | 19, 23, 47, 75, 79, 88, 110, 134, 146, 174, 324, 334, 341, 358 | 19: “tool_scripts , the extra frozen scripts of the tool repository One use …” | A link to the [readiness](../component-readiness.md) row |
| [docs/boot-composition.md](../boot-composition.md) | reference | 1 | 8 | 8: “… was programmed, booted or run on a board, and a successful build …” | A link to the [readiness](../component-readiness.md) row |
| [docs/choosing-an-api.md](../choosing-an-api.md) | reference | 8 | 26, 32, 42, 74, 75 | 26: “… ( <crux/queue.h ) was frozen too and was removed on 20 November …” | A link to the [readiness](../component-readiness.md) row |
| [docs/cli-contract.md](../cli-contract.md) | reference | 1 | 3 | 3: “… , ADR-0004 phase 1b, Experimental), which owns the console thread and the …” | A link to the [readiness](../component-readiness.md) row |
| [docs/coding-guidelines.md](../coding-guidelines.md) | reference | 1 | 112 | 112: “… Crux headers: the three frozen ones ( <crux/thread.h , <crux/sync.h , <crux/serial.h …” | A link to the [readiness](../component-readiness.md) row |
| [docs/composition-interfaces.md](../composition-interfaces.md) | reference | 5 | 7, 23, 35, 39 | 7: “… file system type ( Experimental, one constant and no function; see the …” | A link to the [readiness](../component-readiness.md) row |
| [docs/credential-store.md](../credential-store.md) | reference | 1 | 7 | 7: “… Public header <crux/credential_store.h ( Experimental), usage target crux::credential_store . It declares the …” | A link to the [readiness](../component-readiness.md) row |
| [docs/file-composition-interface.md](../file-composition-interface.md) | reference | 5 | 71, 75, 99, 118, 119 | 71: “Any run on a board none not authorised and …” | A link to the [readiness](../component-readiness.md) row |
| [docs/file-contract.md](../file-contract.md) | reference | 1 | 319 | 319: “new Experimental function and an owner decision under AGENTS.md, …” | A link to the [readiness](../component-readiness.md) row |
| [docs/gpio-contract.md](../gpio-contract.md) | reference | 6 | 3 | 3: “Frozen as Experimental, to be removed. ADR-0001, owner decision D4 …” | A link to the [readiness](../component-readiness.md) row |
| [docs/https-composition.md](../https-composition.md) | reference | 1 | 4 | 4: “… decision W18. Nothing here ran on a board. RT1060-EVKB results are” | A link to the [readiness](../component-readiness.md) row |
| [docs/i2c-contract.md](../i2c-contract.md) | reference | 6 | 3 | 3: “Frozen as Experimental, to be removed. ADR-0001, owner decision D4 …” | A link to the [readiness](../component-readiness.md) row |
| [docs/image-state-contract.md](../image-state-contract.md) | reference | 3 | 3 | 3: “Status: Experimental. The first piece of the contract's implementation: …” | A link to the [readiness](../component-readiness.md) row |
| [docs/management-glossary.md](../management-glossary.md) | reference | 1 | 3 | 3: “… records under docs/evidence/ are frozen and keep the names they were written …” | False positive: the sentence is about evidence records, not a component |
| [docs/messaging-contract.md](../messaging-contract.md) | reference | 3 | 3, 15 | 3: “… used Queue, it was frozen for new product code under P2 of …” | A link to the [readiness](../component-readiness.md) row |
| [docs/native-composition-242.md](../native-composition-242.md) | reference | 1 | 9 | 9: “… physical evidence, and nothing ran on a board. native_sim uses the host's …” | A link to the [readiness](../component-readiness.md) row |
| [docs/native-interface-policy.md](../native-interface-policy.md) | reference | 2 | 38 | 38: “Frozen interfaces. Thread, Sync and Serial are frozen …” | A link to the [readiness](../component-readiness.md) row |
| [docs/native-management-composition.md](../native-management-composition.md) | reference | 2 | 285, 334 | 285: “… Crux module's CONFIG_CRUX_PSA_THREADING ( Experimental, zephyr/psa_threading ) turns on MBEDTLS_THREADING_C and MBEDTLS_THREADING_ALT …” | A link to the [readiness](../component-readiness.md) row |
| [docs/network-settings-service.md](../network-settings-service.md) | reference | 2 | 3, 55 | 3: “… port. Nothing here has run on a board, and nothing applies an …” | A link to the [readiness](../component-readiness.md) row |
| [docs/reboot-service.md](../reboot-service.md) | reference | 1 | 3 | 3: “… image. Nothing here has run on a board. The services image does …” | A link to the [readiness](../component-readiness.md) row |
| [docs/release-bundle-checker.md](../release-bundle-checker.md) | reference | 3 | 3, 113 | 3: “… the checker are not frozen before a product's first real release, and …” | A link to the [readiness](../component-readiness.md) row |
| [docs/security-event-contract.md](../security-event-contract.md) | reference | 1 | 351 | 351: “… rest of this component, Experimental (ADR-0001 decision 4). web.csrf_rejected was defined before …” | A link to the [readiness](../component-readiness.md) row |
| [docs/serial-contract.md](../serial-contract.md) | reference | 2 | 3 | 3: “… November 2026). Serial is frozen for new product code: no new features …” | A link to the [readiness](../component-readiness.md) row |
| [docs/spi-contract.md](../spi-contract.md) | reference | 6 | 3 | 3: “Frozen as Experimental, to be removed. ADR-0001, owner decision D4 …” | A link to the [readiness](../component-readiness.md) row |
| [docs/thread-sync.md](../thread-sync.md) | reference | 6 | 3, 142, 153, 164, 185 | 3: “… Thread and Sync are frozen for new product code: no new features …” | A link to the [readiness](../component-readiness.md) row |
| [docs/time-contract.md](../time-contract.md) | reference | 1 | 289 | 289: “… a Zephyr image or run on a board.” | A link to the [readiness](../component-readiness.md) row |
| [docs/tls-certificate.md](../tls-certificate.md) | reference | 5 | 3, 7, 41, 44, 509 | 3: “… has passed. Nothing here ran on a board. The evidence of #190 …” | A link to the [readiness](../component-readiness.md) row |
| [docs/web-assets.md](../web-assets.md) | reference | 1 | 5 | 5: “… of #220. Nothing here ran on a board, and #189's own image …” | A link to the [readiness](../component-readiness.md) row |
| [docs/web-contract.md](../web-contract.md) | reference | 1 | 3 | 3: “… #184. Nothing here has run on a board. #184's own image uses …” | A link to the [readiness](../component-readiness.md) row |
| [docs/web-management-apis.md](../web-management-apis.md) | reference | 2 | 3, 7 | 3: “… #187. Nothing here has run on a board. #187's own suites are …” | A link to the [readiness](../component-readiness.md) row |
| [docs/web-session.md](../web-session.md) | reference | 6 | 3, 5, 24, 112, 313 | 3: “… #186. Nothing here has run on a board. #186's own test image …” | A link to the [readiness](../component-readiness.md) row |
| [tests/README.md](../../tests/README.md) | reference | 2 | 290, 294 | 290: “… on mutated copies (each frozen Crux header, each Zephyr header class, composition” | A link to the [readiness](../component-readiness.md) row |
| [tests/consumer_system/README.md](../../tests/consumer_system/README.md) | reference | 2 | 10 | 10: “Status: Experimental (the symbol it uses is Experimental, ADR-0001 …” | A link to the [readiness](../component-readiness.md) row |
| [docs/architecture.md](../architecture.md) | explanation | 20 | 65, 117, 119, 121, 152, 314, 324, 325, 330, 331, 334, 335, 336 | 65: “… November 2026; Queue was frozen too, then removed on 20 November 2026): …” | A link to the [readiness](../component-readiness.md) row |
| [docs/boot-overview.md](../boot-overview.md) | explanation | 5 | 5, 27, 46, 59, 66 | 5: “… No boot experiment has run on any board: no signed image has …” | A link to the [readiness](../component-readiness.md) row |
| [docs/secure-boot-and-update-review.md](../secure-boot-and-update-review.md) | explanation | 9 | 5, 6, 93, 95, 97, 171, 202 | 5: “… No boot experiment has run on any board: no signed image has …” | A link to the [readiness](../component-readiness.md) row |
| [docs/secure-boot-verification-ladder.md](../secure-boot-verification-ladder.md) | explanation | 6 | 5, 47, 48, 97, 107 | 5: “… No boot experiment has run on any board (see the boot overview), …” | A link to the [readiness](../component-readiness.md) row |
| [docs/secure-management-review.md](../secure-management-review.md) | explanation | 4 | 5, 92, 174, 209 | 5: “… the management stack has run on a board. Every result is a …” | A link to the [readiness](../component-readiness.md) row |
| [docs/sftp-design.md](../sftp-design.md) | explanation | 1 | 285 | 285: “… test Access ports. Nothing ran on a board. The record, with every …” | A link to the [readiness](../component-readiness.md) row |

Hand-found, without a marker word:

| Page | Line | Quote | Target |
| --- | --- | --- | --- |
| `README.md` | 11 | “It has not yet run on a board.” (the #543 guard has no board marker) | The readiness link already on line 15 |
| `docs/getting-started.md` | 3, 108 | “It has not yet been run on WSL2 or on native Linux.” | Readiness, or a tested-environments row there |
| `docs/README.md` | 3 | “Each page states its own status at its top” | Rule 4 of the guidelines: only non-current types carry a status line |

### (e) Detail level wrong for the page type

| # | File and line | Quote | Finding | Proposed target |
| --- | --- | --- | --- | --- |
| E1 | `docs/README.md:22` | “Migrating an existing controller product (for example a PLC runtime…” | An entry page carries a migration walkthrough with lifecycle and evidence detail | A how-to for migrating a product, linked from the map |
| E2 | `docs/README.md:123`–`148` | “Decision codes (P3, R4, O4, D10, I5, Q2 ...)” | A 22-row glossary with decision codes, the owner role and agent files on the entry map | A reference glossary page; the map links it |
| E3 | `docs/getting-started.md:33`, `:59`–`83`, `:108` | “The Dev Container mounts the parent folder of the repository” | Container mount internals, a download table and debug-probe scripts on the entry set-up page | Build guide and a debugging how-to; the layout branch reworks this page |
| E4 | `docs/management-in-a-product.md:134`–`167`, `:217`, `:247` | “Kconfig” | A 400-line how-to holds full reference tables (Kconfig, routes, errors) | Reference pages; the guide keeps its steps (`:53`–`115`) |
| E5 | `docs/product-composition.md` (552 lines) | “Who owns what” | See A9: a newcomer starting a product reads release and SBOM detail first | Split by task |
| E6 | `tests/README.md` (1090 lines) | “Test organisation” | Per-suite detail for every component in one guide | Overview plus per-suite READMEs |
| E7 | `docs/architecture.md:316`–`353` | “Current capability integration” | The explanation page carries a capability inventory with status and evidence per row | Readiness for status; contract pages for capabilities; the explanation keeps the structure |
| E8 | `docs/build.md:161` | “Complete Time and Thread example” | The complete consumer example uses a frozen component and says it is not a model | An example with a component that is not frozen |
| E9 | `docs/board-image-profiles.md:108`–`304` | “Is the product session's reading right?” | Review narrative and capture design in depth on a reference page | Record of the capture change; the reference keeps the profile fields |
| E10 | `docs/README.md:47`, `:63`, `:69` | “Nothing in the boot path has run on a board.” | The map restates evidence limits per section | One link to readiness |
| E11 | `docs/first-hour.md:117`–`190` | “Kconfig options (CONFIG_...) select features and values.” | The tutorial's step 7 explains three build mechanisms in reference depth (merge order table) | Keep the three exercises; move the merge-order table to `docs/build.md`. Re-check on `docs/tutorial.md` after the layout branch |
| E12 | `templates/product/README.md:3` | “This template moved from samples/product_template to templates/product on 9 November 2026.” | The first line of the template's guide is a change notice | Release notes or `docs/history/` |

## Prioritised fix plan

Each batch is one small pull request. The order follows reader impact: what a newcomer and a product team read first comes first. Every batch lowers the allowlist entries of the pages it fixes in the same pull request.

| Batch | Pages | Findings | Size |
| --- | --- | --- | --- |
| 1. Entry pages, after #543 and the layout branch merge | `README.md`, `docs/README.md`, `docs/getting-started.md`, `docs/tutorial.md` | b (docs/README rows, hand rows), C1, C4, C5, d (docs/README, README:11, getting-started), E1, E2, E3, E10, E11 | Small to medium; the glossary and the migration how-to (E1, E2) may each need a new page |
| 2. Product guides | `docs/product-composition.md`, `templates/product/README.md`, `docs/porting-to-a-new-board.md`, `docs/writing-a-product-driver.md`, `docs/shared-hardware-modules.md`, `docs/vendor-kits.md`, `docs/build.md` | b and d rows of these pages, C2, C3, C9, C12, E5 (split only if the owner wants it now), E8, E12 | Medium |
| 3. Secure management guide | `docs/management-in-a-product.md` and the Kconfig reference | A5, C8, C13, E4, its d row | Medium |
| 4. The status-line template of the management-stack pages | the 22 A1 pages | A1, their b and d rows | Large but mechanical; can go in two halves (web pages, then the others) |
| 5. Older contracts | `thread-sync`, `messaging-contract`, `configuration-contract`, `file-contract`, the GPIO, I2C, SPI and serial contracts, `docs/superpowers/specs/` | A10, A13, A14, A15, their b and d rows | Medium; A10 needs an owner choice on where design alternatives live |
| 6. Explanation pages | `docs/architecture.md`, `docs/boot-overview.md`, the secure boot and management review pages | A2, C11, E7, their b and d rows | Medium |
| 7. Structure | the 50 top-level records, `docs/test-foundation-proposal.md`, `docs/board-image-profiles.md`, `docs/static-analysis-coverage.md`, `docs/ci-zephyr-shards.md` | A3, A4, A8, A11, A16, E9 | Needs an owner decision first (a `docs/records/` folder or not), then moves with link updates |
| 8. Test and sample READMEs | `tests/README.md`, `tests/execution_runtime/README.md`, sample and web READMEs | A6, A7, A12, C9, E6, their rows | Medium |

Decisions for the owner before the batches start:

1. Whether records get their own folder (A8, batch 7) or stay in place with only the map changed.
2. Where a design's alternatives live once its contract is current (A10, A14, A15): in an ADR, in an explanation page, or in the original design moved to `docs/history/`.
3. Whether a CHANGELOG starts now, so that history text from batches 1, 2 and 5 has a release-notes home before the first tag; until then it goes to the contract's migration notes or `docs/history/`.

## Limits of this audit

- The lexical scan over-reports in a few places and under-reports history written without its marker words. Two scanned rows are false positives and are marked so in their tables: `docs/logging-contract.md:38` ("previously pending SIGPIPE" is signal behaviour) and `docs/management-glossary.md:3` (evidence records are frozen, not a component). Their markers stay in the allowlist so that the check does not fail on them. Other rows hold a mix of real and false markers (for example a URL anchor such as `#frozen-then-removed-gpio-i2c-and-spi`); each row was read, but not every marker was judged one by one, and a fix batch re-reads its pages.
- The audit was made at the revisions named under Scope. Pull request #538, merged into `main` afterwards, moved lines of `docs/product-composition.md` and added one more `history` marker there (`no longer`, line 426 at `main` `5784e253`); the allowlist records it, so that page's entry is 3, not the 2 its row shows.
- Some current-state pages open with a status block that has no marker word (for example `docs/boot-composition.md:3`); rule 4 applies to them, but the scan does not see them.
- Group (c) covers duplicated commands found mechanically and facts found by reading the entry, product and contract pages; it is not a complete search for every repeated sentence.
- No page of the typed folders (decisions, plans, history, evidence, research) was audited for content: their type allows dated text.
