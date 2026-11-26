/* Private: the Logging backend of a console that shares its UART
 * (CONFIG_CRUX_CLI_CONSOLE_UART_SHARED). See cli_console_log_backend.c. */
#ifndef CRUX_CLI_CONSOLE_LOG_ZEPHYR_H
#define CRUX_CLI_CONSOLE_LOG_ZEPHYR_H

#include "crux_cli_console.h"

/* The queued log text, for the console's configuration. */
extern const crux_cli_console_log_t crux_cli_console_log_source;

/* Called once by the console's thread before it opens the port: log text stops going straight to
 * the UART and goes to the queue. Thread context. */
void crux_cli_console_log_attach(void);

#endif
