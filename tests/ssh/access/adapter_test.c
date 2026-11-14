/*
 * The access entry points of #192 on the real crux_access core with its fake ports. It holds the
 * mapping that docs/ssh-provider-contract.md records. It shows no SSH protocol behaviour: that is
 * for the provider on native_sim.
 */
#include "access_test.h"
#include "crux_ssh_access.h"
#include "crux_ssh_attachment.h"
#include "crux_ssh_callbacks.h"
#include "ssh_check.h"
#include "ssh_port_fake.h"

#define USER "operator"

static const uint8_t ed25519_key[51] = {0,   0,   0,   11, 's', 's', 'h', '-', 'e', 'd', '2', '5',
                                        '5', '1', '9', 0,  0,   0,   32,  1,   2,   3,   4};
static const uint8_t other_key[51] = {0,   0,   0,   11, 's', 's', 'h', '-', 'e', 'd', '2', '5',
                                      '5', '1', '9', 0,  0,   0,   32,  9,   8,   7,   6};
static const crux_ssh_peer_t peer = {.address = {192, 0, 2, 1}, .address_length = 4};
static const crux_ssh_peer_t other_peer = {.address = {192, 0, 2, 2}, .address_length = 4};
static const crux_access_origin_t serial_origin = {.channel = CRUX_ACCESS_CHANNEL_SERIAL};

static const uint8_t *password(void)
{
    return (const uint8_t *)ACCESS_TEST_PASSWORD;
}

static size_t password_length(void)
{
    return strlen(ACCESS_TEST_PASSWORD);
}

static void setup(void)
{
    crux_access_session_t session = {0};
    uint32_t retry_after_ms;

    crux_access_test_reset();
    access_fake_reset();
    SSH_CHECK(crux_access_init(&access_test_profile_reference.policy) == CRUX_ACCESS_OK);
    SSH_CHECK(crux_access_provision_first_account(USER, ACCESS_TEST_PASSWORD,
                                                  strlen(ACCESS_TEST_PASSWORD), "administrator",
                                                  &serial_origin) == CRUX_ACCESS_OK);
    SSH_CHECK(crux_access_login_password(USER, ACCESS_TEST_PASSWORD, strlen(ACCESS_TEST_PASSWORD),
                                         &serial_origin, &session,
                                         &retry_after_ms) == CRUX_ACCESS_OK);
    SSH_CHECK(crux_access_account_add_key(session, USER, ed25519_key, sizeof(ed25519_key)) ==
              CRUX_ACCESS_OK);
    crux_access_logout(&session);
    access_fake_events_clear();
    access_fake_derive_counters_clear();
}

static crux_ssh_attachment_t *login(const crux_ssh_peer_t *from)
{
    crux_ssh_attachment_t *attachment = NULL;

    SSH_CHECK(crux_ssh_access_password(NULL, from, USER, password(), password_length(),
                                       &attachment) == CRUX_SSH_AUTH_ACCEPTED);
    SSH_CHECK(attachment != NULL);
    return attachment;
}

static void test_password_login_holds_a_session_of_the_ssh_channel(void)
{
    crux_ssh_attachment_t *attachment;
    crux_access_session_t session;
    char name[CRUX_ACCESS_NAME_SIZE] = {0};
    uint8_t channel = 0;
    uint8_t source[16] = {0};
    uint8_t source_length = 0;

    setup();
    attachment = login(&peer);
    session = crux_ssh_attachment_session(attachment);
    SSH_CHECK(session.value != 0u);
    SSH_CHECK(crux_access_session_user(session, name, sizeof(name)) == CRUX_ACCESS_OK);
    SSH_CHECK(strcmp(name, USER) == 0);
    SSH_CHECK(crux_access_session_origin(session, &channel, source, &source_length) ==
              CRUX_ACCESS_OK);
    SSH_CHECK(channel == (uint8_t)CRUX_ACCESS_CHANNEL_SSH);
    SSH_CHECK(source_length == 4u);
    SSH_CHECK(memcmp(source, peer.address, 4) == 0);
    SSH_CHECK(crux_ssh_access_session_alive(NULL, attachment));

    /* The end of the connection ends the session, and its reference is no use afterwards. */
    crux_ssh_access_connection_closed(NULL, attachment);
    SSH_CHECK(crux_access_session_user(session, name, sizeof(name)) ==
              CRUX_ACCESS_ERR_SESSION_INVALID);
}

