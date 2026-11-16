/**
 * @file
 * @brief The state of the two firmware image slots: query it, request a test boot, confirm.
 *
 * Status: Experimental (image state contract proposal, rows I1 to I7; ADR-0001 decision 4). A
 * change is listed in the release notes. It becomes Unstable only under the condition of row I7.
 * The contract has one provider so far, the Host double of this component, which is a test double
 * and not a bootloader. No Zephyr, MCUboot or board provider exists yet, so nothing here says how
 * a real bootloader behaves. See docs/image-state-contract.md.
 *
 * The contract describes one image in two slots, numbered like the bootloader numbers them. It has
 * three operations on state: query (crux_image_boot_record_get() and crux_image_slot_get()), a
 * request that the other slot boots once as a test (crux_image_request_test()), and a confirm of
 * the running image (crux_image_confirm()). It has no permanent request, no staging write or
 * erase, no bootloader update and no events. The update agent stages an image. The contract only
 * asks the bootloader to try it.
 *
 * "Reverted" is an outcome, not a slot state. crux_image_outcome() derives it from the boot record
 * and an attempt record that the update agent keeps. The contract stores nothing.
 *
 * Thread context only. crux_image_request_test() and crux_image_confirm() write storage and can
 * block for the length of a medium write, so a control thread must not call them. They are
 * serialised by one internal lock, and a caller that finds it taken gets CRUX_IMAGE_ERR_BUSY.
 * crux_image_start() runs once at boot, before other threads use the service. The boot record is
 * read once at start and never changes. crux_image_slot_get(), crux_image_request_test() and
 * crux_image_confirm() read the live trailers. crux_image_slot_get() takes no lock, so a read that
 * overlaps a request or a confirm sees the slot before or after a write, as the medium's driver
 * serialises them. The pure functions have no state and may be called from any context.
 *
 * The contract checks no permission. A management adapter checks access before it calls the update
 * agent. The caller is trusted code.
 */
#ifndef CRUX_IMAGE_STATE_H
#define CRUX_IMAGE_STATE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * A call whose result must be used. A start that is ignored leaves every other call failing
 * closed, and a request or confirm that is ignored hides a lost update.
 */
#if defined(__cplusplus)
#define CRUX_IMAGE_NODISCARD [[nodiscard]]
#elif defined(__GNUC__) || defined(__clang__)
#define CRUX_IMAGE_NODISCARD __attribute__((warn_unused_result))
#else
#define CRUX_IMAGE_NODISCARD
#endif

/** One image, two slots. There is no multi-image and no third slot. */
#define CRUX_IMAGE_SLOT_COUNT 2u

/** A slot number: 0 or 1, equal to the bootloader's slot number. */
typedef uint8_t crux_image_slot_t;

/**
 * An image version. Versions compare on major, minor and revision, in that order. The build number
 * is carried and never compared, so the bootloader and the application cannot disagree about which
 * image is newer. A composition must not build the bootloader with the build-number comparison.
 */
typedef struct {
    uint8_t major;
    uint8_t minor;
    uint16_t revision;
    uint32_t build; /**< Carried, never compared. */
} crux_image_version_t;

/** What a slot holds, derived from its header and its trailer. */
typedef enum {
    CRUX_IMAGE_SLOT_EMPTY = 0,  /**< No valid header. */
    CRUX_IMAGE_SLOT_STAGED = 1, /**< Valid header and an erased trailer: written, not requested. */
    CRUX_IMAGE_SLOT_PENDING_TEST = 2,      /**< Requested. Boots on the next reset if selected. */
    CRUX_IMAGE_SLOT_PENDING_PERMANENT = 3, /**< Reported only. This contract never creates it. */
    CRUX_IMAGE_SLOT_RUNNING_CONFIRMED = 4, /**< The running image, confirmed. */
    CRUX_IMAGE_SLOT_RUNNING_TESTING = 5, /**< The running image on trial: confirm, or the next reset
                                              erases it. */
    CRUX_IMAGE_SLOT_STANDBY_CONFIRMED = 6, /**< Valid, confirmed, not running: the fallback. */
    CRUX_IMAGE_SLOT_TRIED = 7,  /**< Selected by the bootloader, not running. Erased at the next
                                     reset. */
    CRUX_IMAGE_SLOT_INVALID = 8 /**< The trailer holds a value outside the defined ones. */
} crux_image_slot_state_t;

/** One slot as read from the medium. */
typedef struct {
    crux_image_slot_state_t state;
    crux_image_version_t version; /**< Meaningful unless state is EMPTY or INVALID. */
} crux_image_slot_info_t;

