/*
 * The update agent's core: the transition table of row U1 (TR1 to TR19), the checks of TR6 (gates
 * G1 to G7 and the version policy of U3), and the staging path of U4. See crux/update_agent.h.
 *
 * Locking. One try-lock serialises start, begin, confirm and acknowledge: a caller that finds it
 * taken gets CRUX_UPDATE_ERR_BUSY at once, a bounded wait of zero, so that a higher-priority thread
 * never spins on a preempted holder. The state is written only under that lock, so there is one
 * writer at a time. The status snapshot is published with a sequence counter (a seqlock) whose
 * fields are atomics: the reader never blocks the writer, and it retries a few times before it
 * reports CRUX_UPDATE_ERR_BUSY. Cancel is an atomic flag that the writer polls between two sector
 * operations.
 */
#include "update_agent_image.h"
#include "update_agent_port.h"

#include <stdatomic.h>
#include <string.h>

#define CHUNK_SIZE 256u    /* bytes per source read and slot write; a multiple of write_block */
#define TLV_AREA_MAX 1024u /* the unprotected metadata area, information header included */
#define SNAPSHOT_TRIES 8u
#define HEADER_MAGIC_SIZE 4u

typedef struct {
    crux_image_slot_t slot;
    crux_update_port_slot_geometry_t geo;
    update_image_header_t header;
    uint32_t tlv_start; /* end of the range the SHA-256 entry covers */
    uint16_t tlv_total;
    uint32_t total; /* the whole image: header, body, both metadata areas */
    uint8_t image_digest[CRUX_UPDATE_DIGEST_SIZE];
    uint8_t copy_digest[CRUX_UPDATE_DIGEST_SIZE];
} attempt_t;

typedef struct {
    crux_update_state_t state;
    crux_update_result_t last_result;
    crux_image_outcome_t outcome;
    bool attempt_present;
    crux_image_attempt_t attempt;
    bool record_lost;
    bool slot_staged;
    uint32_t progress_done;
    uint32_t progress_total;
    bool start_ran;
    crux_update_result_t start_result;
    crux_update_config_t config;
    crux_image_boot_record_t boot;
} agent_t;

static agent_t agent;
static attempt_t current;
static uint8_t chunk[CHUNK_SIZE];
static uint8_t tlv_area[TLV_AREA_MAX];

static atomic_flag lock = ATOMIC_FLAG_INIT;
static atomic_bool in_attempt;
static atomic_bool cancel_requested;

/* The snapshot: one writer (the lock holder), any number of readers. */
#define FLAG_ATTEMPT_PRESENT 1u
#define FLAG_REQUESTED 2u
#define FLAG_RECORD_LOST 4u
#define FLAG_SLOT_STAGED 8u

static atomic_uint snap_seq;
static atomic_int snap_state;
static atomic_int snap_result;
static atomic_int snap_outcome;
static atomic_uint snap_flags;
static atomic_uint snap_slot;
static atomic_uint snap_version; /* major | minor << 8 | revision << 16 */
static atomic_uint snap_build;
static atomic_uint snap_done;
static atomic_uint snap_total;

static void publish(void)
{
    unsigned seq = atomic_load_explicit(&snap_seq, memory_order_relaxed);
    atomic_store_explicit(&snap_seq, seq + 1u, memory_order_relaxed);
    atomic_thread_fence(memory_order_release);

    unsigned flags = (agent.attempt_present ? FLAG_ATTEMPT_PRESENT : 0u) |
                     (agent.attempt.requested ? FLAG_REQUESTED : 0u) |
                     (agent.record_lost ? FLAG_RECORD_LOST : 0u) |
                     (agent.slot_staged ? FLAG_SLOT_STAGED : 0u);
    unsigned version = (unsigned)agent.attempt.version.major |
                       ((unsigned)agent.attempt.version.minor << 8) |
                       ((unsigned)agent.attempt.version.revision << 16);
    atomic_store_explicit(&snap_state, (int)agent.state, memory_order_relaxed);
    atomic_store_explicit(&snap_result, (int)agent.last_result, memory_order_relaxed);
    atomic_store_explicit(&snap_outcome, (int)agent.outcome, memory_order_relaxed);
    atomic_store_explicit(&snap_flags, flags, memory_order_relaxed);
    atomic_store_explicit(&snap_slot, agent.attempt.slot, memory_order_relaxed);
    atomic_store_explicit(&snap_version, version, memory_order_relaxed);
    atomic_store_explicit(&snap_build, agent.attempt.version.build, memory_order_relaxed);
    atomic_store_explicit(&snap_done, agent.progress_done, memory_order_relaxed);
    atomic_store_explicit(&snap_total, agent.progress_total, memory_order_relaxed);

    atomic_store_explicit(&snap_seq, seq + 2u, memory_order_release);
}

