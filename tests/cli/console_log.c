/* The queue and the stage between Logging and a console on a shared UART: entries whole or not at
 * all, drop new with a count, the drop line in the queue's order, a cut message and the text rules.
 */
#include "cli_test.h"
#include "logging_console_queue.h"

#include <stdint.h>

static uint8_t storage[CRUX_LOG_QUEUE_MIN];
static crux_log_queue_t queue;
static char text[CRUX_LOG_QUEUE_ENTRY_MAX + 1];

static void begin(void)
{
    memset(storage, 0xA5, sizeof(storage));
    CHECK(crux_log_queue_init(&queue, storage, sizeof(storage)));
}

static bool put(const char *line)
{
    return crux_log_queue_put(&queue, line, strlen(line));
}

/* The next entry as text, or "" when there is none. */
static const char *get(void)
{
    size_t length = crux_log_queue_get(&queue, text, CRUX_LOG_QUEUE_ENTRY_MAX);
    CHECK(length <= CRUX_LOG_QUEUE_ENTRY_MAX);
    text[length <= CRUX_LOG_QUEUE_ENTRY_MAX ? length : CRUX_LOG_QUEUE_ENTRY_MAX] = '\0';
    return text;
}

static void init_refuses_a_small_queue(void)
{
    crux_log_queue_t other;
    CHECK(!crux_log_queue_init(&other, NULL, sizeof(storage)));
    CHECK(!crux_log_queue_init(&other, storage, CRUX_LOG_QUEUE_MIN - 1u));
    CHECK(crux_log_queue_init(&other, storage, CRUX_LOG_QUEUE_MIN));
    CHECK_TEXT(get(), "");
}

static void entries_come_out_in_order(void)
{
    begin();
    CHECK_TEXT(get(), "");
    CHECK(put("one\n"));
    CHECK(put("two\n"));
    CHECK_TEXT(get(), "one\n");
    CHECK(put("three\n"));
    CHECK_TEXT(get(), "two\n");
    CHECK_TEXT(get(), "three\n");
    CHECK_TEXT(get(), "");
}

static void entries_wrap_around_the_storage(void)
{
    /* Many more bytes than the storage holds, so every offset of the wrap is crossed. */
    begin();
    char line[40];
    for (unsigned index = 0; index < 400u; ++index) {
        int length = snprintf(line, sizeof(line), "entry %u of the wrap test\n", index);
        CHECK(crux_log_queue_put(&queue, line, (size_t)length));
        CHECK_TEXT(get(), line);
    }
    CHECK(queue.used == 0u);
}

static void a_full_queue_drops_new_entries_and_keeps_old_ones(void)
{
    begin();
    char line[100];
    memset(line, 'x', sizeof(line) - 2u);
    line[sizeof(line) - 2u] = '\n';
    line[sizeof(line) - 1u] = '\0';
    unsigned admitted = 0;
    while (put(line)) {
        admitted += 1;
    }
    CHECK(admitted == CRUX_LOG_QUEUE_MIN / (2u + 99u));
    CHECK(queue.dropped == 1u);
    CHECK(!put("late\n"));
    CHECK(queue.dropped == 2u);
    /* The old entries are all there, then the count, and the late ones are gone. */
    for (unsigned index = 0; index < admitted; ++index) {
        CHECK_TEXT(get(), line);
    }
    CHECK_TEXT(get(), "--- 2 log messages dropped ---\n");
    CHECK_TEXT(get(), "");
    CHECK(queue.dropped == 0u);
}

static void the_drop_line_stands_where_the_gap_is(void)
{
    begin();
    char line[100];
    memset(line, 'y', sizeof(line) - 2u);
    line[sizeof(line) - 2u] = '\n';
    line[sizeof(line) - 1u] = '\0';
    while (put(line)) {
    }
    /* Room for the next entry, but not for the next entry and the count together: still dropped. */
    CHECK_TEXT(get(), line);
    CHECK(!put(line));
    CHECK(queue.dropped == 2u);
    /* With room for both, the count goes in first, then the entry. */
    CHECK_TEXT(get(), line);
    CHECK(put("after the gap\n"));
    CHECK(queue.dropped == 0u);
    while (strcmp(get(), line) == 0) {
    }
    CHECK_TEXT(text, "--- 2 log messages dropped ---\n");
    CHECK_TEXT(get(), "after the gap\n");
    CHECK_TEXT(get(), "");
}

