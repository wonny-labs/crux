/*
 * The checks of TR6 (gates G1 to G7 and the version policy VP1 of the update agent proposal) and
 * the staging path of U4. Every refusal must leave the staging slot and the attempt record
 * untouched: no medium operation at all, and the state it came from.
 */
#include "common.h"

#include <string.h>

static uint8_t image[MEDIUM_IMAGE_MAX];

/* Begins with a source over the image and checks the refusal: no operation, state unchanged. */
static void expect_refusal(size_t size, crux_update_result_t expected)
{
    medium_source_t state;
    crux_update_source_t source = medium_source(&state, image, size);
    crux_update_state_t before = state_now();
    size_t writes = medium_slot_write_count(1);
    CHECK_INT(expected, crux_update_begin(&source));
    CHECK_INT(0, medium_op_count());
    CHECK_INT(writes, medium_slot_write_count(1));
    CHECK_INT(before, state_now());
    CHECK_INT(expected, status_now().last_result);
    CHECK(!medium_record_get(NULL));
}

static size_t build(const medium_image_spec_t *spec)
{
    return medium_image_build(spec, image, sizeof(image));
}

static void fresh(void)
{
    medium_init();
    start_ok();
    CHECK_INT(CRUX_UPDATE_STATE_IDLE, state_now());
}

static void header_gates(void)
{
    medium_image_spec_t spec;
    size_t size;

    CASE("G1: a wrong header magic is refused before any write");
    fresh();
    size = build_image(image, 1, 1, 0);
    image[0] ^= 0xFFu;
    expect_refusal(size, CRUX_UPDATE_ERR_FORMAT);

    CASE("G1: a header size other than the composition's is refused");
    fresh();
    spec = medium_image_default(1, 1, 0);
    spec.header_size = MEDIUM_HEADER_SIZE * 2u;
    expect_refusal(build(&spec), CRUX_UPDATE_ERR_FORMAT);

    CASE("G1: a source shorter than the header fields is refused");
    fresh();
    build_image(image, 1, 1, 0);
    expect_refusal(16, CRUX_UPDATE_ERR_FORMAT);

    CASE("G2: an image without the RAM-load flag is refused");
    fresh();
    spec = medium_image_default(1, 1, 0);
    spec.flags = 0;
    expect_refusal(build(&spec), CRUX_UPDATE_ERR_LOAD_ADDRESS);

    CASE("G2: a load address other than the composition's is refused");
    fresh();
    spec = medium_image_default(1, 1, 0);
    spec.load_address = MEDIUM_LOAD_ADDRESS + 0x1000u;
    expect_refusal(build(&spec), CRUX_UPDATE_ERR_LOAD_ADDRESS);
}

