/*
 * ADR-0004 phase 1b. The serial console with its first-account setup, started through the public
 * composition interface <crux/cli_zephyr.h>, on real PSA providers, a real FatFs on a simulated disk and
 * the Crux Logging provider. The first account is not created in code: the test types `!setup` into an
 * emulated UART, as a person would at a terminal, and reads the console's replies. This is the first run
 * of the console in any image. Test only: the entropy is test-only. The file includes only public
 * headers: no <crux/serial.h>, no <crux/thread.h>, no adapter and no console header.
 */
#include <crux/access.h>
#include <crux/cli.h>
#include <crux/cli_zephyr.h>
#include <crux/credential_store.h>
#include <crux/file_zephyr.h>
#include <crux/security_event.h>
#include <crux/time.h>

#include <ff.h>
#include <string.h>
#include <zephyr/drivers/serial/uart_emul.h>
#include <zephyr/fs/fs.h>
#include <zephyr/kernel.h>
#include <zephyr/ztest.h>

enum { ROOT_SLOT_A = 1, ROOT_SLOT_B = 2 };
#define MOUNT_POINT "/SD:"
#define DISK_NAME "SD:"
#define PATH_SLOT_A MOUNT_POINT "/secure-a"
#define PATH_SLOT_B MOUNT_POINT "/secure-b"
#define ADMIN "admin"
#define ADMIN_PASSWORD "console test password"
#define WRONG_PASSWORD "this is the wrong password"
/* The role of the first account: it holds access.manage, as the console's setup requires. */
#define SETUP_ROLE "administrator"

static const char *const admin_permissions[] = {CRUX_ACCESS_PERMISSION_MANAGE};
static const char *const guest_permissions[] = {"guest.only"};
static const crux_access_role_t roles[] = {
    {"guest", guest_permissions, ARRAY_SIZE(guest_permissions)},
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

/* What the console has written, not yet consumed by an expectation. */
static char capture[2048];
static size_t captured;

static void drain(void)
{
    uint8_t chunk[64];
    uint32_t got;
    while ((got = uart_emul_get_tx_data(console_uart, chunk, sizeof(chunk))) > 0u) {
        zassert_true(captured + got < sizeof(capture), "the console wrote more than the fixture keeps");
        memcpy(&capture[captured], chunk, got);
        captured += got;
        capture[captured] = '\0';
        /* A password is read without echo: no byte of one ever reaches the transmit side. */
        zassert_is_null(strstr(capture, ADMIN_PASSWORD), "a password was echoed");
        zassert_is_null(strstr(capture, WRONG_PASSWORD), "a password was echoed");
    }
}

/* Waits for the console to write `text`, then drops everything up to and including it. */
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
    zassert_unreachable("the console did not write \"%s\"; it wrote \"%s\"", text, capture);
}

/* Types a line as a terminal does: the bytes and a carriage return. */
static void type_line(const char *text)
{
    char line[96];
    size_t length = strlen(text);
    zassert_true(length + 1u < sizeof(line));
    memcpy(line, text, length);
    line[length] = '\r';
    zassert_equal(uart_emul_put_rx_data(console_uart, (const uint8_t *)line, length + 1u), length + 1u);
}

static void *start_services_and_console(void)
{
    zassert_true(device_is_ready(console_uart));
    /* The order of docs/management-in-a-product.md, as far as the console needs it. */
    zassert_equal(crux_security_event_init(NULL, 0), CRUX_OK);
    zassert_equal(crux_realtime_init(), CRUX_OK);
    zassert_true(medium_ready());
    crux_credential_result_t store = crux_credential_start(ROOT_SLOT_A, ROOT_SLOT_B);
    zassert_true(store == CRUX_CREDENTIAL_OK || store == CRUX_CREDENTIAL_ERR_UNUSABLE);
    zassert_equal(crux_access_init(&policy), CRUX_ACCESS_OK);
    zassert_equal(crux_security_event_start(), CRUX_OK);
    /* The product's command tables: none. The built-in help, logout, passwd and account list remain. */
    zassert_equal(crux_cli_init(NULL, NULL, 0u), CRUX_CLI_OK);
    static const crux_cli_serial_config_t console = {.setup_role = SETUP_ROLE};
    zassert_equal(crux_cli_serial_start(&console), CRUX_CLI_OK);
    /* A second call changes nothing. */
    zassert_equal(crux_cli_serial_start(&console), CRUX_CLI_OK);
    return NULL;
}

ZTEST_SUITE(cli_console, NULL, start_services_and_console, NULL, NULL, NULL);

ZTEST(cli_console, test_01_the_start_refuses_a_missing_argument)
{
    static const crux_cli_serial_config_t no_role = {.setup_role = NULL};
    zassert_equal(crux_cli_serial_start(NULL), CRUX_CLI_ERR_INVALID_ARGUMENT);
    zassert_equal(crux_cli_serial_start(&no_role), CRUX_CLI_ERR_INVALID_ARGUMENT);
}

ZTEST(cli_console, test_02_nothing_but_the_login_prompt_appears_and_an_unknown_user_is_refused)
{
    expect("login: ");
    type_line("nobody");
    expect("password: ");
    type_line(WRONG_PASSWORD);
    expect("login failed");
    expect("login: ");
}

ZTEST(cli_console, test_03_setup_creates_the_first_account_from_typed_input)
{
    type_line("!setup");
    expect("new user: ");
    type_line(ADMIN);
    expect("password: ");
    type_line(ADMIN_PASSWORD);
    expect("repeat: ");
    type_line(ADMIN_PASSWORD);
    expect("account created");
    expect("login: ");
}

ZTEST(cli_console, test_04_a_second_setup_is_refused_because_an_account_exists)
{
    type_line("!setup");
    expect("new user: ");
    type_line("second");
    expect("password: ");
    type_line(ADMIN_PASSWORD);
    expect("repeat: ");
    type_line(ADMIN_PASSWORD);
    expect("setup not available");
    expect("login: ");
}

ZTEST(cli_console, test_05_a_login_as_the_new_account_runs_a_command_and_logs_out)
{
    type_line(ADMIN);
    expect("password: ");
    type_line(ADMIN_PASSWORD);
    expect("> ");
    type_line("help");
    expect("logout");
    expect("> ");
    type_line("logout");
    expect("login: ");
}
