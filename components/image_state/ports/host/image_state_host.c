/*
 * The Host double of the image state contract: a fake medium and a hand model of the bootloader
 * (see image_state_host.h). The model's version order is written out here on purpose and does not
 * call crux_image_version_compare(), so that the two can disagree and a test can see it.
 */
#include "image_state_host.h"

#include <string.h>

#define HOST_LOG_CAPACITY 16u

typedef struct {
    image_state_host_write_t op;
    crux_image_slot_t slot;
} host_log_entry_t;

static crux_image_port_slot_view_t slots[CRUX_IMAGE_SLOT_COUNT];
static bool image_valid[CRUX_IMAGE_SLOT_COUNT];
static crux_image_port_shared_data_t shared;
static bool shared_absent;
static host_log_entry_t log_entries[HOST_LOG_CAPACITY];
static size_t log_count;
static size_t writes_until_failure;
static void (*write_hook)(void);
static bool copy_done_write_fails;
static bool read_fails[CRUX_IMAGE_SLOT_COUNT];

void image_state_host_init(void)
{
    memset(slots, 0, sizeof(slots));
    slots[0].header_valid = true;
    slots[0].version = (crux_image_version_t){1, 0, 0, 0};
    slots[0].magic = CRUX_IMAGE_PORT_MAGIC_GOOD;
    slots[0].image_ok = CRUX_IMAGE_PORT_FLAG_SET;
    slots[0].copy_done = CRUX_IMAGE_PORT_FLAG_SET;
    image_valid[0] = true;
    image_valid[1] = true;
    shared =
        (crux_image_port_shared_data_t){true, 0, CRUX_IMAGE_PORT_MODE_RAM_LOAD, true, {2, 4, 0, 0}};
    shared_absent = false;
    memset(log_entries, 0, sizeof(log_entries));
    log_count = 0;
    writes_until_failure = 0;
    write_hook = NULL;
    copy_done_write_fails = false;
    memset(read_fails, 0, sizeof(read_fails));
    crux_image_core_reset();
}

void image_state_host_slot_put(crux_image_slot_t slot, const crux_image_port_slot_view_t *view)
{
    slots[slot] = *view;
}

crux_image_port_slot_view_t image_state_host_slot_peek(crux_image_slot_t slot)
{
    return slots[slot];
}

void image_state_host_slot_set_image_valid(crux_image_slot_t slot, bool valid)
{
    image_valid[slot] = valid;
}

void image_state_host_shared_put(const crux_image_port_shared_data_t *data)
{
    shared = *data;
}

void image_state_host_shared_set_absent(bool absent)
{
    shared_absent = absent;
}

static void erase(crux_image_slot_t slot)
{
    memset(&slots[slot], 0, sizeof(slots[slot]));
    image_valid[slot] = true;
}

void image_state_host_stage(crux_image_slot_t slot, crux_image_version_t version)
{
    erase(slot);
    slots[slot].header_valid = true;
    slots[slot].version = version;
}

size_t image_state_host_write_count(void)
{
    return log_count;
}

image_state_host_write_t image_state_host_write_op(size_t index)
{
    return log_entries[index].op;
}

crux_image_slot_t image_state_host_write_slot(size_t index)
{
    return log_entries[index].slot;
}

void image_state_host_fail_nth_write(size_t n)
{
    writes_until_failure = n;
}

void image_state_host_fail_slot_read(crux_image_slot_t slot, bool fails)
{
    read_fails[slot] = fails;
}

void image_state_host_set_write_hook(void (*hook)(void))
{
    write_hook = hook;
}

void image_state_host_set_copy_done_write_fails(bool fails)
{
    copy_done_write_fails = fails;
}

/* Logs the write and says whether it lands. A failed write changes nothing and is not logged. */
static bool write_lands(image_state_host_write_t op, crux_image_slot_t slot)
{
    if (write_hook != NULL) {
        write_hook();
    }
    if (writes_until_failure != 0 && --writes_until_failure == 0) {
        return false;
    }
    if (log_count < HOST_LOG_CAPACITY) {
        log_entries[log_count].op = op;
        log_entries[log_count].slot = slot;
        log_count++;
    }
    return true;
}

bool crux_image_port_shared_data_get(crux_image_port_shared_data_t *out)
{
    if (shared_absent) {
        return false;
    }
    *out = shared;
    return true;
}

crux_image_result_t crux_image_port_slot_read(crux_image_slot_t slot,
                                              crux_image_port_slot_view_t *view)
{
    if (read_fails[slot]) {
        return CRUX_IMAGE_ERR_IO;
    }
    *view = slots[slot];
    return CRUX_IMAGE_OK;
}

crux_image_result_t crux_image_port_write_magic(crux_image_slot_t slot)
{
    if (!write_lands(IMAGE_STATE_HOST_WRITE_MAGIC, slot)) {
        return CRUX_IMAGE_ERR_IO;
    }
    slots[slot].magic = CRUX_IMAGE_PORT_MAGIC_GOOD;
    return CRUX_IMAGE_OK;
}

crux_image_result_t crux_image_port_write_swap_info_test(crux_image_slot_t slot)
{
    if (!write_lands(IMAGE_STATE_HOST_WRITE_SWAP_INFO_TEST, slot)) {
        return CRUX_IMAGE_ERR_IO;
    }
    return CRUX_IMAGE_OK;
}

crux_image_result_t crux_image_port_write_image_ok(crux_image_slot_t slot)
{
    if (!write_lands(IMAGE_STATE_HOST_WRITE_IMAGE_OK, slot)) {
        return CRUX_IMAGE_ERR_IO;
    }
    slots[slot].image_ok = CRUX_IMAGE_PORT_FLAG_SET;
    return CRUX_IMAGE_OK;
}

/* Strictly greater on major, minor and revision. The build number is ignored. */
static bool model_newer(const crux_image_version_t *a, const crux_image_version_t *b)
{
    if (a->major != b->major) {
        return a->major > b->major;
    }
    if (a->minor != b->minor) {
        return a->minor > b->minor;
    }
    return a->revision > b->revision;
}

void image_state_host_boot(void)
{
    bool tried[CRUX_IMAGE_SLOT_COUNT] = {false, false};
    bool booted = false;
    uint32_t running = 0;

    while (!booted) {
        /* The available slot with the highest version. On equal versions the lower slot wins. */
        int best = -1;
        for (crux_image_slot_t s = 0; s < CRUX_IMAGE_SLOT_COUNT; s++) {
            if (!slots[s].header_valid || tried[s]) {
                continue;
            }
            if (best < 0 || model_newer(&slots[s].version, &slots[best].version)) {
                best = s;
            }
        }
        if (best < 0) {
            break;
        }
        crux_image_slot_t slot = (crux_image_slot_t)best;
        tried[slot] = true;
        /* Select or erase, before the image is loaded or validated. */
        if (slots[slot].magic != CRUX_IMAGE_PORT_MAGIC_GOOD ||
            (slots[slot].copy_done == CRUX_IMAGE_PORT_FLAG_SET &&
             slots[slot].image_ok != CRUX_IMAGE_PORT_FLAG_SET)) {
            erase(slot);
            continue;
        }
        if (!copy_done_write_fails) {
            slots[slot].copy_done = CRUX_IMAGE_PORT_FLAG_SET;
        }
        /* A validation failure only makes the slot unavailable for this boot. */
        if (!image_valid[slot]) {
            continue;
        }
        running = slot;
        booted = true;
    }
    shared.running_slot_present = booted;
    shared.running_slot = running;
}