static void test_every_refusal_is_a_denial_and_holds_no_slot(void)
{
    const uint8_t wrong[] = "not the password";
    crux_ssh_attachment_t *attachment = NULL;

    setup();
    /* Far more refusals than there are slots, from a new source each time so that none is delayed.
     */
    for (unsigned i = 0; i < 40u; ++i) {
        crux_ssh_peer_t from = {.address = {198, 51, 100, (uint8_t)i}, .address_length = 4};

        SSH_CHECK(crux_ssh_access_password(NULL, &from, "unknown", wrong, sizeof(wrong) - 1,
                                           &attachment) == CRUX_SSH_AUTH_DENIED);
        SSH_CHECK(attachment == NULL);
    }
    crux_ssh_access_connection_closed(NULL, login(&other_peer));
}

static void test_delay_is_a_denial_that_verifies_nothing(void)
{
    const uint8_t wrong[] = "not the password";
    crux_ssh_attachment_t *attachment = NULL;

    setup();
    for (unsigned i = 0; i <= CRUX_ACCESS_DELAY_FREE_ATTEMPTS; ++i) {
        SSH_CHECK(crux_ssh_access_password(NULL, &peer, USER, wrong, sizeof(wrong) - 1,
                                           &attachment) == CRUX_SSH_AUTH_DENIED);
    }
    SSH_CHECK(access_fake_derive_count() == CRUX_ACCESS_DELAY_FREE_ATTEMPTS + 1u);
    /* Inside the window, even the right password is refused, and nothing is derived. */
    SSH_CHECK(crux_ssh_access_password(NULL, &peer, USER, password(), password_length(),
                                       &attachment) == CRUX_SSH_AUTH_DENIED);
    SSH_CHECK(attachment == NULL);
    SSH_CHECK(access_fake_derive_count() == CRUX_ACCESS_DELAY_FREE_ATTEMPTS + 1u);
    SSH_CHECK(access_fake_event_count_of(CRUX_ACCESS_EVENT_DELAY_APPLIED) == 1u);

    access_fake_clock_advance(CRUX_ACCESS_DELAY_BASE_MS);
    crux_ssh_access_connection_closed(NULL, login(&peer));
}

static void busy_login(void *context)
{
    crux_ssh_attachment_t *attachment = NULL;

    (void)context;
    /* The first verification is running, so this one is refused at once rather than waiting. */
    SSH_CHECK(crux_ssh_access_password(NULL, &other_peer, USER, password(), password_length(),
                                       &attachment) == CRUX_SSH_AUTH_DENIED);
    SSH_CHECK(attachment == NULL);
}

static void test_busy_verification_is_a_denial(void)
{
    setup();
    access_fake_derive_hook(busy_login, NULL);
    crux_ssh_access_connection_closed(NULL, login(&peer));
    SSH_CHECK(access_fake_event_count_of(CRUX_ACCESS_EVENT_LOGIN_BUSY) == 1u);
}

static void test_session_replaced_by_the_account_cap_is_no_longer_alive(void)
{
    crux_ssh_attachment_t *held[CRUX_ACCESS_SESSIONS_PER_ACCOUNT] = {0};
    crux_ssh_attachment_t *attachment = NULL;

    setup();
    for (size_t i = 0; i < CRUX_ACCESS_SESSIONS_PER_ACCOUNT; ++i) {
        held[i] = login(&peer);
    }
    /* A fourth login replaces the account's oldest session, so the attachment stays a real one. */
    SSH_CHECK(crux_ssh_access_password(NULL, &peer, USER, password(), password_length(),
                                       &attachment) == CRUX_SSH_AUTH_ACCEPTED);
    SSH_CHECK(attachment != NULL);
    SSH_CHECK(!crux_ssh_access_session_alive(NULL, held[0]));
    SSH_CHECK(crux_ssh_access_session_alive(NULL, attachment));
    crux_ssh_access_connection_closed(NULL, attachment);
    for (size_t i = 0; i < CRUX_ACCESS_SESSIONS_PER_ACCOUNT; ++i) {
        crux_ssh_access_connection_closed(NULL, held[i]);
    }
    crux_ssh_access_connection_closed(NULL, login(&peer));
}

