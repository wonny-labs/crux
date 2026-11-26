#ifndef CRUX_SERVICE_PRIORITY_PRIVATE_H
#define CRUX_SERVICE_PRIORITY_PRIVATE_H
/*
 * Private: places a Crux service worker at its per-service priority (ADR-0002 P3), and reports its
 * progress to the product's supervisor. Not a Thread feature and not a consumer interface. See
 * docs/thread-sync.md#priority-map-of-crux-threads.
 *
 * Each worker is a LOW-class Crux Thread. On Zephyr, where the target that compiles the worker
 * links crux_service_priority_placement and so has CRUX_SERVICE_PRIORITY_PLACEMENT, its entry calls
 * crux_service_priority_place() first, and the worker then runs at its
 * CONFIG_CRUX_<SERVICE>_<ROLE>_PRIORITY; each pass of its loop calls crux_service_progress_report().
 * On the Linux Host nothing is called, as Host Thread has no priorities and no supervisor.
 *
 * The thread identifiers are public in <crux/service_priority_zephyr.h> (Experimental), with the
 * registration of the progress function.
 */
#include <crux/service_priority_zephyr.h>

/* Sets the calling thread's priority to the setting of `thread`. An unknown one changes nothing. */
void crux_service_priority_place(crux_service_thread_t thread);

/* Calls the registered progress function, if any, on the calling thread. An unknown identifier
 * calls nothing. Never waits, and takes no lock. */
void crux_service_progress_report(crux_service_thread_t thread);
#endif
