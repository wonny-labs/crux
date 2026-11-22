/* SPDX-License-Identifier: Apache-2.0 */
/* LittleFS over a block device, a RAM disk named like the eMMC disk: the fixture that the Settings
 * File suite includes for the target provider on a file system other than Reliance Edge. The medium
 * is provisioned as an operator would, with the two directories made before the settings are
 * initialised, because the firmware makes none. A mount never formats. */
#ifndef CRUX_TESTS_CONFIGURATION_SETTINGS_FIXTURE_LITTLEFS_H
#define CRUX_TESTS_CONFIGURATION_SETTINGS_FIXTURE_LITTLEFS_H

#include <stdint.h>
#include <zephyr/fs/fs.h>
#include <zephyr/fs/littlefs.h>
#include <zephyr/ztest.h>

#define FIXTURE_DISK "MMC"
#define FIXTURE_ROOT "/MMC:"
/* LittleFS commits a file's blocks only when the file is synced, so the suite's volume filler syncs
 * after each chunk. Without it the filler's blocks stay free and the volume never fills. */
#define FIXTURE_FILL_SYNCS_EACH_CHUNK 1

FS_LITTLEFS_DECLARE_DEFAULT_CONFIG(fixture_littlefs);

/* Not static: extra_cases.c unmounts and remounts the volume. */
struct fs_mount_t fixture_mount = {
    .type = FS_LITTLEFS,
    .mnt_point = FIXTURE_ROOT,
    .fs_data = &fixture_littlefs,
    .storage_dev = (void *)FIXTURE_DISK,
    .flags = FS_MOUNT_FLAG_USE_DISK_ACCESS | FS_MOUNT_FLAG_NO_FORMAT,
};

static void fixture_provision(void)
{
    zassert_ok(fs_mkfs(FS_LITTLEFS, (uintptr_t)FIXTURE_DISK, &fixture_littlefs,
                       FS_MOUNT_FLAG_USE_DISK_ACCESS));
    zassert_ok(fs_mount(&fixture_mount));
    zassert_ok(fs_mkdir(FIXTURE_ROOT "/files"));
    zassert_ok(fs_mkdir(FIXTURE_ROOT "/settings"));
}

#endif /* CRUX_TESTS_CONFIGURATION_SETTINGS_FIXTURE_LITTLEFS_H */
