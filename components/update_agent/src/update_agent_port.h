/*
 * Private ports of the update agent's core. Not a public header: it is not under include/, no
 * usage target exports it, and only a provider and the core include it. A composition links one
 * provider of each port. The Host fakes of the tests implement them over memory; the Zephyr
 * providers (flash areas, NVS, PSA Crypto) are a separate piece of work.
 *
 * Every port function returns true on success. A provider carries no Zephyr or bootloader type
 * across this seam.
 */
#ifndef CRUX_UPDATE_AGENT_PORT_H
#define CRUX_UPDATE_AGENT_PORT_H

#include <crux/update_agent.h>

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/*
 * Slot port: the staging slot. Sectors are uniform; sector 0 holds the image header. The trailer
 * area is the last trailer_size bytes of the slot, and the capacity for an image is size minus
 * trailer_size. A provider refuses a slot that is not the staging slot of this boot.
 */
typedef struct {
    uint32_t size;         /**< The whole slot, trailer included. A multiple of sector_size. */
    uint32_t sector_size;  /**< The erase unit. */
    uint32_t trailer_size; /**< The bootloader's trailer area at the end of the slot. */
    uint32_t write_block;  /**< Writes are whole multiples of this, at offsets aligned to it. */
    uint8_t erased_value;  /**< What an erased byte reads as. */
} crux_update_port_slot_geometry_t;

bool crux_update_port_slot_geometry(crux_image_slot_t slot, crux_update_port_slot_geometry_t *geo);
bool crux_update_port_slot_erase(crux_image_slot_t slot, uint32_t sector);
/** Whether every byte of the sector reads as the erased value. */
bool crux_update_port_slot_sector_blank(crux_image_slot_t slot, uint32_t sector, bool *blank);
bool crux_update_port_slot_write(crux_image_slot_t slot, uint32_t offset, const void *data,
                                 uint32_t length);
bool crux_update_port_slot_read(crux_image_slot_t slot, uint32_t offset, void *data,
                                uint32_t length);

/*
 * Record port: the attempt record. store() returns true only when the record is durable. After a
 * power cut at any point of a store, load() returns the new record or the previous one, never a
 * mixture, and a torn store is detected, not accepted (row U2). load() returns false when the
 * store cannot be read at all; *present is then meaningless.
 */
bool crux_update_port_record_load(bool *present, crux_image_attempt_t *attempt);
bool crux_update_port_record_store(const crux_image_attempt_t *attempt);
bool crux_update_port_record_clear(void);

/*
 * Verify port: SHA-256 in two independent contexts and the signature check over a digest. The
 * public key is the provider's composition input. The signature is the value of the image's
 * ECDSA signature entry as the image carries it.
 */
#define CRUX_UPDATE_DIGEST_SIZE 32u

typedef enum {
    CRUX_UPDATE_HASH_IMAGE = 0, /**< The range the image's SHA-256 entry covers. */
    CRUX_UPDATE_HASH_COPY = 1   /**< Every byte of the image, for the read-back compare. */
} crux_update_hash_context_t;

bool crux_update_port_hash_begin(crux_update_hash_context_t context);
bool crux_update_port_hash_update(crux_update_hash_context_t context, const void *data,
                                  size_t length);
bool crux_update_port_hash_finish(crux_update_hash_context_t context,
                                  uint8_t digest[CRUX_UPDATE_DIGEST_SIZE]);
bool crux_update_port_signature_verify(const uint8_t digest[CRUX_UPDATE_DIGEST_SIZE],
                                       const uint8_t *signature, size_t signature_length);

/*
 * Progress port: called between two sector operations, so that a composition can feed a watchdog.
 * It may call crux_update_cancel(). It must not call any other function of the agent.
 */
void crux_update_port_progress(crux_update_state_t phase, uint32_t done, uint32_t total);

/*
 * Test control: forgets everything the agent holds in RAM, as a reset does. Called by a test
 * composition between two simulated boots. A product never calls it.
 */
void crux_update_core_reset(void);

#endif /* CRUX_UPDATE_AGENT_PORT_H */
