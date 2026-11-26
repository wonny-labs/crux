#!/usr/bin/env bash
# The TCP initial sequence number of default images when the key read or the hash fails, on native_sim
# (patches/zephyr/tcp-isn-fail-closed.patch, patches/zephyr/README.md). It never flashes, resets or runs
# anything on a board.
#
#   scripts/test-tcp-isn.sh [default|upstream|drift|all]
#
#   default:  tests/native/tcp_isn with the Crux module, which replaces tcp.c. A failed key read or hash
#             must refuse the connection, and a working one must give a keyed number.
#   upstream: the same application without the Crux module, on upstream tcp.c (the negative control). It
#             must fail, with the sys_rand32_get() fallback the patch is for.
#   drift:    a copy of the pinned tree with one changed byte in tcp.c. Configuration with the Crux
#             module must stop.
#   all:      the prepare test, then the three, one after another (default).
# It needs a Linux host or the Dev Container, Zephyr at its pin, and mbedtls and tf-psa-crypto at theirs
# (the optional west group). CRUX_WORKSPACE names the workspace and CRUX_SSH_MODULES a folder that holds
# mbedtls and tf-psa-crypto when they are not under modules/crypto of the workspace. CRUX_TCP_ISN_OUTPUT
# is the output folder (default build/tcp-isn in the repository) and CRUX_TCP_ISN_JOBS the build's
# parallelism (default 2).
set -euo pipefail

mode="${1:-all}"
case "$mode" in default | upstream | drift | all) ;; *)
    printf 'usage: %s [default|upstream|drift|all]\n' "$0" >&2
    exit 2
    ;;
esac

repo="$(git rev-parse --show-toplevel)"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
out="${CRUX_TCP_ISN_OUTPUT:-$repo/build/tcp-isn}"
jobs="${CRUX_TCP_ISN_JOBS:-2}"
crypto="${CRUX_SSH_MODULES:-$workspace/modules/crypto}"
source_dir="$repo/tests/native/tcp_isn"
board='native_sim/native/64'

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

[[ "$(uname -s)" == Linux ]] || { printf 'Run this script in the Linux Dev Container image.\n' >&2; exit 2; }

pinned_revision() { # project name in west.yml
    awk -v name="$1" '$1 == "-" && $2 == "name:" { in_project = ($3 == name) }
        in_project && $1 == "revision:" { print $2; exit }' "$repo/west.yml"
}

check_pins() {
    local module
    [[ "$(git -C "$workspace/zephyr" rev-parse HEAD)" == "$(pinned_revision zephyr)" ]] ||
        fail 'the Zephyr checkout is not at the pin of west.yml'
    for module in mbedtls tf-psa-crypto; do
        [[ -e "$crypto/$module/.git" ]] ||
            fail "$module is missing. Enable the optional stacks: west config manifest.group-filter -- +crux-secure-management && west update"
        [[ "$(git -C "$crypto/$module" rev-parse HEAD)" == "$(pinned_revision "$module")" ]] ||
            fail "$module is not at the pin of west.yml"
    done
}

configure() { # variant ZEPHYR_BASE ZEPHYR_MODULES
    local variant="$1" base="$2" modules="$3"
    rm -rf "${out:?}/$variant"
    mkdir -p "$out"
    ZEPHYR_TOOLCHAIN_VARIANT=host ZEPHYR_BASE="$base" cmake -S "$source_dir" -B "$out/$variant" -G Ninja \
        -DBOARD="$board" "-DZEPHYR_MODULES=$modules" "-DPython3_EXECUTABLE=$(command -v python3)" \
        > "$out/$variant-configure.log" 2>&1
}

build_and_run() { # variant ZEPHYR_MODULES
    local variant="$1" build="$out/$1" status=0
    configure "$variant" "$workspace/zephyr" "$2" ||
        { tail -30 "$out/$variant-configure.log" >&2; fail "$variant: the configuration failed"; }
    ninja -C "$build" -j "$jobs" > "$out/$variant-build.log" 2>&1 ||
        { grep -E 'error|FAILED' "$out/$variant-build.log" | head -20 >&2; fail "$variant: the build failed"; }
    grep -q '^CONFIG_NET_TCP_ISN_RFC6528=y' "$build/zephyr/.config" || fail "$variant: the RFC 6528 sequence number is not on"
    grep -q '^CONFIG_NET_NATIVE_TCP=y' "$build/zephyr/.config" || fail "$variant: Zephyr's own TCP is not built"
    ! grep -q '^CONFIG_NET_TEST=y' "$build/zephyr/.config" || fail "$variant: NET_TEST skips tcp_init_isn()"
    timeout 300 "$build/zephyr/zephyr.exe" > "$out/$variant-run.txt" 2>&1 || status=$?
    grep -E 'ISN-REPORT|FAIL|PASS|PROJECT EXECUTION|Assertion|Expectation|expected' "$out/$variant-run.txt" || true
    return "$status"
}

# Which tcp.c the build compiled: the build-local copy, or the one in the Zephyr checkout.
compiled_tcp() { # variant
    python3 - "$out/$1/compile_commands.json" "$workspace/zephyr/subsys/net/ip/tcp.c" "$out/$1" <<'PY'
import json, os, sys
entries = json.load(open(sys.argv[1]))
tcp = [os.path.normpath(os.path.join(e["directory"], e["file"])) for e in entries if os.path.basename(e["file"]) == "tcp.c"]
build = os.path.normpath(sys.argv[3]) + os.sep
if tcp == [os.path.normpath(sys.argv[2])]:
    print("upstream")
elif len(tcp) == 1 and tcp[0].startswith(build) and tcp[0].endswith("/crux-tcp-isn/tcp.c"):
    print("local")
else:
    print("other: %s" % tcp)
PY
}

