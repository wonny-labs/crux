/* SPDX-License-Identifier: Apache-2.0 */
/*
 * LittleFS over a block device (FS_LITTLEFS_BLK_DEV) as the file system under test, on disk "MMC".
 * LittleFS initialises the disk itself when it mounts or formats. A mount never formats.
 */
#include "fs_backend.h"

#include <stdint.h>
#include <zephyr/fs/fs.h>
#include <zephyr/fs/littlefs.h>

#define POWERCUT_DISK "MMC"

FS_LITTLEFS_DECLARE_DEFAULT_CONFIG(powercut_littlefs);

static struct fs_mount_t mount = {
    .type = FS_LITTLEFS,
    .mnt_point = POWERCUT_MOUNT_POINT,
    .fs_data = &powercut_littlefs,
    .storage_dev = (void *)POWERCUT_DISK,
    .flags = FS_MOUNT_FLAG_USE_DISK_ACCESS | FS_MOUNT_FLAG_NO_FORMAT,
};

int powercut_fs_format(void)
{
    return fs_mkfs(FS_LITTLEFS, (uintptr_t)POWERCUT_DISK, &powercut_littlefs,
                   FS_MOUNT_FLAG_USE_DISK_ACCESS);
}

int powercut_fs_mount(void)
{
    return fs_mount(&mount);
}

int powercut_fs_unmount(void)
{
    return fs_unmount(&mount);
}
