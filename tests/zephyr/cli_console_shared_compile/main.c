/*
 * Compile and link evidence for the serial console that shares its UART with Crux Logging on the
 * RT1060-EVKB. It binds no File root and starts no service that a login needs, so it is not a
 * working console and has not run on a board. The two calls below put the console, and through its
 * start the Logging backend, in the image. See run.sh.
 */
#include <crux/cli.h>
#include <crux/cli_zephyr.h>

int main(void)
{
    static const crux_cli_serial_config_t console = {.setup_role = "administrator"};

    if (crux_cli_init(NULL, NULL, 0u) == CRUX_CLI_OK) {
        (void)crux_cli_serial_start(&console);
    }
    return 0;
}
