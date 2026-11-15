#!/usr/bin/env bash
# Read the images that scripts/test-boot-composition.sh built and compare tests/target/inspect_boot_image.py
# with them and with MCUboot's own tool. The real images are the ground truth for the inspector: its
# reading of the TLV layout and of the trailer has so far been checked only against synthetic images
# that the same reading produced (docs/boot-image-inspection.md).
#
# This script builds nothing, programs nothing, boots nothing and generates no key. It reads the build
# directory of the RT1060 composition check ($repo/build/zephyr/boot-composition unless an argument names
# another one) and writes only below $build/check_boot_images.tmp (changed copies of the signed image, the
# inspector's JSON outputs, the images that the oversized check signs with imgtool sign and small helper
# files), which it removes again, also after a failure.
# It is NOT wired into any workflow: a step in .github/workflows/zephyr.yml is a protected-file change
# that needs the project owner's approval (proposal: docs/boot-image-inspection.md, "Check of the
# CI-built images"). It has never run on a real build; the host tests in
# tests/build/test_check_boot_images.py run it against a synthetic build tree and a fake imgtool only.
#
# Usage: tests/target/check_boot_images.sh [build-dir]
# Environment: CRUX_PYTHON (python3 by default), CRUX_WORKSPACE (the parent of the repository by default,
# where bootloader/mcuboot is checked out, as in scripts/test-boot-composition.sh).
# Exit status: 0 every check passed (a key hash that could not be compared is said so on the last line),
# 1 a check failed (including a disagreement between the inspector and imgtool, a missing confirmed image,
# an image that does not fit the slot, imgtool signing into a slot that is too small and an image name that
# is not exactly one file), 2 the build or a tool cannot be used: a missing build directory, image, Python,
# imgtool or key, imgtool without its requirements (a traceback on --help), or a control signing with the
# real slot size that imgtool refuses.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
python="${CRUX_PYTHON:-python3}"
app="$repo/samples/controller/zephyr"
image="$(basename "$app")"
build="${1:-$repo/build/zephyr/boot-composition}"
mcuboot="$workspace/bootloader/mcuboot"
key="$mcuboot/root-ec-p256.pem"
# The slot size and the other signing arguments of the composition page (docs/boot-composition.md).
slot_size=3145728
imgtool=("$python" "$mcuboot/scripts/imgtool.py")
inspector=("$python" "$repo/tests/target/inspect_boot_image.py")

fail() {
    printf 'boot image check failed: %s\n' "$1" >&2
    exit 1
}

missing() {
    printf 'boot image check: %s\nRun scripts/test-boot-composition.sh first, then run this check on its build directory.\n' "$1" >&2
    exit 2
}

command -v "$python" >/dev/null 2>&1 || missing "Python is not available as $python (set CRUX_PYTHON)"
[[ -d "$build" ]] || missing "the build directory $build does not exist"
[[ -d "$build/$image" ]] || missing "the build directory has no application directory $build/$image"
[[ -f "$mcuboot/scripts/imgtool.py" ]] || missing "imgtool is not in the MCUboot checkout: $mcuboot/scripts/imgtool.py"
[[ -f "$key" ]] || missing "the MCUboot test key is not in the checkout: $key"
[[ -f "$repo/tests/target/inspect_boot_image.py" ]] || missing "the inspector tests/target/inspect_boot_image.py is missing"
# imgtool imports packages that the Zephyr requirements do not list. Without them it ends in a traceback,
# which is a missing tool and not a verdict on an image.
if ! imgtool_help="$("${imgtool[@]}" --help 2>&1)" || grep -q Traceback <<<"$imgtool_help"; then
    missing "imgtool does not run (install the requirements of $mcuboot/scripts/requirements.txt): $(grep -v '^$' <<<"$imgtool_help" | tail -n 1)"
fi

