#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Checks of the out-of-tree consumer (ADR-0004 T3), as plain functions that tests/build can call on small inputs.

scripts/test-consumer-composition.sh builds a copy of this directory outside the repository and then runs
``check_build.py build ROOT_OF_COPY BUILD_DIR REPO``. The functions answer one question each:

* include_violations: does a source of the consumer see an include directory that the rules of ADR-0004
  section 5 refuse? An allowed one is ``components/<c>/include`` or ``components/<c>/ports/zephyr/include``.
* link_violations: does the consumer's CMake link anything that is not a ``crux::`` target?
* Frozen headers and composition interfaces in the domain are checked by templates/product/check_domain_includes.py.
* symbol_violations: does the image hold a wolfSSL, wolfSSH or wolfPSA symbol, or set a CONFIG_WOLF* option?
"""
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

PUBLIC_ROOTS = re.compile(r"/components/[^/]+/(?:include|ports/zephyr/include)/?$")
UNDER_COMPONENTS = re.compile(r"/components/[^/]+(?:/|$)")
LINK_COMMAND = re.compile(r"target_link_libraries\s*\(\s*\w+\s+((?:PRIVATE|PUBLIC|INTERFACE)\s+)?([^)]*)\)", re.S)
ALLOWED_LINK_ITEMS = re.compile(r"^(?:PRIVATE|PUBLIC|INTERFACE)$|^crux::\w+$")
SERVICE_SYMBOLS = {
    "CRUX_ACCESS", "CRUX_CONFIG_SERVICE", "CRUX_MGMT_STATUS", "CRUX_NETWORK_SETTINGS",
    "CRUX_NETWORK_SETTINGS_NO_APPLY", "CRUX_TLS_CERTIFICATE", "CRUX_FILE_SERVICE", "CRUX_REBOOT",
    "CRUX_WEB", "CRUX_WEB_SESSION", "CRUX_WEB_MANAGEMENT",
}
# Capabilities that a service needs under it and that the product states itself, and settings of the web adapter.
CAPABILITY_SYMBOLS = {"CRUX_FILE_FATFS_SIMULATOR", "CRUX_LOGGING", "CRUX_NETIF", "CRUX_SYSTEM"}
SETTING_PREFIXES = ("CRUX_WEB_PORT", "CRUX_WEB_REQUEST_", "CRUX_WEB_RESPONSE_", "CRUX_WEB_SEND_",
                    "CRUX_WEB_BODY_", "CRUX_WEB_BACKLOG", "CRUX_WEB_BIND_", "CRUX_WEB_TLS_")
# Symbols whose names a consumer must not state: the interfaces frozen for new product code, and what a service
# symbol selects for it (ADR-0004 C6).
NEVER_NAMED = re.compile(r"^CRUX_(THREAD|SYNC|TIME|QUEUE|SERIAL)(_|$)")


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

    Only a file under consumer_root is a consumer source: the sources that Crux compiles into the image are
    not the product's. A directory under repo/components that is not a public include root is refused, so a
    new private directory is refused until someone names it public.
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


def link_violations(cmake_text):
    """Return every item of a target_link_libraries() that is not a crux:: target or a visibility keyword."""
    text = "\n".join(re.sub(r"#.*", "", line) for line in cmake_text.splitlines())
    problems = []
    for match in LINK_COMMAND.finditer(text):
        for item in match.group(2).split():
            if not ALLOWED_LINK_ITEMS.match(item):
                problems.append(item)
    return problems


def path_violations(cmake_text):
    """Return every mention of a Crux component directory in the consumer's CMake."""
    text = "\n".join(re.sub(r"#.*", "", line) for line in cmake_text.splitlines())
    return re.findall(r"components/[\w-]+/(?:src|ports|adapter|management|session|host|zephyr|tests)\b", text)


def conf_violations(conf_text):
    """Return the Crux symbols of a prj.conf that a consumer may not name, by their config names."""
    problems = []
    for line in conf_text.splitlines():
        match = re.match(r"\s*CONFIG_(CRUX_\w+)\s*=", line)
        if not match:
            continue
        name = match.group(1)
        if NEVER_NAMED.match(name):
            problems.append(name)
        elif name not in SERVICE_SYMBOLS | CAPABILITY_SYMBOLS and not name.startswith(SETTING_PREFIXES):
            problems.append(name)
    return problems


def symbol_violations(nm_text, config_text):
    """Return wolfSSL, wolfSSH or wolfPSA symbols of an image, and CONFIG_WOLF* options that are set."""
    problems = [line for line in nm_text.splitlines() if re.search(r"wolf", line, re.I)]
    problems += [line for line in config_text.splitlines() if re.match(r"CONFIG_(WOLF\w*|CRUX_SSH)=", line)]
    return problems


def apply_variant(root, variant):
    """Apply a one-line variant of variants.json to a copy of the consumer, and return the path it changed."""
    path = Path(root) / variant["file"]
    text = path.read_text()
    if text.count(variant["old"]) != 1:
        raise ValueError(f"{variant['name']}: {variant['old']!r} is not in {variant['file']} exactly once")
    path.write_text(text.replace(variant["old"], variant["new"], 1))
    return path


def check_build(copy_root, build_dir, repo):
    """Run every check on a finished build. Return a list of problems, empty when it is clean."""
    problems = []
    commands = json.loads((Path(build_dir) / "compile_commands.json").read_text())
    for source, directory in include_violations(commands, Path(copy_root) / "app", repo):
        problems.append(f"include: {source} sees {directory}")
    cmake = (Path(copy_root) / "app" / "CMakeLists.txt").read_text()
    problems += [f"link: {item}" for item in link_violations(cmake)]
    problems += [f"cmake path: {item}" for item in path_violations(cmake)]
    conf = (Path(copy_root) / "app" / "prj.conf").read_text()
    problems += [f"symbol in prj.conf: {name}" for name in conf_violations(conf)]
    checker = Path(repo) / "templates/product/check_domain_includes.py"
    result = subprocess.run([sys.executable, str(checker), "--product", str(copy_root),
                             "--domain", "domain"], capture_output=True, text=True)
    if result.returncode != 0:
        problems.append("headers: " + (result.stdout + result.stderr).strip())
    # A configure-only build, as the variants of T4 use, has a .config and no ELF.
    elf = Path(build_dir) / "zephyr" / "zephyr.elf"
    nm = subprocess.run(["nm", str(elf)], capture_output=True, text=True).stdout if elf.exists() else ""
    config = (Path(build_dir) / "zephyr" / ".config").read_text()
    problems += [f"licence: {line}" for line in symbol_violations(nm, config)]
    return problems


def main(argv):
    if len(argv) != 5 or argv[1] != "build":
        print("usage: check_build.py build COPY_ROOT BUILD_DIR REPO", file=sys.stderr)
        return 2
    problems = check_build(*argv[2:])
    for problem in problems:
        print(f"FAIL: {problem}")
    if not problems:
        print("ok: the consumer's includes, links, symbols, headers and licence boundary are clean")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
