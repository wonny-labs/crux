/* The start of the serial console on Zephyr (ADR-0004 phase 1b, Experimental): one thread that runs
 * crux_cli_console_run() on port 0, which the devicetree alias crux-serial0 binds. The context, the
 * settings and the thread handle are static, so a product holds none of them and includes neither
 * <crux/serial.h> nor <crux/thread.h>. The thread is a placed service worker (ADR-0002 P3): its
 * entry calls the placement first, so that it runs at CONFIG_CRUX_CLI_CONSOLE_PRIORITY. */
#include "cli_console.h"
#include "cli_internal.h"

#include <crux/cli_zephyr.h>
#include <crux/thread.h>

#ifdef CRUX_SERVICE_PRIORITY_PLACEMENT
#include "service_priority.h"
#endif

/* The one logical port that the Zephyr Serial binding supports: crux-serial0. */
#define CRUX_CLI_CONSOLE_PORT 0u

static crux_cli_context_t console_context;
static crux_cli_console_config_t console_config;
static crux_thread_t console_thread;
static bool console_started;

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
    if (crux_thread_create(&options, console_main, NULL, &console_thread) != CRUX_OK) {
        return CRUX_CLI_ERR_FAILED;
    }
    console_started = true;
    return CRUX_CLI_OK;
}
