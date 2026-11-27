#!/usr/bin/env bash
# Install what Crux needs, and skip what is already installed. The Dev Container runs it after
# it is created (postCreateCommand); run it again by hand at any time, from /workspace/crux:
#
#   scripts/bootstrap.sh [--keep-going] [all|host|zephyr|status]
#   scripts/bootstrap.sh board-host      # on the Linux host of a board user, outside the container
#
#   all     every step below (the default; CRUX_BOOTSTRAP=host|zephyr|all sets another default)
#   host    tools, then scripts/bootstrap-host.sh: configure, build and test the Linux Host preset
#           (CRUX_HOST_PRESET, default host-debug); the first run fetches GoogleTest
#   zephyr  tools, then scripts/bootstrap-zephyr.sh --install-sdk: the west workspace in the parent
#           folder, Zephyr's Python requirements and the Zephyr SDK with arm-zephyr-eabi; then
#           west's bash Tab completion (see west_completion)
#   status  print each step's state and whether the J-Link software is installed; installs nothing
#           (the Dev Container prints it when VS Code attaches). A step is ok, running, needs rerun
#           (it finished, but its inputs changed since), FAILED (exit N), or not run
#   board-host  only for a board: prepare the Linux system that the J-Link probe is attached to
#           (WSL2 or native Linux) so that the Dev Container can open it; see board_host below.
#           Never run automatically, and refused inside the container
#
# The tools step adds the west workspace folders to Git's safe.directory list and installs the
# pinned CMake, Ninja, clang-format, west and pytest into a Python virtual environment in the
# cache volume ($CRUX_CACHE_DIR/venv).
#
# A finished step is recorded in $CRUX_CACHE_DIR/bootstrap/ and skipped while its inputs stay the
# same: the tool pins; west.yml, the west workspace and the SDK; the Host build folder.
# CRUX_BOOTSTRAP_FORCE=1 runs every selected step again. Each step's output is kept in
# $CRUX_CACHE_DIR/bootstrap/<step>.log. A run holds $CRUX_CACHE_DIR/bootstrap/run.pid until it
# exits; a lock whose process is gone is ignored.
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
    printf 'Usage: %s [--keep-going] [all|host|zephyr|status|board-host]\n' "$0" >&2
    printf '       (default: $CRUX_BOOTSTRAP, else all)\n' >&2
    exit 2
}

# board_host: the Linux side of the J-Link board route, run on that Linux system and never in the
# Dev Container: a WSL2 distribution with the probe attached through usbipd-win, or a native
# Linux machine. It installs usbutils if lsusb is missing, checks that USB devices and a SEGGER
# J-Link (USB vendor ID 1366) are visible, installs the udev rule
# .devcontainer/jlink/99-crux-jlink.rules once, and reports whether the Dev Container can open
# the probe's current device node. A probe that re-enumerates gets a new node, so run it again
# after a reattach. It never talks to the probe or the board. It is safe to run again.
# Environment, for tests only: CRUX_USB_DIR (default /dev/bus/usb), CRUX_UDEV_RULES_DIR (default
# /etc/udev/rules.d), CRUX_PLUGDEV_GID (group ID of plugdev in the container, default 46),
# CRUX_DOCKERENV (the file that marks a container, default /.dockerenv).
# board_host begin
board_host() {
    if [ -n "${CRUX_REPO:-}" ] || [ -f "${CRUX_DOCKERENV:-/.dockerenv}" ]; then
        printf 'error: run "scripts/bootstrap.sh board-host" on the Linux host with the probe, not in the Dev Container.\n' >&2
        exit 2
    fi
    usb_dir=${CRUX_USB_DIR:-/dev/bus/usb}
    rules_dir=${CRUX_UDEV_RULES_DIR:-/etc/udev/rules.d}
    plugdev_gid=${CRUX_PLUGDEV_GID:-46}
    rule_src=$repo/.devcontainer/jlink/99-crux-jlink.rules
    rule_dst=$rules_dir/99-crux-jlink.rules

    sudo=sudo
    if [ "$(id -u)" -eq 0 ]; then
        sudo=
    fi

    step() { printf '\n== %s\n' "$*"; }
    fail() { printf 'error: %s\n' "$*" >&2; exit 1; }
    attach_hint() {
        printf 'Attach the probe (WSL2: usbipd attach --wsl --busid <BUSID> in PowerShell; native Linux: plug it in),\n' >&2
        printf 'then run this again. See docs/board-jlink-usbipd.md, step 1.\n' >&2
    }

    step "1/5 usbutils"
    if command -v lsusb >/dev/null 2>&1; then
        echo "lsusb is installed"
    else
        $sudo apt-get update
        $sudo apt-get install -y usbutils
        command -v lsusb >/dev/null 2>&1 || fail "lsusb is still missing after installing usbutils"
    fi

    step "2/5 USB devices"
    if [ ! -d "$usb_dir" ]; then
        printf 'error: %s does not exist: no USB device is attached.\n' "$usb_dir" >&2
        attach_hint
        exit 1
    fi
    echo "$usb_dir exists"

    step "3/5 J-Link probe"
    probes=$(lsusb -d 1366: 2>/dev/null || true)
    if [ -z "$probes" ]; then
        printf 'error: lsusb lists no SEGGER J-Link (USB vendor ID 1366).\n' >&2
        attach_hint
        exit 1
    fi
    printf '%s\n' "$probes"

    step "4/5 udev rule"
    if cmp -s "$rule_src" "$rule_dst"; then
        echo "$rule_dst is already installed"
    else
        $sudo cp "$rule_src" "$rule_dst"
        $sudo chmod 0644 "$rule_dst"
        echo "installed $rule_dst"
    fi
    if $sudo udevadm control --reload-rules \
        && $sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=1366 \
        && $sudo udevadm settle; then
        echo "udev rules reloaded"
    else
        printf 'warning: udevadm failed (WSL2 needs [boot] systemd=true in /etc/wsl.conf); the check below decides.\n' >&2
    fi

    step "5/5 device permissions"
    blocked=0
    while read -r _ bus _ device _; do
        device=${device%:}
        node=$usb_dir/$bus/$device
        if [ ! -e "$node" ]; then
            printf 'error: %s is listed by lsusb but does not exist\n' "$node" >&2
            blocked=1
            continue
        fi
        ls -l "$node"
        # shellcheck disable=SC2046  # split the ls -ln fields on purpose
        set -- $(ls -ln "$node")
        mode=$1
        gid=$4
        if [ "${mode:7:2}" = "rw" ]; then
            echo "  Every user can open it (0666). The usual result on WSL2 with usbipd, even with"
            echo "  owner root: the Dev Container can open the probe."
        elif [ "$gid" = "$plugdev_gid" ] && [ "${mode:4:2}" = "rw" ]; then
            echo "  Group plugdev (ID $plugdev_gid) can open it (0660). The expected result on native"
            echo "  Linux: the container user is in plugdev and can open the probe."
        else
            printf 'error: the Dev Container cannot open %s (mode %s, group ID %s; needs 0666, or 0660 with group ID %s).\n' \
                "$node" "$mode" "$gid" "$plugdev_gid" >&2
            blocked=1
        fi
    done <<<"$probes"

    if [ "$blocked" -ne 0 ]; then
        printf 'Reattach the probe (usbipd detach --busid <BUSID>, then usbipd attach --wsl --busid <BUSID>) or replug it, then run this again.\n' >&2
        printf 'See docs/board-jlink-usbipd.md#if-a-step-fails.\n' >&2
        exit 1
    fi
    printf '\nThe Linux side is ready. Open the Dev Container next.\n'
}
# board_host end

