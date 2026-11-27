/*
 * The core under a clock that has failed, which the clock port reports as CRUX_ACCESS_CLOCK_FAILED.
 * Nothing that needs the time proceeds: a login and a key attempt return NOT_READY, create no
 * session and leave every bucket as it was, and a session from before the fault expires. See
 * docs/access-contract.md and docs/native-management-composition.md#what-each-port-maps.
 */
#include "access_test.h"

#define NOW_MS (CRUX_ACCESS_DELAY_QUIET_MS + 5000u)

static const char wrong[] = "a wrong password for this";
static const uint8_t listed[] = ACCESS_TEST_ED25519_KEY(0xA1);

static crux_access_session_t start(void)
{
    access_fake_reset();
    crux_access_test_reset();
    access_fake_clock_set(NOW_MS);
    CHECK(crux_access_init(&access_test_profile_reference.policy) == CRUX_ACCESS_OK);
    CHECK(crux_access_provision_first_account(ACCESS_TEST_ADMIN, ACCESS_TEST_PASSWORD,
                                              strlen(ACCESS_TEST_PASSWORD),
                                              access_test_profile_reference.administrator_role,
                                              &access_test_serial) == CRUX_ACCESS_OK);
    crux_access_session_t admin =
        access_test_session(ACCESS_TEST_ADMIN, ACCESS_TEST_PASSWORD, &access_test_serial);
    access_test_create_user(admin);
    CHECK(crux_access_account_add_key(admin, ACCESS_TEST_USER, listed, sizeof(listed)) ==
          CRUX_ACCESS_OK);
    return admin;
}

static crux_access_result_t login(const char *password, crux_access_session_t *session)
{
    uint32_t retry_after_ms = 0;
    return crux_access_login_password(ACCESS_TEST_ADMIN, password, strlen(password),
                                      &access_test_web, session, &retry_after_ms);
}

static void a_session_from_before_the_fault_expires(void)
{
    crux_access_session_t session = {0};
    start();
    CHECK(login(ACCESS_TEST_PASSWORD, &session) == CRUX_ACCESS_OK);
    CHECK(crux_access_check(session, "status.read") == CRUX_ACCESS_OK);
    access_fake_clock_fail(true);
    CHECK(crux_access_check(session, "status.read") == CRUX_ACCESS_ERR_SESSION_INVALID);
    access_fake_clock_fail(false);
    CHECK(crux_access_check(session, "status.read") == CRUX_ACCESS_ERR_SESSION_INVALID);
}

