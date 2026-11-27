#include "logging_binding.h"
#include <zephyr/devicetree.h>
#include <zephyr/sys/util.h>

#if defined(CONFIG_CRUX_LOGGING_CONSOLE_BACKEND)
/* The console shares its UART with Logging: the console's own backend writes log text on the UART
 * of crux-serial0 (logging_console_backend.c). zephyr,log-uart is optional, and when it is chosen
 * it names that UART. The console's start checks that the UART's rate is the console's. */
#define LOG_UART DT_ALIAS(crux_serial0)
#if !DT_NODE_HAS_STATUS(LOG_UART, okay)
#error "Crux Logging shared with the console requires an enabled crux-serial0 UART alias"
#endif
#if DT_HAS_CHOSEN(zephyr_log_uart)
BUILD_ASSERT(DT_PROP_LEN(DT_CHOSEN(zephyr_log_uart), uarts) == 1 &&
                 DT_SAME_NODE(DT_PHANDLE_BY_IDX(DT_CHOSEN(zephyr_log_uart), uarts, 0), LOG_UART),
             "Crux Logging shared with the console requires zephyr,log-uart to name crux-serial0");
#endif
#define CRUX_LOGGING_HAS_UART 1
#elif !DT_HAS_CHOSEN(zephyr_log_uart)
#error "Crux Logging requires explicit zephyr,log-uart selection"
#else
#define LOG_SELECTION DT_CHOSEN(zephyr_log_uart)
BUILD_ASSERT(DT_PROP_LEN(LOG_SELECTION, uarts) == 1, "Crux Logging requires exactly one UART");
#define LOG_UART DT_PHANDLE_BY_IDX(LOG_SELECTION, uarts, 0)
#define CRUX_LOGGING_HAS_UART 1
#endif

#ifdef CRUX_LOGGING_HAS_UART
BUILD_ASSERT(DT_NODE_HAS_STATUS(LOG_UART, okay), "Crux Logging UART must be enabled");
/* The UART drivers whose deferred-backend profile is reviewed, selected by compatible: any enabled
 * node of one of them, on any board, with the mode and owner checks below. The board's devicetree
 * chooses which instance (zephyr,log-uart, or crux-serial0 when the console shares it); Crux checks
 * no pin conflict, so reviewing the board's pins is the product's duty. Accepted is not qualified.
 * Another driver is a reviewed addition here, keyed by its compatible. */
#define TARGET_UART DT_NODE_HAS_COMPAT(LOG_UART, nxp_lpuart)
#define SIMULATED_UART                                                                             \
    (DT_NODE_HAS_COMPAT(LOG_UART, zephyr_uart_emul) ||                                             \
     DT_NODE_HAS_COMPAT(LOG_UART, zephyr_native_pty_uart))
BUILD_ASSERT((IS_ENABLED(CONFIG_BOARD_NATIVE_SIM) && SIMULATED_UART) || TARGET_UART,
             "Crux Logging unsupported UART resource");
BUILD_ASSERT(DT_PROP(LOG_UART, current_speed) == 115200 &&
                 DT_ENUM_IDX_OR(LOG_UART, parity, 0) == 0 &&
                 DT_ENUM_IDX_OR(LOG_UART, stop_bits, 1) == 1 &&
                 DT_PROP_OR(LOG_UART, data_bits, 8) == 8 &&
                 !DT_PROP_OR(LOG_UART, hw_flow_control, 0) &&
                 !DT_PROP_OR(LOG_UART, single_wire, 0) && !DT_PROP_OR(LOG_UART, nxp_rs485_mode, 0),
             "Crux Logging unsupported UART mode");
BUILD_ASSERT(DT_CHILD_NUM_STATUS_OKAY(LOG_UART) == 0, "Crux Logging rejects UART child consumers");
#define REJECT_OWNER(node, message) BUILD_ASSERT(!DT_SAME_NODE(LOG_UART, node), message)
#if DT_HAS_CHOSEN(zephyr_console) && defined(CONFIG_UART_CONSOLE)
/* Pinned native UART backend requires UART_CONSOLE. The inert Console prerequisite may share the
 * logging UART only under the Logging-only routing conditions below, which are about the Console,
 * not the board. */
BUILD_ASSERT(!DT_SAME_NODE(LOG_UART, DT_CHOSEN(zephyr_console)) ||
                 (IS_ENABLED(CONFIG_LOG_PRINTK) && !IS_ENABLED(CONFIG_STDOUT_CONSOLE) &&
                  !IS_ENABLED(CONFIG_CONSOLE_HANDLER) && !IS_ENABLED(CONFIG_CONSOLE_SUBSYS) &&
                  !IS_ENABLED(CONFIG_EARLY_CONSOLE) && !IS_ENABLED(CONFIG_SHELL)),
             "Crux Logging shared Console requires Logging-only routing");
#endif
#if DT_HAS_CHOSEN(zephyr_shell_uart) && defined(CONFIG_SHELL_BACKEND_SERIAL)
REJECT_OWNER(DT_CHOSEN(zephyr_shell_uart), "Crux Logging conflicts with UART Shell");
#endif
/* The console is the one Crux Serial user, and it may share the UART only in the shared mode. */
#if DT_NODE_EXISTS(DT_ALIAS(crux_serial0)) && defined(CONFIG_CRUX_SERIAL) &&                       \
    !defined(CONFIG_CRUX_LOGGING_CONSOLE_BACKEND)
REJECT_OWNER(DT_ALIAS(crux_serial0), "Crux Logging conflicts with Crux Serial");
#endif
#if DT_HAS_CHOSEN(zephyr_uart_mcumgr) && defined(CONFIG_UART_MCUMGR)
REJECT_OWNER(DT_CHOSEN(zephyr_uart_mcumgr), "Crux Logging conflicts with UART management");
#endif
#if DT_HAS_CHOSEN(zephyr_bt_uart) && defined(CONFIG_BT_HCI)
REJECT_OWNER(DT_CHOSEN(zephyr_bt_uart), "Crux Logging conflicts with Bluetooth UART");
#endif
#if DT_NODE_EXISTS(DT_ALIAS(m2_hci_bt_uart)) && defined(CONFIG_BT_HCI)
REJECT_OWNER(DT_ALIAS(m2_hci_bt_uart), "Crux Logging conflicts with Bluetooth UART");
#endif

const struct device *crux_log_zephyr_device(void)
{
    return DEVICE_DT_GET(LOG_UART);
}
#endif
