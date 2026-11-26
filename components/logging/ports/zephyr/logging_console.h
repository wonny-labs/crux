/* Private: the Logging backend of a console that shares its UART
 * (CONFIG_CRUX_LOGGING_CONSOLE_BACKEND), as the console's start sees it. Plain functions and no CLI
 * type, so that Logging does not depend on the command line; the start copies them into the
 * console's log source. See logging_console_backend.c. */
#ifndef CRUX_LOGGING_CONSOLE_H
#define CRUX_LOGGING_CONSOLE_H

#include <stddef.h>

/* The longest entry that next() hands out. The console's buffer for one entry has this size. */
#define CRUX_LOGGING_CONSOLE_TEXT_MAX 512u

typedef struct {
    /* Copies the oldest queued message, which ends with a LF, and returns its length; 0 when there
     * is none. Never waits. source is unused. */
    size_t (*next)(void *source, char *text, size_t capacity);
    /* Called by the console's thread before it opens the port: log text stops going straight to
     * the UART and goes to the queue. Thread context. source is unused. */
    void (*attach)(void *source);
    /* Called by the console's thread when it has no port open after an attach: an open failed, or
     * the port was closed after a failure. What is queued goes out once, straight to the UART, and
     * later log text does too, until the next attach. Thread context; it may wait while it writes
     * the queue. source is unused. */
    void (*detach)(void *source);
} crux_logging_console_t;

extern const crux_logging_console_t crux_logging_console;

#endif