static bool lock_take(void)
{
    return !atomic_flag_test_and_set_explicit(&lock, memory_order_acquire);
}

static void lock_give(void)
{
    atomic_flag_clear_explicit(&lock, memory_order_release);
}

static void set_state(crux_update_state_t state)
{
    agent.state = state;
    publish();
}

static crux_update_result_t fail(crux_update_result_t reason)
{
    agent.last_result = reason;
    set_state(CRUX_UPDATE_STATE_FAILED);
    return reason;
}

static bool cancelled(void)
{
    return atomic_load_explicit(&cancel_requested, memory_order_acquire);
}

static void progress(crux_update_state_t phase, uint32_t done, uint32_t total)
{
    agent.progress_done = done;
    agent.progress_total = total;
    publish();
    crux_update_port_progress(phase, done, total);
}

static uint64_t align_up(uint64_t value, uint32_t alignment)
{
    return (value + alignment - 1u) / alignment * alignment;
}

static uint32_t min_u32(uint32_t a, uint32_t b)
{
    return a < b ? a : b;
}

static bool versions_equal(const crux_image_version_t *a, const crux_image_version_t *b)
{
    return a->major == b->major && a->minor == b->minor && a->revision == b->revision &&
           a->build == b->build;
}

void crux_update_core_reset(void)
{
    while (!lock_take()) {
    }
    memset(&agent, 0, sizeof(agent));
    agent.state = CRUX_UPDATE_STATE_NOT_STARTED;
    atomic_store(&in_attempt, false);
    atomic_store(&cancel_requested, false);
    publish();
    lock_give();
}

/* ---- start: TR1 to TR5 ---- */

static void start_locked(const crux_update_config_t *config)
{
    agent.start_ran = true;
    agent.config = *config;
    if (crux_image_start() != CRUX_IMAGE_OK ||
        crux_image_boot_record_get(&agent.boot) != CRUX_IMAGE_OK) {
        agent.start_result = CRUX_UPDATE_ERR_NOT_READY; /* TR1: fail closed */
        agent.last_result = CRUX_UPDATE_ERR_NOT_READY;
        set_state(CRUX_UPDATE_STATE_UNAVAILABLE);
        return;
    }

    bool present = false;
    crux_image_attempt_t attempt = {0};
    if (!crux_update_port_record_load(&present, &attempt)) {
        agent.record_lost = true; /* TR5: treated as no record */
        present = false;
    }
    agent.attempt_present = present;
    if (present) {
        agent.attempt = attempt;
    }
    agent.outcome =
        present ? crux_image_outcome(&agent.boot, &agent.attempt) : CRUX_IMAGE_OUTCOME_NONE;

    crux_update_state_t state = CRUX_UPDATE_STATE_IDLE; /* TR4 */
    if (!agent.boot.running_confirmed) {
        state = CRUX_UPDATE_STATE_TESTING; /* TR2 */
    } else if (agent.outcome == CRUX_IMAGE_OUTCOME_CONFIRMED ||
               agent.outcome == CRUX_IMAGE_OUTCOME_REVERTED ||
               agent.outcome == CRUX_IMAGE_OUTCOME_NOT_BOOTED) {
        state = CRUX_UPDATE_STATE_OUTCOME; /* TR3 */
    }
    agent.start_result = CRUX_UPDATE_OK;
    set_state(state);
}

crux_update_result_t crux_update_start(const crux_update_config_t *config)
{
    if (config == NULL || config->header_size == 0) {
        return CRUX_UPDATE_ERR_INVALID_ARGUMENT;
    }
    if (!lock_take()) {
        return CRUX_UPDATE_ERR_BUSY;
    }
    if (!agent.start_ran) {
        start_locked(config);
    }
    crux_update_result_t result = agent.start_result;
    lock_give();
    return result;
}

/* ---- TR6: the checks, before any write ---- */

