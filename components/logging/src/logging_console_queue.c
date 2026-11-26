#include "logging_console_queue.h"

#include <string.h>

/* Each entry is a two-byte length, least significant byte first, and its text. */
#define ENTRY_HEADER 2u
#define CUT_MARK "...\n"
#define CUT_MARK_LENGTH 4u
/* "--- 4294967295 log messages dropped ---\n" and a spare byte. */
#define DROP_LINE_MAX 48u

_Static_assert(CRUX_LOG_QUEUE_ENTRY_MAX <= 0xFFFFu, "an entry's length must fit its header");
_Static_assert(CRUX_LOG_QUEUE_MIN >= 2u * ENTRY_HEADER + DROP_LINE_MAX + CRUX_LOG_QUEUE_ENTRY_MAX,
               "the smallest queue must hold the drop line and a longest entry");

void crux_log_stage_begin(crux_log_stage_t *stage)
{
    stage->length = 0;
    stage->truncated = false;
    stage->started = false;
}

void crux_log_stage_append(crux_log_stage_t *stage, const void *data, size_t length)
{
    const unsigned char *bytes = data;
    for (size_t index = 0; index < length; ++index) {
        unsigned char byte = bytes[index];
        stage->started = true;
        if (byte == '\r') {
            continue;
        }
        if ((byte < 0x20u && byte != '\n' && byte != '\t') || byte == 0x7Fu) {
            byte = '?';
        }
        /* The last bytes are kept for the line end or the cut mark. */
        if (stage->length >= CRUX_LOG_QUEUE_ENTRY_MAX - CUT_MARK_LENGTH) {
            stage->truncated = true;
            return;
        }
        stage->bytes[stage->length] = (char)byte;
        stage->length += 1;
    }
}

size_t crux_log_stage_finish(crux_log_stage_t *stage)
{
    if (!stage->started) {
        return 0;
    }
    if (stage->truncated) {
        memcpy(&stage->bytes[stage->length], CUT_MARK, CUT_MARK_LENGTH);
        stage->length += CUT_MARK_LENGTH;
    } else if (stage->length == 0 || stage->bytes[stage->length - 1u] != '\n') {
        stage->bytes[stage->length] = '\n';
        stage->length += 1;
    }
    return stage->length;
}

bool crux_log_queue_init(crux_log_queue_t *queue, void *storage, size_t capacity)
{
    if (queue == NULL || storage == NULL || capacity < CRUX_LOG_QUEUE_MIN) {
        return false;
    }
    queue->storage = storage;
    queue->capacity = capacity;
    queue->head = 0;
    queue->used = 0;
    queue->dropped = 0;
    return true;
}

static size_t free_bytes(const crux_log_queue_t *queue)
{
    return queue->capacity - queue->used;
}

static void ring_write(crux_log_queue_t *queue, const void *data, size_t length)
{
    size_t tail = (queue->head + queue->used) % queue->capacity;
    size_t first = queue->capacity - tail < length ? queue->capacity - tail : length;
    memcpy(&queue->storage[tail], data, first);
    memcpy(queue->storage, (const uint8_t *)data + first, length - first);
    queue->used += length;
}

static void ring_read(crux_log_queue_t *queue, void *data, size_t length)
{
    size_t first = queue->capacity - queue->head < length ? queue->capacity - queue->head : length;
    memcpy(data, &queue->storage[queue->head], first);
    memcpy((uint8_t *)data + first, queue->storage, length - first);
    queue->head = (queue->head + length) % queue->capacity;
    queue->used -= length;
}

static void write_entry(crux_log_queue_t *queue, const char *text, size_t length)
{
    const uint8_t header[ENTRY_HEADER] = {(uint8_t)(length & 0xFFu), (uint8_t)(length >> 8u)};
    ring_write(queue, header, sizeof(header));
    ring_write(queue, text, length);
}

static size_t format_drop_line(char *text, uint32_t count)
{
    static const char start[] = "--- ";
    static const char end[] = " log messages dropped ---\n";
    char reversed[10];
    size_t digits = 0;
    do {
        reversed[digits] = (char)('0' + (count % 10u));
        count /= 10u;
        digits += 1;
    } while (count != 0);
    size_t length = sizeof(start) - 1u;
    memcpy(text, start, length);
    while (digits > 0) {
        digits -= 1;
        text[length] = reversed[digits];
        length += 1;
    }
    memcpy(&text[length], end, sizeof(end) - 1u);
    return length + sizeof(end) - 1u;
}

void crux_log_queue_add_dropped(crux_log_queue_t *queue, uint32_t count)
{
    queue->dropped = count > UINT32_MAX - queue->dropped ? UINT32_MAX : queue->dropped + count;
}

bool crux_log_queue_put(crux_log_queue_t *queue, const char *text, size_t length)
{
    if (length == 0 || length > CRUX_LOG_QUEUE_ENTRY_MAX) {
        crux_log_queue_add_dropped(queue, 1u);
        return false;
    }
    size_t needed = ENTRY_HEADER + length;
    char drop_line[DROP_LINE_MAX];
    size_t drop_length = 0;
    if (queue->dropped > 0) {
        drop_length = format_drop_line(drop_line, queue->dropped);
        needed += ENTRY_HEADER + drop_length;
    }
    if (free_bytes(queue) < needed) {
        crux_log_queue_add_dropped(queue, 1u);
        return false;
    }
    if (drop_length > 0) {
        write_entry(queue, drop_line, drop_length);
        queue->dropped = 0;
    }
    write_entry(queue, text, length);
    return true;
}

size_t crux_log_queue_get(crux_log_queue_t *queue, char *text, size_t capacity)
{
    if (capacity < CRUX_LOG_QUEUE_ENTRY_MAX) {
        return 0;
    }
    if (queue->used >= ENTRY_HEADER) {
        uint8_t header[ENTRY_HEADER];
        ring_read(queue, header, sizeof(header));
        size_t length = (size_t)header[0] | ((size_t)header[1] << 8u);
        ring_read(queue, text, length);
        return length;
    }
    if (queue->dropped > 0) {
        size_t length = format_drop_line(text, queue->dropped);
        queue->dropped = 0;
        return length;
    }
    return 0;
}
