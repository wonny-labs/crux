#!/usr/bin/env python3
"""Find NOR references reachable from the FlexSPI NOR write and erase path of a built MCUboot ELF (#165).

Static, host-only, and read-only: it reads `nm` and `objdump -d` text of the image and the bytes of the ELF's
loadable segments. It runs no board and writes nothing. See issue #165 for what each check is for.

  S1 placement      the FlexSPI configuration object must not run in the NOR window; each function reached
                    from the roots must run in ITCM (its run address, not its load address).
  S2 reachability   from the roots, follow direct calls; report a call into NOR, a literal-pool value in the
                    NOR window, and an indirect branch whose target the text does not give.
  S3 device record  for every device record whose `config` pointer is a memc_flexspi_config_* object, read the
                    pointer from the ELF and report one in NOR. This is the step that found the failure by hand.
  S4 source pin     compare the SHA-256 of the three upstream files with the ones of scripts/prepare-flash-poc.py.
  S5 report only    print where the vectors and the fault and NMI handlers run.

A pass shows the absence of the edges these checks look for. It is **not closure** of the #22 matrix: the
check does not see run-time state, stack contents, what the boot ROM left active, or an indirect target. Report
mode (the default) exits 0 on findings so that a log shows them (a tool that cannot run still fails). --strict
exits 1 on any finding. A disassembly that parses to nothing, a reached function with no parsed instruction and
a pc-relative load whose value cannot be resolved are findings, not silent passes.
"""
import argparse
import hashlib
import re
import struct
import subprocess
import sys
from collections import deque
from pathlib import Path

NOR_WINDOW = (0x60000000, 0x60800000)
ITCM_END = 0x00080000
REGIONS = (
    ("ITCM", 0x00000000, ITCM_END),
    ("DTCM", 0x20000000, 0x20080000),
    ("OCRAM", 0x20200000, 0x20300000),
    ("PERIPHERAL", 0x40000000, 0x60000000),
    ("NOR", NOR_WINDOW[0], NOR_WINDOW[1]),
    ("SDRAM", 0x80000000, 0xA0000000),
)
ROOTS = ("flash_flexspi_nor_write", "flash_flexspi_nor_erase")
# Relative to the Zephyr checkout, or to the hal_nxp checkout for the path under mcux/. The digests are the
# ones of scripts/prepare-flash-poc.py (NOR_HASH, MEMC_HASH, HAL_HASH), at Zephyr v4.5.0 and its hal_nxp pin.
# All three files changed from v4.4.2; the physical results of issue #165 were recorded on v4.4.x.
PINNED_FILES = {
    "drivers/flash/flash_mcux_flexspi_nor.c": "9331e05799b447716203cb7ce838f9e6c413f73e3fd3d8ad95f85ae17f2d3cf0",
    "drivers/memc/memc_mcux_flexspi.c": "432c578152d8d921a334ca3c4ab927075a4251c8e6a97b6bcd522c3f0e8ca50d",
    "mcux/mcux-sdk-ng/drivers/flexspi/fsl_flexspi.c": "96af77b8f02eacbf1eee2d8b8fe98b592cbfc6dc0d5d89d5c3c30745ee96d8f9",
}
DEVICE_PREFIX = "__device_dts_ord_"
CONFIG_PREFIX = "memc_flexspi_config_"
CONFIG_OFFSET = 4  # struct device: name, config, ... on a 32-bit target

HEADER = re.compile(r"^([0-9a-f]+) <([^>]+)>:\s*$")
LINE = re.compile(r"^\s*([0-9a-f]+):(?:\t|\s+)(?:[0-9a-f ]+\t)?(\S+)\s*(.*)$")
WORD = re.compile(r"^\s*([0-9a-f]+):(?:\t|\s+)[0-9a-f ]+\s+\.word\s+(0x[0-9a-f]+)")
TARGET = re.compile(r"\s(?:0x)?([0-9a-f]+) <([^>+]+)(?:\+0x[0-9a-f]+)?>")
LITERAL = re.compile(r"[@;] \(?(?:0x)?([0-9a-f]+) ")
BRANCH = re.compile(r"^(?:b|bl|bx|blx|cb[n]?z)(?:\.[nw]|eq|ne|cs|hs|cc|lo|mi|pl|vs|vc|hi|ls|ge|lt|gt|le|al)*(?:\.[nw])?$")


