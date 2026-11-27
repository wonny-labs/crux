#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != Linux ]]; then
    printf 'Zephyr firmware builds are configured for Linux only; reopen this repository in the Dev Container.\n' >&2
    exit 2
fi
if [[ $# -ne 1 || -z "${1:-}" ]]; then
    printf 'Usage: %s <validated-board-target>\n' "$0" >&2
    exit 2
fi

repo="$(git rev-parse --show-toplevel)"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
board="$1"
build="$repo/build/zephyr/product-template"
if [[ ! -f "$workspace/.west/config" || ! -d "$workspace/zephyr" ]]; then
    printf 'Run scripts/bootstrap-zephyr.sh before building the product template.\n' >&2
    exit 2
fi

# These use real west on local repositories. The host CI job installs west and runs them too, without a Zephyr tree.
python="${CRUX_PYTHON:-python3}"
"$python" -m unittest discover -s "$repo/tests/build" -p test_crux_pins.py -v
"$python" -m unittest discover -s "$repo/tests/build" -p test_product_template.py -v
"$python" -m unittest discover -s "$repo/tests/build" -p test_product_driver_kit.py -v

# This runs the shipped command on a real Zephyr manifest: Crux's own workspace.
(cd "$workspace" && west crux-pins)

# This builds the application inside Crux's own workspace, not through the template's
# manifest. Build only: no debugger, serial transport, programming or reset.
export ZEPHYR_BASE="$workspace/zephyr"
(cd "$workspace" && west build -p always -b "$board" -d "$build" \
    "$repo/templates/product/app" -- -DZEPHYR_EXTRA_MODULES="$repo")
for output in zephyr.bin zephyr.meta; do
    if [[ ! -f "$build/zephyr/$output" ]]; then
        printf 'The product template build did not produce %s.\n' "$output" >&2
        exit 1
    fi
done

# The template is also a Zephyr module: an example driver with its emulator, an example board and
# tests. Twister finds the module through ZEPHYR_EXTRA_MODULES, here and when it lists boards.
template="$repo/templates/product"
unit_output="$repo/build/zephyr/twister-product-template-unit"
build_output="$repo/build/zephyr/twister-product-template-build"

# The unit tests of the example driver run on native_sim, against its emulator: the only place
# where the kit's tests run. Both native_sim platforms, because the guide names both.
(cd "$workspace" && ZEPHYR_EXTRA_MODULES="$template" west twister -j 2 \
    -p native_sim -p native_sim/native/64 -T "$template/tests" \
    -O "$unit_output" --inline-logs)

# A filtered or skipped scenario exits successfully with nothing run. Require every test case of
# the emulator scenario to have passed on both platforms.
"$python" - "$unit_output/twister.json" <<'PY'
import json
import sys

suites = [s for s in json.load(open(sys.argv[1]))['testsuites']
          if s['name'].endswith('example_temp.emul')]
platforms = sorted(s['platform'] for s in suites)
if platforms != ['native_sim/native', 'native_sim/native/64']:
    raise RuntimeError(f'The example driver tests did not run on both native_sim platforms: '
                       f'{[(s["platform"], s.get("status")) for s in suites]}')
for suite in suites:
    cases = suite.get('testcases', [])
    bad = [(c['identifier'], c.get('status')) for c in cases if c.get('status') != 'passed']
    if suite.get('status') != 'passed' or len(cases) < 10 or bad:
        raise RuntimeError(f'The example driver tests did not pass on {suite["platform"]}: '
                           f'status {suite.get("status")}, {len(cases)} cases, not passed: {bad}')
    print(f'Example driver tests passed on {suite["platform"]}: {len(cases)} test cases')
PY

# The hardware scenario is gated on a Twister fixture. This run names no fixture, no device and no
# hardware map, and adds --build-only: Twister builds the image for the vendor board and for the
# example board and runs nothing. A run on a board is a separate step with its own approval.
(cd "$workspace" && ZEPHYR_EXTRA_MODULES="$template" west twister -j 2 \
    -p 'mimxrt1060_evk@B/mimxrt1062/qspi' -p example_rt1062/mimxrt1062 -T "$template/tests" \
    --build-only -O "$build_output" --inline-logs)

"$python" - "$build_output/twister.json" <<'PY'
import json
import sys

suites = [s for s in json.load(open(sys.argv[1]))['testsuites']
          if s['name'].endswith('example_temp.hardware')]
platforms = sorted(s['platform'] for s in suites)
if platforms != ['example_rt1062/mimxrt1062', 'mimxrt1060_evk@B/mimxrt1062/qspi']:
    raise RuntimeError(f'The hardware scenario did not build on both boards: '
                       f'{[(s["platform"], s.get("status")) for s in suites]}')
# A build-only scenario that built reports "not run". A run would report passed or failed.
for suite in suites:
    if suite.get('status') != 'not run' or suite.get('runnable'):
        raise RuntimeError(f'The hardware scenario is not a built, unrun scenario on '
                           f'{suite["platform"]}: {suite.get("status")}, runnable {suite.get("runnable")}')
    print(f'Hardware scenario built, not run, on {suite["platform"]}')
PY

# The template README records an adapter that called kernel message queue functions and failed to
# link as a plain STATIC library. This probe links the same kind of adapter three ways for
# native_sim and checks the outcome that the driver guide states for each. Build only.
probe="$repo/tests/product_template_link"
for variant in app_sources plain_static module_library; do
    probe_build="$repo/build/zephyr/product-template-link-$variant"
    probe_log="$probe_build.log"
    mkdir -p "$(dirname "$probe_log")"
    set +e
    (cd "$workspace" && west build -p always -b native_sim -d "$probe_build" "$probe" -- \
        -DPROBE_VARIANT="$variant" -DZEPHYR_EXTRA_MODULES="$probe/module") >"$probe_log" 2>&1
    probe_status=$?
    set -e
    if [[ "$variant" == plain_static ]]; then
        if ((probe_status == 0)) || ! grep -Eq "undefined reference to .k_msgq_init" "$probe_log"; then
            cat "$probe_log" >&2
            printf 'Link probe %s: expected a link failure on k_msgq_init, got status %d.\n' \
                "$variant" "$probe_status" >&2
            exit 1
        fi
        printf 'Link probe %s: fails to link with an undefined k_msgq_init, as expected.\n' "$variant"
    else
        if ((probe_status != 0)); then
            cat "$probe_log" >&2
            printf 'Link probe %s: the build failed with status %d.\n' "$variant" "$probe_status" >&2
            exit 1
        fi
        printf 'Link probe %s: links.\n' "$variant"
    fi
done
printf 'Product template built for %s. No flash, reset, or hardware command was run.\n' "$board"
