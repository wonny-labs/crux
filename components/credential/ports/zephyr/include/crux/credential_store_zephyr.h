#ifndef CRUX_CREDENTIAL_STORE_ZEPHYR_H
#define CRUX_CREDENTIAL_STORE_ZEPHYR_H

/**
 * @file
 * @brief Erase of the credential store, for a product's factory reset, and of its accounts only.
 * A composition interface.
 *
 * Status: Experimental (ADR-0001 decision 4). A change is listed in the release notes.
 *
 * This is a composition interface, not a portable one (rules of docs/composition-interfaces.md).
 * Only the platform composition of a product calls it, from a local trigger that the product
 * owns, and a native-free consumer check rejects the target that publishes it
 * (crux::credential_store_zephyr). The header includes no Zephyr, vendor, board or adapter
 * header.
 *
 * A product reaches it by linking the CMake target crux::credential_store_zephyr, which adds this
 * include root and crux::credential_store. The credential store itself is built by the module
 * under CONFIG_CRUX_ACCESS and is not linked by this target. The steps of a factory reset, with
 * the settings file and the restart, are in docs/management-in-a-product.md#factory-reset.
 */

#include <crux/credential_store.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Overwrite both slots with zeros, sync and remove them, in any state after start. Every record
 * goes: the accounts, the TLS key and certificate and the SSH host key.
 *
 * The function takes no session and checks no permission, so the caller is the whole protection.
 * Call it only after a trigger that proves physical access or an authenticated administrator: a
 * button held while the device starts, or a command that needs a login and the permission
 * access.manage. Never offer an unauthenticated wipe, such as a serial command without a login:
 * it would let anyone on the serial line take over the device (decision S4).
 *
 * The state is UNUSABLE from this call until the next reset, and then EMPTY when both slots were
 * removed, which opens first-account setup again. Restart the device as soon as the call returns:
 * until then Access keeps in RAM the accounts it loaded, and sessions stay valid. The device keys
 * are generated again at the next start, so clients see a new certificate and host key. A reset
 * during the erase can leave a valid slot, so repeat the erase until it returns OK.
 *
 * The call does not prove physical erasure: a card's internal mapping can keep old pages. It
 * erases the credential store only. Settings and files are the product's to remove.
 *
 * Thread context only. It waits on storage and on the store lock, and holds at most one File
 * handle. Call it after crux_security_event_init() to have the event credential.erased recorded,
 * and after crux_credential_start().
 *
 * @retval CRUX_CREDENTIAL_OK Both slots are gone.
 * @retval CRUX_CREDENTIAL_ERR_STORE A step failed, for example a full File pool or a medium
 * error. The state is UNUSABLE. Repeat the call.
 * @retval CRUX_CREDENTIAL_ERR_NOT_READY Not started, or the store lock could not be taken. Nothing
 * was done.
 */
crux_credential_result_t crux_credential_erase(void);

/**
 * Remove the accounts from both slots and keep the device identity: the TLS key, the TLS
 * certificate, whether self-signed or installed by an operator, and the SSH host key. The accounts
 * record holds every account, password hash, role and SSH user key, so all of them go.
 *
 * Use it only to recover a device for the same owner, for example after every administrator
 * password is lost. Clients then keep seeing the fingerprints they already trust. The kept private
 * keys are as readable as the rest of the store to anyone who can read the medium and the chip ID,
 * so a transfer of ownership, a resale or decommissioning uses the full erase,
 * crux_credential_erase(), and prepares the device again.
 *
 * The caller is the whole protection, as for the full erase: the same triggers and the same rule
 * against an unauthenticated wipe apply.
 *
 * The state is UNUSABLE from this call until the next reset, and then VALID with no accounts, which
 * opens first-account setup again. Restart the device as soon as the call returns: until then
 * Access keeps the accounts it loaded in RAM, and sessions stay valid, but nothing more is saved.
 * The new image reaches both slots before OK, so no copy of the accounts is left in either slot. A
 * reset during the call can leave them in the older slot, and the next start removes them from
 * there. If the accounts still load after a reset, repeat the call.
 *
 * The same limits as the full erase apply to physical erasure. It changes the credential store
 * only.
 *
 * Thread context only. It waits on storage and on the store lock, holds at most one File handle,
 * and records the event credential.erased with the subject accounts. Call it after
 * crux_credential_start().
 *
 * @retval CRUX_CREDENTIAL_OK Neither slot holds the accounts, or the store was EMPTY.
 * @retval CRUX_CREDENTIAL_ERR_STORE A write failed, for example a full File pool or a medium error.
 * The state is UNUSABLE. Restart, then repeat the call.
 * @retval CRUX_CREDENTIAL_ERR_ENTROPY No random data for the new image. Nothing was written. The
 * state is UNUSABLE. Restart, then repeat the call.
 * @retval CRUX_CREDENTIAL_ERR_READ The active slot could not be read. Nothing was written, and the
 * state is unchanged. Use the full erase if it persists.
 * @retval CRUX_CREDENTIAL_ERR_UNUSABLE The state is UNUSABLE, so the identity cannot be read to be
 * kept. Nothing was done. Use the full erase.
 * @retval CRUX_CREDENTIAL_ERR_NOT_READY Not started, or the store lock could not be taken. Nothing
 * was done.
 */
crux_credential_result_t crux_credential_erase_accounts(void);

#ifdef __cplusplus
}
#endif

#endif /* CRUX_CREDENTIAL_STORE_ZEPHYR_H */
