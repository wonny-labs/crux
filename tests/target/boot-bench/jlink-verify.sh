#!/usr/bin/env bash
# Read-only compare of the target's flash with one file of <bench>/handoff/. Used as the `verify` command
# of the device-control profile: <bench>/jlink-verify.sh {image}. Exits 0 only when Commander exits 0 and
# its output contains `Verify successful`. See _jlink-common.sh for the rules. Not run on a board.
set -eu
# shellcheck source=_jlink-common.sh
. "$(dirname "$0")/_jlink-common.sh"
bench_prepare verify "$@"
bench_write_commands verify
bench_run verify
status=$BENCH_STATUS
if [ "${BENCH_PRINT_ONLY:-}" != 1 ] && [ "$status" -eq 0 ]; then
    grep -q 'Verify successful' "$BENCH_OUTPUT_FILE" || {
        printf 'boot-bench: the output has no "Verify successful" line\n' >&2
        status=1
    }
fi
bench_finish
exit "$status"
