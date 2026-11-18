/*
 * The pure parts of the contract: the version rule and the outcome classifier. No provider, no
 * state, no storage. A consumer that only classifies links no provider.
 */
#include <crux/image_state.h>

#include <stddef.h>

int crux_image_version_compare(const crux_image_version_t *a, const crux_image_version_t *b)
{
    /* Major, minor, revision, in that order. The build number is carried and never compared. */
    if (a->major != b->major) {
        return a->major < b->major ? -1 : 1;
    }
    if (a->minor != b->minor) {
        return a->minor < b->minor ? -1 : 1;
    }
    if (a->revision != b->revision) {
        return a->revision < b->revision ? -1 : 1;
    }
    return 0;
}

crux_image_outcome_t crux_image_outcome(const crux_image_boot_record_t *record,
                                        const crux_image_attempt_t *attempt)
{
    /* Rule 1: no attempt. A missing record or a slot that does not exist is no attempt either. */
    if (record == NULL || attempt == NULL || attempt->slot >= CRUX_IMAGE_SLOT_COUNT) {
        return CRUX_IMAGE_OUTCOME_NONE;
    }

    if (attempt->slot == record->running_slot) {
        /* Rule 3: stale, the slot was reused for another release. */
        if (crux_image_version_compare(&attempt->version, &record->running_version) != 0) {
            return CRUX_IMAGE_OUTCOME_NONE;
        }
        /* Rule 2 */
        return record->running_confirmed ? CRUX_IMAGE_OUTCOME_CONFIRMED
                                         : CRUX_IMAGE_OUTCOME_TESTING;
    }

    crux_image_slot_state_t state = record->slot_state_at_start[attempt->slot];
    /* Rule 4: stale, the slot holds a confirmed image. */
    if (state == CRUX_IMAGE_SLOT_STANDBY_CONFIRMED) {
        return CRUX_IMAGE_OUTCOME_NONE;
    }
    /* Rule 5: the agent never asked for a boot. */
    if (!attempt->requested) {
        return CRUX_IMAGE_OUTCOME_NOT_BOOTED;
    }

    switch (state) {
    case CRUX_IMAGE_SLOT_STAGED:
    case CRUX_IMAGE_SLOT_PENDING_TEST:
    case CRUX_IMAGE_SLOT_PENDING_PERMANENT:
        /* Rule 6: the request was not consumed. */
        return CRUX_IMAGE_OUTCOME_NOT_BOOTED;
    case CRUX_IMAGE_SLOT_EMPTY:
    case CRUX_IMAGE_SLOT_TRIED:
    case CRUX_IMAGE_SLOT_INVALID:
        /* Rule 7: the image is gone or refused. */
        return CRUX_IMAGE_OUTCOME_REVERTED;
    case CRUX_IMAGE_SLOT_RUNNING_CONFIRMED:
    case CRUX_IMAGE_SLOT_RUNNING_TESTING:
    case CRUX_IMAGE_SLOT_STANDBY_CONFIRMED:
    default:
        /* A running state on the slot that is not running is not in the table. */
        return CRUX_IMAGE_OUTCOME_NONE;
    }
}
