#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != Linux ]]; then
    printf 'Zephyr tests are configured for Linux only; reopen this repository in the Dev Container.\n' >&2
    exit 2
fi

repo="$(git rev-parse --show-toplevel)"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
if [[ ! -f "$workspace/.west/config" || ! -d "$workspace/zephyr" ]]; then
    printf 'Run scripts/bootstrap-zephyr.sh before Zephyr tests.\n' >&2
    exit 2
fi
export ZEPHYR_BASE="$workspace/zephyr"
# shellcheck source=lib/board.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib/board.sh"
crux_board_require "$(crux_board_target 'mimxrt1060_evk@B/mimxrt1062/qspi')" 'mimxrt1060_evk@B/mimxrt1062/qspi'
board='mimxrt1060_evk@B/mimxrt1062/qspi'
output="${CRUX_FILE_RT1060_OUTPUT:-$repo/build/zephyr/twister-file-rt1060}"

# Compile only: the File sources and the SD card FatFs composition become an unlinked object.
# Nothing is linked into a runnable File provider and no board is programmed or reset.
(cd "$workspace" && west twister -p "$board" -T "$repo/tests/zephyr/file_fatfs_compile" \
    --build-only -O "$output" --inline-logs)

# A filtered testcase exits successfully with nothing built; require the configuration to build.
python3 - "$output/twister.json" "$board" <<'PY'
import json
import sys

suites = json.load(open(sys.argv[1]))['testsuites']
# A build-only testcase that built reports "not run"; filtered or failed ones report otherwise.
if (len(suites) != 1 or suites[0]['platform'] != sys.argv[2] or
        suites[0].get('status') != 'not run' or suites[0].get('runnable')):
    raise RuntimeError(f'RT1060 File compile check did not build on {sys.argv[2]}: '
                       f"{[(s['platform'], s.get('status')) for s in suites]}")
print(f"RT1060 File compile check built on {sys.argv[2]}: {suites[0]['name']}")
PY

# Link only: the microSD composition image links the File provider and FatFs for the same board.
# Both scenarios must build (the mount sequence compiled out, and compiled in). No board is
# programmed, and the mount-at-boot scenario must not be flashed without physical approval.
link_output="${CRUX_FILE_RT1060_LINK_OUTPUT:-$repo/build/zephyr/twister-file-rt1060-link}"
(cd "$workspace" && west twister -p "$board" -T "$repo/samples/boards/nxp/mimxrt1060_evk/sd_card_file" \
    --build-only -O "$link_output" --inline-logs)

python3 - "$link_output/twister.json" "$board" <<'PY'
import json
import sys

suites = json.load(open(sys.argv[1]))['testsuites']
names = sorted(s['name'] for s in suites)
expected = ['crux.sample.boards.mimxrt1060_evk.sd_card_file', 'crux.sample.boards.mimxrt1060_evk.sd_card_file.start']
if (names != expected or any(s['platform'] != sys.argv[2] or s.get('status') != 'not run' or
                             s.get('runnable') for s in suites)):
    raise RuntimeError(f'RT1060 File link check did not build both scenarios: '
                       f"{[(s['name'], s['platform'], s.get('status')) for s in suites]}")
# The mount-at-boot scenario must really enable it, and the base scenario must not.
from pathlib import Path
root = Path(sys.argv[1]).parent
for name, wanted in [('crux.sample.boards.mimxrt1060_evk.sd_card_file', False), ('crux.sample.boards.mimxrt1060_evk.sd_card_file.start', True)]:
    configs = [p for p in root.rglob('.config') if p.parent.parent.name == name]
    if len(configs) != 1:
        raise RuntimeError(f'expected one build configuration for {name}, found {len(configs)}')
    enabled = 'CONFIG_SAMPLE_SD_START=y' in configs[0].read_text().splitlines()
    if enabled != wanted:
        raise RuntimeError(f'{name}: CONFIG_SAMPLE_SD_START enabled={enabled}, expected {wanted}')
