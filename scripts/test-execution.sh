#!/usr/bin/env bash
set -euo pipefail
if [[ "$(uname -s)" != Linux ]]; then
    printf 'Execution probes require the Linux development environment.\n' >&2
    exit 2
fi
repo="$(git rev-parse --show-toplevel)"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
export ZEPHYR_BASE="$workspace/zephyr"
# shellcheck source=lib/board.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib/board.sh"
board="$(crux_board_target 'mimxrt1060_evk@B//qspi')"
(cd "$workspace" && west twister -j 2 -p native_sim/native/64 -T "$repo/tests/execution" \
    -O "$repo/build/zephyr/twister-execution" --inline-logs)
# Cross-builds only: no programming, reset, debugger or serial access.
for profile in native posix; do
    extra=()
    if [[ "$profile" == posix ]]; then
        extra+=("-DEXTRA_CONF_FILE=$repo/tests/execution/posix.conf")
    fi
    (cd "$workspace" && west build -p always -b "$board" \
        -d "$repo/build/zephyr/execution-$profile-$(crux_board_tag "$board")" "$repo/tests/execution" -- \
        -DZEPHYR_EXTRA_MODULES="$repo" "${extra[@]}")
done
