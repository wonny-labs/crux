/*
 * The event port of the SSH access adapter, as a thin translation onto the public emit. It holds
 * no state and takes no lock of its own. Neither record has a user or a subject: the adapter only
 * knows what the client claimed, and a claim is not a known account. See
 * docs/security-event-contract.md.
 */
#include "crux_ssh_access_port.h"

#include <crux/security_event.h>

#include <string.h>

void crux_ssh_access_port_event(const crux_ssh_access_event_t *event)
{
    crux_security_event_t record;

    if (event == NULL) {
        return;
    }
    memset(&record, 0, sizeof(record));
    /* A type that the table below does not map is recorded as a failure of unknown kind, and not as
     * id 0 with the result OK, which would read as a success. */
    record.id = CRUX_SECURITY_EVENT_ID_EVENT_UNKNOWN;
    record.result = CRUX_SECURITY_EVENT_FAILED;
    /* No default case: the compiler refuses a new type that this table does not map. */
    switch (event->type) {
    case CRUX_SSH_ACCESS_EVENT_AUTH_LIMIT:
        record.id = CRUX_SECURITY_EVENT_ID_SSH_AUTH_LIMIT;
        record.result = CRUX_SECURITY_EVENT_LIMIT;
        break;
    case CRUX_SSH_ACCESS_EVENT_HOST_KEY_MISSING:
        record.id = CRUX_SECURITY_EVENT_ID_SSH_HOST_KEY_MISSING;
        record.result = CRUX_SECURITY_EVENT_FAILED;
        break;
    }
    record.channel = event->channel;
    record.source_length = event->source_length;
    memcpy(record.source, event->source, sizeof(record.source));
    crux_security_event_emit(&record);
}
