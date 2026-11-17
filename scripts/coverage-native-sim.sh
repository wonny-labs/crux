#!/usr/bin/env bash
# Advisory native_sim coverage for a representative set of component suites.
#
#   coverage-native-sim.sh run      run the suites on native_sim/native/64 with gcov data
#   coverage-native-sim.sh report   collect the data and write the report (never gates)
#
# The suites are the Time, Logging, System and FatFs File Twister suites, run with the same
# test roots and module arguments as their own scripts. One failing suite does not stop the
# others, but the run still fails. Reports go to build/coverage/native-sim/report.
set -euo pipefail

if [[ "$(uname -s)" != Linux ]]; then
    printf 'Zephyr coverage is configured for Linux only; reopen this repository in the Dev Container.\n' >&2
    exit 2
fi
mode="${1:-}"
if [[ "$mode" != run && "$mode" != report ]]; then
    printf 'Usage: %s run|report\n' "$0" >&2
    exit 2
fi

repo="$(git rev-parse --show-toplevel)"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
export ZEPHYR_BASE="$workspace/zephyr"
build="$repo/build/coverage/native-sim"
out="$build/report"
gcov_tool="${CRUX_GCOV:-gcov}"

suite() { # name test-root [twister argument ...]
    local name="$1" root="$2"
    shift 2
    (cd "$workspace" && west twister -j 2 -p native_sim/native/64 --enable-coverage \
        -T "$root" -O "$build/twister-$name" --inline-logs "$@")
}

if [[ "$mode" == run ]]; then
    if [[ ! -f "$workspace/.west/config" || ! -d "$ZEPHYR_BASE" ]]; then
        printf 'Run scripts/bootstrap-zephyr.sh before Zephyr coverage.\n' >&2
        exit 2
    fi
    rm -rf "$build"
    mkdir -p "$build"
    fatfs="$(cd "$workspace" && west list fatfs -f '{abspath}')"
    failed=()
    suite time "$repo/tests/time/zephyr" || failed+=(time)
    suite logging "$repo/tests/logging/zephyr" --extra-args="ZEPHYR_MODULES=$repo" || failed+=(logging)
    suite system "$repo/tests/system/zephyr" --extra-args="ZEPHYR_MODULES=$repo" || failed+=(system)
    ZEPHYR_TOOLCHAIN_VARIANT=host suite file-fatfs "$repo/tests/native/file_fatfs" \
        --extra-args="ZEPHYR_MODULES=$fatfs" || failed+=(file-fatfs)
    if ((${#failed[@]})); then
        printf 'Suites that failed to build or run with coverage: %s\n' "${failed[*]}" >&2
        exit 1
    fi
    exit 0
fi

# Component sources only: with the root set to this repository, Zephyr and kernel code fall
# outside it, and the test sources are excluded as Twister's own coverage run excludes them.
mkdir -p "$out"
cd "$repo"
reports=()
for directory in "$build"/twister-*; do
    [[ -d "$directory" ]] || continue
    gcovr -r "$repo" --gcov-executable "$gcov_tool" --gcov-object-directory "$directory" \
        --filter 'components/' --exclude 'tests/.*' \
        --exclude-unreachable-branches --exclude-throw-branches \
        --merge-mode-functions separate \
        --gcov-ignore-parse-errors=negative_hits.warn_once_per_file \
        --gcov-ignore-parse-errors=suspicious_hits.warn_once_per_file \
        --json "$directory/coverage.json" "$directory"
    reports+=("$directory/coverage.json")
done
if ((${#reports[@]} == 0)); then
    printf 'No Twister output under %s; nothing to report.\n' "$build" >&2
    exit 1
fi
tracefiles=()
for report in "${reports[@]}"; do tracefiles+=(--add-tracefile "$report"); done
gcovr -r "$repo" --merge-mode-functions separate "${tracefiles[@]}" \
    --json "$out/coverage.json" --html-details "$out/index.html" --txt "$out/coverage.txt"
python3 "$repo/scripts/coverage-summary.py" --title "native_sim (Time, Logging, System, FatFs File)" \
    "${reports[@]}" > "$out/summary.md"
