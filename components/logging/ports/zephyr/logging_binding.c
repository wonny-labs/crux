#include "logging_binding.h"
#include <zephyr/devicetree.h>
#include <zephyr/sys/util.h>

#if !DT_HAS_CHOSEN(zephyr_log_uart)
#error "Crux Logging requires explicit zephyr,log-uart selection"
#else
#define LOG_SELECTION DT_CHOSEN(zephyr_log_uart)
BUILD_ASSERT(DT_PROP_LEN(LOG_SELECTION, uarts) == 1, "Crux Logging requires exactly one UART");
#define LOG_UART DT_PHANDLE_BY_IDX(LOG_SELECTION, uarts, 0)
BUILD_ASSERT(DT_NODE_HAS_STATUS(LOG_UART, okay), "Crux Logging UART must be enabled");
#if defined(CONFIG_SOC_MIMXRT1062)
#if defined(CONFIG_BOARD_MIMXRT1060_EVK) && DT_NODE_EXISTS(DT_NODELABEL(lpuart1))
/* The revision-B EVKB keeps its bounded LPUART1 profile, as its evidence has it. */
#define TARGET_UART                                                                                \
    (DT_NODE_HAS_COMPAT(LOG_UART, nxp_lpuart) && DT_SAME_NODE(LOG_UART, DT_NODELABEL(lpuart1)))
#elif defined(CONFIG_BOARD_MIMXRT1060_EVK)
#define TARGET_UART 0
#else
/* Any other board with the RT1062 SoC: any enabled LPUART, accepted by SoC and devicetree,
 * not by board name, with the mode and owner checks below. Crux checks no pin conflict on
 * such a board; reviewing its pins is the product's duty. Accepted is not qualified. */
#define TARGET_UART DT_NODE_HAS_COMPAT(LOG_UART, nxp_lpuart)
#endif
#else
#define TARGET_UART 0
#endif
BUILD_ASSERT((IS_ENABLED(CONFIG_BOARD_NATIVE_SIM) &&
              DT_NODE_HAS_COMPAT(LOG_UART, zephyr_uart_emul)) ||
                 TARGET_UART,
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
#if defined(CONFIG_SOC_MIMXRT1062)
/* Pinned native UART backend requires UART_CONSOLE. On the RT1062 SoC the
 * inert Console prerequisite may share the logging UART only under the
 * Logging-only routing conditions below, which are about the Console, not the board. */
BUILD_ASSERT(!DT_SAME_NODE(LOG_UART, DT_CHOSEN(zephyr_console)) ||
                 (IS_ENABLED(CONFIG_LOG_PRINTK) && !IS_ENABLED(CONFIG_STDOUT_CONSOLE) &&
                  !IS_ENABLED(CONFIG_CONSOLE_HANDLER) && !IS_ENABLED(CONFIG_CONSOLE_SUBSYS) &&
                  !IS_ENABLED(CONFIG_EARLY_CONSOLE) && !IS_ENABLED(CONFIG_SHELL)),
             "Crux Logging shared Console requires Logging-only routing");
#else
REJECT_OWNER(DT_CHOSEN(zephyr_console), "Crux Logging conflicts with UART Console");
#endif
#endif
#if DT_HAS_CHOSEN(zephyr_shell_uart) && defined(CONFIG_SHELL_BACKEND_SERIAL)
REJECT_OWNER(DT_CHOSEN(zephyr_shell_uart), "Crux Logging conflicts with UART Shell");
#endif
#if DT_NODE_EXISTS(DT_ALIAS(crux_serial0)) && defined(CONFIG_CRUX_SERIAL)
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
