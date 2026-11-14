/*
 * ADR-0004 T3. The product's execution shell: it owns the start order of the management services
 * and calls the domain (../../domain). It includes public <crux/...> headers only. What the start
 * order still needs from headers that do not exist yet is listed at each step as PENDING, with the
 * phase 1a header that will carry it, and is added when that header merges (see the README, "What
 * is missing"). Test only: the entropy is test-only.
 */
#include "../../domain/product_policy.h"
#include "crux_tf_psa_threading.h"

#include <crux/access.h>
#include <crux/credential_store.h>
#include <crux/file_zephyr.h>
#include <crux/security_event.h>
#include <crux/time.h>

/* The store's start is public with phase 1a (<crux/credential_store_start.h>, PR 419). Until that
 * header is on main this file builds without it, and the step below stays PENDING. */
#if __has_include(<crux/credential_store_start.h>)
#include <crux/credential_store_start.h>
#define CONSUMER_HAS_CREDENTIAL_START 1
#else
#define CONSUMER_HAS_CREDENTIAL_START 0
#endif

#include <ff.h>
#include <zephyr/fs/fs.h>
#include <zephyr/ztest.h>

enum { ROOT_SLOT_A = 1, ROOT_SLOT_B = 2 };
#define MOUNT_POINT "/SD:"
#define DISK_NAME "SD:"
#define PATH_SLOT_A MOUNT_POINT "/secure-a"
#define PATH_SLOT_B MOUNT_POINT "/secure-b"

static FATFS fat;
static struct fs_mount_t mount = {
    .type = FS_FATFS,
    .mnt_point = MOUNT_POINT,
    .fs_data = &fat,
    .flags = FS_MOUNT_FLAG_NO_FORMAT,
};
static const crux_access_session_t never_valid = {0};

static bool directory_ready(const char *path)
{
    int result = fs_mkdir(path);
    return result == 0 || result == -EEXIST;
}

/* Step 2 of the start order: the File roots, through the public composition interface
 * <crux/file_zephyr.h>. */
static bool medium_ready(void)
{
    if (fs_mount(&mount) != 0) {
        if (fs_mkfs(FS_FATFS, (uintptr_t)DISK_NAME, NULL, 0) != 0 || fs_mount(&mount) != 0) {
            return false;
        }
    }
    return directory_ready(PATH_SLOT_A) && directory_ready(PATH_SLOT_B) &&
           crux_file_zephyr_bind_root(ROOT_SLOT_A, PATH_SLOT_A) == CRUX_FILE_OK &&
           crux_file_zephyr_bind_root(ROOT_SLOT_B, PATH_SLOT_B) == CRUX_FILE_OK;
}

static void *start_services(void)
{
    /* Step 1. */
    zassert_equal(crux_security_event_init(NULL, 0), CRUX_OK);
    zassert_equal(crux_realtime_init(), CRUX_OK);
    zassert_true(medium_ready());
    /* Step 3. PENDING until <crux/credential_store_start.h> is on main. */
#if CONSUMER_HAS_CREDENTIAL_START
    crux_credential_result_t store = crux_credential_start(ROOT_SLOT_A, ROOT_SLOT_B);
    zassert_true(store == CRUX_CREDENTIAL_OK || store == CRUX_CREDENTIAL_ERR_UNUSABLE);
#endif
    /* Step 4. Without the store started, Access answers NOT_READY and stays so: it fails closed. */
    crux_access_result_t access = crux_access_init(product_policy());
    zassert_true(access == CRUX_ACCESS_OK || access == CRUX_ACCESS_ERR_NOT_READY);
    /* Steps 5 and 6, PENDING: the Configuration, status, network settings, file and reboot services
     * have public headers but no usage target yet (crux::config_service and the others, phase 1a).
     */
    zassert_equal(crux_security_event_start(), CRUX_OK);
    /* Steps 7 to 10, PENDING: the first account, the TLS certificate, the web session and
     * management lifecycle and crux_web_start() need the phase 1a headers (the TLS certificate, the
     * apply port, the web lifecycle and web_zephyr). */
    return NULL;
}

ZTEST_SUITE(consumer_composition, NULL, start_services, NULL, NULL, NULL);

ZTEST(consumer_composition,
      test_01_access_is_linked_from_the_module_and_refuses_a_session_that_never_was)
{
    zassert_equal(crux_access_check(never_valid, PRODUCT_PERMISSION_DEMO),
                  CRUX_ACCESS_ERR_SESSION_INVALID);
}

ZTEST(consumer_composition, test_02_the_store_state_is_readable_from_its_public_header)
{
    crux_credential_store_info_t info;
    crux_status_t status = crux_credential_store_get_info(&info);
#if CONSUMER_HAS_CREDENTIAL_START
    /* Started on a fresh disk: nothing is stored yet. */
    zassert_equal(status, CRUX_OK);
    zassert_equal(info.state, CRUX_CREDENTIAL_STATE_EMPTY);
#else
    zassert_equal(status, CRUX_ERR_NOT_READY);
#endif
}
