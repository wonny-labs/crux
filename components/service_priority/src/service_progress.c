/* The progress hook of the Crux service threads (<crux/service_priority_zephyr.h>, Experimental).
 *
 * Portable C11 atomics, so that the Host tests the same file. One registration per boot: the first
 * call claims the slot, stores the function and its context, and then publishes them with a release
 * store; a report reads the flag with an acquire load before it reads them. A report takes no lock
 * and never waits, so a service thread never blocks on its supervisor's registration. */
#include "service_priority.h"

#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>

static atomic_flag claimed = ATOMIC_FLAG_INIT;
static atomic_bool published;
static crux_service_progress_t progress_callback;
static void *progress_context;

crux_status_t crux_service_progress_register(crux_service_progress_t callback, void *context)
{
    if (callback == NULL) {
        return CRUX_ERR_INVALID_ARGUMENT;
    }
    if (atomic_flag_test_and_set_explicit(&claimed, memory_order_acq_rel)) {
        return CRUX_ERR_BUSY;
    }
    progress_callback = callback;
    progress_context = context;
    atomic_store_explicit(&published, true, memory_order_release);
    return CRUX_OK;
}

void crux_service_progress_report(crux_service_thread_t thread)
{
    if ((unsigned)thread >= (unsigned)CRUX_SERVICE_THREAD_COUNT ||
        !atomic_load_explicit(&published, memory_order_acquire)) {
        return;
    }
    progress_callback(thread, progress_context);
}

#ifdef CRUX_SERVICE_PROGRESS_TESTING
/* Test composition only: forgets the registration, with no report running. */
void crux_service_progress_test_reset(void);
void crux_service_progress_test_reset(void)
{
    atomic_store_explicit(&published, false, memory_order_relaxed);
    progress_callback = NULL;
    progress_context = NULL;
    atomic_flag_clear_explicit(&claimed, memory_order_release);
}
#endif