class Function:
    def __init__(self, name, address):
        self.name = name
        self.address = address
        self.calls = set()
        self.literals = []
        self.indirect = 0
        self.instructions = 0
        self.unresolved = []  # pc-relative loads whose pool word the text does not give


def region(address):
    for name, low, high in REGIONS:
        if low <= address < high:
            return name
    return "UNKNOWN"


def parse_nm(text):
    symbols = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and re.fullmatch(r"[0-9a-fA-F]+", parts[0]):
            symbols.setdefault(parts[2], int(parts[0], 16))
    return symbols


def parse_objdump(text):
    functions = {}
    words = {}
    current = None
    pending = []  # (function, literal address) resolved once the pool word has been seen
    for line in text.splitlines():
        header = HEADER.match(line)
        if header:
            current = Function(header.group(2), int(header.group(1), 16))
            functions[current.name] = current
            continue
        if current is None:
            continue
        word = WORD.match(line)
        if word:
            words[int(word.group(1), 16)] = int(word.group(2), 16)
            continue
        match = LINE.match(line)
        if not match:
            continue
        mnemonic, operands = match.group(2), match.group(3)
        current.instructions += 1
        if mnemonic.startswith("ldr") and "[pc" in operands:
            literal = LITERAL.search(operands)
            if literal:
                pending.append((current, int(literal.group(1), 16)))
            else:
                current.unresolved.append("%s: %s" % (match.group(1), operands.strip()))
            continue
        base = mnemonic.split(".")[0]
        if base in ("blx", "bx") and re.match(r"^(r\d+|ip|sl|fp)\b", operands):
            current.indirect += 1
            continue
        if base == "bx" and operands.startswith("lr"):
            continue
        if BRANCH.match(mnemonic):
            target = TARGET.search(" " + operands)
            if target and target.group(2) != current.name:
                current.calls.add(target.group(2))
    for function, address in pending:
        if address in words:
            function.literals.append(words[address])
        else:
            function.unresolved.append("pool word at 0x%x" % address)
    return functions


def symbol_at(symbols, value):
    for name, address in symbols.items():
        if address == value:
            return name
    return None


def check_placement(symbols):
    errors = []
    for name, address in sorted(symbols.items()):
        if name.startswith(CONFIG_PREFIX) and region(address) == "NOR":
            errors.append("%s runs in NOR (0x%08x): the busy poll reads its register base from it" % (name, address))
    return errors


def check_closure(symbols, functions, roots, allow, read=None):
    """`read(address)` gives the word of the ELF at an address, for a pool word the text does not show."""
    errors = []
    if functions and not any(f.instructions for f in functions.values()):
        errors.append(
            "the disassembly has %d function header(s) and no parsed instruction: its format is not the one "
            "this check reads, so nothing was checked" % len(functions)
        )
    seen = set()
    queue = deque()
    for root in roots:
        if root not in functions:
            errors.append("root %s is not in the disassembly: the check cannot say anything about it" % root)
        else:
            queue.append(root)
    while queue:
        name = queue.popleft()
        if name in seen:
            continue
        seen.add(name)
        function = functions[name]
        address = symbols.get(name, function.address)
        if region(address) != "ITCM":
            errors.append(
                "%s is reached from the write path and runs in %s (0x%08x), not in ITCM"
                % (name, region(address), address)
            )
        if not function.instructions:
            errors.append("%s is reached from the write path and has no parsed instruction" % name)
        values = list(function.literals)
        for note in function.unresolved:
            match = re.match(r"pool word at 0x([0-9a-f]+)", note)
            word = read(int(match.group(1), 16)) if (match and read) else None
            if word is None:
                errors.append("%s has a pc-relative load with no resolvable value (%s)" % (name, note))
            else:
                values.append(word)
        if function.indirect:
            errors.append(
                "%s has %d indirect branch(es) with no target in the text: not followed" % (name, function.indirect)
            )
        for value in values:
            if region(value) == "NOR":
                label = symbol_at(symbols, value)
                if label in allow:
                    continue
                errors.append(
                    "%s loads 0x%08x from its literal pool, which is in NOR%s"
                    % (name, value, " (%s)" % label if label else "")
                )
        for callee in sorted(function.calls):
            if callee in allow:
                continue
            if callee in functions:
                queue.append(callee)
            elif callee in symbols and region(symbols[callee]) == "NOR":
                errors.append("%s calls %s, which is in NOR (0x%08x)" % (name, callee, symbols[callee]))
            elif callee in symbols and region(symbols[callee]) != "ITCM":
                errors.append("%s calls %s in %s" % (name, callee, region(symbols[callee])))
    return errors


