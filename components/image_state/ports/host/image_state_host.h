/*
 * Test controls of the Host double of the image state contract. Kept apart from the public header,
 * as CONTRIBUTING.md requires of test controls, and exposed only to the targets that test the
 * contract. A product image never links the Host double.
 *
 * The double holds two slots and the bootloader's shared data, logs the writes of the contract,
 * injects failures, and carries a small hand model of the bootloader's select and erase rules as
 * the contract's record tabulates them. It is a test double and not a copy of MCUboot: whether the
 * real bootloader behaves like the model is Not verified and needs a board.
 */
#ifndef CRUX_IMAGE_STATE_HOST_H
#define CRUX_IMAGE_STATE_HOST_H

#include "image_state_port.h"

#include <stdbool.h>
#include <stddef.h>

typedef enum {
    IMAGE_STATE_HOST_WRITE_MAGIC = 1,
    IMAGE_STATE_HOST_WRITE_SWAP_INFO_TEST = 2,
    IMAGE_STATE_HOST_WRITE_IMAGE_OK = 3
} image_state_host_write_t;

/**
 * Resets the double and the core's cached start. Slot 0 holds a confirmed 1.0.0 image and runs
 * (the shared data names slot 0, RAM load and bootloader 2.4.0.0). Slot 1 is empty. No fault is
 * armed, and the write log is empty.
 */
void image_state_host_init(void);

void image_state_host_slot_put(crux_image_slot_t slot, const crux_image_port_slot_view_t *view);
crux_image_port_slot_view_t image_state_host_slot_peek(crux_image_slot_t slot);
/** Whether the image passes validation after the bootloader loads it. The default is true. */
void image_state_host_slot_set_image_valid(crux_image_slot_t slot, bool valid);

void image_state_host_shared_put(const crux_image_port_shared_data_t *shared);
void image_state_host_shared_set_absent(bool absent);

/** The update agent's staging: erase the whole slot, trailer included, then write a header. */
void image_state_host_stage(crux_image_slot_t slot, crux_image_version_t version);

/** The writes that landed since the last init, in order. A failed write is not logged. */
size_t image_state_host_write_count(void);
image_state_host_write_t image_state_host_write_op(size_t index);
crux_image_slot_t image_state_host_write_slot(size_t index);

/** The nth write counted from this call (1 is the next one) fails with an I/O error, once. */
void image_state_host_fail_nth_write(size_t n);
/** While set, reading the slot fails with an I/O error. */
void image_state_host_fail_slot_read(crux_image_slot_t slot, bool fails);
/** Called at the start of every write, so that a test can re-enter the service. */
void image_state_host_set_write_hook(void (*hook)(void));
/** The bootloader's copy-done write fails (the bootloader only logs this) when set. */
void image_state_host_set_copy_done_write_fails(bool fails);

/**
 * One reset of the board: the bootloader's select and erase rules, then new shared data. The
 * highest version that has a valid header wins, and the lower slot wins on equal versions. A slot
 * whose magic is not good, or whose copy-done flag is set without the confirm flag, is erased
 * whole. Otherwise copy-done is set, and an image that fails validation is skipped for this boot
 * and keeps its trailer. When no slot can boot, the shared data names no running slot. The model
 * does not read the swap information, so a slot left by a cut after the magic write boots as a
 * test, and it does not model the erase that the real loader does on a load failure.
 * The core's cached start is not reset: a test calls crux_image_core_reset() after a reset.
 */
void image_state_host_boot(void);

#endif /* CRUX_IMAGE_STATE_HOST_H */
