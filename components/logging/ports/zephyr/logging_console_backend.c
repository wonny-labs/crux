/* The Logging backend of a console that shares its UART with Logging
 * (CONFIG_CRUX_LOGGING_CONSOLE_BACKEND, which CONFIG_CRUX_CLI_CONSOLE_UART_SHARED selects). It
 * replaces Zephyr's UART backend, which must be off, and writes on the UART of crux-serial0, which
 * the console owns. The console takes the queued text through crux_logging_console
 * (logging_console.h), so Logging does not depend on the CLI.
 *
 * Three modes.
 *
 * DIRECT, at boot and whenever the console has no port open: each message is written with
 * uart_poll_out on the log thread, as Zephyr's UART backend does, so boot output is not held back.
 *
 * QUEUED, from the console's attach, which it makes just before it opens the port: each message is
 * formatted into a stage and put in a bounded queue, whole or not at all (drop new, with a count,
 * logging_console_queue.c). The log thread never waits for the console's output or the UART. The
 * console prints the queue only while it waits for input (components/cli/console/
 * cli_console_serial.c). When an open fails, or the port is closed after a failure, the console
 * detaches: what is queued is written once with uart_poll_out, in order, and the mode is DIRECT
 * again, so log text is not held while the console is down.
 *
 * PANIC, from log_panic(), and final: what is still queued is written once with uart_poll_out, in
 * order, then every later message is written the same way, from whatever context logs it.
 *
 * Locks, and their order. direct_lock, a mutex, is taken first; queue_lock, a spinlock, is
 * innermost, and nothing is taken under it. The log thread holds direct_lock for each message
 * while the mode is DIRECT or QUEUED, and the console's attach and detach take it to change the
 * mode, so a message is handled whole in one mode: the console never opens the port in the middle
 * of a direct line, and no message is queued after a detach has flushed. The log thread can
 * therefore wait for an attach, which only changes the mode, or for a detach, which writes at most
 * the queue's size. queue_lock is held around each queue call, only to copy one entry of at most
 * CRUX_LOG_QUEUE_ENTRY_MAX bytes in or out; on a single core it masks interrupts for that copy.
 * The console thread takes queue_lock alone to read an entry, and holds neither lock while it
 * writes to Crux Serial.
 *
 * The panic path is the only one that can run in an interrupt or a fault. It takes no mutex. It
 * reads the queue only when queue_busy is clear and k_spin_trylock succeeds, and skips it
 * otherwise. On a single core (the RT1060) k_spin_trylock only masks interrupts and cannot fail,
 * because the lock state exists only with CONFIG_SMP; a holder of queue_lock runs with interrupts
 * masked, so a panic can reach the queue in the middle of a copy only through a fault in that
 * copy. queue_busy, set while queue_lock is held, makes such a panic skip the queue, which it would
 * otherwise read half updated, or with CONFIG_SPIN_VALIDATE trip the assertion on a lock that its
 * own CPU holds. With CONFIG_SMP, k_spin_trylock also fails while another CPU holds the lock. The
 * panic path formats with an output of its own (panic_output), so it never shares the buffer of a
 * message that the log thread was formatting.
 *
 * Limits. After a panic, if the system goes on (a product's fatal error handler that does not
 * halt), the console may still write with interrupts while the panic output polls, so bytes can
 * interleave, and two contexts that log after the panic share panic_output, as with Zephyr's
 * backend. A message that the log thread was handling when a panic preempted it is lost. If a
 * port close fails and keeps the handle (CRUX_ERR_BUSY), the console stays attached until a later
 * close succeeds, and log text that does not fit the queue meanwhile is dropped and counted. */
#include "logging_console.h"
#include "logging_console_queue.h"

#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log_backend.h>
#include <zephyr/logging/log_backend_std.h>
#include <zephyr/logging/log_output.h>
#include <zephyr/spinlock.h>
#include <zephyr/sys/atomic.h>

