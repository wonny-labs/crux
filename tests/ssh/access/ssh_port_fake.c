#include "ssh_port_fake.h"

#include <stdbool.h>

static crux_ssh_access_event_t events[SSH_PORT_FAKE_EVENTS_MAX];
static size_t count;
static bool overflowed;

void crux_ssh_access_port_event(const crux_ssh_access_event_t *event)
{
    if (event == NULL) {
        return;
    }
    if (count == SSH_PORT_FAKE_EVENTS_MAX) {
        overflowed = true;
        return;
    }
    events[count++] = *event;
}

void ssh_port_fake_reset(void)
{
    count = 0;
    overflowed = false;
}

size_t ssh_port_fake_count(void)
{
    return count;
}

const crux_ssh_access_event_t *ssh_port_fake_event(size_t index)
{
    return index < count ? &events[index] : NULL;
}

size_t ssh_port_fake_count_of(crux_ssh_access_event_type_t type)
{
    size_t found = 0;

    for (size_t i = 0; i < count; ++i) {
        if (events[i].type == type) {
            ++found;
        }
    }
    return found;
}

bool ssh_port_fake_overflowed(void)
{
    return overflowed;
}
