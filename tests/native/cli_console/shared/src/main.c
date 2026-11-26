/*
 * The serial console and Crux Logging on one emulated UART (CONFIG_CRUX_CLI_CONSOLE_UART_SHARED,
 * Experimental), and the progress hook of the Crux service threads. Text written before the console
 * starts goes out directly; at a prompt a log line clears the input line and the line is redrawn;
 * at a password prompt the typed bytes are never redrawn; a burst reports its drops; the console
 * and the security event drain report progress at least once a second; after a panic log text goes
 * straight out. Test only: the entropy is test-only. Public headers only.
 */
#include <crux/access.h>
#include <crux/cli.h>
#include <crux/cli_zephyr.h>
#include <crux/credential_store.h>
#include <crux/file_zephyr.h>
#include <crux/logging.h>
#include <crux/security_event.h>
#include <crux/service_priority_zephyr.h>
#include <crux/time.h>

#include <ff.h>
#include <string.h>
#include <zephyr/drivers/serial/uart_emul.h>
#include <zephyr/fs/fs.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log_ctrl.h>
#include <zephyr/sys/atomic.h>
#include <zephyr/ztest.h>

enum { ROOT_SLOT_A = 1, ROOT_SLOT_B = 2 };
#define MOUNT_POINT "/SD:"
#define DISK_NAME "SD:"
#define PATH_SLOT_A MOUNT_POINT "/secure-a"
#define PATH_SLOT_B MOUNT_POINT "/secure-b"
#define SETUP_ROLE "administrator"
/* Typed at a password prompt in two parts. Neither part may reach the transmit side. */
#define SECRET_START "shared-secret"
#define SECRET_END "-is-not-shown"
#define CLEAR "\r\x1b[K"

static const char *const admin_permissions[] = {CRUX_ACCESS_PERMISSION_MANAGE};
static const crux_access_role_t roles[] = {
    {SETUP_ROLE, admin_permissions, ARRAY_SIZE(admin_permissions)},
};
static const crux_access_policy_t policy = {roles, ARRAY_SIZE(roles), 15u * 60u, 8u * 3600u, NULL};

static FATFS fat;
static struct fs_mount_t mount = {
    .type = FS_FATFS,
    .mnt_point = MOUNT_POINT,
    .fs_data = &fat,
    .flags = FS_MOUNT_FLAG_NO_FORMAT,
};
static const struct device *const console_uart = DEVICE_DT_GET(DT_NODELABEL(serial_test));

static atomic_t reports[CRUX_SERVICE_THREAD_COUNT];

static void count_progress(crux_service_thread_t thread, void *context)
{
    ARG_UNUSED(context);
    atomic_inc(&reports[thread]);
}

static bool directory_ready(const char *path)
{
    int result = fs_mkdir(path);
    return result == 0 || result == -EEXIST;
}

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

/* What the UART has carried, not yet consumed by an expectation. Log text makes it long. */
static char capture[65536];
static size_t captured;

static void drain(void)
{
    uint8_t chunk[256];
    uint32_t got;
    while ((got = uart_emul_get_tx_data(console_uart, chunk, sizeof(chunk))) > 0u) {
        if (captured + got >= sizeof(capture)) {
            /* Keep the newest half: an expectation looks only forward. */
            size_t keep = sizeof(capture) / 2u;
            memmove(capture, &capture[captured - keep], keep);
            captured = keep;
        }
        memcpy(&capture[captured], chunk, got);
        captured += got;
        capture[captured] = '\0';
        zassert_is_null(strstr(capture, SECRET_START), "a typed secret was written");
        zassert_is_null(strstr(capture, SECRET_END), "a typed secret was written");
    }
}

static void expect(const char *text)
{
    for (int attempt = 0; attempt < 1000; ++attempt) {
        drain();
        char *found = strstr(capture, text);
        if (found != NULL) {
            size_t consumed = (size_t)(found - capture) + strlen(text);
            memmove(capture, &capture[consumed], captured - consumed + 1u);
            captured -= consumed;
            return;
        }
        k_msleep(10);
    }
    zassert_unreachable("the UART did not carry \"%s\"; it carried \"%s\"", text, capture);
}

/* Types bytes as a terminal does, with no line end added. */
static void type(const char *text)
{
    size_t length = strlen(text);
    zassert_equal(uart_emul_put_rx_data(console_uart, (const uint8_t *)text, length), length);
}

/* Lets the console read and echo what was typed, while the capture keeps up. */
static void settle(void)
{
    for (int step = 0; step < 30; ++step) {
        drain();
        k_msleep(10);
    }
}

