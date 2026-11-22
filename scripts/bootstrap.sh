#!/usr/bin/env bash
# Install what Crux needs, and skip what is already installed. The Dev Container runs it after
# it is created (postCreateCommand); run it again by hand at any time, from /workspace/crux-pilot:
#
#   scripts/bootstrap.sh [--keep-going] [all|host|zephyr|status]
#
#   all     every step below (the default; CRUX_BOOTSTRAP=host|zephyr|all sets another default)
#   host    tools, then scripts/bootstrap-host.sh: configure, build and test the Linux Host preset
#           (CRUX_HOST_PRESET, default host-debug); the first run fetches GoogleTest
#   zephyr  tools, then scripts/bootstrap-zephyr.sh --install-sdk: the west workspace in the parent
#           folder, Zephyr's Python requirements and the Zephyr SDK with arm-zephyr-eabi
#   status  print the result of each step's last run and whether the J-Link software is installed;
#           installs nothing (the Dev Container prints it when VS Code attaches)
#
# The tools step adds the west workspace folders to Git's safe.directory list and installs the
# pinned CMake, Ninja, clang-format, west and pytest into a Python virtual environment in the
# cache volume ($CRUX_CACHE_DIR/venv).
#
# A finished step is recorded in $CRUX_CACHE_DIR/bootstrap/ and skipped while its inputs stay the
# same: the tool pins; west.yml, the west workspace and the SDK; the Host build folder.
# CRUX_BOOTSTRAP_FORCE=1 runs every selected step again. Each step's output is kept in
# $CRUX_CACHE_DIR/bootstrap/<step>.log.
#
# Without --keep-going the first failed step stops the script with exit status 1. With
# --keep-going every step runs, each failure is reported with its log and the command that
# reruns it, and the exit status is 0, so a failed download never keeps the Dev Container from
# opening. Nothing here flashes, resets or talks to a board.
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
workspace=${CRUX_WORKSPACE:-$(dirname "$repo")}
cache=${CRUX_CACHE_DIR:-$repo/../.crux-cache}
venv=$cache/venv
host_preset=${CRUX_HOST_PRESET:-host-debug}
host_build=$repo/build/linux/${host_preset#host-}
sdk=${ZEPHYR_SDK_INSTALL_DIR:-$cache/sdk/zephyr-sdk-1.0.1}
tool_pins="cmake==3.28.4 ninja==1.11.1 clang-format==18.1.8 west==1.4.0 pytest==8.3.5"
safe_directories="$repo $workspace/zephyr $workspace/modules/hal/cmsis $workspace/modules/hal/cmsis_6 $workspace/modules/hal/nxp"
force=${CRUX_BOOTSTRAP_FORCE:-}

usage() {
    printf 'Usage: %s [--keep-going] [all|host|zephyr|status]\n' "$0" >&2
    printf '       (default: $CRUX_BOOTSTRAP, else all)\n' >&2
    exit 2
}

keep_going=0
mode=
for argument in "$@"; do
    case "$argument" in
        --keep-going) keep_going=1 ;;
        all | host | zephyr | status)
            [ -z "$mode" ] || usage
            mode=$argument
            ;;
        *) usage ;;
    esac
done
mode=${mode:-${CRUX_BOOTSTRAP:-all}}
case "$mode" in
    all | host | zephyr | status) ;;
    *)
        printf 'CRUX_BOOTSTRAP must be host, zephyr or all, not %s\n' "$mode" >&2
        usage
        ;;
esac

state=$cache/bootstrap
mkdir -p "$state" 2>/dev/null || state=$(mktemp -d)

# A step's record holds the inputs it finished with; the step is done while they match.
tools_inputs() { printf 'pins %s\n' "$tool_pins"; }
zephyr_inputs() {
    tools_inputs
    printf 'workspace %s\nsdk %s\nmanifest %s\n' "$workspace" "$sdk" "$(cksum <"$repo/west.yml")"
}
host_inputs() { printf 'preset %s\n' "$host_preset"; }
host_record() { printf '%s/.crux-bootstrap' "$host_build"; }
record_file() {
    case "$1" in
        host) host_record ;;
        *) printf '%s/%s.done' "$state" "$1" ;;
    esac
}

is_done() {
    local record
    record=$(record_file "$1")
    [ -z "$force" ] || return 1
    [ -f "$record" ] && [ "$(cat "$record")" = "$("$1_inputs")" ] || return 1
    case "$1" in
        tools) [ -x "$venv/bin/python" ] ;;
        zephyr)
            [ -f "$workspace/.west/config" ] && [ -d "$workspace/zephyr" ] \
                && { [ -d "$sdk/gnu/arm-zephyr-eabi/bin" ] || [ -d "$sdk/arm-zephyr-eabi/bin" ]; }
            ;;
    esac
}

