/* A recording provider of the access adapter's event port, for the Host tests that link the
 * adapter. */
#ifndef CRUX_SSH_PORT_FAKE_H
#define CRUX_SSH_PORT_FAKE_H

#include "crux_ssh_access_port.h"

#include <stdbool.h>
#include <stddef.h>

/* The most reports it keeps. Later ones are dropped, and ssh_port_fake_overflowed() says so. */
#define SSH_PORT_FAKE_EVENTS_MAX 16u

/* Forgets every report. */
void ssh_port_fake_reset(void);
/* Reports kept so far, in order. The pointer is valid until the next reset. */
size_t ssh_port_fake_count(void);
const crux_ssh_access_event_t *ssh_port_fake_event(size_t index);
/* How many reports are of this type. */
size_t ssh_port_fake_count_of(crux_ssh_access_event_type_t type);
/* True if a report came after the fake was full. */
bool ssh_port_fake_overflowed(void);

#endif /* CRUX_SSH_PORT_FAKE_H */
