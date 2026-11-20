/* The apply port of a composition whose application applies no address. It says it applied
 * nothing, so the boot report reads applied false and source default, and GET shows no running
 * values. */
#include "network_settings_port.h"

bool crux_network_settings_port_apply(const crux_network_settings_t *settings)
{
    (void)settings;
    return false;
}

bool crux_network_settings_port_running(crux_network_settings_t *settings)
{
    (void)settings;
    return false;
}
