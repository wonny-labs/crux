/*
 * Composition for CONFIG_CRUX_FILE_SIMULATOR: LittleFS on a partition of the native_sim flash
 * simulator (app.overlay), through the Zephyr file system API.
 */
#include "storage.h"

#include <crux/file.h>
#include <crux/file_zephyr.h>
#include <errno.h>
#include <stdint.h>
#include <zephyr/fs/fs.h>
#include <zephyr/fs/littlefs.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/sys/printk.h>

#define MOUNT_POINT "/lfs"
#define FILE_ROOT MOUNT_POINT "/files"

FS_LITTLEFS_DECLARE_DEFAULT_CONFIG(littlefs_storage);

static struct fs_mount_t mount = {
    .type = FS_LITTLEFS,
    .fs_data = &littlefs_storage,
    .storage_dev = (void *)PARTITION_ID(file_sample_partition),
    .mnt_point = MOUNT_POINT,
    .flags = FS_MOUNT_FLAG_NO_FORMAT,
};

const char *const storage_provider_name = "simulator";

int storage_init(void)
{
    int rc = fs_mount(&mount);
    if (rc != 0) {
        /*
         * A blank simulated partition is formatted here. Formatting is the composition's
         * decision; the File provider never mounts or formats anything.
         */
        rc = fs_mkfs(FS_LITTLEFS, (uintptr_t)mount.storage_dev, NULL, 0);
        if (rc == 0) {
            rc = fs_mount(&mount);
        }
    }
    if (rc != 0) {
        printk("Storage: LittleFS mount failed (%d)\n", rc);
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

    printk("Storage: LittleFS on the flash simulator, bound at %s\n", FILE_ROOT);
    return 0;
}
