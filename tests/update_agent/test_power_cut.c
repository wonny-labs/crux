/*
 * The power-interruption table of row U5 (PC0 to PC17), executable on Host: each row cuts the
 * power at its point, resets (the image state double's hand model of the bootloader runs), starts
 * the agent again and checks the slot state, the outcome and the recovery that the row states.
 * A sweep then cuts at every medium operation of an attempt, in each of three ways, and checks the
 * invariants of U5: the running image survives, the agent starts, and a retry succeeds.
 *
 * These are results over a hand model of the bootloader, not over the bootloader. Rows that
 * depend on how a real device tears a write or orders an erase are Not verified until a board and
 * a power fixture run them.
 */
#include "common.h"

#include "image_state_host.h"

#include <stdio.h>
#include <string.h>

static uint8_t image[MEDIUM_IMAGE_MAX];
static size_t image_size;
static uint8_t old_image[MEDIUM_IMAGE_MAX];
static size_t old_image_size;
static uint8_t standby[MEDIUM_IMAGE_MAX];
static size_t standby_size;

typedef enum { X_EMPTY, X_STANDBY } prior_t;

/* Running slot 0 with 1.0.0 confirmed; slot 1 empty or an older confirmed standby (0.9.0). */
static void fresh(prior_t prior)
{
    medium_init();
    old_image_size = build_image(old_image, 1, 0, 0);
    image_size = build_image(image, 1, 1, 0);
    standby_size = 0;
    if (prior == X_STANDBY) {
        standby_size = build_image(standby, 0, 9, 0);
        medium_slot_load(1, standby, standby_size, true);
    }
    start_ok();
}

static crux_update_result_t begin_image(void)
{
    medium_source_t state;
    crux_update_source_t source = medium_source(&state, image, image_size);
    return crux_update_begin(&source);
}

/* Counts the operations of an uncut attempt from the given prior state. */
static size_t operations_of_attempt(prior_t prior)
{
    fresh(prior);
    CHECK_INT(CRUX_UPDATE_OK, begin_image());
    return medium_op_count();
}

static void check_running_image_intact(void)
{
    CHECK(memcmp(medium_slot_bytes(0), old_image, old_image_size) == 0);
}

static void expect_after_reset(crux_image_slot_t running, crux_update_state_t state,
                               crux_image_outcome_t outcome, crux_image_slot_state_t slot1)
{
    reboot_and_start();
    CHECK_INT(running, running_slot_now());
    CHECK_INT(state, state_now());
    CHECK_INT(outcome, status_now().outcome);
    CHECK_INT(slot1, medium_slot_state(1));
}

/* A retry after the reset reaches WAITING_RESET, and the next reset boots it on trial. */
static void expect_retry_succeeds(void)
{
    CHECK_INT(CRUX_UPDATE_OK, begin_image());
    CHECK_INT(CRUX_UPDATE_STATE_WAITING_RESET, state_now());
    reboot_and_start();
    CHECK_INT(1, running_slot_now());
    CHECK_INT(CRUX_UPDATE_STATE_TESTING, state_now());
    CHECK_INT(CRUX_IMAGE_OUTCOME_TESTING, status_now().outcome);
}

/*
 * U4: a header whose magic is whole is never over a torn rest of the header. The hand model reads
 * a header as valid from its magic, so this is checked on the bytes, at the cut.
 */
static void check_no_whole_magic_over_torn_header(void)
{
    const uint8_t *slot = medium_slot_bytes(1);
    if (memcmp(slot, image, 4) == 0) {
        CHECK(memcmp(slot, image, MEDIUM_HEADER_SIZE) == 0 ||
              (standby_size != 0 && memcmp(slot, standby, MEDIUM_HEADER_SIZE) == 0));
    }
}

static void cut_and_begin(size_t op, medium_cut_t mode)
{
    medium_cut_at(op, mode);
    (void)begin_image();
    CHECK(medium_power_lost());
    check_no_whole_magic_over_torn_header();
}

