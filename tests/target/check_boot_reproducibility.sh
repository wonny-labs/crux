#!/usr/bin/env bash
# Compare two builds of the boot composition (docs/boot-composition.md) for reproducibility, and run
# imgtool verify on both signed images. What "reproducible" means is in docs/boot-reproducibility.md:
# the unsigned binaries are byte-identical, and a signed image differs at most in its randomised ECDSA
# signature (Stage 8 of the boot and update investigation). The comparison is tests/target/
# compare_boot_builds.py.
#
# Two ways to get the two builds:
#   check_boot_reproducibility.sh [--strict-signature] BUILD_A BUILD_B
#       compares two existing build directories of the composition, for example two runs in different
#       checkouts (a different build path is the stronger test).
#   check_boot_reproducibility.sh [--strict-signature] --build [BUILD_DIR]
#       runs the composition command (scripts/test-boot-composition.sh, or CRUX_COMPOSITION_COMMAND), moves
#       its build directory (default $repo/build/zephyr/boot-composition) to BUILD_DIR.first, runs it a
#       second time and compares the two. Both builds use the same path, so this does not test path
#       independence. The composition command changes the local workspace as its own header says, and runs
#       twice (each run is a full sysbuild).
#
# The script generates no key, programs and boots nothing, and reads the build directories and the MCUboot
# checkout. In --build mode it writes BUILD_DIR.first and whatever the composition command writes.
# It is NOT wired into any workflow: a step in .github/workflows/zephyr.yml is a protected-file change that
# needs the project owner's approval (proposal: docs/boot-reproducibility.md).
# It has never run on a real build. The host tests in tests/build/test_check_boot_reproducibility.py run
# it against fake build trees, a fake imgtool and a fake composition command only.
#
# Environment: CRUX_PYTHON (python3 by default), CRUX_WORKSPACE (the parent of the repository by default,
# where bootloader/mcuboot is checked out), CRUX_COMPOSITION_COMMAND (--build only).
# Exit status: 0 reproducible and both signed images verify, 1 not reproducible, imgtool refuses or crashes
# on a signed image, 2 the inputs or a tool cannot be used (a missing directory, Python, imgtool or key,
# imgtool without its requirements, the same directory twice, a failing composition command, an existing
# BUILD_DIR.first).
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
python="${CRUX_PYTHON:-python3}"
mcuboot="$workspace/bootloader/mcuboot"
key="$mcuboot/root-ec-p256.pem"
imgtool=("$python" "$mcuboot/scripts/imgtool.py")
compare=("$python" "$repo/tests/target/compare_boot_builds.py")
default_build="$repo/build/zephyr/boot-composition"
image="$(basename "$repo/samples/controller/zephyr")"

fail() {
    printf 'boot reproducibility check failed: %s\n' "$1" >&2
    exit 1
}

missing() {
    printf 'boot reproducibility check: %s\n' "$1" >&2
    exit 2
}

usage() {
    printf 'Usage: %s [--strict-signature] BUILD_A BUILD_B\n       %s [--strict-signature] --build [BUILD_DIR]\n(--build runs scripts/test-boot-composition.sh twice; BUILD_A and BUILD_B are two existing build directories of the composition)\n' \
        "$0" "$0" >&2
    exit 2
}

strict=()
build_mode=0
positional=()
for argument in "$@"; do
    case "$argument" in
        --strict-signature) strict=(--strict-signature) ;;
        --build) build_mode=1 ;;
        -*) usage ;;
        *) positional+=("$argument") ;;
    esac
done
if [[ "$build_mode" -eq 1 ]]; then
    [[ "${#positional[@]}" -le 1 ]] || usage
else
    [[ "${#positional[@]}" -eq 2 ]] || usage
fi

