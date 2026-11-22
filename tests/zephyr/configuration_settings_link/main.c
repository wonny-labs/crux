/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Link only: a Configuration consumer over the Settings File provider on LittleFS. It mounts the
 * volume without formatting it, initialises the settings only when the settings directory exists,
 * then loads one parameter and saves it, so that crux_config_save and the provider's write path are
 * in the image. The image is never flashed: the EVKB has no eMMC.
 */
#include "configuration_settings.h"

#include <crux/configuration.h>
#include <stdint.h>
#include <zephyr/fs/fs.h>
#include <zephyr/fs/littlefs.h>

FS_LITTLEFS_DECLARE_DEFAULT_CONFIG(link_littlefs);

static struct fs_mount_t mount = {
    .type = FS_LITTLEFS,
    .mnt_point = "/MMC:",
    .fs_data = &link_littlefs,
    .storage_dev = (void *)"MMC",
    .flags = FS_MOUNT_FLAG_USE_DISK_ACCESS | FS_MOUNT_FLAG_NO_FORMAT,
};

static const crux_config_spec_t spec = {
    .key = "speed",
    .schema_version = 1,
    .default_value = {.type = CRUX_CONFIG_U32, .data.u32 = 11},
};

int main(void)
{
    struct fs_dirent entry;
    crux_config_param_t param = {0};
    crux_config_value_t value = {.type = CRUX_CONFIG_U32, .data.u32 = 12};

    if (fs_mount(&mount) != 0 || fs_stat("/MMC:/settings", &entry) != 0 ||
        entry.type != FS_DIR_ENTRY_DIR || crux_config_zephyr_init() != CRUX_CONFIG_OK ||
        crux_config_init(&param, &spec) != CRUX_CONFIG_OK) {
        return 1;
    }
    (void)crux_config_load(&param);
    if (crux_config_update(&param, &value) != CRUX_CONFIG_OK) {
        return 1;
    }
    return crux_config_save(&param) == CRUX_CONFIG_OK ? 0 : 1;
}
