#!/usr/bin/env bash
# ADR-0004 phase 1b (Experimental): the serial console with the first-account setup, started through the
# public composition interface <crux/cli_zephyr.h>, on native_sim. No hardware: it builds and runs a
# native_sim image and never flashes or resets anything.
#
#   tests/native/cli_console/run.sh
#
# 1. The static checks of tests/build/test_cli_zephyr_public.py and test_cli_console_fixture.py.
# 2. The fixture, on the Mbed profile: an application that names CONFIG_CRUX_CLI_CONSOLE, includes only
#    public headers and links only public targets. It builds, its five cases pass (the run has a time limit),
#    the configuration shows the console symbols, and the ELF defines the start and the event port.
# 3. The refusals: a console without Access, and a console beside a Zephyr shell, stop the configuration.
#
# CI runs this from scripts/test-management-module.sh, in the job of the Mbed profile, which has the mbedtls
# and tf-psa-crypto projects; so does any workspace that enables them. native_sim needs a Linux host.
set -euo pipefail

if [[ "$(uname -s)" != Linux ]]; then
    printf 'Run this script in the Linux Dev Container image.\n' >&2
    exit 2
fi

repo="$(git rev-parse --show-toplevel)"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
out="${CRUX_CONSOLE_OUTPUT:-$repo/build/cli-console}"
jobs="${CRUX_CONSOLE_JOBS:-4}"
board=native_sim/native/64
fixture="$repo/tests/native/cli_console"
profile="-DEXTRA_CONF_FILE=../tls_offload_probe/mbed.conf;../management_composition/profile-psa.conf;../management_composition/mbed-threading.conf"
export ZEPHYR_TOOLCHAIN_VARIANT="${ZEPHYR_TOOLCHAIN_VARIANT:-host}"

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

mkdir -p "$out"
python3 -m unittest discover -s "$repo/tests/build" -p test_cli_zephyr_public.py ||
    fail 'the static checks of the console interface'
python3 -m unittest discover -s "$repo/tests/build" -p test_cli_console_fixture.py ||
    fail 'the static checks of the console fixture'

build="$out/fixture"
(cd "$workspace" && west build -p always -b "$board" -d "$build" -o="-j$jobs" "$fixture" -- "$profile") \
    > "$out/fixture-build.log" 2>&1 || { tail -40 "$out/fixture-build.log" >&2; fail 'the fixture failed to build'; }
rm -f "$out/disk.bin"
# native_sim runs in real time here, so a hung image would otherwise hold the job until the runner's limit.
timeout -k 10 "${CRUX_CONSOLE_RUN_TIMEOUT:-300}" "$build/zephyr/zephyr.exe" --flash="$out/disk.bin" --seed=7 \
    > "$out/fixture-run.log" 2>&1 ||
    { tail -40 "$out/fixture-run.log" >&2; fail 'the fixture failed to run, or ran past its time limit'; }
grep -q 'PROJECT EXECUTION SUCCESSFUL' "$out/fixture-run.log" || fail 'the fixture did not report success'
grep -q 'pass = 5, fail = 0' "$out/fixture-run.log" || fail 'the fixture did not pass its five cases'
config="$build/zephyr/.config"
for symbol in CRUX_CLI_CONSOLE CRUX_CLI CRUX_SERIAL CRUX_ACCESS CRUX_THREAD CRUX_SYNC CRUX_TIME; do
    grep -qx "CONFIG_$symbol=y" "$config" || fail "CONFIG_$symbol is not set in the fixture's configuration"
done
grep -qx 'CONFIG_SHELL=n' "$config" || ! grep -q '^CONFIG_SHELL=y' "$config" || fail 'a Zephyr shell is enabled'
grep -qx 'CONFIG_CRUX_THREAD_STACK_BYTES=8192' "$config" || fail 'the console image did not get the 8192 default stack'
# The symbols are read into a variable before grep, never piped: grep -q ends at its first match, nm then gets
# SIGPIPE, and under pipefail the pipeline fails although the symbol is there.
fixture_symbols="$(nm "$build/zephyr/zephyr.elf")"
for entry in crux_cli_serial_start crux_cli_console_run crux_cli_port_event crux_access_provision_first_account; do
    grep -qE " [Tt] ${entry}\$" <<< "$fixture_symbols" || fail "the fixture's ELF does not define $entry"
