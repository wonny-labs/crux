#ifndef CRUX_CLI_ZEPHYR_H
#define CRUX_CLI_ZEPHYR_H

/**
 * @file
 * @brief Start of the serial console, with its first-account setup, on a Zephyr UART. A composition
 * interface.
 *
 * Status: Experimental (ADR-0001 decision 4). No image uses it yet, and a change is listed in the
 * release notes.
 *
 * This is a composition interface, not a portable one (ADR-0004 phase 1b, rules of
 * docs/composition-interfaces.md). crux_cli_serial_start() binds the Crux console to the UART that
 * the devicetree alias crux-serial0 names, so only the platform composition of a product calls it,
 * and a native-free consumer check rejects the target that publishes it (crux::cli_zephyr). The
 * header includes no Zephyr, vendor, board, frozen or adapter header: a product that starts the
 * console needs neither <crux/serial.h> nor <crux/thread.h>, and never sees the first-account call
 * of Access, which only the console's own setup step makes.
 *
 * A product reaches it by linking the CMake target crux::cli_zephyr, which adds this include root
 * and crux::cli. The provider, the STATIC library that the module registers under
 * CONFIG_CRUX_CLI_CONSOLE, is not linked by this target. The baud rate and the thread's priority
 * are Kconfig symbols (CONFIG_CRUX_CLI_CONSOLE_BAUD_RATE and CONFIG_CRUX_CLI_CONSOLE_PRIORITY), and
 * the thread takes a stack of CONFIG_CRUX_THREAD_STACK_BYTES, as every Crux thread does.
 *
 * What the console does. It owns the serial port that crux-serial0 names, and nothing else may open
 * it: no Zephyr console, log backend, shell or other Crux Serial user on the same UART. It prints
 * nothing before login. At the login prompt a person types a name and a password. The exact word
 * !setup instead asks for a new name, a password and its repeat, and creates the first account with
 * the setup role. Access alone decides whether setup is open: with no account it is, and with one
 * it is refused, so there is no first account in the image and no password in the build. A serial
 * error ends any session, closes and reopens the port, and starts again at the prompt. See
 * docs/cli-contract.md, which also states the limit that a typed password stays in the Serial ring
 * and the UART FIFO after the console has cleared its own buffers.
 *
 * Order, for a product's start code. ADR-0004 section 3 puts the first account at step 7, before
 * the CLI tables of step 9; here the console starts after them, because the start refuses a
 * registry that is not ready: crux_access_init() has returned, the product's command tables have
 * been passed to crux_cli_init(), and the services that the commands call have started. Then
 * crux_cli_serial_start(), once, from thread context.
 */

#include <crux/cli.h>

#ifdef __cplusplus
extern "C" {
#endif

/** The console's settings. The strings are borrowed for the program's life. */
typedef struct {
    /**
     * The role that the first account gets. It must exist in the Access policy and hold
     * access.manage.
     */
    const char *setup_role;
} crux_cli_serial_config_t;

/**
 * Start the console on its own thread and return. The thread opens the port, serves login and setup
 * and sessions, and never ends. Thread context only, once, after crux_access_init() and
 * crux_cli_init().
 *
 * @param config The settings. The call copies the role pointer, not the text: keep the text for the
 *        program's life.
 * @retval CRUX_CLI_OK The thread is running, or was started by an earlier call.
 * @retval CRUX_CLI_ERR_INVALID_ARGUMENT @p config or its setup role is NULL.
 * @retval CRUX_CLI_ERR_NOT_READY crux_cli_init() has not succeeded.
 * @retval CRUX_CLI_ERR_FAILED The thread could not be created.
 */
crux_cli_result_t crux_cli_serial_start(const crux_cli_serial_config_t *config);

#ifdef __cplusplus
}
#endif

#endif /* CRUX_CLI_ZEPHYR_H */
