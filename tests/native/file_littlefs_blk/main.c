/* SPDX-License-Identifier: Apache-2.0 */
/*
 * The File provider on LittleFS over a block device (CONFIG_CRUX_FILE_LITTLEFS_BLK_DEV), with
 * Configuration saving on the same volume through the Settings File backend. The disk is a RAM
 * disk: not a card, and not power-loss evidence. The cases are the File contract and the roots,
 * stat, size, rename and listing additions, plus the mount rule: a failed mount never formats.
 */
#include "configuration_settings.h"
#include "conformance.h"
#include "file_port.h"
#include <crux/configuration.h>
#include <crux/file.h>
#include <crux/file_zephyr.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <zephyr/fs/fs.h>
#include <zephyr/fs/littlefs.h>
#include <zephyr/storage/disk_access.h>
#include <zephyr/ztest.h>

#define DISK "SD"
#define MOUNT_POINT "/lfs"
#define ROOT_A MOUNT_POINT "/a"
#define ROOT_B MOUNT_POINT "/b"
#define SECTOR 512
#define SECTORS 2048

FS_LITTLEFS_DECLARE_DEFAULT_CONFIG(storage);

/* The mount of a product's recipe: a mount never formats. */
static struct fs_mount_t mount = {
    .type = FS_LITTLEFS,
    .mnt_point = MOUNT_POINT,
    .fs_data = &storage,
    .storage_dev = (void *)DISK,
    .flags = FS_MOUNT_FLAG_USE_DISK_ACCESS | FS_MOUNT_FLAG_NO_FORMAT,
};

static uint8_t kept_disk[SECTORS * SECTOR];
static uint8_t seen_disk[SECTORS * SECTOR];

/* A write that the disk refuses, to make a File write fail inside LittleFS. */
static bool fail_disk_writes;
int __real_disk_access_write(const char *disk, const uint8_t *data, uint32_t sector,
                             uint32_t count);
int __wrap_disk_access_write(const char *disk, const uint8_t *data, uint32_t sector, uint32_t count)
{
    return fail_disk_writes ? -EIO : __real_disk_access_write(disk, data, sector, count);
}

static void read_disk(uint8_t *to)
{
    zassert_ok(disk_access_read(DISK, to, 0, SECTORS));
}

static void *setup(void)
{
    uint32_t sectors = 0;

    zassert_ok(disk_access_init(DISK));
    zassert_ok(disk_access_ioctl(DISK, DISK_IOCTL_GET_SECTOR_COUNT, &sectors));
    zassert_equal(sectors, SECTORS);

    /* A blank disk: the mount fails and writes nothing. */
    read_disk(kept_disk);
    zassert_true(fs_mount(&mount) < 0, "an unformatted disk must not mount");
    read_disk(seen_disk);
    zassert_mem_equal(seen_disk, kept_disk, sizeof(seen_disk), "a failed mount must not format");

    /* Provisioning is an explicit step, never the path of a failed mount. */
    zassert_ok(fs_mkfs(FS_LITTLEFS, (uintptr_t)DISK, &storage, FS_MOUNT_FLAG_USE_DISK_ACCESS));
    zassert_ok(fs_mount(&mount));
    zassert_ok(fs_mkdir(ROOT_A));
    zassert_ok(fs_mkdir(ROOT_A "/inner"));
    zassert_ok(fs_mkdir(ROOT_B));
    zassert_ok(fs_mkdir(MOUNT_POINT "/free"));
    zassert_ok(fs_mkdir(MOUNT_POINT "/a2"));
    zassert_ok(fs_mkdir(MOUNT_POINT "/settings"));
    zassert_equal(crux_file_zephyr_bind(ROOT_A), CRUX_FILE_OK, "the original bind is root 0");
    zassert_equal(crux_file_zephyr_bind_root(1, ROOT_B), CRUX_FILE_OK);
    zassert_equal(crux_config_zephyr_init(), CRUX_CONFIG_OK);
    return NULL;
}

