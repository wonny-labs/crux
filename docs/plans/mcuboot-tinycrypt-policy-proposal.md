# MCUboot's bundled tinycrypt under the cryptographic dependency policy: a proposal

| Field | Value |
| --- | --- |
| Status | **Proposed.** Five numbered decisions, each **Open (proposed)**. Nothing in this file is adopted, and no owner approval is recorded for any of it. |
| Date | 15 November 2026 |
| Baseline | `origin/main` at `6c246d1367def5e0abcaf83127df054707f90f0c` |
| Author | Claude Code, model `claude-sonnet-5-5`. Independent review: see the pull request |
| Origin | The open follow-up of the owner's decision D9 of 15 November 2026 (MCUboot keeps its bundled tinycrypt in the M8 composition, PSA is not adopted): the [plan's D9 row](secure-boot-development-plan.md#6-decisions-the-owner-needs-to-make) and [sections 5 and 6 of the size comparison](mcuboot-crypto-backend-comparison.md) name the open follow-up, a dependency review of the vendored copy that no Crux policy covers yet |
| Scope | Documentation only. This file adds no code, check, Kconfig symbol or `west.yml` change, edits no existing file, opens no issue and needs no hardware, key or tag. It reopens no decision: D9 stays as the owner decided it |

**Labels.** **Verified on pinned source** means read from a file of the MCUboot repository at the revision Crux pins (`6d3b3d2c38ab20c242e5b9abb04d050086383eb2`, MCUboot v2.4.0), with `gh api` on 15 November 2026. **Verified in repository** means read in this repository at the baseline. **Verified by build** appears only where a cited record states a CI result and means that record's claim, which I did not re-run. **Verified (public page)** means read from a public page or API response on 15 November 2026, named in the row. **Inference** is my reading. **Not verified** means no read or run exists. No build, `west` command, test or hardware run was made for this file (see [What was run](#what-was-run)).

## Summary

- **tinycrypt is not a Crux pin.** It is a vendored copy inside MCUboot (`ext/tinycrypt`, version file `0.2.8`), compiled into the bootloader for ECDSA P-256 verification and SHA-256. [ADR-0006](../decisions/0006-cryptographic-dependency-policy.md) and the [dependency review guide](../dependency-review.md) cover pins in `west.yml` and name MCUboot only as a candidate for the same review. They say nothing about a crypto copy that sits inside a pinned dependency.
- **Its upstream is archived.** `intel/tinycrypt` is archived on GitHub, its last push was 5 March 2024 and its last tag is `v0.2.8` (2017). MCUboot's copy also carries MCUboot's own commits, including a 2020 CTR-mode change, so it is not necessarily that tag byte for byte. A fix reaches Crux only if MCUboot makes it.
- **The real channel for tinycrypt issues is MCUboot's advisories, and it fired this week.** MCUboot published eight security advisories on 12 and 13 November 2026, seven of them list v2.5.0 as the patched version and one (a medium serial-recovery advisory) lists none. Crux pins v2.4.0. One of them names MCUboot's tinycrypt AES-CTR glue (encrypted images only). None of them was assessed for Crux's configuration: that is the first use of the policy proposed here, and it is a separate task.
- **Recommended shape (all Open):** classify tinycrypt and the vendored ASN.1 parser as *bundled crypto copies of a pinned dependency*, covered by the dependency review of MCUboot and owned through the MCUboot pin (T1). Watch MCUboot's advisories, and revisit D9 on four named triggers (T2). Have a product record the MCUboot revision, the resolved crypto settings and the advisories it reviewed (T3). Keep PSA over the Mbed TLS pair as the named exit, with its measured sizes and the boot-time measurement that does not exist yet (T4). Change no ADR text. Record the policy in the guide, and decide a rule for moving the MCUboot pin that ADR-0006 does not give (T5).

## 1. Facts

### 1.1 tinycrypt in the pinned MCUboot tree

| # | Fact | Source | Label |
| --- | --- | --- | --- |
| F1 | tinycrypt is vendored as a directory, `ext/tinycrypt`, with `lib/source`, `lib/include`, a `LICENSE`, a `README` and a `VERSION` file that reads `0.2.8`. The repository's `.gitmodules` lists no tinycrypt entry, so it is not a submodule | `gh api repos/zephyrproject-rtos/mcuboot/contents/ext/tinycrypt?ref=6d3b3d2c...` and `.gitmodules` at the same revision | Verified on pinned source |
| F2 | A second vendored directory, `ext/mbedtls-asn1`, holds `asn1parse.c` and `platform_util.c`. Its README says it bundles the ASN.1 parser of Mbed TLS so that tinycrypt-based EC crypto works for operating systems that do not bundle Mbed TLS. It states no upstream version | `ext/mbedtls-asn1/README` at the pin | Verified on pinned source for the text. The upstream version is **Not verified** |
| F3 | For ECDSA P-256 with the tinycrypt backend the Zephyr build compiles four tinycrypt files: `ecc.c`, `ecc_dsa.c`, `sha256.c` and `utils.c`. When the backend is not PSA, Mbed TLS is not built in and `CONFIG_BOOT_KEY_IMPORT_BYPASS_ASN` is off, it also compiles the two ASN.1 files of F2 | `boot/zephyr/CMakeLists.txt:34-36` and `:164-189` at the pin | Verified on pinned source for the build rules. That the Crux build compiles the ASN.1 files is an **Inference**: the job log was not read for them |
| F4 | The AES, CTR, HMAC and ECDH files of tinycrypt are compiled only for encrypted images (`CONFIG_BOOT_ENCRYPT_EC256` or `CONFIG_BOOT_ENCRYPT_X25519`). The separate `ext/tinycrypt-sha512` copy is compiled only for Ed25519 | `boot/zephyr/CMakeLists.txt:224-283` at the pin | Verified on pinned source |
| F5 | tinycrypt is the default ECDSA backend: `BOOT_ECDSA_IMPLEMENTATION` defaults to `BOOT_ECDSA_TINYCRYPT`. The alternatives are `BOOT_ECDSA_MBEDTLS`, `BOOT_ECDSA_CC310` and `BOOT_ECDSA_PSA` | `boot/zephyr/Kconfig:315-333` at the pin | Verified on pinned source |
| F6 | Crux's composition builds MCUboot with tinycrypt (51,668 B image) and the comparison record measured the alternatives. The board file sets no image-encryption, backend or serial-recovery symbol | [comparison record, section 3](mcuboot-crypto-backend-comparison.md), the board's `mcuboot.conf` under `zephyr/boot/boards/` | Verified in repository for the file and the build result. That the symbols are therefore off is an **Inference**: the Kconfig defaults of encryption and serial recovery were not read, and I read no resolved `.config` of the bootloader |
| F7 | The licence texts at the pin read as BSD: the `LICENSE` of `ext/tinycrypt` carries Intel's 2017 three-clause text and a second BSD notice for the micro-ecc code of Kenneth MacKay, and the `ecc_dsa.c` header carries the MacKay notice. GitHub's API reports no SPDX identifier for the archived upstream (`NOASSERTION`) | `ext/tinycrypt/LICENSE`, `ext/tinycrypt/lib/source/ecc_dsa.c` at the pin; `gh api repos/intel/tinycrypt` | Verified on pinned source for the texts. This is a reading, not a licence review |
| F8 | MCUboot's own history for `ext/tinycrypt` at the pin has seven commits: the imports of v0.2.6 and v0.2.8 (September and October 2017), build-system changes, and "ext: tinycrypt: update ctr mode to stream" (25 November 2020). So the copy is v0.2.8 plus at least that change, not necessarily the upstream tag byte for byte | `gh api 'repos/zephyrproject-rtos/mcuboot/commits?path=ext/tinycrypt&sha=6d3b3d2c...'` | Verified for the commit list. The diffs were **not read** |
| F9 | Zephyr's own manifest at `v4.4.2` has no tinycrypt project, so there is no Zephyr module for Crux to follow. The copy moves only with MCUboot | Zephyr `west.yml` at `v4.4.2`, searched for "tinycrypt", no match | Verified (public page) |
| F10 | No Crux source includes or links tinycrypt. The files that mention the word are the comparison script, its configuration fragments and test, and documents | `grep -rIl -i tinycrypt` over the tree at the baseline, excluding `.git` and `.claude` | Verified in repository |
| F11 | Crux pins MCUboot in the optional group `crux-boot`, at the revision of Zephyr's own manifest at Crux's Zephyr tag (`west.yml` comment). It is Apache-2.0 | `west.yml:29-38`, [product composition guide, Composition](../product-composition.md#composition) | Verified in repository |

### 1.2 The upstream project and what is published about it

| # | Fact | Source | Label |
| --- | --- | --- | --- |
| U1 | `intel/tinycrypt` is **archived**. Default branch `master`, last push 2024-03-05. Its tags end at `v0.2.8` (released 2017-08-29) | `gh api repos/intel/tinycrypt` (`archived: true`, `pushed_at`), tags and releases endpoints | Verified (public page) |
| U2 | The repository lists no published security advisory (the advisories endpoint returned an empty list) | `gh api repos/intel/tinycrypt/security-advisories` | Verified (public page) |
| U3 | A keyword search for "tinycrypt" in the NVD CVE API returned exactly one record: CVE-2026-128091, published 2026-11-13. It concerns MCUboot's tinycrypt AES-CTR backend (see U4), not the tinycrypt source | `https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=tinycrypt` | Verified (public page) for the one result. That no other CVE concerns tinycrypt is **Not verified**: a keyword search is not a search by product identifier, and an archived upstream may not have been assigned any |
| U4 | MCUboot advisory GHSA-wx3x-935q-6rcf (CVE-2026-128091, severity low): in builds with the tinycrypt backend and encrypted images, `bootutil_aes_ctr_drop()` in `boot/bootutil/include/bootutil/crypto/aes_ctr_tinycrypt.h` was an empty stub, so the AES key schedule was not cleared. Affected `>= 1.3.0, <= 2.4.0`, patched `2.5.0`. The defect is in MCUboot's glue code, not in tinycrypt's library files | `https://github.com/mcu-tools/mcuboot/security/advisories/GHSA-wx3x-935q-6rcf`, read through the repository's advisories API | Verified (public page) |
| U5 | MCUboot published seven more advisories on 12 and 13 November 2026, none about tinycrypt: GHSA-8rcq-2mgr-fhp8 (CVE-2026-16664, medium, serial-recovery slot index, `>= 2.0.0`, no patched version listed), GHSA-vj6q-r752-fpqv (CVE-2026-16671, low, split-image validation with SHA-384 or SHA-512), GHSA-779w-4x76-5chf (CVE-2026-16662, low, measured-boot record), GHSA-777r-3chm-p78c (CVE-2026-16659, medium, serial-recovery upload with encrypted images), GHSA-4fp3-3qw2-25jv (CVE-2026-127915, low, TLV iterator, described as affecting all configurations), GHSA-hqmg-jwp9-8cf8 (CVE-2026-127928, low, image key left on the stack in serial recovery), GHSA-c7cx-5pqv-x9m6 (CVE-2026-127916, low, image hash span). Except the first, each lists `2.5.0` as the patched version (the affected ranges end below 2.5.0, or at 2.4.0). Severities are the ones the advisory pages carry | `gh api repos/mcu-tools/mcuboot/security-advisories` | Verified (public page) for the list. The reach into Crux's build is **not assessed** |
| U6 | MCUboot's `v2.5.0` tag (annotated, dated 2026-10-22) points to `725d63c9d5bc1bb572d802e7a768daf504186daf`. Crux's pin `6d3b3d2c` is identical to `v2.4.0` and `v2.5.0` is 202 commits ahead of it with 271 changed files in the compare. The releases API lists `v2.4.0` (2026-04-23) as the latest release | `gh api repos/zephyrproject-rtos/mcuboot/compare/...`, tag and releases endpoints | Verified (public page) |
| U7 | Zephyr pins MCUboot `6d3b3d2c` (v2.4.0) in `v4.4-branch`, and `725d63c9` (v2.5.0) in `main`, `v4.5.0` and `v4.5-branch` | Zephyr `west.yml` at each ref | Verified (public page) |

### 1.3 What the policy covers today

| # | Fact | Source | Label |
| --- | --- | --- | --- |
| P1 | ADR-0006 sets a policy for Crux's own crypto pins: the two Mbed TLS pins (option B, a security-fix path that may move them ahead of the Zephyr tag, only to revisions Zephyr pins on a release branch and within the line Crux builds) and the three wolf pins (tagged stable releases, same review). It was accepted on 14 November 2026 | [ADR-0006, section 3 and the owner's decisions](../decisions/0006-cryptographic-dependency-policy.md) | Verified in repository |
| P2 | ADR-0006 lists MCUboot, "pinned by the open PR #339", among the dependencies that would need the same review, undecided and each a decision for the owner. The guide says the same of MCUboot and one other module | ADR-0006 section 5, [dependency review guide, Scope](../dependency-review.md#scope) | Verified in repository |
| P3 | The size comparison says MCUboot's tinycrypt "is not one of those pins", that it is a vendored copy of an archived upstream project, and that "no Crux policy covers it until the dependency review that ADR-0006 mentions" | [comparison record, sections 5 and 6](mcuboot-crypto-backend-comparison.md) | Verified in repository |
| P4 | The guide's procedure (triggers, record, steps, pin base check, fix-inclusion check) is written for a Zephyr-fork module pin. Its pin base check uses `gh api .../compare` against a module's upstream tag | [dependency review guide](../dependency-review.md) | Verified in repository |
| P5 | `west crux-pins` reports a pin and not a library line or version, and the generated compatibility table shows a version only when `west.yml` carries a version comment. The `mcuboot` entry of `west.yml` has no version comment | `west.yml:33-38`, [compatibility table](../compatibility-table.md), [product composition guide, Crypto library pins](../product-composition.md#crypto-library-pins) | Verified in repository |
| P6 | The guide for products records the product's own duties for the two Mbed TLS pins (same line, own review, record the line and version, licence terms). It has nothing for a bootloader's crypto backend | [product composition guide, Crypto library pins](../product-composition.md#crypto-library-pins) | Verified in repository |

**Reading.** ADR-0006's option B is worded for pins that follow Zephyr's module revisions. tinycrypt has no pin to move, so option B's path does not apply to it. The gap is a classification and an owner, not a missing mechanism (**Inference**). A second gap is specific to MCUboot: option B allows a move only to a revision that Zephyr pins on a release branch. For MCUboot, Zephyr's `v4.4-branch` still pins v2.4.0 while the fixes of U5 are in v2.5.0, which Zephyr pins on `main` and `v4.5-branch` only (U7). Under the rule as worded for the Mbed TLS pair, Crux could not take v2.5.0 without moving its Zephyr baseline (**Inference**: the rule was written for Mbed TLS, and nobody has applied it to MCUboot).

## 2. Decisions

Each decision has a recommendation, a reason, one alternative and a status. All are **Open (proposed)**: none is adopted, and no owner answer exists for any of them. The wording of each recommendation is a proposal for the owner.

### T1. Classification of tinycrypt under ADR-0006, and who owns it

**Recommendation.** Classify tinycrypt, and the vendored ASN.1 parser next to it, as **bundled crypto copies of a pinned dependency**. Four rules would follow:

1. They are in scope of the dependency review of MCUboot (the guide's procedure, with the MCUboot pin as the subject). The review record lists which bundled files the composition compiles (F3, F4) and under which configuration (the resolved MCUboot settings, see T3).
2. Crux does not fork, patch or re-vendor them, and no Crux source includes them (F10). A defect is fixed by taking an MCUboot revision that fixes it, or by leaving the backend (T4).
3. ADR-0006's option B path (a pin move ahead of the Zephyr tag) does not apply to them directly, because there is no pin. What moves is the MCUboot pin, under T5.
4. The owner of the classification is the person who approves moves of the `crux-boot` pin: the project owner for security-sensitive pin moves, by extension of ADR-0006 Q3, which is worded for the crypto pins. The author of a review records it, and an independent reviewer checks it. Upstream has no owner to name: `intel/tinycrypt` is archived (U1), and MCUboot maintains its copy only as part of MCUboot.

**Reason.** F1 to F4 show that the copy is compiled into the bootloader that verifies every image, F10 shows that no other Crux code depends on it, and P1 to P3 show that no document classifies it. A classification costs no code and uses the procedure that exists (P4). It keeps Crux from owning archived crypto code.

**Alternative.** Treat tinycrypt as a **separate dependency with its own Crux-maintained copy**, using the vendor-branch method of the [product composition guide](../product-composition.md#modifying-third-party-code). It gives Crux control of fixes. It also makes Crux the maintainer of an archived crypto library with no upstream to follow (U1), splits the copy from MCUboot's own glue (the defect of U4 is in the glue, not in the library files) and adds a review burden for a component that the PSA exit (T4) would remove.

**Status: Open (proposed).**

### T2. How Crux learns about security issues, and when D9 is revisited

**Recommendation.**

*Monitoring.* Use MCUboot's published security advisories (`https://github.com/mcu-tools/mcuboot/security/advisories`) as the one channel for tinycrypt issues, because the upstream of tinycrypt publishes none and is archived (U1, U2) and the only record found so far arrived through MCUboot (U3, U4). At each of these events, read the list and the NVD keyword search for "tinycrypt", and note the result in the PR or issue of the event:

- a change of the `crux-boot` pin,
- a move of Crux's Zephyr baseline,
- the start of a board session for the bootloader,
- a consumer report.

Between events, the owner may subscribe to the repository's security advisories on GitHub. That is an action of the owner, and nothing here assumes it. A pin change, a baseline move and a consumer report are triggers in the sense of the guide, so a recorded dependency review follows each within 14 days if the read finds a new advisory for the pin or the backend. The start of a board session is only an occasion to read the list. The 14 days are a Crux target and not a promise to consumers (ADR-0006 Q4, the guide).

*Triggers to revisit D9.* D9 stays as decided until one of these happens, and then the owner is asked, with a review record attached:

- **R1.** An advisory affects code that the composition compiles (the four tinycrypt files and the two ASN.1 files of F3, or the glue that calls them) and the review's verdict is **applies** or **cannot tell**, and no fixed MCUboot revision is available for Crux to take within the review window.
- **R2.** MCUboot or Zephyr deprecates or removes the tinycrypt backend, or changes the default of `BOOT_ECDSA_IMPLEMENTATION`.
- **R3.** Boot-time evidence from a board exists for both backends, so that the size difference of T4 can be weighed against a measured time (the possibility that the [D9 record](secure-boot-development-plan.md#6-decisions-the-owner-needs-to-make) leaves open: revisiting when boot-time evidence from a board exists; the owner's quoted words in that row are only the approval to keep tinycrypt).
- **R4.** A product composing the bootloader needs one crypto line across bootloader and application, or needs the PSA backend for a reason of its own (for example a key store).

*First use.* The advisories of U5 are a trigger today. The first dependency review of MCUboot would take them as input, together with the pin move to v2.5.0 that they point to. That review and that move are separate tasks and need the owner's approval. This proposal does neither.

**Reason.** Monitoring needs a source that publishes. The size of the gap between the pin and the fixes (202 commits, U6) shows that the cost of not looking is real. R1 to R4 turn the open possibility of the D9 record (revisit when boot-time evidence exists) into events that can be recognised, and keep one trigger (R1) that does not wait for a board.

**Alternative.** An **automated check** that reads the advisories on a schedule and opens an issue when a published advisory lists an affected range that includes the pin. It removes the dependence on someone looking. It needs a new workflow and network access (a protected path under `.github/`), it shares the GitHub API limit with every other session and job, and it fires on advisories that the review would call not applicable. It could follow once the manual path has run twice, in the way ADR-0006 Q3 treats routine delegation.

**Status: Open (proposed).**

### T3. What a product that composes MCUboot must record

**Recommendation.** A product that builds the bootloader records these items in its release record, next to the crypto line record that the [product composition guide](../product-composition.md#crypto-library-pins) already asks for:

1. **MCUboot revision.** The commit and the version, and whether it is Crux's pin or an override declared with `crux-override`, with the advisory as the reason.
2. **Resolved bootloader settings** that decide which advisories apply: the ECDSA backend symbol (`BOOT_ECDSA_TINYCRYPT`, `BOOT_ECDSA_PSA`), the signature type, whether any image-encryption symbol is on, whether serial recovery is on. The resolved `.config` of the MCUboot image is the source (F6: none was read).
3. **The bundled copies compiled**, by name and version as the pinned tree shows them (tinycrypt `0.2.8` as the `VERSION` file at `6d3b3d2c`, with MCUboot's own changes to it, F8, covered by the MCUboot revision) and the ASN.1 parser. With the PSA backend, the Mbed TLS and TF-PSA-Crypto revisions instead, by the pin base check of the guide.
4. **Advisories reviewed** since the last release: identifier, verdict (applies, no, cannot tell), date and the link to the review record.
5. **The bootloader version** in the boot-result record, as the plan's M9 text already declares.

A generated SBOM does not make items 2 and 3 visible (**Inference**): a bundled copy inside a module is part of that module's package, and the SBOM notes in the guide describe only module-level and file-level data. The product adds them by hand until a generator carries them.

**Reason.** The backend and the encryption setting decide which of U4 and U5 apply, and a version number alone does not show them. A product that overrides the pin owns its own evidence (ADR-0006, section 3), so it must be able to say what it shipped.

**Alternative.** Record **only the MCUboot version**. It is the least work and it is what `west crux-pins` and the compatibility table can show. It does not tell a reader whether the encrypted-image path of U4 is in the build, so every advisory would have to be treated as "cannot tell" (and a "cannot tell" is a defer, never a silent not applicable).

**Status: Open (proposed).**

### T4. The exit path from tinycrypt

**Recommendation.** Name **PSA Crypto over Zephyr's Mbed TLS pair** (`BOOT_ECDSA_PSA`, the pins of ADR-0006) as the exit path, to be taken only on R1, R2 or R4 of T2, or on the owner's decision after R3. Do not prepare it beyond what the comparison record already holds. The measured facts:

| | tinycrypt (M8 composition) | PSA with `CONFIG_MBEDTLS=y` and `CONFIG_MBEDTLS_PSA_CRYPTO_C=y` |
| --- | --- | --- |
| Bootloader image `zephyr.bin` | 51,668 B | 69,620 B |
| Headroom in the 128 KiB partition | 79,404 B | 61,452 B |
| Difference | | +17,952 B flash (+34.7 %), +1,920 B RAM (14,656 B to 16,576 B) |
| Builds at the pinned revisions | yes | only with the two settings above, which MCUboot's option does not select |
| `BOOT_ECDSA_MBEDTLS` (legacy Mbed TLS API) | does not configure at the pins with the settings tried | |
| Boot time | **Not measured** | **Not measured** |

Source: the [comparison record](mcuboot-crypto-backend-comparison.md), sections 3 and 4 (**Verified by build** for the sizes, in a CI run that the record names). The sizes date from the Mbed TLS pair at the earlier pins (`a3e190fe`, `dc575a2d`). The pair moved to the 4.1.1 and 1.1.1 revisions on `main` afterwards (#416), and **no PSA variant was rebuilt on the new pair** (**Not verified**: the sizes may differ).

*What is still missing before the exit could be executed, none of it done here:*

- **The boot-time measurement.** It needs a board and a task-specific hardware approval (`AGENTS.md`). The proposed order is: first, the time that verification takes with tinycrypt, taken in the first approved board session for the M8 composition; then the same image built with the PSA backend, in a session that is approved on its own.
- **Whether the PSA build boots** at all on the target (ROM acceptance of the image, PSA core initialisation, entropy), which the record lists as Not verified.
- **The entropy glue.** The PSA build uses Zephyr's `zephyr_entropy.c` unpatched, while Crux replaces that file with a fail-closed copy in the management images (ADR-0006, section 1). Which one the bootloader uses is a decision.
- **Working memory for ECDSA in the PSA core** (heap and stack), which the record did not examine.
- **The group coupling.** The Mbed TLS pair is in the opt-in group `crux-secure-management`, which also holds GPL stacks. A bootloader build that uses PSA needs the two projects without the rest, as the comparison script fetches them by name. How a product consumes that is the product composition guide's group question (**Inference**).
- **The MCUboot revision.** The record's PSA settings were found at v2.4.0. Whether the same settings hold at v2.5.0 is **Not verified**.

**Reason.** PSA is the one alternative that built, it sits under ADR-0006's existing security-fix path, and it gives one crypto line for bootloader and application. Its cost is known in size and unknown in time. Naming the exit and its missing evidence now means that a trigger does not start a new investigation.

**Alternative.** **No planned exit.** Stay on tinycrypt until MCUboot removes the backend, and accept MCUboot's advisories as the only fix source. It needs no work and keeps the smallest image. It leaves Crux with no answer when R1 fires and no fix is available, and ties the bootloader's crypto to a backend whose upstream is archived (U1).

**Status: Open (proposed).**

### T5. What ADR-0006 would need to change

**Recommendation.** **No change to the text of ADR-0006.** An accepted record is not rewritten (the [decision records convention](../decisions/README.md#convention)), and ADR-0006 already marks MCUboot as a candidate for the review, each a decision for the owner. Instead, if the owner accepts T1 to T4:

1. Record the classification of T1, the triggers of T2 and the product record of T3 in ordinary maintained documents: the scope paragraph of [`docs/dependency-review.md`](../dependency-review.md) and the crypto section of [`docs/product-composition.md`](../product-composition.md). Neither is a protected path.
2. Decide, in the same owner answer, the **target rule for moving the MCUboot pin**, which ADR-0006 does not give. The proposal: a move to an MCUboot release tag of the same major line that fixes an advisory the review found to apply (or could not rule out), after the recorded review, the independent reviewer and the owner's approval (ADR-0006 Q3 applies to the first two moves). That departs from option B item 1, which allows only a revision that Zephyr pins on a release branch. It is needed because of the gap in section 1.3: the fixes listed for seven of the U5 advisories are at a revision that Zephyr's `v4.4-branch` does not pin. One advisory (GHSA-8rcq-2mgr-fhp8) lists no patched version, so a move to v2.5.0 is not shown to close it. The alternative target, waiting for Zephyr's baseline, is tied to Zephyr's tag cadence, the problem ADR-0006 section 2.3 measured for the Mbed TLS pair.
3. Close the open follow-up of the D9 row with a pointer to the owner's answer, when there is one.

**Reason.** ADR-0006's decisions are about two pins and three wolf pins. T1 to T4 add a class of dependency and a rule for a third pin, and neither contradicts an accepted decision. The gap in item 2 is a real difference between MCUboot and the Mbed TLS pair (U7), so it needs its own answer.

**Alternative.** A **short new ADR** (ADR-0007) that amends ADR-0006 and states the bundled-copy class and the MCUboot target rule as policy. It makes the rule citable and keeps the numbered record complete. It costs a record for a rule that one dependency uses, and the convention keeps contract-level decisions out of ADRs.

**Status: Open (proposed).**

## 3. What is not decided or not verified

- Whether any of the advisories of U4 and U5 applies to Crux's composition. The M8 configuration appears to leave encrypted images off (F6, **Inference**), which would exclude the advisories that name encrypted images (U4 and two serial-recovery ones), but the other five were not read against the configuration, and the TLV iterator advisory is described as affecting all configurations. GHSA-8rcq-2mgr-fhp8 has no patched version listed, so its status after a move to v2.5.0 is open.
- Whether the pin move to v2.5.0 builds and keeps the M8 build evidence (the 51,668 B figure, the signed image checks). Nothing was built.
- The contents of MCUboot's changes to `ext/tinycrypt` (F8) and the upstream version of `ext/mbedtls-asn1` (F2).
- Whether another CVE concerns tinycrypt itself (U3).
- Zephyr's `v4.5.0` and later behaviour with Crux, beyond the MCUboot revision it pins (U7).
- Boot time of either backend, and that the PSA build boots (T4).
- Any licence conclusion (F7 is a reading of the texts).
- Hardware: nothing here ran on a board.

## 4. Follow-up changes

None is part of this proposal. Each would be its own reviewed change after the owner decides.

| Change | Needed by | Protected path |
| --- | --- | --- |
| The scope paragraph of `docs/dependency-review.md` (bundled copies, the MCUboot pin as subject) | T1, T2, T5 | No |
| A bootloader crypto record in `docs/product-composition.md` | T3 | No |
| The first dependency review of MCUboot, taking the advisories of U5 as input, as a record under `docs/` | T2 | No (a new file) |
| A move of the `crux-boot` pin to v2.5.0, with the evidence of a pin move | T5 | `west.yml` is not on the protected list. Security-sensitive, so the owner's approval of the move itself |
| A resolved `.config` of the MCUboot image kept as evidence, so T3 can be answered from a file | T3 | A new file under `docs/evidence/` may be added within a task. A change to a check script or workflow is protected |
| A scheduled advisory check | T2 alternative | Yes, `.github/` |
| A short ADR amending ADR-0006 | T5 alternative | No (a new file) |
| Boot-time measurement on a board | T4 | Hardware approval for the task. Not covered by anything here |

## 5. Follow-up issue text (ready to post, not posted)

Title: **Bring a bootloader's bundled crypto copies under the cryptographic dependency policy**

Body:

> **Context.** The bootloader that Crux composes (MCUboot, optional group `crux-boot`) verifies image signatures with a copy of the tinycrypt library that is vendored inside MCUboot's tree. The upstream project of that library is archived and publishes no advisories. MCUboot keeps the copy and publishes its own advisories, eight of them on 12 and 13 November 2026, seven of which list MCUboot v2.5.0 as the patched version (one lists none), while Crux pins v2.4.0. ADR-0006 and the dependency review guide cover the Mbed TLS and wolf pins and name MCUboot only as a candidate for the same review. The decision to keep tinycrypt for the first boot composition is recorded in the secure boot plan (D9). It left one follow-up open: a policy for the vendored copy.
>
> **Proposal.** `docs/plans/mcuboot-tinycrypt-policy-proposal.md` has five decisions, all open: classification and owner (T1), monitoring and revisit triggers (T2), what a product records (T3), the exit path (T4) and the effect on ADR-0006 (T5).
>
> **Wanted.** An owner answer on T1 to T5, as recommended or with changes. Then, as separate tasks, each with its own approval: record the decision in `docs/dependency-review.md` and `docs/product-composition.md`; run the first dependency review of MCUboot with the eight advisories as input; decide the move of the `crux-boot` pin to v2.5.0.
>
> **Not in scope.** Any change of the D9 decision, any hardware operation, key or tag. The boot-time measurement of T4 needs its own hardware approval.
>
> **Done when.** The owner's answer is recorded, the guide and the product guide state the rules that were accepted, and the first review of MCUboot exists as a record with a verdict for each advisory.

## What was run

On native macOS, in a git worktree at `6c246d13`: `git fetch`, reads of the files cited above, `grep`, and read-only `gh api` and `curl` calls against public GitHub and the public NVD API on 15 November 2026 between about 22:55 and 23:00 UTC (contents, commits, compare, tags, releases and advisories endpoints of the MCUboot, tinycrypt and Zephyr repositories). No repository content or private context was sent. Not run: `west`, any build, `native_sim`, any test, any hardware command. The documentation link check runs in CI. `docs/plans/` is excluded from it, but the links of this file were checked by hand against the tree.

## Record

| Item | Value |
| --- | --- |
| Baseline | `6c246d1367def5e0abcaf83127df054707f90f0c` |
| Model | `claude-sonnet-5-5`, Claude Code |
| Skills and agents | None beyond the repository's own guides. The review is by the `reviewer` agent (read-only, Opus), result in the pull request |
| Approval | None. This file is a proposal under the task that asked for it. Every decision in it is Open (proposed) |