print(f'RT1060 File link check built {len(suites)} scenarios on {sys.argv[2]}')
PY

# Link only: the interrupted-write test image. It writes to a card until power is cut, so the scenario
# that enables it must never be flashed without physical approval.
interrupt_output="${CRUX_FILE_RT1060_INTERRUPT_OUTPUT:-$repo/build/zephyr/twister-file-rt1060-interrupt}"
(cd "$workspace" && west twister -p "$board" -T "$repo/tests/board_images/sd_card_power_cut_append" \
    --build-only -O "$interrupt_output" --inline-logs)

python3 - "$interrupt_output/twister.json" "$board" <<'PY'
import json
import sys
from pathlib import Path

suites = json.load(open(sys.argv[1]))['testsuites']
names = sorted(s['name'] for s in suites)
expected = ['crux.file.sd_card_power_cut_append', 'crux.file.sd_card_power_cut_append.test']
if (names != expected or any(s['platform'] != sys.argv[2] or s.get('status') != 'not run' or
                             s.get('runnable') for s in suites)):
    raise RuntimeError(f'RT1060 interrupted-write link check did not build both scenarios: '
                       f"{[(s['name'], s['platform'], s.get('status')) for s in suites]}")
root = Path(sys.argv[1]).parent
for name, wanted in [('crux.file.sd_card_power_cut_append', False),
                     ('crux.file.sd_card_power_cut_append.test', True)]:
    configs = [p for p in root.rglob('.config') if p.parent.parent.name == name]
    if len(configs) != 1:
        raise RuntimeError(f'expected one build configuration for {name}, found {len(configs)}')
    enabled = 'CONFIG_SAMPLE_SD_INTERRUPT_TEST=y' in configs[0].read_text().splitlines()
    if enabled != wanted:
        raise RuntimeError(f'{name}: CONFIG_SAMPLE_SD_INTERRUPT_TEST enabled={enabled}, expected {wanted}')
print(f'RT1060 interrupted-write link check built {len(suites)} scenarios on {sys.argv[2]}')
PY

# Link only: the replace-pattern power-cut image. It writes to a card until power is cut, so the scenario
# that enables it must never be flashed without physical approval.
replace_output="${CRUX_FILE_RT1060_REPLACE_OUTPUT:-$repo/build/zephyr/twister-file-rt1060-replace}"
(cd "$workspace" && west twister -p "$board" -T "$repo/tests/board_images/sd_card_power_cut_replace" \
    --build-only -O "$replace_output" --inline-logs)

python3 - "$replace_output/twister.json" "$board" <<'PY'
import json
import sys
from pathlib import Path

suites = json.load(open(sys.argv[1]))['testsuites']
names = sorted(s['name'] for s in suites)
expected = ['crux.file.sd_card_power_cut_replace', 'crux.file.sd_card_power_cut_replace.test']
if (names != expected or any(s['platform'] != sys.argv[2] or s.get('status') != 'not run' or
                             s.get('runnable') for s in suites)):
    raise RuntimeError(f'RT1060 replace-pattern link check did not build both scenarios: '
                       f"{[(s['name'], s['platform'], s.get('status')) for s in suites]}")
root = Path(sys.argv[1]).parent
for name, wanted in [('crux.file.sd_card_power_cut_replace', False),
                     ('crux.file.sd_card_power_cut_replace.test', True)]:
    configs = [p for p in root.rglob('.config') if p.parent.parent.name == name]
    if len(configs) != 1:
        raise RuntimeError(f'expected one build configuration for {name}, found {len(configs)}')
    enabled = 'CONFIG_SAMPLE_SD_REPLACE_TEST=y' in configs[0].read_text().splitlines()
    if enabled != wanted:
        raise RuntimeError(f'{name}: CONFIG_SAMPLE_SD_REPLACE_TEST enabled={enabled}, expected {wanted}')
