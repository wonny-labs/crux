/*
 * The Host test composition of the update agent. See medium.h. The fake digest is not SHA-256 and
 * the fake signature is not ECDSA: they stand in for the verify port, so that the agent's order and
 * gates can be tested. The verify provider over PSA Crypto is separate work.
 */
#include "medium.h"

#include "image_state_host.h"
#include "update_agent_port.h"

#include <string.h>

#define LOG_CAPACITY 512u
#define FAKE_SIGNATURE_SIZE 64u
#define ERASED 0xFFu

const crux_update_config_t medium_config = {MEDIUM_HEADER_SIZE, MEDIUM_LOAD_ADDRESS};

typedef enum { OP_FULL = 0, OP_TORN = 1, OP_NONE = 2 } op_effect_t;

static uint8_t bytes[CRUX_IMAGE_SLOT_COUNT][MEDIUM_SLOT_SIZE];
static uint32_t write_block = 1;
static size_t op_count;
static medium_op_t op_log[LOG_CAPACITY];
static size_t cut_n;
static medium_cut_t cut_mode;
static bool power_lost;
static size_t slot_writes[CRUX_IMAGE_SLOT_COUNT];

static bool record_present;
static crux_image_attempt_t record_value;
static bool record_unreadable;
static bool record_store_fails;
static bool record_clear_fails;

static bool slot_erase_fails;
static size_t slot_erases_before_failure;

static size_t progress_calls;
static void (*progress_hook)(crux_update_state_t, uint32_t, uint32_t);

/* ---- fake digest: four FNV-1a lanes, streaming ---- */

typedef struct {
    uint64_t lane[4];
} fake_hash_t;

static fake_hash_t hash_contexts[2];

static void fake_hash_init(fake_hash_t *h)
{
    for (unsigned i = 0; i < 4u; i++) {
        h->lane[i] = 0xcbf29ce484222325ull ^ (0x9e3779b97f4a7c15ull * (i + 1u));
    }
}

static void fake_hash_update(fake_hash_t *h, const uint8_t *data, size_t length)
{
    for (size_t at = 0; at < length; at++) {
        for (unsigned i = 0; i < 4u; i++) {
            h->lane[i] ^= data[at];
            h->lane[i] *= 0x100000001b3ull + 2u * i;
        }
    }
}

static void fake_hash_final(const fake_hash_t *h, uint8_t out[CRUX_UPDATE_DIGEST_SIZE])
{
    for (unsigned i = 0; i < 4u; i++) {
        for (unsigned b = 0; b < 8u; b++) {
            out[i * 8u + b] = (uint8_t)(h->lane[i] >> (8u * b));
        }
    }
}

static void fake_signature(const uint8_t digest[CRUX_UPDATE_DIGEST_SIZE], uint8_t *out)
{
    for (unsigned i = 0; i < CRUX_UPDATE_DIGEST_SIZE; i++) {
        out[i] = digest[i];
        out[CRUX_UPDATE_DIGEST_SIZE + i] = (uint8_t)~digest[i];
    }
}

/* ---- the medium ---- */

static uint32_t read_u32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static void put_u16(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
}

static void put_u32(uint8_t *p, uint32_t v)
{
    put_u16(p, v);
    put_u16(p + 2, v >> 16);
}

/* The double's header view follows the bytes: valid while the header magic is whole. */
static void sync_header(crux_image_slot_t slot)
{
    crux_image_port_slot_view_t view = image_state_host_slot_peek(slot);
    view.header_valid = read_u32(bytes[slot]) == 0x96f3b83du;
    if (view.header_valid) {
        view.version.major = bytes[slot][20];
        view.version.minor = bytes[slot][21];
        view.version.revision = (uint16_t)(bytes[slot][22] | (bytes[slot][23] << 8));
        view.version.build = read_u32(&bytes[slot][24]);
    } else {
        view.version = (crux_image_version_t){0, 0, 0, 0};
    }
    image_state_host_slot_put(slot, &view);
}

static void clear_trailer(crux_image_slot_t slot)
{
    crux_image_port_slot_view_t view = image_state_host_slot_peek(slot);
    view.magic = CRUX_IMAGE_PORT_MAGIC_UNSET;
    view.image_ok = CRUX_IMAGE_PORT_FLAG_UNSET;
    view.copy_done = CRUX_IMAGE_PORT_FLAG_UNSET;
    image_state_host_slot_put(slot, &view);
}

static bool trailer_sector(uint32_t sector)
{
    uint32_t start = sector * MEDIUM_SECTOR_SIZE;
    return start + MEDIUM_SECTOR_SIZE > MEDIUM_SLOT_SIZE - MEDIUM_TRAILER_SIZE;
}

