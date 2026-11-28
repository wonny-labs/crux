/*
 * The transition table of row U1 (TR1 to TR19): every resting state against every event (START,
 * BEGIN, CANCEL, CONFIRM, ACK), the refused pairs included, and the states inside an attempt
 * reached from the progress port. Also the status snapshot under a concurrent reader.
 */
#include "common.h"

#include "image_state_host.h"
#include "update_agent_port.h"

#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>

static uint8_t image[MEDIUM_IMAGE_MAX];
static size_t image_size;
static medium_source_t source_state;
static crux_update_source_t source;

static void use_image(uint8_t major, uint8_t minor, uint16_t revision)
{
    image_size = build_image(image, major, minor, revision);
    source = medium_source(&source_state, image, image_size);
}

/* A resting state, set up through the agent's own transitions. */
typedef enum {
    SETUP_NOT_STARTED,
    SETUP_UNAVAILABLE,
    SETUP_IDLE,
    SETUP_OUTCOME,
    SETUP_TESTING,
    SETUP_FAILED,
    SETUP_WAITING_RESET,
    SETUP_COUNT
} setup_t;

static const crux_update_state_t setup_state[SETUP_COUNT] = {
    CRUX_UPDATE_STATE_NOT_STARTED, CRUX_UPDATE_STATE_UNAVAILABLE, CRUX_UPDATE_STATE_IDLE,
    CRUX_UPDATE_STATE_OUTCOME,     CRUX_UPDATE_STATE_TESTING,     CRUX_UPDATE_STATE_FAILED,
    CRUX_UPDATE_STATE_WAITING_RESET};

static void setup(setup_t which)
{
    medium_init();
    use_image(1, 1, 0);
    switch (which) {
    case SETUP_NOT_STARTED:
        break;
    case SETUP_UNAVAILABLE:
        image_state_host_shared_set_absent(true);
        CHECK_INT(CRUX_UPDATE_ERR_NOT_READY, crux_update_start(&medium_config));
        break;
    case SETUP_IDLE:
        start_ok();
        break;
    case SETUP_OUTCOME: /* staged, request lost in a reset before it was made: NOT_BOOTED */
        medium_record_set(&(crux_image_attempt_t){1, {1, 1, 0, 7}, false});
        start_ok();
        break;
    case SETUP_TESTING:
        start_ok();
        CHECK_INT(CRUX_UPDATE_OK, crux_update_begin(&source));
        reboot_and_start();
        break;
    case SETUP_FAILED:
        start_ok();
        medium_record_fail_next_store(true);
        CHECK_INT(CRUX_UPDATE_ERR_RECORD, crux_update_begin(&source));
        break;
    case SETUP_WAITING_RESET:
        start_ok();
        CHECK_INT(CRUX_UPDATE_OK, crux_update_begin(&source));
        break;
    case SETUP_COUNT:
        break;
    }
    CHECK_INT(setup_state[which], state_now());
}

typedef enum { EV_START, EV_BEGIN, EV_CANCEL, EV_CONFIRM, EV_ACK, EV_COUNT } event_t;

static crux_update_result_t fire(event_t event)
{
    switch (event) {
    case EV_START:
        return crux_update_start(&medium_config);
    case EV_BEGIN:
        use_image(1, 2, 0);
        return crux_update_begin(&source);
    case EV_CANCEL:
        return crux_update_cancel();
    case EV_CONFIRM:
        return crux_update_confirm();
    case EV_ACK:
        return crux_update_acknowledge();
    case EV_COUNT:
        break;
    }
    return CRUX_UPDATE_ERR_INVALID_ARGUMENT;
}

typedef struct {
    crux_update_result_t result;
    crux_update_state_t next;
} expect_t;

#define OK_TO(state) {CRUX_UPDATE_OK, CRUX_UPDATE_STATE_##state}
#define REFUSED(code, state) {CRUX_UPDATE_ERR_##code, CRUX_UPDATE_STATE_##state}