# The images sit in the sysbuild directory $build/<image>/zephyr. Only that directory is searched, so a
# stray file deeper in the tree is not taken, and the match must be exactly one file.
app_dir="$build/$image/zephyr"
located=""
locate() {
    local name="$1" line
    local count=0 list=""
    located=""
    if [[ -d "$app_dir" ]]; then
        while IFS= read -r line; do
            [[ -n "$line" ]] || continue
            count=$((count + 1))
            list="${list:+$list, }$line"
            located="$line"
        done < <(find "$app_dir" -maxdepth 1 -name "$name" -print)
    fi
    if [[ "$count" -gt 1 ]]; then
        fail "$name is not exactly one file in $app_dir: $list"
    fi
    [[ "$count" -eq 1 ]] || located=""
}
locate zephyr.signed.bin
signed="$located"
[[ -n "$signed" && -f "$signed" ]] || missing "no zephyr.signed.bin in $app_dir"
mcuboot_bin="$build/mcuboot/zephyr/zephyr.bin"
[[ -f "$mcuboot_bin" ]] || missing "no MCUboot image at $mcuboot_bin"

# At Zephyr v4.4.2 RAM load with revert implies MCUBOOT_GENERATE_CONFIRMED_IMAGE, so the build writes a
# padded, confirmed image next to the signed one (erratum of docs/boot-update-investigation.md). A build
# without it is not the build that the composition page describes.
locate zephyr.signed.confirmed.bin
confirmed="$located"
[[ -n "$confirmed" && -f "$confirmed" ]] ||
    fail "the build produced no zephyr.signed.confirmed.bin in $app_dir; at Zephyr v4.4.2 RAM load with revert implies it (erratum of docs/boot-update-investigation.md), so this is not the build of docs/boot-composition.md"

work="$build/check_boot_images.tmp"
rm -rf "$work"
mkdir -p "$work"
trap 'rm -rf "$work"' EXIT

summary=()
record() {
    summary+=("$(printf '%-34s %-5s %s' "$1" "$2" "$3")")
}

# Run the inspector on a file: $1 output base name. The exit status is kept in $inspector_status, the
# output in $work/<base>.json and $work/<base>.err. Status 2 is a usage error and never expected.
inspector_status=0
run_inspector() {
    local base="$1"
    shift
    inspector_status=0
    "${inspector[@]}" "$@" >"$work/$base.json" 2>"$work/$base.err" || inspector_status=$?
    if [[ "$inspector_status" -eq 126 || "$inspector_status" -eq 127 ]]; then
        missing "the inspector could not be run (exit $inspector_status): $python $repo/tests/target/inspect_boot_image.py"
    fi
    if [[ "$inspector_status" -gt 1 ]]; then
        fail "the inspector exited $inspector_status for: $* ($(head -n 1 "$work/$base.err"))"
    fi
}

jfield() {
    "$python" - "$1" "$2" <<'PY'
import json
import sys

value = json.load(open(sys.argv[1]))
for part in sys.argv[2].split("."):
    value = value[part]
print(value)
PY
}

# imgtool is the authority on the signature. verify_status and verify_output hold the last result.
verify_status=0
verify_output=""
run_verify() {
    verify_status=0
    verify_output="$("${imgtool[@]}" verify -k "$key" "$1" 2>&1)" || verify_status=$?
    if grep -q Traceback <<<"$verify_output"; then
        fail "imgtool crashed instead of answering for $1: $verify_output"
    fi
}

show_both() {
    printf -- '--- inspector (exit %s) ---\n' "$inspector_status" >&2
    cat "$work/$1.json" >&2
    printf -- '--- imgtool verify (exit %s) ---\n%s\n' "$verify_status" "$verify_output" >&2
}

disagree() {
    printf 'boot image check failed: the inspector and imgtool disagree about %s\n' "$1" >&2
    show_both "$2"
    exit 1
}

