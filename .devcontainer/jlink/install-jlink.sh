#!/bin/sh
# Install the SEGGER J-Link Debian package that the developer downloaded and
# placed in .devcontainer/jlink/packages/. Run by the Dockerfile only when the
# board Dev Container sets CRUX_JLINK=1. It never downloads anything: the SEGGER
# licence must be accepted by the person who downloads the package.
#
# Environment:
#   CRUX_JLINK_DEB         file name of the package in the folder (optional when
#                          the folder holds exactly one JLink_Linux_*_x86_64.deb)
#   CRUX_JLINK_DEB_SHA256  expected SHA-256 of the package (optional)
set -eu

dir=${1:?usage: install-jlink.sh <package folder>}
deb=${CRUX_JLINK_DEB:-}
expected=$(printf '%s' "${CRUX_JLINK_DEB_SHA256:-}" | tr 'A-F' 'a-f')

cd "$dir"
if [ -z "$deb" ]; then
    set -- JLink_Linux_*_x86_64.deb
    if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
        echo "error: place exactly one SEGGER J-Link package (JLink_Linux_<version>_x86_64.deb)" \
             "in .devcontainer/jlink/packages/, or name one with CRUX_JLINK_DEB" >&2
        exit 1
    fi
    deb=$1
fi

case "$deb" in
    */* | .* | -*)
        echo "error: CRUX_JLINK_DEB must be a plain file name in .devcontainer/jlink/packages/" >&2
        exit 1
        ;;
esac
if [ ! -f "$deb" ]; then
    echo "error: .devcontainer/jlink/packages/$deb not found" >&2
    exit 1
fi

actual=$(sha256sum "$deb" | cut -d ' ' -f 1)
echo "J-Link package: $deb, SHA-256 $actual"
if [ -n "$expected" ] && [ "$actual" != "$expected" ]; then
    echo "error: SHA-256 of $deb is $actual, expected $expected" >&2
    exit 1
fi

apt-get update
apt-get install -y --no-install-recommends usbutils "./$deb"
# The Dockerfile removes the apt lists after this script, so the script
# deletes nothing itself.

# The probe's device node belongs to group plugdev on the host (see
# 99-crux-jlink.rules). Debian and Ubuntu give plugdev the same fixed ID (46).
usermod -aG plugdev vscode

for tool in JLinkExe JLinkGDBServer; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "error: $tool is missing after installing $deb" >&2
        exit 1
    fi
done