done
printf 'ok: the fixture builds and passes its five cases, and the ELF defines the console start, the console, the event port and the first-account call\n'

# Each refusal is a configuration error before any compilation.
refuse() { # name expected-text extra-conf...
    local name="$1" text="$2"
    shift 2
    local conf="$out/refuse-$name.conf"
    printf '%s\n' "$@" > "$conf"
    if (cd "$workspace" && west build -p always -b "$board" -d "$out/refuse-$name" "$fixture" -- \
            "$profile;$conf") > "$out/refuse-$name.log" 2>&1; then
        fail "the configuration '$name' was accepted, and it must not be"
    fi
    grep -q "$text" "$out/refuse-$name.log" || { tail -20 "$out/refuse-$name.log" >&2; fail "'$name' failed for another reason"; }
}
# The text is the one of the fixture's own CMake check, not the symbol's name, which Kconfig's own warning
# prints too.
refuse no-access 'The fixture needs CONFIG_CRUX_CLI_CONSOLE' CONFIG_CRUX_ACCESS=n
refuse with-shell 'must not enable CONFIG_SHELL' CONFIG_SHELL=y CONFIG_SHELL_BACKEND_SERIAL=y
printf 'ok: a console without Access and a console beside a Zephyr shell are both refused at configuration\n'

# 4. The console and Logging on one UART (CONFIG_CRUX_CLI_CONSOLE_UART_SHARED, Experimental), with the progress
#    hook of the service threads: the fixture in shared/, which adds shared.conf and shared.overlay to the files
#    above. Its profile paths are absolute, because the fixture is one level deeper.
shared="$fixture/shared"
shared_profile="-DEXTRA_CONF_FILE=$repo/tests/native/tls_offload_probe/mbed.conf;$repo/tests/native/management_composition/profile-psa.conf;$repo/tests/native/management_composition/mbed-threading.conf"
build="$out/shared"
(cd "$workspace" && west build -p always -b "$board" -d "$build" -o="-j$jobs" "$shared" -- "$shared_profile") \
    > "$out/shared-build.log" 2>&1 || { tail -40 "$out/shared-build.log" >&2; fail 'the shared fixture failed to build'; }
rm -f "$out/shared-disk.bin"
timeout -k 10 "${CRUX_CONSOLE_RUN_TIMEOUT:-300}" "$build/zephyr/zephyr.exe" --flash="$out/shared-disk.bin" --seed=7 \
    > "$out/shared-run.log" 2>&1 ||
    { tail -40 "$out/shared-run.log" >&2; fail 'the shared fixture failed to run, or ran past its time limit'; }
grep -q 'PROJECT EXECUTION SUCCESSFUL' "$out/shared-run.log" || fail 'the shared fixture did not report success'
grep -q 'pass = 5, fail = 0' "$out/shared-run.log" || fail 'the shared fixture did not pass its five cases'
config="$build/zephyr/.config"
grep -qx 'CONFIG_CRUX_CLI_CONSOLE_UART_SHARED=y' "$config" || fail 'the shared fixture is not in the shared mode'
! grep -qx 'CONFIG_LOG_BACKEND_UART=y' "$config" || fail "the shared fixture kept Zephyr's UART backend"
printf 'ok: the console and Logging share one UART, and the service threads report progress\n'

refuse_shared() { # name expected-text extra-conf...
    local name="$1" text="$2"
    shift 2
    local conf="$out/refuse-$name.conf"
    printf '%s\n' "$@" > "$conf"
    if (cd "$workspace" && west build -p always -b "$board" -d "$out/refuse-$name" "$shared" -- \
            "$shared_profile;$conf") > "$out/refuse-$name.log" 2>&1; then
        fail "the configuration '$name' was accepted, and it must not be"
    fi
    grep -q "$text" "$out/refuse-$name.log" || { tail -20 "$out/refuse-$name.log" >&2; fail "'$name' failed for another reason"; }
}
refuse_shared shared-with-uart-backend 'requires CONFIG_LOG_BACKEND_UART=n' CONFIG_LOG_BACKEND_UART=y
refuse_shared shared-without-logging 'CONFIG_CRUX_CLI_CONSOLE_UART_SHARED needs CONFIG_CRUX_LOGGING' CONFIG_CRUX_LOGGING=n
printf "ok: a shared console beside Zephyr's UART backend, and one without Crux Logging, are both refused\n"
