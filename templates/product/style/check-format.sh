#!/usr/bin/env bash
set -euo pipefail

# Check that the C and C++ sources of a product repository match its .clang-format.
# Run it from anywhere inside the repository: it uses the Git top level. It reads the
# product's own .clang-format, and falls back to the copy beside this script when the
# product root has none. It formats nothing: it only reports. Crux's scripts/check-format.sh
# does the same for the Crux repository and works in any repository too, but it
# reads whatever .clang-format that repository has.

usage() {
    cat <<'EOF'
Usage: check-format.sh

Run clang-format in dry-run mode on every tracked or untracked (not ignored) .c, .h, .cpp and .hpp file
of the Git repository that contains the current directory. Exit status 0: all files match.

Environment:
  CLANG_FORMAT  the formatter to run (default clang-format-18, the version Crux pins)
EOF
}

case "${1:-}" in
-h | --help)
    usage
    exit 0
    ;;
esac
if (($# > 0)); then
    usage >&2
    exit 2
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repo="$(git rev-parse --show-toplevel)"
formatter="${CLANG_FORMAT:-clang-format-18}"
if ! command -v "$formatter" >/dev/null 2>&1; then
    printf 'Formatter not found: %s. Install clang-format 18 or set CLANG_FORMAT.\n' "$formatter" >&2
    exit 2
fi

style=()
if [[ ! -f "$repo/.clang-format" ]]; then
    style=("--style=file:$here/.clang-format")
fi

sources=()
while IFS= read -r source; do
    # Git still lists the old path of a deleted or unstaged-renamed file.
    if [[ -f "$repo/$source" ]]; then
        sources+=("$repo/$source")
    fi
done < <(git -C "$repo" ls-files --cached --others --exclude-standard -- '*.c' '*.h' '*.cpp' '*.hpp')
if ((${#sources[@]} == 0)); then
    printf 'No C/C++ files found.\n'
    exit 0
fi
"$formatter" --dry-run --Werror ${style[@]+"${style[@]}"} "${sources[@]}"