BUILD_ASSERT(CONFIG_CRUX_LOGGING_CONSOLE_QUEUE_BYTES >= CRUX_LOG_QUEUE_MIN,
             "CONFIG_CRUX_LOGGING_CONSOLE_QUEUE_BYTES is below the smallest queue");
BUILD_ASSERT(!IS_ENABLED(CONFIG_LOG_MODE_IMMEDIATE),
             "the console's backend needs deferred logging");
BUILD_ASSERT(CRUX_LOG_QUEUE_ENTRY_MAX == CRUX_LOGGING_CONSOLE_TEXT_MAX,
             "an entry must fit the console's buffer");

enum { MODE_DIRECT, MODE_QUEUED, MODE_PANIC };

static const struct device *const console_uart = DEVICE_DT_GET(DT_ALIAS(crux_serial0));
static atomic_t mode = ATOMIC_INIT(MODE_DIRECT);
static K_MUTEX_DEFINE(direct_lock);
static struct k_spinlock queue_lock;
/* Set while queue_lock is held, for the panic path (above). */
static atomic_t queue_busy;
static uint8_t queue_storage[CONFIG_CRUX_LOGGING_CONSOLE_QUEUE_BYTES];
static crux_log_queue_t queue = {queue_storage, sizeof(queue_storage), 0, 0, 0};
/* Used under direct_lock only, in QUEUED mode. */
static crux_log_stage_t stage;
/* One entry on its way out, written by a detach under direct_lock. */
static char detach_entry[CRUX_LOG_QUEUE_ENTRY_MAX];
/* One entry on its way out, written by the panic path, which may preempt a detach. */
static char panic_entry[CRUX_LOG_QUEUE_ENTRY_MAX];

static k_spinlock_key_t queue_enter(void)
{
    k_spinlock_key_t key = k_spin_lock(&queue_lock);
    atomic_set(&queue_busy, 1);
    return key;
}

static void queue_leave(k_spinlock_key_t key)
{
    atomic_set(&queue_busy, 0);
    k_spin_unlock(&queue_lock, key);
}

static void poll_out(const uint8_t *data, size_t length)
{
    for (size_t index = 0; index < length; ++index) {
        uart_poll_out(console_uart, data[index]);
    }
}

/* A queued entry has LF line ends, and the terminal needs CR LF. */
static void poll_out_entry(const char *text, size_t length)
{
    for (size_t index = 0; index < length; ++index) {
        if (text[index] == '\n') {
            uart_poll_out(console_uart, '\r');
        }
        uart_poll_out(console_uart, (unsigned char)text[index]);
    }
}

static int write_direct(uint8_t *data, size_t length, void *context)
{
    ARG_UNUSED(context);
    poll_out(data, length);
    return (int)length;
}

static int write_stage(uint8_t *data, size_t length, void *context)
{
    ARG_UNUSED(context);
    crux_log_stage_append(&stage, data, length);
    return (int)length;
}

/* Three outputs, one per user of a formatting buffer: the log thread in DIRECT mode, the log
 * thread in QUEUED mode, and the panic path with every message after it. */
static uint8_t direct_buffer[64];
static uint8_t stage_buffer[64];
static uint8_t panic_buffer[64];
LOG_OUTPUT_DEFINE(direct_output, write_direct, direct_buffer, sizeof(direct_buffer));
LOG_OUTPUT_DEFINE(stage_output, write_stage, stage_buffer, sizeof(stage_buffer));
LOG_OUTPUT_DEFINE(panic_output, write_direct, panic_buffer, sizeof(panic_buffer));

static void queue_message(struct log_msg *message, uint32_t flags)
{
    crux_log_stage_begin(&stage);
    /* The stage would turn colour sequences into '?', so none are asked for. */
    log_output_msg_process(&stage_output, message, flags & ~LOG_OUTPUT_FLAG_COLORS);
    size_t length = crux_log_stage_finish(&stage);
    if (length == 0) {
        return;
    }
    k_spinlock_key_t key = queue_enter();
    (void)crux_log_queue_put(&queue, stage.bytes, length);
    queue_leave(key);
}

