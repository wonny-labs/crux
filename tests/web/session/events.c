/* The reports of a refused CSRF token and a refused Origin to the event port (Issue #319): when
 * one is made, what it holds, and the bound that keeps a flood from becoming a flood of reports.
 * The fake port records what the session module reported, and tests/web/session/events_provider.c
 * holds the real provider to the security events. */
#include "session_test.h"

#define WINDOW CRUX_WEB_SESSION_FORGERY_WINDOW_MS
#define SHARE CRUX_WEB_SESSION_FORGERY_EVENTS

static void expect_error(const fake_reply_t *reply, int status, const char *code)
{
    char expected[64];

    snprintf(expected, sizeof(expected), "{\"code\":\"%s\"}", code);
    CHECK(reply->origin == FAKE_FROM_CORE);
    CHECK(reply->status == status);
    CHECK(strcmp(reply->body, expected) == 0);
}

/* A state-changing request of a signed-in browser, with the given token and Origin. */
static const fake_reply_t *post(const session_jar_t *jar, const char *origin, const char *xsrf)
{
    session_request_t request = {.method = CRUX_WEB_POST,
                                 .url = "/api/v1/test/session",
                                 .cookie = jar->header,
                                 .origin = origin,
                                 .host = SESSION_TEST_HOST,
                                 .xsrf = xsrf};

    return session_send(&request);
}

static void expect_last(crux_web_session_event_type_t type, const char *user)
{
    size_t count = session_events_count();
    const crux_web_session_event_t *event = count == 0u ? NULL : session_events_at(count - 1u);

    CHECK(event != NULL);
    if (event == NULL) {
        return;
    }
    CHECK(event->type == type);
    CHECK(event->channel == (uint8_t)CRUX_ACCESS_CHANNEL_WEB);
    CHECK(event->source_length == 4u);
    CHECK(event->source[0] == 192u && event->source[1] == 0u && event->source[2] == 2u &&
          event->source[3] == 9u);
    CHECK(strcmp(event->user, user) == 0);
}

static void test_refused_token_is_reported(void)
{
    session_jar_t jar;
    session_jar_t other;
    char prefix[64];
    const char *wrong[5];
    size_t expected = 0;

    session_test_setup();
    CHECK(session_login("viewer", SESSION_TEST_PASSWORD, &jar)->status == 200);
    CHECK(session_login("forced", SESSION_TEST_PASSWORD, &other)->status == 200);
    snprintf(prefix, sizeof(prefix), "%s", jar.xsrf);
    prefix[42] = '\0';
    wrong[0] = NULL;
    wrong[1] = "";
    wrong[2] = other.xsrf;
    wrong[3] = jar.session;
    wrong[4] = prefix;
    CHECK(session_events_count() == 0u);
    for (size_t index = 0; index < 5u; ++index) {
        /* A new window each time, so the bound is not what this case looks at. */
        session_clock_advance(WINDOW);
        expect_error(post(&jar, SESSION_TEST_ORIGIN, wrong[index]), 403, "csrf_rejected");
        ++expected;
        CHECK(session_events_count() == expected);
        expect_last(CRUX_WEB_SESSION_EVENT_CSRF_REJECTED, "viewer");
    }
    CHECK(session_events_count_of(CRUX_WEB_SESSION_EVENT_ORIGIN_REJECTED) == 0u);
}

static void test_refused_origin_is_reported(void)
{
    static const char *const wrong[] = {NULL, "https://evil.test", "https://device.test.evil.test",
                                        "null", "http://device.test"};
    session_jar_t jar;
    size_t expected = 0;

    session_test_setup();
    CHECK(session_login("viewer", SESSION_TEST_PASSWORD, &jar)->status == 200);
    for (size_t index = 0; index < sizeof(wrong) / sizeof(wrong[0]); ++index) {
        session_clock_advance(WINDOW);
        expect_error(post(&jar, wrong[index], jar.xsrf), 403, "origin_rejected");
        ++expected;
        CHECK(session_events_count() == expected);
        expect_last(CRUX_WEB_SESSION_EVENT_ORIGIN_REJECTED, "viewer");
    }
    /* Origin is checked first, so a request wrong in both is one report, of the Origin. */
    session_clock_advance(WINDOW);
    expect_error(post(&jar, "https://evil.test", "wrong"), 403, "origin_rejected");
    CHECK(session_events_count() == expected + 1u);
    expect_last(CRUX_WEB_SESSION_EVENT_ORIGIN_REJECTED, "viewer");
    CHECK(session_events_count_of(CRUX_WEB_SESSION_EVENT_CSRF_REJECTED) == 0u);
}

