#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != Darwin ]]; then
    printf 'This launcher must run on macOS, where the J-Link probe is connected.\n' >&2
    exit 2
fi

server="/usr/local/bin/JLinkGDBServer"
if [[ ! -x "$server" ]]; then
    server="/Applications/SEGGER/JLink_V986a/JLinkGDBServerCLExe"
fi
if [[ ! -x "$server" ]]; then
    printf 'J-Link GDB Server was not found at the expected SEGGER installation paths.\n' >&2
    exit 2
fi

# shellcheck source=../lib/board.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib/board.sh"
board="$(crux_board_target 'mimxrt1060_evk@B//qspi')"
device="${CRUX_JLINK_DEVICE:-$(crux_board_jlink_device "$board" || true)}"
if [[ -z "$device" ]]; then
    printf 'No J-Link device is known for board %s. Name the core in the board target, or set CRUX_JLINK_DEVICE.\n' "$board" >&2
    exit 2
fi

printf 'Starting J-Link GDB Server for %s over SWD at 400 kHz on port 2331.\n' "$device"
if [[ "$device" == MIMXRT1062xxx6A ]]; then
    printf '400 kHz has been verified for QSPI download and a main breakpoint on the connected EVKB.\n'
fi
printf 'Remote connections are enabled. The server may halt the target on startup.\n'
printf 'Press Ctrl-C to stop the server when debugging is finished.\n\n'

exec "$server" \
    -device "$device" \
    -if SWD \
    -speed 400 \
    -endian little \
    -port 2331 \
    -localhostonly 0
