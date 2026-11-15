/**
 * @file
 * @brief Start the status and configuration routes of the management web server.
 *
 * Status: Experimental (ADR-0001 decision 4). It has no Zephyr composition outside tests/ yet, and
 * a change is listed in the release notes.
 *
 * This is ordinary service API, not a composition interface: it binds nothing to Zephyr, so it has
 * no `_zephyr` name. A product links crux::web_management, which the Zephyr module defines under
 * CONFIG_CRUX_WEB_MANAGEMENT, and compiles the route sources that the build lists in
 * CRUX_WEB_MANAGEMENT_ROUTES, CRUX_WEB_MANAGEMENT_NETWORK_ROUTES and
 * CRUX_WEB_MANAGEMENT_REBOOT_ROUTES (components/web/management/sources.cmake) into its route table,
 * so that a route that is not named is not served. The routes call the status and configuration
 * services with the session that the web core found, and add nothing to what those services decide:
 *
 * - GET /api/v1/status lists the status items this session may see.
 * - GET /api/v1/config lists the configuration parameters this session may see.
 * - GET and PUT /api/v1/config/{name} read and update one parameter, in memory.
 * - POST /api/v1/config/save queues a save on one bounded worker, and the list reports its outcome.
 *
 * The account routes are those of <crux/web_session.h>. See docs/web-management-apis.md.
 *
 * Order, for a product's start code (ADR-0004 section 3): crux_web_management_init() runs after the
 * services have started, before crux_web_start(), and on one thread.
 * crux_web_management_start_worker() follows it.
 */
#ifndef CRUX_WEB_MANAGEMENT_API_H
#define CRUX_WEB_MANAGEMENT_API_H

#include <crux/web.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Reset the save state and take the lock and signal of the worker. After the services have started,
 * before crux_web_start(), and on one thread.
 *
 * @retval CRUX_WEB_ERR_FAILED The lock or the worker's signal could not be created.
 */
crux_web_result_t crux_web_management_init(void);

/** Start the one worker thread that runs configuration saves, at low priority. After the init. */
crux_web_result_t crux_web_management_start_worker(void);

/**
 * Whether a configuration save is queued or running, for a service that must not cut one short,
 * such as the reboot service's wait. Takes no session and records nothing. A lock that does not
 * come in time reads as pending, the safe answer. Before crux_web_management_init() there is no
 * save to wait for.
 *
 * @return True while a save that a session queued has not ended.
 */
bool crux_web_management_save_pending(void);

#ifdef __cplusplus
}
#endif

#endif /* CRUX_WEB_MANAGEMENT_API_H */