static void write_file(const char *name, const char *text)
{
    crux_file_t *file = NULL;
    size_t count = 0;

    zassert_equal(crux_file_open(name, CRUX_FILE_CREATE_REPLACE, &file), CRUX_FILE_OK, "%s", name);
    zassert_equal(crux_file_write(file, text, strlen(text), &count), CRUX_FILE_OK);
    zassert_equal(count, strlen(text));
    zassert_equal(crux_file_sync(file), CRUX_FILE_OK);
    zassert_equal(crux_file_close(&file), CRUX_FILE_OK);
}

static void expect_file(const char *name, const char *text)
{
    crux_file_t *file = NULL;
    size_t count = 0;
    char value[32] = {0};

    zassert_true(strlen(text) < sizeof(value));
    zassert_equal(crux_file_open(name, CRUX_FILE_READ, &file), CRUX_FILE_OK, "%s", name);
    zassert_equal(crux_file_read(file, value, sizeof(value), &count), CRUX_FILE_OK);
    zassert_equal(count, strlen(text));
    zassert_mem_equal(value, text, strlen(text));
    zassert_equal(crux_file_close(&file), CRUX_FILE_OK);
}

static void remount(void)
{
    zassert_ok(fs_unmount(&mount));
    zassert_ok(fs_mount(&mount));
}

/* The shared cases of the File additions, as on the Linux provider, the fake and FatFs. */
static void add_directory(crux_file_root_t root, const char *name)
{
    char path[128];

    zassert_true(snprintf(path, sizeof(path), "%s/%s", root == 0 ? ROOT_A : ROOT_B, name) <
                 (int)sizeof(path));
    zassert_ok(fs_mkdir(path));
}

static void raw_file(crux_file_root_t root, const char *leaf)
{
    char path[160];
    struct fs_file_t file;

    fs_file_t_init(&file);
    zassert_true(snprintf(path, sizeof(path), "%s/%s", root == 0 ? ROOT_A : ROOT_B, leaf) <
                 (int)sizeof(path));
    zassert_ok(fs_open(&file, path, FS_O_CREATE | FS_O_WRITE), "%s", leaf);
    zassert_ok(fs_close(&file));
}

static void add_foreign_files(crux_file_root_t root)
{
    char name[71];

    raw_file(root, "with space");
    raw_file(root, "tilde~name");
    /* Longer than a File name. A directory entry of 64 characters is cut to 64, so neither of these
     * can be listed as a File name. */
    memset(name, 'l', 64);
    name[64] = '\0';
    raw_file(root, name);
    memset(name, 'm', 70);
    name[70] = '\0';
    raw_file(root, name);
}

static const crux_file_conformance_env_t env = {
    .add_directory = add_directory,
    .add_foreign_files = add_foreign_files,
    .bind_root = crux_file_zephyr_bind_root,
    .path_0 = ROOT_A,
    .path_0_parent = MOUNT_POINT,
    .path_0_child = ROOT_A "/inner",
    .path_free = MOUNT_POINT "/free",
    .path_0_prefix = MOUNT_POINT "/a2",
};

/* One case, because the conformance sequence leaves entries that its later steps expect. */
ZTEST(file_littlefs_blk, test_conformance_of_the_additions)
{
    crux_file_conformance_roots(&env);
    crux_file_conformance_stat(&env);
    crux_file_conformance_size();
    crux_file_conformance_rename(&env);
    crux_file_conformance_listing(&env);
    crux_file_conformance_binding(&env);
}

ZTEST(file_littlefs_blk, test_names_are_stored_as_they_are)
{
    struct fs_dirent entry;

    write_file("Mixed.Case-1_", "data");
    zassert_ok(fs_stat(ROOT_A "/Mixed.Case-1_", &entry));
    zassert_equal(entry.type, FS_DIR_ENTRY_FILE);
    zassert_equal(entry.size, 4);
}

