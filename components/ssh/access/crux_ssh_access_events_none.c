/*
 * Drops every report of the access adapter, for an image that has no Security events, such as the
 * test images of the provider and the settings probe. An image that has them links
 * crux_ssh_security_events.c instead: see sources.cmake.
 */
#include "crux_ssh_access_port.h"

void crux_ssh_access_port_event(const crux_ssh_access_event_t *event)
{
    (void)event;
}