/* Finds the 1-based index of an operation in an uncut run from the same prior state. */
// NOLINTNEXTLINE(bugprone-easily-swappable-parameters): offset and count
static size_t op_of(prior_t prior, medium_op_kind_t kind, uint32_t offset, unsigned nth)
{
    operations_of_attempt(prior);
    unsigned seen = 0;
    for (size_t i = 0; i < medium_op_count(); i++) {
        medium_op_t op = medium_op(i);
        if (op.kind == kind && (offset == UINT32_MAX || op.offset == offset)) {
            seen++;
            if (seen == nth) {
                return i + 1u;
            }
        }
    }
    return 0;
}

static void rows_before_the_header(void)
{
    size_t op;

    CASE("PC0: a reset during the checks (no write yet) changes nothing");
    fresh(X_EMPTY);
    {
        medium_image_spec_t spec = medium_image_default(1, 0, 0); /* refused: not newer */
        uint8_t refused[MEDIUM_IMAGE_MAX];
        size_t size = medium_image_build(&spec, refused, sizeof(refused));
        medium_source_t state;
        crux_update_source_t source = medium_source(&state, refused, size);
        CHECK_INT(CRUX_UPDATE_ERR_NOT_NEWER, crux_update_begin(&source));
    }
    expect_after_reset(0, CRUX_UPDATE_STATE_IDLE, CRUX_IMAGE_OUTCOME_NONE, CRUX_IMAGE_SLOT_EMPTY);
    expect_retry_succeeds();

    CASE("PC1: a torn record store leaves the previous record; slot unchanged");
    op = op_of(X_EMPTY, MEDIUM_OP_RECORD_STORE, UINT32_MAX, 1);
    CHECK_INT(1, op);
    fresh(X_EMPTY);
    cut_and_begin(op, MEDIUM_CUT_TORN);
    CHECK(!medium_record_get(NULL));
    expect_after_reset(0, CRUX_UPDATE_STATE_IDLE, CRUX_IMAGE_OUTCOME_NONE, CRUX_IMAGE_SLOT_EMPTY);
    expect_retry_succeeds();

    CASE("PC2: after the record, before the erase, slot EMPTY: NOT_BOOTED (case 5)");
    fresh(X_EMPTY);
    cut_and_begin(op, MEDIUM_CUT_LANDS);
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_NOT_BOOTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    expect_retry_succeeds();

    CASE("PC2: after the record, before the erase, older standby: NONE (case 4), not erased");
    op = op_of(X_STANDBY, MEDIUM_OP_RECORD_STORE, UINT32_MAX, 1);
    fresh(X_STANDBY);
    cut_and_begin(op, MEDIUM_CUT_LANDS);
    expect_after_reset(0, CRUX_UPDATE_STATE_IDLE, CRUX_IMAGE_OUTCOME_NONE,
                       CRUX_IMAGE_SLOT_STANDBY_CONFIRMED);
    CHECK(memcmp(medium_slot_bytes(1), standby, standby_size) == 0);
    expect_retry_succeeds();

    CASE("PC3: a cut before the header sector's erase lands keeps the old standby: NONE");
    op = op_of(X_STANDBY, MEDIUM_OP_SLOT_ERASE, 0, 1);
    fresh(X_STANDBY);
    cut_and_begin(op, MEDIUM_CUT_LOST);
    expect_after_reset(0, CRUX_UPDATE_STATE_IDLE, CRUX_IMAGE_OUTCOME_NONE,
                       CRUX_IMAGE_SLOT_STANDBY_CONFIRMED);
    expect_retry_succeeds();

    CASE("PC3: a torn erase of the header sector reads EMPTY: NOT_BOOTED (case 5)");
    fresh(X_STANDBY);
    cut_and_begin(op, MEDIUM_CUT_TORN);
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_NOT_BOOTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    expect_retry_succeeds();

    CASE("PC3: a cut later in the erase (header gone, trailer left): NOT_BOOTED; retry erases it");
    op = op_of(X_STANDBY, MEDIUM_OP_SLOT_ERASE, 2, 1);
    fresh(X_STANDBY);
    cut_and_begin(op, MEDIUM_CUT_LANDS);
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_NOT_BOOTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    CHECK(!medium_slot_blank(1)); /* the stale trailer is still there */
    expect_retry_succeeds();

    CASE("PC4: a cut during the body write: header blank, NOT_BOOTED; the attempt repeats");
    op = op_of(X_EMPTY, MEDIUM_OP_SLOT_WRITE, MEDIUM_HEADER_SIZE + 512u, 1);
    CHECK(op != 0u);
    fresh(X_EMPTY);
    cut_and_begin(op, MEDIUM_CUT_TORN);
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_NOT_BOOTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    expect_retry_succeeds();
}

