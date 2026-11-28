/**
 * @file
 * @brief The update agent: check a candidate image, stage it in the inactive slot, ask for a test
 *        boot, confirm it, and report what became of the attempt.
 *
 * Status: Experimental (update agent design proposal, rows U1 to U7 and W4). A change is listed in
 * the release notes. See docs/update-agent-contract.md.
 *
 * The agent is a table of resting states, events and transitions (row U1). It runs on the caller's
 * thread: crux_update_begin() goes from the checks to the request in one call and blocks for the
 * length of the erase and the writes. It owns no thread, never resets the device and never makes a
 * permanent request. A reset goes through the Reboot service.
 *
 * Before the first erase or write it checks the whole image: the header, the load address, the
 * length, the version (strictly newer than the running image on major, minor and revision, row U3),
 * the SHA-256 and the signature. It records the attempt before it changes the slot, writes the body
 * first and the header last, reads the slot back, records that the request is made, and only then
 * asks the bootloader for a test boot (rows U4 and U5).
 *
 * The agent uses the image state contract (crux/image_state.h) for the slots' state and the
 * request. It reaches the staging slot, the attempt record, the digest and signature check and a
 * progress hook through providers that a composition links. A product links one provider of each;
 * the agent's core names no Zephyr, bootloader or board facility.
 *
 * Thread context only. crux_update_start(), crux_update_begin(), crux_update_confirm() and
 * crux_update_acknowledge() are serialised by one internal lock, and a caller that finds it taken
 * gets CRUX_UPDATE_ERR_BUSY at once. crux_update_status_get() and crux_update_cancel() may be
 * called from another thread while an attempt runs. None of the functions may be called from an
 * interrupt.
 *
 * The agent checks no permission. A management adapter checks access before it calls the agent.
 * The caller is trusted code.
 */
#ifndef CRUX_UPDATE_AGENT_H
#define CRUX_UPDATE_AGENT_H

#include <crux/image_state.h>

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** A call whose result must be used: an ignored result hides a refused or lost update. */
#if defined(__cplusplus)
#define CRUX_UPDATE_NODISCARD [[nodiscard]]
#elif defined(__GNUC__) || defined(__clang__)
#define CRUX_UPDATE_NODISCARD __attribute__((warn_unused_result))
#else
#define CRUX_UPDATE_NODISCARD
#endif

/** The resting states of row U1. An operation in progress is not a state. */
typedef enum {
    CRUX_UPDATE_STATE_NOT_STARTED = 0,  /**< crux_update_start() has not succeeded. */
    CRUX_UPDATE_STATE_UNAVAILABLE = 1,  /**< The image state contract failed to start. */
    CRUX_UPDATE_STATE_IDLE = 2,         /**< No attempt in flight and no outcome to report. */
    CRUX_UPDATE_STATE_OUTCOME = 3,      /**< A previous attempt has an unacknowledged outcome. */
    CRUX_UPDATE_STATE_TESTING = 4,      /**< The running image is on trial. Confirm is offered. */
    CRUX_UPDATE_STATE_CHECKED = 5,      /**< A source passed every check. Nothing is written. */
    CRUX_UPDATE_STATE_RECORDED = 6,     /**< The attempt is recorded, not yet requested. */
    CRUX_UPDATE_STATE_ERASED = 7,       /**< The staging slot is blank, trailer included. */
    CRUX_UPDATE_STATE_BODY_WRITTEN = 8, /**< The image without its header is in the slot. */
    CRUX_UPDATE_STATE_STAGED = 9,       /**< The header is written. */
    CRUX_UPDATE_STATE_VERIFIED = 10,    /**< The read-back matches the checked image. */
    CRUX_UPDATE_STATE_WAITING_RESET = 11, /**< The test boot is requested. A reset boots it. */
    CRUX_UPDATE_STATE_FAILED = 12         /**< The attempt ended without a request. */
} crux_update_state_t;

