#!/usr/bin/env bash
# Build the MCUboot RAM load composition of docs/boot-composition.md (RT1060-EVK Rev B) once for each
# ECDSA P-256 backend of MCUboot that the pinned revisions offer, and report the size of the bootloader
# for each: tinycrypt (MCUboot's bundled copy, the default and the #141 trial), Zephyr's Mbed TLS ("Use
# mbedTLS") and PSA crypto ("Use PSA crypto"). This is the size comparison that plan decision D9 asks for
# (docs/plans/secure-boot-development-plan.md); the result and its reading are in
# docs/plans/mcuboot-crypto-backend-comparison.md. It is a one-off decision input, not a regression check.
#
# Build only: nothing is programmed, booted, debugged or reset, no key is generated or stored, and
# the manifest is not edited. The application is signed with MCUboot's published public test key as in
# scripts/test-boot-composition.sh. Boot time is not measured: it needs a board.
#
# It is NOT wired into any workflow. Run outside CI it changes the local workspace: it adds +crux-boot and
# +crux-secure-management to manifest.group-filter, fetches mcuboot, mbedtls and tf-psa-crypto (and nothing
# else of the secure management group) and pip-installs the MCUboot requirements into $CRUX_PYTHON.
# The baseline is built before the two crypto projects are fetched, so that it is the composition of the
# composition check, and again afterwards, to show what the presence of the modules alone does.
#
# A variant that does not configure or build is reported with the first error lines of its log and does not
# stop the others. Exit status: 0 the baseline built and the table was written, 1 the baseline did not
# build, 2 the environment cannot be used (not Linux, no workspace, a missing file).
# Output: $CRUX_COMPARISON_OUT (default $repo/build/zephyr/mcuboot-crypto): <variant>/ build directories,
# <variant>.log, <variant>.json and summary.md.
set -euo pipefail

if [[ "$(uname -s)" != Linux ]]; then
    printf 'The MCUboot crypto backend comparison needs the Linux development environment.\n' >&2
    exit 2
fi

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
python="${CRUX_PYTHON:-python3}"
board='mimxrt1060_evk@B//qspi'
files="$repo/zephyr/boot/boards/mimxrt1060_evk_mimxrt1062_qspi_B"
variants="$repo/tests/target/mcuboot-crypto"
app="$repo/samples/controller/zephyr"
image="$(basename "$app")"
out="${CRUX_COMPARISON_OUT:-$repo/build/zephyr/mcuboot-crypto}"
mcuboot="$workspace/bootloader/mcuboot"
public_key="$mcuboot/root-ec-p256.pem"
inspector=("$python" "$repo/tests/target/inspect_boot_image.py")
# The mcuboot flash partition of the composition is 128 KiB and the application slot 3 MiB
# (docs/boot-composition.md).
partition_bytes=131072
slot_bytes=3145728

need() {
    printf 'MCUboot crypto backend comparison: %s\n' "$1" >&2
    exit 2
}

if [[ ! -f "$workspace/.west/config" || ! -d "$workspace/zephyr" ]]; then
    need 'run scripts/bootstrap-zephyr.sh first'
fi
for name in mcuboot.conf mcuboot.overlay app.conf app.overlay; do
    [[ -f "$files/$name" ]] || need "$files/$name is missing"
done
for name in mbedtls-legacy.conf psa.conf psa-mbedtls.conf psa-mbedtls-entropy.conf; do
    [[ -f "$variants/$name" ]] || need "$variants/$name is missing"
done

mkdir -p "$out"

# MCUboot is the plain project in the optional group crux-boot, as in scripts/test-boot-composition.sh.
filter="$(cd "$workspace" && west config manifest.group-filter 2>/dev/null || true)"
if [[ ",$filter," != *",+crux-boot,"* ]]; then
    (cd "$workspace" && west config manifest.group-filter -- "${filter:+$filter,}+crux-boot")
fi
(cd "$workspace" && west update mcuboot)
[[ -f "$public_key" ]] || need "the public test key is not in the MCUboot checkout: $public_key"
"$python" -m pip install --disable-pip-version-check --no-cache-dir -r "$mcuboot/scripts/requirements.txt"
export ZEPHYR_BASE="$workspace/zephyr"

