#!/usr/bin/env bash
set -euo pipefail

repo="$(git rev-parse --show-toplevel)"
workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"
export ZEPHYR_BASE="$workspace/zephyr"
export ZEPHYR_TOOLCHAIN_VARIANT=host
littlefs="$(cd "$workspace" && west list littlefs -f '{abspath}')"
fatfs="$(cd "$workspace" && west list fatfs -f '{abspath}')"

# Actual VFS/LittleFS on both simulator widths; never a target board.
(cd "$workspace" && west twister -j 2 \
    -p native_sim/native -p native_sim/native/64 \
    -T "$repo/tests/native/file_littlefs" \
    -O "$repo/build/zephyr/twister-storage-file" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$littlefs")

# Actual FatFs on a RAM disk on both simulator widths; never a target board.
(cd "$workspace" && west twister -j 2 \
    -p native_sim/native -p native_sim/native/64 \
    -T "$repo/tests/native/file_fatfs" \
    -O "$repo/build/zephyr/twister-storage-fatfs" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$fatfs")

# The File additions (roots, stat, size, rename, listing) on the same FatFs RAM disk.
(cd "$workspace" && west twister -j 2 \
    -p native_sim/native -p native_sim/native/64 \
    -T "$repo/tests/native/file_roots" \
    -O "$repo/build/zephyr/twister-storage-file-roots" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$fatfs")

# The credential store's contract on the same FatFs, with its test-only protection (Issue #142).
(cd "$workspace" && west twister -j 2 \
    -p native_sim/native -p native_sim/native/64 \
    -T "$repo/tests/native/credential_fatfs" \
    -O "$repo/build/zephyr/twister-storage-credential" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$fatfs")

# The File provider on LittleFS over a block device (CONFIG_CRUX_FILE_LITTLEFS_BLK_DEV) on a RAM
# disk: the File contract and the additions, a mount that never formats, and Configuration saving on
# the same volume.
(cd "$workspace" && west twister -j 2 \
    -p native_sim/native -p native_sim/native/64 \
    -T "$repo/tests/native/file_littlefs_blk" \
    -O "$repo/build/zephyr/twister-storage-file-littlefs-blk" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$littlefs")

# The credential store's contract on the same provider, with its test-only protection.
(cd "$workspace" && west twister -j 2 \
    -p native_sim/native -p native_sim/native/64 \
    -T "$repo/tests/native/credential_littlefs" \
    -O "$repo/build/zephyr/twister-storage-credential-littlefs" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$littlefs")

# That provider stores names as they are, so the build refuses FatFs in the same image, naming the
# reason.
lfs_file_dir="$repo/build/zephyr/file-littlefs-blk-fatfs"
lfs_file_log="$lfs_file_dir.log"
if (cd "$workspace" && west build --cmake-only -p always -b native_sim/native/64 -d "$lfs_file_dir" \
        "$repo/tests/native/file_littlefs_blk" -- "-DZEPHYR_MODULES=$littlefs;$fatfs" \
        -DCONFIG_FAT_FILESYSTEM_ELM=y) >"$lfs_file_log" 2>&1; then
    printf 'The LittleFS block device File provider configured with FatFs in the image\n' >&2
    exit 1
fi
folded="$(tr -s '[:space:]' ' ' <"$lfs_file_log")"
[[ "$folded" == *'The LittleFS block device File provider refuses FatFs (CONFIG_FAT_FILESYSTEM_ELM)'* ]] || {
    printf 'The LittleFS block device File provider was not refused for FatFs; see %s\n' "$lfs_file_log" >&2
    exit 1
}
printf 'LittleFS block device File provider: refused with FatFs in the image, naming the reason\n'

# The microSD composition sequence (mount order, fail-closed policy) on a RAM disk named "SD".
(cd "$workspace" && west twister -j 2 \
    -p native_sim/native -p native_sim/native/64 \
    -T "$repo/tests/native/file_sd_composition" \
    -O "$repo/build/zephyr/twister-storage-sd-composition" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$fatfs")

# The write/read/restart check of the same sample (boot counter and a 4 KiB pattern file).
(cd "$workspace" && west twister -j 2 \
    -p native_sim/native -p native_sim/native/64 \
    -T "$repo/tests/native/file_sd_check" \
    -O "$repo/build/zephyr/twister-storage-sd-check" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$fatfs")

# The interrupted-write test: record format and recovery logic of tests/board_images/sd_card_power_cut_append.
(cd "$workspace" && west twister -j 2 \
    -p native_sim/native -p native_sim/native/64 \
    -T "$repo/tests/native/file_sd_interrupt" \
    -O "$repo/build/zephyr/twister-storage-sd-interrupt" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$fatfs")

# Its host script (parsing, pairing, port loss and return) runs against scripted boards, no hardware.
python3 -m unittest discover -s "$repo/tests/board_images/sd_card_power_cut_append/host" -p test_interrupt_capture.py -v

# The replace-pattern power-cut test: classification logic of tests/board_images/sd_card_power_cut_replace.
(cd "$workspace" && west twister -j 2 \
    -p native_sim/native -p native_sim/native/64 \
    -T "$repo/tests/native/file_sd_replace" \
    -O "$repo/build/zephyr/twister-storage-sd-replace" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$fatfs")

# Its host script (parsing, classification, cycle loop) runs against scripted boards, no hardware.
python3 -m unittest discover -s "$repo/tests/board_images/sd_card_power_cut_replace/host" -p test_replace_capture.py -v

# The probes for the remaining physical items: the workload and the removal state machine.
(cd "$workspace" && west twister -j 2 \
    -p native_sim/native -p native_sim/native/64 \
    -T "$repo/tests/native/file_sd_probe" \
    -O "$repo/build/zephyr/twister-storage-sd-probe" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$fatfs")

# The recovery step for the one state a Settings File compaction can leave after a power cut (no
# settings file, a complete temporary), on the real unpatched Settings File backend.
(cd "$workspace" && west twister -j 2 \
    -p native_sim/native -p native_sim/native/64 \
    -T "$repo/tests/native/file_sd_settings_recover" \
    -O "$repo/build/zephyr/twister-storage-sd-settings-recover" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$fatfs")

# The shared Configuration conformance cases, scalar and string, with the fake provider.
(cd "$workspace" && west twister -j 2 -p native_sim/native/64 \
    -T "$repo/tests/configuration/zephyr" \
    -O "$repo/build/zephyr/twister-configuration-software" --inline-logs)

# The status and configuration services with the real System, Time and Sync. Only here can a status
# poll be shown to leave the System contract's one permission to clear alone.
(cd "$workspace" && west twister -j 2 -p native_sim/native/64 \
    -T "$repo/tests/native/mgmt_services" \
    -O "$repo/build/zephyr/twister-mgmt-services" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$repo")

# The Configuration fixture stages its existing three pinned source copies.
(cd "$workspace" && west twister -j 2 -p native_sim/native/64 \
    -T "$repo/tests/native/configuration_settings" \
    -O "$repo/build/zephyr/twister-storage-configuration" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$repo")

python3 -m unittest discover -s "$repo/tests/native/configuration_settings" -p test_prepare.py -v

# Settings File on a FatFs RAM disk with the staged fault-propagation corrections. This is a
# 64-bit simulator fixture only; the corrected backend is not a product configuration.
(cd "$workspace" && west twister -j 2 -p native_sim/native/64 \
    -T "$repo/tests/native/configuration_settings_file" \
    -O "$repo/build/zephyr/twister-storage-settings-file" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$fatfs")

python3 -m unittest discover -s "$repo/tests/native/configuration_settings_file" -p test_prepare.py -v

# Negative control: the same suite on the unpatched upstream backend must fail exactly the
# cases that characterise its defects and pass the rest. Zephyr v4.5.0 returns a name write error
# and a compaction close error itself, so test_name_write_error_is_failure and
# test_compaction_close_error_is_not_success pass on it and are not in the three controls.
control="$repo/build/zephyr/settings-file-control"
(cd "$workspace" && west build -b native_sim/native/64 -d "$control" -p always \
    "$repo/tests/native/configuration_settings_file" -- \
    -DZEPHYR_MODULES="$fatfs" -DCRUX_SETTINGS_FILE_CONTROL=ON > "$control.build.log" 2>&1)
if timeout 120 "$control/zephyr/zephyr.exe" > "$control.run.log" 2>&1; then
    echo "settings-file control unexpectedly passed on the unpatched backend" >&2
    exit 1
fi
python3 - "$control.run.log" <<'PY'
import re
import sys

expected = {
    'test_a_callback_error_is_returned_by_the_load',
    'test_compaction_read_error_keeps_other_records',
    'test_compaction_read_fault_never_loses_a_record',
    'test_each_load_read_fault_preserves_active',
    'test_full_volume_never_acknowledges_a_lost_save',
    'test_interrupted_save_never_yields_a_wrong_value',
    'test_missing_file_with_a_compaction_leftover_is_an_error',
    'test_save_scan_error_is_not_success',
    'test_scan_read_error_is_not_missing',
    'test_short_write_is_failure',
    'test_zero_write_is_failure',
}
log = open(sys.argv[1], errors='replace').read()
failed = set(re.findall(r'^ - FAIL - \[configuration_settings_file\.(\w+)\]', log, re.M))
if failed != expected or 'pass = 15, fail = 11' not in log:
    raise RuntimeError(f'settings-file control differs: unexpected {sorted(failed - expected)}, '
                       f'missing {sorted(expected - failed)}')
print(f'settings-file control (unpatched backend): {len(failed)} of 26 cases fail as expected')
PY

# Configuration on the Settings File backend over LittleFS on a block device, through the target
# provider of the selection that does not depend on Reliance Edge
# (CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS). The only workspace module is LittleFS, so the
# image cannot reach Reliance Edge or FatFs. The cases of tests/native/configuration_settings_file
# run on a RAM disk named MMC with the corrected backend that the module stages. 64-bit native_sim
# only, as the FatFs suite.
(cd "$workspace" && west twister -j 2 -p native_sim/native/64 \
    -T "$repo/tests/native/configuration_settings_littlefs" \
    -O "$repo/build/zephyr/twister-storage-settings-littlefs" --inline-logs \
    --extra-args="ZEPHYR_MODULES=$littlefs")
python3 - "$repo/build/zephyr/twister-storage-settings-littlefs" <<'PY'
import json
from pathlib import Path
import subprocess
import sys

output = Path(sys.argv[1])
# Twister scans only the case of extra_cases.c. The others are in the shared main.c, and the exact
# names are required here, so that a case dropped from either source cannot go unnoticed. They are
# the shared cases of the Reliance Edge suite: the read-back case exists only in the FatFs probe copy.
expected = {
    'a_callback_error_is_returned_by_the_load', 'a_missing_settings_file_reads_as_missing',
    'callback_short_count_preserves_active', 'compaction_close_error_is_not_success',
    'compaction_read_error_keeps_other_records', 'compaction_read_fault_never_loses_a_record',
    'each_load_read_fault_preserves_active', 'full_volume_never_acknowledges_a_lost_save',
    'interrupted_save_never_yields_a_wrong_value', 'malformed_records_are_rejected',
    'many_saves_keep_every_key_across_compactions', 'missing_and_valid_roundtrip',
    'missing_file_with_a_compaction_leftover_is_an_error', 'name_write_error_is_failure',
    'read_fault_never_yields_a_stale_value', 'roundtrip_survives_remount_for_u32_and_bool',
    'save_after_a_torn_tail_records_the_outcome', 'save_scan_error_is_not_success',
    'scan_read_error_is_not_missing', 'short_write_is_failure', 'staging_limit_boundary',
    'string_roundtrip_survives_remount',
    'truncated_tail_keeps_earlier_records', 'value_only_corruption_is_not_detected',
    'zero_write_is_failure',
    'compaction_leaves_no_cmp_file',
}
name = 'crux.configuration.settings_littlefs'
suites = json.loads((output / 'twister.json').read_text())['testsuites']
if len(suites) != 1 or suites[0]['name'].rsplit('/', 1)[-1] != name:
    raise RuntimeError(f'unexpected or missing Settings File suites: {[s["name"] for s in suites]}')
suite = suites[0]
prefix = name + '.configuration_settings_littlefs.'
cases = {c['identifier'][len(prefix):]: c['status'] for c in suite.get('testcases', [])}
passed = {case for case, status in cases.items() if status == 'passed'}
if (suite.get('platform') != 'native_sim/native/64' or suite.get('status') != 'passed' or
        not suite.get('runnable') or passed != expected or len(cases) != len(passed)):
    raise RuntimeError(f'{name}: passed {sorted(passed)}, all {sorted(cases.items())}')
print(f'{name}: {len(passed)} executed cases PASS')

# The image holds the real provider and not the probe copy, LittleFS and neither FatFs nor Reliance
# Edge, and was built from the corrected copies of the Settings File sources, not the pinned ones.
builds = list(output.rglob('compile_commands.json'))
if len(builds) != 1:
    raise RuntimeError(f'expected one build, found {len(builds)}')
build = builds[0].parent
files = {str(Path(entry['directory'], entry['file']).resolve())
         for entry in json.loads(builds[0].read_text())}
staged = {source for source in ('settings_file.c', 'settings_line.c', 'settings_store.c')
          if str((build / 'settings-file-candidate' / source).resolve()) in files}
originals = [f for f in files if f.endswith(('subsys/settings/src/settings_file.c',
                                                'subsys/settings/src/settings_line.c',
                                                'subsys/settings/src/settings_store.c'))]
if staged != {'settings_file.c', 'settings_line.c', 'settings_store.c'} or originals:
    raise RuntimeError(f'staged copies {sorted(staged)}, pinned originals built {originals}')
if (not any(f.endswith('components/configuration/ports/zephyr/configuration_settings.c')
            for f in files) or any(f.endswith('configuration_no_provider.c') for f in files)):
    raise RuntimeError('the build does not compile the Settings File provider alone')
symbols = subprocess.run(['nm', str(build / 'zephyr/zephyr.exe')], check=True, capture_output=True,
                         text=True).stdout.split()
for wanted in ('crux_config_zephyr_init', 'crux_config_save', 'littlefs_mount'):
    if wanted not in symbols:
        raise RuntimeError(f'{wanted} is not in the image')
for unwanted in ('crux_probe_read_back', 'f_mount', 'red_mount2'):
    if unwanted in symbols:
        raise RuntimeError(f'{unwanted} is in the image of the target provider on LittleFS')
print('Settings File on LittleFS: the real provider with the staged corrections, no FatFs, '
      'no Reliance Edge, no probe copy')
PY

# Negative control: the same suite on the unpatched upstream backend must fail exactly the cases that
# characterise its defects on this file system, and pass the rest.
lfs_control="$repo/build/zephyr/settings-littlefs-control"
(cd "$workspace" && west build -b native_sim/native/64 -d "$lfs_control" -p always \
    "$repo/tests/native/configuration_settings_littlefs" -- \
    -DZEPHYR_MODULES="$littlefs" -DCRUX_SETTINGS_FILE_CONTROL=ON > "$lfs_control.build.log" 2>&1)
if timeout 180 "$lfs_control/zephyr/zephyr.exe" > "$lfs_control.run.log" 2>&1; then
    echo "settings-littlefs control unexpectedly passed on the unpatched backend" >&2
    exit 1
fi
python3 - "$lfs_control.run.log" <<'PY'
import re
import sys

# The same 10 cases as on Reliance Edge (scripts/test-storage-emmc.sh), for the same reason: the
# unpatched backend turns an injected I/O fault into success, a missing key or a lost record. As on
# Reliance Edge and unlike FatFs, test_full_volume_never_acknowledges_a_lost_save passes: LittleFS
# answers a write that finds no free block with -ENOSPC, which the unpatched backend returns.
expected = {
    'test_a_callback_error_is_returned_by_the_load',
    'test_compaction_read_error_keeps_other_records',
    'test_compaction_read_fault_never_loses_a_record',
    'test_each_load_read_fault_preserves_active',
    'test_interrupted_save_never_yields_a_wrong_value',
    'test_missing_file_with_a_compaction_leftover_is_an_error',
    'test_save_scan_error_is_not_success',
    'test_scan_read_error_is_not_missing',
    'test_short_write_is_failure',
    'test_zero_write_is_failure',
}
log = open(sys.argv[1], errors='replace').read()
failed = set(re.findall(r'^ - FAIL - \[configuration_settings_littlefs\.(\w+)\]', log, re.M))
if failed != expected or 'pass = 16, fail = 10, skip = 0, total = 26' not in log:
    raise RuntimeError(f'settings-littlefs control differs: unexpected {sorted(failed - expected)}, '
                       f'missing {sorted(expected - failed)}')
print(f'settings-littlefs control (unpatched backend): {len(failed)} of 26 cases fail as expected, '
      '16 pass')
PY

# The selection refuses FatFs (owner decision 4 of the configuration persistence spike): a FatFs
# rename removes the destination first, so a power cut in a compaction can leave the settings file
# missing. With FatFs in the image the module refuses the build at CMake, naming the reason. A Kconfig
# dependency would only drop the selection with a warning and build an image without a provider.
fat_dir="$repo/build/zephyr/settings-littlefs-fatfs"
fat_log="$fat_dir.log"
if (cd "$workspace" && west build --cmake-only -p always -b native_sim/native/64 -d "$fat_dir" \
        "$repo/tests/native/configuration_settings_littlefs" -- "-DZEPHYR_MODULES=$littlefs;$fatfs" \
        -DCONFIG_FAT_FILESYSTEM_ELM=y) >"$fat_log" 2>&1; then
    printf 'The Settings File selection configured with FatFs in the image\n' >&2
    exit 1
fi
folded="$(tr -s '[:space:]' ' ' <"$fat_log")"
[[ "$folded" == *"The Settings File selection refuses FatFs (CONFIG_FAT_FILESYSTEM_ELM)"* ]] || {
    printf 'The Settings File selection was not refused for FatFs; see %s\n' "$fat_log" >&2
    exit 1
}
printf 'Settings File selection: refused with FatFs in the image, naming the reason\n'

# Power-cut replay of W4 on LittleFS over the eMMC simulator: three keys saved through the Settings
# File backend under the same selection, which compacts its file through a temporary and a rename.
# lfs-fix-settings has the MMC cache flush correction, which the selection requires on an MMC disk.
# lfs-nofix-settings is built without it under the fixture-only CRUX_EMMC_FLUSH_CONTROL, for the
# flush control. Without the correction or the control, the image is refused at CMake.
lfs_powercut="$repo/build/zephyr/powercut-littlefs"
lfs_guard_log="$lfs_powercut-guard.log"
if (cd "$workspace" && west build --cmake-only -p always -b native_sim/native/64 \
        -d "$lfs_powercut/lfs-guard" "$repo/tests/native/emmc_powercut" -- \
        -DZEPHYR_MODULES="$littlefs" "-DEXTRA_CONF_FILE=littlefs.conf;settings_littlefs.conf" \
        -DCONFIG_CRUX_MMC_CACHE_FLUSH=n) >"$lfs_guard_log" 2>&1; then
    printf 'The Settings File selection on an MMC disk configured without the flush correction\n' >&2
    exit 1
fi
folded="$(tr -s '[:space:]' ' ' <"$lfs_guard_log")"
[[ "$folded" == *'The Settings File selection on an MMC disk requires CONFIG_CRUX_MMC_CACHE_FLUSH=y'* ]] || {
    printf 'The MMC guard of the Settings File selection did not fail for the stated reason; see %s\n' \
        "$lfs_guard_log" >&2
    exit 1
}
printf 'Settings File selection MMC guard: refused without the flush correction\n'
(cd "$workspace" && west build -p always -b native_sim/native/64 -d "$lfs_powercut/lfs-fix-settings" \
    "$repo/tests/native/emmc_powercut" -- -DZEPHYR_MODULES="$littlefs" \
    "-DEXTRA_CONF_FILE=littlefs.conf;settings_littlefs.conf" -DCONFIG_CRUX_MMC_CACHE_FLUSH=y)
(cd "$workspace" && west build -p always -b native_sim/native/64 -d "$lfs_powercut/lfs-nofix-settings" \
    "$repo/tests/native/emmc_powercut" -- -DZEPHYR_MODULES="$littlefs" \
    "-DEXTRA_CONF_FILE=littlefs.conf;settings_littlefs.conf" -DCONFIG_CRUX_MMC_CACHE_FLUSH=n \
    -DCRUX_EMMC_FLUSH_CONTROL=ON)
python3 "$repo/tests/native/emmc_powercut/run_replay.py" \
    --exe-fix "$lfs_powercut/lfs-fix-settings/zephyr/zephyr.exe" \
    --exe-nofix "$lfs_powercut/lfs-nofix-settings/zephyr/zephyr.exe" \
    --fs littlefs --workload W4 --seed 1 --samples 8 --max-seconds 600 --out "$lfs_powercut/replay"

# The counts are exact for seed 1 and 8 samples. They depend on the traces, so on the pinned Zephyr
# and LittleFS, and on the algorithms of Python's random module. A cut that leaves the backend's
# temporary behind is counted, and is not a failure. A missing active file would be.
python3 - "$lfs_powercut/replay/littlefs-w4.json" <<'PY'
import json
from pathlib import Path
import sys

report = json.loads(Path(sys.argv[1]).read_text())
if report.get('workload') != 'W4' or list(report['observations']) != ['W4']:
    raise RuntimeError(f'not a W4 report: {sorted(report)}')
if report['asserted'] != ['I1', 'I2', 'I3', 'I4', 'I5', 'read_error=0']:
    raise RuntimeError(f'asserted: {report["asserted"]}')
models = {'cached': {'lost', 'prefix', 'reordered', 'torn'}, 'nocache': {'prefix', 'torn'}}
leftovers = 0
for profile, expected in models.items():
    groups = report['observations']['W4'][profile]
    if (set(groups) != expected or
            any(group['cases'] == 0 or group['passed'] != group['cases'] for group in groups.values())):
        raise RuntimeError(f'W4 {profile}: missing or failing cases')
    leftovers += sum(group.get('cmp_leftover', 0) for group in groups.values())
    trace = report['traces']['W4'][profile]
    if trace['writes'] == 0 or (profile == 'cached' and trace['flushes'] == 0):
        raise RuntimeError(f'W4 {profile}: the trace holds no write or no flush')
if leftovers == 0:
    raise RuntimeError('no W4 cut left a temporary behind, so none reached the compaction')
controls = {control['name']: control['failed_as_required'] for control in report['controls']}
if controls != {'flush': True, 'early acknowledgement': True, 'damaged image': True}:
    raise RuntimeError(f'controls: {controls}')
staged = report['staged_w4']
if (not staged['as_required'] or
        sorted(case['damage'] for case in staged['cases']) != ['leftover', 'missing', 'none']):
    raise RuntimeError(f'staged W4 states: {staged}')
if report['counts']['cases'] != 493 or report['failures']:
    raise RuntimeError(f'counts {report["counts"]}, failures {report["failures"]}')
print(f'replay littlefs W4: {report["counts"]["cases"]} cases, invariants held on lfs-fix-settings, '
      f'{leftovers} cases with a temporary left behind, all three controls failed as required')
PY

# Power-cut replay of the File provider on the same LittleFS over the eMMC simulator: W5 appends
# records through File, W8 replaces a file with File writes and the VFS rename, and W8C replaces as
# File allows today. lfs-fix-file has the MMC cache flush correction, which a File composition on an
# MMC disk requires. lfs-nofix-file is built without it under the fixture-only
# CRUX_EMMC_FLUSH_CONTROL, for the flush control. Without the correction or the control, the image is
# refused at CMake. These are results of the simulator's model, not evidence about a device.
lfs_file_guard_log="$lfs_powercut-file-guard.log"
if (cd "$workspace" && west build --cmake-only -p always -b native_sim/native/64 \
        -d "$lfs_powercut/lfs-file-guard" "$repo/tests/native/emmc_powercut" -- \
        -DZEPHYR_MODULES="$littlefs" "-DEXTRA_CONF_FILE=littlefs.conf;littlefs-file.conf" \
        -DCONFIG_CRUX_MMC_CACHE_FLUSH=n) >"$lfs_file_guard_log" 2>&1; then
    printf 'The LittleFS File provider on an MMC disk configured without the flush correction\n' >&2
    exit 1
fi
folded="$(tr -s '[:space:]' ' ' <"$lfs_file_guard_log")"
[[ "$folded" == *'A Crux File composition on an MMC disk requires CONFIG_CRUX_MMC_CACHE_FLUSH=y'* ]] || {
    printf 'The MMC guard of the LittleFS File provider did not fail for the stated reason; see %s\n' \
        "$lfs_file_guard_log" >&2
    exit 1
}
printf 'LittleFS File provider MMC guard: refused without the flush correction\n'
(cd "$workspace" && west build -p always -b native_sim/native/64 -d "$lfs_powercut/lfs-fix-file" \
    "$repo/tests/native/emmc_powercut" -- -DZEPHYR_MODULES="$littlefs" \
    "-DEXTRA_CONF_FILE=littlefs.conf;littlefs-file.conf" -DCONFIG_CRUX_MMC_CACHE_FLUSH=y)
(cd "$workspace" && west build -p always -b native_sim/native/64 -d "$lfs_powercut/lfs-nofix-file" \
    "$repo/tests/native/emmc_powercut" -- -DZEPHYR_MODULES="$littlefs" \
    "-DEXTRA_CONF_FILE=littlefs.conf;littlefs-file.conf" -DCONFIG_CRUX_MMC_CACHE_FLUSH=n \
    -DCRUX_EMMC_FLUSH_CONTROL=ON)
for workload in W5 W8; do
    python3 "$repo/tests/native/emmc_powercut/run_replay.py" \
        --exe-fix "$lfs_powercut/lfs-fix-file/zephyr/zephyr.exe" \
        --exe-nofix "$lfs_powercut/lfs-nofix-file/zephyr/zephyr.exe" \
        --fs littlefs --workload "$workload" --seed 1 --samples 8 --max-seconds 600 \
        --out "$lfs_powercut/replay"
done

# Every case of both profiles and every model must hold the invariants. A W8C case may instead be the
# window that remove-then-rename opens, and the window control requires one in every generation.
python3 - "$lfs_powercut/replay" <<'PY'
import json
from pathlib import Path
import sys

models = {'cached': {'lost', 'prefix', 'reordered', 'torn'}, 'nocache': {'prefix', 'torn'}}
runs = {
    'W5': (['W5'], ['damaged image', 'early acknowledgement', 'flush']),
    'W8': (['W8', 'W8C'], ['damaged image', 'early acknowledgement', 'flush', 'window']),
}
for name, (workloads, expected_controls) in runs.items():
    report = json.loads((Path(sys.argv[1]) / f'littlefs-{name.lower()}.json').read_text())
    if report.get('workload') != name or sorted(report['observations']) != workloads:
        raise RuntimeError(f'not a {name} report: {sorted(report)}')
    if report['asserted'] != ['I1', 'I2', 'I3', 'I4', 'I5', 'read_error=0']:
        raise RuntimeError(f'{name} asserted: {report["asserted"]}')
    controls = {control['name']: control['failed_as_required'] for control in report['controls']}
    if controls != {control: True for control in expected_controls}:
        raise RuntimeError(f'{name} controls: {controls}')
    for workload in workloads:
        for profile, expected in models.items():
            groups = report['observations'][workload][profile]
            allowed = 'window' if workload == 'W8C' else None
            if (set(groups) != expected or
                    any(group['cases'] == 0 or
                        group['passed'] + group.get(allowed, 0) != group['cases']
                        for group in groups.values())):
                raise RuntimeError(f'{workload} {profile}: missing or failing cases')
            trace = report['traces'][workload][profile]
            if trace['writes'] == 0 or trace['marks'] == 0 or (profile == 'cached' and
                                                               trace['flushes'] == 0):
                raise RuntimeError(f'{workload} {profile}: the trace holds no write, mark or flush')
    if report['failures'] or report['counts']['cases'] == 0:
        raise RuntimeError(f'{name}: counts {report["counts"]}, failures {report["failures"]}')
    print(f'replay littlefs {name}: {report["counts"]["cases"]} cases, invariants held on '
          f'lfs-fix-file, all {len(controls)} controls failed as required')
PY

# A filtered/build-only Twister run must not satisfy the provider gate.
python3 - "$repo/build/zephyr" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
for directory, expected in [
    ('twister-storage-file', {'native_sim/native': 7, 'native_sim/native/64': 7}),
    # Two scenarios: the default pools and CONFIG_CRUX_FILE_POOL_SIZE=8 (crux.file.fatfs.pool8).
    ('twister-storage-fatfs', {('native_sim/native', 'crux.file.fatfs'): 19,
                               ('native_sim/native/64', 'crux.file.fatfs'): 19,
                               ('native_sim/native', 'crux.file.fatfs.pool8'): 19,
                               ('native_sim/native/64', 'crux.file.fatfs.pool8'): 19}),
    ('twister-storage-file-roots', {'native_sim/native': 5, 'native_sim/native/64': 5}),
    ('twister-storage-credential', {'native_sim/native': 2, 'native_sim/native/64': 2}),
    # Two scenarios: the default pools and CONFIG_CRUX_FILE_POOL_SIZE=8 (crux.file.littlefs_blk.pool8).
    ('twister-storage-file-littlefs-blk',
     {('native_sim/native', 'crux.file.littlefs_blk'): 16,
      ('native_sim/native/64', 'crux.file.littlefs_blk'): 16,
      ('native_sim/native', 'crux.file.littlefs_blk.pool8'): 16,
      ('native_sim/native/64', 'crux.file.littlefs_blk.pool8'): 16}),
    ('twister-storage-credential-littlefs', {'native_sim/native': 2, 'native_sim/native/64': 2}),
    ('twister-storage-sd-composition', {'native_sim/native': 8, 'native_sim/native/64': 8}),
    ('twister-storage-sd-probe', {'native_sim/native': 4, 'native_sim/native/64': 4}),
    ('twister-storage-sd-check', {'native_sim/native': 8, 'native_sim/native/64': 8}),
    ('twister-storage-sd-interrupt', {'native_sim/native': 7, 'native_sim/native/64': 7}),
    ('twister-storage-sd-replace', {'native_sim/native': 7, 'native_sim/native/64': 7}),
    ('twister-storage-sd-settings-recover', {'native_sim/native': 13, 'native_sim/native/64': 13}),
    ('twister-configuration-software', {'native_sim/native/64': 2}),
    ('twister-mgmt-services', {'native_sim/native/64': 4}),
    ('twister-storage-configuration', {'native_sim/native/64': 11}),
    ('twister-storage-settings-file', {'native_sim/native/64': 26}),
    ('twister-storage-settings-littlefs', {'native_sim/native/64': 26}),
]:
    suites = json.loads((root / directory / 'twister.json').read_text())['testsuites']
    # A key is a platform, or a (platform, scenario) pair where a directory has several scenarios.
    by_scenario = isinstance(next(iter(expected)), tuple)
    def key(suite):
        return ((suite['platform'], suite['name'].rsplit('/', 1)[-1]) if by_scenario
                else suite['platform'])
    if len(suites) != len(expected) or {key(s) for s in suites} != set(expected):
        raise RuntimeError(f'{directory}: unexpected or missing simulator suites')
    for suite in suites:
        cases = suite.get('testcases', [])
        if (suite.get('status') != 'passed' or not suite.get('runnable') or
                len(cases) != expected[key(suite)] or
                any(c.get('status') != 'passed' for c in cases)):
            raise RuntimeError(f'{directory}: provider cases did not all execute and pass')
        print(f"{directory} {key(suite)}: {len(cases)} executed cases PASS")
PY

# Source staging must not patch the original Zephyr checkout.
git -C "$ZEPHYR_BASE" diff HEAD --exit-code -- \
    subsys/settings/src/settings_store.c subsys/settings/src/settings_nvs.c subsys/kvss/nvs/nvs.c \
    subsys/settings/src/settings_file.c subsys/settings/src/settings_line.c
