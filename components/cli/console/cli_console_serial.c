/* The console's connection to crux_serial. Portable: the Serial contract owns everything native,
 * and a composition selects the port, which on the EVKB is LPUART3 (rule L1).
 *
 * With a log source (a UART shared with Logging), the console shows log text only while it waits for
 * input: it clears the input line, writes the text, and redraws the line from what it wrote since the
 * last line end. That record holds the prompt and the echo, and never a secret, which is not echoed.
 * Command output is never interleaved, because no read happens while a command prints. */
#include "cli_console.h"

#include "cli_console_log.h"
#include "cli_internal.h"

#include <crux/thread.h>

/* What the console wrote since the last line end, as a terminal shows it. */
typedef struct {
    char text[CRUX_CLI_CONSOLE_REDRAW_MAX];
    size_t length;
    bool lost; /* More than fits: the line cannot be redrawn. */
} console_line_t;

typedef struct {
    crux_serial_t serial;
    crux_cli_line_ends_t line_ends;
    const crux_cli_console_config_t *config;
    console_line_t line;
    char entry[CRUX_CLI_LOG_ENTRY_MAX];
} console_transport_t;

static const crux_access_session_t no_session = {0};

static void report_progress(const crux_cli_console_config_t *config)
{
    if (config->progress != NULL) {
        config->progress();
    }
}

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters): as crux_cli_io_t.read.
static int serial_read(console_transport_t *console, void *buffer, size_t length,
                       uint32_t timeout_ms)
{
    size_t transferred = 0;
    crux_status_t status =
        crux_serial_read(console->serial, buffer, length, timeout_ms, &transferred);
    if (status == CRUX_OK) {
        return (int)transferred;
    }
    return status == CRUX_ERR_TIMEOUT || status == CRUX_ERR_BUSY ? 0 : -1;
}

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters): crux_cli_io_t fixes this signature.
static int raw_write(void *transport, const void *buffer, size_t length, uint32_t timeout_ms)
{
    console_transport_t *console = transport;
    size_t transferred = 0;
    crux_status_t status =
        crux_serial_write(console->serial, buffer, length, timeout_ms, &transferred);
    if (status == CRUX_OK) {
        return (int)transferred;
    }
    return status == CRUX_ERR_TIMEOUT || status == CRUX_ERR_BUSY ? 0 : -1;
}

/* Log text and redraws: the terminal's line ends, and no record of what was written. */
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters): crux_cli_io_t fixes this signature.
static int untracked_write(void *transport, const void *buffer, size_t length,
                           uint32_t timeout_ms)
{
    console_transport_t *console = transport;
    return crux_cli_write_terminal(&console->line_ends, raw_write, console, buffer, length,
                                   timeout_ms);
}

/* The CLI only ends lines, erases one byte with "\b \b" and writes printable text, so a cursor
 * that only moves back on a backspace is all a redraw needs. */
static void track(console_line_t *line, const char *bytes, size_t length)
{
    for (size_t index = 0; index < length; ++index) {
        unsigned char byte = (unsigned char)bytes[index];
        if (byte == '\n') {
            line->length = 0;
            line->lost = false;
        } else if (byte == '\b') {
            if (line->length > 0) {
                line->length -= 1;
            }
        } else if (byte >= 0x20u && byte != 0x7Fu) {
            if (line->length < sizeof(line->text)) {
                line->text[line->length] = (char)byte;
                line->length += 1;
            } else {
                line->lost = true;
            }
        }
    }
}

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters): crux_cli_io_t fixes this signature.
static int console_write(void *transport, const void *buffer, size_t length, uint32_t timeout_ms)
{
    console_transport_t *console = transport;
    int sent = untracked_write(console, buffer, length, timeout_ms);
    if (sent > 0) {
        track(&console->line, buffer, (size_t)sent);
    }
    return sent;
}

