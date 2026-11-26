/* Session exhaustion and reclaim, store states, malformed records, 64-bit time, provider failures,
 * lock failure and concurrent logins. */
#include "access_test.h"

#include <pthread.h>
#include <stdatomic.h>

#define ADMIN ACCESS_TEST_ADMIN
#define USER ACCESS_TEST_USER
#define PASSWORD ACCESS_TEST_PASSWORD
#define WRONG "wrong-password-here"

static const crux_access_policy_t *reference(void)
{
    return &access_test_profile_reference.policy;
}

static crux_access_session_t setup_accounts(void)
{
    access_test_boot_with_admin();
    crux_access_session_t admin = access_test_session(ADMIN, PASSWORD, &access_test_serial);
    access_test_create_user(admin);
    CHECK(crux_access_account_create(admin, "carol", "viewer", PASSWORD, strlen(PASSWORD)) ==
          CRUX_ACCESS_OK);
    CHECK(crux_access_account_create(admin, "dave", "viewer", PASSWORD, strlen(PASSWORD)) ==
          CRUX_ACCESS_OK);
    return admin;
}

static void per_account_cap_cases(void)
{
    (void)setup_accounts();
    crux_access_session_t sessions[CRUX_ACCESS_SESSIONS_PER_ACCOUNT];
    for (size_t index = 0; index < CRUX_ACCESS_SESSIONS_PER_ACCOUNT; ++index) {
        sessions[index] = access_test_session(USER, PASSWORD, &access_test_web);
    }
    /* The clock has not moved, so age alone cannot choose: the oldest is the earliest created. */
    crux_access_session_t next = access_test_session(USER, PASSWORD, &access_test_web);
    CHECK(crux_access_check(sessions[0], "status.read") == CRUX_ACCESS_ERR_SESSION_INVALID);
    for (size_t index = 1; index < CRUX_ACCESS_SESSIONS_PER_ACCOUNT; ++index) {
        CHECK(crux_access_check(sessions[index], "status.read") == CRUX_ACCESS_OK);
    }
    CHECK(crux_access_check(next, "status.read") == CRUX_ACCESS_OK);
}

static void exhaustion_cases(void)
{
    crux_access_session_t admin = setup_accounts();
    crux_access_session_t none = {0};
    const char *const fillers[] = {USER, "carol", "dave"};

    /* The admin holds the reserved serial slot. Three accounts fill the seven network slots. */
    crux_access_session_t network[7];
    for (size_t index = 0; index < 7; ++index) {
        network[index] = access_test_session(fillers[index % 3], PASSWORD, &access_test_web);
    }
    access_fake_derive_counters_clear();
    CHECK(access_test_login(USER, PASSWORD, &access_test_web, &none) ==
          CRUX_ACCESS_ERR_NO_RESOURCES);
    CHECK(access_test_login(ADMIN, PASSWORD, &access_test_ssh, &none) ==
          CRUX_ACCESS_ERR_NO_RESOURCES);
    CHECK(access_fake_derive_count() == 0);
    const uint8_t key[] = ACCESS_TEST_ED25519_KEY(1);
    CHECK(crux_access_account_add_key(admin, USER, key, sizeof(key)) == CRUX_ACCESS_OK);
    /* A failed reservation must not hold the verification slot. */
    CHECK(crux_access_login_verified(USER, key, sizeof(key), &access_test_ssh, &none) ==
          CRUX_ACCESS_ERR_NO_RESOURCES);
    CHECK(crux_access_check(network[1], "status.read") == CRUX_ACCESS_OK);

    /* Network logins can never take the reserved slot, so serial keeps a way in. */
    crux_access_logout(&admin);
    crux_access_session_t serial = access_test_session(ADMIN, PASSWORD, &access_test_serial);
    CHECK(crux_access_check(serial, CRUX_ACCESS_PERMISSION_MANAGE) == CRUX_ACCESS_OK);

    /* A logout frees a slot, and the login that follows works. */
    crux_access_logout(&network[2]);
    (void)access_test_session(ADMIN, PASSWORD, &access_test_web);
    CHECK(access_test_login(USER, PASSWORD, &access_test_web, &none) ==
          CRUX_ACCESS_ERR_NO_RESOURCES);

    /* Expired sessions cannot exhaust the table: a login reclaims their slots, with their events.
     */
    access_fake_clock_advance((uint64_t)reference()->session_idle_limit_s * 1000u);
    access_fake_events_clear();
    crux_access_session_t after = access_test_session(ADMIN, PASSWORD, &access_test_web);
    CHECK(crux_access_check(after, CRUX_ACCESS_PERMISSION_MANAGE) == CRUX_ACCESS_OK);
    CHECK(access_fake_event_count_of(CRUX_ACCESS_EVENT_SESSION_EXPIRED) >= 7);
    /* The old handles are gone. */
    CHECK(crux_access_check(serial, CRUX_ACCESS_PERMISSION_MANAGE) ==
          CRUX_ACCESS_ERR_SESSION_INVALID);
    CHECK(crux_access_check(network[0], "status.read") == CRUX_ACCESS_ERR_SESSION_INVALID);
}

