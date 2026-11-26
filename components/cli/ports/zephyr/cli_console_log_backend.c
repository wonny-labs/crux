/* The Logging backend of a console that shares its UART with Logging
 * (CONFIG_CRUX_CLI_CONSOLE_UART_SHARED). It replaces Zephyr's UART backend, which must be off, and
 * writes on the UART of crux-serial0, which the console owns.
 *
 * Three modes, which only move forward:
 *   DIRECT  until the console's thread starts: each message is written with uart_poll_out on the
 * log thread, as Zephyr's UART backend does, so boot output is not held back. QUEUED  once the
 * console's thread attaches, just before it opens the port: each message is formatted into a stage
 * and put in a bounded queue, whole or not at all (drop new, with a count, cli_console_log.c). The
 * log thread never waits for the console or the UART. The console prints the queue only while it
 * waits for input (cli_console_serial.c). PANIC   from log_panic(): what is still queued is written
 * once with uart_poll_out, in order, then every later message is written the same way, from
 * whatever context logs it.
 *
 * Locks, and their order. queue_lock is a spinlock around each queue call, held only to copy one
 * entry in or out; nothing is called under it that waits, and no other lock is taken under it.
 * direct_lock is a mutex that the log thread holds while it writes one message in DIRECT mode, and
 * that the attach takes to move to QUEUED, so that the console never opens the port in the middle
 * of a direct line; queue_lock is never taken under it. The console thread takes queue_lock to read
 * an entry and direct_lock once to attach, and holds neither while it writes to Crux Serial.
 * Nothing here runs in an interrupt except the panic path, which uses k_spin_trylock and skips the
 * queue if the lock is held, and takes no mutex. On a single core the spinlock masks interrupts for
 * the length of one copy of at most CRUX_CLI_LOG_ENTRY_MAX bytes.
 *
 * Limits. After a panic, if the system goes on (a product's fatal error handler that does not
 * halt), the console may still write with interrupts while the panic output polls, so bytes can
 * interleave. A message formatted on the log thread when a panic preempts it is lost, as with
 * Zephyr's backend. */
#include "cli_console_log.h"
#include "cli_console_log_zephyr.h"

#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log_backend.h>
#include <zephyr/logging/log_backend_std.h>
#include <zephyr/logging/log_output.h>
#include <zephyr/spinlock.h>
#include <zephyr/sys/atomic.h>

BUILD_ASSERT(CONFIG_CRUX_CLI_CONSOLE_LOG_QUEUE_BYTES >= CRUX_CLI_LOG_QUEUE_MIN,
             "CONFIG_CRUX_CLI_CONSOLE_LOG_QUEUE_BYTES is below the smallest queue");
BUILD_ASSERT(!IS_ENABLED(CONFIG_LOG_MODE_IMMEDIATE),
             "the console's backend needs deferred logging");

enum { MODE_DIRECT, MODE_QUEUED, MODE_PANIC };

static const struct device *const console_uart = DEVICE_DT_GET(DT_ALIAS(crux_serial0));
static atomic_t mode = ATOMIC_INIT(MODE_DIRECT);
static K_MUTEX_DEFINE(direct_lock);
static struct k_spinlock queue_lock;
static uint8_t queue_storage[CONFIG_CRUX_CLI_CONSOLE_LOG_QUEUE_BYTES];
static crux_cli_log_queue_t queue = {queue_storage, sizeof(queue_storage), 0, 0, 0};
/* Used only by the log thread, in QUEUED mode. */
static crux_cli_log_stage_t stage;
/* Used only by the panic path. */
static char panic_entry[CRUX_CLI_LOG_ENTRY_MAX];