static bool geometry_ok(const crux_update_port_slot_geometry_t *geo)
{
    return geo->sector_size != 0 && geo->size != 0 && geo->size % geo->sector_size == 0 &&
           geo->trailer_size < geo->size && geo->write_block != 0 &&
           geo->write_block <= CHUNK_SIZE && CHUNK_SIZE % geo->write_block == 0 &&
           geo->sector_size % geo->write_block == 0;
}

/* G1, G2, G3 and G4 on the header and the two metadata information headers. */
static crux_update_result_t check_layout(const crux_update_source_t *source, attempt_t *a,
                                         uint8_t fields[UPDATE_IMAGE_HEADER_FIELDS_SIZE])
{
    if (source->size < UPDATE_IMAGE_HEADER_FIELDS_SIZE) {
        return CRUX_UPDATE_ERR_FORMAT;
    }
    if ((uint64_t)source->size > UINT32_MAX) {
        return CRUX_UPDATE_ERR_LENGTH;
    }
    if (!source->read(source->context, 0, fields, UPDATE_IMAGE_HEADER_FIELDS_SIZE)) {
        return CRUX_UPDATE_ERR_SOURCE;
    }
    const update_image_header_t *h = &a->header;
    update_image_header_read(fields, &a->header);
    if (h->magic != UPDATE_IMAGE_MAGIC || h->header_size != agent.config.header_size ||
        h->header_size < UPDATE_IMAGE_HEADER_FIELDS_SIZE ||
        h->header_size % a->geo.write_block != 0) {
        return CRUX_UPDATE_ERR_FORMAT; /* G1 */
    }
    if ((h->flags & UPDATE_IMAGE_FLAG_RAM_LOAD) == 0 ||
        h->load_address != agent.config.load_address) {
        return CRUX_UPDATE_ERR_LOAD_ADDRESS; /* G2 */
    }

    uint8_t info[UPDATE_IMAGE_TLV_INFO_SIZE];
    uint16_t magic = 0;
    uint16_t total = 0;
    uint64_t protected_start = (uint64_t)h->header_size + h->image_size;
    uint64_t tlv_start = protected_start + h->protect_tlv_size;
    if (h->protect_tlv_size != 0) {
        if (protected_start + UPDATE_IMAGE_TLV_INFO_SIZE > source->size) {
            return CRUX_UPDATE_ERR_LENGTH; /* G3 */
        }
        if (!source->read(source->context, (size_t)protected_start, info, sizeof(info))) {
            return CRUX_UPDATE_ERR_SOURCE;
        }
        update_image_tlv_info_read(info, &magic, &total);
        if (magic != UPDATE_IMAGE_TLV_PROT_INFO_MAGIC || total != h->protect_tlv_size) {
            return CRUX_UPDATE_ERR_FORMAT;
        }
    }
    if (tlv_start + UPDATE_IMAGE_TLV_INFO_SIZE > source->size) {
        return CRUX_UPDATE_ERR_LENGTH; /* G3 */
    }
    if (!source->read(source->context, (size_t)tlv_start, info, sizeof(info))) {
        return CRUX_UPDATE_ERR_SOURCE;
    }
    update_image_tlv_info_read(info, &magic, &total);
    if (magic != UPDATE_IMAGE_TLV_INFO_MAGIC || total < UPDATE_IMAGE_TLV_INFO_SIZE ||
        total > TLV_AREA_MAX) {
        return CRUX_UPDATE_ERR_FORMAT;
    }
    if (tlv_start + total != source->size) {
        return CRUX_UPDATE_ERR_LENGTH; /* G3: no extra bytes, none missing */
    }
    a->tlv_start = (uint32_t)tlv_start;
    a->tlv_total = total;
    a->total = (uint32_t)source->size;

    if (align_up(a->total, a->geo.write_block) > a->geo.size - a->geo.trailer_size) {
        return CRUX_UPDATE_ERR_TOO_LARGE; /* G4 */
    }
    return CRUX_UPDATE_OK;
}

