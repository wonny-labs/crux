/**
 * @file
 * @brief What the web management module keeps private: the body size and the counters.
 *
 * Internal to Crux, like crux_web_session.h: a project never sees this header. The start calls and
 * the save query are public, in <crux/web_management.h>, which this header includes and which also
 * lists the routes. A composition compiles these sources with the web core and names
 * web_management_routes.c to crux_web_routes(). The routes are described in openapi.yaml, the
 * management API specification, and docs/web-management-apis.md holds their design.
 */
#ifndef CRUX_WEB_MANAGEMENT_H
#define CRUX_WEB_MANAGEMENT_H

#include "crux_web_adapter.h"

#include <crux/web_management.h>
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#ifndef CRUX_WEB_MANAGEMENT_BODY_MAX
/**
 * Bytes of the largest response body of these routes, which is one document held in one buffer. A
 * list or report that does not fit gets 503 with the code `not_ready`. The web core's
 * CRUX_WEB_RESPONSE_MAX is the same size by default, and a composition that raises one raises both.
 */
#define CRUX_WEB_MANAGEMENT_BODY_MAX 4096u
#endif

/** Counters, for tests and the design's measurements. */
typedef struct {
    uint32_t saves_queued;   /**< Saves accepted for the worker. */
    uint32_t saves_busy;     /**< Saves refused because one was queued or running. */
    uint32_t saves_finished; /**< Saves the worker ended, whatever their result. */
} crux_web_management_stats_t;

/** A snapshot of the counters. */
void crux_web_management_stats_get(crux_web_management_stats_t *stats);

#ifdef __cplusplus
}
#endif

#endif /* CRUX_WEB_MANAGEMENT_H */