static op_effect_t op_begin(medium_op_kind_t kind, crux_image_slot_t slot, uint32_t offset,
                            uint32_t length)
{
    if (power_lost) {
        return OP_NONE;
    }
    if (op_count < LOG_CAPACITY) {
        op_log[op_count] = (medium_op_t){kind, slot, offset, length};
    }
    op_count++;
    if (cut_n != 0 && op_count == cut_n) {
        power_lost = true;
        if (cut_mode == MEDIUM_CUT_TORN) {
            return OP_TORN;
        }
        return cut_mode == MEDIUM_CUT_LANDS ? OP_FULL : OP_NONE;
    }
    return OP_FULL;
}

static bool running_slot(crux_image_slot_t *running)
{
    crux_image_boot_record_t record;
    if (crux_image_boot_record_get(&record) != CRUX_IMAGE_OK) {
        return false;
    }
    *running = record.running_slot;
    return true;
}

/* Every write of the image state contract is a medium operation too. */
static void contract_write_hook(void)
{
    op_effect_t effect = op_begin(MEDIUM_OP_CONTRACT_WRITE, 0, 0, 0);
    if (effect == OP_FULL) {
        return;
    }
    if (effect == OP_TORN) {
        crux_image_slot_t running = 0;
        if (running_slot(&running)) {
            crux_image_slot_t other = (crux_image_slot_t)(1u - running);
            crux_image_port_slot_view_t run = image_state_host_slot_peek(running);
            crux_image_port_slot_view_t view = image_state_host_slot_peek(other);
            if (run.image_ok != CRUX_IMAGE_PORT_FLAG_SET) {
                run.image_ok = CRUX_IMAGE_PORT_FLAG_INVALID; /* a torn confirm flag */
                image_state_host_slot_put(running, &run);
            } else if (view.magic == CRUX_IMAGE_PORT_MAGIC_UNSET) {
                view.magic = CRUX_IMAGE_PORT_MAGIC_BAD; /* a torn request magic */
                image_state_host_slot_put(other, &view);
            }
        }
    }
    image_state_host_fail_nth_write(1); /* this write does not land */
}

void medium_init(void)
{
    image_state_host_init();
    image_state_host_set_write_hook(contract_write_hook);
    memset(bytes, ERASED, sizeof(bytes));
    write_block = 1;
    op_count = 0;
    cut_n = 0;
    power_lost = false;
    memset(slot_writes, 0, sizeof(slot_writes));
    record_present = false;
    record_unreadable = false;
    record_store_fails = false;
    record_clear_fails = false;
    slot_erase_fails = false;
    slot_erases_before_failure = 0;
    progress_calls = 0;
    progress_hook = NULL;

    static uint8_t image[MEDIUM_IMAGE_MAX];
    medium_image_spec_t spec = medium_image_default(1, 0, 0);
    size_t size = medium_image_build(&spec, image, sizeof(image));
    medium_slot_load(0, image, size, true);
    crux_update_core_reset();
}

void medium_set_write_block(uint32_t block)
{
    write_block = block;
}

void medium_cut_at(size_t n, medium_cut_t mode)
{
    cut_n = n == 0 ? 0 : op_count + n;
    cut_mode = mode;
}

bool medium_power_lost(void)
{
    return power_lost;
}

size_t medium_op_count(void)
{
    return op_count;
}

medium_op_t medium_op(size_t index)
{
    return op_log[index];
}

size_t medium_op_find(medium_op_kind_t kind, uint32_t offset)
{
    for (size_t i = 0; i < op_count && i < LOG_CAPACITY; i++) {
        if (op_log[i].kind == kind && (offset == UINT32_MAX || op_log[i].offset == offset)) {
            return i + 1u;
        }
    }
    return 0;
}

void medium_reboot(void)
{
    crux_image_port_slot_view_t before[CRUX_IMAGE_SLOT_COUNT];
    power_lost = false;
    cut_n = 0;
    op_count = 0;
    record_store_fails = false;
    record_clear_fails = false;
    slot_erase_fails = false;
    slot_erases_before_failure = 0;
    image_state_host_fail_nth_write(0);
    for (crux_image_slot_t s = 0; s < CRUX_IMAGE_SLOT_COUNT; s++) {
        before[s] = image_state_host_slot_peek(s);
    }
    image_state_host_boot();
    for (crux_image_slot_t s = 0; s < CRUX_IMAGE_SLOT_COUNT; s++) {
        crux_image_port_slot_view_t after = image_state_host_slot_peek(s);
        if (before[s].header_valid && !after.header_valid) {
            memset(bytes[s], ERASED, sizeof(bytes[s])); /* the model erased the whole slot */
        }
    }
    crux_image_core_reset();
    crux_update_core_reset();
}