ZTEST(file_littlefs_blk, test_maximum_length_and_similar_names_do_not_alias)
{
    const char *names[] = {"item", "ITEM", "item."};
    const char *values[] = {"a", "b", "c"};
    char longest[64];

    memset(longest, 'a', sizeof(longest) - 1);
    longest[63] = '\0';
    write_file(longest, "ok");
    write_file(longest + 1, "zz");
    expect_file(longest, "ok");
    expect_file(longest + 1, "zz");
    for (size_t i = 0; i < ARRAY_SIZE(names); i++) {
        write_file(names[i], values[i]);
    }
    for (size_t i = 0; i < ARRAY_SIZE(names); i++) {
        expect_file(names[i], values[i]);
    }
}

/* The remount reuses the same in-process RAM disk, so this is not persistence evidence. */
ZTEST(file_littlefs_blk, test_create_replace_truncates_and_survives_a_remount)
{
    write_file("replace", "old-value");
    write_file("replace", "new");
    remount();
    expect_file("replace", "new");
}

ZTEST(file_littlefs_blk, test_close_keeps_unsynced_data_across_a_remount)
{
    crux_file_t *file = NULL;
    size_t count = 0;

    zassert_equal(crux_file_open("closed", CRUX_FILE_CREATE_REPLACE, &file), CRUX_FILE_OK);
    zassert_equal(crux_file_write(file, "kept", 4, &count), CRUX_FILE_OK);
    zassert_equal(crux_file_close(&file), CRUX_FILE_OK);
    remount();
    expect_file("closed", "kept");
}

ZTEST(file_littlefs_blk, test_a_rename_survives_a_remount_and_keeps_a_destination)
{
    crux_file_info_t info;

    write_file("source", "data");
    write_file("target", "kept");
    zassert_equal(crux_file_rename(0, "source", "target"), CRUX_FILE_ERR_EXISTS,
                  "LittleFS itself would replace the destination");
    expect_file("target", "kept");
    zassert_equal(crux_file_rename(0, "source", "moved"), CRUX_FILE_OK);
    remount();
    zassert_equal(crux_file_stat(0, "source", &info), CRUX_FILE_ERR_NOT_FOUND);
    expect_file("moved", "data");
}

ZTEST(file_littlefs_blk, test_read_write_seek_and_eof_bounds)
{
    crux_file_t *file = NULL;
    size_t count = 0;
    char value[6] = {0};

    write_file("seek", "abcdef");
    zassert_equal(crux_file_open("seek", CRUX_FILE_READ_WRITE, &file), CRUX_FILE_OK);
    zassert_equal(crux_file_seek(file, 2), CRUX_FILE_OK);
    zassert_equal(crux_file_write(file, "XY", 2, &count), CRUX_FILE_OK);
    zassert_equal(count, 2);
    zassert_equal(crux_file_seek(file, 0), CRUX_FILE_OK);
    zassert_equal(crux_file_read(file, value, sizeof(value), &count), CRUX_FILE_OK);
    zassert_equal(count, sizeof(value));
    zassert_mem_equal(value, "abXYef", sizeof(value));
    zassert_equal(crux_file_seek(file, 6), CRUX_FILE_OK, "EOF itself is a valid offset");
    zassert_equal(crux_file_read(file, value, sizeof(value), &count), CRUX_FILE_OK);
    zassert_equal(count, 0);
    zassert_equal(crux_file_seek(file, 7), CRUX_FILE_ERR_OUT_OF_RANGE);
    zassert_equal(crux_file_seek(file, (uint64_t)INT32_MAX + 1), CRUX_FILE_ERR_OUT_OF_RANGE);
    zassert_equal(crux_file_seek(file, UINT64_MAX), CRUX_FILE_ERR_OUT_OF_RANGE);
    zassert_equal(crux_file_close(&file), CRUX_FILE_OK);
}