/* Rows: setups. Columns: START, BEGIN, CANCEL, CONFIRM, ACK. */
static const expect_t table[SETUP_COUNT][EV_COUNT] = {
    /* NOT_STARTED: START runs TR4, everything else is not ready */
    {OK_TO(IDLE), REFUSED(NOT_READY, NOT_STARTED), REFUSED(STATE, NOT_STARTED),
     REFUSED(NOT_READY, NOT_STARTED), REFUSED(NOT_READY, NOT_STARTED)},
    /* UNAVAILABLE (TR1): refuses everything */
    {REFUSED(NOT_READY, UNAVAILABLE), REFUSED(NOT_READY, UNAVAILABLE),
     REFUSED(STATE, UNAVAILABLE), REFUSED(NOT_READY, UNAVAILABLE),
     REFUSED(NOT_READY, UNAVAILABLE)},
    /* IDLE: BEGIN runs TR6 to TR13 */
    {OK_TO(IDLE), OK_TO(WAITING_RESET), REFUSED(STATE, IDLE), REFUSED(STATE, IDLE),
     REFUSED(STATE, IDLE)},
    /* OUTCOME: BEGIN replaces the record (TR6, TR8), ACK clears it (TR15) */
    {OK_TO(OUTCOME), OK_TO(WAITING_RESET), REFUSED(STATE, OUTCOME), REFUSED(STATE, OUTCOME),
     OK_TO(IDLE)},
    /* TESTING: BEGIN refused (TR7), CONFIRM runs TR14 */
    {OK_TO(TESTING), REFUSED(NOT_CONFIRMED, TESTING), REFUSED(STATE, TESTING), OK_TO(OUTCOME),
     REFUSED(STATE, TESTING)},
    /* FAILED: BEGIN runs a new attempt (TR6), ACK clears (TR15) */
    {OK_TO(FAILED), OK_TO(WAITING_RESET), REFUSED(STATE, FAILED), REFUSED(STATE, FAILED),
     OK_TO(IDLE)},
    /* WAITING_RESET: no withdraw; BEGIN refused as busy (TR7) */
    {OK_TO(WAITING_RESET), REFUSED(BUSY, WAITING_RESET), REFUSED(STATE, WAITING_RESET),
     REFUSED(STATE, WAITING_RESET), REFUSED(STATE, WAITING_RESET)},
};

static const char *const event_names[EV_COUNT] = {"START", "BEGIN", "CANCEL", "CONFIRM", "ACK"};
static const char *const setup_names[SETUP_COUNT] = {
    "NOT_STARTED", "UNAVAILABLE", "IDLE", "OUTCOME", "TESTING", "FAILED", "WAITING_RESET"};

static void every_pair(void)
{
    static char name[96];
    for (unsigned s = 0; s < SETUP_COUNT; s++) {
        for (unsigned e = 0; e < EV_COUNT; e++) {
            (void)snprintf(name, sizeof(name), "U1 table: %s x %s", setup_names[s],
                           event_names[e]);
            CASE(name);
            setup((setup_t)s);
            size_t writes = medium_slot_write_count(0);
            CHECK_INT(table[s][e].result, fire((event_t)e));
            CHECK_INT(table[s][e].next, state_now());
            CHECK_INT(writes, medium_slot_write_count(0)); /* the running slot 0 is never written */
        }
    }
}

/* ---- the states inside an attempt, reached from the progress port ---- */

static crux_update_state_t seen_phase[16];
static size_t seen_count;
static bool reentry_checked;

static void reentry_hook(crux_update_state_t phase, uint32_t done, uint32_t total)
{
    if (seen_count == 0 || seen_phase[seen_count - 1u] != phase) {
        if (seen_count < 16u) {
            seen_phase[seen_count++] = phase;
        }
    }
    CHECK(done <= total);
    if (!reentry_checked && phase == CRUX_UPDATE_STATE_BODY_WRITTEN) {
        reentry_checked = true;
        CHECK_INT(CRUX_UPDATE_ERR_BUSY, crux_update_start(&medium_config));
        CHECK_INT(CRUX_UPDATE_ERR_BUSY, crux_update_begin(&source));
        CHECK_INT(CRUX_UPDATE_ERR_BUSY, crux_update_confirm());
        CHECK_INT(CRUX_UPDATE_ERR_BUSY, crux_update_acknowledge());
        crux_update_status_t status = status_now();
        CHECK_INT(CRUX_UPDATE_STATE_ERASED, status.state); /* resting state before TR10 ends */
        CHECK(status.progress_total > 0u);
    }
}

static void attempt_states(void)
{
    CASE("U1: inside an attempt every call but status and cancel is busy");
    setup(SETUP_IDLE);
    seen_count = 0;
    reentry_checked = false;
    medium_set_progress_hook(reentry_hook);
    CHECK_INT(CRUX_UPDATE_OK, crux_update_begin(&source));
    CHECK(reentry_checked);
    CHECK(medium_progress_count() > 0u);

    CASE("U1: progress runs through erase, body write and read-back, in order");
    CHECK(seen_count >= 2u);
    {
        bool order_ok = true;
        for (size_t i = 1; i < seen_count; i++) {
            order_ok = order_ok && seen_phase[i] > seen_phase[i - 1u];
        }
        CHECK(order_ok);
    }
    CHECK_INT(CRUX_UPDATE_STATE_VERIFIED, seen_phase[seen_count - 1u]);
}

