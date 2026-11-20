/* On the port that applies nothing, as a composition links it while its application applies no
 * address: the boot report and GET must not say that anything was applied. */
#include "net_test.h"

static void saved_values_are_not_reported_as_applied(void)
{
    crux_network_boot_report_t report = {0};
    crux_network_state_t state;
    const net_options_t keep = {true, 0, false};

    config_fault_reset();
    net_store_set(&net_set_a, true);
    net_boot_with(&keep, &report);
    CHECK(!report.applied);
    CHECK(report.source == CRUX_NETWORK_SOURCE_DEFAULT);
    /* The port declines the saved values and then the defaults, as one that refuses both would. */
    CHECK(report.reason == CRUX_NETWORK_BOOT_APPLY_FAILED);
    CHECK(net_same(&report.values, &net_defaults));
    CHECK(report.persistence);

    /* The saved values stay saved, and the next boot would use them on a port that applies. */
    CHECK(crux_config_service_start(net_table(), NET_TABLE_ENTRIES) == CRUX_CONFIG_SERVICE_OK);
    CHECK(crux_network_settings_start() == CRUX_NETWORK_OK);
    CHECK(crux_network_settings_get(s_both, &state) == CRUX_NETWORK_OK);
    CHECK(state.source == CRUX_NETWORK_SOURCE_DEFAULT);
    CHECK(state.has_saved && net_same(&state.saved, &net_set_a));
    CHECK(!state.has_running && !state.reboot_required);
}

static void defaults_are_not_reported_as_applied(void)
{
    crux_network_boot_report_t report = {0};

    net_boot(&report);
    CHECK(!report.applied);
    CHECK(report.source == CRUX_NETWORK_SOURCE_DEFAULT);
    CHECK(report.reason == CRUX_NETWORK_BOOT_NOT_STORED);
    CHECK(net_same(&report.values, &net_defaults));
}

int main(void)
{
    net_run_case("saved values are not reported as applied",
                 saved_values_are_not_reported_as_applied);
    net_run_case("defaults are not reported as applied", defaults_are_not_reported_as_applied);
    return net_finish("network_settings_no_apply");
}