print(f'RT1060 replace-pattern link check built {len(suites)} scenarios on {sys.argv[2]}')
PY

# Link only: the physical-gate probes (stack use, card removal). Both write to a card, so the scenarios
# that enable them must never be flashed without physical approval.
probe_output="${CRUX_FILE_RT1060_PROBE_OUTPUT:-$repo/build/zephyr/twister-file-rt1060-probe}"
(cd "$workspace" && west twister -p "$board" -T "$repo/tests/board_images/sd_card_probe" \
    --build-only -O "$probe_output" --inline-logs)

python3 - "$probe_output/twister.json" "$board" <<'PY'
import json
import sys
from pathlib import Path

suites = json.load(open(sys.argv[1]))['testsuites']
names = sorted(s['name'] for s in suites)
expected = ['crux.file.sd_card_probe', 'crux.file.sd_card_probe.removal',
            'crux.file.sd_card_probe.stack']
if (names != expected or any(s['platform'] != sys.argv[2] or s.get('status') != 'not run' or
                             s.get('runnable') for s in suites)):
    raise RuntimeError(f'RT1060 probe link check did not build all scenarios: '
                       f"{[(s['name'], s['platform'], s.get('status')) for s in suites]}")
root = Path(sys.argv[1]).parent
wanted = {'crux.file.sd_card_probe': 'CONFIG_SAMPLE_SD_PROBE_NONE=y',
          'crux.file.sd_card_probe.stack': 'CONFIG_SAMPLE_SD_STACK_PROBE=y',
          'crux.file.sd_card_probe.removal': 'CONFIG_SAMPLE_SD_REMOVAL_PROBE=y'}
for name, line in wanted.items():
    configs = [p for p in root.rglob('.config') if p.parent.parent.name == name]
    if len(configs) != 1:
        raise RuntimeError(f'expected one build configuration for {name}, found {len(configs)}')
    if line not in configs[0].read_text().splitlines():
        raise RuntimeError(f'{name}: expected {line}')
print(f'RT1060 probe link check built {len(suites)} scenarios on {sys.argv[2]}')
PY

# Link only: the File provider on LittleFS over the microSD disk, with Configuration saving on the
# same volume. The image writes to a card, so it must never be flashed without physical approval.
littlefs_output="${CRUX_FILE_RT1060_LITTLEFS_OUTPUT:-$repo/build/zephyr/twister-file-rt1060-littlefs}"
(cd "$workspace" && west twister -p "$board" -T "$repo/tests/zephyr/file_littlefs_link" \
    --build-only -O "$littlefs_output" --inline-logs)

python3 - "$littlefs_output/twister.json" "$board" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

suites = json.load(open(sys.argv[1]))['testsuites']
name = 'crux.file.littlefs_blk_link_rt1060'
if (len(suites) != 1 or suites[0]['name'].rsplit('/', 1)[-1] != name or
        suites[0]['platform'] != sys.argv[2] or suites[0].get('status') != 'not run' or
        suites[0].get('runnable')):
    raise RuntimeError(f'RT1060 LittleFS File link check did not build: '
                       f"{[(s['name'], s['platform'], s.get('status')) for s in suites]}")
configs = list(Path(sys.argv[1]).parent.rglob('zephyr/.config'))
if len(configs) != 1:
    raise RuntimeError(f'expected one build configuration, found {len(configs)}')
build = configs[0].parent.parent
lines = configs[0].read_text().splitlines()
for line in ('CONFIG_CRUX_FILE_LITTLEFS_BLK_DEV=y',
             'CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS=y', 'CONFIG_DISK_DRIVER_SDMMC=y',
             'CONFIG_FS_LITTLEFS_CACHE_SIZE=512', 'CONFIG_SDHC_BUFFER_ALIGNMENT=32'):
    if line not in lines:
        raise RuntimeError(f'{line} is missing from {configs[0]}')