static void store_state_cases(void)
{
    /* UNUSABLE: init reports it, logins are refused, and provisioning stays closed. */
    access_fake_reset();
    crux_access_test_reset();
    access_fake_store_state(CRUX_ACCESS_STORE_UNUSABLE);
    CHECK(crux_access_init(reference()) == CRUX_ACCESS_ERR_NOT_READY);
    crux_access_session_t session = {0};
    CHECK(access_test_login(ADMIN, PASSWORD, &access_test_web, &session) ==
          CRUX_ACCESS_ERR_NOT_READY);
    CHECK(access_test_login(ADMIN, PASSWORD, &access_test_serial, &session) ==
          CRUX_ACCESS_ERR_NOT_READY);
    CHECK(access_fake_derive_count() == 0);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, strlen(PASSWORD), "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_DENIED);

    /* A blank medium inserted while running reads as EMPTY, and must not reopen provisioning. */
    access_fake_store_state(CRUX_ACCESS_STORE_EMPTY);
    CHECK(crux_access_init(reference()) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, strlen(PASSWORD), "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_DENIED);
    CHECK(access_fake_store_saves() == 0);

    /* A later boot from a blank medium does open it: this is the accepted limit A7. */
    access_test_power_cycle(reference());
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, strlen(PASSWORD), "administrator",
                                              &access_test_serial) == CRUX_ACCESS_OK);

    /* A store that fails after a good load: sessions continue, and changes report the failure. */
    access_test_power_cycle(reference());
    crux_access_session_t admin = access_test_session(ADMIN, PASSWORD, &access_test_web);
    access_fake_store_save_mode(ACCESS_FAKE_SAVE_FAIL);
    access_fake_store_state(CRUX_ACCESS_STORE_UNUSABLE);
    CHECK(crux_access_check(admin, CRUX_ACCESS_PERMISSION_MANAGE) == CRUX_ACCESS_OK);
    CHECK(crux_access_account_create(admin, USER, "viewer", PASSWORD, strlen(PASSWORD)) ==
          CRUX_ACCESS_ERR_STORE);
    (void)access_test_session(ADMIN, PASSWORD, &access_test_web);
}

static void expect_record_unusable(const uint8_t *record, size_t length)
{
    access_fake_reset();
    crux_access_test_reset();
    access_fake_store_set_record(record, length);
    CHECK(crux_access_init(reference()) == CRUX_ACCESS_ERR_NOT_READY);
    crux_access_session_t session = {0};
    CHECK(access_test_login(ADMIN, PASSWORD, &access_test_serial, &session) ==
          CRUX_ACCESS_ERR_NOT_READY);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, strlen(PASSWORD), "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_DENIED);
}

/* Appends one length-prefixed SSH string. */
static size_t put_ssh_string(uint8_t *out, const void *text, size_t length)
{
    out[0] = 0;
    out[1] = 0;
    out[2] = (uint8_t)(length >> 8);
    out[3] = (uint8_t)length;
    memcpy(&out[4], text, length);
    return 4u + length;
}

/* A well-formed ECDSA blob of the named type, with an uncompressed point of the given size. */
static size_t ecdsa_blob_of(uint8_t *blob, const char *type, size_t point_size, const char *curve)
{
    uint8_t point[CRUX_ACCESS_KEY_SIZE_MAX];
    memset(point, 0x42, sizeof(point));
    point[0] = 4;
    size_t used = put_ssh_string(blob, type, strlen(type));
    used += put_ssh_string(&blob[used], curve, strlen(curve));
    used += put_ssh_string(&blob[used], point, point_size);
    return used;
}

/* The record the key is last in: the single account of `good`, with `key` in place of its key. */
static size_t record_with_key(const uint8_t *good, size_t key_length_at, const uint8_t *key,
                              size_t key_length, uint8_t *record)
{
    memcpy(record, good, key_length_at);
    record[key_length_at] = (uint8_t)key_length;
    record[key_length_at + 1u] = (uint8_t)(key_length >> 8);
    memcpy(&record[key_length_at + 2u], key, key_length);
    return key_length_at + 2u + key_length;
}

/* A store that an earlier revision saved can hold a P-384 or P-521 key, which is no longer a type
 * Access accepts (#316). A record that holds one in an otherwise good shape loads. */
static void legacy_key_type_cases(const uint8_t *good, size_t key_length_at)
{
    uint8_t blob[CRUX_ACCESS_KEY_SIZE_MAX];
    uint8_t record[CRUX_ACCESS_RECORD_SIZE_MAX];
    const struct {
        const char *type;
        size_t point_size;
        const char *curve;
    } types[] = {
        {"ecdsa-sha2-nistp256", 65, "nistp256"},
        {"ecdsa-sha2-nistp384", 97, "nistp384"},
        {"ecdsa-sha2-nistp521", 133, "nistp521"},
    };
    for (size_t index = 0; index < sizeof(types) / sizeof(types[0]); ++index) {
        size_t used =
            ecdsa_blob_of(blob, types[index].type, types[index].point_size, types[index].curve);
        size_t length = record_with_key(good, key_length_at, blob, used, record);
        access_fake_reset();
        crux_access_test_reset();
        access_fake_store_set_record(record, length);
        CHECK(crux_access_init(reference()) == CRUX_ACCESS_OK);
        (void)access_test_session(ADMIN, PASSWORD, &access_test_serial);
    }
}

/* --- A stored user key of a type this build does not support --- */

/* The table that the fixtures below start from, as the core saved it, and the one each fixture
 * edits. Static: each is about 4 KB. */
static access_table_t fixture_table;
static access_table_t fixture_edit;

static void put_be32(uint8_t *out, size_t value)
{
    out[0] = (uint8_t)(value >> 24);
    out[1] = (uint8_t)(value >> 16);
    out[2] = (uint8_t)(value >> 8);
    out[3] = (uint8_t)value;
}

/* A blob whose type string claims `claimed` bytes and holds `type`, followed by `data`. */
static size_t blob_raw(uint8_t *blob, size_t claimed, const char *type, size_t type_length,
                       const uint8_t *data, size_t data_length)
{
    put_be32(blob, claimed);
    memcpy(&blob[4], type, type_length);
    memcpy(&blob[4u + type_length], data, data_length);
    return 4u + type_length + data_length;
}

/* A well-formed blob of the named type: the type string, then one string of opaque key data. */
static size_t blob_of_type(uint8_t *blob, const char *type)
{
    static const uint8_t data[] = {0, 0, 0, 3, 1, 0, 1};
    return blob_raw(blob, strlen(type), type, strlen(type), data, sizeof(data));
}

/* Boots with ACCESS_TEST_ADMIN and ACCESS_TEST_USER, each holding one Ed25519 key, and keeps that
 * table for the fixtures. */
static void fixture_prepare(void)
{
    access_test_boot_with_admin();
    crux_access_session_t admin = access_test_session(ADMIN, PASSWORD, &access_test_serial);
    access_test_create_user(admin);
    const uint8_t admin_key[] = ACCESS_TEST_ED25519_KEY(1);
    const uint8_t user_key[] = ACCESS_TEST_ED25519_KEY(2);
    CHECK(crux_access_account_add_key(admin, ADMIN, admin_key, sizeof(admin_key)) ==
          CRUX_ACCESS_OK);
    CHECK(crux_access_account_add_key(admin, USER, user_key, sizeof(user_key)) == CRUX_ACCESS_OK);
    fixture_table = crux_access_state.table;
}