/* One pass front to back: the two digests and a copy of the unprotected metadata area. */
static crux_update_result_t hash_pass(const crux_update_source_t *source, attempt_t *a,
                                      const uint8_t fields[UPDATE_IMAGE_HEADER_FIELDS_SIZE])
{
    if (!crux_update_port_hash_begin(CRUX_UPDATE_HASH_IMAGE) ||
        !crux_update_port_hash_begin(CRUX_UPDATE_HASH_COPY)) {
        return CRUX_UPDATE_ERR_HASH;
    }
    for (uint32_t offset = 0; offset < a->total;) {
        uint32_t n = min_u32(CHUNK_SIZE, a->total - offset);
        if (!source->read(source->context, offset, chunk, n)) {
            return CRUX_UPDATE_ERR_SOURCE;
        }
        if (offset == 0 && memcmp(chunk, fields, UPDATE_IMAGE_HEADER_FIELDS_SIZE) != 0) {
            return CRUX_UPDATE_ERR_SOURCE; /* the header changed while it was checked */
        }
        if (offset < a->tlv_start &&
            !crux_update_port_hash_update(CRUX_UPDATE_HASH_IMAGE, chunk,
                                          min_u32(n, a->tlv_start - offset))) {
            return CRUX_UPDATE_ERR_HASH;
        }
        if (!crux_update_port_hash_update(CRUX_UPDATE_HASH_COPY, chunk, n)) {
            return CRUX_UPDATE_ERR_HASH;
        }
        if (offset + n > a->tlv_start) {
            uint32_t from = offset < a->tlv_start ? a->tlv_start - offset : 0u;
            memcpy(&tlv_area[offset + from - a->tlv_start], &chunk[from], n - from);
        }
        offset += n;
        progress(CRUX_UPDATE_STATE_CHECKED, offset, a->total);
    }
    if (!crux_update_port_hash_finish(CRUX_UPDATE_HASH_IMAGE, a->image_digest) ||
        !crux_update_port_hash_finish(CRUX_UPDATE_HASH_COPY, a->copy_digest)) {
        return CRUX_UPDATE_ERR_HASH;
    }
    uint16_t magic = 0;
    uint16_t total = 0;
    update_image_tlv_info_read(tlv_area, &magic, &total);
    if (magic != UPDATE_IMAGE_TLV_INFO_MAGIC || total != a->tlv_total) {
        return CRUX_UPDATE_ERR_SOURCE; /* the metadata changed while it was checked */
    }
    return CRUX_UPDATE_OK;
}

/* G6 and G7 on the copied metadata area. */
static crux_update_result_t check_integrity(const attempt_t *a)
{
    const uint8_t *value = NULL;
    uint16_t length = 0;
    int found =
        update_image_tlv_find(tlv_area, a->tlv_total, UPDATE_IMAGE_TLV_SHA256, &value, &length);
    if (found < 0) {
        return CRUX_UPDATE_ERR_FORMAT;
    }
    if (found == 0 || length != CRUX_UPDATE_DIGEST_SIZE ||
        memcmp(value, a->image_digest, CRUX_UPDATE_DIGEST_SIZE) != 0) {
        return CRUX_UPDATE_ERR_HASH; /* G6 */
    }
    found =
        update_image_tlv_find(tlv_area, a->tlv_total, UPDATE_IMAGE_TLV_ECDSA_SIG, &value, &length);
    if (found < 0) {
        return CRUX_UPDATE_ERR_FORMAT;
    }
    if (found == 0 || !crux_update_port_signature_verify(a->image_digest, value, length)) {
        return CRUX_UPDATE_ERR_SIGNATURE; /* G7, required (W5) */
    }
    return CRUX_UPDATE_OK;
}

static crux_update_result_t check_source(const crux_update_source_t *source, attempt_t *a)
{
    uint8_t fields[UPDATE_IMAGE_HEADER_FIELDS_SIZE];
    memset(a, 0, sizeof(*a));
    a->slot = agent.boot.inactive_slot;
    if (!crux_update_port_slot_geometry(a->slot, &a->geo) || !geometry_ok(&a->geo)) {
        return CRUX_UPDATE_ERR_WRITE;
    }
    crux_update_result_t result = check_layout(source, a, fields);
    if (result != CRUX_UPDATE_OK) {
        return result;
    }
    /* G5 / VP1: strictly newer than the running image, read from its header at start. */
    if (crux_image_version_compare(&a->header.version, &agent.boot.running_version) <= 0) {
        return CRUX_UPDATE_ERR_NOT_NEWER;
    }
    result = hash_pass(source, a, fields);
    if (result != CRUX_UPDATE_OK) {
        return result;
    }
    return check_integrity(a);
}

