#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare two builds of the boot composition (docs/boot-composition.md) for reproducibility.

A developer tool, not a Crux interface. It reads the build directories that
`scripts/test-boot-composition.sh` writes and changes nothing; it has no key, board or flash access.

"Reproducible" has the meaning of Stage 8 of the boot and update investigation
(docs/evidence/boot-update/stage8-reproducibility-and-signing.md):

* the unsigned binaries (MCUboot and the application `zephyr.bin`) are byte-identical;
* a signed image is identical in header, payload, protected TLVs, digest and key hash. Its ECDSA
  signature may differ, because the signature of the toolchain that Stage 8 measured is randomised
  (an Inference for any other toolchain). The length of a DER signature varies, so the size of a signed
  image may differ by a byte or two. With --strict-signature the signed images must be byte-identical;
* the padded, confirmed image is held to the same rule, and its trailer must be identical.

ELF files, maps and logs are not compared. The tool does NOT verify a signature: `imgtool verify`
stays authoritative (tests/target/check_boot_reproducibility.sh runs it). Two builds in one container
say nothing about another container, host, SDK installation or date.

Exit status: 0 reproducible, 1 not reproducible, 2 usage error (an unreadable directory, the same
directory twice).
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SIGNATURE_TLV = 0x22
SIGNATURE_NOTE = (
    "This compares two builds and is NOT a signature verification: `imgtool verify` stays authoritative."
)
SIGNATURE_DETAIL = (
    "only the ECDSA_SIG TLV differs, as expected when the signature is randomised (Stage 8, an Inference "
    "for another toolchain)"
)