/* The saved fixture with `extra` as ACCESS_TEST_USER's second key. */
static size_t fixture_record(const uint8_t *extra, size_t extra_length, uint8_t *record)
{
    access_table_t *table = &fixture_edit;
    *table = fixture_table;
    access_account_t *account = crux_access_table_find(table, USER, NULL);
    CHECK(account != NULL && account->key_count == 1);
    account->keys[1].length = extra_length;
    memcpy(account->keys[1].bytes, extra, extra_length);
    account->key_count = 2;
    size_t length = crux_access_record_encode(table, record, CRUX_ACCESS_RECORD_SIZE_MAX);
    crux_access_secure_zero(table, sizeof(*table));
    CHECK(length != 0);
    return length;
}

static crux_access_result_t boot_from(const uint8_t *record, size_t length)
{
    access_fake_reset();
    crux_access_test_reset();
    access_fake_store_set_record(record, length);
    return crux_access_init(reference());
}

static bool bytes_contain(const uint8_t *haystack, size_t length, const uint8_t *needle,
                          size_t needle_length)
{
    for (size_t at = 0; at + needle_length <= length; ++at) {
        if (memcmp(&haystack[at], needle, needle_length) == 0) {
            return true;
        }
    }
    return false;
}

static bool stored_record_contains(const uint8_t *needle, size_t needle_length)
{
    size_t length = 0;
    const uint8_t *stored = access_fake_store_record(&length);
    return bytes_contain(stored, length, needle, needle_length);
}

/* The skip report: one key failure per skipped key, with no channel and an INVALID_ARGUMENT
 * result, which no client attempt produces. */
static void expect_skips_reported(size_t skipped, const char *account)
{
    size_t found = 0;
    for (size_t index = 0; index < access_fake_event_count(); ++index) {
        const crux_access_event_t *event = access_fake_event(index);
        if (event->type == CRUX_ACCESS_EVENT_KEY_FAILURE) {
            ++found;
            CHECK(event->result == CRUX_ACCESS_ERR_INVALID_ARGUMENT);
            CHECK(event->origin.channel == 0);
            CHECK(event->origin.source_length == 0);
            CHECK(event->actor[0] == '\0');
            CHECK(strcmp(event->account, account) == 0);
        }
    }
    CHECK(found == skipped);
    CHECK(access_fake_event_count_of(CRUX_ACCESS_EVENT_NOT_READY) == 0);
}

/* Both accounts log in. Each listed Ed25519 key authenticates, and the skipped blob never does. */
static void expect_others_work(const uint8_t *skipped, size_t skipped_length)
{
    const uint8_t admin_key[] = ACCESS_TEST_ED25519_KEY(1);
    const uint8_t user_key[] = ACCESS_TEST_ED25519_KEY(2);
    crux_access_session_t session = {0};
    uint32_t retry = 0;
    (void)access_test_session(ADMIN, PASSWORD, &access_test_serial);
    (void)access_test_session(USER, PASSWORD, &access_test_web);
    CHECK(crux_access_key_is_authorised(ADMIN, admin_key, sizeof(admin_key), true, &access_test_ssh,
                                        &retry) == CRUX_ACCESS_OK);
    CHECK(crux_access_login_verified(ADMIN, admin_key, sizeof(admin_key), &access_test_ssh,
                                     &session) == CRUX_ACCESS_OK);
    CHECK(crux_access_key_is_authorised(USER, user_key, sizeof(user_key), true, &access_test_ssh,
                                        &retry) == CRUX_ACCESS_OK);
    CHECK(crux_access_login_verified(USER, user_key, sizeof(user_key), &access_test_ssh,
                                     &session) == CRUX_ACCESS_OK);
    CHECK(crux_access_key_is_authorised(USER, skipped, skipped_length, false, &access_test_ssh,
                                        &retry) == CRUX_ACCESS_ERR_DENIED);
    CHECK(crux_access_key_is_authorised(USER, skipped, skipped_length, true, &access_test_ssh,
                                        &retry) == CRUX_ACCESS_ERR_DENIED);
    session.value = 0;
    CHECK(crux_access_login_verified(USER, skipped, skipped_length, &access_test_ssh, &session) ==
          CRUX_ACCESS_ERR_DENIED);
    CHECK(session.value == 0);
}

/* A well-formed record whose only fault is a key type this build does not support loads: that key
 * is skipped and reported, and every other account and key works. */
static void unsupported_key_tolerated_cases(void)
{
    uint8_t blob[CRUX_ACCESS_KEY_SIZE_MAX];
    uint8_t record[CRUX_ACCESS_RECORD_SIZE_MAX];
    uint8_t blobs[6][CRUX_ACCESS_KEY_SIZE_MAX];
    size_t sizes[6];
    char longest[65];
    memset(longest, 'a', 64);
    longest[64] = '\0';
    /* Stored by a revision before #316. */
    sizes[0] = ecdsa_blob_of(blobs[0], "ecdsa-sha2-nistp384", 97, "nistp384");
    sizes[1] = ecdsa_blob_of(blobs[1], "ecdsa-sha2-nistp521", 133, "nistp521");
    /* Never accepted, and well formed. */
    sizes[2] = blob_of_type(blobs[2], "ssh-rsa");
    /* A name with a domain part. */
    sizes[3] = blob_of_type(blobs[3], "sk-ssh-ed25519@openssh.com");
    /* The longest name RFC 4251 allows. */
    sizes[4] = blob_of_type(blobs[4], longest);
    /* A type name with no key data after it. */
    sizes[5] = blob_raw(blobs[5], 7, "ssh-dss", 7, blob, 0);
    fixture_prepare();
    for (size_t index = 0; index < sizeof(sizes) / sizeof(sizes[0]); ++index) {
        size_t used = sizes[index];
        memcpy(blob, blobs[index], used);
        size_t length = fixture_record(blob, used, record);
        CHECK(boot_from(record, length) == CRUX_ACCESS_OK);
        expect_skips_reported(1, USER);
        expect_others_work(blob, used);
        CHECK(crux_access_provision_first_account("other", PASSWORD, strlen(PASSWORD),
                                                  "administrator",
                                                  &access_test_serial) == CRUX_ACCESS_ERR_DENIED);
    }
}