/* A login's Origin is checked before there is a session, so its report has no user. */
static void test_refused_login_origin_is_reported(void)
{
    session_request_t login = {.method = CRUX_WEB_POST,
                               .url = "/api/v1/session",
                               .origin = "https://evil.test",
                               .host = SESSION_TEST_HOST,
                               .content_type = "application/json",
                               .body = "{\"user\":\"viewer\",\"password\":\"x\"}"};

    session_test_setup();
    expect_error(session_send(&login), 403, "origin_rejected");
    CHECK(session_events_count() == 1u);
    expect_last(CRUX_WEB_SESSION_EVENT_ORIGIN_REJECTED, "");
    /* Nothing was queued for the worker. */
    CHECK(!web_session_work_once());
}

/* A request that is not a refusal of these two checks reports nothing. */
static void test_no_report_without_a_refusal(void)
{
    session_jar_t jar;
    session_request_t request;

    session_test_setup();
    CHECK(session_login("viewer", SESSION_TEST_PASSWORD, &jar)->status == 200);
    CHECK(session_events_count() == 0u);
    /* An accepted state-changing request. */
    CHECK(post(&jar, SESSION_TEST_ORIGIN, jar.xsrf)->status == 200);
    /* GET carries no token and no Origin check. */
    request = (session_request_t){.method = CRUX_WEB_GET,
                                  .url = "/api/v1/session/me",
                                  .cookie = jar.header,
                                  .origin = "https://evil.test",
                                  .host = SESSION_TEST_HOST};
    CHECK(session_send(&request)->status == 200);
    /* No session is 401, and says nothing about a token or an Origin. */
    request = (session_request_t){.method = CRUX_WEB_POST,
                                  .url = "/api/v1/test/session",
                                  .origin = "https://evil.test",
                                  .host = SESSION_TEST_HOST,
                                  .xsrf = "wrong"};
    expect_error(session_send(&request), 401, "unauthorized");
    /* A forged session cookie is 401 as well. */
    request.cookie = "crux_session=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
    expect_error(session_send(&request), 401, "unauthorized");
    /* A login with the right Origin, and a wrong password. */
    CHECK(session_login("viewer", "not the password", NULL)->status == 200);
    CHECK(session_events_count() == 0u);
}

/* A flood of refusals reports as many as the window allows, for each kind apart. */
static void test_flood_is_bounded(void)
{
    session_jar_t jar;
    crux_web_session_stats_t stats;

    session_test_setup();
    CHECK(session_login("viewer", SESSION_TEST_PASSWORD, &jar)->status == 200);
    for (unsigned count = 0; count < 100u; ++count) {
        expect_error(post(&jar, SESSION_TEST_ORIGIN, "wrong"), 403, "csrf_rejected");
    }
    CHECK(session_events_count_of(CRUX_WEB_SESSION_EVENT_CSRF_REJECTED) == SHARE);
    crux_web_session_stats_get(&stats);
    CHECK(stats.forgery_suppressed == 100u - SHARE);
    /* Origin has a share of its own: a flood of one kind does not silence the other. */
    for (unsigned count = 0; count < 100u; ++count) {
        expect_error(post(&jar, "https://evil.test", jar.xsrf), 403, "origin_rejected");
    }
    CHECK(session_events_count_of(CRUX_WEB_SESSION_EVENT_ORIGIN_REJECTED) == SHARE);
    CHECK(session_events_count_of(CRUX_WEB_SESSION_EVENT_CSRF_REJECTED) == SHARE);
    CHECK(session_events_count() == 2u * SHARE);
    crux_web_session_stats_get(&stats);
    CHECK(stats.forgery_suppressed == 2u * (100u - SHARE));

    /* The window runs from the first report. One millisecond short of it, nothing more is said. */
    session_clock_advance(WINDOW - 1u);
    expect_error(post(&jar, SESSION_TEST_ORIGIN, "wrong"), 403, "csrf_rejected");
    CHECK(session_events_count() == 2u * SHARE);
    /* And at its end the share is new. */
    session_clock_advance(1u);
    for (unsigned count = 0; count < 10u; ++count) {
        expect_error(post(&jar, SESSION_TEST_ORIGIN, "wrong"), 403, "csrf_rejected");
    }
    CHECK(session_events_count_of(CRUX_WEB_SESSION_EVENT_CSRF_REJECTED) == 2u * SHARE);
    CHECK(session_events_count_of(CRUX_WEB_SESSION_EVENT_ORIGIN_REJECTED) == SHARE);
    /* A new init starts every window again. */
    {
        static const crux_web_session_config_t config = {"https", NULL, 0u};

        CHECK(crux_web_session_init(&config) == CRUX_WEB_OK);
        crux_web_session_stats_get(&stats);
        CHECK(stats.forgery_suppressed == 0u);
    }
}

