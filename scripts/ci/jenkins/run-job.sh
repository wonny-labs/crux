#!/usr/bin/env bash
# Jenkins only: prepare the Dev Container image for one job of scripts/ci/checks.toml, then run
# that job's checks of the tier with scripts/ci/run-tier.sh. The root Jenkinsfile calls it once
# per stage; the GitHub workflows prepare their runners in their own steps with the same pins.
#
#   scripts/ci/jenkins/run-job.sh JOB      (the tier comes from $TIER, default auto)
#
# The repository must be checked out as <workspace>/crux. See docs/ci.md#jenkins.
set -euo pipefail
job=${1:-}
if [[ -z "$job" || $# -ne 1 ]]; then
    printf 'Usage: %s JOB (see scripts/ci/run-tier.sh --list-jobs)\n' "$0" >&2
    exit 2
fi
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
cd "$repo"
tier=${TIER:-auto}
export CRUX_WORKSPACE=${CRUX_WORKSPACE:-$(dirname "$repo")}

scripts/ci/run-tier.sh "$tier" --job "$job" --plan
if [[ "$(scripts/ci/run-tier.sh "$tier" --job "$job" --count)" == 0 ]]; then
    exit 0
fi

# The Python tools of each job, as pinned in the GitHub workflows.
case "$job" in
    host | host-*) tools="cmake==3.28.4 ninja==1.11.1 clang-format==18.1.8 west==1.4.0 pyyaml==6.0.3" ;;
    zephyr-*) tools="cmake==3.28.4 ninja==1.11.1 west==1.4.0 clang-format==18.1.8" ;;
    psa-*) tools="cmake==3.28.4 ninja==1.11.1 west==1.4.0" ;;
    coverage-host) tools="cmake==3.28.4 ninja==1.11.1 gcovr==8.3" ;;
    coverage-native-sim) tools="cmake==3.28.4 ninja==1.11.1 west==1.4.0 gcovr==8.3" ;;
    docs | web-*) tools="" ;;
    *)
        printf 'error: scripts/ci/jenkins/run-job.sh does not know job %s. Add its set-up here. See docs/ci.md#jenkins.\n' "$job" >&2
        exit 2
        ;;
esac

need() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'error: job %s needs %s on the agent, and it is missing. See docs/ci.md#jenkins.\n' "$job" "$1" >&2
        exit 2
    fi
}

if [[ -n "$tools" ]]; then
    python3 -m venv "$CRUX_WORKSPACE/.crux-tools"
    # shellcheck disable=SC2086 # the pins are separate words
    "$CRUX_WORKSPACE/.crux-tools/bin/pip" install --disable-pip-version-check $tools
    export PATH="$CRUX_WORKSPACE/.crux-tools/bin:$PATH"
    export CRUX_PYTHON="$CRUX_WORKSPACE/.crux-tools/bin/python"
fi

case "$job" in
    zephyr-* | coverage-native-sim)
        scripts/bootstrap-zephyr.sh --install-sdk
        ;;
    psa-*)
        (cd "$CRUX_WORKSPACE" && west init -l "$repo" && west config manifest.project-filter -- +mbedtls,+tf-psa-crypto)
        scripts/bootstrap-zephyr.sh --install-sdk
        ;;
    coverage-host)
        need llvm-cov-18
        ;;
    web-browser)
        need npm
        need google-chrome
        ;;
    web-*)
        need npm
        ;;
esac

exec scripts/ci/run-tier.sh "$tier" --job "$job"
