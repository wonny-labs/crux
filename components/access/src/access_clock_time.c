/* The clock port over the Time contract. It takes no lock that a permission check could wait on, as
 * the port requires. */
#include "access_port.h"

#include <crux/time.h>

/*
 * crux_monotonic_now fails only for a NULL argument, in an ISR or on a provider error. A failure,
 * or a negative reading, gives CRUX_ACCESS_CLOCK_FAILED, which no reading reaches: INT64_MAX ns is
 * about 9.2e12 ms. The core then refuses a login or a key attempt with NOT_READY, creates no
 * session and leaves every bucket as it was, and a session from before the fault expires.
 * tests/access/clock_fault.c holds this.
 */
uint64_t crux_access_port_now_ms(void)
{
    crux_monotonic_time_t now;
    if (crux_monotonic_now(&now) != CRUX_OK || now.private_ns < 0) {
        return CRUX_ACCESS_CLOCK_FAILED;
    }
    return (uint64_t)now.private_ns / UINT64_C(1000000);
}
