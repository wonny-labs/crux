#!/usr/bin/env bash
# Build, sign and check the boot composition of docs/boot-composition.md: MCUboot RAM load with
# revert and an application, on the RT1060-EVK Rev B. Build only: nothing is programmed, booted,
# debugged or reset, and no key is generated or stored. The image is signed with MCUboot's
# published public test key, which sysbuild uses when no key argument is given. Images signed
# with it must never be programmed to a board.
#
# It builds the argument set of the page as published: the group route (no -DEXTRA_ZEPHYR_MODULES
# for MCUboot) and no key argument. The M7 reference composition is not touched.
set -euo pipefail

if [[ "$(uname -s)" != Linux ]]; then
    printf 'The boot composition check needs the Linux development environment.\n' >&2
    exit 2
fi

repo="$(git rev-parse --show-toplevel)"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
python="${CRUX_PYTHON:-python3}"
board='mimxrt1060_evk@B//qspi'
files="$repo/zephyr/boot/boards/mimxrt1060_evk_mimxrt1062_qspi_B"
app="$repo/samples/controller/zephyr"
image="$(basename "$app")"
build="$repo/build/zephyr/boot-composition"
mcuboot="$workspace/bootloader/mcuboot"
public_key="$mcuboot/root-ec-p256.pem"

fail() {
    printf 'boot composition check failed: %s\n' "$1" >&2
    exit 1
}

if [[ ! -f "$workspace/.west/config" || ! -d "$workspace/zephyr" ]]; then
    printf 'Run scripts/bootstrap-zephyr.sh before the boot composition check.\n' >&2
    exit 2
fi
for name in mcuboot.conf mcuboot.overlay app.conf app.overlay; do
    [[ -f "$files/$name" ]] || fail "$files/$name is missing"
done

# MCUboot is the plain project in the optional group crux-boot. This enables the group the way a
# workspace owner would, keeping a filter that is already set, and fetches only that project.
filter="$(cd "$workspace" && west config manifest.group-filter 2>/dev/null || true)"
if [[ ",$filter," != *",+crux-boot,"* ]]; then
    (cd "$workspace" && west config manifest.group-filter -- "${filter:+$filter,}+crux-boot")
fi
(cd "$workspace" && west update mcuboot)
[[ -f "$public_key" ]] || fail "the public test key is not in the MCUboot checkout: $public_key"

# imgtool imports packages that the Zephyr requirements do not list. The MCUboot checkout names
# them for its own revision.
"$python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$mcuboot/scripts/requirements.txt"

export ZEPHYR_BASE="$workspace/zephyr"
(cd "$workspace" && west build --sysbuild -p always -b "$board" -d "$build" "$app" -- \
    -DZEPHYR_EXTRA_MODULES="$repo" \
    -DPython3_EXECUTABLE="$(command -v "$python")" \
    -DSB_CONFIG_BOOTLOADER_MCUBOOT=y \
    -DSB_CONFIG_MCUBOOT_MODE_RAM_LOAD_WITH_REVERT=y \
    -DSB_CONFIG_BOOT_SIGNATURE_TYPE_ECDSA_P256=y \
    "-Dmcuboot_EXTRA_CONF_FILE=$files/mcuboot.conf" \
    "-Dmcuboot_EXTRA_DTC_OVERLAY_FILE=$files/mcuboot.overlay" \
    "-D${image}_EXTRA_CONF_FILE=$files/app.conf" \
    "-D${image}_EXTRA_DTC_OVERLAY_FILE=$files/app.overlay")

# The bootloader is configured as the page says.
config="$build/mcuboot/zephyr/.config"
[[ -f "$config" ]] || fail "no MCUboot configuration at $config"
for line in \
    CONFIG_BOOT_RAM_LOAD=y \
    CONFIG_BOOT_RAM_LOAD_REVERT=y \
    CONFIG_BOOT_SIGNATURE_TYPE_ECDSA_P256=y \
    CONFIG_BOOT_IMAGE_EXECUTABLE_RAM_START=0x80000000 \
    CONFIG_BOOT_IMAGE_EXECUTABLE_RAM_SIZE=33554432; do
    grep -qx "$line" "$config" || fail "$line is not set in $config"
done
[[ -f "$build/mcuboot/zephyr/zephyr.bin" ]] || fail 'the build did not produce the MCUboot image'

# The application is signed, and the signature verifies with the public test key.
signed="$(find "$build/$image" -name zephyr.signed.bin -print -quit)"
[[ -n "$signed" && -f "$signed" ]] || fail 'the build did not produce zephyr.signed.bin'
"$python" "$mcuboot/scripts/imgtool.py" verify -k "$public_key" "$signed" ||
    fail 'the signed image does not verify with the public test key'

# The tool is discriminating. A key of another type and an image changed after signing are
# refused. This is a check of the signing tool on the build output, not a boot result.
other_key="$mcuboot/root-rsa-2048.pem"
if [[ -f "$other_key" ]] &&
    "$python" "$mcuboot/scripts/imgtool.py" verify -k "$other_key" "$signed" >/dev/null 2>&1; then
    fail 'the signed image verified with a key of another type'
fi
modified="$build/zephyr.signed.modified.bin"
"$python" - "$signed" "$modified" <<'PY'
import sys
data = bytearray(open(sys.argv[1], "rb").read())
data[0x300] ^= 0xFF
open(sys.argv[2], "wb").write(data)
PY
if "$python" "$mcuboot/scripts/imgtool.py" verify -k "$public_key" "$modified" >/dev/null 2>&1; then
    fail 'an image changed after signing still verified'
fi
rm -f "$modified"

printf 'Boot composition: MCUboot %s bytes, signed application %s bytes (build only, not booted).\n' \
    "$(stat -c %s "$build/mcuboot/zephyr/zephyr.bin")" "$(stat -c %s "$signed")"
