#ifndef CRUX_SERVICE_PRIORITY_ZEPHYR_H
#define CRUX_SERVICE_PRIORITY_ZEPHYR_H

/**
 * @file
 * @brief Progress of Crux's service threads, for a product's supervisor. A composition interface.
 *
 * Status: Experimental (ADR-0001 decision 4). A change is listed in the release notes.
 *
 * A product reaches it by linking crux::service_priority_zephyr, which a native-free consumer check
 * rejects: only the platform composition, which owns the watchdog, includes it. It publishes the
 * identifiers of the Crux service threads and one registration. The header includes no Zephyr
 * header and names no Zephyr type.
 *
 * What a report means. Each service thread calls the registered function, with its identifier, once
 * per pass of its loop. A pass waits at most about a second for work, so an idle thread reports at
 * least that often. A pass that does work reports when the work ends: the work's own bounds apply,
 * such as a password derivation, a save to storage or the reboot service's settle wait, which
 * reports at each of its steps. A thread that is not started never reports. The HTTP server thread
 * and the SSH threads are not Crux service threads, so they do not report here. A report shows that
 * the thread passed through its loop; it does not show that the service did what it should.
 *
 * The intended use is one task watchdog channel per started thread, fed from the function. See
 * docs/composition-interfaces.md and the supervision recipe it links.
 */

#include <crux/status.h>

#ifdef __cplusplus
extern "C" {
#endif

/** The Crux service threads. The values are stable within a release and start at zero. */
typedef enum {
    CRUX_SERVICE_THREAD_SECURITY_EVENT_DRAIN,    /**< crux_security_event_start() */
    CRUX_SERVICE_THREAD_REBOOT_WORKER,           /**< crux_reboot_start_worker() */
    CRUX_SERVICE_THREAD_NETWORK_SETTINGS_WORKER, /**< crux_network_settings_start_worker() */
    CRUX_SERVICE_THREAD_WEB_SESSION_WORKER,      /**< crux_web_session_start_worker() */
    CRUX_SERVICE_THREAD_WEB_MANAGEMENT_WORKER,   /**< crux_web_management_start_worker() */
    CRUX_SERVICE_THREAD_CLI_CONSOLE,             /**< crux_cli_serial_start() */
    CRUX_SERVICE_THREAD_COUNT                    /**< The number of identifiers, not a thread. */
} crux_service_thread_t;

/**
 * A progress report. Called on the reporting service thread, possibly on several threads at once.
 * It must return quickly: no wait, no lock that a Crux service may hold, and no call into a Crux
 * service. Feeding a task watchdog channel is the intended work.
 * @param thread The thread that passed through its loop.
 * @param context The registered context, unchanged.
 */
typedef void (*crux_service_progress_t)(crux_service_thread_t thread, void *context);

/**
 * Register the one progress function for this boot. Thread context. Call it before the services
 * start, so that the first pass of each thread reports; a later call is safe, and each thread reports
 * from its next pass.
 * @param callback Called for every report.
 * @param context Passed unchanged to callback; kept for the program's life.
 * @retval CRUX_OK Registered.
 * @retval CRUX_ERR_INVALID_ARGUMENT callback is NULL.
 * @retval CRUX_ERR_BUSY A function is already registered; it stays.
 */
crux_status_t crux_service_progress_register(crux_service_progress_t callback, void *context);

#ifdef __cplusplus
}
#endif

#endif /* CRUX_SERVICE_PRIORITY_ZEPHYR_H */