/* Changes write the skipped key back unchanged, so a build that supports its type can use it. It
 * holds a key slot until it is removed by its exact bytes. */
static void unsupported_key_write_back_cases(void)
{
    uint8_t blob[CRUX_ACCESS_KEY_SIZE_MAX];
    uint8_t record[CRUX_ACCESS_RECORD_SIZE_MAX];
    fixture_prepare();
    size_t used = ecdsa_blob_of(blob, "ecdsa-sha2-nistp384", 97, "nistp384");
    size_t length = fixture_record(blob, used, record);
    CHECK(boot_from(record, length) == CRUX_ACCESS_OK);
    crux_access_session_t admin = access_test_session(ADMIN, PASSWORD, &access_test_serial);

    /* An unrelated change, and changes to the account that holds the key. */
    CHECK(crux_access_account_create(admin, "carol", "viewer", PASSWORD, strlen(PASSWORD)) ==
          CRUX_ACCESS_OK);
    CHECK(stored_record_contains(blob, used));
    CHECK(crux_access_account_set_role(admin, USER, "viewer") == CRUX_ACCESS_OK);
    CHECK(crux_access_account_disable(admin, USER) == CRUX_ACCESS_OK);
    CHECK(crux_access_account_enable(admin, USER) == CRUX_ACCESS_OK);
    CHECK(stored_record_contains(blob, used));

    /* The account lists both keys, and the skipped one fills the table. */
    crux_access_account_info_t accounts[CRUX_ACCESS_ACCOUNT_MAX];
    size_t count = 0;
    CHECK(crux_access_account_list(admin, accounts, CRUX_ACCESS_ACCOUNT_MAX, &count) ==
          CRUX_ACCESS_OK);
    CHECK(count == 3 && strcmp(accounts[1].user, USER) == 0 && accounts[1].key_count == 2);
    const uint8_t third[] = ACCESS_TEST_ED25519_KEY(3);
    CHECK(crux_access_account_add_key(admin, USER, third, sizeof(third)) ==
          CRUX_ACCESS_ERR_NO_RESOURCES);

    /* The saved record loads again with the same skip and the same working key. */
    access_fake_events_clear();
    access_test_power_cycle(reference());
    expect_skips_reported(1, USER);
    const uint8_t user_key[] = ACCESS_TEST_ED25519_KEY(2);
    uint32_t retry = 0;
    CHECK(crux_access_key_is_authorised(USER, user_key, sizeof(user_key), true, &access_test_ssh,
                                        &retry) == CRUX_ACCESS_OK);
    CHECK(crux_access_key_is_authorised(USER, blob, used, true, &access_test_ssh, &retry) ==
          CRUX_ACCESS_ERR_DENIED);

    /* Removing it by its exact bytes narrows access further, and frees the slot. */
    admin = access_test_session(ADMIN, PASSWORD, &access_test_serial);
    CHECK(crux_access_account_remove_key(admin, USER, blob, used) == CRUX_ACCESS_OK);
    CHECK(!stored_record_contains(blob, used));
    CHECK(crux_access_account_add_key(admin, USER, third, sizeof(third)) == CRUX_ACCESS_OK);
    access_fake_events_clear();
    access_test_power_cycle(reference());
    expect_skips_reported(0, USER);
}

/* Anything other than a well-formed blob of an unsupported type still makes the record malformed:
 * a broken type string, a name RFC 4251 does not allow, or a supported type in a malformed form. */
static void unsupported_key_boundary_cases(void)
{
    uint8_t blob[CRUX_ACCESS_KEY_SIZE_MAX];
    uint8_t record[CRUX_ACCESS_RECORD_SIZE_MAX];
    static const uint8_t data[] = {0, 0, 0, 1, 0x42};
    char too_long[66];
    memset(too_long, 'a', 65);
    too_long[65] = '\0';
    fixture_prepare();

    const struct {
        size_t claimed;
        const char *type;
        size_t type_length;
    } broken[] = {
        {50, "ssh-x", 5},                /* The type string runs past the blob. */
        {0, "", 0},                      /* An empty type name. */
        {7, "ssh rsa", 7},               /* A space. */
        {7, "ssh,rsa", 7},               /* A comma. */
        {7, "ssh\x7frsa", 7},            /* DEL. */
        {7, "ssh\x01rsa", 7},            /* A control character. */
        {7, "ssh\x80rsa", 7},            /* Not US-ASCII. */
        {7, "ssh\0rsa", 7},              /* An embedded NUL. */
        {65, too_long, 65},              /* Longer than 64 characters. */
        {11, "ssh-ed25519", 11},         /* A supported type: needs a 32-byte point. */
        {19, "ecdsa-sha2-nistp256", 19}, /* A supported type: needs a curve and a point. */
    };
    for (size_t index = 0; index < sizeof(broken) / sizeof(broken[0]); ++index) {
        size_t used = blob_raw(blob, broken[index].claimed, broken[index].type,
                               broken[index].type_length, data, sizeof(data));
        expect_record_unusable(record, fixture_record(blob, used, record));
    }

    /* Too short to hold a type string at all. */
    const uint8_t stub[] = {0, 0, 0};
    expect_record_unusable(record, fixture_record(stub, sizeof(stub), record));

    /* Supported types in a malformed form are not skipped. */
    size_t used = ecdsa_blob_of(blob, "ecdsa-sha2-nistp256", 65, "nistp384");
    expect_record_unusable(record, fixture_record(blob, used, record));
    used = ecdsa_blob_of(blob, "ecdsa-sha2-nistp256", 64, "nistp256");
    expect_record_unusable(record, fixture_record(blob, used, record));
    used = ecdsa_blob_of(blob, "ecdsa-sha2-nistp256", 65, "nistp256");
    blob[used - 65u] = 0x02; /* A compressed point. */
    expect_record_unusable(record, fixture_record(blob, used, record));
    const uint8_t ed25519[] = ACCESS_TEST_ED25519_KEY(4);
    memcpy(blob, ed25519, sizeof(ed25519));
    blob[sizeof(ed25519)] = 0;
    expect_record_unusable(record, fixture_record(blob, sizeof(ed25519) + 1u, record));
    expect_record_unusable(record, fixture_record(blob, sizeof(ed25519) - 1u, record));
}

