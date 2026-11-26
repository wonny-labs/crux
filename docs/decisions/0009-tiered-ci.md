# ADR-0009: Tiered CI for Crux and its product repositories

Status: **Proposed**. The owner asked on 26 November 2026, in the Crux core session, for the design and implementation of fast, full and nightly CI with suites chosen per tier, for Crux and the product repositories; acceptance of T1 to T9 is the owner's decision. Baseline: `origin/main` at `cc39cba5`.

This record decides how Crux splits its CI into tiers, how a check is assigned to a tier, and how the same rules run on every CI system.
The current rules are in [Continuous integration](../ci.md); this record keeps the requirements, the options and the reasons.

## Context

- Every pull request ran every check. On `main`, the Host workflow took a median of 27 minutes (6 runs), of which the Python tooling tests took 13.5 minutes, one mutation test 7.2 of them; the four Zephyr shards took a median of 27 minutes; the PSA workflow about 20.
- Many developers on feature branches would each wait that long per push.
- The company CI is a Jenkins on Linux agents with Docker, with Bitbucket Cloud. Company copies keep the `Jenkinsfile` and drop `.github/`.
- The repository is public and `main` has no required checks ([AGENTS.md](../../AGENTS.md#protected-paths)).

## Requirements

Each requirement is labelled **standard** (the documented practice of the cited project or vendor), **documented option** (an option that the cited source offers) or **project choice** (decided here, with the reason).

| # | Requirement | Label and source |
| --- | --- | --- |
| R1 | A fast tier on every push, with a median below 10 minutes per job for a change to one component | Project choice; the practice of running the quickest tests first is from Fowler's [Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html) |
| R2 | A full tier that runs exactly the checks that ran before tiers, under the same path rules | Project choice: no test is removed (AGENTS.md) |
| R3 | The full tier runs on every change before it merges | Standard: Zephyr runs its full PR plan before merge ([twister.yaml](https://github.com/zephyrproject-rtos/zephyr/blob/main/.github/workflows/twister.yaml)); GitHub draft pull requests cannot be merged ([About pull requests](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests)) |
| R4 | A periodic run of every check on the default branch, with coverage | Standard: Zephyr runs a weekly `--all` build (cron `0 2 * * 0` in twister.yaml); the Yocto autobuilder's `a-quick` is a subset of `a-full`, which runs on a schedule ([test process](https://docs.yoctoproject.org/test-manual/test-process.html)) |
| R5 | Selection by changed files, falling back to the full set when a file has no known owner | Standard: Zephyr's `scripts/ci/test_plan_v2.py` runs everything when no strategy handles a changed file; NuttX selects PR build configurations by changed files ([NuttX CI](https://nuttx.apache.org/docs/latest/testing/nuttx-ci.html)) |
| R6 | One entry point and one map file that every CI system calls; the CI files stay thin | Project choice: two CI systems must run the same checks |
| R7 | The selection uses plain git and environment values, no CI service API | Project choice; Jenkins `changeset` does not show a change request's diff ([JENKINS-54285](https://issues.jenkins.io/browse/JENKINS-54285)) |
| R8 | Outputs that both systems read: exit status, JUnit XML, logs under one folder | Standard: Jenkins [`junit`](https://www.jenkins.io/doc/pipeline/steps/junit/) and GitHub artifacts both take files |
| R9 | No automatic retries; a flaky check is recorded and fixed, and leaves the full tier only by an approved change | Documented option: Twister has `--retry-failed` and a quarantine list ([Twister](https://docs.zephyrproject.org/latest/develop/twister/index.html#quarantine)); Bazel's `flaky` reruns up to three times and is to be used sparingly ([common definitions](https://bazel.build/reference/be/common-definitions)) |

### Acceptance criteria

1. The full tier's checks, per job and in order, equal the CI steps on `origin/main` at `cc39cba5`, with the Python tooling tests split into a large part and the rest that together are the same cases.
2. Tests prove that a fast run falls back to the full tier for an unknown path, a build, CI, script or shared configuration file, Kconfig, `west.yml`, the CMake root, a core component, too many components, and an empty or unknown change.
3. Tests prove that a fast run never selects a check that the full run of the same change would not.
4. The tier and the comparison base come from GitHub and Jenkins environment values, tested for each event.
5. A GitHub workflow runs no check outside `scripts/ci/run-tier.sh`, and the Jenkinsfile calls only repository scripts.

## Options and recommendations

### T1: the tiers

**Recommendation:** three tiers, `fast`, `full` and `nightly`, as in the [tier model](../ci.md#tier-model). The nightly tier is the full tier without path rules, plus coverage. Two tiers would leave coverage and path-rule gaps unchecked; more than three adds names without new behaviour.

### T2: the unit of selection

| Option | For | Against |
| --- | --- | --- |
| **a. The check: one script or command in the map file** | Covers Host CTest, Python, npm and Twister alike; matches how the workflows are built | Coarser than single tests |
| b. Twister `levels` or tags per test | Zephyr's own mechanism ([Twister configuration file](https://docs.zephyrproject.org/latest/develop/twister/index.html#twister-configuration-file)) | Only Twister scenarios have them; most Crux checks are not Twister runs |

**Recommendation: a.** A check script may later use Twister levels or `--integration` inside itself; that is a documented option, not adopted now.

### T3: fallback

**Recommendation:** fall back to the full tier for any changed file that matches no component, for the escalation list, and for more than three components. This follows Zephyr's test plan, which runs everything for unhandled files. The list errs towards the full tier: a component's Kconfig, `.conf` or overlay change escalates too.

### T4: large tests

**Recommendation:** a case of the Python tooling tests that takes more than 30 seconds on a hosted runner is large. It runs in the full and nightly tiers and leaves the fast tier, as Bazel's `size` classes separate long tests ([common definitions](https://bazel.build/reference/be/common-definitions)). The list is `scripts/ci/large-tests.txt`; a listed case that discovery does not find is an error.

### T5: GitHub triggers

| Option | For | Against |
| --- | --- | --- |
| **a. `pull_request` (draft: fast; ready: full, also on `ready_for_review`), `push` to `main` (full), `schedule` (nightly), `workflow_dispatch` (tier input)** | One run per push to a pull request; the standard events ([events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)) | A branch without a pull request gets no CI |
| b. Add `push` to every branch (fast) | CI before a pull request exists | Every push to a pull request branch runs twice |

**Recommendation: a.** A developer opens a draft pull request for fast feedback, or runs a workflow by hand.

### T6: Jenkins

**Recommendation:** a root `Jenkinsfile`, the default name that a Multibranch Pipeline reads ([Multibranch](https://www.jenkins.io/doc/book/pipeline/multibranch/)), with one parallel stage per job in the Dev Container image built with `CRUX_JLINK=0`. A change request build (`CHANGE_ID`) runs full, a branch build fast, `main` full, and a `cron` timer nightly ([Pipeline syntax](https://www.jenkins.io/doc/book/pipeline/syntax/)). Bitbucket Cloud has draft pull requests ([draft pull requests](https://support.atlassian.com/bitbucket-cloud/docs/draft-pull-requests/)), and the branch source plugin can skip them (release 937.3.0); whether a draft flag reaches the pipeline is unverified, so a change request build runs full.

### T7: the merge gate

**Recommendation:** the repository relies on draft pull requests and the full tier on ready ones. Required status checks or a merge queue (`merge_group`, [merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)) would enforce it; they are settings, left to the owner. A path-filtered workflow that does not run leaves a required check pending ([workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)), which a required-check rule must handle.

### T8: caching

**Recommendation:** keep the verified apt package cache of the Zephyr jobs and add no new cache now. The Zephyr workspace and SDK step takes 1.6 to 2.2 minutes per job, and a restored SDK folder would skip the installer's download, which needs the same verification the apt cache has. A measured trial can follow. The GitHub cache limit is 10 GB per repository with least-recently-used eviction ([dependency caching](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)).

### T9: product repositories

**Recommendation:** product repositories follow [Continuous integration](../ci.md#use-in-a-product-repository): the same tiers, entry point and selector, with their own map file.

## Decisions

Proposed: T1 to T9 as recommended. None is accepted until the owner decides.
