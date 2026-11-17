#!/usr/bin/env bash
# Shared part of jlink-load.sh and jlink-verify.sh. Sourced, never run on its own.
#
# What the wrappers do (docs/secure-boot-board-test-procedure.md, section 5):
#   * accept exactly one argument: the name of a file in <bench>/handoff/, or its full path;
#   * take the flash address from the file name, never from an argument;
#   * refuse any argument that mentions an erase or a fuse;
#   * write a J-Link Commander command file whose first line is `exec DisableAutoUpdateFW`
#     and whose other lines are only: usb, connect, r, h, loadfile or verifybin, q;
#   * start nothing else. No erase, unlock, fuse or write-memory command is ever written.
#
# Environment: BENCH_PROBE_SERIAL (digits, required), JLINK (Commander executable, default JLinkExe),
# BENCH_PRINT_ONLY=1 (write the command file, print the Commander command, do not start the probe).
# The bench directory is the directory this script lives in: copy the scripts there with
# `evidence_dir.py init-bench`. Nothing here was run on a board.
set -eu
export LC_ALL=C

bench_die() {
    printf 'boot-bench: %s\n' "$*" >&2
    exit 2
}

# Flash map of the RT1060-EVKB QSPI NOR as the procedure states it (section 5, "Addresses"). The two
# sacrificial files are an extension for the ROM serial downloader check (#309), at the base address.
BASE_ADDRESS=0x60000000
BASE_MAX_BYTES=131072     # partition `mcuboot`, 0x20000
SACRIFICIAL_MAX_BYTES=4096 # one sector: the #309 first-sector files only
SLOT0_ADDRESS=0x60020000
SLOT0_MAX_BYTES=3145728   # partition `image-0`, 0x300000

BENCH_DIR=$(CDPATH= cd -P -- "$(dirname "${BASH_SOURCE[1]}")" && pwd -P)
HANDOFF_DIR=$BENCH_DIR/handoff
CMD_DIR=$BENCH_DIR/cmd

# A path that could break the quoted command file line is refused.
case $BENCH_DIR in
    *[!A-Za-z0-9._/+@=,:~-]*) bench_die "the bench directory path has characters that are not allowed: $BENCH_DIR" ;;
esac