static void length_gates(void)
{
    medium_image_spec_t spec;
    size_t size;

    CASE("G3: bytes after the metadata (a padded image) are refused");
    fresh();
    size = build_image(image, 1, 1, 0);
    expect_refusal(size + 16u, CRUX_UPDATE_ERR_LENGTH);

    CASE("G3: a source shorter than the image the header describes is refused");
    fresh();
    size = build_image(image, 1, 1, 0);
    expect_refusal(size - 1u, CRUX_UPDATE_ERR_LENGTH);

    CASE("G3: a body size beyond the source is refused, not read past the end");
    fresh();
    size = build_image(image, 1, 1, 0);
    image[15] = 0x7Fu; /* image_size of about 2 GiB */
    expect_refusal(size, CRUX_UPDATE_ERR_LENGTH);

    CASE("G4: an image that reaches the slot trailer is refused");
    fresh();
    spec = medium_image_default(1, 1, 0);
    spec.body_size = MEDIUM_SLOT_SIZE - MEDIUM_TRAILER_SIZE - MEDIUM_HEADER_SIZE;
    expect_refusal(build(&spec), CRUX_UPDATE_ERR_TOO_LARGE);

    CASE("G4: an image that ends exactly at the trailer fits");
    fresh();
    spec = medium_image_default(1, 1, 0);
    spec.body_size = 0;
    size = build(&spec);
    spec.body_size = (uint32_t)(MEDIUM_SLOT_SIZE - MEDIUM_TRAILER_SIZE - size);
    size = build(&spec);
    CHECK_INT(MEDIUM_SLOT_SIZE - MEDIUM_TRAILER_SIZE, size);
    {
        medium_source_t state;
        crux_update_source_t source = medium_source(&state, image, size);
        CHECK_INT(CRUX_UPDATE_OK, crux_update_begin(&source));
        CHECK_INT(CRUX_UPDATE_STATE_WAITING_RESET, state_now());
    }

    CASE("G3: a protected-area size that disagrees with its information header is refused");
    fresh();
    size = build_image(image, 1, 1, 0);
    image[10] = 16; /* protect_tlv_size 16, the area says 12 */
    expect_refusal(size, CRUX_UPDATE_ERR_FORMAT);

    CASE("G3: a wrong metadata magic is refused");
    fresh();
    size = build_image(image, 1, 1, 0);
    image[MEDIUM_HEADER_SIZE + 3000u + 12u] ^= 0xFFu;
    expect_refusal(size, CRUX_UPDATE_ERR_FORMAT);
}

static void version_gates(void)
{
    size_t size;

    CASE("G5/VP1: an equal version is refused before the first erase or write");
    fresh();
    size = build_image(image, 1, 0, 0);
    expect_refusal(size, CRUX_UPDATE_ERR_NOT_NEWER);

    CASE("G5/VP1: an older version is refused");
    fresh();
    size = build_image(image, 0, 9, 9);
    expect_refusal(size, CRUX_UPDATE_ERR_NOT_NEWER);

    CASE("G5/VP1: a newer build number alone is not newer");
    fresh();
    {
        medium_image_spec_t spec = medium_image_default(1, 0, 0);
        spec.version.build = 9999;
        expect_refusal(build(&spec), CRUX_UPDATE_ERR_NOT_NEWER);
    }

    CASE("G5/VP1: equal version refused with a stale image in the slot: nothing is erased");
    fresh();
    {
        static uint8_t stale[MEDIUM_IMAGE_MAX];
        size_t stale_size = build_image(stale, 0, 5, 0);
        medium_slot_load(1, stale, stale_size, true);
        size = build_image(image, 1, 0, 0);
        expect_refusal(size, CRUX_UPDATE_ERR_NOT_NEWER);
        CHECK(memcmp(medium_slot_bytes(1), stale, stale_size) == 0);
    }

    CASE("G5: a newer revision (16-bit) is accepted");
    fresh();
    size = build_image(image, 1, 0, 300);
    {
        medium_source_t state;
        crux_update_source_t source = medium_source(&state, image, size);
        CHECK_INT(CRUX_UPDATE_OK, crux_update_begin(&source));
    }

    CASE("G5: the version compares with the running image, not with a newer standby");
    fresh();
    {
        static uint8_t standby[MEDIUM_IMAGE_MAX];
        size_t standby_size = build_image(standby, 0, 8, 0);
        medium_slot_load(1, standby, standby_size, true);
        size = build_image(image, 1, 0, 1);
        medium_source_t state;
        crux_update_source_t source = medium_source(&state, image, size);
        CHECK_INT(CRUX_UPDATE_OK, crux_update_begin(&source));
    }
}

