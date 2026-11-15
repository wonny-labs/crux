/* The event port of the session module: what it reports when it refuses a request for its
 * request-forgery checks. Private to the module, like web_session_port.h.
 *
 * A report holds the kind of refusal, where the request came from, and the name of the session's
 * account when a session was found. It holds no byte of the request: not the Origin, not the token
 * and not any other header, so a provider cannot record client text by mistake.
 *
 * The module reports a refusal on the server thread, and at most CRUX_WEB_SESSION_FORGERY_EVENTS
 * times per kind in each CRUX_WEB_SESSION_FORGERY_WINDOW_MS, so a provider is not called once for
 * every request of a flood. components/web/session/web_session_security_events.c is the provider
 * over the security events, and tests/web/session/session_test.c is the recording fake.
 */
#ifndef CRUX_WEB_SESSION_EVENT_PORT_H
#define CRUX_WEB_SESSION_EVENT_PORT_H

#include <crux/access.h>

#include <stdint.h>

typedef enum {
    CRUX_WEB_SESSION_EVENT_CSRF_REJECTED,  /* The X-XSRF-TOKEN header was missing or wrong. */
    CRUX_WEB_SESSION_EVENT_ORIGIN_REJECTED /* The Origin header was missing or not accepted. */
} crux_web_session_event_type_t;

typedef struct {
    crux_web_session_event_type_t type;
    uint8_t channel;       /* Always the web channel, as crux_access_origin_t names it. */
    uint8_t source_length; /* The peer's address as the web adapter gave it, or zero. */
    uint8_t source[16];
    /* The account of the session that the request carried, or empty. A login's Origin is checked
     * before there is a session, so its report has none. */
    char user[CRUX_ACCESS_NAME_SIZE];
} crux_web_session_event_t;

/* Reports a refusal. Server thread. It must return quickly and cannot fail the request. */
void crux_web_session_port_event(const crux_web_session_event_t *event);

#endif /* CRUX_WEB_SESSION_EVENT_PORT_H */