static void rows_of_the_header(void)
{
    size_t op;

    CASE("PC5: a cut after the header rest, before its magic: EMPTY, NOT_BOOTED");
    op = op_of(X_EMPTY, MEDIUM_OP_SLOT_WRITE, 4, 1);
    fresh(X_EMPTY);
    cut_and_begin(op, MEDIUM_CUT_LANDS);
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, medium_slot_state(1)); /* the magic is still blank */
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_NOT_BOOTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    expect_retry_succeeds();

    CASE("PC5: a torn header magic is not a valid header: EMPTY, NOT_BOOTED");
    op = op_of(X_EMPTY, MEDIUM_OP_SLOT_WRITE, 0, 1);
    fresh(X_EMPTY);
    cut_and_begin(op, MEDIUM_CUT_TORN);
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_NOT_BOOTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    expect_retry_succeeds();

    CASE("PC6: after the header, before the requested record: the bootloader erases X");
    fresh(X_EMPTY);
    cut_and_begin(op, MEDIUM_CUT_LANDS);
    CHECK_INT(CRUX_IMAGE_SLOT_STAGED, medium_slot_state(1));
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_NOT_BOOTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    CHECK(medium_slot_blank(1)); /* the whole slot, by the model */
    expect_retry_succeeds();
}

static void rows_of_the_request(void)
{
    size_t op;

    CASE("PC7: after the requested record, before the request: REVERTED for an image that "
         "never ran (the stated window)");
    op = op_of(X_EMPTY, MEDIUM_OP_RECORD_STORE, UINT32_MAX, 2);
    fresh(X_EMPTY);
    cut_and_begin(op, MEDIUM_CUT_LANDS);
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_REVERTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    expect_retry_succeeds();

    CASE("PC7 variant: the requested record torn: the previous record stands, NOT_BOOTED");
    fresh(X_EMPTY);
    cut_and_begin(op, MEDIUM_CUT_TORN);
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_NOT_BOOTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    expect_retry_succeeds();

    CASE("PC8: a torn request magic: the bootloader erases X, REVERTED (case 7)");
    op = op_of(X_EMPTY, MEDIUM_OP_CONTRACT_WRITE, UINT32_MAX, 1);
    fresh(X_EMPTY);
    cut_and_begin(op, MEDIUM_CUT_TORN);
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_REVERTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    expect_retry_succeeds();

    CASE("PC9: after the magic, before the swap information: X boots on trial (case 2)");
    fresh(X_EMPTY);
    cut_and_begin(op, MEDIUM_CUT_LANDS);
    reboot_and_start();
    CHECK_INT(1, running_slot_now());
    CHECK_INT(CRUX_UPDATE_STATE_TESTING, state_now());
    CHECK_INT(CRUX_IMAGE_OUTCOME_TESTING, status_now().outcome);

    CASE("PC10: in WAITING_RESET, any reset boots X on trial");
    fresh(X_EMPTY);
    CHECK_INT(CRUX_UPDATE_OK, begin_image());
    reboot_and_start();
    CHECK_INT(1, running_slot_now());
    CHECK_INT(CRUX_UPDATE_STATE_TESTING, state_now());
    CHECK_INT(CRUX_IMAGE_OUTCOME_TESTING, status_now().outcome);
    check_running_image_intact();

    CASE("PC11: the bootloader's copy-done write fails: still TESTING");
    fresh(X_EMPTY);
    CHECK_INT(CRUX_UPDATE_OK, begin_image());
    image_state_host_set_copy_done_write_fails(true);
    reboot_and_start();
    CHECK_INT(1, running_slot_now());
    CHECK_INT(CRUX_UPDATE_STATE_TESTING, state_now());

    CASE("PC12: the bootloader refuses the image: the old image runs, REVERTED, erased next reset");
    fresh(X_EMPTY);
    CHECK_INT(CRUX_UPDATE_OK, begin_image());
    image_state_host_slot_set_image_valid(1, false);
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_REVERTED,
                       CRUX_IMAGE_SLOT_TRIED);
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_REVERTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    expect_retry_succeeds();
}

