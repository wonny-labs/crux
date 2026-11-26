#include "system_zephyr.h"
#include <zephyr/devicetree.h>
#include <zephyr/sys/util.h>

#if defined(CONFIG_CRUX_SYSTEM_NATIVE_SIM_WATCHDOG) && !defined(CONFIG_BOARD_NATIVE_SIM)
#error "CRUX_SYSTEM_NATIVE_SIM_WATCHDOG is a native_sim test setting, refused on other boards"
#endif

#if defined(CONFIG_BOARD_NATIVE_SIM)
#if defined(CONFIG_CRUX_SYSTEM_NATIVE_SIM_WATCHDOG)
#include "system_sim_watchdog.h"
/* Test-only: the private simulated watchdog of system_sim_watchdog.c. */

const struct device *crux_watchdog_zephyr_device(void)
{
    return crux_system_sim_watchdog_device();
}

bool crux_watchdog_zephyr_running(void)
{
    return crux_system_sim_watchdog_running();
}
#else
/* No physical watchdog is claimed by the normal simulator composition. Tests
 * substitute an actual native driver object at this private binding seam. */

const struct device *crux_watchdog_zephyr_device(void)
{
    return NULL;
}

bool crux_watchdog_zephyr_running(void)
{
    return false;
}
#endif
#else
/* Any board: the watchdog is the node that the board's devicetree selects with crux-watchdog0, and
 * the driver-specific code is chosen by that node's compatible, never by a SoC or board name.
 * Accepted is not qualified: how the watchdog reset is wired on a board is not checked here. */
#if !DT_NODE_EXISTS(DT_ALIAS(crux_watchdog0))
#error "Crux System requires explicit crux-watchdog0 selection"
#elif !DT_NODE_HAS_STATUS(DT_ALIAS(crux_watchdog0), okay)
#error "Crux System watchdog must be enabled"
#elif DT_NODE_HAS_COMPAT(DT_ALIAS(crux_watchdog0), nxp_imx_wdog)
/* The i.MX WDOG block (nxp,imx-wdog): the provider's timeout range, 500 to 64000 ms in steps of
 * 500, is this block's, and Zephyr's watchdog API has no "is running" query, so it is read through
 * the block's HAL. */
#include <fsl_wdog.h>

#define SYSTEM_WDOG DT_ALIAS(crux_watchdog0)
BUILD_ASSERT(DT_NODE_HAS_STATUS(SYSTEM_WDOG, okay), "Crux System watchdog must be enabled");
BUILD_ASSERT(DT_NODE_HAS_COMPAT(SYSTEM_WDOG, nxp_imx_wdog),
             "Crux System requires a supported watchdog driver");

const struct device *crux_watchdog_zephyr_device(void)
{
    return DEVICE_DT_GET(SYSTEM_WDOG);
}

bool crux_watchdog_zephyr_running(void)
{
    return (WDOG_GetStatusFlags((WDOG_Type *)DT_REG_ADDR(SYSTEM_WDOG)) & kWDOG_RunningFlag) != 0;
}
#else
#error "Crux System unsupported watchdog driver: crux-watchdog0 must be an nxp,imx-wdog node"
#endif
#endif