def _load_inspector():
    spec = importlib.util.spec_from_file_location("inspect_boot_image_for_compare", HERE / "inspect_boot_image.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


inspector = _load_inspector()


def _row(artifact, status, detail):
    return {"artifact": artifact, "status": status, "detail": detail}


def _first_difference(a, b):
    for index, (left, right) in enumerate(zip(a, b)):
        if left != right:
            return index
    return min(len(a), len(b))


def _read(path):
    return path.read_bytes() if path.is_file() else None


def _missing(artifact, a, b, optional=False):
    """A row for a file that is absent from a build, or None when both exist."""
    if a is None and b is None:
        return _row(artifact, "absent" if optional else "missing",
                    "absent from both builds" if optional else "missing from both builds")
    if a is None or b is None:
        return _row(artifact, "missing", f"missing from build {'A' if a is None else 'B'}")
    return None


def compare_unsigned(artifact, a, b):
    absent = _missing(artifact, a, b)
    if absent:
        return absent
    if a == b:
        return _row(artifact, "identical", f"byte-identical, {len(a)} bytes")
    return _row(artifact, "differs",
                f"the bytes differ: sizes {len(a)} and {len(b)}, the first difference at offset "
                f"{_first_difference(a, b)}")


def _parts(data, report):
    """The parts of a parsed signed image that must reproduce, and the signature TLV."""
    header = report["header"]
    hdr_size, img_size = header["hdr_size"], header["img_size"]
    prot = report["protected_tlv"]
    unprot = report["unprotected_tlv"]
    payload_end = hdr_size + img_size
    protected = data[payload_end:payload_end + prot["total_length"]] if prot["present"] else b""
    tlvs = [(t["type"], t["value_hex"]) for t in unprot["tlvs"] if t["type"] != SIGNATURE_TLV]
    signature = [t["value_hex"] for t in unprot["tlvs"] if t["type"] == SIGNATURE_TLV]
    padding = report["padding"]
    trailer = None
    if padding["trailer_alignment"] is not None:
        reach = max(inspector.trailer_distances(padding["trailer_alignment"]).values())
        trailer = (padding["trailer_alignment"], data[len(data) - reach:])
    return {
        "header": data[:hdr_size],
        "payload": data[hdr_size:payload_end],
        "protected TLVs": protected,
        "TLVs other than the signature": tlvs,
        "trailer": trailer,
        "padded": padding["padded"],
    }, signature


def compare_signed(artifact, a, b, strict_signature=False, optional=False):
    absent = _missing(artifact, a, b, optional=optional)
    if absent:
        return absent
    if a == b:
        return _row(artifact, "identical", f"byte-identical, {len(a)} bytes")
    reports = {"A": inspector.inspect_image(a), "B": inspector.inspect_image(b)}
    for name, report in reports.items():
        if not report["ok"]:
            return _row(artifact, "differs",
                        f"the image of build {name} does not parse with a matching digest: {report['result']}")
    parts_a, signature_a = _parts(a, reports["A"])
    parts_b, signature_b = _parts(b, reports["B"])
    differing = [name for name in parts_a if parts_a[name] != parts_b[name]]
    padded = parts_a["padded"] or parts_b["padded"]
    if padded and len(a) != len(b):
        differing.append("padded length")
    if differing:
        return _row(artifact, "differs",
                    "differs in " + ", ".join(differing)
                    + f" (sizes {len(a)} and {len(b)})")
    detail = f"{SIGNATURE_DETAIL}; sizes {len(a)} and {len(b)}"
    if strict_signature:
        return _row(artifact, "equivalent", f"{detail}; the strict option requires byte-identical images")
    return _row(artifact, "equivalent", detail)


def compare_builds(dir_a, dir_b, image="zephyr", strict_signature=False):
    """Compare the artifacts of two builds of the composition. Returns the report."""
    dir_a, dir_b = Path(dir_a), Path(dir_b)
    rows = []

    def both(relative):
        return _read(dir_a / relative), _read(dir_b / relative)

    mcuboot = "mcuboot/zephyr/zephyr.bin"
    app_dir = f"{image}/zephyr"
    rows.append(compare_unsigned(mcuboot, *both(mcuboot)))
    rows.append(compare_unsigned(f"{app_dir}/zephyr.bin", *both(f"{app_dir}/zephyr.bin")))
    signed = f"{app_dir}/zephyr.signed.bin"
    rows.append(compare_signed(signed, *both(signed), strict_signature=strict_signature))
    confirmed = f"{app_dir}/zephyr.signed.confirmed.bin"
    rows.append(compare_signed(confirmed, *both(confirmed), strict_signature=strict_signature, optional=True))

    bad = {"differs", "missing"}
    ok = all(row["status"] not in bad for row in rows)
    if strict_signature and any(row["status"] == "equivalent" for row in rows):
        ok = False
    return {
        "kind": "build comparison",
        "ok": ok,
        "result": "reproducible" if ok else "not reproducible",
        "build_a": str(dir_a),
        "build_b": str(dir_b),
        "image": image,
        "strict_signature": strict_signature,
        "signature_verified": False,
        "signature_note": SIGNATURE_NOTE,
        "rows": rows,
    }


def format_report(report):
    lines = [f"Build A: {report['build_a']}", f"Build B: {report['build_b']}"]
    for row in report["rows"]:
        lines.append(f"  {row['artifact']}")
        lines.append(f"    {row['status']:<10} {row['detail']}")
    lines.append(f"Result: {report['result']}")
    lines.append("Unsigned binaries must be byte-identical; a signed image may differ in its ECDSA signature only "
                 "(unless --strict-signature). " + report["signature_note"])
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="compare_boot_builds.py",
        description=(
            "Compare two builds of the boot composition for reproducibility (unsigned binaries "
            "byte-identical, signed images identical but for the randomised ECDSA signature). Reads files "
            "only; not a signature verification."
        ),
        epilog="Exit status: 0 reproducible, 1 not reproducible, 2 usage error.",
    )
    parser.add_argument("build_a", help="the first build directory of the composition")
    parser.add_argument("build_b", help="the second build directory of the composition")
    parser.add_argument("--image", default="zephyr", help="base name of the application directory (default zephyr)")
    parser.add_argument("--strict-signature", action="store_true",
                        help="also require byte-identical signed images (a deterministic signature)")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    return parser


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as stop:
        return stop.code if isinstance(stop.code, int) else 2
    a, b = Path(args.build_a), Path(args.build_b)
    for path in (a, b):
        if not path.is_dir():
            print(f"error: {path} is not a build directory", file=sys.stderr)
            return 2
    if a.resolve() == b.resolve():
        print("error: the two arguments are the same directory, which is not a comparison of two builds",
              file=sys.stderr)
        return 2
    report = compare_builds(a, b, image=args.image, strict_signature=args.strict_signature)
    print(json.dumps(report, indent=2) if args.json else format_report(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