static void a_login_during_the_fault_is_not_ready(void)
{
    crux_access_session_t session = {0};
    start();
    access_fake_clock_fail(true);
    access_fake_events_clear();
    access_fake_derive_counters_clear();
    session.value = 1u;
    CHECK(login(ACCESS_TEST_PASSWORD, &session) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(session.value == 0u);
    CHECK(access_fake_event_count_of(CRUX_ACCESS_EVENT_NOT_READY) == 1u);
    CHECK(access_fake_event_count_of(CRUX_ACCESS_EVENT_LOGIN_SUCCESS) == 0u);
    CHECK(access_fake_event_count_of(CRUX_ACCESS_EVENT_LOGIN_FAILURE) == 0u);
    /* No guess was evaluated. */
    CHECK(access_fake_derive_count() == 0u);
    access_fake_clock_fail(false);
    CHECK(login(ACCESS_TEST_PASSWORD, &session) == CRUX_ACCESS_OK);
    CHECK(crux_access_check(session, "status.read") == CRUX_ACCESS_OK);
}

/* The clock fails after the guess was evaluated: no session, and no failure counted. */
static void a_fault_after_the_verification_is_not_ready(void)
{
    crux_access_session_t session = {0};
    start();
    access_fake_clock_fail_after(1u);
    CHECK(login(ACCESS_TEST_PASSWORD, &session) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(session.value == 0u);
    for (unsigned attempt = 0; attempt < CRUX_ACCESS_DELAY_FREE_ATTEMPTS + 2u; ++attempt) {
        access_fake_clock_fail_after(1u);
        CHECK(login(wrong, &session) == CRUX_ACCESS_ERR_NOT_READY);
    }
    access_fake_clock_fail(false);
    /* The slot and the verification flag were given back, and no bucket counted those guesses. */
    for (unsigned attempt = 0; attempt < CRUX_ACCESS_DELAY_FREE_ATTEMPTS; ++attempt) {
        CHECK(login(wrong, &session) == CRUX_ACCESS_ERR_DENIED);
    }
    CHECK(login(ACCESS_TEST_PASSWORD, &session) == CRUX_ACCESS_OK);
}

static void a_window_stays_closed_through_the_fault(void)
{
    crux_access_session_t session = {0};
    uint32_t retry_after_ms = 0;
    start();
    for (unsigned attempt = 0; attempt < CRUX_ACCESS_DELAY_FREE_ATTEMPTS + 1u; ++attempt) {
        CHECK(login(wrong, &session) == CRUX_ACCESS_ERR_DENIED);
    }
    CHECK(login(ACCESS_TEST_PASSWORD, &session) == CRUX_ACCESS_ERR_RETRY_LATER);
    access_fake_clock_fail(true);
    CHECK(login(ACCESS_TEST_PASSWORD, &session) == CRUX_ACCESS_ERR_NOT_READY);
    access_fake_clock_fail(false);
    CHECK(crux_access_login_password(ACCESS_TEST_ADMIN, ACCESS_TEST_PASSWORD,
                                     strlen(ACCESS_TEST_PASSWORD), &access_test_web, &session,
                                     &retry_after_ms) == CRUX_ACCESS_ERR_RETRY_LATER);
    CHECK(retry_after_ms > 0u && retry_after_ms <= CRUX_ACCESS_DELAY_BASE_MS);
}

/* Attempts during the fault neither count nor date a bucket, so the clock's return finds the real
 * failures where they were, and the free attempts do not come back. */
static void attempts_during_the_fault_leave_a_bucket_unchanged(void)
{
    crux_access_session_t session = {0};
    start();
    for (unsigned attempt = 0; attempt < 3u; ++attempt) {
        CHECK(login(wrong, &session) == CRUX_ACCESS_ERR_DENIED);
    }
    access_fake_clock_fail(true);
    for (unsigned attempt = 0; attempt < 3u; ++attempt) {
        CHECK(login(wrong, &session) == CRUX_ACCESS_ERR_NOT_READY);
    }
    access_fake_clock_fail(false);
    access_fake_clock_set(NOW_MS + 1u);
    for (unsigned attempt = 3u; attempt < CRUX_ACCESS_DELAY_FREE_ATTEMPTS + 1u; ++attempt) {
        CHECK(login(wrong, &session) == CRUX_ACCESS_ERR_DENIED);
    }
    CHECK(login(wrong, &session) == CRUX_ACCESS_ERR_RETRY_LATER);
}

static void a_key_attempt_during_the_fault_is_not_ready(void)
{
    crux_access_session_t session = {0};
    uint32_t retry_after_ms = 0;
    start();
    access_fake_clock_fail(true);
    CHECK(crux_access_key_is_authorised(ACCESS_TEST_USER, listed, sizeof(listed), true,
                                        &access_test_ssh,
                                        &retry_after_ms) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(crux_access_key_is_authorised(ACCESS_TEST_USER, listed, sizeof(listed), false,
                                        &access_test_ssh,
                                        &retry_after_ms) == CRUX_ACCESS_ERR_NOT_READY);
    session.value = 1u;
    CHECK(crux_access_login_verified(ACCESS_TEST_USER, listed, sizeof(listed), &access_test_ssh,
                                     &session) == CRUX_ACCESS_ERR_NOT_READY);
    CHECK(session.value == 0u);
    /* A failed signature reported during the fault counts nothing. */
    for (unsigned attempt = 0; attempt < CRUX_ACCESS_DELAY_FREE_ATTEMPTS + 2u; ++attempt) {
        crux_access_report_key_failure(ACCESS_TEST_USER, &access_test_ssh);
    }
    access_fake_clock_fail(false);
    CHECK(crux_access_key_is_authorised(ACCESS_TEST_USER, listed, sizeof(listed), true,
                                        &access_test_ssh, &retry_after_ms) == CRUX_ACCESS_OK);
    CHECK(retry_after_ms == 0u);
    CHECK(crux_access_login_verified(ACCESS_TEST_USER, listed, sizeof(listed), &access_test_ssh,
                                     &session) == CRUX_ACCESS_OK);
}

/* The clock fails between the session check and the verification of the current password. */
static void a_password_change_during_the_fault_is_not_ready(void)
{
    crux_access_session_t session = {0};
    uint32_t retry_after_ms = 0;
    static const char next[] = "another long password here";
    start();
    CHECK(login(ACCESS_TEST_PASSWORD, &session) == CRUX_ACCESS_OK);
    access_fake_clock_fail_after(1u);
    CHECK(crux_access_account_change_password(session, ACCESS_TEST_PASSWORD,
                                              strlen(ACCESS_TEST_PASSWORD), next, strlen(next),
                                              &retry_after_ms) == CRUX_ACCESS_ERR_NOT_READY);
    access_fake_clock_fail(false);
    CHECK(login(ACCESS_TEST_PASSWORD, &session) == CRUX_ACCESS_OK);
}

/* The clock fails after the current password was derived: nothing is counted or cleared, and the
 * verification flag is given back. */
static void a_fault_after_a_password_change_verification_is_not_ready(void)
{
    crux_access_session_t session = {0};
    uint32_t retry_after_ms = 0;
    static const char next[] = "another long password here";
    start();
    CHECK(login(ACCESS_TEST_PASSWORD, &session) == CRUX_ACCESS_OK);
    access_fake_derive_counters_clear();
    /* One read for the session check, one before the derivation, and the one after it fails. */
    for (unsigned attempt = 0; attempt < CRUX_ACCESS_DELAY_FREE_ATTEMPTS + 2u; ++attempt) {
        access_fake_clock_fail_after(2u);
        CHECK(crux_access_account_change_password(session, wrong, strlen(wrong), next, strlen(next),
                                                  &retry_after_ms) == CRUX_ACCESS_ERR_NOT_READY);
    }
    CHECK(access_fake_derive_count() == CRUX_ACCESS_DELAY_FREE_ATTEMPTS + 2u);
    access_fake_clock_fail(false);
    for (unsigned attempt = 0; attempt < CRUX_ACCESS_DELAY_FREE_ATTEMPTS; ++attempt) {
        CHECK(crux_access_account_change_password(session, wrong, strlen(wrong), next, strlen(next),
                                                  &retry_after_ms) == CRUX_ACCESS_ERR_DENIED);
    }
    CHECK(crux_access_account_change_password(session, ACCESS_TEST_PASSWORD,
                                              strlen(ACCESS_TEST_PASSWORD), next, strlen(next),
                                              &retry_after_ms) == CRUX_ACCESS_OK);
}

int main(void)
{
    a_session_from_before_the_fault_expires();
    a_login_during_the_fault_is_not_ready();
    a_fault_after_the_verification_is_not_ready();
    a_window_stays_closed_through_the_fault();
    attempts_during_the_fault_leave_a_bucket_unchanged();
    a_key_attempt_during_the_fault_is_not_ready();
    a_password_change_during_the_fault_is_not_ready();
    a_fault_after_a_password_change_verification_is_not_ready();
    return access_test_finish("access under a failed clock");
}