/* ---- TR8 to TR17: staging ---- */

static uint32_t sector_count(const attempt_t *a)
{
    return a->geo.size / a->geo.sector_size;
}

/* TR9: erase every sector that is not blank, header sector first, then blank-check all. */
static crux_update_result_t erase_slot(const attempt_t *a)
{
    const uint32_t sectors = sector_count(a);
    for (uint32_t s = 0; s < sectors; s++) {
        if (cancelled()) {
            return CRUX_UPDATE_ERR_CANCELLED;
        }
        bool blank = false;
        if (!crux_update_port_slot_sector_blank(a->slot, s, &blank)) {
            return CRUX_UPDATE_ERR_ERASE;
        }
        if (!blank && !crux_update_port_slot_erase(a->slot, s)) {
            return CRUX_UPDATE_ERR_ERASE;
        }
        progress(CRUX_UPDATE_STATE_ERASED, (s + 1u) * a->geo.sector_size, a->geo.size);
    }
    for (uint32_t s = 0; s < sectors; s++) {
        bool blank = false;
        if (!crux_update_port_slot_sector_blank(a->slot, s, &blank) || !blank) {
            return CRUX_UPDATE_ERR_ERASE;
        }
    }
    return CRUX_UPDATE_OK;
}

/* Copies [from, to) from the source to the slot, padding the last write with the erased value. */
static crux_update_result_t write_range(const crux_update_source_t *source, const attempt_t *a,
                                        uint32_t from, uint32_t to, crux_update_state_t phase)
{
    for (uint32_t offset = from; offset < to;) {
        if (cancelled()) {
            return CRUX_UPDATE_ERR_CANCELLED;
        }
        uint32_t n = min_u32(CHUNK_SIZE, to - offset);
        if (!source->read(source->context, offset, chunk, n)) {
            return CRUX_UPDATE_ERR_SOURCE;
        }
        uint32_t padded = (uint32_t)align_up(n, a->geo.write_block);
        memset(&chunk[n], a->geo.erased_value, padded - n);
        if (!crux_update_port_slot_write(a->slot, offset, chunk, padded)) {
            return CRUX_UPDATE_ERR_WRITE;
        }
        offset += n;
        progress(phase, offset - from, to - from);
    }
    return CRUX_UPDATE_OK;
}

/*
 * TR11: the header, with the write block that holds its magic last, so that a cut leaves a header
 * whose magic is blank or torn and never a whole magic over a torn header.
 */
static crux_update_result_t write_header(const crux_update_source_t *source, const attempt_t *a,
                                         bool *magic_attempted)
{
    const uint32_t first = (uint32_t)align_up(HEADER_MAGIC_SIZE, a->geo.write_block);
    crux_update_result_t result =
        write_range(source, a, first, a->header.header_size, CRUX_UPDATE_STATE_STAGED);
    if (result != CRUX_UPDATE_OK) {
        return result;
    }
    if (!source->read(source->context, 0, chunk, first)) {
        return CRUX_UPDATE_ERR_SOURCE;
    }
    *magic_attempted = true;
    if (!crux_update_port_slot_write(a->slot, 0, chunk, first)) {
        return CRUX_UPDATE_ERR_WRITE;
    }
    return CRUX_UPDATE_OK;
}

/* TR12: the slot's bytes against the checked digest, the version again, and the slot's state. */
static crux_update_result_t read_back(attempt_t *a)
{
    if (!crux_update_port_hash_begin(CRUX_UPDATE_HASH_COPY)) {
        return CRUX_UPDATE_ERR_VERIFY;
    }
    for (uint32_t offset = 0; offset < a->total;) {
        if (cancelled()) {
            return CRUX_UPDATE_ERR_CANCELLED;
        }
        uint32_t n = min_u32(CHUNK_SIZE, a->total - offset);
        if (!crux_update_port_slot_read(a->slot, offset, chunk, n)) {
            return CRUX_UPDATE_ERR_VERIFY;
        }
        if (offset == 0) {
            update_image_header_t h;
            update_image_header_read(chunk, &h);
            if (h.magic != UPDATE_IMAGE_MAGIC || !versions_equal(&h.version, &a->header.version) ||
                crux_image_version_compare(&h.version, &agent.boot.running_version) <= 0) {
                return CRUX_UPDATE_ERR_VERIFY; /* VP2 */
            }
        }
        if (!crux_update_port_hash_update(CRUX_UPDATE_HASH_COPY, chunk, n)) {
            return CRUX_UPDATE_ERR_VERIFY;
        }
        offset += n;
        progress(CRUX_UPDATE_STATE_VERIFIED, offset, a->total);
    }
    uint8_t digest[CRUX_UPDATE_DIGEST_SIZE];
    if (!crux_update_port_hash_finish(CRUX_UPDATE_HASH_COPY, digest) ||
        memcmp(digest, a->copy_digest, sizeof(digest)) != 0) {
        return CRUX_UPDATE_ERR_VERIFY;
    }
    crux_image_slot_info_t info;
    if (crux_image_slot_get(a->slot, &info) != CRUX_IMAGE_OK ||
        info.state != CRUX_IMAGE_SLOT_STAGED ||
        crux_image_version_compare(&info.version, &a->header.version) != 0) {
        return CRUX_UPDATE_ERR_VERIFY;
    }
    return CRUX_UPDATE_OK;
}

