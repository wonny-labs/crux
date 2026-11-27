/*
 * The slot-state table: a slot's state from its header and trailer. Pure.
 */
#include "image_state_port.h"

static bool flag_defined(crux_image_port_flag_t flag)
{
    return flag == CRUX_IMAGE_PORT_FLAG_UNSET || flag == CRUX_IMAGE_PORT_FLAG_SET;
}

static crux_image_result_t derive_running(const crux_image_port_slot_view_t *view,
                                          crux_image_slot_state_t *state)
{
    /* Under revert the bootloader erases a slot whose magic is not good, so it cannot be running.
     */
    if (view->magic != CRUX_IMAGE_PORT_MAGIC_GOOD) {
        *state = CRUX_IMAGE_SLOT_INVALID;
        return CRUX_IMAGE_ERR_BOOT_STATE;
    }
    if (view->image_ok == CRUX_IMAGE_PORT_FLAG_SET) {
        *state = CRUX_IMAGE_SLOT_RUNNING_CONFIRMED; /* copy_done: any */
        return CRUX_IMAGE_OK;
    }
    /* The table does not define these running rows, so they fail closed (row I6). */
    if (view->image_ok != CRUX_IMAGE_PORT_FLAG_UNSET || !flag_defined(view->copy_done)) {
        *state = CRUX_IMAGE_SLOT_INVALID;
        return CRUX_IMAGE_ERR_BOOT_STATE;
    }
    /* image_ok unset: on trial, whether or not the bootloader's copy_done write landed. */
    *state = CRUX_IMAGE_SLOT_RUNNING_TESTING;
    return CRUX_IMAGE_OK;
}

crux_image_result_t crux_image_slot_state_derive(bool is_running,
                                                 const crux_image_port_slot_view_t *view,
                                                 crux_image_slot_state_t *state)
{
    /* Any slot with an invalid or erased header is EMPTY. A running one cannot be. */
    if (!view->header_valid) {
        *state = CRUX_IMAGE_SLOT_EMPTY;
        return is_running ? CRUX_IMAGE_ERR_BOOT_STATE : CRUX_IMAGE_OK;
    }
    if (is_running) {
        return derive_running(view, state);
    }

    /* A magic other than good or unset is not a trailer this contract knows: fail closed. */
    if ((view->magic != CRUX_IMAGE_PORT_MAGIC_GOOD && view->magic != CRUX_IMAGE_PORT_MAGIC_UNSET) ||
        !flag_defined(view->image_ok) || !flag_defined(view->copy_done)) {
        *state = CRUX_IMAGE_SLOT_INVALID;
        return CRUX_IMAGE_OK;
    }
    if (view->magic == CRUX_IMAGE_PORT_MAGIC_UNSET) {
        /*
         * STAGED needs an erased trailer. The table leaves a stale flag under an unset magic open,
         * and the contract takes the safe reading. With image_ok set, a request that writes the
         * magic would make the slot PENDING_PERMANENT, which this contract never creates (row I2).
         * With copy_done set it would read TRIED and be erased at the next reset.
         */
        bool erased = view->image_ok == CRUX_IMAGE_PORT_FLAG_UNSET &&
                      view->copy_done == CRUX_IMAGE_PORT_FLAG_UNSET;
        *state = erased ? CRUX_IMAGE_SLOT_STAGED : CRUX_IMAGE_SLOT_INVALID;
        return CRUX_IMAGE_OK;
    }
    if (view->image_ok == CRUX_IMAGE_PORT_FLAG_SET) {
        *state = view->copy_done == CRUX_IMAGE_PORT_FLAG_SET ? CRUX_IMAGE_SLOT_STANDBY_CONFIRMED
                                                             : CRUX_IMAGE_SLOT_PENDING_PERMANENT;
    } else {
        *state = view->copy_done == CRUX_IMAGE_PORT_FLAG_SET ? CRUX_IMAGE_SLOT_TRIED
                                                             : CRUX_IMAGE_SLOT_PENDING_TEST;
    }
    return CRUX_IMAGE_OK;
}
