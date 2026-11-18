#!/usr/bin/env bash
# Advisory Host coverage: build the Host tree with --coverage, run its CTest set and report.
#
#   coverage-host.sh run      configure, build and run CTest (a build or test failure fails)
#   coverage-host.sh report   collect the data and write the report (no threshold, never gates)
#
# The coverage flags are passed on the command line: CMakePresets.json is not edited. The
# other settings equal the host-debug preset. Reports go to build/coverage/host/report.
set -euo pipefail

if [[ "$(uname -s)" != Linux ]]; then
    printf 'Host coverage is configured for Linux only; reopen this repository in the Dev Container.\n' >&2
    exit 2
fi
mode="${1:-}"
if [[ "$mode" != run && "$mode" != report ]]; then
    printf 'Usage: %s run|report\n' "$0" >&2
    exit 2
fi

repo="$(git rev-parse --show-toplevel)"
build="$repo/build/coverage/host"
out="$build/report"
export CRUX_CACHE_DIR="${CRUX_CACHE_DIR:-${repo}/../.crux-cache}"
# Clang writes gcov-compatible data; llvm-cov reads it. Set CRUX_GCOV for another reader.
gcov_tool="${CRUX_GCOV:-llvm-cov-18 gcov}"

if [[ "$mode" == run ]]; then
    mkdir -p "$CRUX_CACHE_DIR/cmake"
    rm -rf "$build"
    cmake -S "$repo" -B "$build" -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
        -DFETCHCONTENT_BASE_DIR="$CRUX_CACHE_DIR/cmake" \
        -DCMAKE_C_FLAGS=--coverage -DCMAKE_CXX_FLAGS=--coverage -DCMAKE_EXE_LINKER_FLAGS=--coverage
    cmake --build "$build"
    # Ssh.cli_entry_symbols reads the undefined symbols of the SSH entry points' object files
    # and refuses any it does not know. --coverage adds llvm_gcda_* and llvm_gcov_init
    # references, so the test fails only in this instrumented build and says nothing here. It
    # still runs, un-instrumented, in the normal Host job (host.yml). Exclude only that test.
    ctest --test-dir "$build" --output-on-failure --output-junit "$build/ctest-junit.xml" \
        -E '^Ssh\.cli_entry_symbols$'
    exit 0
fi

# Component sources only: tests, the fetched test library and Zephyr or kernel code are out.
mkdir -p "$out"
cd "$repo"
gcovr -r "$repo" --gcov-executable "$gcov_tool" --gcov-object-directory "$build" \
    --filter 'components/' --exclude '.*/tests?/.*' \
    --exclude-unreachable-branches --exclude-throw-branches \
    --merge-mode-functions separate \
    --gcov-ignore-parse-errors=negative_hits.warn_once_per_file \
    --gcov-ignore-parse-errors=suspicious_hits.warn_once_per_file \
    --json "$out/coverage.json" --html-details "$out/index.html" --txt "$out/coverage.txt" \
    "$build"
python3 "$repo/scripts/coverage-summary.py" --title "Host (CTest, debug build)" \
    "$out/coverage.json" > "$out/summary.md"