static void rows_after_the_boot(void)
{
    size_t op;

    CASE("PC13: a reset in TESTING before the confirm: X erased, the old image runs, REVERTED");
    fresh(X_EMPTY);
    CHECK_INT(CRUX_UPDATE_OK, begin_image());
    reboot_and_start();
    CHECK_INT(CRUX_UPDATE_STATE_TESTING, state_now());
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_REVERTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    check_running_image_intact();
    expect_retry_succeeds();

    CASE("PC14: the bootloader's erase of X cut after the header sector: EMPTY, as the row "
         "that led here (hand model)");
    op = op_of(X_EMPTY, MEDIUM_OP_SLOT_WRITE, 0, 1);
    fresh(X_EMPTY);
    cut_and_begin(op, MEDIUM_CUT_LANDS); /* PC6 */
    medium_slot_erase_sector(1, 0);      /* the bootloader's erase, cut after the first sector */
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_NOT_BOOTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    CHECK(!medium_slot_blank(1));
    expect_retry_succeeds();

    CASE("PC14: the erase cut with the header left and the magic bad: erased again at the reset");
    fresh(X_EMPTY);
    CHECK_INT(CRUX_UPDATE_OK, begin_image());
    {
        crux_image_port_slot_view_t view = image_state_host_slot_peek(1);
        view.magic = CRUX_IMAGE_PORT_MAGIC_BAD; /* a partly erased trailer */
        image_state_host_slot_put(1, &view);
    }
    medium_slot_erase_sector(1, 3);
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_REVERTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    expect_retry_succeeds();

    CASE("PC15: the confirm write lands: CONFIRMED (case 2) at every start");
    fresh(X_EMPTY);
    CHECK_INT(CRUX_UPDATE_OK, begin_image());
    reboot_and_start();
    medium_cut_at(1, MEDIUM_CUT_LANDS);
    (void)crux_update_confirm();
    reboot_and_start();
    CHECK_INT(1, running_slot_now());
    CHECK_INT(CRUX_UPDATE_STATE_OUTCOME, state_now());
    CHECK_INT(CRUX_IMAGE_OUTCOME_CONFIRMED, status_now().outcome);

    CASE("PC15: a torn confirm flag is not a confirm: the old image runs, REVERTED");
    fresh(X_EMPTY);
    CHECK_INT(CRUX_UPDATE_OK, begin_image());
    reboot_and_start();
    medium_cut_at(1, MEDIUM_CUT_TORN);
    CHECK(crux_update_confirm() != CRUX_UPDATE_OK);
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_REVERTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    check_running_image_intact();
    expect_retry_succeeds();

    CASE("PC15: a lost confirm write: REVERTED, the attempt is repeated");
    fresh(X_EMPTY);
    CHECK_INT(CRUX_UPDATE_OK, begin_image());
    reboot_and_start();
    medium_cut_at(1, MEDIUM_CUT_LOST);
    CHECK(crux_update_confirm() != CRUX_UPDATE_OK);
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_REVERTED,
                       CRUX_IMAGE_SLOT_EMPTY);

    CASE("PC16: a cut during the clear after the confirm: CONFIRMED is reported again");
    fresh(X_EMPTY);
    CHECK_INT(CRUX_UPDATE_OK, begin_image());
    reboot_and_start();
    CHECK_INT(CRUX_UPDATE_OK, crux_update_confirm());
    medium_cut_at(1, MEDIUM_CUT_LOST);
    CHECK_INT(CRUX_UPDATE_ERR_RECORD, crux_update_acknowledge());
    reboot_and_start();
    CHECK_INT(CRUX_UPDATE_STATE_OUTCOME, state_now());
    CHECK_INT(CRUX_IMAGE_OUTCOME_CONFIRMED, status_now().outcome);
    CHECK_INT(CRUX_UPDATE_OK, crux_update_acknowledge());
    reboot_and_start();
    CHECK_INT(CRUX_UPDATE_STATE_IDLE, state_now());

    CASE("PC17: a request that failed after the record: FAILED now, REVERTED after the reset");
    fresh(X_EMPTY);
    image_state_host_fail_nth_write(1);
    CHECK_INT(CRUX_UPDATE_ERR_REQUEST, begin_image());
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, medium_slot_state(1));
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_REVERTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    expect_retry_succeeds();

    CASE("PC17: the same, with the invalidation also failing: the bootloader erases X");
    fresh(X_EMPTY);
    image_state_host_fail_nth_write(1);
    medium_fail_next_slot_erase(true);
    CHECK_INT(CRUX_UPDATE_ERR_REQUEST, begin_image());
    CHECK(status_now().slot_staged);
    CHECK_INT(CRUX_IMAGE_SLOT_STAGED, medium_slot_state(1));
    expect_after_reset(0, CRUX_UPDATE_STATE_OUTCOME, CRUX_IMAGE_OUTCOME_REVERTED,
                       CRUX_IMAGE_SLOT_EMPTY);
    expect_retry_succeeds();
}

