#!/usr/bin/env bash
# Cross-build check of the serial console that shares its UART with Crux Logging
# (CONFIG_CRUX_CLI_CONSOLE_UART_SHARED, Experimental) on the RT1060-EVKB, with the console on LPUART1. It builds
# and inspects an image and never flashes or runs one: nothing here operates the board.
#
#   tests/zephyr/cli_console_shared_compile/run.sh
#
# 1. The fixture builds for CRUX_BOARD_TARGET (default and only board: mimxrt1060_evk@B//qspi). The resolved
#    configuration selects the shared mode and not Zephyr's UART backend or console, crux-serial0 is the board's
#    console UART, and the ELF defines the console, its start and the Logging backend.
# 2. The refusals on this board: Zephyr's UART console left on, as the board has it by default; Zephyr's UART log
#    backend beside the shared console; and a console rate that differs from the UART's.
#
# CI runs this from scripts/test-management-mbed-rt1060.sh build, which has the mbedtls and tf-psa-crypto projects.
set -euo pipefail

fixture="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$fixture/../../.." && pwd)"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
out="${CRUX_CONSOLE_SHARED_OUTPUT:-$repo/build/cli-console-shared-rt1060}"
jobs="${CRUX_CONSOLE_SHARED_JOBS:-4}"
# shellcheck source=../../../scripts/lib/board.sh
source "$repo/scripts/lib/board.sh"
supported='mimxrt1060_evk@B//qspi'
board="$(crux_board_target "$supported")"
crux_board_require "$board" "$supported"
profile="-DEXTRA_CONF_FILE=$repo/tests/psa_crypto/zephyr/tf-psa-crypto.conf;$repo/tests/native/management_composition/profile-psa.conf"

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

mkdir -p "$out"
build="$out/image"
(cd "$workspace" && west build -p always -b "$board" -d "$build" -o="-j$jobs" "$fixture" -- "$profile") \
    > "$out/build.log" 2>&1 || { tail -60 "$out/build.log" >&2; fail 'the shared console failed to build'; }

config="$build/zephyr/.config"
for line in CONFIG_CRUX_CLI_CONSOLE=y CONFIG_CRUX_CLI_CONSOLE_UART_SHARED=y CONFIG_CRUX_LOGGING_CONSOLE_BACKEND=y \
    CONFIG_CRUX_LOGGING=y CONFIG_CRUX_SERIAL=y CONFIG_CRUX_CLI_CONSOLE_BAUD_RATE=115200 \
    CONFIG_ENTROPY_MCUX_TRNG=y; do
    grep -qx "$line" "$config" || fail "the resolved configuration lacks $line"
done
for symbol in CONFIG_CRUX_CLI_CONSOLE_UART_DEDICATED CONFIG_LOG_BACKEND_UART CONFIG_UART_CONSOLE CONFIG_SHELL \
    CONFIG_TEST_RANDOM_GENERATOR; do
    ! grep -qx "${symbol}=y" "$config" || fail "the resolved configuration has $symbol=y"
done
for node in crux-serial0 zephyr,console; do
    grep -qE "^[[:space:]]*${node} = &lpuart1;" "$build/zephyr/zephyr.dts" || fail "$node is not LPUART1"
done

nm="$(sed -n 's/^CMAKE_NM:[A-Z]*=//p' "$build/CMakeCache.txt")"
[[ -n "$nm" ]] || fail 'no CMAKE_NM in the build'
# The symbols are read into a variable before grep, never piped: grep -q ends at its first match, nm then gets
# SIGPIPE, and under pipefail the pipeline fails although the symbol is there.
symbols="$("$nm" "$build/zephyr/zephyr.elf")"
# The console's start and loop, and the queue of the new backend.
for entry in crux_cli_serial_start crux_cli_console_run crux_log_queue_put; do
    grep -qE " [Tt] ${entry}\$" <<< "$symbols" || fail "the ELF does not define $entry"
done
# The log source that the console reads, and the backend that Zephyr's logging calls: both are data.
for entry in crux_logging_console crux_logging_console_backend; do
    grep -qE " [TtDdRr] ${entry}\$" <<< "$symbols" || fail "the ELF does not define $entry"
done
! grep -qE ' [A-Za-z] log_backend_uart' <<< "$symbols" || fail "Zephyr's UART backend is in the ELF"
printf 'ok: the shared console cross-builds for %s on LPUART1, and the ELF holds the console and the backend\n' "$board"

refuse() { # name, expected text, and the settings that make the build wrong
    local name="$1" text="$2" log="$out/refuse-$1.log"
    shift 2
    if (cd "$workspace" && west build -p always -b "$board" -d "$out/refuse-$name" -o="-j$jobs" "$fixture" -- \
            "$profile" "$@") > "$log" 2>&1; then
        fail "the configuration '$name' was accepted, and it must not be"
    fi
    grep -q "$text" "$log" || { tail -20 "$log" >&2; fail "'$name' failed for another reason"; }
    printf 'ok: %s is refused: %s\n' "$name" "$text"
}
# The Serial binding's check is at compilation; the other two stop the configuration.
refuse zephyr-console 'Crux Serial conflicts with UART Console' -DCONFIG_UART_CONSOLE=y
refuse uart-backend 'requires CONFIG_LOG_BACKEND_UART=n' -DCONFIG_UART_CONSOLE=y -DCONFIG_LOG_BACKEND_UART=y
refuse other-rate 'CONFIG_CRUX_CLI_CONSOLE_BAUD_RATE (9600) differs' -DCONFIG_CRUX_CLI_CONSOLE_BAUD_RATE=9600
printf 'ok: cross-build only. Nothing was flashed, and the shared console has not run on a board.\n'