nm = next(line.split('=', 1)[1] for line in (build / 'CMakeCache.txt').read_text().splitlines()
          if line.startswith('CMAKE_NM:'))
present = {line.split()[-1] for line in subprocess.run(
    [nm, str(build / 'zephyr/zephyr.elf')], check=True, capture_output=True,
    text=True).stdout.splitlines() if len(line.split()) >= 3}
for symbol in ('main', 'littlefs_mount', 'crux_file_zephyr_bind', 'crux_file_open_at',
               'crux_config_save'):
    if symbol not in present:
        raise RuntimeError(f'{symbol} is not linked into the LittleFS File image')
for symbol in ('f_mount', 'red_mount2', 'littlefs_mkfs'):
    if symbol in present:
        raise RuntimeError(f'{symbol} is linked into the LittleFS File image')
print(f'RT1060 LittleFS File link check built on {sys.argv[2]}, without FatFs, Reliance Edge or a '
      'formatter entry')
PY

# The check is selected by devicetree facts, not by board name or revision: Rev C and the hyperflash
# variant have the same SD card node, so they configure and compile the same File object.
for other in 'mimxrt1060_evk@C/mimxrt1062/qspi' 'mimxrt1060_evk@B/mimxrt1062/hyperflash'; do
    variant="$repo/build/zephyr/file-rt1060-variant-${other//[@\/]/_}"
    (cd "$workspace" && west build -p always --cmake-only -b "$other" -d "$variant" \
        "$repo/tests/zephyr/file_fatfs_compile")
    grep -qx 'CONFIG_CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK=y' "$variant/zephyr/.config"
    cmake --build "$variant" --target crux_file_target_compile_only
    echo "SD card File compile check built on $other"
done

# Negative control: without an enabled zephyr,sdmmc-disk node the check must be refused, not
# skipped. An unsatisfied Kconfig dependency only warns, so the testcase's CMake rejects it.
control="$repo/build/zephyr/file-rt1060-refused-no-sd-disk"
mkdir -p "$(dirname "$control")"
printf '&usdhc1 { sdmmc { status = "disabled"; }; };\n' > "$control.overlay"
if (cd "$workspace" && west build -p always -b "$board" -d "$control" \
        "$repo/tests/zephyr/file_fatfs_compile" -- -DEXTRA_DTC_OVERLAY_FILE="$control.overlay" \
        > "$control.log" 2>&1); then
    echo "SD card File compile check was not refused without an SD card disk node" >&2
    exit 1
fi
# The refusal must come from the devicetree fact: Kconfig names the unmet disk-node dependency.
grep -q 'DT_HAS_ZEPHYR_SDMMC_DISK_ENABLED[) ]*(=n)' <(tr '\n' ' ' < "$control.log") || {
    echo "SD card File compile check was refused without the disk-node dependency" >&2
    exit 1
}
grep -q 'compile check is not selected' "$control.log" || {
    echo "SD card File compile check failed without an SD card disk node for another reason" >&2
    exit 1
}
echo "SD card File compile check refused without an SD card disk node, as intended"

# A board with its own name and the RT1062 SoC: the fictional compile-only fixture
# (tests/zephyr/board_fixture) must select the same check by devicetree, and compile the
# File object. Only that object is built: nothing is linked, and the fixture is never programmed.
fixture="$repo/build/zephyr/file-rt1060-fixture"
(cd "$workspace" && west build -p always --cmake-only -b crux_rt1062_fixture -d "$fixture" \
    "$repo/tests/zephyr/file_fatfs_compile" -- -DBOARD_ROOT="$repo/tests/zephyr/board_fixture")
grep -qx 'CONFIG_CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK=y' "$fixture/zephyr/.config"
cmake --build "$fixture" --target crux_file_target_compile_only
echo "RT1060 File compile check built on the fictional board crux_rt1062_fixture"
