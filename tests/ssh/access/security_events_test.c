/*
 * The provider of the access adapter's event port, on the recording fake of the Security event
 * contract: each report to its ssh.* record, and the adapter's entry point through it to the same
 * record. The adapter's own decisions are in adapter_test.c and host_key_test.c.
 */
#include "crux_ssh_access.h"
#include "crux_ssh_access_port.h"
#include "crux_ssh_callbacks.h"
#include "security_event_fake.h"
#include "ssh_check.h"

#include <string.h>

static void boot(void)
{
    security_event_fake_reset();
    security_event_fake_boot();
}

static void test_auth_limit_records_the_channel_and_source_and_nobody_else(void)
{
    crux_ssh_access_event_t report = {.type = CRUX_SSH_ACCESS_EVENT_AUTH_LIMIT,
                                      .channel = CRUX_SSH_ACCESS_EVENT_CHANNEL,
                                      .source_length = 4u,
                                      .source = {192, 0, 2, 9}};
    const crux_security_event_record_t *record;

    boot();
    crux_ssh_access_port_event(&report);
    SSH_CHECK(security_event_fake_count() == 1u);
    record = security_event_fake_last(CRUX_SECURITY_EVENT_ID_SSH_AUTH_LIMIT);
    SSH_CHECK(record != NULL);
    if (record != NULL) {
        SSH_CHECK(record->result == CRUX_SECURITY_EVENT_LIMIT);
        SSH_CHECK(record->channel == 3u);
        SSH_CHECK(record->source_length == 4u && memcmp(record->source, report.source, 4) == 0);
        SSH_CHECK(record->user[0] == '\0' && record->subject[0] == '\0');
    }
}

static void test_host_key_missing_records_a_failure_with_no_source(void)
{
    crux_ssh_access_event_t report = {.type = CRUX_SSH_ACCESS_EVENT_HOST_KEY_MISSING,
                                      .channel = CRUX_SSH_ACCESS_EVENT_CHANNEL};
    const crux_security_event_record_t *record;

    boot();
    crux_ssh_access_port_event(&report);
    SSH_CHECK(security_event_fake_count() == 1u);
    record = security_event_fake_last(CRUX_SECURITY_EVENT_ID_SSH_HOST_KEY_MISSING);
    SSH_CHECK(record != NULL);
    if (record != NULL) {
        SSH_CHECK(record->result == CRUX_SECURITY_EVENT_FAILED);
        SSH_CHECK(record->channel == 3u && record->source_length == 0u);
        SSH_CHECK(record->user[0] == '\0' && record->subject[0] == '\0');
    }
}

static void test_a_null_report_records_nothing(void)
{
    boot();
    crux_ssh_access_port_event(NULL);
    SSH_CHECK(security_event_fake_count() == 0u);
}

static void test_the_adapter_entry_point_reaches_the_record(void)
{
    const crux_ssh_peer_t peer = {.address = {198, 51, 100, 4}, .address_length = 4};
    const crux_security_event_record_t *record;

    boot();
    crux_ssh_access_auth_limit(NULL, &peer);
    SSH_CHECK(security_event_fake_count_of(CRUX_SECURITY_EVENT_ID_SSH_AUTH_LIMIT) == 1u);
    record = security_event_fake_last(CRUX_SECURITY_EVENT_ID_SSH_AUTH_LIMIT);
    SSH_CHECK(record != NULL && record->channel == 3u);
    SSH_CHECK(record != NULL && record->source_length == 4u &&
              memcmp(record->source, peer.address, 4) == 0);
}

int main(void)
{
    test_auth_limit_records_the_channel_and_source_and_nobody_else();
    test_host_key_missing_records_a_failure_with_no_source();
    test_a_null_report_records_nothing();
    test_the_adapter_entry_point_reaches_the_record();
    printf("%u failures\n", ssh_check_failures);
    return ssh_check_failures == 0 ? 0 : 1;
}