static void test_attachments_are_bounded(void)
{
    /* More logins than the pool holds. The account cap replaces sessions, so only the pool limits.
     */
    crux_ssh_attachment_t *held[CRUX_SSH_ACCESS_ATTACHMENT_MAX + 1u] = {0};
    size_t accepted = 0;

    setup();
    for (size_t i = 0; i < CRUX_SSH_ACCESS_ATTACHMENT_MAX + 1u; ++i) {
        if (crux_ssh_access_password(NULL, &peer, USER, password(), password_length(), &held[i]) ==
            CRUX_SSH_AUTH_ACCEPTED) {
            SSH_CHECK(held[i] != NULL);
            ++accepted;
        } else {
            SSH_CHECK(held[i] == NULL);
        }
    }
    SSH_CHECK(accepted == CRUX_SSH_ACCESS_ATTACHMENT_MAX);
    /* The refusal left no session behind. */
    SSH_CHECK(access_fake_event_count_of(CRUX_ACCESS_EVENT_LOGIN_SUCCESS) == accepted);
    for (size_t i = 0; i < accepted; ++i) {
        crux_ssh_access_connection_closed(NULL, held[i]);
    }
    crux_ssh_access_connection_closed(NULL, login(&peer));
}

static void test_key_check_creates_nothing(void)
{
    crux_ssh_attachment_t *attachment = NULL;

    setup();
    SSH_CHECK(crux_ssh_access_key_check(NULL, &peer, USER, CRUX_SSH_KEY_ED25519, ed25519_key,
                                        sizeof(ed25519_key), false) == CRUX_SSH_AUTH_ACCEPTED);
    SSH_CHECK(crux_ssh_access_key_check(NULL, &peer, USER, CRUX_SSH_KEY_ED25519, ed25519_key,
                                        sizeof(ed25519_key), true) == CRUX_SSH_AUTH_ACCEPTED);
    SSH_CHECK(access_fake_event_count_of(CRUX_ACCESS_EVENT_LOGIN_SUCCESS) == 0u);

    /* An unlisted key: a probe records nothing, and a signed request is a key failure. */
    SSH_CHECK(crux_ssh_access_key_check(NULL, &peer, USER, CRUX_SSH_KEY_ED25519, other_key,
                                        sizeof(other_key), false) == CRUX_SSH_AUTH_DENIED);
    SSH_CHECK(access_fake_event_count() == 0u);
    SSH_CHECK(crux_ssh_access_key_check(NULL, &peer, USER, CRUX_SSH_KEY_ED25519, other_key,
                                        sizeof(other_key), true) == CRUX_SSH_AUTH_DENIED);
    SSH_CHECK(access_fake_event_count_of(CRUX_ACCESS_EVENT_KEY_FAILURE) == 1u);

    SSH_CHECK(crux_ssh_access_key_verified(NULL, &peer, USER, CRUX_SSH_KEY_ED25519, other_key,
                                           sizeof(other_key), &attachment) == CRUX_SSH_AUTH_DENIED);
    SSH_CHECK(attachment == NULL);
}

static void test_key_verified_creates_the_session(void)
{
    crux_ssh_attachment_t *attachment = NULL;
    crux_access_session_t session;

    setup();
    SSH_CHECK(crux_ssh_access_key_verified(NULL, &peer, USER, CRUX_SSH_KEY_ED25519, ed25519_key,
                                           sizeof(ed25519_key),
                                           &attachment) == CRUX_SSH_AUTH_ACCEPTED);
    SSH_CHECK(attachment != NULL);
    session = crux_ssh_attachment_session(attachment);
    SSH_CHECK(crux_access_check(session, CRUX_ACCESS_PERMISSION_MANAGE) == CRUX_ACCESS_OK);
    crux_ssh_access_connection_closed(NULL, attachment);
    SSH_CHECK(access_fake_derive_count() == 0u);
}

