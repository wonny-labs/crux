/*
 * Composition for CONFIG_CRUX_FILE_FATFS_SIMULATOR: FatFs on the RAM disk of
 * fatfs_ram_disk.overlay, through the Zephyr file system API.
 */
#include "storage.h"

#include <crux/file.h>
#include <crux/file_zephyr.h>
#include <errno.h>
#include <ff.h>
#include <stdint.h>
#include <zephyr/fs/fs.h>
#include <zephyr/sys/printk.h>

#define DISK_NAME "RAM"
#define MOUNT_POINT "/" DISK_NAME ":"
#define FILE_ROOT MOUNT_POINT "/files"

static FATFS fat_fs;

static struct fs_mount_t mount = {
    .type = FS_FATFS,
    .fs_data = &fat_fs,
    .mnt_point = MOUNT_POINT,
    .flags = FS_MOUNT_FLAG_NO_FORMAT,
};

const char *const storage_provider_name = "fatfs_ram_disk";

int storage_init(void)
{
    int rc = fs_mount(&mount);
    if (rc != 0) {
        /*
         * A RAM disk is empty at every start, so it is formatted here. Formatting is the
         * composition's decision; the File provider never mounts or formats anything.
         */
        rc = fs_mkfs(FS_FATFS, (uintptr_t)DISK_NAME ":", NULL, 0);
        if (rc == 0) {
            rc = fs_mount(&mount);
        }
    }
    if (rc != 0) {
        printk("Storage: FatFs mount failed (%d)\n", rc);
        return rc;
    }

    rc = fs_mkdir(FILE_ROOT);
    if (rc != 0 && rc != -EEXIST) {
        printk("Storage: cannot create %s (%d)\n", FILE_ROOT, rc);
        return rc;
    }
    if (crux_file_zephyr_bind(FILE_ROOT) != CRUX_FILE_OK) {
        printk("Storage: cannot bind %s as the File root\n", FILE_ROOT);
        return -EIO;
    }

    printk("Storage: FatFs on a RAM disk, bound at %s\n", FILE_ROOT);
    return 0;
}