static void *start_services_and_console(void)
{
    zassert_true(device_is_ready(console_uart));
    /* Before any service starts, so that the first pass of each thread reports. */
    zassert_equal(crux_service_progress_register(count_progress, NULL), CRUX_OK);
    zassert_equal(crux_security_event_init(NULL, 0), CRUX_OK);
    zassert_equal(crux_realtime_init(), CRUX_OK);
    zassert_true(medium_ready());
    crux_credential_result_t store = crux_credential_start(ROOT_SLOT_A, ROOT_SLOT_B);
    zassert_true(store == CRUX_CREDENTIAL_OK || store == CRUX_CREDENTIAL_ERR_UNUSABLE);
    zassert_equal(crux_access_init(&policy), CRUX_ACCESS_OK);
    zassert_equal(crux_security_event_start(), CRUX_OK);
    zassert_equal(crux_cli_init(NULL, NULL, 0u), CRUX_CLI_OK);
    /* Logged before the console's thread exists: it goes straight to the UART, or to the queue if
     * the log thread runs after the console attached. Either way it reaches the UART. */
    zassert_equal(crux_log_write(CRUX_LOG_INFO, "shared", "before the console"), CRUX_OK);
    static const crux_cli_serial_config_t console = {.setup_role = SETUP_ROLE};
    zassert_equal(crux_cli_serial_start(&console), CRUX_CLI_OK);
    return NULL;
}

ZTEST_SUITE(cli_console_shared, NULL, start_services_and_console, NULL, NULL, NULL);

ZTEST(cli_console_shared, test_01_boot_text_and_the_prompt_share_the_uart)
{
    expect("shared: before the console");
    expect("login: ");
}

ZTEST(cli_console_shared, test_02_a_log_line_at_a_prompt_redraws_the_typed_text)
{
    type("adm");
    settle();
    zassert_equal(crux_log_write(CRUX_LOG_INFO, "shared", "while typing"), CRUX_OK);
    expect(CLEAR);
    expect("shared: while typing\r\n");
    expect("login: adm");
    type("\r");
    expect("password: ");
    type(SECRET_START);
    settle();
    zassert_equal(crux_log_write(CRUX_LOG_INFO, "shared", "at the password"), CRUX_OK);
    expect("shared: at the password\r\n");
    /* The prompt is redrawn without the bytes typed so far. */
    expect("password: ");
    type(SECRET_END "\r");
    expect("login failed");
    expect("login: ");
}

ZTEST(cli_console_shared, test_03_a_burst_reports_what_it_dropped)
{
    char text[201];
    memset(text, 'b', sizeof(text) - 1u);
    text[sizeof(text) - 1u] = '\0';
    for (int index = 0; index < 200; ++index) {
        zassert_equal(crux_log_write(CRUX_LOG_INFO, "burst", text), CRUX_OK);
    }
    expect("log messages dropped ---\r\n");
    expect("login: ");
}

ZTEST(cli_console_shared, test_04_the_console_and_the_drain_report_progress)
{
    atomic_val_t console = atomic_get(&reports[CRUX_SERVICE_THREAD_CLI_CONSOLE]);
    atomic_val_t drain_thread = atomic_get(&reports[CRUX_SERVICE_THREAD_SECURITY_EVENT_DRAIN]);
    zassert_true(console > 0 && drain_thread > 0, "console %ld, drain %ld", (long)console,
                 (long)drain_thread);
    /* Idle for three seconds: each thread waits at most a second per pass. */
    for (int step = 0; step < 30; ++step) {
        drain();
        k_msleep(100);
    }
    zassert_true(atomic_get(&reports[CRUX_SERVICE_THREAD_CLI_CONSOLE]) - console >= 2);
    zassert_true(atomic_get(&reports[CRUX_SERVICE_THREAD_SECURITY_EVENT_DRAIN]) - drain_thread >=
                 2);
    /* Threads this image never starts never report. */
    zassert_equal(atomic_get(&reports[CRUX_SERVICE_THREAD_REBOOT_WORKER]), 0);
    zassert_equal(atomic_get(&reports[CRUX_SERVICE_THREAD_WEB_SESSION_WORKER]), 0);
}

ZTEST(cli_console_shared, test_05_after_a_panic_log_text_goes_straight_out)
{
    log_panic();
    zassert_equal(crux_log_write(CRUX_LOG_ERROR, "shared", "after the panic"), CRUX_OK);
    expect("shared: after the panic\r\n");
}