void medium_slot_load(crux_image_slot_t slot, const uint8_t *image, size_t size, bool confirmed)
{
    memset(bytes[slot], ERASED, sizeof(bytes[slot]));
    memcpy(bytes[slot], image, size);
    clear_trailer(slot);
    sync_header(slot);
    crux_image_port_slot_view_t view = image_state_host_slot_peek(slot);
    if (confirmed) {
        view.magic = CRUX_IMAGE_PORT_MAGIC_GOOD;
        view.image_ok = CRUX_IMAGE_PORT_FLAG_SET;
        view.copy_done = CRUX_IMAGE_PORT_FLAG_SET;
    }
    image_state_host_slot_put(slot, &view);
}

const uint8_t *medium_slot_bytes(crux_image_slot_t slot)
{
    return bytes[slot];
}

static bool trailer_blank(crux_image_slot_t slot)
{
    crux_image_port_slot_view_t view = image_state_host_slot_peek(slot);
    return view.magic == CRUX_IMAGE_PORT_MAGIC_UNSET &&
           view.image_ok == CRUX_IMAGE_PORT_FLAG_UNSET &&
           view.copy_done == CRUX_IMAGE_PORT_FLAG_UNSET;
}

static bool range_blank(crux_image_slot_t slot, uint32_t offset, uint32_t length)
{
    for (uint32_t i = 0; i < length; i++) {
        if (bytes[slot][offset + i] != ERASED) {
            return false;
        }
    }
    return true;
}

bool medium_slot_blank(crux_image_slot_t slot)
{
    return range_blank(slot, 0, MEDIUM_SLOT_SIZE) && trailer_blank(slot);
}

crux_image_slot_state_t medium_slot_state(crux_image_slot_t slot)
{
    crux_image_slot_info_t info;
    if (crux_image_slot_get(slot, &info) != CRUX_IMAGE_OK) {
        return CRUX_IMAGE_SLOT_INVALID;
    }
    return info.state;
}

static void erase_sector_bytes(crux_image_slot_t slot, uint32_t sector, uint32_t length)
{
    memset(&bytes[slot][sector * MEDIUM_SECTOR_SIZE], ERASED, length);
    if (trailer_sector(sector) && length == MEDIUM_SECTOR_SIZE) {
        clear_trailer(slot);
    }
    sync_header(slot);
}

void medium_slot_erase_sector(crux_image_slot_t slot, uint32_t sector)
{
    erase_sector_bytes(slot, sector, MEDIUM_SECTOR_SIZE);
}

size_t medium_slot_write_count(crux_image_slot_t slot)
{
    return slot_writes[slot];
}

bool medium_record_get(crux_image_attempt_t *attempt)
{
    if (record_present && attempt != NULL) {
        *attempt = record_value;
    }
    return record_present;
}

void medium_record_set(const crux_image_attempt_t *attempt)
{
    record_present = attempt != NULL;
    if (attempt != NULL) {
        record_value = *attempt;
    }
}

void medium_record_set_unreadable(bool unreadable)
{
    record_unreadable = unreadable;
}

void medium_record_fail_next_store(bool fails)
{
    record_store_fails = fails;
}

void medium_record_fail_next_clear(bool fails)
{
    record_clear_fails = fails;
}

void medium_fail_next_slot_erase(bool fails)
{
    slot_erase_fails = fails;
}

void medium_fail_slot_erase_after(size_t erases)
{
    slot_erases_before_failure = erases + 1u;
}

size_t medium_progress_count(void)
{
    return progress_calls;
}

void medium_set_progress_hook(void (*hook)(crux_update_state_t, uint32_t, uint32_t))
{
    progress_hook = hook;
}

/* ---- ports ---- */

static bool staging_slot(crux_image_slot_t slot)
{
    crux_image_slot_t running = 0;
    return slot < CRUX_IMAGE_SLOT_COUNT && running_slot(&running) && slot != running;
}

bool crux_update_port_slot_geometry(crux_image_slot_t slot, crux_update_port_slot_geometry_t *geo)
{
    if (!staging_slot(slot)) {
        return false;
    }
    *geo = (crux_update_port_slot_geometry_t){MEDIUM_SLOT_SIZE, MEDIUM_SECTOR_SIZE,
                                              MEDIUM_TRAILER_SIZE, write_block, ERASED};
    return true;
}