/** The boot record, derived once at start. */
typedef struct {
    crux_image_slot_t running_slot;
    bool running_confirmed; /**< False: the running image is on trial. */
    crux_image_version_t running_version;
    crux_image_slot_t inactive_slot; /**< Where the next image is written and requested. */
    bool bootloader_version_known;   /**< False when the bootloader reported no version. */
    crux_image_version_t bootloader_version;
    crux_image_slot_state_t slot_state_at_start[CRUX_IMAGE_SLOT_COUNT];
} crux_image_boot_record_t;

/**
 * What the update agent writes around a request, and clears after it has handled the outcome. The
 * contract defines the type and stores nothing. Where the record lives is the update agent's
 * design.
 */
typedef struct {
    crux_image_slot_t slot;
    crux_image_version_t version;
    bool requested; /**< False while staging. Set just before crux_image_request_test(). */
} crux_image_attempt_t;

/** What became of an attempt. See crux_image_outcome(). */
typedef enum {
    CRUX_IMAGE_OUTCOME_NONE = 0,       /**< No attempt, or a stale one. */
    CRUX_IMAGE_OUTCOME_TESTING = 1,    /**< The attempted image runs, unconfirmed. */
    CRUX_IMAGE_OUTCOME_CONFIRMED = 2,  /**< The attempted image runs, confirmed. */
    CRUX_IMAGE_OUTCOME_NOT_BOOTED = 3, /**< The request is pending, or was never made. */
    CRUX_IMAGE_OUTCOME_REVERTED = 4    /**< The attempted image is gone or refused. */
} crux_image_outcome_t;

/** Results; zero is success. */
typedef enum {
    CRUX_IMAGE_OK = 0,
    CRUX_IMAGE_ERR_INVALID_ARGUMENT = -1,
    CRUX_IMAGE_ERR_NOT_READY = -2,    /**< Not started, or the start failed. */
    CRUX_IMAGE_ERR_NO_BOOT_DATA = -3, /**< The boot data or a needed key is missing. */
    CRUX_IMAGE_ERR_BOOT_STATE = -4,   /**< The running trailer or the mode is not supported. */
    CRUX_IMAGE_ERR_IO = -5,           /**< The medium failed. */
    CRUX_IMAGE_ERR_ACTIVE_SLOT = -6,  /**< The request names the running slot. */
    CRUX_IMAGE_ERR_NO_IMAGE = -7,     /**< The slot has no valid header. */
    CRUX_IMAGE_ERR_NOT_NEWER = -8,    /**< The slot's version is not strictly newer. */
    CRUX_IMAGE_ERR_SLOT_STATE = -9,   /**< The slot is not STAGED, or PENDING_TEST for a repeat. */
    CRUX_IMAGE_ERR_NOT_CONFIRMED = -10, /**< The running image is on trial. */
    CRUX_IMAGE_ERR_BUSY = -11           /**< Another request or confirm is in progress. */
} crux_image_result_t;

/**
 * Derives the boot record from the boot data and the two slots, once. The provider fails closed
 * (row I6): it never guesses the running slot. It fails with CRUX_IMAGE_ERR_NO_BOOT_DATA when the
 * boot data, or the running-slot key or the mode key in it, is missing. It fails with
 * CRUX_IMAGE_ERR_BOOT_STATE when the mode is not RAM load, when the running slot is not 0 or 1, or
 * when the running slot is not in a state that the contract supports (no valid header, a trailer
 * magic that is not good, or a flag outside set and unset). A failed start caches nothing and may
 * be repeated. After a failed start every other call returns CRUX_IMAGE_ERR_NOT_READY. A missing
 * bootloader version does not fail the start: the record says it is not known.
 *
 * Calling it again after a success returns CRUX_IMAGE_OK and changes nothing.
 *
 * @return CRUX_IMAGE_OK, an error above, CRUX_IMAGE_ERR_IO when a slot cannot be read, or
 *         CRUX_IMAGE_ERR_BUSY when another thread is inside the service.
 */
CRUX_IMAGE_NODISCARD crux_image_result_t crux_image_start(void);

/**
 * Copies the boot record taken at start. It does not read the medium and does not block.
 *
 * @param[out] record Receives the record. Must not be NULL.
 * @return CRUX_IMAGE_OK, CRUX_IMAGE_ERR_INVALID_ARGUMENT or CRUX_IMAGE_ERR_NOT_READY.
 */
CRUX_IMAGE_NODISCARD crux_image_result_t
crux_image_boot_record_get(crux_image_boot_record_t *record);

/**
 * Reads one slot's live state from the medium. A trailer that no longer holds a supported value is
 * reported as CRUX_IMAGE_SLOT_INVALID, not hidden. After a confirm in this boot, the running slot
 * reads CRUX_IMAGE_SLOT_RUNNING_CONFIRMED, while the boot record still says it was on trial.
 *
 * @param slot Slot number, below CRUX_IMAGE_SLOT_COUNT.
 * @param[out] info Receives the state and the header version. Must not be NULL.
 * @return CRUX_IMAGE_OK, CRUX_IMAGE_ERR_INVALID_ARGUMENT, CRUX_IMAGE_ERR_NOT_READY or
 *         CRUX_IMAGE_ERR_IO.
 */
