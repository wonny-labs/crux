/*
 * The service of the contract over the private port: start, the live and cached queries, the test
 * request and the confirm. It fails closed (row I6): it never guesses the running slot, and a
 * failed start leaves every other call returning CRUX_IMAGE_ERR_NOT_READY.
 *
 * One lock serialises start, request and confirm. It is a try-lock: a caller that finds it taken
 * gets CRUX_IMAGE_ERR_BUSY at once, which is a bounded wait of zero. The cached record is written
 * once under the lock and published with a release store, so the query calls read it without the
 * lock after they have seen the start succeed.
 */
#include "image_state_port.h"

#include <stdatomic.h>
#include <stddef.h>

static atomic_flag lock = ATOMIC_FLAG_INIT;
static atomic_bool started;
static crux_image_boot_record_t cached;

void crux_image_core_reset(void)
{
    while (atomic_flag_test_and_set_explicit(&lock, memory_order_acquire)) {
    }
    atomic_store_explicit(&started, false, memory_order_release);
    cached = (crux_image_boot_record_t){0};
    atomic_flag_clear_explicit(&lock, memory_order_release);
}

static bool lock_take(void)
{
    return !atomic_flag_test_and_set_explicit(&lock, memory_order_acquire);
}

static void lock_give(void)
{
    atomic_flag_clear_explicit(&lock, memory_order_release);
}

static bool is_started(void)
{
    return atomic_load_explicit(&started, memory_order_acquire);
}

static bool slot_valid(crux_image_slot_t slot)
{
    return slot < CRUX_IMAGE_SLOT_COUNT;
}

/* Reads one slot from the live medium and classifies it. The cache must be published. */
static crux_image_result_t read_state(crux_image_slot_t slot, crux_image_port_slot_view_t *view,
                                      crux_image_slot_state_t *state)
{
    crux_image_result_t result = crux_image_port_slot_read(slot, view);
    if (result != CRUX_IMAGE_OK) {
        return result;
    }
    return crux_image_slot_state_derive(slot == cached.running_slot, view, state);
}

static crux_image_result_t start_locked(void)
{
    if (is_started()) {
        return CRUX_IMAGE_OK; /* the record is cached and nothing changes */
    }

    crux_image_port_shared_data_t shared;
    if (!crux_image_port_shared_data_get(&shared) || !shared.running_slot_present ||
        shared.mode == CRUX_IMAGE_PORT_MODE_MISSING) {
        return CRUX_IMAGE_ERR_NO_BOOT_DATA;
    }
    if (shared.mode != CRUX_IMAGE_PORT_MODE_RAM_LOAD ||
        shared.running_slot >= CRUX_IMAGE_SLOT_COUNT) {
        return CRUX_IMAGE_ERR_BOOT_STATE;
    }

    crux_image_boot_record_t record = {0};
    record.running_slot = (crux_image_slot_t)shared.running_slot;
    record.inactive_slot = (crux_image_slot_t)(1u - record.running_slot);
    record.bootloader_version_known = shared.bootloader_version_present;
    if (shared.bootloader_version_present) {
        record.bootloader_version = shared.bootloader_version;
    }

    for (crux_image_slot_t slot = 0; slot < CRUX_IMAGE_SLOT_COUNT; slot++) {
        crux_image_port_slot_view_t view = {0};
        crux_image_slot_state_t state = CRUX_IMAGE_SLOT_INVALID;
        crux_image_result_t result = crux_image_port_slot_read(slot, &view);
        if (result != CRUX_IMAGE_OK) {
            return result;
        }
        result = crux_image_slot_state_derive(slot == record.running_slot, &view, &state);
        if (result != CRUX_IMAGE_OK) {
            return result; /* the running slot is not in a state that this contract supports */
        }
        record.slot_state_at_start[slot] = state;
        if (slot == record.running_slot) {
            record.running_version = view.version;
            record.running_confirmed = state == CRUX_IMAGE_SLOT_RUNNING_CONFIRMED;
        }
    }

    cached = record;
    atomic_store_explicit(&started, true, memory_order_release);
    return CRUX_IMAGE_OK;
}

crux_image_result_t crux_image_start(void)
{
    if (!lock_take()) {
        return CRUX_IMAGE_ERR_BUSY;
    }
    crux_image_result_t result = start_locked();
    lock_give();
    return result;
}

crux_image_result_t crux_image_boot_record_get(crux_image_boot_record_t *record)
{
    if (record == NULL) {
        return CRUX_IMAGE_ERR_INVALID_ARGUMENT;
    }
    if (!is_started()) {
        return CRUX_IMAGE_ERR_NOT_READY;
    }
    *record = cached;
    return CRUX_IMAGE_OK;
}