/* The store promises to detect corruption, and this layer does not rely on that alone. */
static void malformed_record_cases(void)
{
    access_test_boot_with_admin();
    crux_access_session_t admin = access_test_session(ADMIN, PASSWORD, &access_test_serial);
    const uint8_t key[] = ACCESS_TEST_ED25519_KEY(1);
    CHECK(crux_access_account_add_key(admin, ADMIN, key, sizeof(key)) == CRUX_ACCESS_OK);
    size_t length = 0;
    const uint8_t *stored = access_fake_store_record(&length);
    uint8_t good[CRUX_ACCESS_RECORD_SIZE_MAX];
    memcpy(good, stored, length);

    /* Every truncation. */
    for (size_t cut = 0; cut < length; ++cut) {
        expect_record_unusable(good, cut);
    }
    /* Trailing bytes. */
    uint8_t mutated[CRUX_ACCESS_RECORD_SIZE_MAX];
    memcpy(mutated, good, length);
    mutated[length] = 0;
    expect_record_unusable(mutated, length + 1u);

    /* Field offsets, from access_record.c. */
    const size_t name_at = CRUX_ACCESS_RECORD_HEADER_SIZE;
    const size_t role_at = name_at + CRUX_ACCESS_NAME_SIZE;
    const size_t flags_at = role_at + CRUX_ACCESS_NAME_SIZE;
    const size_t algorithm_at = flags_at + 1u;
    const size_t key_count_at = algorithm_at + 1u;
    const size_t iterations_at = key_count_at + 1u;
    const size_t key_length_at =
        iterations_at + 4u + CRUX_ACCESS_SALT_SIZE + CRUX_ACCESS_DERIVED_SIZE;
    const struct {
        size_t offset;
        uint8_t value;
    } corruptions[] = {
        {0, 2},                         /* A version this firmware does not know. */
        {2, 0},                         /* No accounts in a record that claims to be valid. */
        {2, 255},                       /* More accounts than the table holds. */
        {3, 1},                         /* Reserved byte. */
        {name_at, 0},                   /* Empty name. */
        {name_at, 'A'},                 /* Name outside the allowed characters. */
        {name_at + 31u, 'x'},           /* Unterminated name. */
        {role_at, 0},                   /* Empty role. */
        {role_at + 31u, 'x'},           /* Unterminated role. */
        {flags_at, 0xFF},               /* Unknown flags. */
        {algorithm_at, 99},             /* Unknown verifier algorithm. */
        {key_count_at, 200},            /* More keys than an account holds. */
        {iterations_at, 0},             /* Combined below with the rest of the zero count. */
        {key_length_at, 0},             /* Zero-length key. */
        {key_length_at + 1u, 0xFF},     /* Oversized key. */
        {key_length_at + 2u + 7u, ' '}, /* A key type name no SSH name can be. */
    };
    for (size_t index = 0; index < sizeof(corruptions) / sizeof(corruptions[0]); ++index) {
        memcpy(mutated, good, length);
        mutated[corruptions[index].offset] = corruptions[index].value;
        if (corruptions[index].offset == iterations_at) {
            memset(&mutated[iterations_at], 0, 4);
        }
        expect_record_unusable(mutated, length);
    }

    /* A valid name of a type this firmware does not support is not malformed: only that key is
     * skipped. Detecting a flipped bit that leaves a valid name is the store's integrity check. */
    memcpy(mutated, good, length);
    mutated[key_length_at + 2u + 7u] = 'x';
    access_fake_reset();
    crux_access_test_reset();
    access_fake_store_set_record(mutated, length);
    CHECK(crux_access_init(reference()) == CRUX_ACCESS_OK);
    CHECK(access_fake_event_count_of(CRUX_ACCESS_EVENT_KEY_FAILURE) == 1);
    (void)access_test_session(ADMIN, PASSWORD, &access_test_serial);

    /* A duplicate name, by copying the record's only account. */
    const size_t account_size = length - CRUX_ACCESS_RECORD_HEADER_SIZE;
    memcpy(mutated, good, length);
    memcpy(&mutated[length], &good[CRUX_ACCESS_RECORD_HEADER_SIZE], account_size);
    mutated[2] = 2;
    expect_record_unusable(mutated, length + account_size);

    /* The control: the record these were all made from loads. */
    access_fake_reset();
    crux_access_test_reset();
    access_fake_store_set_record(good, length);
    CHECK(crux_access_init(reference()) == CRUX_ACCESS_OK);

    CHECK(length < CRUX_ACCESS_RECORD_SIZE_MAX);
    legacy_key_type_cases(good, key_length_at);
}

/* --- 64-bit time --- */

