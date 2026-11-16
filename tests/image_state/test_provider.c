/*
 * The service over the Host double: the slot-state table (S1 to S12), start (B1 to B4), the test
 * request (R1 to R8) and confirm (C1 to C3). Each case starts from image_state_host_init(): slot 0
 * holds a confirmed 1.0.0 image and runs, slot 1 is empty.
 */
#include "harness.h"
#include "image_state_host.h"

#include <crux/image_state.h>

typedef crux_image_port_slot_view_t view_t;

#define UNSET CRUX_IMAGE_PORT_FLAG_UNSET
#define SET CRUX_IMAGE_PORT_FLAG_SET
#define BADFLAG CRUX_IMAGE_PORT_FLAG_INVALID

static crux_image_version_t ver(uint8_t major, uint8_t minor, uint16_t revision, uint32_t build)
{
    return (crux_image_version_t){major, minor, revision, build};
}

static view_t make_view(crux_image_version_t version, crux_image_port_magic_t magic,
                        crux_image_port_flag_t image_ok, crux_image_port_flag_t copy_done)
{
    return (view_t){true, version, magic, image_ok, copy_done};
}

static void started(void)
{
    CHECK_INT(CRUX_IMAGE_OK, crux_image_start());
}

/* The state that crux_image_slot_get() reports for slot 1, with slot 0 running. */
static crux_image_slot_state_t slot1_state(void)
{
    crux_image_slot_info_t info = {0};
    CHECK_INT(CRUX_IMAGE_OK, crux_image_slot_get(1, &info));
    return info.state;
}

