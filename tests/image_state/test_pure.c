/*
 * The pure functions: the version rule (V1) and the outcome classifier (O1 to O7). No provider and
 * no medium.
 */
#include "harness.h"

#include <crux/image_state.h>

static crux_image_version_t ver(uint8_t major, uint8_t minor, uint16_t revision, uint32_t build)
{
    return (crux_image_version_t){major, minor, revision, build};
}

static void version_vectors(void)
{
    struct {
        const char *name;
        crux_image_version_t a;
        crux_image_version_t b;
        int expected;
    } const vectors[] = {
        {"equal", {1, 2, 3, 0}, {1, 2, 3, 0}, 0},
        {"major older", {1, 9, 9, 0}, {2, 0, 0, 0}, -1},
        {"major newer", {2, 0, 0, 0}, {1, 9, 9, 0}, 1},
        {"major beats minor", {2, 0, 0, 0}, {1, 255, 65535, 0}, 1},
        {"minor older", {1, 1, 9, 0}, {1, 2, 0, 0}, -1},
        {"minor newer", {1, 2, 0, 0}, {1, 1, 9, 0}, 1},
        {"minor beats revision", {1, 2, 0, 0}, {1, 1, 65535, 0}, 1},
        {"revision older", {1, 2, 3, 0}, {1, 2, 4, 0}, -1},
        {"revision newer", {1, 2, 4, 0}, {1, 2, 3, 0}, 1},
        {"revision above 8 bits", {1, 2, 256, 0}, {1, 2, 255, 0}, 1},
        {"build ignored, higher build is not newer", {1, 2, 3, 99}, {1, 2, 3, 0}, 0},
        {"build ignored, lower build is not older", {1, 2, 3, 0}, {1, 2, 3, 99}, 0},
        {"build never overrides a lower revision", {1, 2, 3, 1000}, {1, 2, 4, 0}, -1},
        {"zero", {0, 0, 0, 0}, {0, 0, 0, 0}, 0},
        {"maximum", {255, 255, 65535, 0xFFFFFFFFu}, {255, 255, 65535, 0}, 0},
    };
    for (unsigned i = 0; i < sizeof(vectors) / sizeof(vectors[0]); i++) {
        CASE(vectors[i].name);
        CHECK_INT(vectors[i].expected, crux_image_version_compare(&vectors[i].a, &vectors[i].b));
        /* The rule is antisymmetric. */
        CHECK_INT(-vectors[i].expected, crux_image_version_compare(&vectors[i].b, &vectors[i].a));
    }
}

/* A record: slot 0 runs 1.0.0. `confirmed` and the state of slot 1 at start are the inputs. */
static crux_image_boot_record_t record_running_slot0(bool confirmed,
                                                     crux_image_slot_state_t slot1_state)
{
    crux_image_boot_record_t record = {0};
    record.running_slot = 0;
    record.inactive_slot = 1;
    record.running_confirmed = confirmed;
    record.running_version = ver(1, 0, 0, 0);
    record.slot_state_at_start[0] =
        confirmed ? CRUX_IMAGE_SLOT_RUNNING_CONFIRMED : CRUX_IMAGE_SLOT_RUNNING_TESTING;
    record.slot_state_at_start[1] = slot1_state;
    return record;
}

static crux_image_attempt_t attempt_for(crux_image_slot_t slot, crux_image_version_t version,
                                        bool requested)
{
    return (crux_image_attempt_t){slot, version, requested};
}