/** Results; zero is success. A refusal of the checks leaves the staging slot untouched. */
typedef enum {
    CRUX_UPDATE_OK = 0,
    CRUX_UPDATE_ERR_INVALID_ARGUMENT = -1,
    CRUX_UPDATE_ERR_NOT_READY = -2,     /**< Not started, or the image state contract failed. */
    CRUX_UPDATE_ERR_BUSY = -3,          /**< Another call is inside the agent, or a test boot is
                                             already requested. */
    CRUX_UPDATE_ERR_NOT_CONFIRMED = -4, /**< The running image is on trial. */
    CRUX_UPDATE_ERR_STATE = -5,         /**< The event is not allowed in the current state. */
    CRUX_UPDATE_ERR_SOURCE = -6,        /**< The source could not be read. */
    CRUX_UPDATE_ERR_FORMAT = -7,        /**< Header magic, header size or metadata layout (G1). */
    CRUX_UPDATE_ERR_LOAD_ADDRESS = -8,  /**< Not RAM-load, or not the configured address (G2). */
    CRUX_UPDATE_ERR_LENGTH = -9,        /**< The image length is not the source size (G3). */
    CRUX_UPDATE_ERR_TOO_LARGE = -10,    /**< The image would reach the slot trailer (G4). */
    CRUX_UPDATE_ERR_NOT_NEWER = -11,    /**< Not strictly newer than the running image (G5). */
    CRUX_UPDATE_ERR_HASH = -12,         /**< The SHA-256 does not match its metadata (G6). */
    CRUX_UPDATE_ERR_SIGNATURE = -13,    /**< The signature is missing or does not verify (G7). */
    CRUX_UPDATE_ERR_RECORD = -14,       /**< The attempt record could not be stored or cleared. */
    CRUX_UPDATE_ERR_ERASE = -15,        /**< The staging slot could not be erased. */
    CRUX_UPDATE_ERR_WRITE = -16,        /**< The staging slot could not be written. */
    CRUX_UPDATE_ERR_VERIFY = -17,       /**< The read-back did not match the checked image. */
    CRUX_UPDATE_ERR_REQUEST = -18,      /**< The test-boot request failed. */
    CRUX_UPDATE_ERR_CANCELLED = -19,    /**< crux_update_cancel() ended the attempt. */
    CRUX_UPDATE_ERR_IO = -20            /**< The confirm write failed. */
} crux_update_result_t;

/** Composition inputs. The signature key is the verify provider's input, not the agent's. */
typedef struct {
    uint16_t header_size;  /**< The image header size the composition signs with. */
    uint32_t load_address; /**< The RAM-load address the composition builds for. */
} crux_update_config_t;

/**
 * The candidate image: a known size and random-access reads. The agent reads it twice, once to
 * check it and once to write it, and the read-back of the slot catches a change between the two.
 */
typedef struct {
    size_t size;
    /** Reads @p length bytes at @p offset into @p buffer. Returns true on success. */
    bool (*read)(void *context, size_t offset, void *buffer, size_t length);
    void *context;
} crux_update_source_t;

/** A source over bytes in memory, for crux_update_source_memory(). */
typedef struct {
    const uint8_t *data;
    size_t size;
} crux_update_memory_source_t;

/**
 * A copy of the agent's state, taken without blocking on an attempt that runs.
 * @c last_result is the reason of the last refusal or failure, or CRUX_UPDATE_OK.
 */
typedef struct {
    crux_update_state_t state;
    crux_update_result_t last_result;
    crux_image_outcome_t outcome; /**< Meaningful in OUTCOME and TESTING. */
    bool attempt_present;         /**< The attempt record holds @c attempt. */
    crux_image_attempt_t attempt;
    bool record_lost;  /**< The attempt record was unreadable at start: an outcome may be lost. */
    bool slot_staged;  /**< FAILED left a staged image that the bootloader erases at the reset. */
    uint32_t progress_done;  /**< Bytes erased, written or read back in the current phase. */
    uint32_t progress_total; /**< Bytes of the current phase. */
} crux_update_status_t;

