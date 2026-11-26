#!/usr/bin/env bash
set -euo pipefail
if [[ "$(uname -s)" != Linux ]]; then
    printf 'Delay software checks require the Linux development environment.\n' >&2
    exit 2
fi
repo="$(git rev-parse --show-toplevel)"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
export ZEPHYR_BASE="$workspace/zephyr"
# shellcheck source=lib/board.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib/board.sh"
board="$(crux_board_target 'mimxrt1060_evk@B//qspi')"
(cd "$workspace" && west twister -j 2 -p native_sim/native/64 \
    -T "$repo/tests/time/busy_wait/zephyr" -O "$repo/build/zephyr/twister-time-busy-wait" --inline-logs)
(cd "$workspace" && west build -b "$board" \
    -d "$repo/build/zephyr/time-busy-wait-$(crux_board_tag "$board")" "$repo/tests/time/busy_wait/zephyr" -- \
    -DEXTRA_ZEPHYR_MODULES="$repo" -DCMAKE_EXPORT_COMPILE_COMMANDS=ON)
# Compilation only: no programming, reset, debugger, serial or target operation.
