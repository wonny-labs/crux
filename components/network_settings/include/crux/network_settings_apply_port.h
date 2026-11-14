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
 * The product implements both, or sets CONFIG_CRUX_NETWORK_SETTINGS_NO_APPLY for the module's port
 * that applies nothing and reports no running values, never both with
 * CONFIG_CRUX_NETWORK_SETTINGS_NO_APPLY: two definitions of one symbol do not link. An image that
 * does neither does not link.
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
 * Apply settings to the primary interface, once, at boot, before any management channel starts.
 * crux_network_settings_boot() calls it with the saved settings. If it returns false, the boot
 * calls it again with the defaults, so a product that refuses a value should expect two calls.
 * Nothing else calls it: a saved change takes effect at the next boot.
 *
 * @param settings Borrowed for the call.
 * @return false if the interface refused the settings.
 */
bool crux_network_settings_port_apply(const crux_network_settings_t *settings);

/**
 * Report the settings now in use on the interface, for crux_network_settings_get(), which calls it
 * with no service lock held and may run on the server thread, so it must not wait on storage or on
 * the network. Returns false while the interface has no IPv4 address. A port that cannot read the
 * interface returns false, which a client sees as no running values.
 *
 * @param[out] settings Written only when the function returns true.
 * @return true if the running settings were written.
 */
bool crux_network_settings_port_running(crux_network_settings_t *settings);

#ifdef __cplusplus
}
#endif

#endif
