/* The console on a UART that it shares with Logging (CONFIG_CRUX_CLI_CONSOLE_UART_SHARED), over a
 * scripted crux_serial and the real log queue: log text shows only while the console waits for
 * input, the input line is cleared and redrawn around it, a secret is never redrawn, command output
 * is never interleaved, a full queue says how much it dropped, and every pass reports progress. */
#include "cli_console.h"
#include "logging_console_queue.h"

#include "cli_session_test.h"
#include "fake_serial.h"
#include <stdint.h>

#define PASSWORD "correct-horse-password"
#define CLEAR "\r\x1b[K"

static uint8_t storage[CRUX_LOG_QUEUE_MIN];
static crux_log_queue_t queue;
static crux_cli_console_state_t state;
static unsigned progress_calls;

static size_t next_entry(void *source, char *text, size_t capacity)
{
    return crux_log_queue_get(source, text, capacity);
}

static void count_progress(void)
{
    progress_calls += 1;
}

/* The opens that had happened at each attach. */
static unsigned attaches;
static unsigned opens_at_attach;

static void attach(void *source)
{
    (void)source;
    attaches += 1;
    opens_at_attach = cli_fake_serial.open_calls;
}

static const crux_cli_console_log_t log_source = {next_entry, attach, &queue};
static const crux_cli_console_config_t config = {
    0, {115200, 8, 1, CRUX_SERIAL_PARITY_NONE}, "administrator", &log_source, count_progress};

static cli_fake_t *wire(void)
{
    return &cli_fake_serial.transport;
}

static void queue_text(const char *text)
{
    CHECK(crux_log_queue_put(&queue, text, strlen(text)));
}

/* A command whose service logs while it runs: the line must wait for the next prompt. */
static crux_cli_result_t emit(crux_cli_call_t *call, size_t argc, const char *const *argv,
                              void *context)
{
    (void)argc;
    (void)argv;
    (void)context;
    queue_text("during the command\n");
    crux_cli_result_t result = crux_cli_write(call, "first\n", 6u);
    return result == CRUX_CLI_OK ? crux_cli_write(call, "second\n", 7u) : result;
}

static const crux_cli_command_t table[] = {
    CRUX_CLI_COMMAND("emit", "log while printing", CRUX_CLI_SESSION_ONLY, 0, 0,
                     CRUX_CLI_CHANNEL_SERIAL, emit, NULL),
};

static void begin(void)
{
    cli_test_begin_table(table, sizeof(table) / sizeof(table[0]));
    cli_fake_serial_reset();
    memset(&state, 0, sizeof(state));
    CHECK(crux_log_queue_init(&queue, storage, sizeof(storage)));
    progress_calls = 0;
    attaches = 0;
    opens_at_attach = UINT32_MAX;
}

static crux_cli_result_t cycle(void)
{
    return crux_cli_console_cycle(&state, &cli_test_context, &config);
}

static void queue_mid_line(void *context)
{
    queue_text(context);
}

static void logs_at_the_login_prompt(void)
{
    /* Logs wait while input is there, and show when the console would wait. */
    begin();
    queue_text("boot line\n");
    cli_fake_input_timeouts(wire(), 1);
    cli_fake_input(wire(), "alice\r" PASSWORD "\rlogout\r");
    CHECK(cycle() == CRUX_CLI_ERR_OUTPUT);
    CHECK_TEXT(wire()->output, "login: " CLEAR "boot line\r\nlogin: alice\r\npassword: \r\n"
                               "> logout\r\nlogin: ");
    CHECK(cli_fake_access.logout_calls == 1);
    /* The source stopped writing to the UART before the console opened it. */
    CHECK(attaches == 1u);
    CHECK(opens_at_attach == 0u);
    /* Every read reports progress at least once. */
    CHECK(progress_calls >= strlen("alice\r" PASSWORD "\rlogout\r"));
}

static void nothing_is_cleared_without_a_log(void)
{
    begin();
    cli_fake_input_timeouts(wire(), 5);
    cli_fake_input(wire(), "alice\r" PASSWORD "\rlogout\r");
    CHECK(cycle() == CRUX_CLI_ERR_OUTPUT);
    CHECK_TEXT(wire()->output, "login: alice\r\npassword: \r\n> logout\r\nlogin: ");
}

static void logs_while_typing_redraw_the_line(void)
{
    /* The typed text comes back after the log, with an erased byte gone. */
    begin();
    cli_fake_input(wire(), "alx\x7f");
    cli_fake_input_timeouts(wire(), 1);
    cli_fake_input(wire(), "ice\r" PASSWORD "\rlogout\r");
    wire()->on_read_timeout = queue_mid_line;
    wire()->hook_context = "while typing\n";
    CHECK(cycle() == CRUX_CLI_ERR_OUTPUT);
    CHECK_TEXT(wire()->output, "login: alx\b \b" CLEAR "while typing\r\nlogin: alice\r\n"
                               "password: \r\n> logout\r\nlogin: ");
}

