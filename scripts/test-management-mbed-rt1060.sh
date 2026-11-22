#!/usr/bin/env bash
# Cross-build check of the RT1060-EVK Rev B management image on the Mbed TLS profile
# (samples/boards/nxp/mimxrt1060_evk/web_management, docs/rt1060-mbed-management-image.md). It builds and inspects images and
# never flashes, resets or runs one: nothing here operates the board.
#
#   scripts/test-management-mbed-rt1060.sh [static|build|all]
#
# static: the Host checks of tests/build/test_management_mbed_rt1060_image.py. No Zephyr workspace needed.
# build:  two cross-builds for mimxrt1060_evk@B//qspi in the Linux Dev Container, with the mbedtls and tf-psa-crypto
#         projects enabled (`west config manifest.project-filter -- +mbedtls,+tf-psa-crypto`, as the psa-crypto
#         workflow does):
#           default: the form that is off by default. Checks the resolved configuration (Mbed profile, the TRNG driver,
#                    no test entropy, no Wolf, no SSH, no card driver, the first-account form not set), the linked ELF
#                    (the services, the listener and the certificate module are defined, no Wolf or SSH symbol, no
#                    embedded password), that the fail-closed entropy source was applied, and prints the sizes.
#           test:    the first-account form on, with a password file made here outside the repository: the embedded
#                    password is in the binary and in no text file of the build. And two refusals at configuration:
#                    the form with no password file, and with a file inside the repository.
# all:    static, then build.
set -euo pipefail

mode="${1:-all}"
case "$mode" in static | build | all) ;; *)
    printf 'usage: %s [static|build|all]\n' "$0" >&2
    exit 2
    ;;
esac

repo="$(git rev-parse --show-toplevel)"
fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

run_static() {
    python3 -m unittest discover -s "$repo/tests/build" -p test_management_mbed_rt1060_image.py ||
        fail 'the static checks of the image'
}

