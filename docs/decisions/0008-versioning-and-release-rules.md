# ADR-0008: Crux versioning and release rules

Status: **Accepted** by the owner on 25 November 2026, as recommended: O2 to O8, listed under [Decisions](#decisions). **Amends [ADR-0001](0001-application-boundary-and-api-stability.md)** 4.5 and the [Versions](../product-composition.md#versions) rule on pinned-module changes (O5). Baseline: `origin/main` at `1589d960`.

This record decides how Crux names its versions, what the version promises, when a release happens and who makes it.
The version macros are in [`<crux/version.h>`](../../components/base/include/crux/version.h).
The compatibility tiers and change rules stay in [ADR-0001 Decision 4](0001-application-boundary-and-api-stability.md#decision-4-api-stability-and-change-policy).

## Context

- Products pin Crux by full SHA, and a bot moves the pin ([Keeping the Crux pin current](../product-composition.md#keeping-the-crux-pin-current)).
- Company copies of the repository carry no Git history, so neither tags nor `git describe` survive an export.
  The version must live in a checked-in file.
- `west spdx` gives a Zephyr module only its Git revision, so the product's release step adds the Crux version to the SBOM ([SBOM](../product-composition.md#sbom)).
- CMake `project(VERSION)` accepts only integer parts, with no pre-release suffix ([CMake `project()`](https://cmake.org/cmake/help/latest/command/project.html)).
- ADR-0001 sets the tiers, the deprecation window and the rules before `v1.0` (D5 to D9). It does not list the tooling that products run or parse.

The practice followed is [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).
Crux departs from it in two places: before `v1.0` the minor number carries every break (O7), and after `v1.0` the major-version promise covers the Stable set only (O6), as [Zephyr's API lifecycle](https://docs.zephyrproject.org/latest/develop/api/api_lifecycle.html) does with its Unstable tier.

## Options and recommendations

### O2: the version on `main`

| Option | For | Against |
| --- | --- | --- |
| **a. `0.1.0-dev`, plain `-dev`** | Valid SemVer pre-release that sorts below `0.1.0`; the [SemVer FAQ](https://semver.org/spec/v2.0.0.html#faq) starts at `0.1.0`; ESP-IDF's main branch carries the next release with `-dev` | The string alone cannot order two snapshots of `main`; the SHA does that |
| b. Zephyr's `X.Y.99` | Fits tools that read numbers only | Under SemVer `0.0.99` is a release |
| c. `-alpha.N` or `-beta.N` | Common | They sort below `dev` in SemVer precedence, so mixing them misorders, and N is kept by hand |

**Recommendation: a.**
The only pre-release identifiers are `dev` and `rc.N`, which sort correctly (`dev` < `rc`).
Tags are exactly `vX.Y.Z`, the form that `west spdx` and the products already expect.

### O3: the numbers on `main`

On `main` the numeric parts name the target release, so `0.1.0-dev` and `0.1.0` have the same numbers.
**Recommendation:** version-number feature checks are not supported before `v1.0`, so the header has no numeric encoding macro.
No CMake package version file is written while `-dev` is set, because it would claim the release.

### O4: the public API that the version covers

The SemVer public API is ADR-0001's list in 4.1 plus the product tooling surface, which products run or parse. Each item has a tier under ADR-0001 4.1.

| Product tooling surface | Tier |
| --- | --- |
| The `west.yml` contract: the Zephyr pin, the import allowlist and the group names `crux-secure-management`, `crux-reliance` and `crux-boot` | Experimental |
| `west crux-pins` output lines and exit codes | Experimental |
| The command lines of the pin bot scripts (`crux-pin-bot.py`, `update-crux-pin.py`, `open-pin-pr.py`) and of `record-build-provenance.py` | Experimental |
| The release bundle schema ([Release bundle checker](../release-bundle-checker.md)) | Experimental |
| Minimum tool versions: CMake, the Zephyr SDK and the C standard | Experimental |

A raised minimum tool version is a compatibility change, as on the [Mbed TLS](https://github.com/Mbed-TLS/mbedtls/blob/development/BRANCHES.md) long-term support lines.

### O5: pinned-module moves

The rule "a change to a pinned module raises `y`" blocks a security patch release that must move a module within its own patch line.
**Recommendation:** a move within a module's patch line, such as Mbed TLS 4.1.1 to 4.1.2 or Zephyr 4.4.2 to 4.4.3, is allowed in a `z` release. Every other pin move and every Zephyr baseline move raises `y`.

### O6: composition interfaces after `v1.0`

A Stable composition interface could force a major release at every Zephyr baseline move (ADR-0001 composition-interface rule 6).

| Option | For | Against |
| --- | --- | --- |
| **a. Composition interfaces stay Unstable after `v1.0` until a Zephyr LTS policy exists** | Zephyr moves do not force major releases | Composition code gets the Unstable notice period only |
| b. Align Crux major releases with Zephyr LTS moves | One rule | Couples Crux's major number to Zephyr's calendar before Crux has a support policy |

**Recommendation: a.**

### O7: when to release and how the number moves

| Option | For | Against |
| --- | --- | --- |
| **a. Event-driven: a product release needs a named Crux revision, a Zephyr baseline moves, or a released line needs a security fix** | Releases only when someone consumes them | No predictable date |
| b. Calendar, as Zephyr's six-month cycle | Predictable | Empty releases while one product consumes Crux |

**Recommendation: a.** Before `v1.0`:

- Every release from `main` raises `y`. That covers breaking changes in any tier, features, Zephyr baseline moves and pin moves.
- `z` comes only from a release branch `v0.Y.x`, with fixes and the patch-line pin moves of O5.
- The first tag waits for ADR-0001 follow-ups 4 to 6 (the I2C, SPI and GPIO deprecation announcement, the tier table with `Status:` lines and `CRUX_DEPRECATED`, the release-note sections) and the product trial.

From `v1.0`: major for an incompatible change to a Stable interface after the ADR-0001 D7 window; minor for compatible additions, changes to Unstable or Experimental interfaces and Zephyr minor baseline moves; patch for fixes and patch-line pin moves.

### O8: who releases, and where the rules live

The owner decides each release and sets the tag.
The steps:

1. A release pull request drops `-dev` from `<crux/version.h>`, sets `CRUX_VERSION_PRERELEASE` to `""` and is merged with the owner's merge approval.
2. The owner tags that merge commit `vX.Y.Z`. Tags are annotated and never moved.
3. The next pull request sets `0.(Y+1).0-dev`, so no later commit claims the released number.
4. A release branch is cut from the tag only when a `z` release is needed.

The rules live in this record, linked from [Versions](../product-composition.md#versions).
Each tag has release notes: breaking changes with migration notes, deprecations, tier changes, the pin table and Zephyr deprecations. No running change log is kept in `docs/`.

## Consequences

- Machines keep pinning the SHA. The version names a reviewed SHA for people, release notes and the SBOM.
- `CMakeLists.txt` reads the numbers from `<crux/version.h>` into `project(crux VERSION ...)`, so `PROJECT_VERSION` has no `-dev`.
- A pin move whose range holds `BREAKING CHANGE:` footers is visible only in the commit history until the pin bot lists them (follow-up 1).

## Follow-up changes

Each is its own reviewed change. Changes under `scripts/` need the owner's approval of that change.

1. The pin bot's pull request text lists every `BREAKING CHANGE:` footer and every `CRUX_VERSION_STRING` change between the old and the new pin (`scripts/`).
2. A release check fails a tag whose name is not `v` followed by `CRUX_VERSION_STRING`. It is added when the first tag is prepared.
3. Tier labels for the product tooling surface of O4 in [Component readiness](../component-readiness.md), with ADR-0001 follow-up 5.

## Decisions

| # | Decision |
| --- | --- |
| O2 | SemVer. `main` carries the next release with `-dev`, now `0.1.0-dev`. Pre-release identifiers are only `dev` and `rc.N`. Tags are exactly `vX.Y.Z` and the owner sets them |
| O3 | The numeric parts on `main` name the target release. Version-number feature checks are not supported before `v1.0`. No CMake package version file while `-dev` is set |
| O4 | The public API is ADR-0001's list in 4.1 plus the product tooling surface of the table above, each with a tier |
| O5 | A pin move within a module's own patch line, such as a security patch, is allowed in a `z` release. Other pin moves and Zephyr baseline moves raise `y`. This amends ADR-0001 4.5 and the Versions rule |
| O6 | Composition interfaces stay Unstable after `v1.0` until a Zephyr LTS policy exists |
| O7 | Releases are event-driven. Before `v1.0` every release from `main` raises `y`, and `z` comes only from release branches. The first tag waits for ADR-0001 follow-ups 4 to 6 and the product trial |
| O8 | The release pull request drops `-dev`, the owner tags, the next pull request sets `0.(y+1).0-dev`. Release notes per tag, no change log page. The pin bot lists `BREAKING CHANGE:` footers between pins (follow-up 1) |

O1, the layering of the starter sample, is decided in the sample itself and is not part of this record.
