#!/usr/bin/env bash
# Build, sign and check the boot composition of docs/boot-composition.md: MCUboot RAM load with
# revert and an application, on the RT1060-EVK Rev B. Build only: nothing is programmed, booted,
# debugged or reset, and no key is generated or stored. The image is signed with MCUboot's
# published public test key, which sysbuild uses when no key argument is given. Images signed
# with it must never be programmed to a board.
#
# Run outside CI it changes the local workspace: it adds +crux-boot to manifest.group-filter and
# pip-installs the MCUboot requirements into $CRUX_PYTHON (python3 by default).
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

# The tool is discriminating. A key of another type and images changed after signing are
# refused. A refusal must be a plain verification failure, not a crash of the tool, so a
# traceback does not count. This checks the signing tool on the build output, not a boot result.
imgtool=("$python" "$mcuboot/scripts/imgtool.py")
expect_refused() {
    local output
    if output="$("${imgtool[@]}" verify -k "$1" "$2" 2>&1)"; then
        fail "$3"
    fi
    if grep -q Traceback <<<"$output"; then
        fail "imgtool crashed instead of refusing: $3"
    fi
}
other_key="$mcuboot/root-rsa-2048.pem"
[[ -f "$other_key" ]] || fail "the other test key is not in the MCUboot checkout: $other_key"
expect_refused "$other_key" "$signed" 'the signed image verified with a key of another type'
# 0x300 is in the header padding, 0x400 + 0x100 is in the payload.
for offset in 0x300 0x500; do
    modified="$build/zephyr.signed.modified.bin"
    "$python" - "$signed" "$modified" "$offset" <<'PY'
import sys
data = bytearray(open(sys.argv[1], "rb").read())
data[int(sys.argv[3], 16)] ^= 0xFF
open(sys.argv[2], "wb").write(data)
PY
    expect_refused "$public_key" "$modified" "an image changed after signing at $offset still verified"
    rm -f "$modified"
done

# The application's own files reached its configuration, not only the bootloader's.
app_config="$build/$image/zephyr/.config"
[[ -f "$app_config" ]] || fail "no application configuration at $app_config"
grep -qx CONFIG_RETENTION_BOOTLOADER_INFO_TYPE_MCUBOOT=y "$app_config" ||
    fail 'the application configuration lacks the bootloader information type'
[[ -s "$build/mcuboot/zephyr/zephyr.bin" ]] || fail 'the MCUboot image is empty'

# Both images are configured for RAM load with revert, and the build-number comparison is off
# (image-state rows I5 and Q9). It reads the two .config files only.
"$python" "$repo/scripts/check-boot-config.py" "$build" --image "$image" ||
    fail 'the boot build configuration check failed'

# RAM load with revert implies the padded, confirmed image (erratum of docs/boot-update-investigation.md).
# The bench procedure (docs/secure-boot-board-test-procedure.md, section 4) takes this file, which is
# padded to the 3 MiB slot, so it must exist at that size. The explicit path avoids a search by name.
slot_size=3145728
confirmed="$build/$image/zephyr/zephyr.signed.confirmed.bin"
[[ -f "$confirmed" ]] || fail "the build did not produce $confirmed"
[[ "$(stat -c %s "$confirmed")" -eq "$slot_size" ]] ||
    fail "$confirmed is $(stat -c %s "$confirmed") bytes, not the slot size $slot_size"

# The images that this build wrote are read by the boot image inspector (tests/target/inspect_boot_image.py)
# and by imgtool, which must agree, and by the inspector's slot fit decision. It builds and signs nothing
# that is kept, reads $build and removes its own temporary files.
CRUX_PYTHON="$python" CRUX_WORKSPACE="$workspace" "$repo/tests/target/check_boot_images.sh" "$build" ||
    fail 'the boot image check failed'

# Report only (#165): list the NOR references reachable from the FlexSPI write and erase path of the MCUboot
# image. The documented composition is not expected to be clean, so this never fails the check and has no
# --strict. A pass of the check would show the absence of the edges it looks for, not closure of the #22 matrix
# (docs/plans/mcuboot-flexspi-write-path-closure.md, section 5.1). A run that cannot start says so. It weakens
# and removes none of the checks above. Approved by the owner on 2026-11-16 (Secure Boot session chat).
sdk_bin="${ZEPHYR_SDK_INSTALL_DIR:-}/gnu/arm-zephyr-eabi/bin"
[[ -x "$sdk_bin/arm-zephyr-eabi-objdump" ]] || sdk_bin="${ZEPHYR_SDK_INSTALL_DIR:-}/arm-zephyr-eabi/bin"
if [[ -x "$sdk_bin/arm-zephyr-eabi-objdump" && -f "$build/mcuboot/zephyr/zephyr.elf" ]]; then
    "$python" "$repo/scripts/check-flexspi-closure.py" --elf "$build/mcuboot/zephyr/zephyr.elf" \
        --nm "$sdk_bin/arm-zephyr-eabi-nm" --objdump "$sdk_bin/arm-zephyr-eabi-objdump" \
        --zephyr-base "$workspace/zephyr" --hal-nxp "$workspace/modules/hal/nxp" ||
        printf 'FlexSPI closure report: the report itself failed to run (report only, not a failure of this check).\n'
else
    printf 'FlexSPI closure report: no toolchain objdump or no MCUboot ELF, not run.\n'
fi

printf 'Boot composition: MCUboot %s bytes, signed application %s bytes (build only, not booted).\n' \
    "$(stat -c %s "$build/mcuboot/zephyr/zephyr.bin")" "$(stat -c %s "$signed")"
