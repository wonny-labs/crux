#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

# Run the product-side include check on the whole product repository, from the Git top level.
# It runs the documented command, `python3 check_domain_includes.py --product .`, with the root
# resolved for you. The check is the one that sits at the root of the product (a copy of
# templates/product/check_domain_includes.py), or else the copy beside this directory.

usage() {
    cat <<'EOF'
Usage: check-includes.sh [check_domain_includes.py options]

Run check_domain_includes.py --product <Git top level> with the options you give, for example
--exclude PATH for a legacy file that still includes a frozen header, or --domain DIR for another
plain C directory. Do not pass --product yourself.

Environment:
  PYTHON  the interpreter to run (default python3, 3.9 or later)
EOF
}

case "${1:-}" in
-h | --help)
    usage
    exit 0
    ;;
esac

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repo="$(git rev-parse --show-toplevel)"
checker="$repo/check_domain_includes.py"
if [[ ! -f "$checker" ]]; then
    checker="$(cd "$here/.." && pwd -P)/check_domain_includes.py"
fi
if [[ ! -f "$checker" ]]; then
    printf 'check_domain_includes.py not found at the product root or beside this directory.\n' >&2
    exit 2
fi
exec "${PYTHON:-python3}" "$checker" --product "$repo" "$@"
