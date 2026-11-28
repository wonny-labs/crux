/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Link only: the File provider on LittleFS on the microSD disk, with Configuration saving on the
 * same volume. It follows the product recipe: mount without formatting, check the two directories,
 * bind the File root, initialise the settings, then write a File and save a parameter, so that both
 * write paths are in the image. It formats nothing, but it writes to a card: the image is never
 * flashed without approval for the board and the card.
 */
#include <crux/configuration.h>
#include <crux/configuration_zephyr.h>
#include <crux/file.h>
#include <crux/file_zephyr.h>
#include <stdint.h>
#include <zephyr/fs/fs.h>
#include <zephyr/fs/littlefs.h>

FS_LITTLEFS_DECLARE_DEFAULT_CONFIG(link_littlefs);

static struct fs_mount_t mount = {
    .type = FS_LITTLEFS,
    .mnt_point = "/lfs",
    .fs_data = &link_littlefs,
    .storage_dev = (void *)"SD",
    .flags = FS_MOUNT_FLAG_USE_DISK_ACCESS | FS_MOUNT_FLAG_NO_FORMAT,
};

static const crux_config_spec_t spec = {
    .key = "speed",
    .schema_version = 1,
    .default_value = {.type = CRUX_CONFIG_U32, .data.u32 = 11},
};

static bool directory(const char *path)
{
    struct fs_dirent entry;

    return fs_stat(path, &entry) == 0 && entry.type == FS_DIR_ENTRY_DIR;
}

static bool write_record(void)
{
    crux_file_t *file = NULL;
    size_t count = 0;

    if (crux_file_open("record", CRUX_FILE_CREATE_REPLACE, &file) != CRUX_FILE_OK) {
        return false;
    }
    bool written = crux_file_write(file, "record", 6, &count) == CRUX_FILE_OK &&
                   crux_file_sync(file) == CRUX_FILE_OK;
    return crux_file_close(&file) == CRUX_FILE_OK && written;
}

int main(void)
{
    crux_config_param_t param = {0};
    crux_config_value_t value = {.type = CRUX_CONFIG_U32, .data.u32 = 12};

    /* A failed mount stops here: the volume is never formatted on this path. */
    if (fs_mount(&mount) != 0 || !directory("/lfs/files") || !directory("/lfs/settings") ||
        crux_file_zephyr_bind("/lfs/files") != CRUX_FILE_OK ||
        crux_config_zephyr_init() != CRUX_CONFIG_OK ||
        crux_config_init(&param, &spec) != CRUX_CONFIG_OK) {
        return 1;
    }
    (void)crux_config_load(&param);
    if (!write_record() || crux_config_update(&param, &value) != CRUX_CONFIG_OK) {
        return 1;
    }
    return crux_config_save(&param) == CRUX_CONFIG_OK ? 0 : 1;
}