# ---- (a) the signed application image ----------------------------------------------------------
signed_size="$(wc -c <"$signed" | tr -d ' ')"
run_inspector signed image --json "$signed"
signed_inspector_status="$inspector_status"
run_verify "$signed"
if [[ "$signed_inspector_status" -eq 0 && "$verify_status" -ne 0 ]]; then
    disagree 'the signed image (the inspector reads digest ok, imgtool refuses it)' signed
elif [[ "$signed_inspector_status" -ne 0 && "$verify_status" -eq 0 ]]; then
    disagree 'the signed image (imgtool verifies it, the inspector does not read digest ok)' signed
elif [[ "$signed_inspector_status" -ne 0 ]]; then
    printf 'boot image check failed: neither the inspector nor imgtool accepts %s\n' "$signed" >&2
    show_both signed
    exit 1
fi

# The key hash of the image is the SHA-256 of the public key. imgtool prints the public key in PEM form
# (getpub); openssl is the fallback. The image holds the hash of either the DER SubjectPublicKeyInfo or
# its uncompressed point (the last 65 bytes), so both are computed, and the one that matches is named.
key_hashes() {
    "$python" -c '
import base64, hashlib, re, sys
text = sys.stdin.read()
found = re.search(r"-----BEGIN PUBLIC KEY-----(.*?)-----END PUBLIC KEY-----", text, re.S)
if not found:
    sys.exit(1)
der = base64.b64decode("".join(found.group(1).split()))
point = der[-65:] if len(der) == 91 else der
print(hashlib.sha256(der).hexdigest(), hashlib.sha256(point).hexdigest())
'
}
derived="-"
derived_source="none"
if pem="$("${imgtool[@]}" getpub -k "$key" -e pem 2>/dev/null)" && derived="$(key_hashes <<<"$pem")"; then
    derived_source="imgtool getpub"
elif command -v openssl >/dev/null 2>&1 &&
    pem="$(openssl ec -in "$key" -pubout 2>/dev/null)" && derived="$(key_hashes <<<"$pem")"; then
    derived_source="openssl"
else
    derived="-"
fi
spki_hash="-"
point_hash="-"
if [[ "$derived" != "-" ]]; then
    read -r spki_hash point_hash <<<"$derived"
fi

# The checks run from files, not from a heredoc inside a command substitution, which bash 3.2 cannot
# parse when the text holds an apostrophe.
cat >"$work/check_signed.py" <<'PY'
import json
import sys

report = json.load(open(sys.argv[1]))
file_size = int(sys.argv[2])
spki, point, source = sys.argv[3], sys.argv[4], sys.argv[5]


def bad(message):
    print(message)
    sys.exit(1)


if report["errors"]:
    bad("the inspector reports errors: " + "; ".join(report["errors"]))
if report["result"] != "digest ok" or report["digest"]["status"] != "ok":
    bad(f"the inspector result is {report['result']!r}, digest {report['digest']['status']!r}")
header = report["header"]
if header["hdr_size"] != 0x400:
    bad(f"header size is 0x{header['hdr_size']:x}, expected 0x400")
if header["load_addr"] != 0x80000000:
    bad(f"load address is 0x{header['load_addr']:x}, expected 0x80000000")
tlv_bytes = 0
for area in ("protected_tlv", "unprotected_tlv"):
    if report[area]["present"]:
        tlv_bytes += report[area]["total_length"]
expected = header["hdr_size"] + header["img_size"] + tlv_bytes
if file_size != expected:
    bad(f"file size {file_size} is not header {header['hdr_size']} + image {header['img_size']} + "
        f"TLV areas {tlv_bytes} = {expected}")
if report["padding"]["padded"]:
    bad(f"zephyr.signed.bin carries {report['padding']['trailing_bytes']} trailing bytes; it should be unpadded")