static void a_secret_is_never_redrawn(void)
{
    begin();
    cli_fake_input(wire(), "alice\rcorrect-");
    cli_fake_input_timeouts(wire(), 1);
    cli_fake_input(wire(), "horse-password\rlogout\r");
    wire()->on_read_timeout = queue_mid_line;
    wire()->hook_context = "at the password\n";
    CHECK(cycle() == CRUX_CLI_ERR_OUTPUT);
    CHECK_TEXT(wire()->output, "login: alice\r\npassword: " CLEAR "at the password\r\npassword: "
                               "\r\n> logout\r\nlogin: ");
    CHECK(strstr(wire()->output, "correct") == NULL);
    CHECK(strstr(wire()->output, "horse") == NULL);
    CHECK(cli_fake_access.login_calls == 1);
    CHECK(cli_fake_access.logout_calls == 1);
}

static void command_output_is_never_interleaved(void)
{
    begin();
    cli_fake_input(wire(), "alice\r" PASSWORD "\remit\r");
    cli_fake_input_timeouts(wire(), 1);
    cli_fake_input(wire(), "logout\r");
    CHECK(cycle() == CRUX_CLI_ERR_OUTPUT);
    CHECK_TEXT(wire()->output, "login: alice\r\npassword: \r\n> emit\r\nfirst\r\nsecond\r\n"
                               "> " CLEAR "during the command\r\n> logout\r\nlogin: ");
}

static void a_full_queue_says_how_much_it_dropped(void)
{
    begin();
    char line[100];
    memset(line, 'q', sizeof(line) - 2u);
    line[sizeof(line) - 2u] = '\n';
    line[sizeof(line) - 1u] = '\0';
    unsigned admitted = 0;
    while (crux_log_queue_put(&queue, line, strlen(line))) {
        admitted += 1;
    }
    crux_log_queue_add_dropped(&queue, 2u);
    CHECK(admitted == 10u);
    cli_fake_input_timeouts(wire(), 3);
    CHECK(cycle() == CRUX_CLI_ERR_OUTPUT);
    /* Two bursts, each ended by the redrawn prompt, so that typing is not starved; the drop line
     * comes after the last surviving line. */
    char expected[4096];
    int used = snprintf(expected, sizeof(expected), "login: " CLEAR);
    for (unsigned index = 0; index < admitted; ++index) {
        bool burst_ends = index + 1u == (CRUX_CLI_CONSOLE_LOG_BURST_BYTES + 98u) / 99u;
        used += snprintf(&expected[used], sizeof(expected) - (size_t)used, "%.*s\r\n%s",
                         (int)strlen(line) - 1, line, burst_ends ? "login: " CLEAR : "");
    }
    (void)snprintf(&expected[used], sizeof(expected) - (size_t)used,
                   "--- 3 log messages dropped ---\r\nlogin: ");
    CHECK_TEXT(wire()->output, expected);
}

static void a_failed_write_of_log_text_ends_the_cycle(void)
{
    begin();
    queue_text("this line will not fit\n");
    cli_fake_input_timeouts(wire(), 1);
    cli_fake_input(wire(), "alice\r");
    wire()->write_fail_after = 12;
    CHECK(cycle() == CRUX_CLI_ERR_OUTPUT);
    CHECK(cli_fake_serial.close_calls == 1);
    CHECK(cli_fake_event_count_of(CRUX_CLI_EVENT_CONSOLE_ERROR) == 1);
    CHECK(cli_fake_access.login_calls == 0);
    /* The next cycle attaches again before it opens again. */
    cli_fake_output_clear(wire());
    wire()->write_fail_after = SIZE_MAX;
    CHECK(cycle() == CRUX_CLI_ERR_OUTPUT);
    CHECK(attaches == 2u);
    CHECK(opens_at_attach == 1u);
    CHECK(cli_fake_serial.open_calls == 2u);
}

static void a_dedicated_console_takes_no_log_text(void)
{
    /* Without a log source the console reads as before: one read per wait, and no clearing. */
    static const crux_cli_console_config_t dedicated = {
        0, {115200, 8, 1, CRUX_SERIAL_PARITY_NONE}, "administrator", NULL, count_progress};
    begin();
    queue_text("never shown\n");
    cli_fake_input_timeouts(wire(), 2);
    cli_fake_input(wire(), "alice\r" PASSWORD "\rlogout\r");
    CHECK(crux_cli_console_cycle(&state, &cli_test_context, &dedicated) == CRUX_CLI_ERR_OUTPUT);
    CHECK_TEXT(wire()->output, "login: alice\r\npassword: \r\n> logout\r\nlogin: ");
    CHECK(wire()->read_timeouts_seen == 2u);
    CHECK(progress_calls >= strlen("alice\r" PASSWORD "\rlogout\r") + 2u);
}

int main(void)
{
    logs_at_the_login_prompt();
    nothing_is_cleared_without_a_log();
    logs_while_typing_redraw_the_line();
    a_secret_is_never_redrawn();
    command_output_is_never_interleaved();
    a_full_queue_says_how_much_it_dropped();
    a_failed_write_of_log_text_ends_the_cycle();
    a_dedicated_console_takes_no_log_text();
    return cli_test_finish("cli console shared");
}
