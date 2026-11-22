#!/usr/bin/env bash
# Prepare the Linux side of the J-Link board route: a WSL2 distribution with the
# probe attached through usbipd-win, or a native Linux machine. Run it from the
# repository checkout on that Linux system, not in a container:
#
#   scripts/setup-board-host.sh
#
# It installs usbutils if lsusb is missing, checks that USB devices and a SEGGER
# J-Link (USB vendor ID 1366) are visible, installs the udev rule
# .devcontainer/jlink/99-crux-jlink.rules once, and reports whether the board
# Dev Container can open the probe's device node. It never talks to the probe
# or the board. It is safe to run again.
#
# Environment, for tests only:
#   CRUX_USB_DIR         USB device tree (default /dev/bus/usb)
#   CRUX_UDEV_RULES_DIR  udev rules folder (default /etc/udev/rules.d)
#   CRUX_PLUGDEV_GID     group ID of plugdev in the container (default 46)
set -euo pipefail

usb_dir=${CRUX_USB_DIR:-/dev/bus/usb}
rules_dir=${CRUX_UDEV_RULES_DIR:-/etc/udev/rules.d}
plugdev_gid=${CRUX_PLUGDEV_GID:-46}
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
rule_src=$repo/.devcontainer/jlink/99-crux-jlink.rules
rule_dst=$rules_dir/99-crux-jlink.rules

sudo=sudo
if [ "$(id -u)" -eq 0 ]; then
    sudo=
fi

step() { printf '\n== %s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }
attach_hint() {
    cat >&2 <<'EOF'
On WSL2, attach the probe from PowerShell on Windows, then run this script again:

    usbipd attach --wsl --busid <BUSID>

`usbipd list` shows the BUSID of the J-Link (vendor ID 1366). It must be bound
once first with `usbipd bind --busid <BUSID>` in an administrator PowerShell.
On native Linux, plug the probe in.
EOF
}

step "1/5 usbutils"
if command -v lsusb >/dev/null 2>&1; then
    echo "lsusb is installed"
else
    $sudo apt-get install -y usbutils
    command -v lsusb >/dev/null 2>&1 || fail "lsusb is still missing after installing usbutils"
fi

step "2/5 USB devices"
if [ ! -d "$usb_dir" ]; then
    printf 'error: %s does not exist. On WSL2 it appears only after a USB device is attached.\n' "$usb_dir" >&2
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
    printf 'warning: udevadm failed. On WSL2, udev runs only when the distribution runs systemd\n' >&2
    printf 'warning: ([boot] systemd=true in /etc/wsl.conf). The check below decides.\n' >&2
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
        echo "  owner root: the board Dev Container can open the probe."
    elif [ "$gid" = "$plugdev_gid" ] && [ "${mode:4:2}" = "rw" ]; then
        echo "  Group plugdev (ID $plugdev_gid) can open it (0660). The expected result on native"
        echo "  Linux: the container user is in plugdev and can open the probe."
    else
        printf 'error: the board Dev Container cannot open %s (mode %s, group ID %s).\n' \
            "$node" "$mode" "$gid" >&2
        blocked=1
    fi
done <<<"$probes"

if [ "$blocked" -ne 0 ]; then
    cat >&2 <<EOF
The container user can open the probe only if the node is 0666, or 0660 with
group ID $plugdev_gid (plugdev in the container). Check that $rule_dst is
installed and that udev runs, then detach and attach the probe again
(usbipd detach --busid <BUSID>, then usbipd attach --wsl --busid <BUSID>) or
replug it. \`getent group plugdev\` must show ID $plugdev_gid; if it does not,
use MODE="0666" in your local copy of the rule.
EOF
    exit 1
fi
printf '\nThe Linux side is ready. Open the board Dev Container next.\n'
