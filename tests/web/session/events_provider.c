/* The event provider of the session module (Issue #319): each report to its web.* record, on the
 * recording fake of the security event contract. The provider is the file that a product image
 * links, and this suite does not link the session module, so the fake port of the other suites does
 * not take its place. */
#include "security_event_fake.h"
#include "web_session_event_port.h"

#include <stdio.h>
#include <string.h>

static unsigned checks;
static unsigned failures;

#define CHECK(expression)                                                                          \
    do {                                                                                           \
        ++checks;                                                                                  \
        if (!(expression)) {                                                                       \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #expression);                           \
            ++failures;                                                                            \
        }                                                                                          \
    } while (0)

static crux_web_session_event_t report_of(crux_web_session_event_type_t type)
{
    crux_web_session_event_t event;

    memset(&event, 0, sizeof(event));
    event.type = type;
    event.channel = 2u;
    event.source_length = 4u;
    event.source[0] = 192u;
    event.source[1] = 0u;
    event.source[2] = 2u;
    event.source[3] = 9u;
    memcpy(event.user, "viewer", sizeof("viewer"));
    return event;
}

static void test_csrf(void)
{
    crux_web_session_event_t event = report_of(CRUX_WEB_SESSION_EVENT_CSRF_REJECTED);
    const crux_security_event_record_t *record;

    security_event_fake_reset();
    security_event_fake_boot();
    crux_web_session_port_event(&event);
    CHECK(security_event_fake_count() == 1u);
    record = security_event_fake_last(CRUX_SECURITY_EVENT_ID_WEB_CSRF_REJECTED);
    CHECK(record != NULL);
    if (record == NULL) {
        return;
    }
    CHECK(record->result == CRUX_SECURITY_EVENT_DENIED);
    CHECK(record->channel == 2u);
    CHECK(record->source_length == 4u && record->source[0] == 192u && record->source[3] == 9u);
    CHECK(strcmp(record->user, "viewer") == 0);
    CHECK(record->subject[0] == '\0' && !record->subject_truncated);
    CHECK(strcmp(crux_security_event_name(CRUX_SECURITY_EVENT_ID_WEB_CSRF_REJECTED),
                 "web.csrf_rejected") == 0);
}

static void test_origin(void)
{
    crux_web_session_event_t event = report_of(CRUX_WEB_SESSION_EVENT_ORIGIN_REJECTED);
    const crux_security_event_record_t *record;
    crux_security_event_stats_t stats;

    security_event_fake_reset();
    security_event_fake_boot();
    crux_web_session_port_event(&event);
    CHECK(security_event_fake_count() == 1u);
    CHECK(security_event_fake_count_of(CRUX_SECURITY_EVENT_ID_EVENT_UNKNOWN) == 0u);
    CHECK(CRUX_SECURITY_EVENT_ID_WEB_ORIGIN_REJECTED == 0x0605);
    record = security_event_fake_last(CRUX_SECURITY_EVENT_ID_WEB_ORIGIN_REJECTED);
    CHECK(record != NULL);
    if (record == NULL) {
        return;
    }
    CHECK(record->result == CRUX_SECURITY_EVENT_DENIED);
    CHECK(record->channel == 2u && record->source_length == 4u);
    CHECK(strcmp(record->user, "viewer") == 0);
    CHECK(record->subject[0] == '\0');
    CHECK(strcmp(crux_security_event_name(CRUX_SECURITY_EVENT_ID_WEB_ORIGIN_REJECTED),
                 "web.origin_rejected") == 0);
    CHECK(crux_security_event_get_stats(&stats) == CRUX_OK && stats.invalid_fields == 0u);
}

/* A login's Origin has no session, so no user, and an address that cannot be read has no source. */
static void test_no_user_and_no_source(void)
{
    crux_web_session_event_t event = report_of(CRUX_WEB_SESSION_EVENT_ORIGIN_REJECTED);
    const crux_security_event_record_t *record;
    crux_security_event_stats_t stats;

    security_event_fake_reset();
    security_event_fake_boot();
    memset(event.user, 0, sizeof(event.user));
    event.source_length = 0u;
    memset(event.source, 0, sizeof(event.source));
    crux_web_session_port_event(&event);
    record = security_event_fake_last(CRUX_SECURITY_EVENT_ID_WEB_ORIGIN_REJECTED);
    CHECK(record != NULL);
    if (record == NULL) {
        return;
    }
    CHECK(record->user[0] == '\0');
    CHECK(record->channel == 2u && record->source_length == 0u);
    /* Nothing was omitted for being out of rule: an empty user is passed as no user. */
    CHECK(crux_security_event_get_stats(&stats) == CRUX_OK && stats.invalid_fields == 0u);
}

/* A value that is in no enumerator, read through a volatile so that no analysis takes it for a
 * constant cast to the enum, which is not what the provider is handed in a failing image. */
static volatile unsigned unmapped_type = 99u;

/* A type that the table does not map is a failure of unknown kind, and never a success. */
static void test_unknown_type(void)
{
    crux_web_session_event_t event = report_of((crux_web_session_event_type_t)unmapped_type);
    const crux_security_event_record_t *record;

    security_event_fake_reset();
    security_event_fake_boot();
    crux_web_session_port_event(&event);
    record = security_event_fake_last(CRUX_SECURITY_EVENT_ID_EVENT_UNKNOWN);
    CHECK(record != NULL && record->result == CRUX_SECURITY_EVENT_FAILED);
    CHECK(security_event_fake_count() == 1u);
}

int main(void)
{
    test_csrf();
    test_origin();
    test_no_user_and_no_source();
    test_unknown_type();
    printf("web_session_events_provider: %u checks, %u failures\n", checks, failures);
    return failures == 0u ? 0 : 1;
}
