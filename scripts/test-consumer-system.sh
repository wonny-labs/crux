#!/usr/bin/env bash
# ADR-0005 T3, T4 and T5: build the out-of-tree System consumer (tests/consumer_system) from a copy outside the
# repository on native_sim, run it, and apply the checks of check_build.py. Build and run on the host only: no
# board, programming, reset or hardware command. A simulated watchdog is not hardware evidence.
set -euo pipefail

if [[ "$(uname -s)" != Linux ]]; then
    printf 'Zephyr native_sim builds are configured for Linux only; reopen this repository in the Dev Container.\n' >&2
    exit 2
fi

repo="$(git rev-parse --show-toplevel)"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
fixture="$repo/tests/consumer_system"
board='native_sim/native/64'
if [[ ! -f "$workspace/.west/config" || ! -d "$workspace/zephyr" ]]; then
    printf 'Run scripts/bootstrap-zephyr.sh before building the System consumer.\n' >&2
    exit 2
fi
export ZEPHYR_BASE="$workspace/zephyr"
python="${CRUX_PYTHON:-python3}"

# The consumer is built from a copy outside the repository, so that it cannot read the repository by a
# relative path. The Crux module is found through ZEPHYR_EXTRA_MODULES, as a product does.
work="$(mktemp -d "${TMPDIR:-/tmp}/crux-consumer-system.XXXXXX")"
trap 'rm -rf "$work"' EXIT
if [[ "$work/" == "$repo/"* ]]; then
    printf 'The work directory %s is inside the repository %s; set TMPDIR to a directory outside it.\n' "$work" "$repo" >&2
    exit 2
fi

build() { # build <copy> <build-dir> [--cmake-only] [extra cmake args...]
    local copy="$1" dir="$2" mode="$3"
    shift 3
    local args=("$@")
    local only=()
    [[ "$mode" == cmake-only ]] && only=(--cmake-only)
    (cd "$workspace" && west build -p always "${only[@]}" -b "$board" -d "$dir" "$copy/app" -- \
        -DZEPHYR_EXTRA_MODULES="$repo" -DCMAKE_EXPORT_COMPILE_COMMANDS=ON "${args[@]}")
}

# T3: the simulated watchdog on. Build, check, run.
cp -R "$fixture" "$work/on"
build "$work/on" "$work/build-on" full
"$python" "$work/on/check_build.py" build "$work/on" "$work/build-on" "$repo" on
"$python" "$work/on/check_build.py" run "$work/build-on/zephyr/zephyr.exe"

# T5: the symbol off (nothing else changes). No simulated device in the image and no symbol in .config.
cp -R "$fixture" "$work/off"
build "$work/off" "$work/build-off" full -DCONFIG_CRUX_SYSTEM_NATIVE_SIM_WATCHDOG=n
"$python" "$work/off/check_build.py" build "$work/off" "$work/build-off" "$repo" off

# T4: each variant is one change to a fresh copy and must be refused by a check. A variant is configured only
# (no compile), so that the refusal is the check's and not a compiler error.
count="$("$python" -c 'import json,sys; print(len(json.load(open(sys.argv[1]))))' "$fixture/variants.json")"
for ((index = 0; index < count; ++index)); do
    name="$("$python" -c 'import json,sys; print(json.load(open(sys.argv[1]))[int(sys.argv[2])]["name"])' \
        "$fixture/variants.json" "$index")"
    copy="$work/variant-$name"
    cp -R "$fixture" "$copy"
    "$python" - "$copy" "$fixture/variants.json" "$index" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1])))
import check_build
check_build.apply_variant(sys.argv[1], json.load(open(sys.argv[2]))[int(sys.argv[3])])
PY
    expect="$("$python" -c 'import json,sys; print(json.load(open(sys.argv[1]))[int(sys.argv[2])]["expect"])' \
        "$fixture/variants.json" "$index")"
    # The checks of the consumer's own text need no build. Only a variant they let through is configured
    # (no compile), so that the refusal is the check's and not a compiler error.
    if output="$("$python" "$copy/check_build.py" sources "$copy")"; then
        build "$copy" "$work/build-variant-$name" cmake-only -DCRUX_DIR="$repo"
        if output="$("$python" "$copy/check_build.py" build "$copy" "$work/build-variant-$name" "$repo" on)"; then
            printf 'Variant %s was not refused.\n%s\n' "$name" "$output" >&2
            exit 1
        fi
    fi
    if ! grep -qF -- "$expect" <<<"$output"; then
        printf 'Variant %s was refused for another reason (wanted: %s).\n%s\n' "$name" "$expect" "$output" >&2
        exit 1
    fi
    printf 'Variant %s refused: %s\n' "$name" "$expect"
done
printf 'System consumer: on native_sim, build, run and %s variants. No hardware command was run.\n' "$count"
