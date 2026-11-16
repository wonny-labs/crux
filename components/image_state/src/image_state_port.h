/*
 * Private seam between the image state core and its medium. Not a public header: it is not under
 * include/, no usage target exports it, and only a provider and the core include it.
 *
 * The medium is the bootloader's shared data and the two slots' headers and trailers. A provider
 * reads them and writes the three flags that the contract writes. The Host double of this
 * component implements the port over memory. A Zephyr provider over bootutil is a separate piece
 * of work. This header carries no bootloader type, and a provider owns the translation.
 */
#ifndef CRUX_IMAGE_STATE_PORT_H
#define CRUX_IMAGE_STATE_PORT_H

#include <crux/image_state.h>

#include <stdbool.h>
#include <stdint.h>

/** The trailer magic of a slot as the bootloader reads it. */
typedef enum {
    CRUX_IMAGE_PORT_MAGIC_UNSET = 0,
    CRUX_IMAGE_PORT_MAGIC_GOOD = 1,
    CRUX_IMAGE_PORT_MAGIC_BAD = 2
} crux_image_port_magic_t;

/** A trailer flag: unset, set, or a value outside the defined ones. */
typedef enum {
    CRUX_IMAGE_PORT_FLAG_UNSET = 0,
    CRUX_IMAGE_PORT_FLAG_SET = 1,
    CRUX_IMAGE_PORT_FLAG_INVALID = 2
} crux_image_port_flag_t;

/** A slot's header and trailer. */
typedef struct {
    bool header_valid;
    crux_image_version_t version;
    crux_image_port_magic_t magic;
    crux_image_port_flag_t image_ok;
    crux_image_port_flag_t copy_done;
} crux_image_port_slot_view_t;

/** The bootloader's mode as the shared data names it. */
typedef enum {
    CRUX_IMAGE_PORT_MODE_MISSING = 0,
    CRUX_IMAGE_PORT_MODE_RAM_LOAD = 1,
    CRUX_IMAGE_PORT_MODE_OTHER = 2
} crux_image_port_mode_t;

/** The keys of the bootloader's shared data that the contract reads. */
typedef struct {
    bool running_slot_present;
    uint32_t running_slot; /**< As the bootloader reports it, so a value above 1 can be tested. */
    crux_image_port_mode_t mode;
    bool bootloader_version_present;
    crux_image_version_t bootloader_version;
} crux_image_port_shared_data_t;

/** Reads the shared data. Returns false when it is absent altogether. */
bool crux_image_port_shared_data_get(crux_image_port_shared_data_t *out);

/** Reads one slot. Returns CRUX_IMAGE_OK or CRUX_IMAGE_ERR_IO. */
crux_image_result_t crux_image_port_slot_read(crux_image_slot_t slot,
                                              crux_image_port_slot_view_t *view);

/* The request writes, in the order that a stock test request uses: the magic, then the swap
 * information (the test type). Neither writes the confirm flag. */
crux_image_result_t crux_image_port_write_magic(crux_image_slot_t slot);
crux_image_result_t crux_image_port_write_swap_info_test(crux_image_slot_t slot);

/** The confirm write: the confirm flag of one slot. */
crux_image_result_t crux_image_port_write_image_ok(crux_image_slot_t slot);

/**
 * Derives a slot's state from its header and trailer, by the slot-state table of the contract.
 * Pure. Returns CRUX_IMAGE_OK, or CRUX_IMAGE_ERR_BOOT_STATE for a running slot that the contract
 * does not support: no valid header, a magic that is not good (under revert the bootloader erases
 * such a slot, so it cannot be running), or a flag outside set and unset. @p state is then
 * CRUX_IMAGE_SLOT_EMPTY for a missing header and CRUX_IMAGE_SLOT_INVALID otherwise.
 */
crux_image_result_t crux_image_slot_state_derive(bool is_running,
                                                 const crux_image_port_slot_view_t *view,
                                                 crux_image_slot_state_t *state);

/**
 * Test control: forgets the cached start, so that the next crux_image_start() reads the medium
 * again. Called by a test composition's provider when it resets. A product never calls it.
 */
void crux_image_core_reset(void);

#endif /* CRUX_IMAGE_STATE_PORT_H */