crux_image_result_t crux_image_slot_get(crux_image_slot_t slot, crux_image_slot_info_t *info)
{
    if (info == NULL || !slot_valid(slot)) {
        return CRUX_IMAGE_ERR_INVALID_ARGUMENT;
    }
    if (!is_started()) {
        return CRUX_IMAGE_ERR_NOT_READY;
    }
    crux_image_port_slot_view_t view = {0};
    crux_image_slot_state_t state = CRUX_IMAGE_SLOT_INVALID;
    crux_image_result_t result = read_state(slot, &view, &state);
    if (result == CRUX_IMAGE_ERR_BOOT_STATE) {
        /* A live trailer that is no longer one this contract supports is reported, not hidden. */
        result = CRUX_IMAGE_OK;
    }
    if (result != CRUX_IMAGE_OK) {
        return result;
    }
    info->state = state;
    info->version = view.version;
    return CRUX_IMAGE_OK;
}

/* The checks of crux_image_request_test(), in the order of the contract. */
static crux_image_result_t request_checks(crux_image_slot_t slot, crux_image_slot_state_t *state)
{
    if (!slot_valid(slot)) {
        return CRUX_IMAGE_ERR_INVALID_ARGUMENT;
    }
    if (slot == cached.running_slot) {
        return CRUX_IMAGE_ERR_ACTIVE_SLOT;
    }

    crux_image_port_slot_view_t running_view = {0};
    crux_image_slot_state_t running_state = CRUX_IMAGE_SLOT_INVALID;
    crux_image_result_t result = read_state(cached.running_slot, &running_view, &running_state);
    if (result != CRUX_IMAGE_OK) {
        return result;
    }
    if (running_state != CRUX_IMAGE_SLOT_RUNNING_CONFIRMED) {
        return CRUX_IMAGE_ERR_NOT_CONFIRMED;
    }

    crux_image_port_slot_view_t view = {0};
    result = read_state(slot, &view, state);
    if (result != CRUX_IMAGE_OK) {
        return result;
    }
    if (!view.header_valid) {
        return CRUX_IMAGE_ERR_NO_IMAGE;
    }
    /* The running image's version comes from its own header on the medium, not from the cache. */
    if (crux_image_version_compare(&view.version, &running_view.version) <= 0) {
        return CRUX_IMAGE_ERR_NOT_NEWER;
    }
    if (*state != CRUX_IMAGE_SLOT_STAGED && *state != CRUX_IMAGE_SLOT_PENDING_TEST) {
        return CRUX_IMAGE_ERR_SLOT_STATE;
    }
    return CRUX_IMAGE_OK;
}

crux_image_result_t crux_image_request_test(crux_image_slot_t slot)
{
    if (!is_started()) {
        return CRUX_IMAGE_ERR_NOT_READY;
    }
    if (!lock_take()) {
        return CRUX_IMAGE_ERR_BUSY;
    }

    crux_image_slot_state_t state = CRUX_IMAGE_SLOT_EMPTY;
    crux_image_result_t result = request_checks(slot, &state);
    if (result == CRUX_IMAGE_OK && state == CRUX_IMAGE_SLOT_STAGED) {
        /* The stock order: the magic, then the swap information. Never the confirm flag. */
        result = crux_image_port_write_magic(slot);
        if (result == CRUX_IMAGE_OK) {
            result = crux_image_port_write_swap_info_test(slot);
        }
    }
    /* A repeat for a PENDING_TEST slot returns OK without writing. */
    lock_give();
    return result;
}

crux_image_result_t crux_image_confirm(void)
{
    if (!is_started()) {
        return CRUX_IMAGE_ERR_NOT_READY;
    }
    if (!lock_take()) {
        return CRUX_IMAGE_ERR_BUSY;
    }

    crux_image_port_slot_view_t view = {0};
    crux_image_slot_state_t state = CRUX_IMAGE_SLOT_INVALID;
    crux_image_result_t result = read_state(cached.running_slot, &view, &state);
    if (result == CRUX_IMAGE_OK && state == CRUX_IMAGE_SLOT_RUNNING_TESTING) {
        /* The running slot only: confirm never names a slot. */
        result = crux_image_port_write_image_ok(cached.running_slot);
    }
    /* Already confirmed: OK without a write. Any other live state is the BOOT_STATE of read. */
    lock_give();
    return result;
}