static void time_limit_cases(void)
{
    const uint64_t near_end_ms = UINT64_MAX - 500u;
    access_test_boot_with_admin();
    access_fake_clock_set(near_end_ms);

    /* A window near the end of time saturates rather than wrapping into the past. */
    crux_access_session_t session = {0};
    uint32_t retry_after_ms = 0;
    crux_access_origin_t origin = access_test_web_from(1);
    for (unsigned attempt = 0; attempt < CRUX_ACCESS_DELAY_FREE_ATTEMPTS + 1u; ++attempt) {
        CHECK(access_test_login(ADMIN, WRONG, &origin, &session) == CRUX_ACCESS_ERR_DENIED);
    }
    CHECK(crux_access_login_password(ADMIN, PASSWORD, strlen(PASSWORD), &origin, &session,
                                     &retry_after_ms) == CRUX_ACCESS_ERR_RETRY_LATER);
    CHECK(retry_after_ms == 500);
    access_fake_clock_set(UINT64_MAX - 1u);
    CHECK(crux_access_login_password(ADMIN, PASSWORD, strlen(PASSWORD), &origin, &session,
                                     &retry_after_ms) == CRUX_ACCESS_ERR_RETRY_LATER);
    CHECK(retry_after_ms == 1);

    /* Sessions near the end of time: elapsed time is computed, never a deadline that could wrap. */
    access_test_boot_with_admin();
    const uint64_t idle_ms = (uint64_t)reference()->session_idle_limit_s * 1000u;
    access_fake_clock_set(UINT64_MAX - idle_ms - 5u);
    crux_access_session_t admin = access_test_session(ADMIN, PASSWORD, &access_test_web);
    access_fake_clock_advance(idle_ms - 1u);
    CHECK(crux_access_check(admin, CRUX_ACCESS_PERMISSION_MANAGE) == CRUX_ACCESS_OK);
    access_fake_clock_advance(1);
    CHECK(crux_access_check(admin, CRUX_ACCESS_PERMISSION_MANAGE) ==
          CRUX_ACCESS_ERR_SESSION_INVALID);

    /* A 32-bit millisecond counter would wrap after about 49 days. */
    access_test_boot_with_admin();
    const uint64_t beyond_32_bits_ms = (1ull << 32) + 1000u;
    access_fake_clock_set(beyond_32_bits_ms);
    admin = access_test_session(ADMIN, PASSWORD, &access_test_web);
    CHECK(crux_access_check(admin, CRUX_ACCESS_PERMISSION_MANAGE) == CRUX_ACCESS_OK);
    access_fake_clock_advance(idle_ms);
    CHECK(crux_access_check(admin, CRUX_ACCESS_PERMISSION_MANAGE) ==
          CRUX_ACCESS_ERR_SESSION_INVALID);

    /* A clock that runs backwards expires a session, and never clears delay state. */
    access_test_boot_with_admin();
    access_fake_clock_set(1000000);
    admin = access_test_session(ADMIN, PASSWORD, &access_test_web);
    origin = access_test_web_from(2);
    for (unsigned attempt = 0; attempt < CRUX_ACCESS_DELAY_FREE_ATTEMPTS + 1u; ++attempt) {
        CHECK(access_test_login(ADMIN, WRONG, &origin, &session) == CRUX_ACCESS_ERR_DENIED);
    }
    access_fake_clock_set(500000);
    CHECK(crux_access_check(admin, CRUX_ACCESS_PERMISSION_MANAGE) ==
          CRUX_ACCESS_ERR_SESSION_INVALID);
    CHECK(crux_access_login_password(ADMIN, PASSWORD, strlen(PASSWORD), &origin, &session,
                                     &retry_after_ms) == CRUX_ACCESS_ERR_RETRY_LATER);
    CHECK(retry_after_ms == CRUX_ACCESS_DELAY_CAP_MS);
}

/* --- Provider failures --- */

static void provider_failure_cases(void)
{
    access_test_boot_with_admin();
    crux_access_session_t session = {0};
    uint32_t retry_after_ms = 0;
    const uint8_t key[] = ACCESS_TEST_ED25519_KEY(1);

    /* A hash failure refuses the attempt, before anything is verified. */
    access_fake_hmac_fail(true);
    access_fake_derive_counters_clear();
    CHECK(access_test_login(ADMIN, PASSWORD, &access_test_web, &session) ==
          CRUX_ACCESS_ERR_NOT_READY);
    CHECK(access_fake_derive_count() == 0);
    CHECK(crux_access_key_is_authorised(ADMIN, key, sizeof(key), true, &access_test_ssh,
                                        &retry_after_ms) == CRUX_ACCESS_ERR_NOT_READY);
    crux_access_report_key_failure(ADMIN, &access_test_ssh);
    access_fake_hmac_fail(false);
    (void)access_test_session(ADMIN, PASSWORD, &access_test_web);

    /* A derive failure never produces a session, and is no guess: nothing counts. */
    access_fake_derive_fail(true);
    for (unsigned attempt = 0; attempt < 20; ++attempt) {
        CHECK(access_test_login(ADMIN, PASSWORD, &access_test_web_other, &session) ==
              CRUX_ACCESS_ERR_NOT_READY);
        CHECK(session.value == 0);
    }
    access_fake_derive_fail(false);
    (void)access_test_session(ADMIN, PASSWORD, &access_test_web_other);

    /* Setting a password fails the same way, and changes nothing. */
    crux_access_session_t admin = access_test_session(ADMIN, PASSWORD, &access_test_web);
    unsigned saves = access_fake_store_saves();
    access_fake_derive_fail(true);
    CHECK(crux_access_account_create(admin, USER, "viewer", PASSWORD, strlen(PASSWORD)) ==
          CRUX_ACCESS_ERR_NOT_READY);
    CHECK(crux_access_account_reset_password(admin, ADMIN, PASSWORD, strlen(PASSWORD)) ==
          CRUX_ACCESS_ERR_NOT_READY);
    access_fake_derive_fail(false);
    access_fake_random_fail(true);
    CHECK(crux_access_account_create(admin, USER, "viewer", PASSWORD, strlen(PASSWORD)) ==
          CRUX_ACCESS_ERR_NOT_READY);
    access_fake_random_fail(false);
    CHECK(access_fake_store_saves() == saves);

    /* Verifying the current password fails closed too. */
    access_fake_derive_fail(true);
    CHECK(crux_access_account_change_password(admin, PASSWORD, strlen(PASSWORD),
                                              "new long password", 17,
                                              &retry_after_ms) == CRUX_ACCESS_ERR_NOT_READY);
    access_fake_derive_fail(false);
    CHECK(crux_access_check(admin, CRUX_ACCESS_PERMISSION_MANAGE) == CRUX_ACCESS_OK);

    /* Provisioning fails closed and stays open. */
    access_test_boot(reference());
    access_fake_derive_fail(true);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, strlen(PASSWORD), "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_NOT_READY);
    access_fake_derive_fail(false);
    access_fake_random_fail(true);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, strlen(PASSWORD), "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_NOT_READY);
    access_fake_random_fail(false);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, strlen(PASSWORD), "administrator",
                                              &access_test_serial) == CRUX_ACCESS_OK);
}

/* --- A lock that cannot be taken: linked with --wrap=crux_mutex_lock. --- */