default_run() {
    local status=0 log="$out/default-run.txt" compiled
    printf '== default image: the Crux module replaces tcp.c\n'
    build_and_run default "$repo;$crypto/mbedtls;$crypto/tf-psa-crypto" || status=$?
    compiled="$(compiled_tcp default)"
    [[ "$compiled" == local ]] || fail "default: the image did not compile the build-local tcp.c ($compiled)"
    local record
    record="$(find "$out/default" -path '*/crux-tcp-isn/tcp.json' -print -quit)"
    if [[ -z "$record" ]] || ! grep -q '"patch_applied": true' "$record"; then
        fail 'default: the record of the build-local tcp.c is missing or says the patch was not applied'
    fi
    [[ "$status" -eq 0 ]] || fail "default: the cases failed (exit $status), see $log"
    grep -q 'ISN-REPORT phase=A-read-fails path=passive sent=RST' "$log" || fail 'default: no RST for a SYN with a failed key read'
    grep -q 'ISN-REPORT phase=A-read-fails path=active sent=nothing isn=- connect=-5' "$log" ||
        fail 'default: the connect with a failed key read was not refused with -EIO and no SYN'
    grep -q 'ISN-REPORT phase=C-hash-fails path=passive sent=RST' "$log" || fail 'default: no RST for a SYN with a failed hash'
    grep -q 'ISN-REPORT phase=C-hash-fails path=active sent=nothing isn=- connect=-5' "$log" ||
        fail 'default: the connect with a failed hash was not refused with -EIO and no SYN'
    local phase
    for phase in B-read-works D-hash-works; do
        grep -q "ISN-REPORT phase=$phase path=passive sent=SYN|ACK isn=keyed" "$log" || fail "default: $phase: no keyed SYN|ACK"
        grep -q "ISN-REPORT phase=$phase path=active sent=SYN isn=keyed" "$log" || fail "default: $phase: no keyed SYN from a connect"
    done
    printf 'default image: a failed key read or hash refuses, and a working one gives a keyed number\n'
}

upstream_run() {
    local status=0 log="$out/upstream-run.txt" compiled
    printf '== upstream tcp.c, without the Crux module (the negative control)\n'
    build_and_run upstream "$crypto/mbedtls;$crypto/tf-psa-crypto" || status=$?
    compiled="$(compiled_tcp upstream)"
    [[ "$compiled" == upstream ]] || fail "upstream: the control did not compile the checkout's tcp.c ($compiled)"
    [[ "$status" -ne 0 ]] || fail 'upstream: the cases PASSED on upstream tcp.c, so the test does not show the fallback'
    # The control must fail for the reason the patch is for, the sys_rand32_get() fallback, and not another.
    grep -q 'ISN-REPORT phase=A-read-fails path=passive sent=SYN|ACK isn=unkeyed' "$log" ||
        fail 'upstream: the SYN with a failed key read was not answered with an unkeyed SYN|ACK'
    grep -q 'ISN-REPORT phase=A-read-fails path=active sent=SYN isn=unkeyed' "$log" ||
        fail 'upstream: the connect with a failed key read did not send an unkeyed SYN'
    grep -q 'ISN-REPORT phase=C-hash-fails path=passive sent=SYN|ACK isn=unkeyed' "$log" ||
        fail 'upstream: the SYN with a failed hash was not answered with an unkeyed SYN|ACK'
    grep -q 'ISN-REPORT phase=C-hash-fails path=active sent=SYN isn=unkeyed' "$log" ||
        fail 'upstream: the connect with a failed hash did not send an unkeyed SYN'
    grep -q 'ISN-REPORT phase=B-read-works path=passive sent=SYN|ACK isn=keyed' "$log" ||
        fail 'upstream: the control does not key the number when the read works, so it does not show what it should'
    printf 'negative control as expected (exit %s): upstream falls back to sys_rand32_get()\n' "$status"
}

drift_run() {
    local copy="$out/zephyr-drift"
    printf '== a tcp.c that is not the pinned one\n'
    rm -rf "$copy"
    mkdir -p "$copy"
    git -C "$workspace/zephyr" archive HEAD ':!doc' ':!samples' ':!tests' | tar -x -C "$copy"
    printf '/* drift */\n' >> "$copy/subsys/net/ip/tcp.c"
    if configure drift "$copy" "$repo;$crypto/mbedtls;$crypto/tf-psa-crypto"; then
        rm -rf "$copy"
        fail 'drift: the configuration accepted a tcp.c that is not the pinned one'
    fi
    rm -rf "$copy"
    grep -q 'FAIL: .*tcp.c is not the tcp.c of the pinned Zephyr' "$out/drift-configure.log" ||
        { tail -20 "$out/drift-configure.log" >&2; fail 'drift: the configuration stopped for another reason'; }
    printf 'drift: the configuration stopped\n'
}

check_pins
case "$mode" in all)
    ZEPHYR_BASE="$workspace/zephyr" python3 "$repo/tests/native/tcp_isn/test_prepare.py" -v
    ;;
esac
case "$mode" in default | all) default_run ;; esac
case "$mode" in upstream | all) upstream_run ;; esac
case "$mode" in drift | all) drift_run ;; esac
printf 'TCP ISN test (%s): native_sim only. No board was operated.\n' "$mode"
