# ADR-0009: Tiered CI for Crux and its product repositories

Status: **Accepted**. The owner asked on 26 November 2026, in the Crux core session, for the design and implementation of fast, full and nightly CI with suites chosen per tier, for Crux and the product repositories, and accepted T1 to T9 as recommended in the same session the same day. T10 was added afterwards at the owner's request to shorten the tiers; it takes effect with the pull request that adds it. Baseline: `origin/main` at `39140df6`; T10 at `62ed69f1`.

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

**R1 status.** Measured with the manual `base` input after T10, on one-file changes to the controller and File components: the slowest Zephyr fast job took 8.2 minutes (`zephyr-integration`) and 7.6 (`zephyr-storage`), and the `host` job 7.8 and 10.3 minutes, which made it the slowest fast job of the File change. The `host` job is the longest fast job for most components: 8 to 10 minutes with its quick checks, plus the component's own Host checks, up to about 1.6 minutes for the web component. It meets the target only partly; T10 option l would bring it to about 5 to 7 minutes. Neither change selected a PSA or web check, so no fast time is measured for a change that does; five of the six `psa-management` checks are fast checks of the web or management service components, and that job took 11.9 to 12.6 minutes in the full tier, so such a change may exceed the target. A change that falls back to the full tier takes the full time, about 14 minutes (T10).

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

**Recommendation: a.** The list errs towards the full tier: a component's Kconfig, `.conf` or overlay change escalates too. Narrowing it is a later change, backed by measured fallback rates. A text search at `62ed69f1` found 39 references from files outside a component to one of the 85 configuration files under that component's tests (some only by a shared file name), among them `tests/controller_m3/testcase.yaml` using the I2C and SPI `native_sim` overlays and the RT1060 web management sample using `tests/zephyr/web_compile/mbedtls.conf`, so counting those files as their component's own would select too little.

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

**Recommendation: a.** A measured trial of b, with the SDK verified after restore, can follow. T10 rechecks this against the measured set-up times.

### T9: product repositories

| Option | For | Against |
| --- | --- | --- |
| **a. Copy the entry point, selector and runner; each product writes its own map file** | Products keep their own checks and pins; the rules stay the same | Copies of three files to keep in step |
| b. Call Crux's scripts from the Crux checkout in the product's west workspace | No copy | Ties product CI to the pinned Crux revision's script interface |
| c. Each product designs its own tiers | Freedom | Two CI models for one team |

**Recommendation: a**, as [Continuous integration](../ci.md#use-in-a-product-repository) describes.

### T10: shortening the tiers

The full tier took as long as its slowest job: `zephyr-storage`, 30.5 minutes at `be60bc65`, of which one check, `emmc-reliance-edge`, took 9.2 to 14.8 minutes in three runs. Set-up took 0.4 to 0.6 minutes in a Host job and 2.0 to 2.6 in a Zephyr or PSA job. The owner's targets (26 November 2026): fast tier below 10 minutes per job, full tier 15 minutes, 20 at most, by industry-standard methods only.

| Option | Label and source | Result |
| --- | --- | --- |
| **a. More jobs, balanced by measured check time: eight Zephyr shards, three Host and two PSA jobs** | Standard: a job matrix ([GitHub matrix](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations)) and parallel stages ([Jenkins](https://www.jenkins.io/doc/book/pipeline/syntax/#parallel)); Zephyr's own pull request CI spreads Twister over a matrix of shards ([twister.yaml](https://github.com/zephyrproject-rtos/zephyr/blob/main/.github/workflows/twister.yaml)) | Applied. No command changes; `emmc-reliance-edge` is cut at its script boundary into two checks in two shards, as `tests/build` was cut in T4 |
| b. Twister `--subset` over one test plan | Documented option ([Twister](https://docs.zephyrproject.org/latest/develop/twister/index.html)); Zephyr's CI uses it | Not applied: Crux runs many small Twister and `west build` calls inside its check scripts, not one plan; sharding by check gives the same balance without changing a command |
| c. Twister `-j 4` | Documented option (Twister) | Not applied: measured with no clear gain ([Zephyr CI shards](../ci-zephyr-shards.md#options-measured-and-not-adopted)) |
| d. Twister integration mode (`--integration`) | Documented option (Twister) | Not applied: it builds fewer platforms, which removes configurations from the full tier (R2) |
| e. ccache for Zephyr builds | Documented option: Zephyr's build uses ccache when it is installed ([`USE_CCACHE`](https://docs.zephyrproject.org/latest/build/cmake-ref/variable/USE_CCACHE.html)) | Not applied: measured with no gain, since 34 to 54% of compiler calls were cacheable and configuring, linking and running dominate ([Zephyr CI shards](../ci-zephyr-shards.md#options-measured-and-not-adopted)) |
| f. `actions/cache` for west modules (`west update --path-cache`) keyed on `west.yml` | Documented options ([dependency caching](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching), [west update](https://docs.zephyrproject.org/latest/develop/west/built-in.html#west-update)) | Not applied now: it saves at most the module fetch, about one minute of a Zephyr job, and the slowest job after a, `host`, fetches no west modules (T8) |
| g. Cache the Zephyr SDK or pip downloads | Documented options (dependency caching; `actions/setup-python` `cache: pip`) | Not applied: a restored SDK skips the installer's checks (T8); the pip step takes 0.1 minutes |
| h. Move long gating suites to nightly | Project choice | Rejected: no check leaves the full tier (R2, R3) |
| i. Count a component's Kconfig, `.conf` and overlay files as its own in the fast tier | Standard in kind: path rules per component (R5) | Rejected for now: not provably safe (T3) |
| j. Run several checks of one job at the same time | Custom scheduler | Rejected: checks share build folders, and the owner excluded custom schedulers |
| **k. A `base` input for a manual run** | Standard: `workflow_dispatch` inputs ([events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)) and Jenkins parameters | Applied, so that the fast tier can be measured by hand |
| l. The two sanitizer checks in a Host job of their own | Standard, as a | Tried and withdrawn: `web-host` failed there, because `scripts/test-web.sh` runs every Web test of the `host-sanitize` tree but builds only some of them, and in the `host` job `host-sanitizers` builds the rest first. Making `test-web.sh` build what it runs would change a check script; it is left to the owner and would take the `host` job from about 13 to about 10 minutes |

**Recommendation: a and k.** Measured on hosted runners at `a704189d`: the slowest job is `host` (13.3 minutes), then `psa-management` (12.6) and the `controller` shard (12.0); each workflow took 12.7 to 14.1 minutes from creation to end, against 31.3 for the Zephyr workflow at `be60bc65` ([Zephyr CI shards](../ci-zephyr-shards.md#measurements)). More jobs use more of the runner limit ([Zephyr CI shards](../ci-zephyr-shards.md#limits)). f is the next step if a Zephyr job sets the wall time again.

## Decisions

T1 to T9 as recommended, accepted by the owner on 26 November 2026. T10 as recommended, with its pull request.
