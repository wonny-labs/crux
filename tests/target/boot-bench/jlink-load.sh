#!/usr/bin/env bash
# Program one file of <bench>/handoff/ at the address its name fixes. Used as the `flash` command of the
# device-control profile: <bench>/jlink-load.sh {image}. It resets and halts the target, then loads.
# A load is a pass only after a separate jlink-verify.sh run says `Verify successful`.
# See _jlink-common.sh for the rules. Not run on a board.
set -eu
# shellcheck source=_jlink-common.sh
. "$(dirname "$0")/_jlink-common.sh"
bench_prepare load "$@"
bench_write_commands load
bench_run load
bench_finish
exit "$BENCH_STATUS"
