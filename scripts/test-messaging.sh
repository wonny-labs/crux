#!/usr/bin/env bash
# Crux Queue was removed (docs/messaging-contract.md). This runner keeps the checks that did not
# depend on it: the portable controller timing scenario (tests/messaging_consumer/scenario/controller.c) on Host,
# and the fractional Thread timing suite on native_sim.
set -euo pipefail
repo="$(git rev-parse --show-toplevel)"
mode="${1:-all}"
if [[ "$mode" != all && "$mode" != --host-only ]]; then
    printf 'Usage: %s [--host-only]\n' "$0" >&2
    exit 2
fi
cmake -S "$repo/tests/messaging_consumer" -B "$repo/build/messaging-consumer" -G Ninja
cmake --build "$repo/build/messaging-consumer" --parallel 2
ctest --test-dir "$repo/build/messaging-consumer" --output-on-failure \
    --output-junit "$repo/build/messaging-consumer/ctest-junit.xml"
if [[ "$mode" == --host-only ]]; then exit 0; fi
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
export ZEPHYR_BASE="$workspace/zephyr"
(cd "$workspace" && west twister -j 2 -p native_sim/native/64 \
    -T "$repo/tests/thread/zephyr_fractional" \
    -O "$repo/build/zephyr/twister-messaging" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$repo")