static void integrity_gates(void)
{
    medium_image_spec_t spec;
    size_t size;

    CASE("G6: a body byte that differs from the digest is refused");
    fresh();
    size = build_image(image, 1, 1, 0);
    image[MEDIUM_HEADER_SIZE + 10u] ^= 0x01u;
    expect_refusal(size, CRUX_UPDATE_ERR_HASH);

    CASE("G6: a protected metadata byte is covered by the digest");
    fresh();
    size = build_image(image, 1, 1, 0);
    image[MEDIUM_HEADER_SIZE + 3000u + 8u] ^= 0x01u;
    expect_refusal(size, CRUX_UPDATE_ERR_HASH);

    CASE("G6: a header byte is covered by the digest (the build number)");
    fresh();
    size = build_image(image, 1, 1, 0);
    image[24] ^= 0x01u;
    expect_refusal(size, CRUX_UPDATE_ERR_HASH);

    CASE("G6: an image without a SHA-256 entry is refused");
    fresh();
    spec = medium_image_default(1, 1, 0);
    spec.sha256 = false;
    expect_refusal(build(&spec), CRUX_UPDATE_ERR_HASH);

    CASE("G7: a signature that does not verify is refused");
    fresh();
    size = build_image(image, 1, 1, 0);
    image[medium_image_tlv_value_offset(image, size, 0x22u)] ^= 0x01u;
    expect_refusal(size, CRUX_UPDATE_ERR_SIGNATURE);

    CASE("G7/W5: an image without a signature is refused (the check is required)");
    fresh();
    spec = medium_image_default(1, 1, 0);
    spec.signature = false;
    expect_refusal(build(&spec), CRUX_UPDATE_ERR_SIGNATURE);

    CASE("G6: an image without a protected area is accepted");
    fresh();
    spec = medium_image_default(1, 1, 0);
    spec.protected_area = false;
    size = build(&spec);
    {
        medium_source_t state;
        crux_update_source_t source = medium_source(&state, image, size);
        CHECK_INT(CRUX_UPDATE_OK, crux_update_begin(&source));
    }

    CASE("A source that cannot be read is refused before any write");
    fresh();
    size = build_image(image, 1, 1, 0);
    {
        medium_source_t state;
        crux_update_source_t source = medium_source(&state, image, size);
        state.fail_reads = true;
        CHECK_INT(CRUX_UPDATE_ERR_SOURCE, crux_update_begin(&source));
        CHECK_INT(0, medium_op_count());
        CHECK_INT(CRUX_UPDATE_STATE_IDLE, state_now());
    }

    CASE("A NULL source or one without a read function is an invalid argument");
    fresh();
    {
        crux_update_source_t source = {16, NULL, NULL};
        CHECK_INT(CRUX_UPDATE_ERR_INVALID_ARGUMENT, crux_update_begin(NULL));
        CHECK_INT(CRUX_UPDATE_ERR_INVALID_ARGUMENT, crux_update_begin(&source));
        CHECK_INT(0, medium_op_count());
    }
}