static void poll_out(const uint8_t *data, size_t length)
{
    for (size_t index = 0; index < length; ++index) {
        uart_poll_out(console_uart, data[index]);
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
    crux_cli_log_stage_append(&stage, data, length);
    return (int)length;
}

/* Two outputs, so that the panic path never shares the log thread's formatting buffer. */
static uint8_t direct_buffer[64];
static uint8_t stage_buffer[64];
LOG_OUTPUT_DEFINE(direct_output, write_direct, direct_buffer, sizeof(direct_buffer));
LOG_OUTPUT_DEFINE(stage_output, write_stage, stage_buffer, sizeof(stage_buffer));

static void queue_message(struct log_msg *message, uint32_t flags)
{
    crux_cli_log_stage_begin(&stage);
    /* The stage would turn colour sequences into '?', so none are asked for. */
    log_output_msg_process(&stage_output, message, flags & ~LOG_OUTPUT_FLAG_COLORS);
    size_t length = crux_cli_log_stage_finish(&stage);
    if (length == 0) {
        return;
    }
    k_spinlock_key_t key = k_spin_lock(&queue_lock);
    (void)crux_cli_log_queue_put(&queue, stage.bytes, length);
    k_spin_unlock(&queue_lock, key);
}

/* Takes direct_lock when the context allows. Returns the mode that holds while it is held. */
static atomic_val_t lock_direct(bool *locked)
{
    *locked = false;
    if (!k_is_in_isr() && !k_is_pre_kernel() && atomic_get(&mode) == MODE_DIRECT) {
        (void)k_mutex_lock(&direct_lock, K_FOREVER);
        *locked = true;
    }
    return atomic_get(&mode);
}

static void process(const struct log_backend *const backend, union log_msg_generic *message)
{
    ARG_UNUSED(backend);
    uint32_t flags = log_backend_std_get_flags();
    bool locked;
    atomic_val_t now = lock_direct(&locked);
    if (now != MODE_QUEUED) {
        log_output_msg_process(&direct_output, &message->log, flags);
    }
    if (locked) {
        (void)k_mutex_unlock(&direct_lock);
    }
    if (now == MODE_QUEUED) {
        queue_message(&message->log, flags);
    }
}

static void dropped(const struct log_backend *const backend, uint32_t count)
{
    ARG_UNUSED(backend);
    bool locked;
    atomic_val_t now = lock_direct(&locked);
    if (now != MODE_QUEUED) {
        log_output_dropped_process(&direct_output, count);
    }
    if (locked) {
        (void)k_mutex_unlock(&direct_lock);
    }
    if (now == MODE_QUEUED) {
        k_spinlock_key_t key = k_spin_lock(&queue_lock);
        crux_cli_log_queue_add_dropped(&queue, count);
        k_spin_unlock(&queue_lock, key);
    }
}

static void panic(const struct log_backend *const backend)
{
    ARG_UNUSED(backend);
    atomic_set(&mode, MODE_PANIC);
    /* What the console has not shown yet goes out once, in order, with the terminal's line ends. */
    for (;;) {
        k_spinlock_key_t key;
        if (k_spin_trylock(&queue_lock, &key) != 0) {
            break;
        }
        size_t length = crux_cli_log_queue_get(&queue, panic_entry, sizeof(panic_entry));
        k_spin_unlock(&queue_lock, key);
        if (length == 0) {
            break;
        }
        for (size_t index = 0; index < length; ++index) {
            if (panic_entry[index] == '\n') {
                uart_poll_out(console_uart, '\r');
            }
            uart_poll_out(console_uart, (unsigned char)panic_entry[index]);
        }
    }
    log_backend_std_panic(&direct_output);
}

static void init(const struct log_backend *const backend)
{
    ARG_UNUSED(backend);
    __ASSERT_NO_MSG(device_is_ready(console_uart));
}

static size_t next_entry(void *source, char *text, size_t capacity)
{
    ARG_UNUSED(source);
    k_spinlock_key_t key = k_spin_lock(&queue_lock);
    size_t length = crux_cli_log_queue_get(&queue, text, capacity);
    k_spin_unlock(&queue_lock, key);
    return length;
}

const crux_cli_console_log_t crux_cli_console_log_source = {next_entry, NULL};

void crux_cli_console_log_attach(void)
{
    (void)k_mutex_lock(&direct_lock, K_FOREVER);
    (void)atomic_cas(&mode, MODE_DIRECT, MODE_QUEUED);
    (void)k_mutex_unlock(&direct_lock);
}

static const struct log_backend_api console_log_api = {
    .process = process,
    .dropped = dropped,
    .panic = panic,
    .init = init,
};

LOG_BACKEND_DEFINE(crux_cli_console_log, console_log_api, true);