# bench_prepare <kind> <args...>: sets IMAGE_NAME, IMAGE_PATH, IMAGE_ADDRESS, CMD_FILE.
bench_prepare() {
    local kind=$1
    shift
    [ "$#" -eq 1 ] || bench_die "expected exactly one argument, the name of a file in $HANDOFF_DIR"
    local arg=$1
    local lowered
    lowered=$(printf '%s' "$arg" | tr 'A-Z' 'a-z')
    case $lowered in
        *erase* | *fuse*) bench_die "refusing an argument that mentions erase or fuse" ;;
    esac
    [ -n "$arg" ] || bench_die "empty argument"
    [ ! -L "$HANDOFF_DIR" ] || bench_die "the hand-off directory is a symbolic link"
    [ -d "$HANDOFF_DIR" ] || bench_die "no hand-off directory: $HANDOFF_DIR"
    local name=$arg
    case $arg in
        */*)
            local dir=${arg%/*}
            [ -n "$dir" ] || dir=/
            local resolved
            resolved=$(CDPATH= cd -P -- "$dir" 2>/dev/null && pwd -P) || bench_die "cannot resolve the directory of the argument"
            [ "$resolved" = "$HANDOFF_DIR" ] || bench_die "the file is not in the hand-off directory $HANDOFF_DIR"
            name=${arg##*/}
            ;;
    esac
    case $name in
        '' | *[!A-Za-z0-9._-]*) bench_die "the file name has characters that are not allowed" ;;
    esac
    local max
    case $name in
        mcuboot.zephyr.bin | time-baseline.bin)
            IMAGE_ADDRESS=$BASE_ADDRESS
            max=$BASE_MAX_BYTES
            ;;
        sacrificial-blank.bin | sacrificial-pattern.bin)
            IMAGE_ADDRESS=$BASE_ADDRESS
            max=$SACRIFICIAL_MAX_BYTES
            ;;
        blank-slot0.bin | app.?*.bin)
            case $name in
                app.*..* | app..*) bench_die "the file name is not one of the procedure's names" ;;
            esac
            IMAGE_ADDRESS=$SLOT0_ADDRESS
            max=$SLOT0_MAX_BYTES
            ;;
        *) bench_die "the file name is not one of the procedure's names: $name" ;;
    esac
    IMAGE_NAME=$name
    IMAGE_PATH=$HANDOFF_DIR/$name
    [ ! -L "$IMAGE_PATH" ] || bench_die "$name is a symbolic link"
    [ -f "$IMAGE_PATH" ] || bench_die "$name is not a file in the hand-off directory"
    local size
    size=$(wc -c <"$IMAGE_PATH" | tr -d ' ')
    [ "$size" -gt 0 ] || bench_die "$name is empty"
    [ "$size" -le "$max" ] || bench_die "$name is $size bytes, more than its region of $max bytes"
    case ${BENCH_PROBE_SERIAL:-} in
        '' | *[!0-9]*) bench_die "BENCH_PROBE_SERIAL must be the probe's numeric serial number" ;;
    esac
    [ "${#BENCH_PROBE_SERIAL}" -le 12 ] || bench_die "BENCH_PROBE_SERIAL is too long"
    [ ! -L "$CMD_DIR" ] || bench_die "the cmd directory is a symbolic link"
    mkdir -p "$CMD_DIR"
    CMD_FILE=$CMD_DIR/$kind-$name.jlink
    [ ! -L "$CMD_FILE" ] || bench_die "$CMD_FILE is a symbolic link"
}

# bench_write_commands <kind>: the whole command file. `exec DisableAutoUpdateFW` is always first.
bench_write_commands() {
    local kind=$1
    {
        printf 'exec DisableAutoUpdateFW\n'
        printf 'usb %s\n' "$BENCH_PROBE_SERIAL"
        printf 'connect\n'
        case $kind in
            load)
                printf 'r\n'
                printf 'h\n'
                printf 'loadfile "%s", %s\n' "$IMAGE_PATH" "$IMAGE_ADDRESS"
                ;;
            verify)
                printf 'verifybin "%s", %s\n' "$IMAGE_PATH" "$IMAGE_ADDRESS"
                ;;
            *) bench_die "internal error: unknown kind $kind" ;;
        esac
        printf 'q\n'
    } >"$CMD_FILE"
}

# bench_run <kind>: runs Commander with the fixed arguments of the procedure, prints its output and
# returns its status. Sets BENCH_OUTPUT_FILE (removed by the caller through bench_finish).
bench_run() {
    local jlink=${JLINK:-JLinkExe}
    local -a command=("$jlink" -Device MIMXRT1062xxx6A -If SWD -Speed 400 -NoGui 1 -ExitOnError 1
        -AutoConnect 0 -CommandFile "$CMD_FILE")
    if [ "${BENCH_PRINT_ONLY:-}" = 1 ]; then
        printf '%s\n' "${command[*]}"
        BENCH_STATUS=0
        BENCH_OUTPUT_FILE=
        return 0
    fi
    BENCH_OUTPUT_FILE=$(mktemp "${TMPDIR:-/tmp}/boot-bench.XXXXXX")
    trap 'rm -f "$BENCH_OUTPUT_FILE"' EXIT
    BENCH_STATUS=0
    "${command[@]}" >"$BENCH_OUTPUT_FILE" 2>&1 || BENCH_STATUS=$?
    cat "$BENCH_OUTPUT_FILE"
}

bench_finish() {
    [ -z "${BENCH_OUTPUT_FILE:-}" ] || rm -f "$BENCH_OUTPUT_FILE"
}
