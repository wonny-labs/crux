/* The log text of a console that shares its UART with Logging (CONFIG_CRUX_CLI_CONSOLE_UART_SHARED).
 *
 * A Logging backend formats each message into a stage and puts it in a bounded queue; the console
 * thread takes entries out between its reads and prints them. Portable, so that it is tested on the
 * Host. It holds no lock of its own: the caller holds one lock around each queue call, and the stage
 * belongs to the one thread that formats. It never waits and never allocates.
 *
 * Drop policy: drop new. An entry that does not fit is dropped and counted, and nothing already
 * queued is touched. The count becomes one line, "--- N log messages dropped ---", in the queue's
 * order: it is put ahead of the next entry that fits, or handed to the reader when the queue is
 * empty, so that it stands where the gap is.
 */
#ifndef CRUX_CLI_CONSOLE_LOG_H
#define CRUX_CLI_CONSOLE_LOG_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* The longest entry, line ends included: one formatted message, or the drop line. A message that is
 * longer is cut and ends with "...". The console's buffer for one entry has this size. */
#define CRUX_CLI_LOG_ENTRY_MAX 512u
/* The smallest queue: room for the drop line and a longest entry, each with its header. */
#define CRUX_CLI_LOG_QUEUE_MIN 1024u

typedef struct {
    char bytes[CRUX_CLI_LOG_ENTRY_MAX];
    size_t length;
    bool truncated;
    bool started;
} crux_cli_log_stage_t;

typedef struct {
    uint8_t *storage;
    size_t capacity;
    size_t head;      /* The first byte of the oldest entry. */
    size_t used;      /* Bytes in use, headers included. */
    uint32_t dropped; /* Entries dropped since the last drop line, saturating. */
} crux_cli_log_queue_t;

/* Starts a message. */
void crux_cli_log_stage_begin(crux_cli_log_stage_t *stage);
/* Adds formatted text. A CR is left out, because the console sends its own line ends; any other
 * control byte but LF and TAB becomes '?', so that a message cannot carry a terminal sequence onto
 * the console. Text past the limit is dropped, and the message is marked as cut. */
void crux_cli_log_stage_append(crux_cli_log_stage_t *stage, const void *data, size_t length);
/* Ends the message with a LF, or with "...\n" when it was cut. Returns its length, or 0 when nothing
 * was added since the begin. */
size_t crux_cli_log_stage_finish(crux_cli_log_stage_t *stage);

/* False when the storage is missing or smaller than CRUX_CLI_LOG_QUEUE_MIN. */
bool crux_cli_log_queue_init(crux_cli_log_queue_t *queue, void *storage, size_t capacity);
/* Puts one entry of 1 to CRUX_CLI_LOG_ENTRY_MAX bytes, whole or not at all. False means dropped and
 * counted. */
bool crux_cli_log_queue_put(crux_cli_log_queue_t *queue, const char *text, size_t length);
/* Counts entries that were lost before they reached the queue. */
void crux_cli_log_queue_add_dropped(crux_cli_log_queue_t *queue, uint32_t count);
/* Copies the oldest entry into text, or the drop line when only a count is left, and returns its
 * length; 0 when there is nothing. With a capacity below CRUX_CLI_LOG_ENTRY_MAX it takes nothing. */
size_t crux_cli_log_queue_get(crux_cli_log_queue_t *queue, char *text, size_t capacity);

#endif