command -v "$python" >/dev/null 2>&1 || missing "Python is not available as $python (set CRUX_PYTHON)"
[[ -f "$repo/tests/target/compare_boot_builds.py" ]] || missing "the comparison tool tests/target/compare_boot_builds.py is missing"
[[ -f "$mcuboot/scripts/imgtool.py" ]] || missing "imgtool is not in the MCUboot checkout: $mcuboot/scripts/imgtool.py (run scripts/test-boot-composition.sh first)"
[[ -f "$key" ]] || missing "the MCUboot test key is not in the checkout: $key (run scripts/test-boot-composition.sh first)"
# imgtool imports packages that the Zephyr requirements do not list. Without them it ends in a traceback,
# which is a missing tool and not a verdict on an image.
if ! imgtool_help="$("${imgtool[@]}" --help 2>&1)" || grep -q Traceback <<<"$imgtool_help"; then
    missing "imgtool does not run (install the requirements of $mcuboot/scripts/requirements.txt): $(grep -v '^$' <<<"$imgtool_help" | tail -n 1)"
fi

if [[ "$build_mode" -eq 1 ]]; then
    build_b="${positional[0]:-$default_build}"
    build_a="$build_b.first"
    command_path="${CRUX_COMPOSITION_COMMAND:-$repo/scripts/test-boot-composition.sh}"
    [[ -x "$command_path" ]] || missing "the composition command is not executable: $command_path"
    [[ ! -e "$build_a" ]] || missing "$build_a exists already; remove it first, so that an old build is not compared"
    status=0
    "$command_path" || status=$?
    [[ "$status" -eq 0 ]] || missing "the composition command $command_path failed (exit $status) on the first run"
    [[ -d "$build_b" ]] || missing "the composition command left no build directory at $build_b"
    mv "$build_b" "$build_a"
    status=0
    "$command_path" || status=$?
    [[ "$status" -eq 0 ]] || missing "the composition command $command_path failed (exit $status) on the second run"
    [[ -d "$build_b" ]] || missing "the composition command left no build directory at $build_b on the second run"
else
    build_a="${positional[0]}"
    build_b="${positional[1]}"
    [[ -d "$build_a" ]] || missing "$build_a is not a build directory. Run scripts/test-boot-composition.sh and keep its build directory, or use --build to build twice."
    [[ -d "$build_b" ]] || missing "$build_b is not a build directory. Run scripts/test-boot-composition.sh and keep its build directory, or use --build to build twice."
fi

compare_status=0
compare_output="$("${compare[@]}" --image "$image" "${strict[@]+"${strict[@]}"}" "$build_a" "$build_b" 2>&1)" || compare_status=$?
if [[ "$compare_status" -eq 126 || "$compare_status" -eq 127 ]]; then
    missing "the comparison tool could not be run (exit $compare_status)"
fi
if [[ "$compare_status" -eq 2 ]]; then
    missing "the comparison tool refused its arguments: $compare_output"
fi
printf '%s\n' "$compare_output"
if [[ "$compare_status" -ne 0 ]]; then
    fail "the builds are not reproducible by the definition of docs/boot-reproducibility.md (not reproducible, see the rows above)"
fi

# Both signed images must verify with the public test key. A crash of imgtool is not a refusal.
for pair in "A:$build_a" "B:$build_b"; do
    label="${pair%%:*}"
    dir="${pair#*:}"
    for name in zephyr.signed.bin zephyr.signed.confirmed.bin; do
        file="$dir/$image/zephyr/$name"
        [[ -f "$file" ]] || continue
        output=""
        verify_status=0
        output="$("${imgtool[@]}" verify -k "$key" "$file" 2>&1)" || verify_status=$?
        if grep -q Traceback <<<"$output"; then
            fail "imgtool crashed instead of answering for build $label, $name: $output"
        fi
        # The padded confirmed image is informational: how imgtool treats its padding is not established here.
        if [[ "$name" == zephyr.signed.bin && "$verify_status" -ne 0 ]]; then
            fail "imgtool verify refuses the signed image of build $label ($file, exit $verify_status): $output"
        fi
        printf 'imgtool verify, build %s, %s: %s\n' "$label" "$name" "$([[ "$verify_status" -eq 0 ]] && echo ok || echo "refused, exit $verify_status (informational)")"
    done
done

printf '%s\n' "Reproducibility check passed (not a boot result): the unsigned binaries are byte-identical and the signed images differ at most in the randomised signature, in the same container. imgtool verify stays authoritative."
