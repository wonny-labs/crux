/*
 * The event port of the SSH access adapter: what it reports and the one function that takes it.
 * Crux code only, and not a stable interface. The port is a function that a composition links by
 * name, so that this adapter names no Security events type and an image with none still builds:
 * crux_ssh_security_events.c records on Security events, and crux_ssh_access_events_none.c drops
 * the report, for an image that has no event core. Exactly one of them is linked.
 */
#ifndef CRUX_SSH_ACCESS_PORT_H
#define CRUX_SSH_ACCESS_PORT_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** The SSH channel, as Access and the Security events number it. */
#define CRUX_SSH_ACCESS_EVENT_CHANNEL 3u
/** Largest source in a report, as in a Security event. */
#define CRUX_SSH_ACCESS_EVENT_SOURCE_MAX 16u

/** What is reported, with the identifier that the security event provider records it as. */
typedef enum {
    /** `ssh.auth_limit`, result LIMIT: a connection ended at max_auth_attempts. Has a source. */
    CRUX_SSH_ACCESS_EVENT_AUTH_LIMIT,
    /** `ssh.host_key_missing`, result FAILED: no host key, so the server must not start. */
    CRUX_SSH_ACCESS_EVENT_HOST_KEY_MISSING
} crux_ssh_access_event_type_t;

/**
 * One report. It holds no client input: the source is the peer's address in the form Access uses
 * (an IPv4 address, or an IPv6 /64), and a user name never goes in, because it is unchecked text
 * from the client.
 */
typedef struct {
    crux_ssh_access_event_type_t type;
    uint8_t channel;       /**< CRUX_SSH_ACCESS_EVENT_CHANNEL. */
    uint8_t source_length; /**< 0, 4 or 8. Zero when no connection is behind the report. */
    uint8_t source[CRUX_SSH_ACCESS_EVENT_SOURCE_MAX];
} crux_ssh_access_event_t;

/**
 * Reports an event. Returns nothing, and nothing the adapter decides depends on it. It runs on the
 * thread of a connection or of the composition's start, and must not wait on storage.
 *
 * @param event Borrowed for the call.
 */
void crux_ssh_access_port_event(const crux_ssh_access_event_t *event);

#ifdef __cplusplus
}
#endif

#endif /* CRUX_SSH_ACCESS_PORT_H */
