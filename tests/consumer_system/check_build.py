#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Checks of the out-of-tree System consumer (ADR-0005 T3, T4, T5), as plain functions that tests/build can call
on small inputs.

scripts/test-consumer-system.sh copies app/ outside the repository, builds it on native_sim, and runs
``check_build.py build COPY_ROOT BUILD_DIR REPO on|off``, ``check_build.py sources COPY_ROOT`` (the checks that
need no build) and ``check_build.py run EXECUTABLE``. The functions
answer one question each:

* include_violations: does a source of the consumer see an include directory of Crux that is not a public root?
  An allowed one is ``components/<c>/include`` or ``components/<c>/ports/zephyr/include``.
* header_violations: does a consumer source include a Crux header that is not <crux/system.h>, <crux/status.h>
  or <crux/logging.h>, or a private file of a component?
* link_violations: does the consumer's CMake link anything that is not ``crux::system``?
* wrap_violations: does the consumer's CMake wrap a Crux symbol at link time? (The consumer guard of
  cmake/CruxConsumerBoundary.cmake refuses that too, but it cannot run on Zephyr's ``app`` target, whose own
  requirements are Zephyr's.)
* conf_violations: does prj.conf or a board fragment name a Crux symbol beyond System and its simulated watchdog?
* config_violations and device_violations: with the simulated watchdog on, is the symbol in .config on
  native_sim with the process restart, and is the simulated device in the image? With it off, neither.
* run_violations: do the lines of one run show the three behaviours, in order?

A simulated watchdog is not hardware evidence: nothing here says anything about a board.
"""
import json
import os
from pathlib import Path
import re
import selectors
import shlex
import subprocess
import sys
import time

PUBLIC_ROOTS = re.compile(r"/components/[^/]+/(?:include|ports/zephyr/include)/?$")
UNDER_COMPONENTS = re.compile(r"/components/[^/]+(?:/|$)")
LINK_COMMAND = re.compile(r"target_link_libraries\s*\(\s*\w+\s+((?:PRIVATE|PUBLIC|INTERFACE)\s+)?([^)]*)\)", re.S)
ALLOWED_LINK_ITEMS = re.compile(r"^(?:PRIVATE|PUBLIC|INTERFACE)$|^crux::system$")
ALLOWED_CRUX_HEADERS = {"crux/system.h", "crux/status.h", "crux/logging.h"}
INCLUDE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.M)
PRIVATE_FILE = re.compile(r"(^|/)(components|ports|src)/|(^|/)system_(zephyr|binding|sim_watchdog)\b|crux_system_zephyr")
ALLOWED_CONF = {"CRUX_SYSTEM", "CRUX_SYSTEM_NATIVE_SIM_WATCHDOG", "CRUX_TIME"}
WRAP = re.compile(r"(?:^|[^A-Za-z0-9_])--?wra?p?[= ,]+(?:-Xlinker[ ,]+)?(?:-Wl,)?([^ ,;)\"]+)")

# The lines of one run, in order. Boot 1 is a power-on start; the simulated device restarts the process on the
# missed feed; boot 2 reads the cause SOFTWARE (never WATCHDOG on native_sim) and feeds, so the run ends.
RUN_LINES = [
    r"simwdt: boot 1 cause POR",
    r"simwdt: idle before start, simulated",
    r"simwdt: started, 2000 ms, active, simulated",
    r"simwdt: feed cycle ok, 6 feeds over 3000 ms, no restart",
    r"simwdt: missed feed, no more feeds",
    r"Crux simulated watchdog expired: no feed for 2000 ms; restarting the simulated process \(after 2[0-9]{3} ms\)",
    r"simwdt: boot 2 cause SOFTWARE, not WATCHDOG",
    r"simwdt: boot 2 fresh state, idle, simulated",
    r"simwdt: boot 2 feed cycle ok, no second restart, scenario complete",
]


def include_dirs(command):
    """Return the include directories of one compile command, in order."""
    words = shlex.split(command)
    found = []
    for index, word in enumerate(words):
        if word in ("-I", "-isystem", "-iquote") and index + 1 < len(words):
            found.append(words[index + 1])
        elif word.startswith("-I") and len(word) > 2:
            found.append(word[2:])
        elif word.startswith("-isystem") and len(word) > 8:
            found.append(word[8:])
    return found


def include_violations(compile_commands, consumer_root, repo):
    """Return (file, directory) for every consumer source that sees a refused Crux include directory.

    Only a file under consumer_root is a consumer source: the sources that Crux compiles into the image are not
    the product's. A directory under repo/components that is not a public include root is refused.
    """
    consumer_root = Path(consumer_root).resolve()
    repo = Path(repo).resolve()
    problems = []
    for entry in compile_commands:
        source = Path(entry["file"])
        if not source.is_absolute():
            source = Path(entry["directory"]) / source
        if consumer_root not in source.resolve().parents:
            continue
        for directory in include_dirs(entry.get("command") or " ".join(entry["arguments"])):
            path = Path(directory)
            if not path.is_absolute():
                path = Path(entry["directory"]) / path
            text = str(path.resolve()).replace("\\", "/")
            if repo in path.resolve().parents and UNDER_COMPONENTS.search(text) and not PUBLIC_ROOTS.search(text):
                problems.append((str(source), text))
    return problems


def header_violations(source_text):
    """Return every include of a consumer source that names Crux but is not one of the three public headers."""
    problems = []
    for name in INCLUDE.findall(source_text):
        if name.startswith("zephyr/") or name.startswith("zephyr_"):
            continue
        if name.startswith("crux/") or "crux" in name.lower():
            if name not in ALLOWED_CRUX_HEADERS:
                problems.append(name)
        elif PRIVATE_FILE.search(name):
            problems.append(name)
    return problems


def _code(cmake_text):
    return "\n".join(re.sub(r"#.*", "", line) for line in cmake_text.splitlines())


def link_violations(cmake_text):
    """Return every item of a target_link_libraries() that is not crux::system or a visibility keyword."""
    problems = []
    for match in LINK_COMMAND.finditer(_code(cmake_text)):
        problems += [item for item in match.group(2).split() if not ALLOWED_LINK_ITEMS.match(item)]
    return problems


def wrap_violations(cmake_text):
    """Return every Crux symbol (crux_*, __wrap_crux_*, __real_crux_*) that the consumer's CMake wraps."""
    return [symbol for symbol in WRAP.findall(_code(cmake_text))
            if re.match(r"(__wrap_|__real_)?crux_", symbol)]


