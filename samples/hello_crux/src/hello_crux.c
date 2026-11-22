#include "hello_crux.h"

#include <crux/status.h>
#include <crux/time.h>

#include <stddef.h>

const char *hello_crux_time_state(void)
{
    if (crux_realtime_init() != CRUX_OK) {
        return NULL;
    }

    /* Initialisation leaves the clock ready but unset: Crux never invents a time of day. */
    crux_realtime_t now;
    const crux_status_t status = crux_realtime_now(&now);
    if (status == CRUX_ERR_NO_DATA) {
        return "unset";
    }
    return status == CRUX_OK ? "set" : NULL;
}