static void slot_state_table(void)
{
    static const crux_image_port_magic_t GOOD = CRUX_IMAGE_PORT_MAGIC_GOOD;
    static const crux_image_port_magic_t NOMAGIC = CRUX_IMAGE_PORT_MAGIC_UNSET;
    static const crux_image_port_magic_t BADMAGIC = CRUX_IMAGE_PORT_MAGIC_BAD;
    const crux_image_version_t v110 = ver(1, 1, 0, 5);
    view_t v;

    /* Slots that are not running (slot 1, with slot 0 running). */
    CASE("S1 not running, header invalid or erased: EMPTY, whatever the trailer says");
    image_state_host_init();
    started();
    v = make_view(v110, GOOD, SET, SET);
    v.header_valid = false;
    image_state_host_slot_put(1, &v);
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, slot1_state());

    CASE("S2 not running, magic unset: STAGED");
    image_state_host_init();
    started();
    v = make_view(v110, NOMAGIC, UNSET, UNSET);
    image_state_host_slot_put(1, &v);
    CHECK_INT(CRUX_IMAGE_SLOT_STAGED, slot1_state());

    CASE("S3 not running, magic good, no flags: PENDING_TEST");
    image_state_host_init();
    started();
    v = make_view(v110, GOOD, UNSET, UNSET);
    image_state_host_slot_put(1, &v);
    CHECK_INT(CRUX_IMAGE_SLOT_PENDING_TEST, slot1_state());

    CASE("S4 not running, magic good, image_ok set: PENDING_PERMANENT");
    image_state_host_init();
    started();
    v = make_view(v110, GOOD, SET, UNSET);
    image_state_host_slot_put(1, &v);
    CHECK_INT(CRUX_IMAGE_SLOT_PENDING_PERMANENT, slot1_state());

    CASE("S5 not running, magic good, copy_done set: TRIED");
    image_state_host_init();
    started();
    v = make_view(v110, GOOD, UNSET, SET);
    image_state_host_slot_put(1, &v);
    CHECK_INT(CRUX_IMAGE_SLOT_TRIED, slot1_state());

    CASE("S6 not running, magic good, both flags set: STANDBY_CONFIRMED");
    image_state_host_init();
    started();
    v = make_view(v110, GOOD, SET, SET);
    image_state_host_slot_put(1, &v);
    CHECK_INT(CRUX_IMAGE_SLOT_STANDBY_CONFIRMED, slot1_state());

    CASE("S11 not running, magic bad: INVALID");
    image_state_host_init();
    started();
    v = make_view(v110, BADMAGIC, UNSET, UNSET);
    image_state_host_slot_put(1, &v);
    CHECK_INT(CRUX_IMAGE_SLOT_INVALID, slot1_state());

    CASE("S12 not running, a flag outside set and unset: INVALID");
    image_state_host_init();
    started();
    v = make_view(v110, GOOD, BADFLAG, UNSET);
    image_state_host_slot_put(1, &v);
    CHECK_INT(CRUX_IMAGE_SLOT_INVALID, slot1_state());
    v = make_view(v110, GOOD, UNSET, BADFLAG);
    image_state_host_slot_put(1, &v);
    CHECK_INT(CRUX_IMAGE_SLOT_INVALID, slot1_state());

    /* The contract's choice where the record is silent: a stale flag under an unset magic is not an
     * erased trailer, so the slot is not STAGED. A request would otherwise create a permanent
     * request (image_ok set) or write into a slot that is erased at the next reset (copy_done set).
     */
    CASE("S2b not running, magic unset with a stale flag: INVALID, not STAGED");
    image_state_host_init();
    started();
    v = make_view(v110, NOMAGIC, SET, UNSET);
    image_state_host_slot_put(1, &v);
    CHECK_INT(CRUX_IMAGE_SLOT_INVALID, slot1_state());
    v = make_view(v110, NOMAGIC, UNSET, SET);
    image_state_host_slot_put(1, &v);
    CHECK_INT(CRUX_IMAGE_SLOT_INVALID, slot1_state());

    /* The running slot. */
    CASE("S7 running, image_ok set: RUNNING_CONFIRMED, whatever copy_done says");
    for (int copy = UNSET; copy <= BADFLAG; copy++) {
        image_state_host_init();
        v = make_view(ver(1, 0, 0, 0), GOOD, SET, (crux_image_port_flag_t)copy);
        image_state_host_slot_put(0, &v);
        started();
        crux_image_slot_info_t info = {0};
        CHECK_INT(CRUX_IMAGE_OK, crux_image_slot_get(0, &info));
        CHECK_INT(CRUX_IMAGE_SLOT_RUNNING_CONFIRMED, info.state);
    }

    CASE("S8 running, image_ok unset, copy_done set: RUNNING_TESTING");
    image_state_host_init();
    v = make_view(ver(1, 0, 0, 0), GOOD, UNSET, SET);
    image_state_host_slot_put(0, &v);
    started();
    crux_image_boot_record_t record;
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK_INT(CRUX_IMAGE_SLOT_RUNNING_TESTING, record.slot_state_at_start[0]);
    CHECK(!record.running_confirmed);

    CASE("S9 running, image_ok unset, the bootloader's copy_done write failed: RUNNING_TESTING");
    image_state_host_init();
    v = make_view(ver(1, 0, 0, 0), GOOD, UNSET, UNSET);
    image_state_host_slot_put(0, &v);
    started();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK_INT(CRUX_IMAGE_SLOT_RUNNING_TESTING, record.slot_state_at_start[0]);

    CASE("S10 running, magic not good: the start fails with BOOT_STATE");
    image_state_host_init();
    v = make_view(ver(1, 0, 0, 0), NOMAGIC, UNSET, UNSET);
    image_state_host_slot_put(0, &v);
    CHECK_INT(CRUX_IMAGE_ERR_BOOT_STATE, crux_image_start());
    v = make_view(ver(1, 0, 0, 0), BADMAGIC, SET, SET);
    image_state_host_slot_put(0, &v);
    CHECK_INT(CRUX_IMAGE_ERR_BOOT_STATE, crux_image_start());

    CASE("S10b running, a case the table leaves open: fail closed");
    image_state_host_init();
    v = make_view(ver(1, 0, 0, 0), GOOD, BADFLAG, SET);
    image_state_host_slot_put(0, &v);
    CHECK_INT(CRUX_IMAGE_ERR_BOOT_STATE, crux_image_start());
    v = make_view(ver(1, 0, 0, 0), GOOD, UNSET, BADFLAG);
    image_state_host_slot_put(0, &v);
    CHECK_INT(CRUX_IMAGE_ERR_BOOT_STATE, crux_image_start());
    v = make_view(ver(1, 0, 0, 0), GOOD, SET, SET);
    v.header_valid = false;
    image_state_host_slot_put(0, &v);
    CHECK_INT(CRUX_IMAGE_ERR_BOOT_STATE, crux_image_start());
}