/* Every operation of an attempt, cut in each of the three ways. */
static void sweep(prior_t prior, const char *label)
{
    static const medium_cut_t modes[3] = {MEDIUM_CUT_LANDS, MEDIUM_CUT_TORN, MEDIUM_CUT_LOST};
    static char name[128];
    size_t total = operations_of_attempt(prior);
    CHECK(total > 5u);
    for (size_t op = 1; op <= total; op++) {
        for (unsigned m = 0; m < 3u; m++) {
            (void)snprintf(name, sizeof(name), "U5 sweep (%s): cut at op %zu of %zu, mode %u",
                           label, op, total, m);
            CASE(name);
            fresh(prior);
            cut_and_begin(op, modes[m]);
            reboot_and_start();
            check_running_image_intact();
            crux_update_status_t status = status_now();
            crux_image_slot_t running = running_slot_now();
            if (running == 1) {
                /* the request landed: the new image runs on trial */
                CHECK_INT(CRUX_UPDATE_STATE_TESTING, status.state);
                CHECK_INT(CRUX_IMAGE_OUTCOME_TESTING, status.outcome);
                CHECK_INT(CRUX_UPDATE_OK, crux_update_confirm());
            } else {
                CHECK_INT(0, running);
                CHECK(status.state == CRUX_UPDATE_STATE_IDLE ||
                      status.state == CRUX_UPDATE_STATE_OUTCOME);
                CHECK(status.outcome == CRUX_IMAGE_OUTCOME_NONE ||
                      status.outcome == CRUX_IMAGE_OUTCOME_NOT_BOOTED ||
                      status.outcome == CRUX_IMAGE_OUTCOME_REVERTED);
                CHECK(medium_slot_state(1) != CRUX_IMAGE_SLOT_PENDING_TEST);
                expect_retry_succeeds();
            }
        }
    }
}

int main(void)
{
    rows_before_the_header();
    rows_of_the_header();
    rows_of_the_request();
    rows_after_the_boot();
    sweep(X_EMPTY, "slot empty");
    sweep(X_STANDBY, "older standby");
    return harness_finish("update_agent_power_cut");
}
