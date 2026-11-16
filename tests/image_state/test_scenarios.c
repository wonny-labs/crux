/*
 * End to end over the Host double and its hand model of the bootloader: stage, request, reset,
 * start again, classify. These are software results of a model. They say nothing about what the
 * real bootloader does (the target cases T1 to T7 of the record need a board).
 *
 * The cases here: the full update (confirmed and left unconfirmed), a refused image, the power-cut
 * limits (O8), an update from slot 1, and a staged image that was never requested.
 */
#include "harness.h"
#include "image_state_host.h"

#include <crux/image_state.h>

static crux_image_version_t ver(uint8_t major, uint8_t minor, uint16_t revision)
{
    return (crux_image_version_t){major, minor, revision, 0};
}

/* A reset: the bootloader runs, then the application starts again and derives its record. */
static void reset_and_start(void)
{
    image_state_host_boot();
    crux_image_core_reset();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_start());
}

static crux_image_outcome_t outcome_of(const crux_image_attempt_t *attempt)
{
    crux_image_boot_record_t record;
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    return crux_image_outcome(&record, attempt);
}

static void full_update(void)
{
    crux_image_boot_record_t record;
    crux_image_attempt_t attempt = {1, {1, 1, 0, 0}, false};

    CASE("N: stage, request, reset, the new image runs on trial, confirm, reset, it stays");
    image_state_host_init();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_start());
    image_state_host_stage(1, ver(1, 1, 0));
    CHECK_INT(CRUX_IMAGE_OK, crux_image_confirm()); /* already confirmed: no write */
    attempt.requested = true;
    CHECK_INT(CRUX_IMAGE_OK, crux_image_request_test(1));
    reset_and_start();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK_INT(1, record.running_slot);
    CHECK_INT(0, record.inactive_slot);
    CHECK(!record.running_confirmed);
    CHECK_INT(CRUX_IMAGE_SLOT_STANDBY_CONFIRMED, record.slot_state_at_start[0]);
    CHECK_INT(CRUX_IMAGE_OUTCOME_TESTING, outcome_of(&attempt));
    CHECK_INT(CRUX_IMAGE_OK, crux_image_confirm());
    reset_and_start();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK_INT(1, record.running_slot);
    CHECK(record.running_confirmed);
    CHECK_INT(CRUX_IMAGE_OUTCOME_CONFIRMED, outcome_of(&attempt));

    CASE("N2: the next update runs from slot 1 and targets slot 0 (the B63a case, end to end)");
    image_state_host_stage(0, ver(1, 2, 0));
    attempt = (crux_image_attempt_t){0, ver(1, 2, 0), true};
    CHECK_INT(CRUX_IMAGE_OK, crux_image_request_test(0));
    reset_and_start();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK_INT(0, record.running_slot);
    CHECK_INT(CRUX_IMAGE_OUTCOME_TESTING, outcome_of(&attempt));
    CHECK_INT(CRUX_IMAGE_OK, crux_image_confirm());
    /* The boot record is the snapshot at start: a confirm shows after the next reset. */
    CHECK_INT(CRUX_IMAGE_OUTCOME_TESTING, outcome_of(&attempt));
    reset_and_start();
    CHECK_INT(CRUX_IMAGE_OUTCOME_CONFIRMED, outcome_of(&attempt));

    CASE("N3: an attempt record that was not cleared is stale once its slot holds another image");
    /* Slot 1 now holds the confirmed 1.1.0 of the first update (rule 4). */
    CHECK_INT(CRUX_IMAGE_OUTCOME_NONE, outcome_of(&(crux_image_attempt_t){1, ver(1, 1, 0), true}));
    /* Slot 0 runs 1.2.0, so an attempt for another release on it is stale (rule 3). */
    CHECK_INT(CRUX_IMAGE_OUTCOME_NONE, outcome_of(&(crux_image_attempt_t){0, ver(1, 1, 0), true}));
}

static void left_unconfirmed(void)
{
    crux_image_boot_record_t record;
    crux_image_attempt_t attempt = {1, {1, 1, 0, 0}, true};

    CASE("T2: tested, never confirmed, reset: the previous image runs and the outcome is REVERTED");
    image_state_host_init();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_start());
    image_state_host_stage(1, ver(1, 1, 0));
    CHECK_INT(CRUX_IMAGE_OK, crux_image_request_test(1));
    reset_and_start();
    CHECK_INT(CRUX_IMAGE_OUTCOME_TESTING, outcome_of(&attempt));
    reset_and_start(); /* no confirm in between */
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK_INT(0, record.running_slot);
    CHECK(record.running_confirmed);
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, record.slot_state_at_start[1]); /* the bootloader erased it */
    CHECK_INT(CRUX_IMAGE_OUTCOME_REVERTED, outcome_of(&attempt));
}