keep_going=0
mode=
for argument in "$@"; do
    case "$argument" in
        --keep-going) keep_going=1 ;;
        all | host | zephyr | status | board-host)
            [ -z "$mode" ] || usage
            mode=$argument
            ;;
        *) usage ;;
    esac
done
if [ "$mode" = board-host ]; then
    board_host
    exit 0
fi
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

# run_active: a bootstrap run holds the lock and its process is still alive. The lock outlives a
# rebuilt container, so where /proc exists the process must also be this script.
run_active() {
    local pid
    pid=$(cat "$state/run.pid" 2>/dev/null) || return 1
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null || return 1
    [ ! -r "/proc/$pid/cmdline" ] || grep -q -a 'bootstrap\.sh' "/proc/$pid/cmdline"
}

# run_step <name>: run step_<name> unless it is done, log its output and record the result.
run_step() {
    local name=$1 log=$state/$1.log status
    if is_done "$name"; then
        printf 'ok\n' >"$state/$name.status"
        printf 'bootstrap: %s already done\n' "$name"
        return 0
    fi
    printf '\n== bootstrap: %s\n' "$name"
    printf 'running\n' >"$state/$name.status"
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
    printf 'bootstrap: %s FAILED (exit %s). Log: %s. Rerun: %s. See docs/getting-started.md, section 6.\n' \
        "$name" "$status" "$log" "$(rerun_hint "$name")" >&2
    if [ "$keep_going" -eq 0 ]; then
        exit 1
    fi
    return 1
}

jlink_notice() {
    # Only in the Dev Container (containerEnv sets CRUX_REPO): elsewhere the probe tools are the host's.
    [ -n "${CRUX_REPO:-}" ] || return 0
    # CRUX_JLINK_EXE: the tool looked for; only tests change it.
    if command -v "${CRUX_JLINK_EXE:-JLinkExe}" >/dev/null 2>&1; then
        printf 'J-Link software: installed (%s)\n' "$(command -v "${CRUX_JLINK_EXE:-JLinkExe}")"
        return 0
    fi
    printf 'J-Link software is not installed: board flashing and debugging need it. See docs/board-jlink-usbipd.md, step 3.\n'
}

# west_completion: write west's bash Tab completion, `west completion bash`, to the first
# bash-completion user directory, which bash-completion (2.2 or later) loads on demand. It runs
# in the workspace because its zephyr project provides that command. Every run writes it again; a
# failure only warns and keeps the last script.
west_completion() {
    local user_dir=${BASH_COMPLETION_USER_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion}
    local file=${user_dir%%:*}/completions/west.bash
    if mkdir -p "${file%/*}" && (cd "$workspace" && west completion bash) >"$file.tmp" \
        && mv -f "$file.tmp" "$file"; then
        printf 'west Tab completion: %s\n' "$file"
    else
        rm -f "$file.tmp"
        printf 'warning: could not write the west Tab completion to %s; bootstrap continues\n' "$file" >&2
    fi
}

if [ "$mode" = status ]; then
    for name in tools host zephyr; do
        # A finished step counts only while its record still matches, as in a real run.
        result=$(cat "$state/$name.status" 2>/dev/null || printf 'not run')
        if [ "$result" = running ]; then
            # A step of a run that was killed never finished.
            run_active || result='not run'
        elif is_done "$name"; then
            result=ok
        elif [ "$result" = ok ] || [ -f "$(record_file "$name")" ]; then
            result='needs rerun'
        fi
        line=$(printf '%-7s %s' "$name" "$result")
        case "$result" in
            ok | running) ;;
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

printf '%s\n' "$$" >"$state/run.pid"
# Remove the lock only while it is this run's, not a later run's.
trap '[ "$(cat "$state/run.pid" 2>/dev/null)" != "$$" ] || rm -f "$state/run.pid"' EXIT

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
        [ "$name" != zephyr ] || west_completion
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