ZTEST(file_littlefs_blk, test_access_mapping_handle_lifetime_and_remove)
{
    crux_file_t *file = NULL;
    size_t count = 0;

    zassert_equal(crux_file_open("missing", CRUX_FILE_READ, &file), CRUX_FILE_ERR_NOT_FOUND);
    zassert_is_null(file);
    zassert_equal(crux_file_open("missing", CRUX_FILE_READ_WRITE, &file), CRUX_FILE_ERR_NOT_FOUND);
    zassert_equal(crux_file_remove("missing"), CRUX_FILE_ERR_NOT_FOUND);
    write_file("access", "x");
    zassert_equal(crux_file_open("access", CRUX_FILE_READ, &file), CRUX_FILE_OK);
    zassert_equal(crux_file_write(file, "y", 1, &count), CRUX_FILE_ERR_ACCESS);
    zassert_equal(count, 0);
    zassert_equal(crux_file_remove("access"), CRUX_FILE_ERR_INVALID_STATE);
    zassert_equal(crux_file_close(&file), CRUX_FILE_OK);
    zassert_is_null(file);
    zassert_equal(crux_file_remove("access"), CRUX_FILE_OK);
    zassert_equal(crux_file_open("access", CRUX_FILE_READ, &file), CRUX_FILE_ERR_NOT_FOUND);
    zassert_is_null(file);
}

/* The pools follow the Kconfig values, so the scenario with a pool of 8 opens 8 handles below. */
BUILD_ASSERT(CRUX_FILE_POOL_SIZE == CONFIG_CRUX_FILE_POOL_SIZE);
BUILD_ASSERT(CRUX_FILE_DIR_POOL_SIZE == CONFIG_CRUX_FILE_DIR_POOL_SIZE);

static void open_the_whole_pool(crux_file_t *files[CRUX_FILE_POOL_SIZE])
{
    BUILD_ASSERT(CRUX_FILE_POOL_SIZE <= 10, "pool names are pool0 to pool9");
    for (size_t i = 0; i < CRUX_FILE_POOL_SIZE; ++i) {
        char name[] = "pool0";

        name[4] = (char)('0' + i);
        zassert_equal(crux_file_open(name, CRUX_FILE_CREATE_REPLACE, &files[i]), CRUX_FILE_OK, "%s",
                      name);
    }
}

static void close_the_pool(crux_file_t *files[CRUX_FILE_POOL_SIZE])
{
    for (size_t i = 0; i < CRUX_FILE_POOL_SIZE; ++i) {
        if (files[i]) {
            zassert_equal(crux_file_close(&files[i]), CRUX_FILE_OK);
        }
    }
}

ZTEST(file_littlefs_blk, test_file_handle_pool_limit_and_reuse)
{
    crux_file_t *files[CRUX_FILE_POOL_SIZE] = {0};
    crux_file_t *extra = NULL;

    open_the_whole_pool(files);
    zassert_equal(crux_file_open("extra", CRUX_FILE_CREATE_REPLACE, &extra),
                  CRUX_FILE_ERR_NO_RESOURCES);
    zassert_is_null(extra);
    zassert_equal(crux_file_close(&files[1]), CRUX_FILE_OK);
    zassert_equal(crux_file_open("reuse", CRUX_FILE_CREATE_REPLACE, &extra), CRUX_FILE_OK);
    zassert_equal(crux_file_close(&extra), CRUX_FILE_OK);
    close_the_pool(files);
}

ZTEST(file_littlefs_blk, test_unmounted_volume_is_not_ready)
{
    crux_file_t *file = NULL;
    crux_file_dir_t *dir = NULL;
    crux_file_info_t info;

    zassert_ok(fs_unmount(&mount));
    zassert_equal(crux_file_open("offline", CRUX_FILE_READ, &file), CRUX_FILE_ERR_NOT_READY);
    zassert_is_null(file);
    zassert_equal(crux_file_stat(1, "x", &info), CRUX_FILE_ERR_NOT_READY);
    zassert_equal(crux_file_rename(1, "x", "y"), CRUX_FILE_ERR_NOT_READY);
    zassert_equal(crux_file_dir_open(1, &dir), CRUX_FILE_ERR_NOT_READY);
    zassert_is_null(dir);
    zassert_ok(fs_mount(&mount));
}

