# Continuous integration

This page is the reference for Crux CI: the three tiers, the rules that pick the checks of each tier, the entry point that every CI system calls, and the map file that holds the checks.
Read it to run, add or rerun a check, or to set up CI in a product repository that follows the same model.
The reasons and the options considered are in [ADR-0009](decisions/0009-tiered-ci.md).

## Tier model

| Tier | Runs | Checks | Purpose |
| --- | --- | --- | --- |
| `fast` | On every push to a draft change request, and on every Jenkins branch build | The quick checks of every change (format, static analysis, Host build and unit tests, the Python tooling tests, documentation links, Zephyr smoke builds and patch style) plus the checks of the components that the change touches | Feedback within minutes while a change is developed |
| `full` | On a change request that is ready for review, on every push to it, and after a merge to the default branch | Every check that the change can affect | The gate before merge |
| `nightly` | Once a day on the default branch | Every full check whatever the change, plus advisory coverage | Catch what path rules and merge order can miss |

A product repository uses the same three names and the same rules: its own map file lists its own checks.

## Entry point

Every CI system and every developer runs the same command from the repository root:

```sh
scripts/ci/run-tier.sh fast|full|nightly|auto [--job JOB] [--check ID] [--base REF] [--plan] [--count]
```

| Option | Effect |
| --- | --- |
| `auto` | Decides the tier and the comparison base from the CI environment ([When each tier runs](#when-each-tier-runs)); on a developer machine it is `fast` against `origin/main` |
| `--job JOB` | Runs only that job's checks; repeatable. `--list-jobs` prints the jobs |
| `--check ID` | Runs only that check, whether the tier selects it or not; repeatable |
| `--base REF` | Compares the change with this ref or commit instead of the one `auto` derives; the variable `CRUX_CI_BASE` does the same |
| `--plan` | Prints the selected checks and why, and runs nothing |
| `--count` | Prints the number of selected checks |

It needs Python 3.11 or later as `python3`, or the interpreter named by `CRUX_CI_PYTHON`, and Git.
It compares commits, so uncommitted edits are not part of the change.

Within a job the checks run in the map file's order, each as `bash -eo pipefail -c` from the repository root.
The first failing check stops the job, and the checks after it are reported as skipped.
An advisory check runs after a failure too, and its own failure prints a warning without failing the job.

| Exit status | Meaning |
| --- | --- |
| 0 | Every selected check passed, or none was selected |
| 1 | A check failed; the message names it and the command that reruns it |
| 2 | A usage or map file error |

Each job writes `build/ci/<job>.junit.xml`, with one test case per check, and each check's output to `build/ci/logs/<job>/<check>.log`.
Every GitHub job that runs the entry point uploads `build/ci/`, and the Jenkinsfile archives it.
A check sees `CRUX_CI_TIER`, `CRUX_CI_EVENT`, `CRUX_CI_JOB` and, when the change is known, `CRUX_CI_DIFF_BASE`, the commit the change was compared with.

## Map file

[`scripts/ci/checks.toml`](../scripts/ci/checks.toml) is the one list of CI checks. [`scripts/ci/tiers.py`](../scripts/ci/tiers.py) reads it.

| Table | Holds |
| --- | --- |
| `[selection]` | `docs`: the patterns of documentation; `escalate`: the patterns that make a fast run fall back to the full tier; `max_components` |
| `[components]` | Each component's path patterns |
| `[scopes]` | Named lists of path patterns that a check can use as its scope |
| `[jobs.<name>]` | One CI job: a `description` and optional `env` defaults that its checks see |
| `[[check]]` | One check, with the keys below |

| Key | Meaning |
| --- | --- |
| `id` | A unique name |
| `job` | The job that runs it |
| `run` | The shell commands |
| `scope` | The changes that need it in the full tier: `code` (the default), `always` for every change, or the name of a scope in `[scopes]` |
| `fast` | `"always"`, or the list of components whose changes select it in the fast tier; without it the check runs in the full tier only |
| `tiers` | `["full"]` (the default) or `["nightly"]` for a nightly-only check |
| `advisory` | `true` for a check whose failure must not fail the job |

Patterns follow the GitHub Actions path filter syntax: `**` matches across folders, `*` within one, and a later pattern that starts with `!` removes the paths that earlier patterns matched.

## Selection rules

**Full.** A check runs when its scope matches the change:

- `code` runs for every change, except a documentation-only change (every file in `docs/**` or any `*.md`) while it is developed: in a change request, a branch build or a local run. After a merge it runs.
- `always` runs for every change.
- A named scope runs when a changed file matches its patterns, on every event. The Zephyr jobs use `not-docs`, the same filter as their GitHub workflow; the PSA and web jobs use the paths of their workflows.

A change that is unknown runs every full check.

**Fast.** The fast tier falls back to the full tier, and prints why, when any of these holds:

- the change is unknown or empty;
- a changed file matches `escalate`: CI and build files, scripts, shared configuration, the Zephyr module root, any Kconfig, `.conf` or `.overlay` file, the hardware tools, the templates, the board samples, and the components that the others build on (Base, Interrupt, Sync, Thread, Time);
- a changed file is neither documentation nor part of a component;
- the change touches more components than `max_components` (3).

Otherwise the fast tier runs the full tier's checks that have `fast = "always"` or name a touched component.
It never runs a check that the full tier would not run for the same change.

**Nightly.** Every check of the full and nightly tiers, whatever the change.
On GitHub the coverage checks run in `coverage.yml`, which calls the coverage scripts directly with its own report steps; the map file lists the same commands for other CI systems, and `tests/build/test_ci_tiers.py` keeps them equal.

### Comparison base

The change is the list of files that `git diff --name-only --no-renames` reports between the merge base of the comparison base and `HEAD`, and `HEAD`.
A renamed file counts as both paths.
When the merge base cannot be found, the plain comparison with the base is used, which can only list more files.
When the base itself cannot be found or fetched, the change is unknown.
A post-merge run with no previous commit fails the patch style check, which needs one; [`scripts/ci/check-patch-range.sh`](../scripts/ci/check-patch-range.sh) checks the latest commit when a manual run has no base.

## When each tier runs

| Event | GitHub Actions | Jenkins Multibranch Pipeline | Tier | Comparison base |
| --- | --- | --- | --- | --- |
| Draft change request, opened or pushed | `pull_request` with `draft: true` | No draft flag reaches the pipeline: see [Jenkins](#jenkins) | `fast` | Target branch |
| Change request ready for review, or pushed while ready | `pull_request` types `opened`, `synchronize`, `reopened`, `ready_for_review` | A change request build (`CHANGE_ID` set) | `full` | Target branch (`GITHUB_BASE_REF`, `CHANGE_TARGET`) |
| Push to a branch without a change request | Not built; open a draft pull request or run the workflow by hand | A branch build | `fast` | `origin/main` |
| Merge to the default branch | `push` to `main` | A build of `main` | `full` | The previous commit (`before`, `GIT_PREVIOUS_SUCCESSFUL_COMMIT`); none for the first Jenkins build of the branch |
| Merge queue | `merge_group`, which `auto` handles; the workflows list it once a merge queue is enabled | — | `full` | The queue's base commit |
| Nightly | `schedule`, 02:17 UTC | `cron('H 2 * * *')` on `main`, which sets `CRUX_CI_TRIGGER=timer` | `nightly` | None |
| By hand | `workflow_dispatch` with the `tier` and `base` inputs | The `TIER` and `BASE` parameters | As chosen | `base` or `BASE` when given; otherwise none for GitHub and derived for Jenkins |

`CRUX_CI_DEFAULT_BRANCH` names a default branch other than `main`.
On GitHub a newer push to a pull request cancels the older run of the same workflow; runs on `main` are never cancelled.
On Jenkins a newer build of a branch or change request aborts the older one, except on `main`.

## Merge rule

The full tier must pass on a change before it merges.
On GitHub a draft pull request cannot be merged, and a pull request that is ready runs the full tier on every push and when it is marked ready.
Nothing in the repository settings enforces the rule: required status checks or a merge queue would, and choosing them is the owner's decision.
Until then a ready pull request can be merged while its full run is still pending or after it failed, an administrator can merge past any check, and a merge does not rerun the full tier on the merged result before it lands (a merge queue would).
A workflow skipped by its path filter reports no status, so a required check needs a workflow that always reports, as the `zephyr` summary job does when every shard ran.

## Jenkins

The root [`Jenkinsfile`](../Jenkinsfile) is a declarative Multibranch Pipeline with one parallel stage per job.
Each stage builds the Dev Container image from `.devcontainer/Dockerfile` with `--build-arg CRUX_JLINK=0`, checks the repository out as `<stage workspace>/crux-pilot`, and runs [`scripts/ci/jenkins/run-job.sh`](../scripts/ci/jenkins/run-job.sh), which installs the job's pinned tools, prepares the west workspace and calls the entry point.
A Docker volume `crux-ci-cache` at `/opt/crux-cache` keeps the Zephyr SDK between builds.

| Need | Why |
| --- | --- |
| Docker with BuildKit on the agent | The Dockerfile uses `RUN --mount` |
| An agent labelled `crux-web` with Node.js, npm and Google Chrome | The four web jobs; the Dev Container has neither |
| `llvm-cov-18` in the image | The `coverage-host` job; the Dev Container lacks it, so that nightly job fails until it is added |
| A checkout that also fetches the target branch | Without it the change is unknown, and the full set runs |

The Jenkinsfile has not run on a Jenkins server. These points are unverified:

- whether the Bitbucket Cloud branch source passes a draft flag to the pipeline: its release 937.3.0 can leave draft pull requests unbuilt, so a draft is built as a branch (fast) when branch discovery includes it;
- whether a Multibranch checkout fetches the target branch for `git merge-base`;
- the ownership of the `crux-ci-cache` volume for the agent's user.

Every stage builds the image and checks the repository out even when its job has nothing selected; `run-job.sh` then returns before the set-up. The nightly build runs both coverage jobs every day, about 5 minutes of Host and an hour or more of `native_sim` agent time.

The `changeset` condition of Jenkins is not used: in a change request build it reports the commits since the last build, not the change against the target ([JENKINS-54285](https://issues.jenkins.io/browse/JENKINS-54285)).

### Copies without .github/

A copy of the repository without `.github/` runs CI through the `Jenkinsfile` only. In such a copy:

- the tests that read `.github/workflows` skip with a reason when the folder is missing (a single missing workflow fails them): the workflow parts of `tests/build/test_ci_tiers.py` (`JenkinsTest`), `test_zephyr_ci_shards.py`, `test_ci_wiring.py`, `test_coverage_workflow.py` and the matrix part of `test_boot_composition.py`; the map file and Jenkinsfile parts still run;
- the link to `zephyr.yml` in [Zephyr CI shards](ci-zephyr-shards.md) points at a missing file and must be rewritten or removed;
- the copy gate must check both, because a skip passes.

## Add a check

1. Add a `[[check]]` to `scripts/ci/checks.toml` in the job whose work is closest, at the place in the order where its inputs exist.
2. Give it `fast` if one component owns it and it takes a few minutes at most.
3. Add its id to `EXPECTED_FULL` in [`tests/build/test_ci_tiers.py`](../tests/build/test_ci_tiers.py).
4. Add new output paths to the job's upload step in its GitHub workflow.

A new job also needs a runner in each CI system: a matrix entry or job in a GitHub workflow, a stage in the `Jenkinsfile`, and its tools in `run-job.sh`.
`tests/build/test_ci_tiers.py` and `tests/build/test_zephyr_ci_shards.py` fail when a check or job is missing on either side.
Removing a check from the full tier needs an approved change.

## Rerun a check

```sh
scripts/ci/run-tier.sh full --job zephyr-io --check gpio-zephyr
```

The failure message prints this command for the failed check. Run it in the Dev Container with the job's set-up done ([Build](build.md)).

## Flaky checks

A check is not retried automatically: a retry can hide a defect.
Rerun a failing check with `--check` to tell a flaky failure from a real one, and record a flaky check in an issue.
Taking a check out of the full tier, as Twister's quarantine list does for a test, needs an approved change that names the issue.

## Add a CI system

Another CI system is added by one thin configuration file that calls `scripts/ci/run-tier.sh fast|full|nightly` (or `auto`, after adding the system's variables to `ci_context` in `tiers.py`) once per job.
Run it on that system before relying on it.
Bitbucket Pipelines, for example, would be one `bitbucket-pipelines.yml`; none is set up.

## Use in a product repository

A product repository copies `scripts/ci/run-tier.sh`, `scripts/ci/tiers.py` and `scripts/ci/run_unittests.py`, writes its own `checks.toml` with its own components and checks, and copies the tests of `tests/build/test_ci_tiers.py` that hold the selector's rules.
Its workflows and Jenkinsfile follow this page: one job per runner, the tier from `auto` or the manual input, and `build/ci/` archived.