def conf_violations(conf_text):
    """Return the Crux symbols of a Kconfig fragment that a System consumer may not name."""
    problems = []
    for line in conf_text.splitlines():
        match = re.match(r"\s*CONFIG_(CRUX_\w+)\s*=\s*(\S+)", line)
        if not match:
            continue
        name, value = match.groups()
        if name not in ALLOWED_CONF or (name == "CRUX_TIME" and value != "n"):
            problems.append(f"{name}={value}")
    return problems


def config_violations(config_text, simulated):
    """Check the generated .config. With the simulated watchdog on, it is native_sim with the process restart."""
    settings = dict(re.findall(r"^CONFIG_(\w+)=(\S+)$", config_text, re.M))
    wanted = {"CRUX_SYSTEM": "y", "BOARD_NATIVE_SIM": "y"}
    if simulated:
        wanted.update({"CRUX_SYSTEM_NATIVE_SIM_WATCHDOG": "y", "NATIVE_SIM_REBOOT": "y"})
    problems = [f"{name} is not {value}" for name, value in wanted.items() if settings.get(name) != value]
    if not simulated and settings.get("CRUX_SYSTEM_NATIVE_SIM_WATCHDOG") == "y":
        problems.append("CRUX_SYSTEM_NATIVE_SIM_WATCHDOG is y")
    return problems


def device_violations(nm_text, simulated):
    """The simulated device is in the image when the symbol is on, and only then."""
    present = "crux_system_sim_" in nm_text
    if simulated and not present:
        return ["the simulated device is not in the image"]
    if present and not simulated:
        return ["the simulated device is in the image with the symbol off"]
    return []