step_tools() {
    local directory
    for directory in $safe_directories; do
        if ! git config --global --get-all safe.directory 2>/dev/null | grep -Fxq -- "$directory"; then
            git config --global --add safe.directory "$directory" || return
        fi
    done
    if [ ! -x "$venv/bin/python" ]; then
        python3 -m venv "$venv" || return
    fi
    # shellcheck disable=SC2086  # one argument per pin
    "$venv/bin/python" -m pip install --disable-pip-version-check --no-cache-dir $tool_pins
}
step_host() { CRUX_HOST_PRESET=$host_preset "$repo/scripts/bootstrap-host.sh"; }
step_zephyr() { "$repo/scripts/bootstrap-zephyr.sh" --install-sdk; }

failed=
rerun_hint() { printf 'scripts/bootstrap.sh %s' "$1"; }

# run_step <name>: run step_<name> unless it is done, log its output and record the result.
run_step() {
    local name=$1 log=$state/$1.log status
    if is_done "$name"; then
        printf 'bootstrap: %s already done\n' "$name"
        return 0
    fi
    printf '\n== bootstrap: %s\n' "$name"
    set +e
    "step_$name" 2>&1 | tee "$log"
    status=${PIPESTATUS[0]}
    set -e
    if [ "$status" -eq 0 ]; then
        mkdir -p "$(dirname "$(record_file "$name")")"
        "${name}_inputs" >"$(record_file "$name")"
        printf 'ok\n' >"$state/$name.status"
        printf 'bootstrap: %s ok\n' "$name"
        return 0
    fi
    printf 'FAILED (exit %s)\n' "$status" >"$state/$name.status"
    rm -f "$(record_file "$name")"
    failed="$failed $name"
    printf 'bootstrap: %s FAILED (exit %s). Log: %s\n' "$name" "$status" "$log" >&2
    printf 'bootstrap: fix the cause (network, proxy, disk), then run: %s\n' "$(rerun_hint "$name")" >&2
    if [ "$keep_going" -eq 0 ]; then
        exit 1
    fi
    return 1
}

jlink_notice() {
    # Only in the Dev Container (containerEnv sets CRUX_REPO): elsewhere the probe tools are the host's.
    [ -n "${CRUX_REPO:-}" ] || return 0
    if command -v JLinkExe >/dev/null 2>&1; then
        printf 'J-Link software: installed (%s)\n' "$(command -v JLinkExe)"
        return 0
    fi
    cat <<'EOF'
J-Link software is not installed in this container. Host and native_sim work without it; flashing
and debugging a board need it. Download JLink_Linux_<version>_x86_64.deb from SEGGER (accept its
licence there), place it in .devcontainer/jlink/packages/ on the host, then run
"Dev Containers: Rebuild Container". See docs/board-jlink-usbipd.md.
EOF
}

if [ "$mode" = status ]; then
    for name in tools host zephyr; do
        result=$(cat "$state/$name.status" 2>/dev/null || printf 'not run')
        line=$(printf '%-7s %s' "$name" "$result")
        case "$result" in
            ok) ;;
            *) line="$line   rerun: $(rerun_hint "$name")" ;;
        esac
        printf 'bootstrap: %s\n' "$line"
    done
    jlink_notice
    exit 0
fi

if [ "$(uname -s)" != Linux ]; then
    printf 'scripts/bootstrap.sh sets up Linux; reopen this repository in the Dev Container.\n' >&2
    exit 2
fi

steps=tools
case "$mode" in
    all) steps="tools host zephyr" ;;
    host) steps="tools host" ;;
    zephyr) steps="tools zephyr" ;;
esac
tools_ok=1
for name in $steps; do
    if [ "$name" != tools ] && [ "$tools_ok" -eq 0 ]; then
        printf 'bootstrap: %s skipped, it needs the tools step. Rerun: %s\n' "$name" "$(rerun_hint "$name")" >&2
        failed="$failed $name"
        continue
    fi
    if run_step "$name"; then
        [ "$name" != tools ] || export PATH="$venv/bin:$PATH"
    else
        [ "$name" != tools ] || tools_ok=0
    fi
done

printf '\n'
jlink_notice
if [ -n "$failed" ]; then
    printf 'bootstrap: not finished:%s. The Dev Container is usable; rerun the commands above.\n' "$failed" >&2
fi
exit 0