/* ---- cancel ---- */

static crux_update_state_t cancel_phase;
static void cancel_hook(crux_update_state_t phase, uint32_t done, uint32_t total)
{
    (void)done;
    (void)total;
    if (phase == cancel_phase) {
        CHECK_INT(CRUX_UPDATE_OK, crux_update_cancel());
    }
}

static void cancel_cases(void)
{
    CASE("TR19: a cancel during the erase ends FAILED(cancelled), header blank, nothing to undo");
    setup(SETUP_IDLE);
    {
        static uint8_t stale[MEDIUM_IMAGE_MAX];
        size_t stale_size = build_image(stale, 0, 5, 0);
        medium_slot_load(1, stale, stale_size, true);
    }
    cancel_phase = CRUX_UPDATE_STATE_ERASED;
    medium_set_progress_hook(cancel_hook);
    CHECK_INT(CRUX_UPDATE_ERR_CANCELLED, crux_update_begin(&source));
    CHECK_INT(CRUX_UPDATE_STATE_FAILED, state_now());
    CHECK_INT(CRUX_UPDATE_ERR_CANCELLED, status_now().last_result);
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, medium_slot_state(1));
    CHECK_INT(0, medium_op_find(MEDIUM_OP_CONTRACT_WRITE, UINT32_MAX));

    CASE("TR19: a cancel during the body write ends FAILED, no header written");
    setup(SETUP_IDLE);
    cancel_phase = CRUX_UPDATE_STATE_BODY_WRITTEN;
    medium_set_progress_hook(cancel_hook);
    CHECK_INT(CRUX_UPDATE_ERR_CANCELLED, crux_update_begin(&source));
    CHECK_INT(0, medium_op_find(MEDIUM_OP_SLOT_WRITE, 0));
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, medium_slot_state(1));

    CASE("TR16: a cancel during the read-back invalidates the staged slot");
    setup(SETUP_IDLE);
    cancel_phase = CRUX_UPDATE_STATE_VERIFIED;
    medium_set_progress_hook(cancel_hook);
    CHECK_INT(CRUX_UPDATE_ERR_CANCELLED, crux_update_begin(&source));
    CHECK_INT(CRUX_UPDATE_STATE_FAILED, state_now());
    CHECK(medium_op_find(MEDIUM_OP_SLOT_WRITE, 0) != 0);
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, medium_slot_state(1));
    CHECK(!status_now().slot_staged);
    CHECK_INT(0, medium_op_find(MEDIUM_OP_CONTRACT_WRITE, UINT32_MAX));

    CASE("TR16: an invalidation that fails leaves slot_staged for the bootloader");
    setup(SETUP_IDLE);
    cancel_phase = CRUX_UPDATE_STATE_VERIFIED;
    medium_set_progress_hook(cancel_hook);
    medium_fail_next_slot_erase(true);
    CHECK_INT(CRUX_UPDATE_ERR_CANCELLED, crux_update_begin(&source));
    CHECK(status_now().slot_staged);
    CHECK_INT(CRUX_IMAGE_SLOT_STAGED, medium_slot_state(1));
}

/* ---- failures of single steps ---- */

static void fail_source_hook(crux_update_state_t phase, uint32_t done, uint32_t total)
{
    (void)done;
    (void)total;
    if (phase == CRUX_UPDATE_STATE_ERASED) {
        source_state.fail_reads = true;
    }
}

static void fail_record_hook(crux_update_state_t phase, uint32_t done, uint32_t total)
{
    (void)done;
    (void)total;
    if (phase == CRUX_UPDATE_STATE_VERIFIED) {
        medium_record_fail_next_store(true);
    }
}

