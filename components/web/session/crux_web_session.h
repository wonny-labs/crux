/**
 * @file
 * @brief What the session module keeps private: the token sizes and the counters.
 *
 * Internal to Crux, like crux_web_adapter.h: a project never sees this header. The settings type,
 * the start calls and the authentication function are public, in <crux/web_session.h>, which this
 * header includes and which also lists the session routes that the composition names to
 * crux_web_routes(). See docs/web-session.md.
 */
#ifndef CRUX_WEB_SESSION_H
#define CRUX_WEB_SESSION_H

#include "crux_web_adapter.h"

#include <crux/web_session.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Random bytes in a session token, a CSRF token and an attempt identifier. */
#define CRUX_WEB_SESSION_TOKEN_BYTES 32u
/** Characters of one of those in unpadded base64url, without a terminator. */
#define CRUX_WEB_SESSION_TOKEN_TEXT 43u

/** Counters, for tests and the design's measurements. */
typedef struct {
    uint32_t attempts;      /**< Attempts queued. */
    uint32_t busy;          /**< Logins and changes refused with 503 before queueing. */
    uint32_t verified;      /**< Attempts the worker finished. */
    uint32_t expired;       /**< Attempts that expired before anyone collected them. */
    uint32_t sessions;      /**< Sessions handed out by a poll. */
    uint32_t worker_max_ms; /**< Longest attempt on the worker, by the web clock. */
    /** Refused forgery checks not reported as events, because the window's share was used. */
    uint32_t forgery_suppressed;
} crux_web_session_stats_t;

/** A snapshot of the counters. */
void crux_web_session_stats_get(crux_web_session_stats_t *stats);

#ifdef __cplusplus
}
#endif

#endif /* CRUX_WEB_SESSION_H */