/* Takes direct_lock unless the context forbids it or a panic has happened, so that the mode it
 * returns holds until the unlock. Returns the mode. */
static atomic_val_t lock_direct(bool *locked)
{
    *locked = false;
    if (!k_is_in_isr() && !k_is_pre_kernel() && atomic_get(&mode) != MODE_PANIC) {
        (void)k_mutex_lock(&direct_lock, K_FOREVER);
        *locked = true;
    }
    return atomic_get(&mode);
}

static void unlock_direct(bool locked)
{
    if (locked) {
        (void)k_mutex_unlock(&direct_lock);
    }
}

static void process(const struct log_backend *const backend, union log_msg_generic *message)
{
    ARG_UNUSED(backend);
    uint32_t flags = log_backend_std_get_flags();
    bool locked;
    atomic_val_t now = lock_direct(&locked);
    if (now == MODE_QUEUED) {
        queue_message(&message->log, flags);
    } else {
        log_output_msg_process(now == MODE_PANIC ? &panic_output : &direct_output, &message->log,
                               flags);
    }
    unlock_direct(locked);
}

static void dropped(const struct log_backend *const backend, uint32_t count)
{
    ARG_UNUSED(backend);
    bool locked;
    atomic_val_t now = lock_direct(&locked);
    if (now == MODE_QUEUED) {
        k_spinlock_key_t key = queue_enter();
        crux_log_queue_add_dropped(&queue, count);
        queue_leave(key);
    } else {
        log_output_dropped_process(now == MODE_PANIC ? &panic_output : &direct_output, count);
    }
    unlock_direct(locked);
}

static void panic(const struct log_backend *const backend)
{
    ARG_UNUSED(backend);
    atomic_set(&mode, MODE_PANIC);
    /* What the console has not shown yet goes out once, in order. */
    for (;;) {
        if (atomic_get(&queue_busy) != 0) {
            break;
        }
        k_spinlock_key_t key;
        if (k_spin_trylock(&queue_lock, &key) != 0) {
            break;
        }
        size_t length = crux_log_queue_get(&queue, panic_entry, sizeof(panic_entry));
        k_spin_unlock(&queue_lock, key);
        if (length == 0) {
            break;
        }
        poll_out_entry(panic_entry, length);
    }
    log_backend_std_panic(&panic_output);
}

static void init(const struct log_backend *const backend)
{
    ARG_UNUSED(backend);
    __ASSERT_NO_MSG(device_is_ready(console_uart));
}

static size_t next_entry(void *source, char *text, size_t capacity)
{
    ARG_UNUSED(source);
    k_spinlock_key_t key = queue_enter();
    size_t length = crux_log_queue_get(&queue, text, capacity);
    queue_leave(key);
    return length;
}

static void attach(void *source)
{
    ARG_UNUSED(source);
    (void)k_mutex_lock(&direct_lock, K_FOREVER);
    (void)atomic_cas(&mode, MODE_DIRECT, MODE_QUEUED);
    (void)k_mutex_unlock(&direct_lock);
}

static void detach(void *source)
{
    ARG_UNUSED(source);
    (void)k_mutex_lock(&direct_lock, K_FOREVER);
    if (atomic_cas(&mode, MODE_QUEUED, MODE_DIRECT)) {
        for (;;) {
            k_spinlock_key_t key = queue_enter();
            size_t length = crux_log_queue_get(&queue, detach_entry, sizeof(detach_entry));
            queue_leave(key);
            if (length == 0) {
                break;
            }
            poll_out_entry(detach_entry, length);
        }
    }
    (void)k_mutex_unlock(&direct_lock);
}

const crux_logging_console_t crux_logging_console = {next_entry, attach, detach};

static const struct log_backend_api console_log_api = {
    .process = process,
    .dropped = dropped,
    .panic = panic,
    .init = init,
};

LOG_BACKEND_DEFINE(crux_logging_console_backend, console_log_api, true);
