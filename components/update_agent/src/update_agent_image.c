/* The image layout, read without a bootloader header. See update_agent_image.h. */
#include "update_agent_image.h"

static uint16_t read_u16(const uint8_t *bytes)
{
    return (uint16_t)((unsigned)bytes[0] | ((unsigned)bytes[1] << 8));
}

static uint32_t read_u32(const uint8_t *bytes)
{
    return (uint32_t)bytes[0] | ((uint32_t)bytes[1] << 8) | ((uint32_t)bytes[2] << 16) |
           ((uint32_t)bytes[3] << 24);
}

void update_image_header_read(const uint8_t *bytes, update_image_header_t *header)
{
    header->magic = read_u32(&bytes[0]);
    header->load_address = read_u32(&bytes[4]);
    header->header_size = read_u16(&bytes[8]);
    header->protect_tlv_size = read_u16(&bytes[10]);
    header->image_size = read_u32(&bytes[12]);
    header->flags = read_u32(&bytes[16]);
    header->version.major = bytes[20];
    header->version.minor = bytes[21];
    header->version.revision = read_u16(&bytes[22]);
    header->version.build = read_u32(&bytes[24]);
    /* bytes 28 to 31 are padding */
}

void update_image_tlv_info_read(const uint8_t *bytes, uint16_t *magic, uint16_t *total)
{
    *magic = read_u16(&bytes[0]);
    *total = read_u16(&bytes[2]);
}

int update_image_tlv_find(const uint8_t *area, size_t area_size, uint16_t type,
                          const uint8_t **value, uint16_t *value_length)
{
    int found = 0;
    size_t at = UPDATE_IMAGE_TLV_INFO_SIZE;
    while (at < area_size) {
        if (area_size - at < UPDATE_IMAGE_TLV_ENTRY_HEADER_SIZE) {
            return -1;
        }
        uint16_t entry_type = read_u16(&area[at]);
        uint16_t entry_length = read_u16(&area[at + 2u]);
        at += UPDATE_IMAGE_TLV_ENTRY_HEADER_SIZE;
        if (area_size - at < entry_length) {
            return -1;
        }
        if (entry_type == type) {
            if (found != 0) {
                return -1;
            }
            found = 1;
            *value = &area[at];
            *value_length = entry_length;
        }
        at += entry_length;
    }
    return found;
}