def load_segments(path):
    data = Path(path).read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
        raise ValueError("expected a 32-bit little-endian ELF")
    phoff, = struct.unpack_from("<I", data, 28)
    phentsize, phnum = struct.unpack_from("<HH", data, 42)
    segments = []
    for index in range(phnum):
        ptype, offset, vaddr, paddr, filesz, memsz, flags, align = struct.unpack_from(
            "<IIIIIIII", data, phoff + index * phentsize
        )
        if ptype == 1:
            segments.append((vaddr, paddr, offset, filesz))
    return data, segments


def read_word(data, segments, address):
    for vaddr, paddr, offset, filesz in segments:
        for base in (vaddr, paddr):
            if base <= address and address + 4 <= base + filesz:
                return struct.unpack_from("<I", data, offset + address - base)[0]
    return None


def check_device_records(symbols, elf):
    errors = []
    data, segments = load_segments(elf)
    configs = {address: name for name, address in symbols.items() if name.startswith(CONFIG_PREFIX)}
    found = False
    for name, address in sorted(symbols.items()):
        if not name.startswith(DEVICE_PREFIX):
            continue
        pointer = read_word(data, segments, address + CONFIG_OFFSET)
        if pointer in configs:
            found = True
            if region(pointer) == "NOR":
                errors.append(
                    "%s has its config pointer 0x%08x (%s) in NOR: a copy of this record keeps the pointer"
                    % (name, pointer, configs[pointer])
                )
    if not found:
        errors.append("no device record whose config pointer is a %s* object was found in the ELF" % CONFIG_PREFIX)
    return errors


def check_pins(zephyr_base, hal_nxp, with_notes=False):
    errors, notes = [], []
    for relative, digest in PINNED_FILES.items():
        root = hal_nxp if relative.startswith("mcux/") else zephyr_base
        if not root:
            notes.append("%s: tree not given, not checked" % relative)
            continue
        path = Path(root) / relative
        if not path.is_file():
            errors.append("%s is missing under %s" % (relative, root))
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            errors.append("%s differs from the pinned file: the analysis may no longer describe it" % relative)
    return (errors, notes) if with_notes else errors


def report_vectors(symbols):
    lines = []
    for name in ("_vector_table", "z_arm_nmi", "z_arm_fault"):
        if name in symbols:
            lines.append("S5 %s runs in %s (0x%08x)" % (name, region(symbols[name]), symbols[name]))
        else:
            lines.append("S5 %s not found in the symbols" % name)
    return lines


def tool(command, *arguments):
    return subprocess.run([command, *arguments], check=True, capture_output=True, text=True).stdout


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--elf", required=True, help="the MCUboot zephyr.elf")
    parser.add_argument("--nm", default="nm", help="nm of the toolchain (default: nm)")
    parser.add_argument("--objdump", default="objdump", help="objdump of the toolchain (default: objdump)")
    parser.add_argument("--zephyr-base", help="Zephyr checkout, for the source pin check")
    parser.add_argument("--hal-nxp", help="hal_nxp checkout, for the source pin check")
    parser.add_argument("--allow", action="append", default=[], help="a symbol whose NOR reference is reviewed; allowing a callee also skips everything it calls")
    parser.add_argument("--strict", action="store_true", help="exit 1 on any finding (default: report only)")
    args = parser.parse_args(argv)

    symbols = parse_nm(tool(args.nm, "--defined-only", args.elf))
    functions = parse_objdump(tool(args.objdump, "-d", args.elf))
    data, segments = load_segments(args.elf)
    findings = []
    findings += ["S1 " + e for e in check_placement(symbols)]
    findings += ["S2 " + e for e in check_closure(symbols, functions, ROOTS, set(args.allow), lambda a: read_word(data, segments, a))]
    findings += ["S3 " + e for e in check_device_records(symbols, args.elf)]
    pin_errors, notes = check_pins(args.zephyr_base, args.hal_nxp, with_notes=True)
    findings += ["S4 " + e for e in pin_errors]
    for line in report_vectors(symbols):
        print(line)
    for note in notes:
        print("S4 " + note)
    for finding in findings:
        print("finding: " + finding)
    print("%d finding(s). A pass shows the absence of these edges only, not closure of the #22 matrix." % len(findings))
    return 1 if (findings and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
