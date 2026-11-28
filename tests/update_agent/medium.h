/*
 * The Host test composition of the update agent: fakes of the slot, record, verify and progress
 * ports, one simulated medium shared with the image state contract's Host double, a power-cut
 * injector, and an image builder.
 *
 * The medium holds the bytes of both slots. The slot trailers are the image state double's slot
 * views, so the agent's writes and the contract's request and confirm writes act on one medium:
 * a header written by the agent makes the double's slot STAGED, and an erase by the double's hand
 * model of the bootloader erases the bytes. The double is a test double, not a copy of the
 * bootloader. Results over it say nothing about the real bootloader or a board.
 *
 * A power cut is armed at the n-th medium operation (counted from medium_init() or the last
 * reboot): a slot erase or write, a record store or clear, or a write of the image state contract.
 * The operation lands, is torn or is lost, and every later operation fails and changes nothing
 * until medium_reboot().
 */
#ifndef CRUX_UPDATE_AGENT_TEST_MEDIUM_H
#define CRUX_UPDATE_AGENT_TEST_MEDIUM_H

#include <crux/update_agent.h>

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define MEDIUM_SECTOR_SIZE 512u
#define MEDIUM_SECTOR_COUNT 32u
#define MEDIUM_SLOT_SIZE (MEDIUM_SECTOR_SIZE * MEDIUM_SECTOR_COUNT)
#define MEDIUM_TRAILER_SIZE MEDIUM_SECTOR_SIZE
#define MEDIUM_HEADER_SIZE 256u
#define MEDIUM_LOAD_ADDRESS 0x80000000u
#define MEDIUM_IMAGE_MAX MEDIUM_SLOT_SIZE

typedef enum {
    MEDIUM_CUT_LANDS = 0, /**< The operation completes, then the power goes. */
    MEDIUM_CUT_TORN = 1,  /**< Part of the operation lands. */
    MEDIUM_CUT_LOST = 2   /**< Nothing of the operation lands. */
} medium_cut_t;

typedef enum {
    MEDIUM_OP_SLOT_ERASE = 1,
    MEDIUM_OP_SLOT_WRITE = 2,
    MEDIUM_OP_RECORD_STORE = 3,
    MEDIUM_OP_RECORD_CLEAR = 4,
    MEDIUM_OP_CONTRACT_WRITE = 5
} medium_op_kind_t;

typedef struct {
    medium_op_kind_t kind;
    crux_image_slot_t slot;
    uint32_t offset; /**< Slot write: the offset. Slot erase: the sector. */
    uint32_t length;
} medium_op_t;

/** The default configuration of the tests. */
extern const crux_update_config_t medium_config;

/**
 * Fresh medium: slot 0 holds a confirmed, running 1.0.0 image (bytes and trailer), slot 1 is
 * blank, no record, no cut armed, write block 1, the agent and the contract's cached starts
 * forgotten.
 */
void medium_init(void);

/** Sets the slot write block for the next operations (a power of two up to 256). */
void medium_set_write_block(uint32_t write_block);

/** Arms a cut at the n-th operation from now (1 is the next one). 0 disarms. */
void medium_cut_at(size_t n, medium_cut_t mode);
bool medium_power_lost(void);

/** Operations since medium_init() or the last reboot, with the first 512 logged. */
size_t medium_op_count(void);
medium_op_t medium_op(size_t index);
/** 1-based index of the first logged operation that matches, or 0. Offset UINT32_MAX: any. */
size_t medium_op_find(medium_op_kind_t kind, uint32_t offset);

/** One reset: the power returns, the double's bootloader model runs, RAM state is forgotten. */
void medium_reboot(void);

/** Puts a whole image into a slot's bytes, and sets its trailer: confirmed or blank. */
void medium_slot_load(crux_image_slot_t slot, const uint8_t *image, size_t size, bool confirmed);
const uint8_t *medium_slot_bytes(crux_image_slot_t slot);
bool medium_slot_blank(crux_image_slot_t slot);
crux_image_slot_state_t medium_slot_state(crux_image_slot_t slot);
/** Erases one sector of a slot directly (a bootloader erase that a test models by hand). */
void medium_slot_erase_sector(crux_image_slot_t slot, uint32_t sector);
/** Slot writes to a slot since medium_init(), across reboots. */
size_t medium_slot_write_count(crux_image_slot_t slot);

/** The record fake. */
bool medium_record_get(crux_image_attempt_t *attempt);
void medium_record_set(const crux_image_attempt_t *attempt);
void medium_record_set_unreadable(bool unreadable);
void medium_record_fail_next_store(bool fails);
void medium_record_fail_next_clear(bool fails);

/** The slot fake fails the next erase or write with an I/O error (not a power cut). */
void medium_fail_next_slot_erase(bool fails);
void medium_fail_slot_erase_after(size_t erases);

/** Progress: calls seen, and a hook called from every progress call. */
size_t medium_progress_count(void);
void medium_set_progress_hook(void (*hook)(crux_update_state_t phase, uint32_t done,
                                           uint32_t total));

/** Image builder. Returns the size. The digest and the signature are those of the fake verify. */
typedef struct {
    crux_image_version_t version;
    uint32_t body_size;
    uint32_t flags;
    uint32_t load_address;
    uint16_t header_size;
    bool protected_area;
    bool sha256;
    bool signature;
} medium_image_spec_t;

medium_image_spec_t medium_image_default(uint8_t major, uint8_t minor, uint16_t revision);
size_t medium_image_build(const medium_image_spec_t *spec, uint8_t *out, size_t capacity);
/** Offsets in a built image, for tests that corrupt it. */
size_t medium_image_tlv_value_offset(const uint8_t *image, size_t size, uint16_t type);

/**
 * A source over a buffer that can change between the agent's two reads: after a read has reached
 * the end of the image once, later reads see byte @p mutate_offset inverted.
 */
typedef struct {
    const uint8_t *data;
    size_t size;
    bool mutate;
    size_t mutate_offset;
    bool reached_end;
    bool fail_reads;
    size_t reads;
} medium_source_t;

crux_update_source_t medium_source(medium_source_t *state, const uint8_t *data, size_t size);

#endif /* CRUX_UPDATE_AGENT_TEST_MEDIUM_H */