/* Shows queued log text, if any, around the input line. Returns -1 when a write failed. */
static int show_logs(console_transport_t *console)
{
    const crux_cli_console_log_t *log = console->config->log;
    size_t length = log->next(log->source, console->entry, sizeof(console->entry));
    if (length == 0) {
        return 0;
    }
    const crux_cli_io_t io = {NULL, untracked_write, console, false};
    /* A line that cannot be redrawn is left as it is, and the text starts on the next line. */
    crux_cli_result_t result =
        crux_cli_send_text(&io, no_session, console->line.lost ? "\n" : "\r\x1b[K");
    size_t shown = 0;
    while (result == CRUX_CLI_OK) {
        result = crux_cli_send(&io, no_session, console->entry, length);
        if (result == CRUX_CLI_OK && console->entry[length - 1u] != '\n') {
            result = crux_cli_send_text(&io, no_session, "\n");
        }
        shown += length;
        if (shown >= CRUX_CLI_CONSOLE_LOG_BURST_BYTES) {
            break;
        }
        length = log->next(log->source, console->entry, sizeof(console->entry));
        if (length == 0) {
            break;
        }
    }
    crux_cli_secure_zero(console->entry, sizeof(console->entry));
    if (result == CRUX_CLI_OK && !console->line.lost) {
        result = crux_cli_send(&io, no_session, console->line.text, console->line.length);
    } else if (result == CRUX_CLI_OK) {
        /* What follows starts a new line, which can be redrawn again. */
        console->line.lost = false;
        console->line.length = 0;
    }
    return result == CRUX_CLI_OK ? 1 : -1;
}

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters): crux_cli_io_t fixes this signature.
static int console_read(void *transport, void *buffer, size_t length, uint32_t timeout_ms)
{
    console_transport_t *console = transport;
    report_progress(console->config);
    if (console->config->log == NULL) {
        return serial_read(console, buffer, length, timeout_ms);
    }
    uint32_t waited = 0;
    for (;;) {
        /* Typed input goes first, so that log text never holds it off for longer than a burst. */
        int got = serial_read(console, buffer, length, 0u);
        if (got != 0) {
            return got;
        }
        if (show_logs(console) < 0) {
            return -1;
        }
        uint32_t step = timeout_ms - waited < CRUX_CLI_CONSOLE_LOG_POLL_MS
                            ? timeout_ms - waited
                            : CRUX_CLI_CONSOLE_LOG_POLL_MS;
        if (step == 0) {
            return 0;
        }
        got = serial_read(console, buffer, length, step);
        waited += step;
        if (got != 0 || waited >= timeout_ms) {
            return got;
        }
        report_progress(console->config);
    }
}

static void report_console_error(void)
{
    crux_cli_event_t event = {CRUX_CLI_EVENT_CONSOLE_ERROR,
                              CRUX_CLI_EVENT_FAILED,
                              (uint8_t)CRUX_ACCESS_CHANNEL_SERIAL,
                              {0}};
    crux_cli_port_event(&event);
}

/* Close keeps the handle on BUSY, and consumes it otherwise, even on a native failure. */
static void close_port(crux_cli_console_state_t *state)
{
    crux_status_t status = crux_serial_close(&state->serial);
    if (status != CRUX_ERR_BUSY) {
        state->open = false;
    }
    if (status != CRUX_OK) {
        report_console_error();
    }
}

crux_cli_result_t crux_cli_console_cycle(crux_cli_console_state_t *state,
                                         crux_cli_context_t *context,
                                         const crux_cli_console_config_t *config)
{
    if (state->open) {
        close_port(state);
        if (state->open) {
            return CRUX_CLI_ERR_OUTPUT;
        }
    }
    if (crux_serial_open(config->port, &config->serial, &state->serial) != CRUX_OK) {
        report_console_error();
        return CRUX_CLI_ERR_OUTPUT;
    }
    state->open = true;
    console_transport_t transport = {state->serial, {false}, config, {{0}, 0, false}, {0}};
    crux_cli_io_t io = {console_read, console_write, &transport, true};
    /* It returns only when the transport has failed, and any session is over by then. */
    crux_cli_result_t result = crux_cli_console_serve(context, &io, config->setup_role);
    report_console_error();
    close_port(state);
    return result;
}

crux_cli_result_t crux_cli_console_run(crux_cli_context_t *context,
                                       const crux_cli_console_config_t *config)
{
    if (context == NULL || config == NULL || config->setup_role == NULL) {
        return CRUX_CLI_ERR_INVALID_ARGUMENT;
    }
    crux_cli_console_state_t state = {{0, 0}, false};
    for (;;) {
        (void)crux_cli_console_cycle(&state, context, config);
        /* A persistent failure retries at a slow rate, with an event for each attempt. A supervisor
         * hears from the console at least once a second, so the pause is slept in steps. */
        if (config->progress == NULL) {
            (void)crux_thread_sleep_for(crux_duration_from_ms(CRUX_CLI_CONSOLE_RETRY_MS));
            continue;
        }
        for (int slept = 0; slept < CRUX_CLI_CONSOLE_RETRY_MS;
             slept += CRUX_CLI_CONSOLE_PROGRESS_MS) {
            report_progress(config);
            (void)crux_thread_sleep_for(crux_duration_from_ms(CRUX_CLI_CONSOLE_PROGRESS_MS));
        }
    }
}
