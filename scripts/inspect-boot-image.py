#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Inspect an MCUboot image or a slot trailer. A developer tool, not a Crux interface.

  image <file>    parse the header and the TLV areas of an MCUboot image and compare the SHA-256
                  that MCUboot hashes with the SHA256 TLV
  trailer <file>  decode the MCUboot trailer at the end of a slot dump or of a padded image

The standard library only, and no access to a board, a key or a flash tool. The format notes in
this file come from the repository's records, not from MCUboot's source:

* Image header, 32 bytes, little endian: magic 0x96f3b83d, load_addr, hdr_size (u16), protect_tlv_size
  (u16), img_size, flags, version (major u8, minor u8, revision u16, build_num u32) and 4 reserved bytes.
  Source: `ModelImage` in tests/native/emmc_trailer/trailer_model.py. The header is followed by padding up
  to hdr_size, then img_size bytes of payload.
* TLV areas: an info header (magic u16, total length u16 including the info header) and entries (type
  u8, one pad byte, length u16, value). The protected area (magic 0x6908, protect_tlv_size bytes) comes
  first when the header says it exists, then the unprotected area (magic 0x6907). The repository does not
  record these magics or the entry layout; they, and what MCUboot hashes (the header up to hdr_size, the
  payload and the protected TLV area), are the author's reading of MCUboot's image format and are the
  least checked part of this tool. docs/evidence/boot-update/stage1-pinned-source-findings.md (B50) only
  says that the image copy covers header, payload, protected TLVs and TLVs.
* Trailer: at the end of a slot, the 16-byte magic, then image_ok, copy_done and swap_info, each one
  alignment unit below the previous one. Source: `Layout` in trailer_model.py (boot_magic_off,
  boot_image_ok_off, boot_copy_done_off, boot_swap_info_off) and the trailer-replay record in
  docs/evidence/boot-emmc/trailer-replay/README.md.
* Slot state names: docs/plans/image-state-contract-proposal.md, "Slot states".