static void losses_before_the_queue_are_counted_too(void)
{
    begin();
    crux_log_queue_add_dropped(&queue, 3u);
    CHECK_TEXT(get(), "--- 3 log messages dropped ---\n");
    CHECK_TEXT(get(), "");
    crux_log_queue_add_dropped(&queue, 2u);
    CHECK(put("next\n"));
    CHECK_TEXT(get(), "--- 2 log messages dropped ---\n");
    CHECK_TEXT(get(), "next\n");
    /* The count saturates rather than wrapping to a small number. */
    crux_log_queue_add_dropped(&queue, UINT32_MAX);
    crux_log_queue_add_dropped(&queue, 5u);
    CHECK_TEXT(get(), "--- 4294967295 log messages dropped ---\n");
}

static void entries_out_of_range_are_dropped(void)
{
    begin();
    char line[CRUX_LOG_QUEUE_ENTRY_MAX + 1u];
    memset(line, 'z', sizeof(line));
    CHECK(!crux_log_queue_put(&queue, line, 0u));
    CHECK(!crux_log_queue_put(&queue, line, sizeof(line)));
    CHECK(queue.dropped == 2u);
    CHECK(crux_log_queue_put(&queue, line, CRUX_LOG_QUEUE_ENTRY_MAX));
    CHECK(queue.dropped == 0u);
    /* A reader whose buffer cannot hold a longest entry takes nothing. */
    char small[CRUX_LOG_QUEUE_ENTRY_MAX - 1u];
    CHECK(crux_log_queue_get(&queue, small, sizeof(small)) == 0u);
    CHECK_TEXT(get(), "--- 2 log messages dropped ---\n");
    CHECK(crux_log_queue_get(&queue, text, CRUX_LOG_QUEUE_ENTRY_MAX) == CRUX_LOG_QUEUE_ENTRY_MAX);
    CHECK(queue.used == 0u);
}

static void the_stage_keeps_text_and_ends_each_message(void)
{
    crux_log_stage_t stage;
    crux_log_stage_begin(&stage);
    CHECK(crux_log_stage_finish(&stage) == 0u);

    crux_log_stage_begin(&stage);
    crux_log_stage_append(&stage, "[00:00:01.000,000] ", 19u);
    crux_log_stage_append(&stage, "<inf> app: ready", 16u);
    size_t length = crux_log_stage_finish(&stage);
    CHECK(length == 36u);
    CHECK(memcmp(stage.bytes, "[00:00:01.000,000] <inf> app: ready\n", length) == 0);

    /* A line end of its own is kept, and a CR before it is left out. */
    crux_log_stage_begin(&stage);
    crux_log_stage_append(&stage, "a\r\nb\r\n", 6u);
    length = crux_log_stage_finish(&stage);
    CHECK(length == 4u);
    CHECK(memcmp(stage.bytes, "a\nb\n", length) == 0);

    /* No terminal sequence reaches the console: ESC, BEL and DEL become '?', TAB and UTF-8 stay. */
    crux_log_stage_begin(&stage);
    crux_log_stage_append(&stage, "\x1b[2J\a\t\x7f\xc3\xa9", 9u);
    length = crux_log_stage_finish(&stage);
    CHECK(length == 10u);
    CHECK(memcmp(stage.bytes, "?[2J?\t?\xc3\xa9\n", length) == 0);
}

static void a_long_message_is_cut_and_marked(void)
{
    crux_log_stage_t stage;
    char chunk[100];
    memset(chunk, 'm', sizeof(chunk));
    crux_log_stage_begin(&stage);
    for (unsigned index = 0; index < 10u; ++index) {
        crux_log_stage_append(&stage, chunk, sizeof(chunk));
    }
    size_t length = crux_log_stage_finish(&stage);
    CHECK(length == CRUX_LOG_QUEUE_ENTRY_MAX);
    CHECK(stage.truncated);
    CHECK(memcmp(&stage.bytes[length - 4u], "...\n", 4u) == 0);
    CHECK(stage.bytes[length - 5u] == 'm');
    /* The cut message fits the queue whole. */
    begin();
    CHECK(crux_log_queue_put(&queue, stage.bytes, length));
    CHECK(crux_log_queue_get(&queue, text, CRUX_LOG_QUEUE_ENTRY_MAX) == length);
}

int main(void)
{
    init_refuses_a_small_queue();
    entries_come_out_in_order();
    entries_wrap_around_the_storage();
    a_full_queue_drops_new_entries_and_keeps_old_ones();
    the_drop_line_stands_where_the_gap_is();
    losses_before_the_queue_are_counted_too();
    entries_out_of_range_are_dropped();
    the_stage_keeps_text_and_ends_each_message();
    a_long_message_is_cut_and_marked();
    return cli_test_finish("cli console log");
}
