# ADR-0009: Tiered CI for Crux and its product repositories

Status: **Proposed**. The owner asked on 26 November 2026, in the Crux core session, for the design and implementation of fast, full and nightly CI with suites chosen per tier, for Crux and the product repositories; acceptance of T1 to T9 is the owner's decision. Baseline: `origin/main` at `39140df6`.

This record decides how Crux splits its CI into tiers, how a check is assigned to a tier, and how the same rules run on every CI system.
The current rules are in [Continuous integration](../ci.md); this record keeps the requirements, the options and the reasons.

## Context

- Every pull request ran every check, apart from the documentation filters of the workflows. On `main`, the Host workflow took a median of 27 minutes (6 runs), of which the Python tooling tests took 13.5 minutes, one mutation test 7.2 of them; the four Zephyr shards took a median of 27 minutes; the PSA workflow about 20.
- Many developers on feature branches would each wait that long per push.
- The organisation's CI is a Jenkins on Linux agents with Docker, with Bitbucket Cloud. Its copies of the repository keep the `Jenkinsfile` and drop `.github/`.
- The repository is public and `main` has no required checks ([AGENTS.md](../../AGENTS.md#protected-paths)).

## Requirements

Each requirement is labelled **standard** (the documented practice of the cited project or vendor), **documented option** (an option that the cited source offers) or **project choice** (decided here, with the reason).

| # | Requirement | Label and source |
| --- | --- | --- |
| R1 | A fast tier on every push to a draft change request (GitHub) or a branch (Jenkins), with a median below 10 minutes per job for a change to one component | Project choice; the practice of running the quickest tests first is from Fowler's [Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html) |
| R2 | A full tier that runs exactly the checks that ran before tiers, under the same path rules | Project choice: no test is removed (AGENTS.md) |
| R3 | The full tier runs on every change before it merges | Project choice. Zephyr's pull request workflow ends in one status job, `twister-status-check`, that collects its shards, but its pull request plan is a selected subset ([twister.yaml](https://github.com/zephyrproject-rtos/zephyr/blob/main/.github/workflows/twister.yaml)); GitHub draft pull requests cannot be merged ([About pull requests](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests)) |
| R4 | A periodic run of every check on the default branch, with coverage | Standard: Zephyr's `schedule` trigger (cron `0 2 * * 0`, weekly) runs Twister with `--all --build-only` (twister.yaml); the Yocto autobuilder's `a-quick` is a subset of `a-full` ([test process](https://docs.yoctoproject.org/test-manual/test-process.html)) |
| R5 | Selection by changed files, falling back to the full set when a file has no known owner | Standard: Zephyr's `scripts/ci/test_plan_v2.py`, which twister.yaml calls, signals a full run when no strategy handles a changed file; NuttX selects pull request build configurations by changed files ([NuttX CI](https://nuttx.apache.org/docs/latest/testing/nuttx-ci.html)) |
| R6 | One entry point and one map file that every CI system calls; the CI files stay thin | Project choice: two CI systems must run the same checks |
| R7 | The selection uses plain git and environment values, no CI service API | Project choice; Jenkins `changeset` does not show a change request's diff ([JENKINS-54285](https://issues.jenkins.io/browse/JENKINS-54285)) |
| R8 | Outputs that both systems read: exit status, JUnit XML, logs under one folder | Standard: Jenkins [`junit`](https://www.jenkins.io/doc/pipeline/steps/junit/) and GitHub artifacts both take files |
| R9 | No automatic retries; a flaky check is recorded and fixed, and leaves the full tier only by an approved change | Documented option: Twister has `--retry-failed` and a quarantine list ([Twister](https://docs.zephyrproject.org/latest/develop/twister/index.html#quarantine)); Bazel's `flaky` reruns up to three times and is to be used sparingly ([common definitions](https://bazel.build/reference/be/common-definitions)) |

**R1 status.** Estimated from the per-check times of the first full runs, the fast tier meets the target for most single components: Host jobs 6 to 9 minutes, a Zephyr shard 3.3 minutes when only its quick checks run and 5 to 9 with one component's checks. It misses it for the controller component (about 15 minutes, `controller-integration` alone about 7), the File component (the storage shard, about 10 to 15) and any change to the PSA or web parts (about 6 to 12 in their own jobs). A change that falls back to the full tier takes the full time.

### Acceptance criteria

1. The full tier's checks, per job and in order, equal the CI steps on `origin/main`, with the Python tooling tests split into a large part and the rest that together are the same cases.
2. Tests prove that a fast run falls back to the full tier for an unknown path, a build, CI, script or shared configuration file, Kconfig, `west.yml`, the CMake root, a core component, too many components, and an empty or unknown change.
3. Tests prove that a fast run never selects a check that the full run of the same change would not.
4. The tier and the comparison base come from GitHub and Jenkins environment values, tested for each event.
5. A GitHub tier workflow runs no check outside `scripts/ci/run-tier.sh`; the advisory `coverage.yml` calls the coverage scripts directly, and a test keeps them equal to the map file's coverage checks. The Jenkinsfile calls only repository scripts.

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

| Option | For | Against |
| --- | --- | --- |
| **a. Fall back to full for an unowned file, the escalation list and more than three components** | Never selects too little for a file the map does not know; the same rule as Zephyr's test plan | Many changes (any script, Kconfig or overlay) get the full time |
| b. Run only the owned components' checks and ignore unowned files | Faster | A change in an unmapped place runs nothing relevant |
| c. Derive dependencies from the build (CMake or Kconfig graphs) | Precise | A large tool to build and maintain; wrong edges select too little |

**Recommendation: a.** The list errs towards the full tier: a component's Kconfig, `.conf` or overlay change escalates too. Narrowing it is a later change, backed by measured fallback rates.

### T4: large tests

| Option | For | Against |
| --- | --- | --- |
| **a. List the slow cases in a file; the fast tier leaves them out** | Two cases take 8 of the 13.5 minutes; no test changes | A list to keep; a renamed case must be caught (it is: a missing id is an error) |
| b. A size attribute or decorator on each test | Lives with the test, like Bazel's `size` ([common definitions](https://bazel.build/reference/be/common-definitions)) | Edits many test files; unittest has no standard attribute |
| c. Keep every case in the fast tier | Simplest | The Host feedback stays above 13 minutes |

**Recommendation: a**, with a threshold of 30 seconds on a hosted runner. The list is `scripts/ci/large-tests.txt`.

### T5: GitHub triggers

| Option | For | Against |
| --- | --- | --- |
| **a. `pull_request` (draft: fast; ready: full, also on `ready_for_review`), `push` to `main` (full), `schedule` (nightly), `workflow_dispatch` (tier input)** | One run per push to a pull request; the standard events ([events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)) | A branch without a pull request gets no CI |
| b. Add `push` to every branch (fast) | CI before a pull request exists | Every push to a pull request branch runs twice |

**Recommendation: a.** A developer opens a draft pull request for fast feedback, or runs a workflow by hand.

### T6: Jenkins

| Option | For | Against |
| --- | --- | --- |
| **a. A root `Jenkinsfile`, one parallel stage per job, each in the Dev Container image built with `CRUX_JLINK=0`** | The default file of a Multibranch Pipeline ([Multibranch](https://www.jenkins.io/doc/book/pipeline/multibranch/)); developers and CI share one image; stages report separately | Every stage builds the image and a workspace; web stages need another agent |
| b. One stage that runs every job in sequence | One image build | No parallelism; one failure hides the rest |
| c. A prebuilt image in a registry | No build per stage | A registry and its upkeep, and the image can drift from the Dockerfile |

**Recommendation: a.** A change request build (`CHANGE_ID`) runs full, a branch build fast, `main` full, and a `cron` timer nightly ([Pipeline syntax](https://www.jenkins.io/doc/book/pipeline/syntax/)). Bitbucket Cloud has draft pull requests ([draft pull requests](https://support.atlassian.com/bitbucket-cloud/docs/draft-pull-requests/)), and the branch source plugin can skip them (release 937.3.0); whether a draft flag reaches the pipeline is unverified, so a change request build runs full.

### T7: the merge gate

**Recommendation:** the repository relies on draft pull requests and the full tier on ready ones. Required status checks or a merge queue (`merge_group`, [merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)) would enforce it; they are settings, left to the owner. A path-filtered workflow that does not run leaves a required check pending ([workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)), which a required-check rule must handle.

### T8: caching

| Option | For | Against |
| --- | --- | --- |
| **a. Keep the verified apt cache; add no other cache now** | No new trust question; nothing to maintain | The workspace and SDK step stays at 1.6 to 2.2 minutes per Zephyr job |
| b. Cache the Zephyr SDK and west modules with `actions/cache` | Saves up to that step's time | A restored SDK folder skips the installer's download and its checks; the 10 GB limit with least-recently-used eviction ([dependency caching](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)) |
| c. ccache | Measured once with 84.7 to 99.7% hits | No measured gain ([Zephyr CI shards](../ci-zephyr-shards.md#options-measured-and-not-adopted)) |

**Recommendation: a.** A measured trial of b, with the SDK verified after restore, can follow.

### T9: product repositories

| Option | For | Against |
| --- | --- | --- |
| **a. Copy the entry point, selector and runner; each product writes its own map file** | Products keep their own checks and pins; the rules stay the same | Copies of three files to keep in step |
| b. Call Crux's scripts from the Crux checkout in the product's west workspace | No copy | Ties product CI to the pinned Crux revision's script interface |
| c. Each product designs its own tiers | Freedom | Two CI models for one team |

**Recommendation: a**, as [Continuous integration](../ci.md#use-in-a-product-repository) describes.

## Decisions

Proposed: T1 to T9 as recommended. None is accepted until the owner decides.