types = {tlv["type"] for tlv in report["unprotected_tlv"]["tlvs"]}
for number, name in ((0x01, "KEYHASH"), (0x10, "SHA256"), (0x22, "ECDSA_SIG")):
    if number not in types:
        bad(f"no {name} TLV (0x{number:02x}) in the unprotected area")
key_hash = report["key_hash"]
if len(key_hash) != 64:
    bad(f"the key hash is {len(key_hash) // 2} bytes, expected 32")
if spki == "-":
    match = "key hash is 32 bytes, NOT compared with the key (imgtool getpub and openssl could not derive the public key)"
elif key_hash == spki:
    match = f"key hash = SHA-256 of the SubjectPublicKeyInfo ({source})"
elif key_hash == point:
    match = f"key hash = SHA-256 of the uncompressed point ({source})"
else:
    bad(f"the key hash {key_hash} equals neither the hash of the public key's SubjectPublicKeyInfo "
        f"{spki} nor that of its point {point}")
print(f"hdr 0x400, load 0x80000000, img_size {header['img_size']}, TLVs {tlv_bytes} B")
print(match)
PY
signed_detail="$("$python" "$work/check_signed.py" "$work/signed.json" "$signed_size" "$spki_hash" "$point_hash" "$derived_source")" ||
    fail "signed image: $signed_detail"
record 'signed image: TLV layout' ok "${signed_detail%%$'\n'*}"
key_detail="${signed_detail#*$'\n'}"
if [[ "$spki_hash" == "-" ]]; then
    record 'signed image: key hash' info "$key_detail"
else
    record 'signed image: key hash' ok "$key_detail"
fi
record 'signed image: inspector vs imgtool' ok 'digest ok and verify ok agree'

# ---- (b) the padded, confirmed image ------------------------------------------------------------
confirmed_size="$(wc -c <"$confirmed" | tr -d ' ')"
[[ "$confirmed_size" -eq "$slot_size" ]] ||
    fail "zephyr.signed.confirmed.bin is $confirmed_size bytes, expected the slot size $slot_size"
run_inspector confirmed image --json "$confirmed"
[[ "$inspector_status" -eq 0 ]] ||
    fail "the inspector does not read digest ok for the confirmed image: $(jfield "$work/confirmed.json" result)"
run_verify "$confirmed"
confirmed_verify="imgtool verify on it: $([[ "$verify_status" -eq 0 ]] && echo ok || echo "refused, exit $verify_status; informational")"

for align in 1 8 16 32; do
    run_inspector "trailer-$align-running" trailer "$confirmed" --align "$align" --slot-size "$slot_size" --running --json
    run_inspector "trailer-$align-idle" trailer "$confirmed" --align "$align" --slot-size "$slot_size" --json
done
cat >"$work/check_confirmed.py" <<'PY'
import json
import sys

work, slot_size = sys.argv[1], int(sys.argv[2])
# The states of docs/plans/image-state-contract-proposal.md, "Slot states", for a trailer with a good magic,
# image_ok set and copy_done unset: the running slot is RUNNING_CONFIRMED (image_ok set, copy_done any),
# a slot that is not running is PENDING_PERMANENT. The inspector prints the proposal's names.
EXPECTED_RUNNING = "RUNNING_CONFIRMED"
EXPECTED_IDLE = "PENDING_PERMANENT"


def load(name):
    return json.load(open(f"{work}/{name}.json"))


def bad(message):
    print(message)
    sys.exit(1)


image = load("confirmed")
trailer_magic = image["padding"]["trailer_magic"]
if trailer_magic != "good":
    bad(f"the confirmed image does not end with a known trailer magic (inspector: {trailer_magic})")
magic_alignment = image["padding"]["trailer_alignment"]

