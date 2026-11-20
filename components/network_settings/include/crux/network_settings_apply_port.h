/**
 * @file
 * @brief The apply port of the network settings service: two functions that the product implements.
 *
 * Status: Experimental (ADR-0001 decision 4). The network settings service has no Zephyr
 * composition outside tests/ yet, and a change is listed in the release notes. This header is the
 * port that ADR-0004 (decision C3) publishes. It is the inverse of a composition interface: Crux
 * declares the two functions, the product defines them with its own native code, such as Zephyr's
 * network interface calls, and this header names no native type.
 *
 * The product implements both. Alternatively it links the port that applies nothing and reports no
 * running values: CONFIG_CRUX_NETWORK_SETTINGS_NO_APPLY in the Zephyr module, the
 * crux_network_settings_no_apply target on Host. Never both: two definitions of one symbol do not
 * link. An image that does neither does not link.
 *
 * Thread context only. Neither function may call back into the network settings service.
 */
#ifndef CRUX_NETWORK_SETTINGS_APPLY_PORT_H
#define CRUX_NETWORK_SETTINGS_APPLY_PORT_H

#include <crux/network_settings.h>

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Apply settings to the primary interface at boot, before any management channel starts. Only
 * crux_network_settings_boot() calls it, and nothing else does: a saved change takes effect at the
 * next boot. When valid saved settings exist it calls this with them, and if that returns false it
 * calls it once more with the defaults. In every other case (first boot, no provider, a store error
 * or invalid saved values) it calls it once with the defaults. A false return for the defaults is
 * reported in the boot report and not retried. A product that refuses a value should expect up to
 * two calls.
 *
 * A port that applies nothing, such as the one that CONFIG_CRUX_NETWORK_SETTINGS_NO_APPLY selects,
 * returns false for every call, so the boot report reads applied false and source default.
 *
 * @param settings Borrowed for the call.
 * @return false if the interface refused the settings or the port applies nothing.
 */
bool crux_network_settings_port_apply(const crux_network_settings_t *settings);

/**
 * Report the settings now in use on the interface, for crux_network_settings_get(), which calls it
 * with no service lock held and may run on the server thread, so it must not wait on storage or on
 * the network. Returns false while the interface has no IPv4 address. A port that cannot read the
 * interface returns false, which a client sees as no running values.
 *
 * @param[out] settings The service ignores it when the function returns false.
 * @return true if the running settings were written.
 */
bool crux_network_settings_port_running(crux_network_settings_t *settings);

#ifdef __cplusplus
}
#endif

#endif