/* TR16: erase the header sector and the trailer sectors, best effort. */
static void invalidate(const attempt_t *a)
{
    const uint32_t sectors = sector_count(a);
    const uint32_t first_trailer = (a->geo.size - a->geo.trailer_size) / a->geo.sector_size;
    bool header_erased = crux_update_port_slot_erase(a->slot, 0);
    for (uint32_t s = first_trailer; s < sectors; s++) {
        if (s != 0) {
            (void)crux_update_port_slot_erase(a->slot, s);
        }
    }
    agent.slot_staged = !header_erased; /* the bootloader erases it at the next reset */
}

static crux_update_result_t abandon(const attempt_t *a, crux_update_result_t reason)
{
    invalidate(a);
    return fail(reason);
}

/* TR17: a failure inside TR13. A slot that reads PENDING_TEST is requested after all. */
static crux_update_result_t request_failed(const attempt_t *a, crux_update_result_t reason)
{
    crux_image_slot_info_t info;
    if (crux_image_slot_get(a->slot, &info) == CRUX_IMAGE_OK &&
        info.state == CRUX_IMAGE_SLOT_PENDING_TEST) {
        agent.last_result = CRUX_UPDATE_OK;
        set_state(CRUX_UPDATE_STATE_WAITING_RESET);
        return CRUX_UPDATE_OK;
    }
    return abandon(a, reason);
}

static crux_update_result_t stage(const crux_update_source_t *source, attempt_t *a)
{
    if (cancelled()) { /* TR19 from CHECKED */
        agent.last_result = CRUX_UPDATE_ERR_CANCELLED;
        set_state(CRUX_UPDATE_STATE_IDLE);
        return CRUX_UPDATE_ERR_CANCELLED;
    }

    /* TR8: the record before the first change to the slot. */
    crux_image_attempt_t record = {a->slot, a->header.version, false};
    if (!crux_update_port_record_store(&record)) {
        return fail(CRUX_UPDATE_ERR_RECORD);
    }
    agent.attempt = record;
    agent.attempt_present = true;
    agent.outcome = CRUX_IMAGE_OUTCOME_NONE;
    set_state(CRUX_UPDATE_STATE_RECORDED);

    crux_update_result_t result = erase_slot(a); /* TR9 */
    if (result != CRUX_UPDATE_OK) {
        return fail(result);
    }
    set_state(CRUX_UPDATE_STATE_ERASED);

    result = write_range(source, a, a->header.header_size, a->total,
                         CRUX_UPDATE_STATE_BODY_WRITTEN); /* TR10 */
    if (result != CRUX_UPDATE_OK) {
        return fail(result);
    }
    set_state(CRUX_UPDATE_STATE_BODY_WRITTEN);

    bool magic_attempted = false;
    result = write_header(source, a, &magic_attempted); /* TR11 */
    if (result != CRUX_UPDATE_OK) {
        return magic_attempted ? abandon(a, result) : fail(result);
    }
    set_state(CRUX_UPDATE_STATE_STAGED);

    if (cancelled()) {
        return abandon(a, CRUX_UPDATE_ERR_CANCELLED); /* TR16 */
    }
    result = read_back(a); /* TR12 */
    if (result != CRUX_UPDATE_OK) {
        return abandon(a, result);
    }
    set_state(CRUX_UPDATE_STATE_VERIFIED);
    if (cancelled()) {
        return abandon(a, CRUX_UPDATE_ERR_CANCELLED);
    }

    /* TR13: `requested` is durable before the request writes. No cancel from here on. */
    record.requested = true;
    if (!crux_update_port_record_store(&record)) {
        return request_failed(a, CRUX_UPDATE_ERR_RECORD);
    }
    agent.attempt = record;
    publish();
    if (crux_image_request_test(a->slot) != CRUX_IMAGE_OK) {
        return request_failed(a, CRUX_UPDATE_ERR_REQUEST);
    }
    agent.last_result = CRUX_UPDATE_OK;
    set_state(CRUX_UPDATE_STATE_WAITING_RESET);
    return CRUX_UPDATE_OK;
}