static bool holds(const void *bytes, size_t length, const char *text)
{
    const uint8_t *memory = bytes;
    size_t text_length = strlen(text);

    for (size_t offset = 0; offset + text_length <= length; ++offset) {
        if (memcmp(memory + offset, text, text_length) == 0) {
            return true;
        }
    }
    return false;
}

/* The client chooses the Origin and the token, and neither reaches the report. */
static void test_no_client_text_in_a_report(void)
{
    static const char hostile_origin[] = "https://evil.test/ORIGIN-SENTINEL";
    static const char hostile_token[] = "TOKEN-SENTINEL-0123456789";
    session_jar_t jar;

    session_test_setup();
    CHECK(session_login("viewer", SESSION_TEST_PASSWORD, &jar)->status == 200);
    expect_error(post(&jar, SESSION_TEST_ORIGIN, hostile_token), 403, "csrf_rejected");
    session_clock_advance(WINDOW);
    expect_error(post(&jar, hostile_origin, hostile_token), 403, "origin_rejected");
    {
        session_request_t login = {.method = CRUX_WEB_POST,
                                   .url = "/api/v1/session",
                                   .origin = hostile_origin,
                                   .host = SESSION_TEST_HOST,
                                   .content_type = "application/json",
                                   .body = "{\"user\":\"USER-SENTINEL\",\"password\":\"x\"}"};

        session_clock_advance(WINDOW);
        session_clock_advance(WINDOW);
        expect_error(session_send(&login), 403, "origin_rejected");
    }
    CHECK(session_events_count() == 3u);
    for (size_t index = 0; index < session_events_count(); ++index) {
        const crux_web_session_event_t *event = session_events_at(index);

        CHECK(event != NULL);
        if (event == NULL) {
            continue;
        }
        CHECK(!holds(event, sizeof(*event), "SENTINEL"));
        CHECK(!holds(event, sizeof(*event), "evil.test"));
        CHECK(!holds(event, sizeof(*event), jar.xsrf));
        CHECK(!holds(event, sizeof(*event), jar.session));
    }
}

/* The report keeps only an address of a form that the event contract takes, and a known session's
 * user. */
static void test_report_fields(void)
{
    crux_web_request_head_t head;
    const crux_web_session_event_t *event;

    session_test_setup();
    memset(&head, 0, sizeof(head));
    memset(head.source, 0xAB, sizeof(head.source));
    head.source_length = 8u;
    web_session_report_refusal(WEB_REFUSAL_ORIGIN, &head, (crux_access_session_t){0u});
    event = session_events_at(0u);
    CHECK(event != NULL);
    CHECK(event != NULL && event->source_length == 8u && event->source[7] == 0xABu);
    CHECK(event != NULL && event->user[0] == '\0');
    CHECK(event != NULL && event->channel == (uint8_t)CRUX_ACCESS_CHANNEL_WEB);

    /* A length that fits no buffer is reported as no address, and the bytes are not read. */
    session_clock_advance(WINDOW);
    head.source_length = 17u;
    web_session_report_refusal(WEB_REFUSAL_CSRF, &head, (crux_access_session_t){0u});
    event = session_events_at(1u);
    CHECK(event != NULL && event->type == CRUX_WEB_SESSION_EVENT_CSRF_REJECTED);
    CHECK(event != NULL && event->source_length == 0u && event->source[0] == 0u);

    session_clock_advance(WINDOW);
    head.source_length = 0u;
    web_session_report_refusal(WEB_REFUSAL_CSRF, &head, session_admin);
    event = session_events_at(2u);
    CHECK(event != NULL && event->source_length == 0u);
    CHECK(event != NULL && strcmp(event->user, "admin") == 0);

    /* A session that has ended has no user to name, and the report is still made. */
    session_clock_advance(WINDOW);
    {
        crux_access_session_t never = {0x7fffffffu};

        web_session_report_refusal(WEB_REFUSAL_ORIGIN, &head, never);
    }
    event = session_events_at(3u);
    CHECK(event != NULL && event->user[0] == '\0');
}

int main(void)
{
    test_refused_token_is_reported();
    test_refused_origin_is_reported();
    test_refused_login_origin_is_reported();
    test_no_report_without_a_refusal();
    test_flood_is_bounded();
    test_no_client_text_in_a_report();
    test_report_fields();
    return session_test_finish("web_session_events");
}