static void start_cases(void)
{
    crux_image_boot_record_t record = {0};
    crux_image_boot_record_t again = {0};

    CASE("B0 nothing works before a start; a started image reports its record");
    image_state_host_init();
    crux_image_slot_info_t info;
    CHECK_INT(CRUX_IMAGE_ERR_NOT_READY, crux_image_boot_record_get(&record));
    CHECK_INT(CRUX_IMAGE_ERR_NOT_READY, crux_image_slot_get(1, &info));
    CHECK_INT(CRUX_IMAGE_ERR_NOT_READY, crux_image_request_test(1));
    CHECK_INT(CRUX_IMAGE_ERR_NOT_READY, crux_image_confirm());
    started();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK_INT(0, record.running_slot);
    CHECK_INT(1, record.inactive_slot);
    CHECK(record.running_confirmed);
    CHECK_INT(0, crux_image_version_compare(&record.running_version,
                                            &(crux_image_version_t){1, 0, 0, 0}));
    CHECK_INT(CRUX_IMAGE_SLOT_RUNNING_CONFIRMED, record.slot_state_at_start[0]);
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, record.slot_state_at_start[1]);

    CASE("B1 no running slot in the boot data: NO_BOOT_DATA, and every later call is NOT_READY");
    image_state_host_init();
    crux_image_port_shared_data_t shared = {false, 0, CRUX_IMAGE_PORT_MODE_RAM_LOAD, false, {0}};
    image_state_host_shared_put(&shared);
    CHECK_INT(CRUX_IMAGE_ERR_NO_BOOT_DATA, crux_image_start());
    CHECK_INT(CRUX_IMAGE_ERR_NOT_READY, crux_image_confirm());
    CHECK_INT(CRUX_IMAGE_ERR_NOT_READY, crux_image_request_test(1));
    CHECK_INT(CRUX_IMAGE_ERR_NOT_READY, crux_image_boot_record_get(&record));
    CASE("B1b the boot data absent altogether, or the mode key missing");
    image_state_host_init();
    image_state_host_shared_set_absent(true);
    CHECK_INT(CRUX_IMAGE_ERR_NO_BOOT_DATA, crux_image_start());
    image_state_host_init();
    shared = (crux_image_port_shared_data_t){true, 0, CRUX_IMAGE_PORT_MODE_MISSING, false, {0}};
    image_state_host_shared_put(&shared);
    CHECK_INT(CRUX_IMAGE_ERR_NO_BOOT_DATA, crux_image_start());
    CASE("B1c a failed start caches nothing: once the data is there, a start succeeds");
    image_state_host_shared_set_absent(false);
    shared = (crux_image_port_shared_data_t){true, 0, CRUX_IMAGE_PORT_MODE_RAM_LOAD, false, {0}};
    image_state_host_shared_put(&shared);
    started();

    CASE("B2 a mode other than RAM load, or a running slot above 1: BOOT_STATE");
    image_state_host_init();
    shared =
        (crux_image_port_shared_data_t){true, 0, CRUX_IMAGE_PORT_MODE_OTHER, true, {2, 4, 0, 0}};
    image_state_host_shared_put(&shared);
    CHECK_INT(CRUX_IMAGE_ERR_BOOT_STATE, crux_image_start());
    CHECK_INT(CRUX_IMAGE_ERR_NOT_READY, crux_image_confirm());
    image_state_host_init();
    shared =
        (crux_image_port_shared_data_t){true, 2, CRUX_IMAGE_PORT_MODE_RAM_LOAD, true, {2, 4, 0, 0}};
    image_state_host_shared_put(&shared);
    CHECK_INT(CRUX_IMAGE_ERR_BOOT_STATE, crux_image_start());

    CASE("B3 bootloader version: present, absent, present with zero fields");
    image_state_host_init();
    started();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK(record.bootloader_version_known);
    CHECK_INT(0, crux_image_version_compare(&record.bootloader_version,
                                            &(crux_image_version_t){2, 4, 0, 0}));
    image_state_host_init();
    shared = (crux_image_port_shared_data_t){
        true, 0, CRUX_IMAGE_PORT_MODE_RAM_LOAD, false, {9, 9, 9, 9}};
    image_state_host_shared_put(&shared);
    started();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK(!record.bootloader_version_known);
    image_state_host_init();
    shared =
        (crux_image_port_shared_data_t){true, 0, CRUX_IMAGE_PORT_MODE_RAM_LOAD, true, {0, 0, 0, 0}};
    image_state_host_shared_put(&shared);
    started();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK(record.bootloader_version_known); /* the flag follows the key, not the value */
    CHECK_INT(0, record.bootloader_version.major);

    CASE("B4 start twice returns the same record and reads nothing again");
    image_state_host_init();
    started();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    /* Change the medium: a second start must not notice. */
    view_t v = make_view(ver(3, 0, 0, 0), CRUX_IMAGE_PORT_MAGIC_GOOD, SET, SET);
    image_state_host_slot_put(1, &v);
    started();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&again));
    CHECK_INT(again.running_slot, record.running_slot);
    CHECK_INT(again.slot_state_at_start[1], record.slot_state_at_start[1]);
    CHECK_INT(CRUX_IMAGE_SLOT_EMPTY, again.slot_state_at_start[1]);

    CASE("B5 a slot that cannot be read fails the start with IO, and a later start can succeed");
    image_state_host_init();
    image_state_host_fail_slot_read(1, true);
    CHECK_INT(CRUX_IMAGE_ERR_IO, crux_image_start());
    image_state_host_fail_slot_read(1, false);
    started();

    CASE("B6 arguments: NULL, and a slot that does not exist");
    image_state_host_init();
    CHECK_INT(CRUX_IMAGE_ERR_INVALID_ARGUMENT, crux_image_boot_record_get(NULL));
    CHECK_INT(CRUX_IMAGE_ERR_INVALID_ARGUMENT, crux_image_slot_get(0, NULL));
    CHECK_INT(CRUX_IMAGE_ERR_INVALID_ARGUMENT, crux_image_slot_get(2, &info));
    started();
    CHECK_INT(CRUX_IMAGE_ERR_INVALID_ARGUMENT, crux_image_boot_record_get(NULL));
    CHECK_INT(CRUX_IMAGE_ERR_INVALID_ARGUMENT, crux_image_slot_get(0, NULL));
    CHECK_INT(CRUX_IMAGE_ERR_INVALID_ARGUMENT, crux_image_slot_get(2, &info));
    CHECK_INT(CRUX_IMAGE_ERR_INVALID_ARGUMENT, crux_image_request_test(2));
    CHECK_INT(0, image_state_host_write_count());

    CASE("B7 running from slot 1: the record names slot 1 and the inactive slot 0");
    image_state_host_init();
    view_t slot0 = make_view(ver(1, 0, 0, 0), CRUX_IMAGE_PORT_MAGIC_GOOD, SET, SET);
    view_t slot1 = make_view(ver(1, 1, 0, 0), CRUX_IMAGE_PORT_MAGIC_GOOD, UNSET, SET);
    image_state_host_slot_put(0, &slot0);
    image_state_host_slot_put(1, &slot1);
    shared =
        (crux_image_port_shared_data_t){true, 1, CRUX_IMAGE_PORT_MODE_RAM_LOAD, true, {2, 4, 0, 0}};
    image_state_host_shared_put(&shared);
    started();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK_INT(1, record.running_slot);
    CHECK_INT(0, record.inactive_slot);
    CHECK(!record.running_confirmed);
    CHECK_INT(CRUX_IMAGE_SLOT_RUNNING_TESTING, record.slot_state_at_start[1]);
    CHECK_INT(CRUX_IMAGE_SLOT_STANDBY_CONFIRMED, record.slot_state_at_start[0]);
}