size_tool="$(find "${ZEPHYR_SDK_INSTALL_DIR:-/nonexistent}" -name arm-zephyr-eabi-size -print -quit 2>/dev/null || true)"
[[ -n "$size_tool" ]] || size_tool="$(command -v arm-zephyr-eabi-size || true)"

results=()

# The collection of the sizes of one variant, from files so that bash 3.2 has no quoting trouble.
collector="$out/collect.py"
cat >"$collector" <<'PY'
import json
import os
import re
import subprocess
import sys

(name, status, build, log, target, size_tool, extra, partition, slot, key, imgtool) = sys.argv[1:12]
inspector, image = sys.argv[12:-1], sys.argv[-1]
partition, slot = int(partition), int(slot)
record = {"variant": name, "status": status, "extra_conf": os.path.basename(extra) if extra else None}
text = open(log, errors="replace").read()
if status != "ok":
    errors = [l for l in text.splitlines() if re.search(r"error|Error|undefined|No such|failed|FAILED", l)]
    record["first_errors"] = errors[:25]
else:
    elf = f"{build}/mcuboot/zephyr/zephyr.elf"
    binary = f"{build}/mcuboot/zephyr/zephyr.bin"
    record["bootloader_bin_bytes"] = os.path.getsize(binary)
    record["headroom_bytes"] = partition - record["bootloader_bin_bytes"]
    record["partition_bytes"] = partition
    if size_tool and os.path.isfile(elf):
        out = subprocess.run([size_tool, elf], capture_output=True, text=True).stdout.split("\n")
        if len(out) > 1:
            record["size_berkeley"] = out[1].split()[:3]  # text data bss
    block, take = [], False
    for line in text.splitlines():
        if line.startswith("Memory region"):
            take = True
            block = []
        if take:
            if not line.strip():
                take = False
                record.setdefault("memory_regions", []).append(list(block))
            else:
                block.append(line.rstrip())
    config = f"{build}/mcuboot/zephyr/.config"
    if os.path.isfile(config):
        keep = re.compile(r"^CONFIG_(BOOT_ECDSA|BOOT_USE_|BOOT_SIGNATURE_TYPE|MBEDTLS_HEAP_SIZE|MBEDTLS_VERSION|"
                          r"PSA_CRYPTO|ENTROPY_GENERATOR|MBEDTLS=|MBEDTLS_BUILTIN|MBEDTLS_ENABLE_HEAP)")
        record["config"] = [l for l in open(config).read().splitlines() if keep.match(l)]
    signed = f"{build}/{image}/zephyr/zephyr.signed.bin"
    if os.path.isfile(signed):
        record["signed_app_bytes"] = os.path.getsize(signed)
        done = subprocess.run([sys.executable, imgtool, "verify", "-k", key, signed], capture_output=True, text=True)
        record["signed_app_imgtool_verify"] = "ok" if done.returncode == 0 else f"exit {done.returncode}"
        fit = subprocess.run(inspector + ["fit", signed, "--slot-size", str(slot), "--align", "1",
                                          "--slot-offset", "0x20000", "--json"], capture_output=True, text=True)
        try:
            record["signed_app_fit"] = json.loads(fit.stdout)["result"]
        except Exception:
            record["signed_app_fit"] = f"not decided (exit {fit.returncode})"
json.dump(record, open(target, "w"), indent=2)
print(f"{name}: {status}" + (f", MCUboot zephyr.bin {record['bootloader_bin_bytes']} bytes" if status == "ok" else ""))
PY

reporter="$out/report.py"
cat >"$reporter" <<'PY'
import json
import sys

out, names = sys.argv[1], sys.argv[2:]
rows = [json.load(open(f"{out}/{n}.json")) for n in names]
base = next((r for r in rows if r["variant"] == "tinycrypt-modules-absent" and r["status"] == "ok"), None)
lines = ["| Variant | Build | MCUboot zephyr.bin (B) | Headroom in 128 KiB (B) | Change against the baseline (B) | text / data / bss (B) |",
         "| --- | --- | --- | --- | --- | --- |"]