bool crux_update_port_slot_erase(crux_image_slot_t slot, uint32_t sector)
{
    if (!staging_slot(slot) || sector >= MEDIUM_SECTOR_COUNT) {
        return false;
    }
    slot_writes[slot]++;
    if (slot_erase_fails) {
        slot_erase_fails = false;
        return false;
    }
    if (slot_erases_before_failure != 0) {
        slot_erases_before_failure--;
        if (slot_erases_before_failure == 0) {
            return false;
        }
    }
    op_effect_t effect = op_begin(MEDIUM_OP_SLOT_ERASE, slot, sector, MEDIUM_SECTOR_SIZE);
    if (effect == OP_FULL) {
        erase_sector_bytes(slot, sector, MEDIUM_SECTOR_SIZE);
        return true;
    }
    if (effect == OP_TORN) {
        erase_sector_bytes(slot, sector, MEDIUM_SECTOR_SIZE / 2u);
    }
    return false;
}

bool crux_update_port_slot_sector_blank(crux_image_slot_t slot, uint32_t sector, bool *blank)
{
    if (slot >= CRUX_IMAGE_SLOT_COUNT || sector >= MEDIUM_SECTOR_COUNT) {
        return false;
    }
    *blank = range_blank(slot, sector * MEDIUM_SECTOR_SIZE, MEDIUM_SECTOR_SIZE) &&
             (!trailer_sector(sector) || trailer_blank(slot));
    return true;
}

/* A NOR write programs erased bytes only, at aligned offsets, outside the trailer. */
bool crux_update_port_slot_write(crux_image_slot_t slot, uint32_t offset, const void *data,
                                 uint32_t length)
{
    if (!staging_slot(slot) || offset % write_block != 0 || length % write_block != 0 ||
        offset + length > MEDIUM_SLOT_SIZE - MEDIUM_TRAILER_SIZE ||
        !range_blank(slot, offset, length)) {
        return false;
    }
    slot_writes[slot]++;
    op_effect_t effect = op_begin(MEDIUM_OP_SLOT_WRITE, slot, offset, length);
    if (effect == OP_NONE) {
        return false;
    }
    uint32_t landed = effect == OP_FULL ? length : (length / 2u) / write_block * write_block;
    memcpy(&bytes[slot][offset], data, landed);
    sync_header(slot);
    return effect == OP_FULL;
}

bool crux_update_port_slot_read(crux_image_slot_t slot, uint32_t offset, void *data,
                                uint32_t length)
{
    if (slot >= CRUX_IMAGE_SLOT_COUNT || offset + length > MEDIUM_SLOT_SIZE) {
        return false;
    }
    memcpy(data, &bytes[slot][offset], length);
    return true;
}

bool crux_update_port_record_load(bool *present, crux_image_attempt_t *attempt)
{
    if (record_unreadable) {
        return false;
    }
    *present = record_present;
    if (record_present) {
        *attempt = record_value;
    }
    return true;
}

/* The store contract of row U2: a torn or lost store leaves the previous record. */
bool crux_update_port_record_store(const crux_image_attempt_t *attempt)
{
    if (record_store_fails) {
        record_store_fails = false;
        return false;
    }
    if (op_begin(MEDIUM_OP_RECORD_STORE, 0, 0, 0) != OP_FULL) {
        return false;
    }
    record_present = true;
    record_value = *attempt;
    record_unreadable = false;
    return true;
}

bool crux_update_port_record_clear(void)
{
    if (record_clear_fails) {
        record_clear_fails = false;
        return false;
    }
    if (op_begin(MEDIUM_OP_RECORD_CLEAR, 0, 0, 0) != OP_FULL) {
        return false;
    }
    record_present = false;
    return true;
}

bool crux_update_port_hash_begin(crux_update_hash_context_t context)
{
    fake_hash_init(&hash_contexts[context]);
    return true;
}

bool crux_update_port_hash_update(crux_update_hash_context_t context, const void *data,
                                  size_t length)
{
    fake_hash_update(&hash_contexts[context], data, length);
    return true;
}

bool crux_update_port_hash_finish(crux_update_hash_context_t context,
                                  uint8_t digest[CRUX_UPDATE_DIGEST_SIZE])
{
    fake_hash_final(&hash_contexts[context], digest);
    return true;
}

bool crux_update_port_signature_verify(const uint8_t digest[CRUX_UPDATE_DIGEST_SIZE],
                                       const uint8_t *signature, size_t signature_length)
{
    uint8_t expected[FAKE_SIGNATURE_SIZE];
    fake_signature(digest, expected);
    return signature_length == FAKE_SIGNATURE_SIZE &&
           memcmp(signature, expected, FAKE_SIGNATURE_SIZE) == 0;
}

