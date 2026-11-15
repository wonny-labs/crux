#ifndef CRUX_WEB_ZEPHYR_H
#define CRUX_WEB_ZEPHYR_H

/**
 * @file
 * @brief Start of the management web server on Zephyr's HTTP server. A composition interface.
 *
 * Status: Experimental (ADR-0001 decision 4). It has no Zephyr composition outside tests/ yet, and
 * a change is listed in the release notes.
 *
 * This is a composition interface, not a portable one (ADR-0004 section 2, rules of
 * docs/composition-interfaces.md). crux_web_start() binds the web core to the Zephyr HTTP server,
 * its sockets and the TLS security tag CONFIG_CRUX_WEB_TLS_SEC_TAG, so only the platform
 * composition of a product calls it, and a native-free consumer check rejects the target that
 * publishes it (crux::web_zephyr). The header includes no Zephyr, vendor or board header, and it
 * declares one function: the settings type crux_web_config_t is in <crux/web.h>, which this header
 * includes, and the routes, the session and the management calls are not here.
 *
 * A product reaches it by linking the CMake target crux::web_zephyr, which adds this include root
 * and crux::web. The provider, the STATIC library that Kconfig selects with CONFIG_CRUX_WEB, is not
 * linked by this target. The route table is the product's, built by crux_web_routes().
 *
 * Order, for a product's start code (ADR-0004 section 3, steps 8 to 10): the services have started,
 * the TLS material is registered under the security tag, then crux_web_session_init() and
 * crux_web_management_init() with their workers, then crux_web_start(), all on one thread.
 * crux_web_start() does not wait for the listener: Zephyr opens it on its own thread, and a
 * listener with no certificate under the tag does not listen, so CRUX_WEB_OK does not mean that a
 * client can connect.
 */

#include <crux/web.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Check the route table that the image linked, take the settings and start serving.
 *
 * @param config The settings. The core copies the structure, so it need not outlive the call, but
 *        the pointer crux_web_config_t.authenticate_context holds is borrowed for the program's
 *        life.
 * @retval CRUX_WEB_OK Zephyr's server was told to start. The listener may not be open yet.
 * @retval CRUX_WEB_ERR_INVALID_ARGUMENT @p config is NULL.
 * @retval CRUX_WEB_ERR_FAILED The route table is malformed or changed by a macro between the
 *         build's scan and the compiler, the C library's fnmatch() does not behave as the server
 *         needs, or http_server_start() of Zephyr returned an error, for example because the server
 *         is already running.
 */
crux_web_result_t crux_web_start(const crux_web_config_t *config);

#ifdef __cplusplus
}
#endif

#endif /* CRUX_WEB_ZEPHYR_H */