static void test_failed_signature_counts_towards_the_delay(void)
{
    uint32_t retry_after_ms = 0;
    crux_access_origin_t origin = {.channel = CRUX_ACCESS_CHANNEL_SSH, .source_length = 4};

    setup();
    memcpy(origin.source, peer.address, 4);
    for (unsigned i = 0; i <= CRUX_ACCESS_DELAY_FREE_ATTEMPTS; ++i) {
        crux_ssh_access_key_failed(NULL, &peer, USER);
    }
    SSH_CHECK(access_fake_event_count_of(CRUX_ACCESS_EVENT_KEY_FAILURE) ==
              CRUX_ACCESS_DELAY_FREE_ATTEMPTS + 1u);
    SSH_CHECK(crux_access_key_is_authorised(USER, ed25519_key, sizeof(ed25519_key), false, &origin,
                                            &retry_after_ms) == CRUX_ACCESS_ERR_RETRY_LATER);
    /* The window holds the check too, as a denial. */
    SSH_CHECK(crux_ssh_access_key_check(NULL, &peer, USER, CRUX_SSH_KEY_ED25519, ed25519_key,
                                        sizeof(ed25519_key), true) == CRUX_SSH_AUTH_DENIED);
}

static void test_session_alive_does_not_refresh_the_idle_timer(void)
{
    crux_ssh_attachment_t *attachment;
    const uint64_t idle_ms =
        (uint64_t)access_test_profile_reference.policy.session_idle_limit_s * 1000u;

    setup();
    attachment = login(&peer);
    access_fake_clock_advance(idle_ms - 1u);
    SSH_CHECK(crux_ssh_access_session_alive(NULL, attachment));
    /* Had the poll refreshed it, this would still be inside the limit. */
    access_fake_clock_advance(1u);
    SSH_CHECK(!crux_ssh_access_session_alive(NULL, attachment));
    crux_ssh_access_connection_closed(NULL, attachment);
}

static void test_ipv6_delay_key_is_the_prefix(void)
{
    const crux_ssh_peer_t first = {
        .address = {0x20, 0x01, 0x0d, 0xb8, 0, 1, 0, 2, 0, 0, 0, 0, 0, 0, 0, 1},
        .address_length = 16};
    const crux_ssh_peer_t same_prefix = {
        .address = {0x20, 0x01, 0x0d, 0xb8, 0, 1, 0, 2, 0, 0, 0, 0, 0, 0, 0, 9},
        .address_length = 16};
    const crux_ssh_peer_t mapped = {
        .address = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xff, 0xff, 192, 0, 2, 7}, .address_length = 16};
    const uint8_t wrong[] = "not the password";
    crux_ssh_attachment_t *attachment = NULL;
    uint8_t channel = 0;
    uint8_t source[16] = {0};
    uint8_t source_length = 0;

    setup();
    attachment = login(&first);
    SSH_CHECK(crux_access_session_origin(crux_ssh_attachment_session(attachment), &channel, source,
                                         &source_length) == CRUX_ACCESS_OK);
    SSH_CHECK(source_length == 8u);
    SSH_CHECK(memcmp(source, first.address, 8) == 0);
    crux_ssh_access_connection_closed(NULL, attachment);
    attachment = NULL;

    /* An address that embeds IPv4 is that IPv4 source, not one shared prefix for all of them. */
    attachment = login(&mapped);
    SSH_CHECK(crux_access_session_origin(crux_ssh_attachment_session(attachment), &channel, source,
                                         &source_length) == CRUX_ACCESS_OK);
    SSH_CHECK(source_length == 4u);
    SSH_CHECK(memcmp(source, &mapped.address[12], 4) == 0);
    crux_ssh_access_connection_closed(NULL, attachment);
    attachment = NULL;

    /* Failures from one address hold back another in the same /64, under any name. */
    for (unsigned i = 0; i <= CRUX_ACCESS_DELAY_FREE_ATTEMPTS; ++i) {
        char name[] = "name-a";

        name[5] = (char)('a' + i);
        SSH_CHECK(crux_ssh_access_password(NULL, &first, name, wrong, sizeof(wrong) - 1,
                                           &attachment) == CRUX_SSH_AUTH_DENIED);
    }
    SSH_CHECK(crux_ssh_access_password(NULL, &same_prefix, USER, password(), password_length(),
                                       &attachment) == CRUX_SSH_AUTH_DENIED);
    SSH_CHECK(attachment == NULL);
}

static void check_auth_limit_report(const crux_ssh_peer_t *from, const uint8_t *source,
                                    uint8_t source_length)
{
    const crux_ssh_access_event_t *report;

    ssh_port_fake_reset();
    crux_ssh_access_auth_limit(NULL, from);
    SSH_CHECK(ssh_port_fake_count() == 1u);
    report = ssh_port_fake_event(0);
    SSH_CHECK(report != NULL && report->type == CRUX_SSH_ACCESS_EVENT_AUTH_LIMIT);
    if (report != NULL) {
        SSH_CHECK(report->channel == (uint8_t)CRUX_ACCESS_CHANNEL_SSH);
        SSH_CHECK(report->source_length == source_length);
        SSH_CHECK(memcmp(report->source, source, source_length) == 0);
    }
}