static void outcome_table(void)
{
    crux_image_boot_record_t record;
    crux_image_attempt_t attempt;

    CASE("O1 no attempt");
    record = record_running_slot0(true, CRUX_IMAGE_SLOT_EMPTY);
    CHECK_INT(CRUX_IMAGE_OUTCOME_NONE, crux_image_outcome(&record, NULL));
    CHECK_INT(CRUX_IMAGE_OUTCOME_NONE, crux_image_outcome(NULL, NULL));

    CASE("O2 the attempted image runs");
    attempt = attempt_for(0, ver(1, 0, 0, 0), true);
    record = record_running_slot0(true, CRUX_IMAGE_SLOT_EMPTY);
    CHECK_INT(CRUX_IMAGE_OUTCOME_CONFIRMED, crux_image_outcome(&record, &attempt));
    record = record_running_slot0(false, CRUX_IMAGE_SLOT_EMPTY);
    CHECK_INT(CRUX_IMAGE_OUTCOME_TESTING, crux_image_outcome(&record, &attempt));
    /* The build number is not part of the comparison. */
    attempt = attempt_for(0, ver(1, 0, 0, 777), true);
    CHECK_INT(CRUX_IMAGE_OUTCOME_TESTING, crux_image_outcome(&record, &attempt));
    /* The attempt can be on slot 1 when slot 1 runs. */
    record = record_running_slot0(false, CRUX_IMAGE_SLOT_RUNNING_TESTING);
    record.running_slot = 1;
    record.inactive_slot = 0;
    record.running_version = ver(1, 1, 0, 0);
    attempt = attempt_for(1, ver(1, 1, 0, 0), true);
    CHECK_INT(CRUX_IMAGE_OUTCOME_TESTING, crux_image_outcome(&record, &attempt));

    CASE("O3 stale: the running slot was reused");
    record = record_running_slot0(true, CRUX_IMAGE_SLOT_EMPTY);
    attempt = attempt_for(0, ver(1, 0, 1, 0), true);
    CHECK_INT(CRUX_IMAGE_OUTCOME_NONE, crux_image_outcome(&record, &attempt));
    attempt = attempt_for(0, ver(2, 0, 0, 0), false);
    CHECK_INT(CRUX_IMAGE_OUTCOME_NONE, crux_image_outcome(&record, &attempt));

    CASE("O4 stale: the slot holds a confirmed image");
    record = record_running_slot0(true, CRUX_IMAGE_SLOT_STANDBY_CONFIRMED);
    attempt = attempt_for(1, ver(1, 1, 0, 0), true);
    CHECK_INT(CRUX_IMAGE_OUTCOME_NONE, crux_image_outcome(&record, &attempt));
    attempt.requested = false;
    CHECK_INT(CRUX_IMAGE_OUTCOME_NONE, crux_image_outcome(&record, &attempt));

    CASE("O5 never requested");
    attempt = attempt_for(1, ver(1, 1, 0, 0), false);
    for (crux_image_slot_state_t state = CRUX_IMAGE_SLOT_EMPTY; state <= CRUX_IMAGE_SLOT_INVALID;
         state++) {
        if (state == CRUX_IMAGE_SLOT_STANDBY_CONFIRMED) {
            continue; /* O4 wins */
        }
        record = record_running_slot0(true, state);
        CHECK_INT(CRUX_IMAGE_OUTCOME_NOT_BOOTED, crux_image_outcome(&record, &attempt));
    }

    CASE("O6 requested and not consumed");
    attempt = attempt_for(1, ver(1, 1, 0, 0), true);
    static const crux_image_slot_state_t pending[] = {
        CRUX_IMAGE_SLOT_STAGED, CRUX_IMAGE_SLOT_PENDING_TEST, CRUX_IMAGE_SLOT_PENDING_PERMANENT};
    for (unsigned i = 0; i < sizeof(pending) / sizeof(pending[0]); i++) {
        record = record_running_slot0(true, pending[i]);
        CHECK_INT(CRUX_IMAGE_OUTCOME_NOT_BOOTED, crux_image_outcome(&record, &attempt));
    }

    CASE("O7 requested and the image is gone or refused");
    static const crux_image_slot_state_t gone[] = {CRUX_IMAGE_SLOT_EMPTY, CRUX_IMAGE_SLOT_TRIED,
                                                   CRUX_IMAGE_SLOT_INVALID};
    for (unsigned i = 0; i < sizeof(gone) / sizeof(gone[0]); i++) {
        record = record_running_slot0(true, gone[i]);
        CHECK_INT(CRUX_IMAGE_OUTCOME_REVERTED, crux_image_outcome(&record, &attempt));
    }

    CASE("outcome: inputs outside the table");
    record = record_running_slot0(true, CRUX_IMAGE_SLOT_EMPTY);
    attempt = attempt_for(2, ver(1, 1, 0, 0), true); /* no such slot */
    CHECK_INT(CRUX_IMAGE_OUTCOME_NONE, crux_image_outcome(&record, &attempt));
    attempt = attempt_for(1, ver(1, 1, 0, 0), true);
    CHECK_INT(CRUX_IMAGE_OUTCOME_NONE, crux_image_outcome(NULL, &attempt));
    /* A running state on the slot that is not running is not in the table. */
    record = record_running_slot0(true, CRUX_IMAGE_SLOT_RUNNING_TESTING);
    CHECK_INT(CRUX_IMAGE_OUTCOME_NONE, crux_image_outcome(&record, &attempt));
    record = record_running_slot0(true, CRUX_IMAGE_SLOT_RUNNING_CONFIRMED);
    CHECK_INT(CRUX_IMAGE_OUTCOME_NONE, crux_image_outcome(&record, &attempt));
    /* The result does not depend on the order of the slots. */
    record = record_running_slot0(true, CRUX_IMAGE_SLOT_TRIED);
    CHECK_INT(CRUX_IMAGE_OUTCOME_REVERTED, crux_image_outcome(&record, &attempt));
    CHECK_INT(CRUX_IMAGE_OUTCOME_REVERTED, crux_image_outcome(&record, &attempt));
}

int main(void)
{
    version_vectors();
    outcome_table();
    return harness_finish("image_state_pure");
}
