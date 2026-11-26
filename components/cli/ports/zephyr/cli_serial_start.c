/* The start of the serial console on Zephyr (ADR-0004 phase 1b, Experimental): one thread that runs
 * crux_cli_console_run() on port 0, which the devicetree alias crux-serial0 binds. The context, the
 * settings and the thread handle are static, so a product holds none of them and includes neither
 * <crux/serial.h> nor <crux/thread.h>. The thread is a placed service worker (ADR-0002 P3): its
 * entry calls the placement first, so that it runs at CONFIG_CRUX_CLI_CONSOLE_PRIORITY, and each
 * pass of its loop reports progress. Under CONFIG_CRUX_CLI_CONSOLE_UART_SHARED the console also
 * prints the log text of the Logging backend in
 * components/logging/ports/zephyr/logging_console_backend.c, which shares its UART.
 */
#include "cli_console.h"
#include "cli_internal.h"

#include <crux/cli_zephyr.h>
#include <crux/thread.h>

#ifdef CRUX_SERVICE_PRIORITY_PLACEMENT
#include "service_priority.h"
#endif
#ifdef CONFIG_CRUX_CLI_CONSOLE_UART_SHARED
#include "logging_console.h"

_Static_assert(CRUX_LOGGING_CONSOLE_TEXT_MAX == CRUX_CLI_CONSOLE_LOG_TEXT_MAX,
               "a log entry must fit the console's buffer");
#endif

/* The one logical port that the Zephyr Serial binding supports: crux-serial0. */
#define CRUX_CLI_CONSOLE_PORT 0u

static crux_cli_context_t console_context;
static crux_cli_console_config_t console_config;
static crux_thread_t console_thread;
static bool console_started;
#ifdef CONFIG_CRUX_CLI_CONSOLE_UART_SHARED
/* The queue of the Logging backend that shares the UART. The console attaches it before each open,
 * so log text stops going straight to the UART, and prints it between reads. */
static crux_cli_console_log_t console_log;
#endif

#ifdef CRUX_SERVICE_PRIORITY_PLACEMENT
/* The console's progress, once per pass of its loop (<crux/service_priority_zephyr.h>). */
static void console_progress(void)
{
    crux_service_progress_report(CRUX_SERVICE_THREAD_CLI_CONSOLE);
}
#endif

static void console_main(void *argument)
{
#ifdef CRUX_SERVICE_PRIORITY_PLACEMENT
    crux_service_priority_place(CRUX_SERVICE_THREAD_CLI_CONSOLE);
#endif
    (void)argument;
    /* It returns only for a bad argument, which the start has already refused. */
    (void)crux_cli_console_run(&console_context, &console_config);
}

crux_cli_result_t crux_cli_serial_start(const crux_cli_serial_config_t *config)
{
    /* The default stack, CONFIG_CRUX_THREAD_STACK_BYTES, which the product budgets for every Crux
     * thread. */
    static const crux_thread_options_t options = {0u, CRUX_THREAD_PRIORITY_LOW};

    if (config == NULL || config->setup_role == NULL) {
        return CRUX_CLI_ERR_INVALID_ARGUMENT;
    }
    if (!crux_cli_registry_ready()) {
        return CRUX_CLI_ERR_NOT_READY;
    }
    if (console_started) {
        return CRUX_CLI_OK;
    }
    console_config.port = CRUX_CLI_CONSOLE_PORT;
    console_config.serial.baud_rate = CONFIG_CRUX_CLI_CONSOLE_BAUD_RATE;
    console_config.serial.data_bits = 8u;
    console_config.serial.stop_bits = 1u;
    console_config.serial.parity = CRUX_SERIAL_PARITY_NONE;
    console_config.setup_role = config->setup_role;
#ifdef CONFIG_CRUX_CLI_CONSOLE_UART_SHARED
    console_log.next = crux_logging_console.next;
    console_log.attach = crux_logging_console.attach;
    console_log.source = NULL;
    console_config.log = &console_log;
#endif
#ifdef CRUX_SERVICE_PRIORITY_PLACEMENT
    console_config.progress = console_progress;
#endif
    if (crux_thread_create(&options, console_main, NULL, &console_thread) != CRUX_OK) {
        return CRUX_CLI_ERR_FAILED;
    }
    console_started = true;
    return CRUX_CLI_OK;
}
