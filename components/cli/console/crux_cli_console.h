/**
 * @file
 * @brief The serial console: login, first-account setup and a session over crux_serial.
 *
 * For the composition that owns the console thread. It is separate from the adapter header so that
 * the SSH adapter never sees a serial type.
 */
#ifndef CRUX_CLI_CONSOLE_H
#define CRUX_CLI_CONSOLE_H

#include <crux/serial.h>
#include <crux_cli_adapter.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Finished log text for a console that shares its UART with Logging. The console takes entries out
 * only while it waits for input, never during a command's output.
 */
typedef struct {
    /**
     * Copy the oldest entry, which ends with a LF, into text and return its length, or 0 when there
     * is none. Called on the console's thread. It must not wait.
     */
    size_t (*next)(void *source, char *text, size_t capacity);
    /**
     * NULL, or called on the console's thread before each open of the port, so that the source
     * stops writing to the UART by itself before the console takes it over.
     */
    void (*attach)(void *source);
    void *source; /**< Passed unchanged to next and attach. */
} crux_cli_console_log_t;

/** The console's settings, as the composition configured them. */
typedef struct {
    crux_serial_port_t port;
    crux_serial_config_t serial;
    const char *setup_role; /**< Role for first-account setup. It must hold access.manage. */
    /** NULL for a console with a UART of its own, which prints no log text. */
    const crux_cli_console_log_t *log;
    /**
     * NULL, or called on the console's thread once per pass of its loop: each read, which waits at
     * most a second, and each second of the pause after a failure. It must not wait.
     */
    void (*progress)(void);
} crux_cli_console_config_t;

/**
 * Serve the serial console: open the port, log in, run a session, and go back to the login prompt.
 *
 * Nothing about the device appears before login, except log text from a log source (above). A
 * serial error ends any session, closes and
 * reopens the port, and starts again at the prompt. A port that will not open is retried at a slow
 * rate, so a quarantined Serial binding keeps the console down until a reset, with an event for
 * each attempt. Does not return unless an argument is wrong.
 *
 * @param context The console's memory, used for the program's life.
 * @param config Borrowed for the program's life.
 * @retval CRUX_CLI_ERR_INVALID_ARGUMENT An argument or the setup role is missing.
 */
crux_cli_result_t crux_cli_console_run(crux_cli_context_t *context,
                                       const crux_cli_console_config_t *config);

#ifdef __cplusplus
}
#endif

#endif