static crux_update_result_t begin_locked(const crux_update_source_t *source)
{
    switch (agent.state) {
    case CRUX_UPDATE_STATE_NOT_STARTED:
    case CRUX_UPDATE_STATE_UNAVAILABLE:
        return CRUX_UPDATE_ERR_NOT_READY;
    case CRUX_UPDATE_STATE_TESTING:
        return CRUX_UPDATE_ERR_NOT_CONFIRMED; /* TR7, VP4 */
    case CRUX_UPDATE_STATE_IDLE:
    case CRUX_UPDATE_STATE_OUTCOME:
    case CRUX_UPDATE_STATE_FAILED:
        break;
    default:
        return CRUX_UPDATE_ERR_BUSY; /* TR7: requested, or inside an attempt */
    }

    atomic_store_explicit(&cancel_requested, false, memory_order_release);
    atomic_store_explicit(&in_attempt, true, memory_order_release);
    crux_update_result_t result = check_source(source, &current); /* TR6 */
    if (result != CRUX_UPDATE_OK) {
        agent.last_result = result; /* a refusal: nothing written, state unchanged */
        publish();
    } else {
        agent.slot_staged = false;
        agent.last_result = CRUX_UPDATE_OK;
        set_state(CRUX_UPDATE_STATE_CHECKED);
        result = stage(source, &current);
    }
    atomic_store_explicit(&in_attempt, false, memory_order_release);
    return result;
}

crux_update_result_t crux_update_begin(const crux_update_source_t *source)
{
    if (source == NULL || source->read == NULL) {
        return CRUX_UPDATE_ERR_INVALID_ARGUMENT;
    }
    if (!lock_take()) {
        return CRUX_UPDATE_ERR_BUSY;
    }
    crux_update_result_t result = begin_locked(source);
    lock_give();
    return result;
}

crux_update_result_t crux_update_cancel(void)
{
    if (!atomic_load_explicit(&in_attempt, memory_order_acquire)) {
        return CRUX_UPDATE_ERR_STATE;
    }
    atomic_store_explicit(&cancel_requested, true, memory_order_release);
    return CRUX_UPDATE_OK;
}

/* ---- TR14 and TR15 ---- */

static crux_update_result_t confirm_locked(void)
{
    if (agent.state == CRUX_UPDATE_STATE_NOT_STARTED ||
        agent.state == CRUX_UPDATE_STATE_UNAVAILABLE) {
        return CRUX_UPDATE_ERR_NOT_READY;
    }
    if (agent.state != CRUX_UPDATE_STATE_TESTING) {
        return CRUX_UPDATE_ERR_STATE;
    }
    if (crux_image_confirm() != CRUX_IMAGE_OK) {
        agent.last_result = CRUX_UPDATE_ERR_IO;
        publish();
        return CRUX_UPDATE_ERR_IO;
    }
    agent.last_result = CRUX_UPDATE_OK;
    if (agent.attempt_present && agent.attempt.slot == agent.boot.running_slot &&
        crux_image_version_compare(&agent.attempt.version, &agent.boot.running_version) == 0) {
        agent.outcome = CRUX_IMAGE_OUTCOME_CONFIRMED;
        set_state(CRUX_UPDATE_STATE_OUTCOME);
    } else {
        agent.outcome = CRUX_IMAGE_OUTCOME_NONE; /* no attempt names this image */
        set_state(CRUX_UPDATE_STATE_IDLE);
    }
    return CRUX_UPDATE_OK;
}

crux_update_result_t crux_update_confirm(void)
{
    if (!lock_take()) {
        return CRUX_UPDATE_ERR_BUSY;
    }
    crux_update_result_t result = confirm_locked();
    lock_give();
    return result;
}