/* What a successful attempt writes, in which order (U4 and TR8 to TR13). */
static void staging_order(void)
{
    size_t size;

    CASE("U4: record, erase, body, header (magic last), read-back, record, request, in order");
    fresh();
    {
        static uint8_t stale[MEDIUM_IMAGE_MAX];
        size_t stale_size = build_image(stale, 0, 5, 0);
        medium_slot_load(1, stale, stale_size, true); /* a stale trailer must be erased */
    }
    size = build_image(image, 1, 1, 0);
    medium_source_t state;
    crux_update_source_t source = medium_source(&state, image, size);
    CHECK_INT(CRUX_UPDATE_OK, crux_update_begin(&source));
    CHECK_INT(CRUX_UPDATE_STATE_WAITING_RESET, state_now());
    CHECK_INT(CRUX_IMAGE_SLOT_PENDING_TEST, medium_slot_state(1));
    CHECK(memcmp(medium_slot_bytes(1), image, size) == 0);

    size_t first_store = medium_op_find(MEDIUM_OP_RECORD_STORE, UINT32_MAX);
    size_t first_erase = medium_op_find(MEDIUM_OP_SLOT_ERASE, UINT32_MAX);
    size_t header_erase = medium_op_find(MEDIUM_OP_SLOT_ERASE, 0);
    size_t trailer_erase = medium_op_find(MEDIUM_OP_SLOT_ERASE, MEDIUM_SECTOR_COUNT - 1u);
    size_t first_body = medium_op_find(MEDIUM_OP_SLOT_WRITE, MEDIUM_HEADER_SIZE);
    size_t header_rest = medium_op_find(MEDIUM_OP_SLOT_WRITE, 4);
    size_t magic = medium_op_find(MEDIUM_OP_SLOT_WRITE, 0);
    size_t request = medium_op_find(MEDIUM_OP_CONTRACT_WRITE, UINT32_MAX);
    CHECK(first_store == 1u);
    CHECK(header_erase == first_erase); /* header sector first */
    CHECK(trailer_erase > header_erase);
    CHECK(first_body > trailer_erase);
    CHECK(header_rest > first_body);
    CHECK(magic > header_rest); /* the header magic is the last slot write */
    CHECK_INT(MEDIUM_OP_RECORD_STORE, medium_op(magic).kind); /* next op: the requested record */
    CHECK(request == magic + 2u);
    CHECK_INT(medium_op_count(), request + 1u); /* magic, then the swap information */
    {
        crux_image_attempt_t attempt;
        CHECK(medium_record_get(&attempt));
        CHECK(attempt.requested);
        CHECK_INT(1, attempt.slot);
        CHECK_INT(1, attempt.version.minor);
    }

    CASE("U4: an already blank slot is not erased again, but blank-checked");
    fresh();
    size = build_image(image, 1, 1, 0);
    source = medium_source(&state, image, size);
    CHECK_INT(CRUX_UPDATE_OK, crux_update_begin(&source));
    CHECK_INT(0, medium_op_find(MEDIUM_OP_SLOT_ERASE, UINT32_MAX));

    CASE("U4: a write block of 8 pads the last write with the erased value");
    fresh();
    medium_set_write_block(8);
    {
        medium_image_spec_t spec = medium_image_default(1, 1, 0);
        spec.body_size = 3001;
        size = build(&spec);
    }
    CHECK(size % 8u != 0);
    source = medium_source(&state, image, size);
    CHECK_INT(CRUX_UPDATE_OK, crux_update_begin(&source));
    CHECK(memcmp(medium_slot_bytes(1), image, size) == 0);
    CHECK_INT(0xFF, medium_slot_bytes(1)[size]);
    CHECK(medium_op_find(MEDIUM_OP_SLOT_WRITE, 8) != 0); /* the header rest starts at block 1 */

    CASE("U4: a source that changes between the check and the write is caught at TR12");
    fresh();
    size = build_image(image, 1, 1, 0);
    source = medium_source(&state, image, size);
    state.mutate = true;
    state.mutate_offset = MEDIUM_HEADER_SIZE + 100u;
    CHECK_INT(CRUX_UPDATE_ERR_VERIFY, crux_update_begin(&source));
    CHECK_INT(CRUX_UPDATE_STATE_FAILED, state_now());
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, medium_slot_state(1)); /* TR16 invalidated the slot */
    CHECK(!status_now().slot_staged);
    {
        crux_image_attempt_t attempt;
        CHECK(medium_record_get(&attempt));
        CHECK(!attempt.requested);
    }

    CASE("The memory source reads in range and refuses beyond its end");
    {
        crux_update_memory_source_t memory;
        uint8_t data[4] = {1, 2, 3, 4};
        uint8_t out[4] = {0};
        crux_update_source_t mem = crux_update_source_memory(&memory, data, sizeof(data));
        CHECK_INT(4, mem.size);
        CHECK(mem.read(mem.context, 1, out, 3));
        CHECK_INT(4, out[2]);
        CHECK(!mem.read(mem.context, 2, out, 3));
    }
}

int main(void)
{
    header_gates();
    length_gates();
    version_gates();
    integrity_gates();
    staging_order();
    return harness_finish("update_agent_gates");
}