static void test_auth_limit_is_reported_with_the_source_access_uses(void)
{
    const crux_ssh_peer_t v6 = {
        .address = {0x20, 0x01, 0x0d, 0xb8, 0, 1, 0, 2, 0, 0, 0, 0, 0, 0, 0, 1},
        .address_length = 16};
    const crux_ssh_peer_t mapped = {
        .address = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xff, 0xff, 192, 0, 2, 7}, .address_length = 16};

    setup();
    /* An IPv4 address, an IPv4 address inside IPv6, and an IPv6 /64: the three sources Access keys
     * on. */
    check_auth_limit_report(&peer, peer.address, 4u);
    check_auth_limit_report(&mapped, &mapped.address[12], 4u);
    check_auth_limit_report(&v6, v6.address, 8u);
    /* The report is the adapter's own: Access hears nothing, and no delay entry is written. */
    SSH_CHECK(access_fake_event_count() == 0u);
    crux_ssh_access_connection_closed(NULL, login(&peer));
}

static void test_auth_limit_without_a_known_peer_still_reports(void)
{
    const crux_ssh_peer_t none = {.address_length = 0};
    const crux_ssh_peer_t odd = {.address = {1, 2, 3}, .address_length = 3};
    const crux_ssh_access_event_t *report;

    setup();
    /* A limit was reached whatever the address looks like, so it is reported with no source. */
    ssh_port_fake_reset();
    crux_ssh_access_auth_limit(NULL, NULL);
    crux_ssh_access_auth_limit(NULL, &none);
    crux_ssh_access_auth_limit(NULL, &odd);
    SSH_CHECK(ssh_port_fake_count_of(CRUX_SSH_ACCESS_EVENT_AUTH_LIMIT) == 3u);
    for (size_t i = 0; i < ssh_port_fake_count(); ++i) {
        report = ssh_port_fake_event(i);
        SSH_CHECK(report != NULL && report->source_length == 0u);
        SSH_CHECK(report != NULL && report->channel == (uint8_t)CRUX_ACCESS_CHANNEL_SSH);
    }
}

static void test_the_other_entry_points_report_no_port_event(void)
{
    const uint8_t wrong[] = "not the password";
    crux_ssh_attachment_t *attachment = NULL;

    setup();
    ssh_port_fake_reset();
    /* Refusals, a failed signature and a logout are Access's events. Only the limit is this port's.
     */
    SSH_CHECK(crux_ssh_access_password(NULL, &peer, USER, wrong, sizeof(wrong) - 1, &attachment) ==
              CRUX_SSH_AUTH_DENIED);
    crux_ssh_access_key_failed(NULL, &peer, USER);
    crux_ssh_access_connection_closed(NULL, login(&other_peer));
    SSH_CHECK(ssh_port_fake_count() == 0u);
}

static void test_null_attachment_is_no_session(void)
{
    SSH_CHECK(crux_ssh_attachment_session(NULL).value == 0u);
    SSH_CHECK(!crux_ssh_access_session_alive(NULL, NULL));
    crux_ssh_access_connection_closed(NULL, NULL);
}

int main(void)
{
    test_password_login_holds_a_session_of_the_ssh_channel();
    test_every_refusal_is_a_denial_and_holds_no_slot();
    test_delay_is_a_denial_that_verifies_nothing();
    test_busy_verification_is_a_denial();
    test_session_replaced_by_the_account_cap_is_no_longer_alive();
    test_attachments_are_bounded();
    test_key_check_creates_nothing();
    test_key_verified_creates_the_session();
    test_failed_signature_counts_towards_the_delay();
    test_session_alive_does_not_refresh_the_idle_timer();
    test_ipv6_delay_key_is_the_prefix();
    test_auth_limit_is_reported_with_the_source_access_uses();
    test_auth_limit_without_a_known_peer_still_reports();
    test_the_other_entry_points_report_no_port_event();
    test_null_attachment_is_no_session();
    printf("%u failures\n", ssh_check_failures);
    return ssh_check_failures == 0 ? 0 : 1;
}