ZTEST(file_littlefs_blk, test_storage_full_is_observable_and_space_is_reclaimed)
{
    static const uint8_t chunk[SECTOR] = {[0 ... SECTOR - 1] = 0x5a};
    crux_file_t *file = NULL;
    crux_file_result_t rc = CRUX_FILE_OK;
    struct fs_statvfs before, after;
    size_t count = 0;

    write_file("sentinel", "kept");
    zassert_equal(crux_file_open("filler", CRUX_FILE_CREATE_REPLACE, &file), CRUX_FILE_OK);
    /* LittleFS commits a file's blocks at a sync, so the filler syncs after each chunk. */
    for (unsigned i = 0; i < 2 * SECTORS && rc == CRUX_FILE_OK; i++) {
        rc = crux_file_write(file, chunk, sizeof(chunk), &count);
        if (rc == CRUX_FILE_OK) {
            rc = crux_file_sync(file);
        }
    }
    zassert_equal(rc, CRUX_FILE_ERR_NO_SPACE, "a 2 MiB workload must exhaust a 1 MiB disk: %d", rc);
    zassert_equal(crux_file_close(&file), CRUX_FILE_ERR_NO_SPACE,
                  "a handle that ran out of space does not close with success");
    zassert_is_null(file);

    /* Empty files need directory blocks, so creating them ends with no space and not another
     * error. */
    crux_file_result_t last = CRUX_FILE_OK;
    unsigned created = 0;
    char name[48];

    for (; created < 400 && last == CRUX_FILE_OK; created++) {
        snprintf(name, sizeof(name), "%040u", created);
        last = crux_file_open(name, CRUX_FILE_CREATE_REPLACE, &file);
        if (last == CRUX_FILE_OK) {
            zassert_equal(crux_file_close(&file), CRUX_FILE_OK);
        }
    }
    zassert_equal(last, CRUX_FILE_ERR_NO_SPACE, "creation gave %d after %u files", last, created);
    for (unsigned i = 0; i + 1 < created; i++) {
        snprintf(name, sizeof(name), "%040u", i);
        zassert_equal(crux_file_remove(name), CRUX_FILE_OK, "%s", name);
    }

    zassert_ok(fs_statvfs(MOUNT_POINT, &before));
    zassert_equal(crux_file_remove("filler"), CRUX_FILE_OK);
    zassert_ok(fs_statvfs(MOUNT_POINT, &after));
    zassert_true(after.f_bfree > before.f_bfree, "removal must free blocks (%lu then %lu)",
                 (unsigned long)before.f_bfree, (unsigned long)after.f_bfree);
    write_file("fresh", "new");
    remount();
    expect_file("sentinel", "kept");
    expect_file("fresh", "new");
}

/*
 * LittleFS closes a file whose write failed without committing it, and reports success. The
 * provider therefore keeps the first error of a writable handle: every later call on the handle
 * returns it, close included, so that no sync or close acknowledges lost data.
 */
ZTEST(file_littlefs_blk, test_a_failed_write_is_reported_until_close)
{
    static uint8_t big[8 * SECTOR];
    crux_file_t *file = NULL;
    uint64_t size = 0;
    size_t count = 0;
    char value[2];

    memset(big, 0x33, sizeof(big));
    write_file("lost", "before");
    zassert_equal(crux_file_open("lost", CRUX_FILE_READ_WRITE, &file), CRUX_FILE_OK);
    fail_disk_writes = true;
    zassert_equal(crux_file_write(file, big, sizeof(big), &count), CRUX_FILE_ERR_IO);
    zassert_equal(count, 0);
    fail_disk_writes = false;
    zassert_equal(crux_file_write(file, "x", 1, &count), CRUX_FILE_ERR_IO);
    zassert_equal(count, 0);
    zassert_equal(crux_file_read(file, value, sizeof(value), &count), CRUX_FILE_ERR_IO);
    zassert_equal(crux_file_seek(file, 0), CRUX_FILE_ERR_IO);
    zassert_equal(crux_file_size(file, &size), CRUX_FILE_ERR_IO);
    zassert_equal(crux_file_sync(file), CRUX_FILE_ERR_IO);
    zassert_equal(crux_file_close(&file), CRUX_FILE_ERR_IO);
    zassert_is_null(file);
    remount();
    expect_file("lost", "before");

    /* The error belongs to that handle: the next one starts clean. */
    write_file("lost", "after");
    expect_file("lost", "after");
}