def run_violations(output):
    """Return the first expected line of RUN_LINES that is missing from the output in order, or a FAIL line."""
    problems = [line for line in output.splitlines() if "simwdt: FAIL" in line or "check_build: FAIL" in line]
    position = 0
    for pattern in RUN_LINES:
        match = re.compile(pattern).search(output, position)
        if match is None:
            problems.append(f"missing or out of order: {pattern}")
            break
        position = match.end()
    return problems


def apply_variant(root, variant):
    """Apply a one-line variant of variants.json to a copy of the consumer, and return the path it changed."""
    path = Path(root) / variant["file"]
    text = path.read_text()
    if text.count(variant["old"]) != 1:
        raise ValueError(f"{variant['name']}: {variant['old']!r} is not in {variant['file']} exactly once")
    path.write_text(text.replace(variant["old"], variant["new"], 1))
    return path


def check_sources(copy_root):
    """Checks that need no build: the consumer's own text."""
    problems = []
    app = Path(copy_root) / "app"
    for source in sorted(app.rglob("*.[ch]")):
        problems += [f"headers: {source.name} includes {name}" for name in header_violations(source.read_text())]
    cmake = (app / "CMakeLists.txt").read_text()
    problems += [f"link: {item}" for item in link_violations(cmake)]
    problems += [f"wrap: {symbol}" for symbol in wrap_violations(cmake)]
    for conf in [app / "prj.conf"] + sorted((app / "boards").glob("*.conf")):
        problems += [f"symbol in {conf.name}: {name}" for name in conf_violations(conf.read_text())]
    return problems


def check_build(copy_root, build_dir, repo, simulated):
    """Run every check on a finished or configure-only build. Return a list of problems, empty when clean."""
    problems = check_sources(copy_root)
    commands = json.loads((Path(build_dir) / "compile_commands.json").read_text())
    for source, directory in include_violations(commands, Path(copy_root) / "app", repo):
        problems.append(f"include: {source} sees {directory}")
    problems += [f"config: {text}" for text in
                 config_violations((Path(build_dir) / "zephyr" / ".config").read_text(), simulated)]
    elf = Path(build_dir) / "zephyr" / "zephyr.exe"
    if elf.exists():
        nm = subprocess.run(["nm", str(elf)], capture_output=True, text=True).stdout
        problems += [f"image: {text}" for text in device_violations(nm, simulated)]
    return problems


def run(executable, timeout=90):
    """Run the image until its last line, or the deadline. The second boot feeds for ever, so it is stopped.

    The deadline holds for a silent image too: the output is read with a selector, not line by line, so a
    process that prints nothing cannot block here. A timeout adds one ``check_build: FAIL`` line to the output.
    """
    last = re.compile(RUN_LINES[-1])
    process = subprocess.Popen([executable], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    text, deadline, timed_out = "", time.monotonic() + timeout, False
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            if not selector.select(min(remaining, 1.0)):
                continue
            data = os.read(process.stdout.fileno(), 4096)
            if not data:
                break
            text += data.decode(errors="replace")
            if last.search(text):
                break
    finally:
        selector.close()
        process.kill()
        process.wait()
        process.stdout.close()
    if timed_out:
        text += f"\ncheck_build: FAIL no last scenario line within {timeout} s\n"
    return text


def main(argv):
    if len(argv) == 6 and argv[1] == "build" and argv[5] in ("on", "off"):
        problems = check_build(argv[2], argv[3], argv[4], argv[5] == "on")
        for problem in problems:
            print(f"FAIL: {problem}")
        if not problems:
            print("ok: the consumer's includes, headers, links, symbols, .config and image are clean")
        return 1 if problems else 0
    if len(argv) == 3 and argv[1] == "sources":
        problems = check_sources(argv[2])
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1 if problems else 0
    if len(argv) == 3 and argv[1] == "run":
        output = run(argv[2])
        sys.stdout.write(output)
        problems = run_violations(output)
        for problem in problems:
            print(f"FAIL: {problem}")
        if not problems:
            print("ok: cause POR, start, feeds, missed feed, restart, cause SOFTWARE, fresh state, feeds again")
        return 1 if problems else 0
    print("usage: check_build.py build COPY_ROOT BUILD_DIR REPO on|off | sources COPY_ROOT | run EXECUTABLE", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