for r in rows:
    if r["status"] == "ok":
        delta = "-" if base is None else f"{r['bootloader_bin_bytes'] - base['bootloader_bin_bytes']:+d}"
        sizes = " / ".join(r.get("size_berkeley", ["?"] * 3))
        lines.append(f"| {r['variant']} | ok | {r['bootloader_bin_bytes']} | {r['headroom_bytes']} | {delta} | {sizes} |")
    else:
        lines.append(f"| {r['variant']} | failed | - | - | - | - |")
lines.append("")
lines.append("Boot time: not measured (it needs a board).")
text = "\n".join(lines)
open(f"{out}/summary.md", "w").write(text + "\n")
print(text)
for r in rows:
    print()
    print(f"== {r['variant']}: {r['status']}")
    if r["status"] != "ok":
        print("first error lines:")
        for line in r.get("first_errors", []):
            print("  " + line)
    else:
        for key in ("size_berkeley", "signed_app_bytes", "signed_app_imgtool_verify", "signed_app_fit"):
            print(f"  {key}: {r.get(key)}")
        for block in r.get("memory_regions", []):
            for line in block:
                print("  " + line)
        for line in r.get("config", []):
            print("  " + line)
sys.exit(0 if base is not None else 1)
PY

# run_variant NAME [EXTRA_CONF_FILE]: configure and build, then collect the sizes into $out/NAME.json.
run_variant() {
    local name="$1" extra="${2:-}"
    local dir="$out/$name" log="$out/$name.log"
    local mcuboot_conf="$files/mcuboot.conf"
    [[ -z "$extra" ]] || mcuboot_conf="$mcuboot_conf;$extra"
    rm -rf "$dir"
    local status=ok
    (cd "$workspace" && west build --sysbuild -p always -b "$board" -d "$dir" "$app" -- \
        -DZEPHYR_EXTRA_MODULES="$repo" \
        -DPython3_EXECUTABLE="$(command -v "$python")" \
        -DSB_CONFIG_BOOTLOADER_MCUBOOT=y \
        -DSB_CONFIG_MCUBOOT_MODE_RAM_LOAD_WITH_REVERT=y \
        -DSB_CONFIG_BOOT_SIGNATURE_TYPE_ECDSA_P256=y \
        "-Dmcuboot_EXTRA_CONF_FILE=$mcuboot_conf" \
        "-Dmcuboot_EXTRA_DTC_OVERLAY_FILE=$files/mcuboot.overlay" \
        "-D${image}_EXTRA_CONF_FILE=$files/app.conf" \
        "-D${image}_EXTRA_DTC_OVERLAY_FILE=$files/app.overlay") >"$log" 2>&1 || status=failed
    if [[ "$status" == ok && ! -f "$dir/mcuboot/zephyr/zephyr.bin" ]]; then
        status=failed
    fi
    "$python" "$collector" "$name" "$status" "$dir" "$log" "$out/$name.json" "$size_tool" "$extra" \
        "$partition_bytes" "$slot_bytes" "$public_key" "$mcuboot/scripts/imgtool.py" \
        "${inspector[@]}" "$image"
    results+=("$name")
}

# 1. The baseline: the composition of docs/boot-composition.md, tinycrypt (the default), no crypto module
#    in the workspace.
run_variant tinycrypt-modules-absent

# 2. The two Apache-2.0 crypto projects of the optional group crux-secure-management. The group also holds
#    GPL stacks, so only these two projects are fetched, and never with a plain west update.
filter="$(cd "$workspace" && west config manifest.group-filter 2>/dev/null || true)"
if [[ ",$filter," != *",+crux-secure-management,"* ]]; then
    (cd "$workspace" && west config manifest.group-filter -- "${filter:+$filter,}+crux-secure-management")
fi
(cd "$workspace" && west update mbedtls tf-psa-crypto)

run_variant tinycrypt-modules-present
run_variant mbedtls-legacy "$variants/mbedtls-legacy.conf"
run_variant psa "$variants/psa.conf"
run_variant psa-mbedtls "$variants/psa-mbedtls.conf"
run_variant psa-mbedtls-entropy "$variants/psa-mbedtls-entropy.conf"

"$python" "$reporter" "$out" "${results[@]}"
