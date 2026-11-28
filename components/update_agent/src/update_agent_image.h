/*
 * The image layout the agent reads: the bootloader's image header and its two metadata areas
 * (protected and unprotected), each a 4-byte information header followed by entries of a 16-bit
 * type, a 16-bit length and the value. Little-endian. Pure functions, private to the core.
 *
 * The field order and the constants follow MCUboot's boot/bootutil/include/bootutil/image.h at the
 * revision that Zephyr v4.4.2 pins (6d3b3d2c). They are restated here, not copied, so that the core
 * includes no bootloader header.
 */
#ifndef CRUX_UPDATE_AGENT_IMAGE_H
#define CRUX_UPDATE_AGENT_IMAGE_H

#include <crux/image_state.h>

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define UPDATE_IMAGE_MAGIC 0x96f3b83du
#define UPDATE_IMAGE_HEADER_FIELDS_SIZE 32u /* the fields; the header area may be larger */
#define UPDATE_IMAGE_FLAG_RAM_LOAD 0x00000020u
#define UPDATE_IMAGE_TLV_INFO_MAGIC 0x6907u
#define UPDATE_IMAGE_TLV_PROT_INFO_MAGIC 0x6908u
#define UPDATE_IMAGE_TLV_INFO_SIZE 4u
#define UPDATE_IMAGE_TLV_ENTRY_HEADER_SIZE 4u
#define UPDATE_IMAGE_TLV_SHA256 0x10u
#define UPDATE_IMAGE_TLV_ECDSA_SIG 0x22u

typedef struct {
    uint32_t magic;
    uint32_t load_address;
    uint16_t header_size;
    uint16_t protect_tlv_size;
    uint32_t image_size;
    uint32_t flags;
    crux_image_version_t version;
} update_image_header_t;

/** Reads the header fields from @p bytes (at least UPDATE_IMAGE_HEADER_FIELDS_SIZE). No checks. */
void update_image_header_read(const uint8_t *bytes, update_image_header_t *header);

/** Reads a metadata information header: its magic and its total length (header included). */
void update_image_tlv_info_read(const uint8_t *bytes, uint16_t *magic, uint16_t *total);

/**
 * Finds the one entry of @p type in a metadata area whose information header was already checked.
 * @p area holds the whole area, information header included. Returns 1 and sets the value when
 * exactly one entry exists, 0 when none exists, and -1 when the entries do not fill the area
 * exactly or the type occurs more than once.
 */
int update_image_tlv_find(const uint8_t *area, size_t area_size, uint16_t type,
                          const uint8_t **value, uint16_t *value_length);

#endif /* CRUX_UPDATE_AGENT_IMAGE_H */