static crux_update_result_t acknowledge_locked(void)
{
    if (agent.state == CRUX_UPDATE_STATE_NOT_STARTED ||
        agent.state == CRUX_UPDATE_STATE_UNAVAILABLE) {
        return CRUX_UPDATE_ERR_NOT_READY;
    }
    if (agent.state != CRUX_UPDATE_STATE_OUTCOME && agent.state != CRUX_UPDATE_STATE_FAILED) {
        return CRUX_UPDATE_ERR_STATE;
    }
    if (!crux_update_port_record_clear()) {
        agent.last_result = CRUX_UPDATE_ERR_RECORD;
        publish();
        return CRUX_UPDATE_ERR_RECORD;
    }
    agent.attempt_present = false;
    agent.attempt = (crux_image_attempt_t){0};
    agent.outcome = CRUX_IMAGE_OUTCOME_NONE;
    agent.slot_staged = false;
    agent.last_result = CRUX_UPDATE_OK;
    set_state(CRUX_UPDATE_STATE_IDLE);
    return CRUX_UPDATE_OK;
}

crux_update_result_t crux_update_acknowledge(void)
{
    if (!lock_take()) {
        return CRUX_UPDATE_ERR_BUSY;
    }
    crux_update_result_t result = acknowledge_locked();
    lock_give();
    return result;
}

/* ---- status and the memory source ---- */

crux_update_result_t crux_update_status_get(crux_update_status_t *status)
{
    if (status == NULL) {
        return CRUX_UPDATE_ERR_INVALID_ARGUMENT;
    }
    for (unsigned attempt = 0; attempt < SNAPSHOT_TRIES; attempt++) {
        unsigned seq = atomic_load_explicit(&snap_seq, memory_order_acquire);
        if ((seq & 1u) != 0) {
            continue;
        }
        int state = atomic_load_explicit(&snap_state, memory_order_relaxed);
        int result = atomic_load_explicit(&snap_result, memory_order_relaxed);
        int outcome = atomic_load_explicit(&snap_outcome, memory_order_relaxed);
        unsigned flags = atomic_load_explicit(&snap_flags, memory_order_relaxed);
        unsigned slot = atomic_load_explicit(&snap_slot, memory_order_relaxed);
        unsigned version = atomic_load_explicit(&snap_version, memory_order_relaxed);
        unsigned build = atomic_load_explicit(&snap_build, memory_order_relaxed);
        unsigned done = atomic_load_explicit(&snap_done, memory_order_relaxed);
        unsigned total = atomic_load_explicit(&snap_total, memory_order_relaxed);
        atomic_thread_fence(memory_order_acquire);
        if (atomic_load_explicit(&snap_seq, memory_order_relaxed) != seq) {
            continue;
        }
        status->state = (crux_update_state_t)state;
        status->last_result = (crux_update_result_t)result;
        status->outcome = (crux_image_outcome_t)outcome;
        status->attempt_present = (flags & FLAG_ATTEMPT_PRESENT) != 0;
        status->attempt.slot = (crux_image_slot_t)slot;
        status->attempt.version.major = (uint8_t)(version & 0xFFu);
        status->attempt.version.minor = (uint8_t)((version >> 8) & 0xFFu);
        status->attempt.version.revision = (uint16_t)(version >> 16);
        status->attempt.version.build = build;
        status->attempt.requested = (flags & FLAG_REQUESTED) != 0;
        status->record_lost = (flags & FLAG_RECORD_LOST) != 0;
        status->slot_staged = (flags & FLAG_SLOT_STAGED) != 0;
        status->progress_done = done;
        status->progress_total = total;
        return CRUX_UPDATE_OK;
    }
    return CRUX_UPDATE_ERR_BUSY;
}

static bool memory_read(void *context, size_t offset, void *buffer, size_t length)
{
    const crux_update_memory_source_t *memory = context;
    if (offset > memory->size || length > memory->size - offset) {
        return false;
    }
    memcpy(buffer, &memory->data[offset], length);
    return true;
}

crux_update_source_t crux_update_source_memory(crux_update_memory_source_t *memory,
                                               const void *data, size_t size)
{
    memory->data = data;
    memory->size = size;
    return (crux_update_source_t){size, memory_read, memory};
}
