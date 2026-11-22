#ifndef HELLO_CRUX_H
#define HELLO_CRUX_H

/*
 * The portable part of the sample. It uses only the public Crux API (<crux/time.h>), so the
 * Zephyr application and the Linux Host program compile the same file.
 */

/**
 * Prepare Crux Time and describe its realtime clock in one word.
 *
 * @return "unset" when no realtime value has been established yet (the state right after
 *         initialisation), "set" when one has, or NULL when Crux Time could not be used.
 */
const char *hello_crux_time_state(void);

#endif
