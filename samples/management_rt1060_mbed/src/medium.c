/* SPDX-License-Identifier: Apache-2.0 */
/* The mount of the RAM disk, and its format when blank: see medium.h. This is the only source of
 * the image that names a format function, and it names the RAM disk's name only. */
#include "medium.h"

#include <ff.h>
#include <stdint.h>
#include <zephyr/devicetree.h>
#include <zephyr/fs/fs.h>
#include <zephyr/sys/printk.h>

#define RAM_DISK_NAME "RAM:"
#define RAM_DISK_BYTES                                                                             \
    ((unsigned)(DT_PROP(DT_NODELABEL(mgmt_ram_disk), sector_size) *                                \
                DT_PROP(DT_NODELABEL(mgmt_ram_disk), sector_count)))

static FATFS fat;
/* FS_MOUNT_FLAG_NO_FORMAT: a failed mount is a failed mount in the file system layer too. The
 * format is ours. */
static struct fs_mount_t mount = {
    .type = FS_FATFS,
    .mnt_point = MEDIUM_MOUNT_POINT,
    .fs_data = &fat,
    .flags = FS_MOUNT_FLAG_NO_FORMAT,
};

bool medium_mount(void)
{
    bool formatted = false;
    int result = fs_mount(&mount);

    if (result != 0) {
        /* The one place a format is reached. */
        if (fs_mkfs(FS_FATFS, (uintptr_t)RAM_DISK_NAME, NULL, 0) == 0) {
            formatted = true;
            result = fs_mount(&mount);
        }
    }
    printk("MBED-MGMT file-medium ram-disk %u B in SDRAM, %s, mounted=%d: nothing persists across "
           "a reset\n",
           RAM_DISK_BYTES, formatted ? "formatted at this boot" : "found formatted", result == 0);
    return result == 0;
}