static void stage_newer(crux_image_slot_t slot, crux_image_version_t version)
{
    image_state_host_stage(slot, version);
}

static void write_hook_reenters_confirm(void)
{
    static bool inside;
    if (inside) {
        return;
    }
    inside = true;
    CHECK_INT(CRUX_IMAGE_ERR_BUSY, crux_image_start());
    CHECK_INT(CRUX_IMAGE_ERR_BUSY, crux_image_confirm());
    CHECK_INT(CRUX_IMAGE_ERR_BUSY, crux_image_request_test(1));
    inside = false;
}

static void request_cases(void)
{
    crux_image_slot_info_t info;

    CASE("R1a request from slot 0 for slot 1 writes the inactive slot: magic, then swap info");
    image_state_host_init();
    started();
    stage_newer(1, ver(1, 1, 0, 0));
    CHECK_INT(CRUX_IMAGE_OK, crux_image_request_test(1));
    CHECK_INT(2, image_state_host_write_count());
    CHECK_INT(IMAGE_STATE_HOST_WRITE_MAGIC, image_state_host_write_op(0));
    CHECK_INT(IMAGE_STATE_HOST_WRITE_SWAP_INFO_TEST, image_state_host_write_op(1));
    CHECK_INT(1, image_state_host_write_slot(0));
    CHECK_INT(1, image_state_host_write_slot(1));
    CHECK_INT(CRUX_IMAGE_SLOT_PENDING_TEST, slot1_state());
    CHECK_INT(CRUX_IMAGE_PORT_FLAG_UNSET,
              image_state_host_slot_peek(1).image_ok); /* a test request */

    CASE("R1b request from slot 1 for slot 0 writes slot 0, the B63a regression");
    image_state_host_init();
    view_t slot0 = make_view(ver(1, 0, 0, 0), CRUX_IMAGE_PORT_MAGIC_GOOD, SET, SET);
    view_t slot1 = make_view(ver(1, 1, 0, 0), CRUX_IMAGE_PORT_MAGIC_GOOD, SET, SET);
    image_state_host_slot_put(0, &slot0);
    image_state_host_slot_put(1, &slot1);
    crux_image_port_shared_data_t shared = {
        true, 1, CRUX_IMAGE_PORT_MODE_RAM_LOAD, true, {2, 4, 0, 0}};
    image_state_host_shared_put(&shared);
    started();
    stage_newer(0, ver(1, 2, 0, 0));
    CHECK_INT(CRUX_IMAGE_OK, crux_image_request_test(0));
    CHECK_INT(2, image_state_host_write_count());
    CHECK_INT(0, image_state_host_write_slot(0));
    CHECK_INT(0, image_state_host_write_slot(1));
    CHECK_INT(CRUX_IMAGE_PORT_MAGIC_GOOD, image_state_host_slot_peek(0).magic);
    /* The running slot is untouched. */
    CHECK_INT(CRUX_IMAGE_PORT_FLAG_SET, image_state_host_slot_peek(1).image_ok);

    CASE("R2 the running slot is refused and nothing is written");
    image_state_host_init();
    started();
    CHECK_INT(CRUX_IMAGE_ERR_ACTIVE_SLOT, crux_image_request_test(0));
    CHECK_INT(0, image_state_host_write_count());

    CASE("R3 the running image on trial: NOT_CONFIRMED, nothing is written");
    image_state_host_init();
    view_t trial = make_view(ver(1, 0, 0, 0), CRUX_IMAGE_PORT_MAGIC_GOOD, UNSET, SET);
    image_state_host_slot_put(0, &trial);
    started();
    stage_newer(1, ver(1, 1, 0, 0));
    CHECK_INT(CRUX_IMAGE_ERR_NOT_CONFIRMED, crux_image_request_test(1));
    CHECK_INT(0, image_state_host_write_count());

    CASE("R3b the live state counts: after a confirm in this boot a request passes");
    CHECK_INT(CRUX_IMAGE_OK, crux_image_confirm());
    CHECK_INT(CRUX_IMAGE_OK, crux_image_request_test(1));

    CASE("R4 an empty slot: NO_IMAGE");
    image_state_host_init();
    started();
    CHECK_INT(CRUX_IMAGE_ERR_NO_IMAGE, crux_image_request_test(1));
    CHECK_INT(0, image_state_host_write_count());

    CASE("R5 older and equal versions are refused, newer succeeds, the build number is ignored");
    image_state_host_init();
    started();
    stage_newer(1, ver(0, 9, 0, 0));
    CHECK_INT(CRUX_IMAGE_ERR_NOT_NEWER, crux_image_request_test(1));
    stage_newer(1, ver(1, 0, 0, 0));
    CHECK_INT(CRUX_IMAGE_ERR_NOT_NEWER, crux_image_request_test(1));
    stage_newer(1, ver(1, 0, 0, 9999)); /* same release, a higher build number */
    CHECK_INT(CRUX_IMAGE_ERR_NOT_NEWER, crux_image_request_test(1));
    CHECK_INT(0, image_state_host_write_count());
    stage_newer(1, ver(1, 0, 1, 0));
    CHECK_INT(CRUX_IMAGE_OK, crux_image_request_test(1));

    CASE("R5b the running version is read from its header on the medium, not from the record");
    image_state_host_init();
    started();
    view_t moved = make_view(ver(1, 5, 0, 0), CRUX_IMAGE_PORT_MAGIC_GOOD, SET, SET);
    image_state_host_slot_put(0, &moved);
    stage_newer(1, ver(1, 4, 0, 0));
    CHECK_INT(CRUX_IMAGE_ERR_NOT_NEWER, crux_image_request_test(1));

    CASE("R6 a stale confirmed trailer under a newer image: SLOT_STATE, not a silent success");
    image_state_host_init();
    started();
    view_t stale = make_view(ver(1, 1, 0, 0), CRUX_IMAGE_PORT_MAGIC_GOOD, SET, SET);
    image_state_host_slot_put(1, &stale);
    CHECK_INT(CRUX_IMAGE_ERR_SLOT_STATE, crux_image_request_test(1));
    view_t permanent = make_view(ver(1, 1, 0, 0), CRUX_IMAGE_PORT_MAGIC_GOOD, SET, UNSET);
    image_state_host_slot_put(1, &permanent);
    CHECK_INT(CRUX_IMAGE_ERR_SLOT_STATE, crux_image_request_test(1));
    view_t tried = make_view(ver(1, 1, 0, 0), CRUX_IMAGE_PORT_MAGIC_GOOD, UNSET, SET);
    image_state_host_slot_put(1, &tried);
    CHECK_INT(CRUX_IMAGE_ERR_SLOT_STATE, crux_image_request_test(1));
    view_t flagged = make_view(ver(1, 1, 0, 0), CRUX_IMAGE_PORT_MAGIC_UNSET, SET, UNSET);
    image_state_host_slot_put(1, &flagged);
    CHECK_INT(CRUX_IMAGE_ERR_SLOT_STATE, crux_image_request_test(1));
    view_t badmagic = make_view(ver(1, 1, 0, 0), CRUX_IMAGE_PORT_MAGIC_BAD, UNSET, UNSET);
    image_state_host_slot_put(1, &badmagic);
    CHECK_INT(CRUX_IMAGE_ERR_SLOT_STATE, crux_image_request_test(1));
    CHECK_INT(0, image_state_host_write_count());

    CASE("R7 a second request for a pending slot returns OK and writes nothing");
    image_state_host_init();
    started();
    stage_newer(1, ver(1, 1, 0, 0));
    CHECK_INT(CRUX_IMAGE_OK, crux_image_request_test(1));
    size_t writes = image_state_host_write_count();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_request_test(1));
    CHECK_INT(writes, image_state_host_write_count());

    CASE("R8a a failure on the first write changes nothing, and a retry completes");
    image_state_host_init();
    started();
    stage_newer(1, ver(1, 1, 0, 0));
    image_state_host_fail_nth_write(1);
    CHECK_INT(CRUX_IMAGE_ERR_IO, crux_image_request_test(1));
    CHECK_INT(0, image_state_host_write_count());
    CHECK_INT(CRUX_IMAGE_SLOT_STAGED, slot1_state());
    CHECK_INT(CRUX_IMAGE_OK, crux_image_request_test(1));
    CHECK_INT(CRUX_IMAGE_SLOT_PENDING_TEST, slot1_state());

    CASE("R8b a failure after the magic leaves the slot PENDING_TEST, and a repeat is OK");
    image_state_host_init();
    started();
    stage_newer(1, ver(1, 1, 0, 0));
    image_state_host_fail_nth_write(2);
    CHECK_INT(CRUX_IMAGE_ERR_IO, crux_image_request_test(1));
    CHECK_INT(1, image_state_host_write_count());
    CHECK_INT(IMAGE_STATE_HOST_WRITE_MAGIC, image_state_host_write_op(0));
    CHECK_INT(CRUX_IMAGE_SLOT_PENDING_TEST, slot1_state());
    CHECK_INT(CRUX_IMAGE_OK, crux_image_request_test(1));

    CASE("R9 a slot that cannot be read: IO, nothing written");
    image_state_host_init();
    started();
    stage_newer(1, ver(1, 1, 0, 0));
    image_state_host_fail_slot_read(1, true);
    CHECK_INT(CRUX_IMAGE_ERR_IO, crux_image_request_test(1));
    CHECK_INT(CRUX_IMAGE_ERR_IO, crux_image_slot_get(1, &info));
    image_state_host_fail_slot_read(1, false);
    image_state_host_fail_slot_read(0, true);
    CHECK_INT(CRUX_IMAGE_ERR_IO, crux_image_request_test(1));
    CHECK_INT(0, image_state_host_write_count());

    CASE("R10 the running slot's live trailer stops being a supported one: BOOT_STATE");
    image_state_host_init();
    started();
    stage_newer(1, ver(1, 1, 0, 0));
    view_t broken = make_view(ver(1, 0, 0, 0), CRUX_IMAGE_PORT_MAGIC_BAD, SET, SET);
    image_state_host_slot_put(0, &broken);
    CHECK_INT(CRUX_IMAGE_ERR_BOOT_STATE, crux_image_request_test(1));
    CHECK_INT(CRUX_IMAGE_ERR_BOOT_STATE, crux_image_confirm());
    CHECK_INT(CRUX_IMAGE_OK, crux_image_slot_get(0, &info));
    CHECK_INT(CRUX_IMAGE_SLOT_INVALID, info.state); /* reported, not hidden */
    CHECK_INT(0, image_state_host_write_count());

    CASE("R12 a pending slot that is no longer strictly newer: NOT_NEWER, not an idempotent OK");
    image_state_host_init();
    started();
    stage_newer(1, ver(1, 1, 0, 0));
    CHECK_INT(CRUX_IMAGE_OK, crux_image_request_test(1));
    view_t overtaken = make_view(ver(1, 1, 0, 0), CRUX_IMAGE_PORT_MAGIC_GOOD, SET, SET);
    image_state_host_slot_put(0,
                              &overtaken); /* the running image is now as new as the pending one */
    CHECK_INT(CRUX_IMAGE_ERR_NOT_NEWER, crux_image_request_test(1));

    CASE("R11 a request, a confirm and a start inside another call get BUSY");
    image_state_host_init();
    started();
    stage_newer(1, ver(1, 1, 0, 0));
    image_state_host_set_write_hook(write_hook_reenters_confirm);
    CHECK_INT(CRUX_IMAGE_OK, crux_image_request_test(1));
    image_state_host_set_write_hook(NULL);
    CHECK_INT(2, image_state_host_write_count());
}