static void step_failures(void)
{
    CASE("TR8: a failed record store ends FAILED(record) before any slot change");
    setup(SETUP_IDLE);
    medium_record_fail_next_store(true);
    CHECK_INT(CRUX_UPDATE_ERR_RECORD, crux_update_begin(&source));
    CHECK_INT(0, medium_slot_write_count(1));
    CHECK(!medium_record_get(NULL));

    CASE("TR9: a failed erase ends FAILED(erase)");
    setup(SETUP_IDLE);
    {
        static uint8_t stale[MEDIUM_IMAGE_MAX];
        size_t stale_size = build_image(stale, 0, 5, 0);
        medium_slot_load(1, stale, stale_size, true);
    }
    medium_fail_slot_erase_after(2);
    CHECK_INT(CRUX_UPDATE_ERR_ERASE, crux_update_begin(&source));
    CHECK_INT(CRUX_UPDATE_STATE_FAILED, state_now());
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, medium_slot_state(1)); /* header sector went first */

    CASE("TR10: a source that fails on the second read ends FAILED(source), header blank");
    setup(SETUP_IDLE);
    medium_set_progress_hook(fail_source_hook);
    CHECK_INT(CRUX_UPDATE_ERR_SOURCE, crux_update_begin(&source));
    CHECK_INT(CRUX_UPDATE_STATE_FAILED, state_now());
    CHECK_INT(0, medium_op_find(MEDIUM_OP_SLOT_WRITE, 0));
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, medium_slot_state(1));

    CASE("TR13/TR17: a refused request after the record invalidates the slot: FAILED(request)");
    setup(SETUP_IDLE);
    image_state_host_fail_nth_write(1); /* the request's magic write fails with an I/O error */
    CHECK_INT(CRUX_UPDATE_ERR_REQUEST, crux_update_begin(&source));
    CHECK_INT(CRUX_UPDATE_STATE_FAILED, state_now());
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, medium_slot_state(1));
    {
        crux_image_attempt_t attempt;
        CHECK(medium_record_get(&attempt));
        CHECK(attempt.requested);
    }

    CASE("TR17: a request whose swap write fails after the magic landed counts as made");
    setup(SETUP_IDLE);
    image_state_host_fail_nth_write(2);
    CHECK_INT(CRUX_UPDATE_OK, crux_update_begin(&source));
    CHECK_INT(CRUX_UPDATE_STATE_WAITING_RESET, state_now());
    CHECK_INT(CRUX_IMAGE_SLOT_PENDING_TEST, medium_slot_state(1));

    CASE("TR13/TR17: a failed requested-record store invalidates the slot: FAILED(record)");
    setup(SETUP_IDLE);
    medium_set_progress_hook(fail_record_hook);
    CHECK_INT(CRUX_UPDATE_ERR_RECORD, crux_update_begin(&source));
    CHECK_INT(CRUX_UPDATE_STATE_FAILED, state_now());
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, medium_slot_state(1));
    CHECK_INT(0, medium_op_find(MEDIUM_OP_CONTRACT_WRITE, UINT32_MAX));
    {
        crux_image_attempt_t attempt;
        CHECK(medium_record_get(&attempt));
        CHECK(!attempt.requested); /* the previous record stands */
    }

    CASE("TR14: a failed confirm keeps TESTING, and a retry confirms");
    setup(SETUP_TESTING);
    image_state_host_fail_nth_write(1);
    CHECK_INT(CRUX_UPDATE_ERR_IO, crux_update_confirm());
    CHECK_INT(CRUX_UPDATE_STATE_TESTING, state_now());
    CHECK_INT(CRUX_UPDATE_OK, crux_update_confirm());
    CHECK_INT(CRUX_UPDATE_STATE_OUTCOME, state_now());
    CHECK_INT(CRUX_IMAGE_OUTCOME_CONFIRMED, status_now().outcome);

    CASE("TR15: a failed clear keeps the outcome, a retry clears it");
    setup(SETUP_OUTCOME);
    medium_record_fail_next_clear(true);
    CHECK_INT(CRUX_UPDATE_ERR_RECORD, crux_update_acknowledge());
    CHECK_INT(CRUX_UPDATE_STATE_OUTCOME, state_now());
    CHECK_INT(CRUX_UPDATE_OK, crux_update_acknowledge());
    CHECK_INT(CRUX_UPDATE_STATE_IDLE, state_now());
    CHECK(!medium_record_get(NULL));
}

/* ---- start ---- */

