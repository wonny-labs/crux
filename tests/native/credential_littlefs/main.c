#include "conformance.h"
#include "credential_test.h"
#include <crux/file_zephyr.h>
#include <zephyr/fs/fs.h>
#include <zephyr/fs/littlefs.h>
#include <zephyr/ztest.h>

/* The store's contract on its two File roots of one LittleFS volume over a RAM disk. This is not a
 * card and shows no power loss, and the protection is the test-only fake. */
FS_LITTLEFS_DECLARE_DEFAULT_CONFIG(storage);
static struct fs_mount_t mount = {
    .type = FS_LITTLEFS,
    .mnt_point = "/lfs",
    .fs_data = &storage,
    .storage_dev = (void *)"SD",
    .flags = FS_MOUNT_FLAG_USE_DISK_ACCESS | FS_MOUNT_FLAG_NO_FORMAT,
};

void credential_medium_blank(void)
{
    test_slot_remove(TEST_SLOT_A);
    test_slot_remove(TEST_SLOT_B);
}

static void *setup(void)
{
    zassert_ok(fs_mkfs(FS_LITTLEFS, (uintptr_t) "SD", &storage, FS_MOUNT_FLAG_USE_DISK_ACCESS));
    zassert_ok(fs_mount(&mount));
    zassert_ok(fs_mkdir("/lfs/secure-a"));
    zassert_ok(fs_mkdir("/lfs/secure-b"));
    zassert_equal(crux_file_zephyr_bind_root(TEST_ROOT_A, "/lfs/secure-a"), CRUX_FILE_OK);
    zassert_equal(crux_file_zephyr_bind_root(TEST_ROOT_B, "/lfs/secure-b"), CRUX_FILE_OK);
    return NULL;
}

ZTEST(credential_littlefs, test_conformance_on_littlefs)
{
    credential_conformance_run();
    zassert_equal(credential_test_failures, 0, "%u of %u checks failed", credential_test_failures,
                  credential_test_checks);
}

/* Both slots reach full size and keep it across a remount, and the erase removes both. */
ZTEST(credential_littlefs, test_saves_survive_a_remount_and_erase_removes_both_slots)
{
    static const uint8_t first[] = "first value";
    static const uint8_t second[] = "second value, a little longer";
    crux_file_info_t info;

    test_fresh_empty();
    zassert_equal(crux_credential_write(CRUX_CREDENTIAL_RECORD_ACCOUNTS, first, sizeof(first)),
                  CRUX_CREDENTIAL_OK);
    zassert_equal(crux_credential_write(CRUX_CREDENTIAL_RECORD_ACCOUNTS, second, sizeof(second)),
                  CRUX_CREDENTIAL_OK);
    zassert_equal(crux_credential_key_ensure(CRUX_CREDENTIAL_RECORD_SSH_HOST_KEY,
                                             CRUX_CREDENTIAL_KEY_ED25519),
                  CRUX_CREDENTIAL_OK);

    /* The same in-process RAM disk, so this is not persistence evidence. */
    zassert_ok(fs_unmount(&mount));
    zassert_ok(fs_mount(&mount));
    zassert_equal(test_boot(), CRUX_CREDENTIAL_OK);
    zassert_equal(crux_credential_state(), CRUX_CREDENTIAL_STATE_VALID);
    test_expect_record(CRUX_CREDENTIAL_RECORD_ACCOUNTS, second, sizeof(second));
    zassert_equal(credential_test_failures, 0);

    for (crux_file_root_t root = TEST_ROOT_A; root <= TEST_ROOT_B; ++root) {
        zassert_equal(crux_file_stat(root, TEST_SLOT_NAME, &info), CRUX_FILE_OK);
        zassert_equal(info.size, CRUX_CREDENTIAL_SLOT_BYTES);
    }
    zassert_equal(crux_credential_erase(), CRUX_CREDENTIAL_OK);
    zassert_equal(crux_file_stat(TEST_ROOT_A, TEST_SLOT_NAME, &info), CRUX_FILE_ERR_NOT_FOUND);
    zassert_equal(crux_file_stat(TEST_ROOT_B, TEST_SLOT_NAME, &info), CRUX_FILE_ERR_NOT_FOUND);
}

/*
 * An application root with a byte limit on the same volume
 * (docs/file-contract.md#root-byte-limits): once its files reach the limit, a write there gets
 * CRUX_FILE_ERR_NO_SPACE, and the store still saves a record and makes a key in its own roots.
 */
ZTEST(credential_littlefs, test_a_full_limited_root_leaves_room_for_credential_saves)
{
    static const uint8_t chunk[512] = {[0 ... 511] = 0x61};
    static const uint8_t account[] = "saved next to a full root";
    const crux_file_root_t app = 3;
    crux_file_t *file = NULL;
    crux_file_result_t rc = CRUX_FILE_OK;
    size_t count = 0;
    unsigned chunks = 0;

    zassert_ok(fs_mkdir("/lfs/app"));
    zassert_equal(crux_file_zephyr_bind_root_limited(app, "/lfs/app", 32 * sizeof(chunk)),
                  CRUX_FILE_OK);
    zassert_equal(crux_file_open_at(app, "data", CRUX_FILE_CREATE_REPLACE, &file), CRUX_FILE_OK);
    for (; chunks < 2048 && rc == CRUX_FILE_OK; chunks++) {
        rc = crux_file_write(file, chunk, sizeof(chunk), &count);
        if (rc == CRUX_FILE_OK) {
            rc = crux_file_sync(file);
        }
    }
    zassert_equal(rc, CRUX_FILE_ERR_NO_SPACE, "the limit gave %d", rc);
    zassert_equal(count, 0);
    zassert_equal(chunks, 33, "32 blocks fit and the 33rd write is refused");
    zassert_equal(crux_file_close(&file), CRUX_FILE_OK);

    test_fresh_empty();
    zassert_equal(crux_credential_write(CRUX_CREDENTIAL_RECORD_ACCOUNTS, account, sizeof(account)),
                  CRUX_CREDENTIAL_OK);
    zassert_equal(crux_credential_key_ensure(CRUX_CREDENTIAL_RECORD_SSH_HOST_KEY,
                                             CRUX_CREDENTIAL_KEY_ED25519),
                  CRUX_CREDENTIAL_OK);
    test_expect_record(CRUX_CREDENTIAL_RECORD_ACCOUNTS, account, sizeof(account));
    zassert_equal(credential_test_failures, 0);

    /* Still full: the store's saves took nothing from the application root. */
    zassert_equal(crux_file_open_at(app, "more", CRUX_FILE_CREATE_REPLACE, &file),
                  CRUX_FILE_ERR_NO_SPACE);
    zassert_equal(crux_file_remove_at(app, "data"), CRUX_FILE_OK);
}

ZTEST_SUITE(credential_littlefs, NULL, setup, NULL, NULL, NULL);