static void confirm_cases(void)
{
    crux_image_slot_info_t info;
    view_t trial = make_view(ver(1, 0, 0, 0), CRUX_IMAGE_PORT_MAGIC_GOOD, UNSET, SET);

    CASE("C1 confirm on trial writes image_ok of the running slot, and a second call writes "
         "nothing");
    image_state_host_init();
    image_state_host_slot_put(0, &trial);
    started();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_confirm());
    CHECK_INT(1, image_state_host_write_count());
    CHECK_INT(IMAGE_STATE_HOST_WRITE_IMAGE_OK, image_state_host_write_op(0));
    CHECK_INT(0, image_state_host_write_slot(0));
    CHECK_INT(CRUX_IMAGE_OK, crux_image_slot_get(0, &info));
    CHECK_INT(CRUX_IMAGE_SLOT_RUNNING_CONFIRMED, info.state);
    CHECK_INT(CRUX_IMAGE_OK, crux_image_confirm());
    CHECK_INT(1, image_state_host_write_count());
    /* The record is the snapshot at start: it still says the image was on trial. */
    crux_image_boot_record_t record;
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    CHECK(!record.running_confirmed);

    CASE("C1b an already confirmed image: OK, no write");
    image_state_host_init();
    started();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_confirm());
    CHECK_INT(0, image_state_host_write_count());

    CASE("C2 confirm when running from slot 1 changes slot 1 and not slot 0");
    image_state_host_init();
    view_t slot0 = make_view(ver(1, 0, 0, 0), CRUX_IMAGE_PORT_MAGIC_GOOD, SET, SET);
    view_t slot1 = make_view(ver(1, 1, 0, 0), CRUX_IMAGE_PORT_MAGIC_GOOD, UNSET, SET);
    image_state_host_slot_put(0, &slot0);
    image_state_host_slot_put(1, &slot1);
    crux_image_port_shared_data_t shared = {
        true, 1, CRUX_IMAGE_PORT_MODE_RAM_LOAD, true, {2, 4, 0, 0}};
    image_state_host_shared_put(&shared);
    started();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_confirm());
    CHECK_INT(1, image_state_host_write_count());
    CHECK_INT(1, image_state_host_write_slot(0));
    CHECK_INT(CRUX_IMAGE_PORT_FLAG_SET, image_state_host_slot_peek(1).image_ok);
    CHECK_INT(CRUX_IMAGE_PORT_FLAG_SET,
              image_state_host_slot_peek(0).image_ok); /* it was set before */
    slot0.image_ok = UNSET; /* a sentinel: a confirm of slot 0 would set it */
    image_state_host_init();
    image_state_host_slot_put(0, &slot0);
    slot1.image_ok = UNSET;
    image_state_host_slot_put(1, &slot1);
    image_state_host_shared_put(&shared);
    started();
    CHECK_INT(CRUX_IMAGE_OK, crux_image_confirm());
    CHECK_INT(CRUX_IMAGE_PORT_FLAG_SET, image_state_host_slot_peek(1).image_ok);
    CHECK_INT(CRUX_IMAGE_PORT_FLAG_UNSET, image_state_host_slot_peek(0).image_ok);

    CASE("C3 a write failure: IO, and the state stays RUNNING_TESTING");
    image_state_host_init();
    image_state_host_slot_put(0, &trial);
    started();
    image_state_host_fail_nth_write(1);
    CHECK_INT(CRUX_IMAGE_ERR_IO, crux_image_confirm());
    CHECK_INT(CRUX_IMAGE_OK, crux_image_slot_get(0, &info));
    CHECK_INT(CRUX_IMAGE_SLOT_RUNNING_TESTING, info.state);
    CHECK_INT(CRUX_IMAGE_OK, crux_image_confirm()); /* a retry works */

    CASE("C4 the running slot cannot be read: IO");
    image_state_host_init();
    started();
    image_state_host_fail_slot_read(0, true);
    CHECK_INT(CRUX_IMAGE_ERR_IO, crux_image_confirm());
}

int main(void)
{
    slot_state_table();
    start_cases();
    request_cases();
    confirm_cases();
    return harness_finish("image_state_provider");
}