static void start_cases(void)
{
    CASE("TR1: a failed contract start leaves the agent UNAVAILABLE and writes nothing");
    setup(SETUP_UNAVAILABLE);
    CHECK_INT(0, medium_op_count());

    CASE("TR2: an image booted on trial with no record is TESTING, outcome NONE");
    medium_init();
    {
        crux_image_port_slot_view_t view = image_state_host_slot_peek(0);
        view.image_ok = CRUX_IMAGE_PORT_FLAG_UNSET;
        image_state_host_slot_put(0, &view);
    }
    start_ok();
    CHECK_INT(CRUX_UPDATE_STATE_TESTING, state_now());
    CHECK_INT(CRUX_IMAGE_OUTCOME_NONE, status_now().outcome);
    CHECK_INT(0, medium_op_count());

    CASE("TR14: confirming an image with no record goes to IDLE, not OUTCOME");
    CHECK_INT(CRUX_UPDATE_OK, crux_update_confirm());
    CHECK_INT(CRUX_UPDATE_STATE_IDLE, state_now());

    CASE("TR4: a stale record (a confirmed standby in its slot) gives IDLE, outcome NONE");
    medium_init();
    {
        static uint8_t standby[MEDIUM_IMAGE_MAX];
        size_t standby_size = build_image(standby, 0, 9, 0);
        medium_slot_load(1, standby, standby_size, true);
    }
    medium_record_set(&(crux_image_attempt_t){1, {0, 9, 0, 0}, true});
    start_ok();
    CHECK_INT(CRUX_UPDATE_STATE_IDLE, state_now());
    CHECK(status_now().attempt_present);

    CASE("TR5: an unreadable record is treated as none and sets record_lost");
    medium_init();
    medium_record_set_unreadable(true);
    start_ok();
    CHECK_INT(CRUX_UPDATE_STATE_IDLE, state_now());
    CHECK(status_now().record_lost);
    CHECK(!status_now().attempt_present);

    CASE("START: a NULL config or a zero header size is an invalid argument and starts nothing");
    medium_init();
    CHECK_INT(CRUX_UPDATE_ERR_INVALID_ARGUMENT, crux_update_start(NULL));
    {
        crux_update_config_t config = {0, MEDIUM_LOAD_ADDRESS};
        CHECK_INT(CRUX_UPDATE_ERR_INVALID_ARGUMENT, crux_update_start(&config));
    }
    CHECK_INT(CRUX_UPDATE_STATE_NOT_STARTED, state_now());
    CHECK_INT(CRUX_UPDATE_ERR_INVALID_ARGUMENT, crux_update_status_get(NULL));

    CASE("U4: the next update after a confirmed one targets slot 0 and erases the old image");
    setup(SETUP_TESTING);
    CHECK_INT(CRUX_UPDATE_OK, crux_update_confirm());
    CHECK_INT(CRUX_UPDATE_OK, crux_update_acknowledge());
    reboot_and_start();
    CHECK_INT(1, running_slot_now());
    use_image(1, 2, 0);
    size_t slot1_writes = medium_slot_write_count(1);
    CHECK_INT(CRUX_UPDATE_OK, crux_update_begin(&source));
    CHECK_INT(slot1_writes, medium_slot_write_count(1));
    CHECK(memcmp(medium_slot_bytes(0), image, image_size) == 0);
    reboot_and_start();
    CHECK_INT(0, running_slot_now());
    CHECK_INT(CRUX_UPDATE_STATE_TESTING, state_now());
    CHECK_INT(CRUX_IMAGE_OUTCOME_TESTING, status_now().outcome);
}

/* ---- the status snapshot under a concurrent reader ---- */

static atomic_bool reader_stop;
static atomic_uint reader_reads;
static atomic_uint reader_bad;

static void *reader(void *unused)
{
    (void)unused;
    while (!atomic_load(&reader_stop)) {
        crux_update_status_t status;
        if (crux_update_status_get(&status) == CRUX_UPDATE_OK) {
            atomic_fetch_add(&reader_reads, 1u);
            if (status.progress_done > status.progress_total ||
                (unsigned)status.state > (unsigned)CRUX_UPDATE_STATE_FAILED) {
                atomic_fetch_add(&reader_bad, 1u);
            }
        }
    }
    return NULL;
}

static void snapshot_concurrency(void)
{
    CASE("Status: a concurrent reader always sees a consistent snapshot during attempts");
    pthread_t thread;
    atomic_store(&reader_stop, false);
    atomic_store(&reader_reads, 0u);
    atomic_store(&reader_bad, 0u);
    CHECK_INT(0, pthread_create(&thread, NULL, reader, NULL));
    for (int round = 0; round < 20; round++) {
        setup(SETUP_IDLE);
        CHECK_INT(CRUX_UPDATE_OK, crux_update_begin(&source));
    }
    atomic_store(&reader_stop, true);
    CHECK_INT(0, pthread_join(thread, NULL));
    CHECK(atomic_load(&reader_reads) > 0u);
    CHECK_INT(0, atomic_load(&reader_bad));
}

int main(void)
{
    every_pair();
    attempt_states();
    cancel_cases();
    step_failures();
    start_cases();
    snapshot_concurrency();
    return harness_finish("update_agent_table");
}