survey, consistent, matching = [], [], []
for align in (1, 8, 16, 32):
    running, idle = load(f"trailer-{align}-running"), load(f"trailer-{align}-idle")
    ok = running["ok"] and running["magic"]["state"] == "good"
    flags = f"image_ok {running['image_ok']['state']}, copy_done {running['copy_done']['state']}"
    survey.append(f"alignment {align:>2}: magic {running['magic']['state']}"
                  + (f" (the magic of alignment {running['magic']['alignment_hint']})"
                     if running["magic"]["alignment_hint"] else "")
                  + f", {flags}, running {running['slot_state']}, not running {idle['slot_state']}, "
                  + ("decodes consistently" if ok else "INCONSISTENT"))
    if ok:
        consistent.append(align)
        if (running["image_ok"]["state"] == "set" and running["copy_done"]["state"] == "unset"
                and running["slot_state"] == EXPECTED_RUNNING and idle["slot_state"] == EXPECTED_IDLE):
            matching.append(align)
with open(f"{work}/survey.txt", "w") as stream:
    stream.write("\n".join("  " + line for line in survey) + "\n")
if not consistent:
    bad("no alignment of 1, 8, 16 and 32 decodes the trailer consistently (survey above)")
if not matching:
    bad(f"the trailer decodes consistently for alignment {consistent} but not to {EXPECTED_RUNNING} "
        f"(running) and {EXPECTED_IDLE} (not running) with image_ok set and copy_done unset (survey above)")
print(f"size {slot_size}, digest ok, trailer magic good (the magic of alignment {magic_alignment}), "
      f"{EXPECTED_RUNNING}/{EXPECTED_IDLE} at --align {','.join(map(str, matching))}")
PY
confirmed_detail="$("$python" "$work/check_confirmed.py" "$work" "$slot_size")" || {
    if [[ -f "$work/survey.txt" ]]; then
        printf 'Alignment survey of the confirmed image:\n' >&2
        cat "$work/survey.txt" >&2
    fi
    fail "confirmed image: $confirmed_detail"
}
record 'confirmed image: digest, trailer' ok "$confirmed_detail"
record 'confirmed image: imgtool' info "$confirmed_verify"

# ---- (c) the MCUboot image has no image header ---------------------------------------------------
run_inspector mcuboot-header image --header-only --json "$mcuboot_bin"
[[ "$(jfield "$work/mcuboot-header.json" classification)" == 'no image' ]] ||
    fail "the inspector finds an image magic at the start of the MCUboot image $mcuboot_bin"
run_inspector mcuboot-image image --json "$mcuboot_bin"
[[ "$inspector_status" -eq 1 ]] ||
    fail "the inspector accepts the MCUboot image as an MCUboot image (exit $inspector_status)"
record 'MCUboot zephyr.bin: no image' ok "no image magic; the full image command exits 1"

# ---- (d) a changed byte is a digest mismatch for both tools --------------------------------------
# 0x300 is in the header padding, 0x400 + 0x100 is in the payload (scripts/test-boot-composition.sh).
for offset in 0x300 0x500; do
    modified="$work/zephyr.signed.modified.bin"
    "$python" - "$signed" "$modified" "$offset" <<'PY'
import sys

data = bytearray(open(sys.argv[1], "rb").read())
data[int(sys.argv[3], 16)] ^= 0xFF
open(sys.argv[2], "wb").write(data)
PY
    run_inspector "modified-$offset" image --json "$modified"
    [[ "$inspector_status" -eq 1 && "$(jfield "$work/modified-$offset.json" result)" == 'digest MISMATCH' ]] ||
        fail "an image changed at $offset is not a digest mismatch for the inspector (exit $inspector_status, $(jfield "$work/modified-$offset.json" result))"
    run_verify "$modified"
    [[ "$verify_status" -ne 0 ]] || disagree "an image changed at $offset (the inspector reads a digest mismatch, imgtool verifies it)" "modified-$offset"
    rm -f "$modified"
    record "changed byte at $offset" ok 'inspector: digest MISMATCH, imgtool: refused'
done