/* A refused seek is not a failure of the handle. */
ZTEST(file_littlefs_blk, test_a_refused_seek_leaves_a_writable_handle_usable)
{
    crux_file_t *file = NULL;
    size_t count = 0;

    write_file("usable", "ab");
    zassert_equal(crux_file_open("usable", CRUX_FILE_READ_WRITE, &file), CRUX_FILE_OK);
    zassert_equal(crux_file_seek(file, 3), CRUX_FILE_ERR_OUT_OF_RANGE);
    zassert_equal(crux_file_seek(file, 2), CRUX_FILE_OK);
    zassert_equal(crux_file_write(file, "cd", 2, &count), CRUX_FILE_OK);
    zassert_equal(crux_file_sync(file), CRUX_FILE_OK);
    zassert_equal(crux_file_close(&file), CRUX_FILE_OK);
    expect_file("usable", "abcd");
}

/* Configuration saves through the Settings File backend on the volume that File uses. */
ZTEST(file_littlefs_blk, test_configuration_saves_on_the_same_volume)
{
    static const crux_config_spec_t spec = {
        .key = "speed",
        .schema_version = 1,
        .default_value = {.type = CRUX_CONFIG_U32, .data.u32 = 11},
    };
    crux_file_t *files[CRUX_FILE_POOL_SIZE] = {0};
    crux_config_param_t param = {0};
    crux_config_value_t value = {.type = CRUX_CONFIG_U32, .data.u32 = 42};
    struct fs_dirent entry;

    zassert_equal(crux_config_init(&param, &spec), CRUX_CONFIG_OK);
    write_file("cfg", "a File of the same name");
    /* The File pool is full: the backend's two files come out of the file system's own budget. */
    open_the_whole_pool(files);
    zassert_equal(crux_config_update(&param, &value), CRUX_CONFIG_OK);
    zassert_equal(crux_config_save(&param), CRUX_CONFIG_OK);
    close_the_pool(files);
    remount();
    value.data.u32 = 0;
    zassert_equal(crux_config_update(&param, &value), CRUX_CONFIG_OK);
    zassert_equal(crux_config_load(&param), CRUX_CONFIG_OK);
    zassert_equal(crux_config_read(&param, &value), CRUX_CONFIG_OK);
    zassert_equal(value.data.u32, 42);
    expect_file("cfg", "a File of the same name");
    zassert_ok(fs_stat(CONFIG_SETTINGS_FILE_PATH, &entry));
}

/*
 * The settings half of a product's factory reset (docs/management-in-a-product.md#factory-reset):
 * the temporary first, then the settings file. A load then finds nothing and keeps the default, and
 * a later save works.
 */
ZTEST(file_littlefs_blk, test_removing_the_settings_files_gives_the_defaults_again)
{
    static const crux_config_spec_t spec = {
        .key = "mode",
        .schema_version = 1,
        .default_value = {.type = CRUX_CONFIG_U32, .data.u32 = 7},
    };
    crux_config_param_t param = {0};
    crux_config_value_t value = {.type = CRUX_CONFIG_U32, .data.u32 = 8};
    struct fs_file_t file;

    zassert_equal(crux_config_init(&param, &spec), CRUX_CONFIG_OK);
    zassert_equal(crux_config_update(&param, &value), CRUX_CONFIG_OK);
    zassert_equal(crux_config_save(&param), CRUX_CONFIG_OK);
    /* A temporary left by an interrupted compaction. */
    fs_file_t_init(&file);
    zassert_ok(fs_open(&file, CONFIG_SETTINGS_FILE_PATH ".cmp", FS_O_CREATE | FS_O_WRITE));
    zassert_ok(fs_close(&file));

    zassert_ok(fs_unlink(CONFIG_SETTINGS_FILE_PATH ".cmp"));
    zassert_ok(fs_unlink(CONFIG_SETTINGS_FILE_PATH));
    zassert_equal(crux_config_load(&param), CRUX_CONFIG_DEFAULT_MISSING);
    zassert_equal(crux_config_save(&param), CRUX_CONFIG_OK);
    zassert_equal(crux_config_load(&param), CRUX_CONFIG_OK);
}