run_build() {
    if [[ "$(uname -s)" != Linux ]]; then
        printf 'Run the build in the Linux Dev Container image.\n' >&2
        exit 2
    fi
    local workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
    local out="${CRUX_MBED_MGMT_OUTPUT:-$repo/build/management-mbed-rt1060}"
    local jobs="${CRUX_MBED_MGMT_JOBS:-4}"
    local board='mimxrt1060_evk@B//qspi'
    local sample="$repo/samples/boards/nxp/mimxrt1060_evk/web_management"
    local default="$out/default" test_build="$out/test-form"
    mkdir -p "$out"
    # Pristine build directories: west -p always cleans a directory that holds a build, and these are ours.
    # Never inherit a password file: the default build must not need one.
    (cd "$workspace" && env -u CRUX_MBED_MGMT_PASSWORD_FILE west build -p always -b "$board" -d "$default" \
        -o="-j$jobs" "$sample") > "$out/default-build.log" 2>&1 ||
        { tail -60 "$out/default-build.log" >&2; fail 'the default image failed to build'; }
    local config="$default/zephyr/.config" elf="$default/zephyr/zephyr.elf" line
    for line in CONFIG_PSA_CRYPTO_PROVIDER_MBEDTLS=y CONFIG_MBEDTLS=y CONFIG_ENTROPY_MCUX_TRNG=y \
        CONFIG_MBEDTLS_PSA_DRIVER_GET_ENTROPY=y CONFIG_CRUX_ACCESS=y CONFIG_CRUX_WEB=y CONFIG_CRUX_WEB_SESSION=y \
        CONFIG_CRUX_WEB_MANAGEMENT=y CONFIG_CRUX_TLS_CERTIFICATE=y CONFIG_CRUX_REBOOT=y CONFIG_CRUX_LOGGING=y \
        CONFIG_CRUX_FILE_FATFS_RT1060_RAM_DISK=y; do
        grep -qx "$line" "$config" || fail "the resolved configuration lacks $line"
    done
    local absent
    for absent in CONFIG_WOLFSSL CONFIG_WOLFSSH CONFIG_WOLFPSA CONFIG_CRUX_SSH CONFIG_TEST_RANDOM_GENERATOR \
        CONFIG_FAKE_ENTROPY_NATIVE_SIM CONFIG_DISK_DRIVER_SDMMC CONFIG_IMX_USDHC CONFIG_CRUX_WEB_PLAIN_HTTP_FOR_TESTS \
        CONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT CONFIG_SHELL; do
        ! grep -qE "^${absent}=y" "$config" || fail "the resolved configuration has $absent=y"
    done
    # The fail-closed copy of Zephyr's Mbed TLS entropy glue was generated.
    find "$default" -path '*crux-mbedtls/zephyr_entropy.c' | grep -q . ||
        fail 'the fail-closed entropy source was not generated'

    local nm
    nm="$(sed -n 's/^CMAKE_NM:[A-Z]*=//p' "$default/CMakeCache.txt")"
    [[ -n "$nm" ]] || fail 'no CMAKE_NM in the build'
    # The symbols are read into a variable before grep, never piped: grep -q ends at its first match, nm then gets
    # SIGPIPE, and under pipefail the pipeline fails although the symbol is there.
    local symbols entry
    symbols="$("$nm" "$elf")"
    for entry in crux_access_init crux_credential_start crux_security_event_start crux_tls_certificate_start \
        crux_web_start crux_web_session_init crux_web_management_init crux_reboot_start crux_file_service_start \
        crux_config_service_start crux_mgmt_status_start crux_network_settings_boot; do
        grep -qE " [Tt] ${entry}\$" <<< "$symbols" || fail "the ELF does not define $entry"
    done
    ! grep -qE ' [A-Za-z] (wolfSSL_|wc_|wolfSSH_|crux_ssh_)' <<< "$symbols" || fail 'a Wolf or SSH symbol is in the ELF'
    ! grep -q 'crux_mbed_mgmt_test_password' <<< "$symbols" || fail 'the default image holds the embedded password'
    printf 'ok: default image, Mbed profile, TRNG, fail-closed entropy, no Wolf or SSH, no test form\n'
    local size_tool="${nm%-nm}-size"
    if [[ -x "$size_tool" ]]; then
        "$size_tool" "$elf"
    fi

    # The test form: a password file outside the repository, made here.
    local scratch password_file password
    scratch="$(mktemp -d)"
    local inside="$repo/build/management-mbed-rt1060-inside-password"
    # Whatever happens next, no copy of the test password stays behind.
    # The trap reads script-level copies of the paths: the locals are gone when the script exits.
    trap 'rm -rf -- "$cleanup_scratch" "$cleanup_inside"' EXIT
    cleanup_scratch="$scratch"
    cleanup_inside="$inside"
    password_file="$scratch/password"
    (umask 077 && head -c 24 /dev/urandom | base64 | tr -d '\n' > "$password_file")
    password="$(cat "$password_file")"
    (cd "$workspace" && CRUX_MBED_MGMT_PASSWORD_FILE="$password_file" west build -p always -b "$board" \
        -d "$test_build" -o="-j$jobs" "$sample" -- -DCONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT=y) \
        > "$out/test-form-build.log" 2>&1 ||
        { tail -60 "$out/test-form-build.log" >&2; fail 'the image with the test first account failed to build'; }
    grep -qx 'CONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT=y' "$test_build/zephyr/.config" ||
        fail 'the test form was not set in the build that asked for it'
    symbols="$("$nm" "$test_build/zephyr/zephyr.elf")"
    grep -q ' crux_mbed_mgmt_test_password$' <<< "$symbols" || fail 'the test form holds no embedded password'
    grep -q -a -F -- "$password" "$test_build/zephyr/zephyr.bin" ||
        fail 'the embedded password is not in the binary, so the check below would mean nothing'
    # The plaintext is in the binary, and in no text file of the build, its logs or its configuration.
    if grep -rIl -F -- "$password" "$test_build" "$out"/*.log 2> /dev/null | grep -q .; then
        fail 'the password is in a text file of the build'
    fi
    printf 'ok: test form builds, the password is in the binary and in no text file\n'

    # Refusals at configuration, never at run time.
    refuse() { # label, expected text, and the environment of the build
        local label="$1" text="$2"
        shift 2
        if (cd "$workspace" && env "$@" west build -p always -b "$board" -d "$out/refuse" "$sample" \
            -- -DCONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT=y) > "$out/refuse.log" 2>&1; then
            fail "$label was accepted"
        fi
        grep -q "$text" "$out/refuse.log" || { tail -20 "$out/refuse.log" >&2; fail "$label stopped, but not with: $text"; }
        printf 'ok: %s is refused\n' "$label"
    }
    refuse 'the test form with no password file' 'needs the environment variable' -u CRUX_MBED_MGMT_PASSWORD_FILE
    mkdir -p "$(dirname "$inside")"
    cp "$password_file" "$inside"
    refuse 'a password file inside the repository' 'inside the repository' "CRUX_MBED_MGMT_PASSWORD_FILE=$inside"
}

case "$mode" in static | all) run_static ;; esac
case "$mode" in build | all) run_build ;; esac
