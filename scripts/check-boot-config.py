#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the resolved build configuration of the boot composition: RAM load with revert, no build number.

It reads the resolved `.config` of the two images that scripts/test-boot-composition.sh builds, the MCUboot
image at `$build/mcuboot/zephyr/.config` and the application at `$build/<image>/zephyr/.config`, and fails
unless

* the bootloader is built for RAM load with revert (CONFIG_BOOT_RAM_LOAD=y and CONFIG_BOOT_RAM_LOAD_REVERT=y),
* the application is built for RAM load with revert (CONFIG_MCUBOOT_BOOTLOADER_MODE_RAM_LOAD_WITH_REVERT=y), and
* the build-number comparison (CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER, which defines
  MCUBOOT_VERSION_CMP_USE_BUILD_NUMBER) is not enabled in either image.

The application cannot catch a bootloader built without revert at run time, because its BLINFO_MODE reports
RAM load for that bootloader too, and a bootloader that compares the build number can disagree with an
application that does not about which image is newer (docs/plans/image-state-contract-proposal.md, rows I5 and
Q9). The option names and the sources they were read from are listed in tests/build/test_check_boot_config.py.

This reads files. It builds nothing, programs nothing, boots nothing and writes nothing. It shows how the
images were configured, not how the bootloader behaves on a board.

scripts/test-boot-composition.sh calls it on its own build, so the `runtime` shard of CI runs it. That edit of a
protected file is pending the project owner's approval; the proposal is in the description of the pull request that
added this file. It has not yet run on a real build.

Usage: scripts/check-boot-config.py [build-dir] [--image NAME]
  build-dir  the build directory of the composition ($repo/build/zephyr/boot-composition by default)
  --image    the application's directory in the sysbuild tree (zephyr, the basename of samples/controller/zephyr)
Exit status: 0 every check passed, 1 a check failed, 2 a configuration cannot be used (missing build directory
or file, or a file without a single CONFIG_ option).
"""
import argparse
import re
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_BUILD = REPOSITORY / "build/zephyr/boot-composition"
DEFAULT_IMAGE = "zephyr"

# Options that must be y in the bootloader image (Zephyr v4.4.2 BOOTLOADER_image_default.cmake sets them for
# SB_CONFIG_MCUBOOT_MODE_RAM_LOAD_WITH_REVERT; MCUboot boot/zephyr/Kconfig defines them).
BOOTLOADER_REQUIRED = (
    ("CONFIG_BOOT_RAM_LOAD", "y"),
    ("CONFIG_BOOT_RAM_LOAD_REVERT", "y"),
)
# Options that must be y in the application image (MAIN_image_default.cmake, modules/Kconfig.mcuboot). The
# option sits in a choice of modes, so no other mode can be set with it.
APPLICATION_REQUIRED = (
    ("CONFIG_MCUBOOT_BOOTLOADER_MODE_RAM_LOAD_WITH_REVERT", "y"),
)
# Options that must be off (absent or n) in both images. MCUboot's boot/zephyr/Kconfig defines this one only
# in the MCUboot image, so the application cannot hold it, and the check on it is a guard.
FORBIDDEN = (
    "CONFIG_BOOT_VERSION_CMP_USE_BUILD_NUMBER",
)

ASSIGNMENT = re.compile(r"^(CONFIG_[A-Za-z0-9_]+)=(.*)$")
NOT_SET = re.compile(r"^# (CONFIG_[A-Za-z0-9_]+) is not set$")


def parse_config(text):
    """Each option of a Kconfig .config with its value as written. `# CONFIG_X is not set` reads as n.
    The last line for an option wins. Only a whole option name matches, never a prefix of a longer one."""
    config = {}
    for line in text.splitlines():
        line = line.rstrip()
        match = ASSIGNMENT.match(line)
        if match:
            config[match.group(1)] = match.group(2)
            continue
        match = NOT_SET.match(line)
        if match:
            config[match.group(1)] = "n"
    return config


def required_errors(config, required):
    errors = []
    for name, wanted in required:
        value = config.get(name)
        if value is None:
            errors.append(f"{name} is not set, and the composition needs {name}={wanted}")
        elif value != wanted:
            errors.append(f"{name}={value}, and the composition needs {name}={wanted}")
    return errors


def forbidden_errors(config):
    errors = []
    for name in FORBIDDEN:
        value = config.get(name, "n")
        if value != "n":
            errors.append(f"{name}={value}, and the composition must not enable it (image-state row I5: "
                          "the version basis is major, minor and revision)")
    return errors


def bootloader_errors(config):
    return required_errors(config, BOOTLOADER_REQUIRED) + forbidden_errors(config)


def application_errors(config):
    return required_errors(config, APPLICATION_REQUIRED) + forbidden_errors(config)


def read_config(path):
    """The parsed options of a file, or None with a message when it cannot be used."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        return None, f"cannot read {path}: {error.strerror or error}"
    config = parse_config(text)
    if not config:
        return None, f"{path} holds no CONFIG_ option, so it is not a resolved configuration"
    return config, None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("build", nargs="?", type=Path, default=DEFAULT_BUILD, help="boot composition build directory")
    parser.add_argument("--image", default=DEFAULT_IMAGE, help="application directory in the sysbuild tree")
    arguments = parser.parse_args(argv)
    build = arguments.build

    def unusable(message):
        print(f"boot config check: {message}\nRun scripts/test-boot-composition.sh first, then run this check on "
              "its build directory.", file=sys.stderr)
        return 2

    if not build.is_dir():
        return unusable(f"the build directory {build} does not exist")
    images = (
        ("bootloader", build / "mcuboot/zephyr/.config", bootloader_errors),
        ("application", build / arguments.image / "zephyr/.config", application_errors),
    )
    failures = []
    for label, path, check in images:
        config, problem = read_config(path)
        if problem:
            return unusable(f"the {label} configuration: {problem}")
        failures.extend(f"{path}: {error}" for error in check(config))
    if failures:
        for failure in failures:
            print(f"boot config check failed: {failure}", file=sys.stderr)
        return 1
    print("Boot config: MCUboot and the application are configured for RAM load with revert, and the "
          "build-number comparison is off (configuration read only, build only, not booted).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