static void refused_image(void)
{
    crux_image_boot_record_t record;
    crux_image_attempt_t attempt = {1, {1, 1, 0, 0}, true};

    CASE("T3: a staged image that fails validation: slot reads TRIED, then EMPTY, REVERTED both "
         "times");
    image_state_host_init();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_start());
    image_state_host_stage(1, ver(1, 1, 0));
    image_state_host_slot_set_image_valid(1, false);
    CHECK_INT(CRUX_IMAGE_OK, crux_image_request_test(1));
    reset_and_start();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK_INT(0, record.running_slot);
    CHECK_INT(CRUX_IMAGE_SLOT_TRIED, record.slot_state_at_start[1]);
    CHECK_INT(CRUX_IMAGE_OUTCOME_REVERTED, outcome_of(&attempt));
    reset_and_start();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, record.slot_state_at_start[1]);
    CHECK_INT(CRUX_IMAGE_OUTCOME_REVERTED, outcome_of(&attempt));
}

static void power_cut_limits(void)
{
    crux_image_boot_record_t record;
    crux_image_attempt_t attempt = {1, {1, 1, 0, 0}, false};

    CASE("O8a a cut during staging (requested false): NOT_BOOTED, and the staged slot reads EMPTY");
    image_state_host_init();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_start());
    image_state_host_stage(1, ver(1, 1, 0));
    reset_and_start(); /* the power returns: a newer image without a request is erased */
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK_INT(0, record.running_slot);
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, record.slot_state_at_start[1]);
    CHECK_INT(CRUX_IMAGE_OUTCOME_NOT_BOOTED, outcome_of(&attempt));

    CASE("O8b the stated limit: requested set, the request writes did not land: REVERTED");
    image_state_host_init();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_start());
    image_state_host_stage(1, ver(1, 1, 0));
    attempt.requested = true;
    image_state_host_fail_nth_write(1); /* the cut: no write landed */
    CHECK_INT(CRUX_IMAGE_ERR_IO, crux_image_request_test(1));
    reset_and_start();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK_INT(0, record.running_slot);
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, record.slot_state_at_start[1]);
    /* An image that never ran is reported as reverted. The error is on the safe side. */
    CHECK_INT(CRUX_IMAGE_OUTCOME_REVERTED, outcome_of(&attempt));

    CASE("O8c a cut after the magic write: the model boots the image as a test");
    image_state_host_init();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_start());
    image_state_host_stage(1, ver(1, 1, 0));
    image_state_host_fail_nth_write(2);
    CHECK_INT(CRUX_IMAGE_ERR_IO, crux_image_request_test(1));
    reset_and_start();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK_INT(1, record.running_slot);
    CHECK_INT(CRUX_IMAGE_OUTCOME_TESTING, outcome_of(&attempt));
}

static void stale_trailer(void)
{
    CASE("O9 staging erases the whole slot: the old confirmed trailer cannot make a new image look "
         "confirmed");
    image_state_host_init();
    crux_image_port_slot_view_t old_image = {true,
                                             {0, 9, 0, 0},
                                             CRUX_IMAGE_PORT_MAGIC_GOOD,
                                             CRUX_IMAGE_PORT_FLAG_SET,
                                             CRUX_IMAGE_PORT_FLAG_SET};
    image_state_host_slot_put(1, &old_image);
    CHECK_INT(CRUX_IMAGE_OK, crux_image_start());
    crux_image_slot_info_t info;
    CHECK_INT(CRUX_IMAGE_OK, crux_image_slot_get(1, &info));
    CHECK_INT(CRUX_IMAGE_SLOT_STANDBY_CONFIRMED, info.state);
    image_state_host_stage(1, ver(1, 1, 0));
    CHECK_INT(CRUX_IMAGE_OK, crux_image_slot_get(1, &info));
    CHECK_INT(CRUX_IMAGE_SLOT_STAGED, info.state);
    CHECK_INT(CRUX_IMAGE_OK, crux_image_request_test(1));
}

int main(void)
{
    full_update();
    left_unconfirmed();
    refused_image();
    power_cut_limits();
    stale_trailer();
    return harness_finish("image_state_scenarios");
}
