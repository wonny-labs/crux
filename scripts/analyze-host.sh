#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != Linux ]]; then
    printf 'Host analysis is configured for Linux build artifacts; reopen this repository in the Dev Container.\n' >&2
    exit 2
fi

repo="$(git rev-parse --show-toplevel)"
host_preset="${CRUX_HOST_PRESET:-host-debug}"
export CRUX_CACHE_DIR="${CRUX_CACHE_DIR:-${repo}/../.crux-cache}"
case "$host_preset" in
    host-debug)
        build_dir="$repo/build/linux/debug"
        ;;
    host-sanitize)
        build_dir="$repo/build/linux/sanitize"
        ;;
    *)
        printf 'Unsupported CRUX_HOST_PRESET: %s\n' "$host_preset" >&2
        exit 2
        ;;
esac
if [[ ! -f "$build_dir/compile_commands.json" ]]; then
    printf 'Configure and build %s first (scripts/bootstrap-host.sh).\n' "$host_preset" >&2
    exit 2
fi
tidy="${CLANG_TIDY:-clang-tidy-18}"
# The sources come from the compile databases of the builds listed in scripts/tidy-sources.conf; see
# docs/static-analysis-coverage.md. CI (GITHUB_ACTIONS) and CRUX_TIDY_STRICT=1 also fail on a listed build
# that was not built and on a compile database that is neither listed nor ignored.
strict=()
if [[ "${GITHUB_ACTIONS:-}" == true || "${CRUX_TIDY_STRICT:-}" == 1 ]]; then
    strict=(--strict)
fi
exec python3 "$repo/scripts/tidy-sources.py" run --repo "$repo" --tidy "$tidy" \
    --primary "build/linux/${host_preset#host-}" ${strict[@]+"${strict[@]}"}