void crux_update_port_progress(crux_update_state_t phase, uint32_t done, uint32_t total)
{
    progress_calls++;
    if (progress_hook != NULL) {
        progress_hook(phase, done, total);
    }
}

/* ---- image builder ---- */

medium_image_spec_t medium_image_default(uint8_t major, uint8_t minor, uint16_t revision)
{
    return (medium_image_spec_t){{major, minor, revision, 7},
                                 3000,
                                 0x00000020u,
                                 MEDIUM_LOAD_ADDRESS,
                                 MEDIUM_HEADER_SIZE,
                                 true,
                                 true,
                                 true};
}

static size_t put_tlv(uint8_t *out, uint16_t type, const uint8_t *value, uint16_t length)
{
    put_u16(out, type);
    put_u16(out + 2, length);
    memcpy(out + 4, value, length);
    return 4u + length;
}

size_t medium_image_build(const medium_image_spec_t *spec, uint8_t *out, size_t capacity)
{
    const uint16_t protected_size = spec->protected_area ? 12u : 0u;
    memset(out, 0, capacity);
    put_u32(&out[0], 0x96f3b83du);
    put_u32(&out[4], spec->load_address);
    put_u16(&out[8], spec->header_size);
    put_u16(&out[10], protected_size);
    put_u32(&out[12], spec->body_size);
    put_u32(&out[16], spec->flags);
    out[20] = spec->version.major;
    out[21] = spec->version.minor;
    put_u16(&out[22], spec->version.revision);
    put_u32(&out[24], spec->version.build);

    size_t at = spec->header_size;
    for (uint32_t i = 0; i < spec->body_size; i++) {
        out[at + i] = (uint8_t)(i * 7u + spec->version.minor + spec->version.revision);
    }
    at += spec->body_size;
    if (spec->protected_area) {
        static const uint8_t counter[4] = {1, 0, 0, 0};
        put_u16(&out[at], 0x6908u);
        put_u16(&out[at + 2], protected_size);
        at += 4u;
        at += put_tlv(&out[at], 0x50u, counter, sizeof(counter));
    }

    uint8_t digest[CRUX_UPDATE_DIGEST_SIZE];
    fake_hash_t h;
    fake_hash_init(&h);
    fake_hash_update(&h, out, at);
    fake_hash_final(&h, digest);

    size_t info = at;
    at += 4u;
    static const uint8_t key_hash[CRUX_UPDATE_DIGEST_SIZE] = {0x4b};
    at += put_tlv(&out[at], 0x01u, key_hash, sizeof(key_hash));
    if (spec->sha256) {
        at += put_tlv(&out[at], 0x10u, digest, sizeof(digest));
    }
    if (spec->signature) {
        uint8_t signature[FAKE_SIGNATURE_SIZE];
        fake_signature(digest, signature);
        at += put_tlv(&out[at], 0x22u, signature, sizeof(signature));
    }
    put_u16(&out[info], 0x6907u);
    put_u16(&out[info + 2], (uint32_t)(at - info));
    return at;
}

size_t medium_image_tlv_value_offset(const uint8_t *image, size_t size, uint16_t type)
{
    uint32_t header = image[8] | (image[9] << 8);
    uint32_t protected_size = image[10] | (image[11] << 8);
    size_t at = header + read_u32(&image[12]) + protected_size + 4u;
    while (at + 4u <= size) {
        uint16_t t = (uint16_t)(image[at] | (image[at + 1] << 8));
        uint16_t l = (uint16_t)(image[at + 2] | (image[at + 3] << 8));
        if (t == type) {
            return at + 4u;
        }
        at += 4u + l;
    }
    return 0;
}

/* ---- source ---- */

static bool source_read(void *context, size_t offset, void *buffer, size_t length)
{
    medium_source_t *s = context;
    s->reads++;
    if (s->fail_reads || offset > s->size || length > s->size - offset) {
        return false;
    }
    memcpy(buffer, &s->data[offset], length);
    if (s->mutate && s->reached_end && s->mutate_offset >= offset &&
        s->mutate_offset < offset + length) {
        uint8_t *out = buffer;
        out[s->mutate_offset - offset] = (uint8_t)~out[s->mutate_offset - offset];
    }
    if (offset + length == s->size) {
        s->reached_end = true;
    }
    return true;
}

crux_update_source_t medium_source(medium_source_t *state, const uint8_t *data, size_t size)
{
    *state = (medium_source_t){data, size, false, 0, false, false, 0};
    return (crux_update_source_t){size, source_read, state};
}
