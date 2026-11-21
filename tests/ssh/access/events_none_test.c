/*
 * The dropping provider of the access adapter's event port, for an image with no event core. No
 * other Host target compiles it, so this is its only Host build. It shows that the adapter links
 * with it and with no Security event library, and that each report, a NULL report and the
 * adapter's own entry point return and leave what the caller holds unchanged. It cannot show that
 * the report is dropped: nothing records it.
 */
#include "crux_ssh_access.h"
#include "crux_ssh_access_port.h"
#include "crux_ssh_callbacks.h"
#include "ssh_check.h"

#include <string.h>

static void test_a_report_of_each_type_returns_and_is_left_unchanged(void)
{
    const crux_ssh_access_event_type_t types[] = {CRUX_SSH_ACCESS_EVENT_AUTH_LIMIT,
                                                  CRUX_SSH_ACCESS_EVENT_HOST_KEY_MISSING};

    for (size_t i = 0; i < sizeof(types) / sizeof(types[0]); ++i) {
        crux_ssh_access_event_t report = {.type = types[i],
                                          .channel = CRUX_SSH_ACCESS_EVENT_CHANNEL,
                                          .source_length = 4u,
                                          .source = {192, 0, 2, 9}};
        const crux_ssh_access_event_t before = report;

        crux_ssh_access_port_event(&report);
        SSH_CHECK(report.type == before.type);
        SSH_CHECK(report.channel == before.channel);
        SSH_CHECK(report.source_length == before.source_length);
        SSH_CHECK(memcmp(report.source, before.source, sizeof(report.source)) == 0);
    }
}

static void test_a_null_report_returns(void)
{
    crux_ssh_access_port_event(NULL);
    SSH_CHECK(true);
}

static void test_the_adapter_entry_point_returns_through_it(void)
{
    const crux_ssh_peer_t peer = {.address = {198, 51, 100, 4}, .address_length = 4};

    crux_ssh_access_auth_limit(NULL, &peer);
    SSH_CHECK(peer.address_length == 4 && peer.address[0] == 198);
}

int main(void)
{
    test_a_report_of_each_type_returns_and_is_left_unchanged();
    test_a_null_report_returns();
    test_the_adapter_entry_point_returns_through_it();
    printf("%u failures\n", ssh_check_failures);
    return ssh_check_failures == 0 ? 0 : 1;
}