CRUX_IMAGE_NODISCARD crux_image_result_t crux_image_slot_get(crux_image_slot_t slot,
                                                             crux_image_slot_info_t *info);

/**
 * Asks the bootloader to boot the image in @p slot once, as a test. It requires, in this order:
 * a successful start (CRUX_IMAGE_ERR_NOT_READY), a slot below CRUX_IMAGE_SLOT_COUNT
 * (CRUX_IMAGE_ERR_INVALID_ARGUMENT), a slot other than the running one
 * (CRUX_IMAGE_ERR_ACTIVE_SLOT), a running image that is confirmed (CRUX_IMAGE_ERR_NOT_CONFIRMED), a
 * valid header in the slot (CRUX_IMAGE_ERR_NO_IMAGE), an image strictly newer than the running
 * image on major, minor and revision (CRUX_IMAGE_ERR_NOT_NEWER, so an equal or older image is
 * refused), and a slot that is CRUX_IMAGE_SLOT_STAGED, or CRUX_IMAGE_SLOT_PENDING_TEST for an
 * idempotent repeat that writes nothing (CRUX_IMAGE_ERR_SLOT_STATE for any other state, such as a
 * stale confirmed trailer, which the bootloader would treat as confirmed without a trial). The
 * running image's version is read from its header on the medium, not from the boot record.
 *
 * It then writes the request in the bootloader's order (magic, then the swap information, never
 * the confirm flag) and returns success only after the writes returned success. It does not reset:
 * a reset goes through the Reboot service. A failure after the first write leaves the slot
 * CRUX_IMAGE_SLOT_PENDING_TEST or CRUX_IMAGE_SLOT_STAGED, and a repeat of the request is safe.
 *
 * @param slot The slot that holds the staged image.
 * @return CRUX_IMAGE_OK, a refusal above, CRUX_IMAGE_ERR_IO, CRUX_IMAGE_ERR_BOOT_STATE when the
 *         running slot's live trailer is no longer a supported one, or CRUX_IMAGE_ERR_BUSY.
 */
CRUX_IMAGE_NODISCARD crux_image_result_t crux_image_request_test(crux_image_slot_t slot);

/**
 * Confirms the running image: writes the confirm flag of the running slot and of no other. It
 * never names a slot, so it cannot confirm the wrong one. If the running image is already
 * confirmed it returns CRUX_IMAGE_OK and writes nothing.
 *
 * @return CRUX_IMAGE_OK, CRUX_IMAGE_ERR_NOT_READY, CRUX_IMAGE_ERR_IO (the state stays
 *         CRUX_IMAGE_SLOT_RUNNING_TESTING), CRUX_IMAGE_ERR_BOOT_STATE or CRUX_IMAGE_ERR_BUSY.
 */
CRUX_IMAGE_NODISCARD crux_image_result_t crux_image_confirm(void);

/**
 * Compares two versions on major, minor and revision, in that order. The build number is ignored.
 * Pure. Both pointers must not be NULL.
 *
 * @return -1 if @p a is older than @p b, 0 if they are the same release, 1 if @p a is newer.
 */
int crux_image_version_compare(const crux_image_version_t *a, const crux_image_version_t *b);

/**
 * Derives what became of an attempt from the boot record and the attempt record. Pure: it reads
 * its arguments only. The first matching rule applies:
 * - no attempt (NULL), an attempt on a slot that does not exist, or no record: NONE;
 * - the attempted slot is the running slot: NONE if its version differs from the running version
 *   on major, minor and revision (stale, the slot was reused), otherwise CONFIRMED if the running
 *   image is confirmed and TESTING if it is not;
 * - the attempted slot held a confirmed image at start (STANDBY_CONFIRMED): NONE (stale);
 * - the agent never asked for a boot (`requested` false): NOT_BOOTED. The slot may read EMPTY,
 *   because the bootloader erases a newer image that was staged and not requested;
 * - `requested` true and the slot was STAGED, PENDING_TEST or PENDING_PERMANENT at start:
 *   NOT_BOOTED (the request was not consumed);
 * - `requested` true and the slot was EMPTY, TRIED or INVALID at start: REVERTED;
 * - any other state: NONE.
 *
 * Known limit: a power cut after `requested` was set and before the request writes landed reports
 * REVERTED for an image that never ran. The error is on the safe side: the agent retries.
 *
 * @param record  The boot record of this boot.
 * @param attempt The attempt record, or NULL.
 */
crux_image_outcome_t crux_image_outcome(const crux_image_boot_record_t *record,
                                        const crux_image_attempt_t *attempt);

#ifdef __cplusplus
}
#endif

#endif /* CRUX_IMAGE_STATE_H */
