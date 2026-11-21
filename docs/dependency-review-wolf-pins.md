# Dependency review: the wolfSSL, wolfSSH and wolfPSA pins

Status: **review record, a use of the [dependency review guide](dependency-review.md)** after the [Mbed TLS record](dependency-review-mbed-tls-4.1.1.md) and the FatFs review (PR #420), 14 November 2026. Baseline: `origin/main` at `7e0a31a4`. Author: the change author. Under [ADR-0006](decisions/0006-cryptographic-dependency-policy.md) (accepted 14 November 2026), Q7: whether newer tagged stable releases or advisories matter to the wolf pins.

This record is documentation only. It moves no pin and edits no `west.yml` and no protected path. It decides nothing about licences: the licence facts below are constraints taken from existing documents.

**Labels.** **Verified** means I read it with `gh api` and cite the source, or I read it at the baseline revision and cite `path:line`. **Reported** means a page says it, as read through a fetch agent on 14 November 2026, and I did not check it independently. **Inference** is my reading. **Not verified** means no read or run for it.

## Result

- **Verdict: no pin move. Nothing is newer to take.** On 14 November 2026 each pinned release is the newest stable tag of its repository: wolfSSL `v5.9.4-stable`, wolfSSH `v1.6.0-stable` and wolfPSA `v5.9.4`. Each pin equals its tag's commit.
- **No published vulnerability entry is fixed after the pinned version.** The wolfSSL vulnerability page lists 11 entries fixed in 5.9.4 and 31 fixed in 5.9.2, and none fixed later. The wolfSSH release notes list five 2026 entries fixed in 1.6.0 and one under 1.5.0, none later. wolfPSA lists none. **For wolfSSH and wolfPSA that means only that no later release exists**: their sources are release pages, which cannot list a fix later than the newest release, and the one source that could (the vendor page's wolfSSH table) was read only as a summary. **So the pins hold the fixes those pages list, as far as their fixed-in versions are right (Reported) and a release tag holds the fixes listed for it (Inference; one fix commit was tested).**
- **Unreleased work exists and cannot be assessed.** `master` is 2328 commits ahead of the wolfSSL pin, 191 ahead of wolfSSH and 59 ahead of wolfPSA. wolfSSL's `ChangeLog.md` has an "unreleased" section whose bullets name no CVE. That is a watch item, not a finding.
- **What this does not show:** whether any listed entry reaches Crux's wolf configuration. It does not need to for a pin move, because no candidate revision exists (and, as far as the pages are right, the pins hold the listed fixes). It is not an assessment of Crux's use of the wolf stacks.
- **Not established:** the complete text of the wolfSSL vulnerability page (part of it was read as a summary), the dates of its entries (the page has none), and the diffs of any fix.

## 1. Subject

| Item | Value | Status |
| --- | --- | --- |
| Pins | `wolfssl` `3c5eead44904df64e6a5a1f4ebdce377d35a849a` (`v5.9.4-stable`), `wolfssh` `8221e4ee48c93da6cea3325a91de2ecc00ae5f56` (`v1.6.0-stable`), `wolfpsa` `55ae0ec58cd2ef4c528f44e8466095550c16ca8a` (`v5.9.4`). All three are in the opt-in group `crux-secure-management` | Verified: `west.yml:40-58` |
| Pin equals the tag commit | wolfSSL, wolfSSH and wolfPSA: yes, each | Verified: `gh api repos/wolfSSL/<repo>/git/ref/tags/<tag>` and `…/git/tags/<sha>` where the ref is an annotated tag, 14 November 2026 |
| Newest releases | wolfSSL `v5.9.4-stable`, wolfSSH `v1.6.0-stable`, wolfPSA `v5.9.4`. Dates: the release titles say 25 September, 6 October and 1 October 2026, and the GitHub `published_at` field says 27 September, 6 October and 1 October 2026 (wolfSSL's 5.9.2: title 23 June, `published_at` 25 June). ADR-0006 section 2.4 gives the `published_at` dates. Both are right for the field they read. The 5.9 stable tags are 5.9.0, 5.9.1, 5.9.2 and 5.9.4. There is no tag for a later stable | Verified: `gh api repos/wolfSSL/<repo>/releases` and `…/git/matching-refs/tags/v5.9` |
| Default branches | `master`, ahead of the pins by 2328 (wolfSSL), 191 (wolfSSH) and 59 (wolfPSA) commits, `behind_by` 0. Last commits 14, 13 and 13 November 2026 | Verified: `gh api repos/wolfSSL/<repo>/compare/<pin>...master` and `…/commits?per_page=1` |
| Sources read | <https://www.wolfssl.com/docs/security-vulnerabilities/>, <https://github.com/wolfSSL/wolfssh/releases>, <https://github.com/wolfSSL/wolfPSA/releases>, <https://raw.githubusercontent.com/wolfSSL/wolfssl/refs/heads/master/ChangeLog.md>, and the GitHub security advisory pages of the three repositories, all on 14 November 2026 | Reported: read through a fetch agent. No source archive or proof-of-concept code was fetched or run |

## 2. What the pages list

### wolfSSL

The vulnerability page has no date per entry, so I applied the version test (fixed in 5.9.2 or later). Entries fixed in 5.9.1 or earlier are not counted here.

| Fixed in | Entries | Examples named on the page | Status |
| --- | --- | --- | --- |
| **5.9.4** | 11: CVE-2026-93302, -89102, -89136, -93304, -89133, -89134, -89135, -15442, -94417, -94418, -94419 | Trusted-peer CA matching ignores the public key (High, needs `WOLFSSL_TRUST_PEER_CERT`). RFC 6961 multiple OCSP stapling accepts a chain certificate as a CA (High). The client accepts an unsolicited raw public key (High, needs `HAVE_RPK`). Name-constraint bypasses. A TLS shutdown use-after-free (Low, default builds). OCSP plus CRL skipping the CRL check (Low) | Reported. The fix of the first, commit `22bcd51d`, is an ancestor of the pin: `gh api repos/wolfSSL/wolfssl/compare/22bcd51d...3c5eead4` returns `ahead`. **Verified** for that one commit |
| **5.9.2** | 31 listed as fixed in 5.9.2 (CVE-2026-11310, -11999, -55958, -55960, -55961, -10097, -6731, -6091, -6094 and others), two with a conflicting version note: CVE-2026-6681 (table 5.9.2, text 5.9.1) and CVE-2026-6679 (table 5.9.1, a changelog summary says 5.9.2) | X.509 verification in the OpenSSL-compatible layer, PKCS #7 and PKCS #12, ML-KEM comparisons, name constraints, a Renesas TSIP port, and others | Reported. The pin is `5.9.4`, later than 5.9.2, so it holds both versions' fixes if the page is right |
| after 5.9.4 | none | | Reported. The page's newest rows are fixed in 5.9.4. The page has no timestamp, and the first fetch cut one row's opening |
| Unreleased | `ChangeLog.md` has a section "wolfSSL Release (unreleased)" above 5.9.4. Its bullets name no CVE | | Reported: only the top of the raw file was read verbatim. A summary of the rest mentions further fixes with no CVE identifiers, and I do not rely on it |

### wolfSSH

| Fixed in | Entries | Component | Status |
| --- | --- | --- | --- |
| **1.6.0** (6 October 2026) | CVE-2026-16516 (Critical, ECDSA host key curve not checked), CVE-2026-83540 (High, wolfSSHd on Windows), CVE-2026-84897 (Medium, DH group exchange messages from a client), CVE-2026-81535 (Medium, forwarded-tcpip policy), CVE-2026-83742 (Medium, SFTP path handling) | host key verification, KEX, port forwarding, SFTP | Reported: the release page of 1.6.0. The pin is the 1.6.0 commit |
| 1.5.0 | CVE-2026-0930 (Low, wolfSSHd on Windows) | | Reported, listed under the 1.5.0 release |
| after 1.6.0 | none | | Reported |

Also in the 1.6.0 notes, as behaviour changes the pin already carries: strict KEX on by default, RSA user-auth keys of at least 2048 bits, the `none` cipher and MAC only with `--enable-none-cipher`, a disconnect after 6 failed authentications, `StrictModes` on, a 120 s login grace time, and `forwarded-tcpip` needing a forwarding callback.

### wolfPSA

No vulnerability entry, and no CVE in any release note. v5.9.4 (1 October 2026) has a "Security" section without identifiers: side-channel hardening and a length check in `psa_import_key`. It requires wolfSSL 5.9.2 or later (**Reported**).

### Advisory pages

The GitHub security advisory pages of wolfSSL, wolfSSH and wolfPSA are empty ("There aren't any published security advisories"). **That is not evidence of absence**: wolfSSL publishes its entries on its own page, and the wolfSSH release notes link GHSA identifiers that the repository does not show as published.

## 3. Fix inclusion and the question of a newer revision

| Question | Answer | Status |
| --- | --- | --- |
| Is there a newer stable release to move to? | No, for any of the three | Verified, section 1 |
| Does a published entry name a fix that the pin lacks? | No. Every fixed-in version on the pages is at most the pinned version | Reported, with one fix commit **Verified** as an ancestor of the pin |
| Do unreleased commits hold a published fix? | Not established. `master` is far ahead, and the pages list no entry for it | Not verified |
| Would moving to `master` follow ADR-0006? | No. Q7, accepted, is "The wolf pins follow tagged stable releases through the same review, with no coupling to Zephyr", and `master` is not a tagged stable release. Option B item 1 (a revision that Zephyr pins on a release branch) is written for the Mbed TLS pair and does not cover the wolf pins | ADR-0006 `:14,110,236` (Verified by reading) |

## 4. Crux's use, for context only

The wolf projects are in the opt-in group `crux-secure-management` and are fetched only in a workspace that enables it (`west.yml:3-7`). Crux's wolfSSH provider (`components/ssh/ports/zephyr/crux_ssh_wolf_provider.c`, `wolf-ssh.conf`) builds the pinned wolfSSH and wolfSSL, and the Wolf profile of the PSA qualification builds wolfPSA. The existing documents state the licence facts: wolfSSL and wolfPSA are **GPL-3.0-or-later** (wolfSSL's `LICENSING` adds an exception for other named software), they are used for test builds and no binary is published (`docs/upstream-reuse.md:43-44`, `docs/psa-crypto-qualification.md:281-282`), and `docs/product-composition.md:358` says the wolf projects are GPL-3.0-or-later or commercial. ADR-0006 section 4 (`:144`) says wolfSSL and wolfSSH are offered under GPL-3.0-or-later or a commercial licence and that wolfPSA's source states GPL-3.0-or-later only. The two statements differ for wolfPSA, and I decide nothing. This record decides nothing about them.

I did not assess which listed entries would reach Crux's wolf configuration. It would be needed if a future pin were older than a fix, or if the Wolf profile moves and a product ships it.

## 5. Decision of this review

- **No move: nothing to take and nothing to defer, because no candidate revision exists.** The pins are the newest stable releases. The unassessed points (applicability of each entry, unreleased `master`) are watch items, not a "not applicable" verdict, and the guide's "cannot tell is a defer" applies to them only if a candidate appears.
- **Watch items, with the event that restarts this review:**
  - the next wolfSSL stable tag (the `ChangeLog.md` already has an "unreleased" section), the next wolfSSH stable tag, or a new wolfPSA release;
  - a new row on the wolfSSL vulnerability page fixed in a version later than 5.9.4, or a wolfSSH or wolfPSA entry later than 1.6.0 or 5.9.4;
  - a decision to ship the Wolf profile in a product, or a change of Crux's wolf configuration, which makes the applicability of each entry to Crux's configuration worth assessing;
  - a consumer report;
  - the GHSA identifiers that the wolfSSH release notes link becoming published, or a vulnerability-page row whose fixed-in field names `master` or a pull request and not a version.
- **This record approves nothing.**

## Guide fields not filled, and why

| Field of the guide | Status in this record |
| --- | --- |
| Configuration read (`file:line`) | **Not read**, outside this review's question (section 4 names the files for context only) |
| Per advisory: what it needs, applies, verdict | **Not assessed.** Each entry's applicability is "cannot tell". The decision does not depend on it, because no candidate revision exists |
| Plan or evidence for a move | **None, because there is no move.** A future wolf pin move would need its own plan: the PSA Wolf profile on Host and `native_sim` (`scripts/test-psa-crypto.sh host` and `zephyr` with the wolf stacks), the wolfSSH provider and SFTP checks on `native_sim` (`docs/ssh-wolf-provider.md`), and ADR-0006 Q3's approval rule. ADR-0006 option B item 4 lists the Mbed-profile evidence and does not fit the wolf stacks as written. Neither the wolf checks nor a default workflow selects the GPL stacks today (`scripts/check-ssh-boundaries.py`), so the evidence would run locally in a workspace with the group enabled |

## What could not be established

- **The whole wolfSSL vulnerability page as text.** Rows up to about character 79874 were read verbatim, and the rest as a model summary (one row's opening was cut in the first fetch, and its fixed-in version was not read again: CVE-2026-5479, which the tail shows fixed in 5.9.1). The summary part covered older rows (fixed in 5.9.1 or earlier) and the wolfSSH table, and I did not rely on it for any claim above.
- **The dates of the wolfSSL entries.** The page has none. The release dates are the release titles and the `published_at` fields (section 1), which differ by up to two days for wolfSSL.
- **A conflict on the page and in the changelog summary** for CVE-2026-6681 and CVE-2026-6679 (fixed in 5.9.1 or 5.9.2). It does not change the result, because the pin is later than both.
- **The wolfSSH product page** says version 1.5.0 (17 April 2026), while the releases page lists 1.6.0 as the latest. I took the releases page and the tag.
- **Whether `master` holds an unpublished security fix.** The pages say nothing, and I did not read commits.
- **Fix diffs.** I read none. One fix commit's ancestry in the pin was tested.
- **Whether any entry reaches Crux's configuration** (section 4).
- **Other sources:** NVD and distribution trackers, which would list wolfSSL entries with their own dates.

## What was run

On native macOS, in the worktree at `7e0a31a4`: `gh api` against `wolfSSL/wolfssl`, `wolfSSL/wolfssh` and `wolfSSL/wolfPSA` for releases, tags, compare and the last commits. A fetch agent (`web-fetch`) read the wolfSSL pages, the wolfSSH and wolfPSA release pages, the ChangeLog and the advisory pages, because I have no direct page-fetch tool. No source archive, no GPL source and no proof-of-concept code was fetched or run. No build, no Docker, no hardware. ECC skills: none.

## Record

| Item | Value |
| --- | --- |
| Author | The change author |
| Independent review | pending |
| Approvals | none |