/**
 * Starts the agent once per boot (rows TR1 to TR5). It starts the image state contract, loads the
 * attempt record and classifies the outcome. It writes nothing. A failed contract start leaves the
 * agent UNAVAILABLE, and every other call then returns CRUX_UPDATE_ERR_NOT_READY. An unreadable
 * attempt record is treated as none and sets @c record_lost.
 *
 * Calling it again after it has run returns the same result and changes nothing.
 *
 * @param config Composition inputs. Must not be NULL, and @c header_size must not be zero.
 * @return CRUX_UPDATE_OK, CRUX_UPDATE_ERR_INVALID_ARGUMENT, CRUX_UPDATE_ERR_NOT_READY or
 *         CRUX_UPDATE_ERR_BUSY.
 */
CRUX_UPDATE_NODISCARD crux_update_result_t crux_update_start(const crux_update_config_t *config);

/**
 * Runs one attempt from IDLE, OUTCOME or FAILED (rows TR6 to TR13). It checks the whole source
 * before any write: a refusal returns the refusal code, writes nothing and leaves the state as it
 * was. After the checks it records the attempt, erases the inactive slot, writes the body and then
 * the header, reads the slot back, records the request and asks for a test boot. On success the
 * state is WAITING_RESET, and the next reset boots the image on trial. A failure after the checks
 * ends in FAILED, invalidates a slot that already has a header (best effort, @c slot_staged when it
 * could not), and never touches the running image.
 *
 * It refuses while the running image is on trial (CRUX_UPDATE_ERR_NOT_CONFIRMED) and after a
 * request (CRUX_UPDATE_ERR_BUSY).
 *
 * @param source The candidate image. Must not be NULL and must stay valid during the call.
 * @return CRUX_UPDATE_OK, a refusal, or the failure of the step that failed.
 */
CRUX_UPDATE_NODISCARD crux_update_result_t crux_update_begin(const crux_update_source_t *source);

/**
 * Asks a running crux_update_begin() to stop at the next point between two sector operations,
 * before the request. A request that was made is never withdrawn.
 *
 * @return CRUX_UPDATE_OK when an attempt runs, CRUX_UPDATE_ERR_STATE otherwise.
 */
crux_update_result_t crux_update_cancel(void);

/**
 * Confirms the running image in TESTING (row TR14). On success the state is OUTCOME with
 * CONFIRMED when the attempt record names the running image, and IDLE when no record does. A
 * failed write keeps TESTING, and a retry is allowed.
 *
 * @return CRUX_UPDATE_OK, CRUX_UPDATE_ERR_NOT_READY, CRUX_UPDATE_ERR_STATE, CRUX_UPDATE_ERR_IO or
 *         CRUX_UPDATE_ERR_BUSY.
 */
CRUX_UPDATE_NODISCARD crux_update_result_t crux_update_confirm(void);

/**
 * Acknowledges an outcome or a failure (row TR15): clears the attempt record and returns to IDLE.
 * A failed clear keeps the state. A stale record is harmless.
 *
 * @return CRUX_UPDATE_OK, CRUX_UPDATE_ERR_NOT_READY, CRUX_UPDATE_ERR_STATE,
 *         CRUX_UPDATE_ERR_RECORD or CRUX_UPDATE_ERR_BUSY.
 */
CRUX_UPDATE_NODISCARD crux_update_result_t crux_update_acknowledge(void);

/**
 * Copies a consistent snapshot of the agent's state. It does not wait for an attempt. If the
 * snapshot changes during every one of a few tries, it returns CRUX_UPDATE_ERR_BUSY, and the
 * caller may try again.
 *
 * @param[out] status Receives the snapshot. Must not be NULL.
 * @return CRUX_UPDATE_OK, CRUX_UPDATE_ERR_INVALID_ARGUMENT or CRUX_UPDATE_ERR_BUSY.
 */
CRUX_UPDATE_NODISCARD crux_update_result_t crux_update_status_get(crux_update_status_t *status);

/**
 * Makes a source over @p size bytes at @p data. @p memory holds the view and must outlive the
 * source. Both pointers must not be NULL.
 *
 * @return The source.
 */
crux_update_source_t crux_update_source_memory(crux_update_memory_source_t *memory,
                                               const void *data, size_t size);

#ifdef __cplusplus
}
#endif

#endif /* CRUX_UPDATE_AGENT_H */
