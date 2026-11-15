/**
 * @file
 * @brief Start the login and session module of the management web server.
 *
 * Status: Experimental (ADR-0001 decision 4). It has no Zephyr composition outside tests/ yet, and
 * a change is listed in the release notes.
 *
 * This is ordinary service API, not a composition interface: it binds nothing to Zephyr, so it has
 * no `_zephyr` name. A product links crux::web_session, which the Zephyr module defines under
 * CONFIG_CRUX_WEB_SESSION, and compiles the route source that the build lists in
 * CRUX_WEB_SESSION_ROUTES (components/web/session/sources.cmake) into its route table, so that a
 * route that is not named is not served. The module implements crux_web_authenticate_t over
 * crux_access, and the session routes of the management API:
 *
 * - POST /api/v1/session queues a login on one bounded worker and returns an attempt identifier.
 * - GET /api/v1/session/attempt/{id} collects the result, and a success sets the cookies.
 * - DELETE /api/v1/session logs out, GET /api/v1/session/me reads the current user, and
 *   POST /api/v1/session/me/password queues a change of one's own password.
 *
 * The server thread never verifies a password. See docs/web-session.md.
 *
 * Order, for a product's start code (ADR-0004 section 3): crux_web_session_init() runs after
 * crux_access_init() and before crux_web_start(), on one thread, and
 * crux_web_session_start_worker() follows it.
 */
#ifndef CRUX_WEB_SESSION_API_H
#define CRUX_WEB_SESSION_API_H

#include <crux/web.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/** The settings of the session module. Strings are borrowed for the program's life. */
typedef struct {
    /**
     * "https". "http" is refused unless the build defines CRUX_WEB_SESSION_PLAIN_HTTP_FOR_TESTS,
     * which only a native_sim test image over plain HTTP does.
     */
    const char *scheme;
    /**
     * Exact Origin values to accept, compared whole. With none, the only accepted Origin is the
     * scheme, "://" and the request's own Host.
     */
    const char *const *origins;
    size_t origin_count;
} crux_web_session_config_t;

/**
 * Reset the session and attempt tables and take the settings. Before crux_web_start(), on one
 * thread, and after crux_access_init().
 *
 * @retval CRUX_WEB_ERR_INVALID_ARGUMENT The settings are missing or the scheme is neither form.
 * @retval CRUX_WEB_ERR_FAILED The lock or the worker's signal could not be created.
 */
crux_web_result_t crux_web_session_init(const crux_web_session_config_t *config);

/** Start the one worker thread that verifies passwords, at low priority. After the init. */
crux_web_result_t crux_web_session_start_worker(void);

/**
 * The crux_web_authenticate_t of an image, to be named as crux_web_config_t.authenticate with a
 * NULL context. It reads the crux_session cookie, and on any method but GET it also checks Origin
 * and the X-XSRF-TOKEN header, and refreshes the session's idle timer. It never waits on storage or
 * a password. With no authentication function in crux_web_config_t, every route that is not
 * public answers 503.
 */
crux_web_auth_t crux_web_session_authenticate(const crux_web_request_head_t *head,
                                              crux_access_session_t *session, void *context);

#ifdef __cplusplus
}
#endif

#endif /* CRUX_WEB_SESSION_API_H */