static bool fail_locks;
static unsigned
    fail_lock_countdown; /* When nonzero, fails only the lock this many calls from now. */
/* The linker's --wrap option fixes these names. */
// NOLINTNEXTLINE(bugprone-reserved-identifier)
crux_status_t __real_crux_mutex_lock(crux_mutex_t mutex, uint32_t timeout_ms);
// NOLINTNEXTLINE(bugprone-reserved-identifier)
crux_status_t __wrap_crux_mutex_lock(crux_mutex_t mutex, uint32_t timeout_ms);

// NOLINTNEXTLINE(bugprone-reserved-identifier)
crux_status_t __wrap_crux_mutex_lock(crux_mutex_t mutex, uint32_t timeout_ms)
{
    if (fail_lock_countdown > 0) {
        fail_lock_countdown -= 1;
        if (fail_lock_countdown == 0) {
            return CRUX_ERR_IO;
        }
    }
    return fail_locks ? CRUX_ERR_IO : __real_crux_mutex_lock(mutex, timeout_ms);
}

static void lock_failure_cases(void)
{
    access_test_boot_with_admin();
    crux_access_session_t admin = access_test_session(ADMIN, PASSWORD, &access_test_web);
    const uint8_t key[] = ACCESS_TEST_ED25519_KEY(1);
    uint32_t retry_after_ms = 0;
    char name[CRUX_ACCESS_NAME_SIZE];
    bool required = false;
    size_t count = 0;
    crux_access_session_t session = {0};

    access_fake_events_clear();
    fail_locks = true;
    CHECK(crux_access_check(admin, CRUX_ACCESS_PERMISSION_MANAGE) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(crux_access_session_user(admin, name, sizeof(name)) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(crux_access_session_role(admin, name, sizeof(name)) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(crux_access_session_must_change_password(admin, &required) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(crux_access_touch(admin) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(access_test_login(ADMIN, PASSWORD, &access_test_web, &session) ==
          CRUX_ACCESS_ERR_NOT_READY);
    CHECK(session.value == 0);
    CHECK(crux_access_key_is_authorised(ADMIN, key, sizeof(key), true, &access_test_ssh,
                                        &retry_after_ms) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(crux_access_login_verified(ADMIN, key, sizeof(key), &access_test_ssh, &session) ==
          CRUX_ACCESS_ERR_NOT_READY);
    CHECK(crux_access_account_list(admin, NULL, 0, &count) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(crux_access_account_disable(admin, ADMIN) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(crux_access_account_create(admin, USER, "viewer", PASSWORD, strlen(PASSWORD)) ==
          CRUX_ACCESS_ERR_NOT_READY);
    crux_access_report_key_failure(ADMIN, &access_test_ssh);
    crux_access_session_t ended = admin;
    crux_access_logout(&ended);
    CHECK(ended.value == 0);
    bool permitted = false;
    uint8_t channel = 0, source[16], source_length = 0;
    CHECK(crux_access_permitted(admin, "status.read", &permitted) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(crux_access_session_origin(admin, &channel, source, &source_length) ==
          CRUX_ACCESS_ERR_NOT_READY);
    fail_locks = false;
    /* A lost lock means a call from the wrong context, where the event port cannot run either. */
    CHECK(access_fake_event_count() == 0);
    CHECK(crux_access_check(admin, CRUX_ACCESS_PERMISSION_MANAGE) == CRUX_ACCESS_OK);

    /* A reset that loses its second lock does not report the account as missing. */
    fail_lock_countdown = 2;
    CHECK(crux_access_account_reset_password(admin, ADMIN, PASSWORD, strlen(PASSWORD)) ==
          CRUX_ACCESS_ERR_NOT_READY);
    CHECK(fail_lock_countdown == 0);
    CHECK(access_fake_event_count() == 0);
}

static void hook_fail_locks(void *context)
{
    (void)context;
    fail_locks = true;
}

static void hook_fail_next_lock(void *context)
{
    (void)context;
    fail_lock_countdown = 1;
}

static void hook_fail_second_lock(void *context)
{
    (void)context;
    fail_lock_countdown = 2;
}

/* A lost lock around the first account's save must not leave provisioning open, or a retry could
 * replace what the medium already holds. */
static void provisioning_fails_closed_on_lock_failure(void)
{
    const crux_access_policy_t *policy = &access_test_profile_reference.policy;
    const size_t length = strlen(PASSWORD);
    crux_access_session_t session = {0};

    /* A lock lost before provisioning closes saves nothing, reports no refusal and can be retried:
     * from the first call, then at the change lock, then at the step that closes it. */
    access_test_boot(policy);
    fail_locks = true;
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, length, "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_NOT_READY);
    fail_locks = false;
    access_fake_derive_hook(hook_fail_next_lock, NULL);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, length, "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(fail_lock_countdown == 0);
    access_fake_derive_hook(hook_fail_second_lock, NULL);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, length, "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(fail_lock_countdown == 0);
    CHECK(access_fake_store_saves() == 0);
    CHECK(access_fake_event_count() == 0);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, length, "administrator",
                                              &access_test_serial) == CRUX_ACCESS_OK);

    /* The save completes, and the lock to apply it fails. */
    access_test_boot(policy);
    access_fake_store_save_hook(hook_fail_locks, NULL);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, length, "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_NOT_READY);
    fail_locks = false;
    size_t stored_length = 0;
    uint8_t stored[CRUX_ACCESS_RECORD_SIZE_MAX];
    memcpy(stored, access_fake_store_record(&stored_length), sizeof(stored));
    CHECK(access_fake_store_saves() == 1);
    CHECK(crux_access_provision_first_account(USER, PASSWORD, length, "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_DENIED);
    CHECK(access_fake_store_saves() == 1);
    size_t after_length = 0;
    CHECK(memcmp(stored, access_fake_store_record(&after_length), sizeof(stored)) == 0);
    CHECK(after_length == stored_length);
    /* RAM stays behind the medium until a reset, so nobody can log in meanwhile. */
    CHECK(access_test_login(ADMIN, PASSWORD, &access_test_web, &session) == CRUX_ACCESS_ERR_DENIED);
    access_test_power_cycle(policy);
    CHECK(crux_access_provision_first_account(USER, PASSWORD, length, "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_DENIED);
    session = access_test_session(ADMIN, PASSWORD, &access_test_web);
    CHECK(session.value != 0);

    /* The same when only that one lock fails, so that a later lock could have reopened it. */
    access_test_boot(policy);
    access_fake_store_save_hook(hook_fail_next_lock, NULL);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, length, "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(fail_lock_countdown == 0);
    CHECK(crux_access_provision_first_account(USER, PASSWORD, length, "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_DENIED);
    CHECK(access_fake_store_saves() == 1);
    access_test_power_cycle(policy);
    session = access_test_session(ADMIN, PASSWORD, &access_test_web);
    CHECK(session.value != 0);

    /* The save fails, and the lock to reopen provisioning fails. A reset finds the medium empty. */
    access_test_boot(policy);
    access_fake_store_save_mode(ACCESS_FAKE_SAVE_FAIL);
    access_fake_store_save_hook(hook_fail_locks, NULL);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, length, "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_NOT_READY);
    fail_locks = false;
    access_fake_store_save_mode(ACCESS_FAKE_SAVE_OK);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, length, "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_DENIED);
    access_test_power_cycle(policy);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, length, "administrator",
                                              &access_test_serial) == CRUX_ACCESS_OK);

    /* A failed save with the lock intact can still be retried. */
    access_test_boot(policy);
    access_fake_store_save_mode(ACCESS_FAKE_SAVE_FAIL);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, length, "administrator",
                                              &access_test_serial) == CRUX_ACCESS_ERR_STORE);
    access_fake_store_save_mode(ACCESS_FAKE_SAVE_OK);
    CHECK(crux_access_provision_first_account(ADMIN, PASSWORD, length, "administrator",
                                              &access_test_serial) == CRUX_ACCESS_OK);
}

/* --- Concurrent logins, for the sanitizers to watch. --- */

typedef struct {
    uint32_t seed;
    unsigned ok;
    unsigned denied;
    unsigned other;
} login_worker_t;

static void *login_worker(void *context)
{
    login_worker_t *worker = context;
    for (uint32_t round = 0; round < 400; ++round) {
        crux_access_session_t session = {0};
        uint32_t retry_after_ms = 0;
        crux_access_origin_t origin = access_test_web_from(worker->seed * 1000u + round);
        if (worker->seed % 2u == 0u) {
            origin.channel = CRUX_ACCESS_CHANNEL_SSH;
        }
        bool right = round % 2u == 0u;
        const char *password = right ? PASSWORD : WRONG;
        crux_access_result_t result = crux_access_login_password(
            USER, password, strlen(password), &origin, &session, &retry_after_ms);
        if (result == CRUX_ACCESS_OK) {
            worker->ok += 1;
            if (crux_access_check(session, "status.read") == CRUX_ACCESS_OK) {
                (void)crux_access_touch(session);
            }
            crux_access_logout(&session);
        } else if (result == CRUX_ACCESS_ERR_DENIED) {
            worker->denied += 1;
        } else {
            worker->other += 1;
            if (result != CRUX_ACCESS_ERR_BUSY && result != CRUX_ACCESS_ERR_RETRY_LATER &&
                result != CRUX_ACCESS_ERR_NO_RESOURCES) {
                CHECK(result == CRUX_ACCESS_ERR_BUSY);
            }
        }
    }
    return NULL;
}

typedef struct {
    crux_access_session_t admin;
    atomic_bool stop;
    unsigned changes;
} change_worker_t;

static void *change_worker(void *context)
{
    change_worker_t *worker = context;
    do {
        /* Changes that do not affect the worker's own session. */
        if (crux_access_account_disable(worker->admin, "carol") == CRUX_ACCESS_OK &&
            crux_access_account_enable(worker->admin, "carol") == CRUX_ACCESS_OK) {
            worker->changes += 1;
        }
        const uint8_t key[] = ACCESS_TEST_ED25519_KEY(1);
        (void)crux_access_account_add_key(worker->admin, USER, key, sizeof(key));
        (void)crux_access_account_remove_key(worker->admin, USER, key, sizeof(key));
    } while (!atomic_load(&worker->stop));
    return NULL;
}

static void concurrent_login_cases(void)
{
    crux_access_session_t admin = setup_accounts();
    enum { WORKERS = 4 };
    login_worker_t workers[WORKERS];
    pthread_t threads[WORKERS];
    change_worker_t changer = {.admin = admin};
    pthread_t changer_thread;
    CHECK(pthread_create(&changer_thread, NULL, change_worker, &changer) == 0);
    for (uint32_t index = 0; index < WORKERS; ++index) {
        workers[index] = (login_worker_t){index + 1u, 0, 0, 0};
        CHECK(pthread_create(&threads[index], NULL, login_worker, &workers[index]) == 0);
    }
    unsigned ok = 0;
    for (uint32_t index = 0; index < WORKERS; ++index) {
        CHECK(pthread_join(threads[index], NULL) == 0);
        ok += workers[index].ok;
    }
    atomic_store(&changer.stop, true);
    CHECK(pthread_join(changer_thread, NULL) == 0);
    CHECK(changer.changes > 0);
    CHECK(ok > 0);
    /* Every slot and verification claim was released, once the delay state has decayed. */
    access_fake_clock_advance(CRUX_ACCESS_DELAY_QUIET_MS);
    crux_access_session_t session = access_test_session(USER, PASSWORD, &access_test_web_other);
    CHECK(crux_access_check(session, "status.read") == CRUX_ACCESS_OK);
    printf("Concurrent logins: %u succeeded, %u changes applied\n", ok, changer.changes);
}

int main(void)
{
    per_account_cap_cases();
    exhaustion_cases();
    store_state_cases();
    malformed_record_cases();
    unsupported_key_tolerated_cases();
    unsupported_key_write_back_cases();
    unsupported_key_boundary_cases();
    time_limit_cases();
    provider_failure_cases();
    lock_failure_cases();
    provisioning_fails_closed_on_lock_failure();
    concurrent_login_cases();
    return access_test_finish("Access faults");
}
