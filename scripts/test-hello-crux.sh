#!/usr/bin/env bash
# Builds and runs the starter samples and checks their output.
#
#   --host    samples/hello_crux/host as a standalone consumer CMake project (Linux with CMake 3.28+,
#             Ninja and a C compiler; the Host composition does not build on macOS)
#   --zephyr  samples/hello_crux and samples/file/write_read with Twister on native_sim/native/64,
#             whose console harness checks each sample's output lines (Linux, west workspace)
#
# With no option it runs both. Nothing here flashes or resets a board.
set -euo pipefail

repo="$(git rev-parse --show-toplevel)"
run_host=0
run_zephyr=0
case "${1:-}" in
    "") run_host=1; run_zephyr=1 ;;
    --host) run_host=1 ;;
    --zephyr) run_zephyr=1 ;;
    *)
        printf 'Usage: %s [--host|--zephyr]\n' "$0" >&2
        exit 2
        ;;
esac
if [[ $# -gt 1 ]]; then
    printf 'Usage: %s [--host|--zephyr]\n' "$0" >&2
    exit 2
fi

if ((run_host)); then
    build="$repo/build/samples/hello_crux_host"
    printf 'Building samples/hello_crux/host as a standalone consumer of %s.\n' "$repo"
    cmake -S "$repo/samples/hello_crux/host" -B "$build" -G Ninja -DCRUX_SOURCE_DIR="$repo"
    cmake --build "$build"
    "${CRUX_PYTHON:-python3}" "$repo/scripts/run-host-sample.py" "$build/hello-crux-host" \
        "--expect=^Hello from Crux on host$" \
        "--expect=^Crux Time: unset$" \
        "--expect=^CRUX_HELLO_READY composition=host$"
    printf 'PASS: hello_crux on the Linux Host composition.\n'
fi

if ((run_zephyr)); then
    if [[ "$(uname -s)" != Linux ]]; then
        printf 'Zephyr checks are configured for Linux only; reopen this repository in the Dev Container.\n' >&2
        exit 2
    fi
    workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
    if [[ ! -f "$workspace/.west/config" || ! -d "$workspace/zephyr" ]]; then
        printf 'Run scripts/bootstrap-zephyr.sh before the Zephyr checks.\n' >&2
        exit 2
    fi
    (cd "$workspace" && west twister -p native_sim/native/64 -t sample \
        -T "$repo/samples/hello_crux" -T "$repo/samples/file/write_read" \
        -O "$repo/build/zephyr/twister-starters" --inline-logs)
    printf 'PASS: hello_crux and write_read on native_sim/native/64.\n'
fi
