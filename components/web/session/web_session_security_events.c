/*
 * The event port of the session module, as a thin translation onto the public emit. It holds no
 * state and takes no lock of its own: the module limits how often it reports. A record has no
 * subject, because the report holds no client text, and the user is the account of a session that
 * the server itself issued. See docs/security-event-contract.md.
 */
#include "web_session_event_port.h"

#include <crux/security_event.h>

#include <string.h>

void crux_web_session_port_event(const crux_web_session_event_t *event)
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
    switch (event->type) {
    case CRUX_WEB_SESSION_EVENT_CSRF_REJECTED:
        record.id = CRUX_SECURITY_EVENT_ID_WEB_CSRF_REJECTED;
        record.result = CRUX_SECURITY_EVENT_DENIED;
        break;
    case CRUX_WEB_SESSION_EVENT_ORIGIN_REJECTED:
        record.id = CRUX_SECURITY_EVENT_ID_WEB_ORIGIN_REJECTED;
        record.result = CRUX_SECURITY_EVENT_DENIED;
        break;
    }
    record.channel = event->channel;
    record.source_length = event->source_length;
    memcpy(record.source, event->source, sizeof(record.source));
    /* An empty name is no user, and not a user of no characters, which the event rule refuses. */
    record.user = event->user[0] != '\0' ? event->user : NULL;
    crux_security_event_emit(&record);
}