ZTEST(file_littlefs_blk, test_corrupted_media_is_not_formatted_and_recovers_when_restored)
{
    static const uint8_t zeros[2 * SECTOR];
    crux_file_t *file = NULL;

    write_file("survivor", "kept");
    zassert_ok(fs_unmount(&mount));
    read_disk(kept_disk);
    /* Blocks 0 and 1 hold the superblock pair. */
    zassert_ok(disk_access_write(DISK, zeros, 0, 2));
    read_disk(seen_disk);

    zassert_true(fs_mount(&mount) < 0, "a volume without a superblock must not mount");
    static uint8_t after[SECTORS * SECTOR];
    read_disk(after);
    zassert_mem_equal(after, seen_disk, sizeof(after), "a failed mount must not format");
    zassert_equal(crux_file_open("survivor", CRUX_FILE_READ, &file), CRUX_FILE_ERR_NOT_READY);
    zassert_is_null(file);
    zassert_equal(crux_file_remove("survivor"), CRUX_FILE_ERR_NOT_READY);

    /* The control: without the flag the same mount formats the disk and the files are gone. */
    mount.flags = FS_MOUNT_FLAG_USE_DISK_ACCESS;
    int rc = fs_mount(&mount);
    mount.flags = FS_MOUNT_FLAG_USE_DISK_ACCESS | FS_MOUNT_FLAG_NO_FORMAT;
    zassert_ok(rc, "without FS_MOUNT_FLAG_NO_FORMAT the mount formats");
    read_disk(after);
    zassert_true(memcmp(after, seen_disk, sizeof(after)) != 0, "the control did not write");
    struct fs_dirent entry;
    zassert_equal(fs_stat(ROOT_A "/survivor", &entry), -ENOENT);
    zassert_ok(fs_unmount(&mount));

    zassert_ok(disk_access_write(DISK, kept_disk, 0, SECTORS));
    zassert_ok(fs_mount(&mount));
    expect_file("survivor", "kept");
}

/* Leave roots 0 and 1 without files and the volume mounted, whatever the case did. */
static void cleanup(void *fixture)
{
    static const char *const directories[] = {ROOT_A, ROOT_B};

    ARG_UNUSED(fixture);
    fail_disk_writes = false;
    (void)fs_mount(&mount); /* fails harmlessly when the case left it mounted */
    for (size_t d = 0; d < ARRAY_SIZE(directories); d++) {
        for (unsigned guard = 0; guard < 1024; guard++) {
            struct fs_dir_t dir;
            struct fs_dirent entry = {0};
            char path[160];
            int rc;

            fs_dir_t_init(&dir);
            if (fs_opendir(&dir, directories[d]) != 0) {
                break;
            }
            do {
                rc = fs_readdir(&dir, &entry);
            } while (rc == 0 && entry.name[0] != '\0' && entry.type != FS_DIR_ENTRY_FILE);
            (void)fs_closedir(&dir);
            if (rc != 0 || entry.name[0] == '\0') {
                break;
            }
            snprintf(path, sizeof(path), "%s/%s", directories[d], entry.name);
            if (fs_unlink(path) != 0) {
                break; /* a foreign name that the directory entry cut short */
            }
        }
    }
}

ZTEST_SUITE(file_littlefs_blk, NULL, setup, NULL, cleanup, NULL);