# ---- (e) fit in the slot: oversized and misaligned -------------------------------------------
# The inspector's `fit` command decides by the repository's trailer model whether an image and its
# trailer region fit the slot, and whether the slot layout and a padded image's trailer are aligned.
# The real images must fit the slot of the composition (3 MiB at 0x20000), with the alignment that the
# confirmed image's trailer magic carries. Then the same image is offered to the inspector and to
# imgtool sign with a slot that is too small: the inspector must say it does not fit, and imgtool must
# refuse, without a crash. A control with the real slot size must sign, so that a refusal is not the
# effect of arguments that imgtool cannot take. This checks the two tools on the build's own
# input, not a boot result, and imgtool's reaction to a misaligned layout is not checked here.
slot_offset=0x20000
fit_align="$(jfield "$work/confirmed.json" padding.trailer_alignment)"
for pair in "confirmed:$confirmed" "signed:$signed"; do
    run_inspector "fit-${pair%%:*}" fit "${pair#*:}" --slot-size "$slot_size" --align "$fit_align" --slot-offset "$slot_offset" --json
    [[ "$inspector_status" -eq 0 ]] || {
        cat "$work/fit-${pair%%:*}.json" >&2
        fail "the inspector says the ${pair%%:*} image does not fit the slot of $slot_size bytes at alignment $fit_align"
    }
done
record 'fit: images in the slot' ok "signed and confirmed image fit $slot_size B at 0x20000, alignment $fit_align"

run_inspector fit-over fit "$signed" --slot-size "$signed_size" --align "$fit_align" --erase-unit 1 --json
[[ "$inspector_status" -eq 1 && "$(jfield "$work/fit-over.json" result)" == 'does not fit' ]] ||
    fail "the inspector does not call the signed image oversized for a slot of $signed_size bytes (exit $inspector_status)"
record 'oversized: inspector' ok "a slot of $signed_size B (the image itself) does not fit: the trailer needs $(jfield "$work/fit-over.json" over_by) B more"

locate zephyr.bin
unsigned="$located"
if [[ -z "$unsigned" || ! -f "$unsigned" ]]; then
    record 'oversized: imgtool sign' info "not run: no zephyr.bin in $app_dir"
else
    sign_status=0
    sign_output=""
    run_sign() {
        sign_status=0
        sign_output="$("${imgtool[@]}" sign -k "$key" --header-size 0x400 --align 1 --version 0.0.0 \
            --slot-size "$1" "$unsigned" "$work/sign-$1.bin" 2>&1)" || sign_status=$?
        if grep -q Traceback <<<"$sign_output"; then
            fail "imgtool crashed instead of answering for a slot of $1 bytes: $sign_output"
        fi
    }
    run_sign "$slot_size"
    if [[ "$sign_status" -ne 0 ]]; then
        printf 'boot image check: the control signing with the real slot size %s was refused (exit %s), so the arguments of this check do not suit this imgtool: %s\n' \
            "$slot_size" "$sign_status" "$sign_output" >&2
        exit 2
    fi
    run_sign "$signed_size"
    [[ "$sign_status" -ne 0 ]] ||
        fail "imgtool signed $unsigned into a slot of $signed_size bytes, which the inspector says is too small for the image and its trailer"
    record 'oversized: imgtool sign' ok "refused a slot of $signed_size B; the control with $slot_size B signed"
fi
record 'misaligned layout' info 'decided by the inspector only (host tests); imgtool is not asked'

printf 'Boot image check (the images of %s, nothing booted):\n' "$build"
printf '  %s\n' "${summary[@]}"
printf 'Alignment survey of the confirmed image (the open --align question of docs/boot-image-inspection.md; evidence only, not a pass criterion):\n'
cat "$work/survey.txt"
printf '%s\n' "Boot image check passed. The result is about the inspector's reading of these images; imgtool verify stays authoritative."
if [[ "$spki_hash" == "-" ]]; then
    printf 'key hash NOT compared with the key\n'
fi
