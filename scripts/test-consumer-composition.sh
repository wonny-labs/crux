#!/usr/bin/env bash
# ADR-0004 T3 and T4 (Experimental): an application outside the Crux repository composes the management
# services with Kconfig and ZEPHYR_EXTRA_MODULES, and the checks of ADR-0004 section 5 hold. No hardware: it
# builds and runs native_sim images and never flashes or resets.
#
#   scripts/test-consumer-composition.sh
#
# 1. The Host checks of tests/build/test_consumer_composition.py.
# 2. The consumer, tests/consumer_composition, copied OUTSIDE the repository, built on native_sim with
#    -DZEPHYR_EXTRA_MODULES=<repo> -DCRUX_DIR=<repo>, run, and held to check_build.py: no include directory under
#    components/ that is not a public include root, only crux:: link targets, no frozen header, only the
#    service symbols of the Kconfig, and no wolfSSL, wolfSSH or wolfPSA symbol or option.
# 3. T4: each variant of tests/consumer_composition/variants.json, a one-line change to a fresh copy, must be
#    refused by those checks, and the baseline must pass them (the control that the checks are not vacuous).
#
# It needs the mbedtls and tf-psa-crypto projects, as scripts/test-management-module.sh does, and a Linux host.
set -euo pipefail

if [[ "$(uname -s)" != Linux ]]; then
    printf 'Run this script in the Linux Dev Container image.\n' >&2
    exit 2
fi

repo="$(git rev-parse --show-toplevel)"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
out="${CRUX_CONSUMER_OUTPUT:-$(mktemp -d)}"
jobs="${CRUX_CONSUMER_JOBS:-4}"
board=native_sim/native/64
variants="$repo/tests/consumer_composition/variants.json"
export ZEPHYR_TOOLCHAIN_VARIANT="${ZEPHYR_TOOLCHAIN_VARIANT:-host}"

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

case "$out" in "$repo"/*) fail "the output directory must be outside the repository: $out" ;; esac
mkdir -p "$out"
python3 -m unittest discover -s "$repo/tests/build" -p test_consumer_composition.py ||
    fail 'the Host checks of the consumer composition'

# A fresh copy of the consumer, outside the repository: its sources must not be under it.
copy() { # destination
    mkdir -p "$1"
    cp -R "$repo/tests/consumer_composition/app" "$repo/tests/consumer_composition/domain" "$1/"
    case "$(cd "$1" && pwd -P)" in "$(cd "$repo" && pwd -P)"/*) fail "the copy is inside the repository: $1" ;; esac
}
configure() { # copy, build directory, extra west arguments
    (cd "$workspace" && west build -p always -b "$board" -d "$2" "$1/app" "${@:3}" -- \
        "-DZEPHYR_EXTRA_MODULES=$repo" "-DCRUX_DIR=$repo")
}
field() { # index, field name
    python3 -c "import json,sys; print(json.load(open(sys.argv[1]))[int(sys.argv[2])][sys.argv[3]])" \
        "$variants" "$1" "$2"
}

baseline="$out/baseline"
copy "$baseline/source"
configure "$baseline/source" "$baseline/build" -o="-j$jobs" > "$out/baseline-build.log" 2>&1 ||
    { tail -40 "$out/baseline-build.log" >&2; fail 'the consumer failed to build'; }
timeout -k 10 "${CRUX_CONSUMER_RUN_TIMEOUT:-300}" "$baseline/build/zephyr/zephyr.exe" \
    --flash="$out/disk.bin" --seed=7 > "$out/baseline-run.log" 2>&1 ||
    { tail -40 "$out/baseline-run.log" >&2; fail 'the consumer failed to run, or ran past its time limit'; }
grep -q 'PROJECT EXECUTION SUCCESSFUL' "$out/baseline-run.log" || fail 'the consumer did not report success'
python3 "$repo/tests/consumer_composition/check_build.py" build "$baseline/source" "$baseline/build" "$repo" ||
    fail 'the consumer is refused by its own checks'
printf 'ok: the consumer builds outside the repository, runs, and passes the checks of ADR-0004 section 5\n'

# T4: each variant must be refused, for its own reason.
count="$(python3 -c "import json,sys; print(len(json.load(open(sys.argv[1]))))" "$variants")"
for ((index = 0; index < count; index++)); do
    name="$(field "$index" name)"
    expect="$(field "$index" expect)"
    variant="$out/variant-$name"
    copy "$variant/source"
    python3 - "$repo" "$variant/source" "$index" << 'PY'
import json
import sys

sys.path.insert(0, sys.argv[1] + "/tests/consumer_composition")
import check_build

variants = json.load(open(sys.argv[1] + "/tests/consumer_composition/variants.json"))
check_build.apply_variant(sys.argv[2], variants[int(sys.argv[3])])
PY
    # Configure only: the checks read the compile commands and the sources, and need no image.
    if configure "$variant/source" "$variant/build" --cmake-only > "$out/variant-$name.log" 2>&1; then
        log="$out/variant-$name-check.log"
        if python3 "$repo/tests/consumer_composition/check_build.py" build "$variant/source" "$variant/build" \
            "$repo" > "$log" 2>&1; then
            fail "T4: variant $name was accepted"
        fi
        grep -q "$expect" "$log" || { cat "$log" >&2; fail "T4: variant $name was refused, but not with: $expect"; }
    else
        grep -q "$expect" "$out/variant-$name.log" || { tail -20 "$out/variant-$name.log" >&2
            fail "T4: variant $name failed to configure, not with: $expect"; }
    fi
    printf 'ok: T4 %s is refused: %s\n' "$name" "$expect"
done
printf 'Consumer composition finished. Native_sim only: no board was built or run.\n'
