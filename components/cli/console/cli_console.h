/* The console's private parts: the login loop, which is portable and runs over any transport, and
 * one open-serve-close cycle over crux_serial. */
#ifndef CRUX_CLI_CONSOLE_PRIVATE_H
#define CRUX_CLI_CONSOLE_PRIVATE_H

#include "crux_cli_console.h"

/* Pause after a transport or open failure, so that a persistent failure retries at a slow rate. */
#ifndef CRUX_CLI_CONSOLE_RETRY_MS
#define CRUX_CLI_CONSOLE_RETRY_MS 5000
#endif
/* With a progress hook, the pause is slept in steps of this, with a report after each. */
#ifndef CRUX_CLI_CONSOLE_PROGRESS_MS
#define CRUX_CLI_CONSOLE_PROGRESS_MS 1000
#endif
/* With a log source, a wait for input is split into steps of this, and log text is shown between
 * them, so that a line waits at most this long while the console is idle at a prompt. */
#ifndef CRUX_CLI_CONSOLE_LOG_POLL_MS
#define CRUX_CLI_CONSOLE_LOG_POLL_MS 100u
#endif
/* Log text shown in one go stops once this much is out, and the line is redrawn, so that a burst
 * cannot hold off typed input for long. One entry more than this can go out. */
#ifndef CRUX_CLI_CONSOLE_LOG_BURST_BYTES
#define CRUX_CLI_CONSOLE_LOG_BURST_BYTES 512u
#endif
/* The buffer for one entry of log text: the longest entry that a log source hands out. */
#define CRUX_CLI_CONSOLE_LOG_TEXT_MAX 512u
/* The input line kept for a redraw: a prompt and a longest line. A longer one is not redrawn. */
#define CRUX_CLI_CONSOLE_REDRAW_MAX (CRUX_CLI_LINE_MAX + 64u)

/* Serves login, setup and sessions until the transport fails. Ends any session before returning.
 * Returns CRUX_CLI_ERR_OUTPUT, or CRUX_CLI_ERR_INVALID_ARGUMENT for a missing argument. */
crux_cli_result_t crux_cli_console_serve(crux_cli_context_t *context, const crux_cli_io_t *io,
                                         const char *setup_role);

/* What survives between cycles: a handle whose close was refused. */
typedef struct {
    crux_serial_t serial;
    bool open;
} crux_cli_console_state_t;

/* One cycle: close a leftover handle, open, serve, and close. Emits cli.console_error for each
 * failure it meets. Returns the result of crux_cli_console_serve, or CRUX_CLI_ERR_OUTPUT if the
 * port would not open. */
crux_cli_result_t crux_cli_console_cycle(crux_cli_console_state_t *state,
                                         crux_cli_context_t *context,
                                         const crux_cli_console_config_t *config);

#endif
