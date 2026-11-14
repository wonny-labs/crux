/**
 * @file
 * @brief Starting the credential store, and the result type of its operations.
 *
 * Status: Experimental (ADR-0001 decision 4). Access and the security events that it is wired to
 * have no Zephyr composition outside tests/ yet, and a change is listed in the release notes.
 *
 * A product calls crux_credential_start() once, with the two File roots that hold the slots, and
 * reads the store's state with <crux/credential_store.h>. The operations on records and device keys
 * are not part of this interface: the services that need them reach them through a private adapter,
 * and a product never reads or writes a record itself. This header is separate from
 * <crux/credential_store.h> so that a reader of the state, such as the status service, does not
 * need the File contract. See docs/credential-store.md.
 */
#ifndef CRUX_CREDENTIAL_STORE_START_H
#define CRUX_CREDENTIAL_STORE_START_H

#include <crux/file.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Store results; zero is success and every other value is a refusal or a failure. */
typedef enum {
    CRUX_CREDENTIAL_OK = 0,
    CRUX_CREDENTIAL_ERR_INVALID_ARGUMENT = -1,
    CRUX_CREDENTIAL_ERR_NOT_READY = -2, /**< Not started, or the store lock could not be taken. */
    CRUX_CREDENTIAL_ERR_UNUSABLE =
        -3, /**< State is UNUSABLE. Nothing is read, written or generated. */
    CRUX_CREDENTIAL_ERR_NOT_FOUND = -4, /**< Record absent from an EMPTY or VALID store. */
    CRUX_CREDENTIAL_ERR_TOO_LARGE =
        -5, /**< Buffer too small, a record over its limit, or a full slot. */
    CRUX_CREDENTIAL_ERR_ENTROPY = -6, /**< No random data for a key or nonce. Nothing was stored. */
    /**
     * A save failed. The previous image stays active, except that a failure writing the second slot
     * for an added record leaves that record active, and it survives a reset (decision S7). Stored
     * bytes can change either way, and a failed save can win at the next boot if the store could
     * not then invalidate it.
     */
    CRUX_CREDENTIAL_ERR_STORE = -7,
    CRUX_CREDENTIAL_ERR_READ = -8 /**< A runtime read failed. Store state is unchanged. */
} crux_credential_result_t;

/**
 * Classify the two slots and make the store usable. A composition calls this once on every boot
 * path, whether or not the medium mounted, before any other thread uses the store and before
 * crux_access_init(). An unbound root gives UNUSABLE, which lasts until the next reset.
 *
 * Thread context only. It can wait on storage and on the store lock. A product does not generate
 * device keys: crux_tls_certificate_start() ensures the TLS key, and the SSH composition code of
 * phase 3 ensures the SSH host key before it starts the provider.
 *
 * @param slot_a File root of the first slot. No file area may name it.
 * @param slot_b File root of the second slot, on a path that does not overlap the first.
 * @retval CRUX_CREDENTIAL_OK The state is EMPTY or VALID.
 * @retval CRUX_CREDENTIAL_ERR_UNUSABLE Started, and the state is UNUSABLE.
 * @retval CRUX_CREDENTIAL_ERR_INVALID_ARGUMENT Equal roots, or a repeated call. Nothing changed.
 * @retval CRUX_CREDENTIAL_ERR_NOT_READY No lock was available. Not started.
 */
crux_credential_result_t crux_credential_start(crux_file_root_t slot_a, crux_file_root_t slot_b);

#ifdef __cplusplus
}
#endif

#endif