Exit status: 0 when the input decodes (and, for an image, the digest matches), 1 when it parses but is
inconsistent or the digest does not match, 2 for a usage error or an unreadable file.
"""
import argparse
import hashlib
import json
import struct
import sys

IMAGE_MAGIC = 0x96F3B83D
HEADER_STRUCT = struct.Struct("<IIHHIIBBHII")
TLV_INFO = struct.Struct("<HH")
TLV_ENTRY = struct.Struct("<BBH")
PROTECTED_MAGIC = 0x6908
UNPROTECTED_MAGIC = 0x6907
TLV_NAMES = {0x01: "KEYHASH", 0x10: "SHA256", 0x22: "ECDSA_SIG"}
TLV_SHORT_VALUE = 32

ERASED = 0xFF
MAGIC_SIZE = 16
# The repository's record (trailer_model.py): the magic of BOOT_MAX_ALIGN 8, and for any other
# alignment the alignment as a little-endian u16 followed by a common tail.
MAGIC_ALIGN_8 = bytes.fromhex("77c295f360d2ef7f3552500f2cb67980")
MAGIC_TAIL = bytes.fromhex("2de15d29410b8d77679c110f1f8a")
MAX_ALIGN = 0xFFFF
# Far from zero and a multiple of every alignment, so offsets from the slot end do not depend on the
# length of the file.
_REFERENCE_END = 1 << 40

SWAP_TYPE_NAMES = {1: "none", 2: "test", 3: "perm"}
STATE_DESCRIPTIONS = {
    "EMPTY": "no valid image header",
    "STAGED": "image staged, trailer unset, no request written",
    "PENDING_TEST": "test request pending",
    "PENDING_PERMANENT": "permanent request pending",
    "TRIED": "tried and not confirmed (the bootloader erases it at the next reset)",
    "STANDBY_CONFIRMED": "confirmed image, not the running slot",
    "RUNNING_CONFIRMED": "running slot, confirmed",
    "RUNNING_TESTING": "running slot on trial, not confirmed",
    "INVALID": "magic bad or a flag outside set and unset",
    "ERR_BOOT_STATE": "running slot without a good magic: the start fails with ERR_BOOT_STATE",
}

SIGNATURE_NOTE = (
    "This is a digest check only and NOT a signature verification: the signature and the key are "
    "not checked. `imgtool verify` stays authoritative."
)
LAYOUT_NOTE = (
    "The layouts are taken from the repository's records of MCUboot's format and are not checked "
    "against upstream source in this repository's tests."
)
EPILOG = (
    "image reports a digest check only and NOT a signature verification: `imgtool verify` stays "
    "authoritative.\n"
    f"{LAYOUT_NOTE}\n"
    "Exit status: 0 decodes (image: digest matches), 1 inconsistent or digest mismatch, 2 usage error."
)


def hex_of(data):
    return bytes(data).hex()


def read_u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


# --------------------------------------------------------------------------------------------
# Trailer magic and trailer decoding
# --------------------------------------------------------------------------------------------

def magic_for(align):
    """The good trailer magic for an alignment unit, as the repository records it."""
    if align == 8:
        return MAGIC_ALIGN_8
    return struct.pack("<H", align) + MAGIC_TAIL


def identify_magic(magic):
    """The alignment that a 16-byte trailer magic belongs to, or None if it is not a known magic."""
    magic = bytes(magic)
    if magic == MAGIC_ALIGN_8:
        return 8
    if len(magic) == MAGIC_SIZE and magic[2:] == MAGIC_TAIL:
        align = read_u16(magic, 0)
        if align:
            return align
    return None


def _align_down(value, unit):
    return value - value % unit


def trailer_distances(align):
    """Distance from the slot end of the magic and of the image_ok, copy_done and swap_info bytes."""
    end = _REFERENCE_END + (-_REFERENCE_END) % align
    magic = end - MAGIC_SIZE
    image_ok = _align_down(magic - align, align)
    copy_done = image_ok - align
    swap_info = copy_done - align
    return {"magic": end - magic, "image_ok": end - image_ok, "copy_done": end - copy_done,
            "swap_info": end - swap_info}


def _flag_state(value):
    if value == ERASED:
        return "unset"
    return "set" if value == 1 else "bad"


def _slot_state(header, running, magic, image_ok, copy_done):
    if header == "no image magic":
        return "EMPTY"
    flags = (image_ok, copy_done)
    if running:
        if magic != "good":
            return "ERR_BOOT_STATE"
        if image_ok == "set":
            return "RUNNING_CONFIRMED"
        if image_ok == "unset":
            return "RUNNING_TESTING"
        return "INVALID"
    if magic == "bad" or "bad" in flags:
        return "INVALID"
    if magic == "unset":
        return "STAGED"
    return {
        ("unset", "unset"): "PENDING_TEST",
        ("set", "unset"): "PENDING_PERMANENT",
        ("unset", "set"): "TRIED",
        ("set", "set"): "STANDBY_CONFIRMED",
    }[flags]


def decode_trailer(data, align, slot_size=None, running=False, check_header=False):
    """Decode the trailer at the end of data for the alignment unit align.

    The fields are found by their distance from the end of the data, which is the slot end for a slot
    dump, a padded image or a dump of the trailer region. The header is examined only for a whole slot
    (data as long as slot_size) or when check_header is true. running says that the slot is the running
    one, which the file cannot tell.
    """
    data = bytes(data)
    errors, warnings, notes = [], [], []
    size = len(data)
    distances = trailer_distances(align)
    offsets = {name: size - distance for name, distance in distances.items()}

    if slot_size is None:
        slot_check = "not given"
    elif size == slot_size:
        slot_check = "equal"
    elif size > slot_size:
        slot_check = "longer"
        notes.append(f"the file is {size - slot_size} bytes longer than the slot size {slot_size}; the "
                     "trailer is read at the end of the file")
    else:
        slot_check = "shorter"
        notes.append(f"the file is {slot_size - size} bytes shorter than the slot size {slot_size}; the "
                     "trailer is read at the end of the file, so this is only right if the file ends "
                     "at the slot end")
    if align > 1 and size % align:
        notes.append(f"the file length is not a multiple of the alignment {align}; the offsets are "
                     "counted from the end of the file as if it ended on a slot boundary")

    needed = max(distances.values())
    readable = min(offsets.values()) >= 0
    if not readable:
        errors.append(f"the file is too short for a trailer of alignment {align}: {size} bytes, at "
                      f"least {needed} needed")

    def field(name):
        if not readable:
            return {"offset": None, "value": None, "state": "unreadable"}
        raw = data[offsets[name]]
        return {"offset": offsets[name], "value": None if raw == ERASED else raw,
                "state": _flag_state(raw) if name != "swap_info" else
                ("unset" if raw == ERASED else "set")}

    image_ok, copy_done, swap_info = field("image_ok"), field("copy_done"), field("swap_info")

    if size >= MAGIC_SIZE:
        raw_magic = data[size - MAGIC_SIZE:]
    else:
        raw_magic = b""
    hint = None
    if not raw_magic:
        magic_state = "unreadable"
    elif raw_magic == bytes([ERASED]) * MAGIC_SIZE:
        magic_state = "unset"
    elif raw_magic == magic_for(align):
        magic_state = "good"
    else:
        magic_state = "bad"
        hint = identify_magic(raw_magic)
        if hint is not None:
            errors.append(f"magic is bad for alignment {align}; it is the magic for alignment {hint}")
        else:
            errors.append("magic is bad: neither the good magic for this alignment nor all 0xFF")
    magic = {"offset": size - MAGIC_SIZE if raw_magic else None, "bytes_hex": hex_of(raw_magic),
             "state": magic_state, "alignment_hint": hint}

    if readable:
        for name, entry in (("image_ok", image_ok), ("copy_done", copy_done)):
            if entry["state"] == "bad":
                errors.append(f"{name} is bad (0x{entry['value']:02x}): neither 0x01 nor erased")
        if magic_state == "unset":
            for name, entry in (("image_ok", image_ok), ("copy_done", copy_done), ("swap_info", swap_info)):
                if entry["state"] != "unset":
                    errors.append(f"{name} is not unset under an unset magic")

    swap_type = swap_name = image_num = None
    if swap_info["value"] is None:
        if readable:
            swap_type, swap_name = 1, SWAP_TYPE_NAMES[1]
    else:
        swap_type, image_num = swap_info["value"] & 0x0F, swap_info["value"] >> 4
        swap_name = SWAP_TYPE_NAMES.get(swap_type, f"other ({swap_type})")
        if swap_type > 4:
            warnings.append(f"swap_info type {swap_type} is above 4; the repository's model reads it as none")
        elif swap_type == 2 and image_ok["state"] == "set":
            warnings.append("swap_info says test request but image_ok is set")
        elif swap_type == 3 and image_ok["state"] == "unset":
            warnings.append("swap_info says permanent request but image_ok is unset")
    swap_info.update({"swap_type": swap_type, "swap_type_name": swap_name, "image_num": image_num})

    if check_header or slot_size == size:
        has_magic = size >= 4 and struct.unpack_from("<I", data, 0)[0] == IMAGE_MAGIC
        header = "image magic present" if has_magic else "no image magic"
    else:
        header = "not examined"
        notes.append("the image header is not in the file or was not asked for, so the slot state "
                     "assumes a valid image header")

    if running and readable and magic_state != "good":
        errors.append("the running slot has no good magic: the start fails with ERR_BOOT_STATE")

    if not readable:
        trailer_state = slot_state = description = None
    else:
        slot_state = _slot_state(header, running, magic_state, image_ok["state"], copy_done["state"])
        description = STATE_DESCRIPTIONS[slot_state]
        if magic_state == "good":
            trailer_state = "good"
        elif magic_state == "bad":
            trailer_state = "bad"
        elif all(entry["state"] == "unset" for entry in (image_ok, copy_done, swap_info)):
            trailer_state = "unset"
        else:
            trailer_state = "inconsistent"

    return {
        "kind": "trailer",
        "file_size": size,
        "alignment": align,
        "slot_size": slot_size,
        "slot_size_check": slot_check,
        "offsets": offsets,
        "magic": magic,
        "image_ok": image_ok,
        "copy_done": copy_done,
        "swap_info": swap_info,
        "header": header,
        "running": bool(running),
        "trailer_state": trailer_state,
        "slot_state": slot_state,
        "state_description": description,
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "notes": notes,
    }


# --------------------------------------------------------------------------------------------
# Image parsing
# --------------------------------------------------------------------------------------------

def _empty_area():
    return {"present": False, "offset": None, "magic": None, "total_length": None, "tlvs": []}


def _parse_area(data, offset, expected_magic, label, errors, expected_total=None):
    """Parse one TLV area at offset. Returns the area dict and the offset after the area."""
    area = _empty_area()
    area["offset"] = offset
    if offset + TLV_INFO.size > len(data):
        errors.append(f"the {label} TLV area at offset {offset} starts beyond the end of the file")
        return area, offset
    magic, total = TLV_INFO.unpack_from(data, offset)
    area.update({"present": True, "magic": magic, "total_length": total})
    if magic != expected_magic:
        errors.append(f"the {label} TLV area at offset {offset} has magic 0x{magic:04x}, expected "
                      f"0x{expected_magic:04x}")
        return area, offset
    if expected_total is not None and total != expected_total:
        errors.append(f"the {label} TLV area length {total} differs from protect_tlv_size {expected_total}")
    if total < TLV_INFO.size:
        errors.append(f"the {label} TLV area length {total} is shorter than its info header")
        return area, offset
    end = offset + total
    if end > len(data):
        errors.append(f"the {label} TLV area ends at offset {end}, beyond the end of the file "
                      f"({len(data)} bytes)")
        limit = len(data)
    else:
        limit = end
    position = offset + TLV_INFO.size
    while position < limit:
        if position + TLV_ENTRY.size > limit:
            errors.append(f"a TLV header at offset {position} runs beyond the end of the {label} area")
            break
        kind, _, length = TLV_ENTRY.unpack_from(data, position)
        value_start = position + TLV_ENTRY.size
        if value_start + length > limit:
            errors.append(f"the TLV 0x{kind:02x} at offset {position} (length {length}) extends beyond the "
                          f"end of the {label} area or the file")
            break
        area["tlvs"].append({
            "type": kind,
            "type_name": TLV_NAMES.get(kind),
            "type_hex": f"0x{kind:02x}",
            "offset": position,
            "length": length,
            "value_hex": hex_of(data[value_start:value_start + length]),
        })
        position = value_start + length
    return area, end


def inspect_image(data):
    """Parse an MCUboot image and check its SHA-256 digest. Not a signature check."""
    data = bytes(data)
    errors, notes = [], []
    report = {
        "kind": "image",
        "file_size": len(data),
        "result": None,
        "ok": False,
        "signature_verified": False,
        "signature_note": SIGNATURE_NOTE,
        "header": None,
        "protected_tlv": _empty_area(),
        "unprotected_tlv": _empty_area(),
        "digest": {
            "covers": "header up to hdr_size (with its padding), payload, protected TLV area",
            "computed": None,
            "expected": None,
            "status": "not computed",
        },
        "key_hash": None,
        "padding": {"padded": False, "trailing_bytes": 0, "trailer_magic": "none",
                    "trailer_alignment": None, "trailer": None},
        "errors": errors,
        "notes": notes,
    }
    if len(data) < HEADER_STRUCT.size:
        errors.append(f"the file is {len(data)} bytes, shorter than the {HEADER_STRUCT.size}-byte image header")
        return _finish_image(report)

    (magic, load_addr, hdr_size, protect_size, img_size, flags, major, minor, revision, build_num,
     _reserved) = HEADER_STRUCT.unpack_from(data, 0)
    report["header"] = {
        "magic": magic,
        "magic_ok": magic == IMAGE_MAGIC,
        "load_addr": load_addr,
        "hdr_size": hdr_size,
        "protect_tlv_size": protect_size,
        "img_size": img_size,
        "flags": flags,
        "version": {"major": major, "minor": minor, "revision": revision, "build_num": build_num},
        "version_string": f"{major}.{minor}.{revision}+{build_num}",
    }
    if magic != IMAGE_MAGIC:
        errors.append(f"bad image magic 0x{magic:08x}, expected 0x{IMAGE_MAGIC:08x}")
        return _finish_image(report)
    if hdr_size < HEADER_STRUCT.size:
        errors.append(f"hdr_size {hdr_size} is smaller than the {HEADER_STRUCT.size}-byte header")
        return _finish_image(report)
    payload_end = hdr_size + img_size
    if payload_end > len(data):
        errors.append(f"the payload ends at offset {payload_end}, beyond the end of the file "
                      f"({len(data)} bytes)")
        return _finish_image(report)

    protected_end = payload_end
    if protect_size:
        area, protected_end = _parse_area(data, payload_end, PROTECTED_MAGIC, "protected", errors,
                                          expected_total=protect_size)
        report["protected_tlv"] = area
        protected_end = payload_end + protect_size
    elif payload_end + TLV_INFO.size <= len(data) and read_u16(data, payload_end) == PROTECTED_MAGIC:
        errors.append("a protected TLV area follows the payload but protect_tlv_size is 0")
    if protected_end > len(data):
        return _finish_image(report)

    area, end = _parse_area(data, protected_end, UNPROTECTED_MAGIC, "unprotected", errors)
    report["unprotected_tlv"] = area

    digests = [t for t in area["tlvs"] if t["type"] == 0x10]
    keyhashes = [t for t in area["tlvs"] if t["type"] == 0x01]
    if keyhashes:
        report["key_hash"] = keyhashes[0]["value_hex"]
    if not digests:
        errors.append("there is no SHA256 TLV in the unprotected area")
    else:
        computed = hashlib.sha256(data[:protected_end]).hexdigest()
        expected = digests[0]["value_hex"]
        report["digest"].update({"computed": computed, "expected": expected,
                                 "status": "ok" if computed == expected else "MISMATCH"})

    if not errors:
        _inspect_padding(data, end, report)
    return _finish_image(report)


def _inspect_padding(data, end, report):
    trailing = len(data) - end
    padding = report["padding"]
    padding["padded"] = trailing > 0
    padding["trailing_bytes"] = trailing
    erased_until = len(data)
    if trailing >= MAGIC_SIZE:
        align = identify_magic(data[len(data) - MAGIC_SIZE:])
        if align is not None:
            padding["trailer_magic"] = "good"
            padding["trailer_alignment"] = align
            reach = max(trailer_distances(align).values())
            if len(data) - reach >= end:
                padding["trailer"] = decode_trailer(data, align, check_header=True)
                erased_until = len(data) - reach
            else:
                report["notes"].append(f"the trailer fields of alignment {align} would overlap the image, "
                                       "so the trailer is not decoded")
    if trailing and any(b != ERASED for b in data[end:erased_until]):
        report["notes"].append("some padding bytes are not erased (not 0xFF)")
    if trailing and padding["trailer_magic"] == "none":
        report["notes"].append("the file ends with padding but not with a known trailer magic")


def _finish_image(report):
    if report["errors"]:
        report["result"] = "structure inconsistent"
    elif report["digest"]["status"] == "ok":
        report["result"] = "digest ok"
    else:
        report["result"] = "digest MISMATCH"
    report["ok"] = report["result"] == "digest ok"
    return report


def inspect_header_only(data):
    """Report whether a short read of the start of a slot carries the image magic."""
    data = bytes(data)
    if len(data) < 4:
        raise ValueError("a header-only check needs at least 4 bytes")
    present = struct.unpack_from("<I", data, 0)[0] == IMAGE_MAGIC
    return {
        "kind": "image-header",
        "file_size": len(data),
        "bytes_read_hex": hex_of(data[:32]),
        "image_magic_present": present,
        "classification": "image magic present" if present else "no image",
        "erased": all(b == ERASED for b in data),
        "ok": True,
        "note": "Only the 4-byte image magic at offset 0 was checked. Nothing else about the image is known.",
    }


# --------------------------------------------------------------------------------------------
# Text output
# --------------------------------------------------------------------------------------------

def _short(value_hex):
    if len(value_hex) // 2 <= TLV_SHORT_VALUE:
        return value_hex
    return value_hex[:32] + "..."


def _format_area(label, area):
    if not area["present"]:
        return [f"{label}: absent"]
    lines = [f"{label}: offset 0x{area['offset']:x}, magic 0x{area['magic']:04x}, total length "
             f"{area['total_length']}"]
    for tlv in area["tlvs"]:
        name = tlv["type_name"] or "unknown"
        lines.append(f"  {tlv['type_hex']} {name}, length {tlv['length']}: {_short(tlv['value_hex'])}")
    return lines


def format_image(report, name="image"):
    lines = [f"MCUboot image: {name} ({report['file_size']} bytes)", report["signature_note"]]
    header = report["header"]
    if header:
        lines += [
            "Header:",
            f"  magic 0x{header['magic']:08x} ({'ok' if header['magic_ok'] else 'BAD'})",
            f"  load_addr 0x{header['load_addr']:08x}",
            f"  hdr_size 0x{header['hdr_size']:x}, protect_tlv_size {header['protect_tlv_size']}, "
            f"img_size {header['img_size']}",
            f"  flags 0x{header['flags']:08x}",
            f"  version {header['version_string']}",
        ]
    lines += _format_area("Protected TLV area", report["protected_tlv"])
    lines += _format_area("Unprotected TLV area", report["unprotected_tlv"])
    digest = report["digest"]
    lines += [f"Digest covers: {digest['covers']}",
              f"  computed: {digest['computed']}",
              f"  expected: {digest['expected']}",
              f"  status: {digest['status']}"]
    lines.append(f"Key hash (SHA-256 of the public key, as the image carries it): {report['key_hash']}")
    padding = report["padding"]
    if padding["padded"]:
        lines.append(f"Padding: {padding['trailing_bytes']} trailing bytes after the TLV area")
    else:
        lines.append("Padding: none (the file ends with the TLV area)")
    if padding["trailer_magic"] == "good":
        lines.append(f"Trailer magic at the end of the file: good, alignment {padding['trailer_alignment']}")
        trailer = padding["trailer"]
        if trailer:
            lines.append(f"  image_ok {trailer['image_ok']['state']}, copy_done {trailer['copy_done']['state']}, "
                         f"swap_info {trailer['swap_info']['state']}: {trailer['slot_state']} "
                         f"({trailer['state_description']})")
    else:
        lines.append("Trailer magic at the end of the file: none")
    for error in report["errors"]:
        lines.append(f"ERROR: {error}")
    for note in report["notes"]:
        lines.append(f"Note: {note}")
    lines.append(f"Result: {report['result']}")
    return "\n".join(lines)


def format_header_only(report, name="image"):
    text = report["classification"]
    if not report["image_magic_present"] and report["erased"]:
        text += " (erased: every byte read is 0xFF)"
    return "\n".join([
        f"MCUboot image header check: {name} ({report['file_size']} bytes read)",
        f"Result: {text}",
        report["note"],
    ])


def _format_flag(name, entry):
    if entry["offset"] is None:
        return f"{name:<9} unreadable"
    value = "0xff (erased)" if entry["value"] is None else f"0x{entry['value']:02x}"
    return f"{name:<9} offset 0x{entry['offset']:x}, value {value}: {entry['state']}"


def format_trailer(report, name="trailer"):
    magic = report["magic"]
    lines = [f"MCUboot trailer: {name} ({report['file_size']} bytes), alignment {report['alignment']}"]
    if magic["offset"] is None:
        lines.append("magic     unreadable")
    else:
        extra = f" (the magic of alignment {magic['alignment_hint']})" if magic["alignment_hint"] else ""
        lines.append(f"magic     offset 0x{magic['offset']:x}, {magic['bytes_hex']}: {magic['state']}{extra}")
    lines.append(_format_flag("image_ok", report["image_ok"]))
    lines.append(_format_flag("copy_done", report["copy_done"]))
    swap = report["swap_info"]
    lines.append(_format_flag("swap_info", swap) + (
        f", type {swap['swap_type']} ({swap['swap_type_name']}), image {swap['image_num']}"
        if swap["value"] is not None else ""))
    lines.append(f"slot size: {report['slot_size_check']}"
                 + (f" ({report['slot_size']})" if report["slot_size"] is not None else ""))
    lines.append(f"header: {report['header']}")
    if report["slot_state"]:
        lines.append(f"trailer: {report['trailer_state']}")
        lines.append(f"slot state: {report['slot_state']} ({report['state_description']})"
                     + (" [running slot assumed]" if report["running"] else ""))
    for error in report["errors"]:
        lines.append(f"ERROR: {error}")
    for warning in report["warnings"]:
        lines.append(f"Warning: {warning}")
    for note in report["notes"]:
        lines.append(f"Note: {note}")
    lines.append(LAYOUT_NOTE)
    lines.append("Result: " + ("trailer decodes" if report["ok"] else "trailer inconsistent"))
    return "\n".join(lines)


# --------------------------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------------------------

def _positive_int(text):
    try:
        value = int(text, 0)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be positive: {text!r}")
    return value


def _alignment(text):
    value = _positive_int(text)
    if value > MAX_ALIGN:
        raise argparse.ArgumentTypeError(f"must be at most {MAX_ALIGN}: {text!r}")
    return value


def build_parser():
    parser = argparse.ArgumentParser(
        prog="inspect-boot-image.py",
        description=(
            "Inspect an MCUboot image or a slot trailer. A developer tool, not a Crux interface: no "
            "board, key or flash access."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="{image,trailer}")
    image = sub.add_parser(
        "image",
        help="parse an MCUboot image and check its digest",
        description=(
            "Parse an MCUboot image: header, TLV areas, and the SHA-256 over the header, payload and "
            "protected TLVs compared with the SHA256 TLV. This is a digest check only and NOT a "
            "signature verification."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    image.add_argument("file")
    image.add_argument("--json", action="store_true", help="print the report as JSON")
    image.add_argument(
        "--header-only", action="store_true",
        help="accept a short read of at least 4 bytes and report only whether the image magic is present "
             "(the slot 1 header check); exit 0 either way")
    trailer = sub.add_parser(
        "trailer",
        help="decode the MCUboot trailer at the end of a slot dump or image file",
        description=(
            "Decode the MCUboot trailer in the last bytes of a file: the 16-byte magic, image_ok, "
            "copy_done and swap_info for the alignment unit N, and the slot state name of "
            "docs/plans/image-state-contract-proposal.md. It does not check any signature."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    trailer.add_argument("file")
    trailer.add_argument("--align", type=_alignment, required=True, metavar="N",
                         help="alignment unit of the trailer (BOOT_MAX_ALIGN in the repository's model)")
    trailer.add_argument("--slot-size", type=_positive_int, metavar="S",
                         help="slot size in bytes; the length of the file is compared with it, and a "
                              "file of exactly this length is treated as a whole slot with a header")
    trailer.add_argument("--running", action="store_true",
                         help="the slot is the running slot (the file cannot tell)")
    trailer.add_argument("--check-header", action="store_true",
                         help="the file starts with the image header: check the image magic at offset 0")
    trailer.add_argument("--json", action="store_true", help="print the report as JSON")
    return parser


def main(argv=None):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:
        return stop.code if isinstance(stop.code, int) else 2
    try:
        with open(args.file, "rb") as stream:
            data = stream.read()
    except OSError as error:
        print(f"error: cannot read {args.file}: {error.strerror or error}", file=sys.stderr)
        return 2

    if args.command == "image":
        if args.header_only:
            try:
                report = inspect_header_only(data)
            except ValueError as error:
                print(f"error: {args.file}: {error}", file=sys.stderr)
                return 2
            text = format_header_only(report, args.file)
        else:
            report = inspect_image(data)
            text = format_image(report, args.file)
    else:
        report = decode_trailer(data, args.align, slot_size=args.slot_size, running=args.running,
                                check_header=args.check_header)
        text = format_trailer(report, args.file)
    print(json.dumps(report, indent=2) if args.json else text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
