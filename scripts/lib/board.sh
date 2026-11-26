# shellcheck shell=bash
# Board input of the Zephyr scripts. Source it; it defines functions only.
#
# CRUX_BOARD_TARGET names the board as a west build -b value (Zephyr board target,
# board[@revision][/soc[/variant]]). Each script passes its own default, so a script run without
# CRUX_BOARD_TARGET builds the board it always built. See tests/README.md, "Board input".

# Print CRUX_BOARD_TARGET, or the script's default ($1) when it is unset or empty.
crux_board_target() {
    printf '%s' "${CRUX_BOARD_TARGET:-$1}"
}

# Print one spelling per board. West accepts an empty SoC part ("board@rev//variant") for the
# board's only SoC; Twister needs the full name. Known boards map both spellings to the full name.
crux_board_canonical() {
    case "$1" in
        'mimxrt1060_evk@B//qspi' | 'mimxrt1060_evk@B/mimxrt1062/qspi') printf 'mimxrt1060_evk@B/mimxrt1062/qspi' ;;
        'mimxrt1170_evk@A//cm7' | 'mimxrt1170_evk@A/mimxrt1176/cm7') printf 'mimxrt1170_evk@A/mimxrt1176/cm7' ;;
        *) printf '%s' "$1" ;;
    esac
}

# Print the board target as a file name, as build-target.sh names its build folder:
# mimxrt1060_evk@B//qspi gives mimxrt1060_evk_B_qspi.
crux_board_key() {
    printf '%s' "$1" | sed -E 's/[^A-Za-z0-9_.-]+/_/g'
}

# Print the board part of a build folder name, build/zephyr/<purpose>-<tag>. The boards that
# had folders before the board became an input keep their short names (evkb, rt1170), so CI
# uploads, bench tools and documents still find them. Any other board uses its key.
crux_board_tag() {
    case "$(crux_board_canonical "$1")" in
        'mimxrt1060_evk@B/mimxrt1062/qspi') printf 'evkb' ;;
        'mimxrt1170_evk@A/mimxrt1176/cm7') printf 'rt1170' ;;
        *) crux_board_key "$1" ;;
    esac
}

# Exit with one line unless board $1 is one of the boards that follow it. For scripts whose
# images, overlays or checks exist for those boards only.
crux_board_require() {
    local board="$1" wanted
    shift
    for wanted in "$@"; do
        if [[ "$(crux_board_canonical "$board")" == "$(crux_board_canonical "$wanted")" ]]; then
            return 0
        fi
    done
    printf '%s: board %s is not supported (supported: %s). Set CRUX_BOARD_TARGET to a supported board; see tests/README.md#board-input.\n' \
        "${0##*/}" "$board" "$*" >&2
    exit 2
}

# Print the J-Link device of board $1, as Zephyr's board.cmake passes it to the jlink runner.
crux_board_jlink_device() {
    case "$(crux_board_canonical "$1")" in
        mimxrt1060_evk | mimxrt1060_evk[@/]*) printf 'MIMXRT1062xxx6A' ;;
        mimxrt1170_evk[@/]*/cm7) printf 'MIMXRT1176xxxA_M7' ;;
        *) return 1 ;;
    esac
}

# Print the build folder names of board $1 as KEY=value lines, for $GITHUB_ENV.
crux_board_env() {
    printf 'CRUX_BOARD_KEY=%s\nCRUX_BOARD_TAG=%s\n' "$(crux_board_key "$1")" "$(crux_board_tag "$1")"
}
