/* SPDX-License-Identifier: Apache-2.0 */
/* The management services of this image: the order of docs/management-in-a-product.md, the policy,
 * and one reference parameter. The services themselves come from the Zephyr module under their
 * Kconfig symbols. The web lifecycle headers are the private ones until ADR-0004 phase 1a publishes
 * them (see the transitional list in tests/build/test_management_mbed_rt1060_image.py). */
#include "composition.h"

#include "medium.h"

#include "crux_web_adapter.h"
#include "crux_web_management.h"
#include "crux_web_session.h"

#include <crux/access.h>
#include <crux/config_service.h>
#include <crux/configuration.h>
#include <crux/credential_store.h>
#include <crux/file_service.h>
#include <crux/file_zephyr.h>
#include <crux/management_status.h>
#include <crux/network_settings.h>
#include <crux/reboot.h>
#include <crux/security_event.h>
#include <crux/system.h>
#include <crux/time.h>
#include <crux/tls_certificate_start.h>

#include <errno.h>
#include <string.h>
#include <zephyr/fs/fs.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/tls_credentials.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/util.h>

enum { ROOT_SLOT_A = 1, ROOT_SLOT_B = 2, ROOT_FILES = 3 };
#define PATH_SLOT_A MEDIUM_MOUNT_POINT "/secure-a"
#define PATH_SLOT_B MEDIUM_MOUNT_POINT "/secure-b"
#define PATH_FILES MEDIUM_MOUNT_POINT "/files"
#define FILE_AREA "files"
#define PERMISSION_FILE_READ "file.read"
#define PERMISSION_FILE_WRITE "file.write"
#define PERMISSION_CONFIG_READ "config.read"
#define PERMISSION_CONFIG_WRITE "config.write"
#define PARAM_NAME "device.name"

static const char *const viewer_permissions[] = {
    CRUX_MGMT_STATUS_PERMISSION_READ, PERMISSION_CONFIG_READ, CRUX_NETWORK_SETTINGS_PERMISSION_READ,
    PERMISSION_FILE_READ};
static const char *const operator_permissions[] = {
    CRUX_MGMT_STATUS_PERMISSION_READ,      PERMISSION_CONFIG_READ, PERMISSION_CONFIG_WRITE,
    CRUX_NETWORK_SETTINGS_PERMISSION_READ, PERMISSION_FILE_READ,   PERMISSION_FILE_WRITE};
static const char *const administrator_permissions[] = {
    CRUX_MGMT_STATUS_PERMISSION_READ,
    PERMISSION_CONFIG_READ,
    PERMISSION_CONFIG_WRITE,
    CRUX_CONFIG_SERVICE_PERMISSION_SAVE,
    CRUX_SECURITY_EVENT_PERMISSION_READ,
    CRUX_ACCESS_PERMISSION_MANAGE,
    CRUX_NETWORK_SETTINGS_PERMISSION_READ,
    CRUX_NETWORK_SETTINGS_PERMISSION_WRITE,
    CRUX_REBOOT_PERMISSION,
    PERMISSION_FILE_READ,
    PERMISSION_FILE_WRITE,
};
static const crux_access_role_t roles[] = {
    {"viewer", viewer_permissions, ARRAY_SIZE(viewer_permissions)},
    {"operator", operator_permissions, ARRAY_SIZE(operator_permissions)},
    {"administrator", administrator_permissions, ARRAY_SIZE(administrator_permissions)},
};
static const crux_access_policy_t policy = {roles, ARRAY_SIZE(roles), 15u * 60u, 8u * 3600u, NULL};

/* One reference parameter, so that the configuration routes have something to list. A product names
 * its own. */
static const crux_config_spec_t spec_name = {
    .key = PARAM_NAME,
    .default_value = {.type = CRUX_CONFIG_STRING, .data.string = {"crux-rt1060", 11}},
};
static crux_config_param_t param_name;
static char storage_name[64];
static const crux_config_service_entry_t table[] = {
    {&param_name, PERMISSION_CONFIG_READ, PERMISSION_CONFIG_WRITE, false,
     CRUX_CONFIG_ACTIVATION_APPLICATION},
};
/* The reference table and then the entries of the network settings service, in the order that it
 * hands them over. */
static crux_config_service_entry_t
    services_table[ARRAY_SIZE(table) + CRUX_NETWORK_SETTINGS_ENTRY_COUNT];

static crux_credential_state_t state_at_start = CRUX_CREDENTIAL_STATE_UNUSABLE;
static bool certificate_generated;

/* The address of the interface, parsed once. */
static struct net_in_addr address;
static struct net_in_addr netmask;

static bool address_parse(void)
{
    return net_addr_pton(NET_AF_INET, CONFIG_CRUX_MBED_MGMT_IPV4_ADDRESS, &address) == 0 &&
           net_addr_pton(NET_AF_INET, CONFIG_CRUX_MBED_MGMT_IPV4_NETMASK, &netmask) == 0;
}

static bool failed(const char *step)
{
    printk("MBED-MGMT step failed: %s\n", step);
    return false;
}

bool composition_address_up(void)
{
    struct net_if *iface = net_if_get_default();
    struct net_if_ipv4 *ipv4;
    size_t used = 0;

    if (iface == NULL || !address_parse() ||
        net_if_ipv4_addr_add(iface, &address, NET_ADDR_MANUAL, 0) == NULL ||
        !net_if_ipv4_set_netmask_by_addr(iface, &address, &netmask)) {
        return failed("address");
    }
    int status = net_if_up(iface);
    if (status != 0 && status != -EALREADY) {
        return failed("interface up");
    }
    /* The interface has this address and no other IPv4 address, so that the listener answers on
     * this one. */
    if (net_if_config_ipv4_get(iface, &ipv4) != 0 || ipv4 == NULL) {
        return failed("address check");
    }
    for (size_t i = 0; i < NET_IF_MAX_IPV4_ADDR; i++) {
        if (!ipv4->unicast[i].ipv4.is_used) {
            continue;
        }
        used++;
        if (!net_ipv4_addr_cmp(&ipv4->unicast[i].ipv4.address.in_addr, &address)) {
            return failed("another IPv4 address on the interface");
        }
    }
    return used == 1u || failed("address count");
}

static bool directory_ready(const char *path)
{
    int result = fs_mkdir(path);
    return result == 0 || result == -EEXIST;
}

static bool medium_ready(void)
{
    if (!medium_mount()) {
        return false;
    }
    return directory_ready(PATH_SLOT_A) && directory_ready(PATH_SLOT_B) &&
           directory_ready(PATH_FILES) &&
           crux_file_zephyr_bind_root(ROOT_SLOT_A, PATH_SLOT_A) == CRUX_FILE_OK &&
           crux_file_zephyr_bind_root(ROOT_SLOT_B, PATH_SLOT_B) == CRUX_FILE_OK &&
           crux_file_zephyr_bind_root(ROOT_FILES, PATH_FILES) == CRUX_FILE_OK;
}

/* Network settings boot before the Configuration service starts, on a table that holds its entries.
 * The default is the interface's own static address. Nothing is applied to the interface: the apply
 * port applies nothing. */
static bool config_ready(void)
{
    size_t count = 0;
    uint8_t prefix = 0;
    uint32_t host_address = ((uint32_t)address.s4_addr[0] << 24) |
                            ((uint32_t)address.s4_addr[1] << 16) |
                            ((uint32_t)address.s4_addr[2] << 8) | (uint32_t)address.s4_addr[3];

    for (size_t i = 0; i < 4; i++) {
        prefix += (uint8_t)__builtin_popcount(netmask.s4_addr[i]);
    }
    const crux_network_settings_config_t network = {
        .defaults = {.address = host_address, .prefix_length = prefix, .has_gateway = false}};
    const crux_config_service_entry_t *entries = crux_network_settings_entries(&count);

    if (crux_config_init_string(&param_name, &spec_name, storage_name, sizeof(storage_name)) !=
            CRUX_CONFIG_OK ||
        entries == NULL || count != CRUX_NETWORK_SETTINGS_ENTRY_COUNT) {
        return false;
    }
    memcpy(services_table, table, sizeof(table));
    memcpy(&services_table[ARRAY_SIZE(table)], entries, sizeof(services_table[0]) * count);
    return crux_network_settings_boot(&network, NULL) == CRUX_NETWORK_OK &&
           crux_config_service_start(services_table, ARRAY_SIZE(services_table)) ==
               CRUX_CONFIG_SERVICE_OK;
}

bool composition_core_start(void)
{
    /* First, so that everything that follows can emit. */
    if (crux_security_event_init(NULL, 0) != CRUX_OK) {
        return failed("security events");
    }
    if (crux_realtime_init() != CRUX_OK) {
        return failed("time");
    }
    /* A medium that failed fails closed inside the store: it starts, and reads UNUSABLE. */
    if (!medium_ready()) {
        printk("MBED-MGMT medium not ready: the credential store will be unusable\n");
    }
    crux_credential_result_t store = crux_credential_start(ROOT_SLOT_A, ROOT_SLOT_B);
    if (store != CRUX_CREDENTIAL_OK && store != CRUX_CREDENTIAL_ERR_UNUSABLE) {
        return failed("credential store");
    }
    /* A failed read leaves the state UNUSABLE: it fails closed and no first account is created. */
    crux_credential_store_info_t info;
    state_at_start = CRUX_CREDENTIAL_STATE_UNUSABLE;
    if (crux_credential_store_get_info(&info) == CRUX_OK) {
        state_at_start = info.state;
    }
    /* An unusable store reads NOT_READY here and stays so: it fails closed. */
    crux_access_result_t access = crux_access_init(&policy);
    if (access != CRUX_ACCESS_OK && access != CRUX_ACCESS_ERR_NOT_READY) {
        return failed("access");
    }
    if (!address_parse() || !config_ready()) {
        return failed("configuration");
    }
    crux_reset_cause_t cause = {0};
    crux_mgmt_status_config_t status = {
        .platform_version = "crux",
        .project_version = "rt1060-mbed",
        .boot_reset_cause_status = crux_system_reset_cause_get(&cause),
        .boot_reset_cause = cause,
    };
    if (crux_mgmt_status_start(&status) != CRUX_OK) {
        return failed("status");
    }
    if (crux_security_event_start() != CRUX_OK) {
        return failed("security event thread");
    }
    return true;
}

crux_credential_state_t composition_store_state_at_start(void)
{
    return state_at_start;
}

/* The generated certificate to Zephyr's TLS credentials, as docs/tls-certificate.md step 6 says,
 * before the listener. */
static int tls_credentials_register(int sec_tag)
{
    static crux_tls_certificate_material_t material;

    if (crux_tls_certificate_material_take(&material) != CRUX_TLS_CERTIFICATE_OK) {
        return -ENOENT;
    }
    int result = tls_credential_add(sec_tag, TLS_CREDENTIAL_PUBLIC_CERTIFICATE,
                                    material.certificate, material.certificate_length);
    if (result == 0) {
        result = tls_credential_add(sec_tag, TLS_CREDENTIAL_PRIVATE_KEY, material.private_key,
                                    material.private_key_length);
    }
    return result;
}

static const crux_file_area_t areas[] = {{
    .name = FILE_AREA,
    .root = ROOT_FILES,
    .read_permission = PERMISSION_FILE_READ,
    .write_permission = PERMISSION_FILE_WRITE,
    .max_file_bytes = 4096u,
    .max_area_bytes = 16384u,
    .max_entries = 8u,
    .partial_suffix = NULL,
    .write_modes = CRUX_FILE_SERVICE_MANAGED,
}};
static crux_file_root_t reserved_roots[] = {ROOT_SLOT_A, ROOT_SLOT_B};

bool composition_services_start(void)
{
    /* The certificate names the DNS name and the address of the board. The module reads no clock.
     */
    static const char *const dns_names[] = {"crux-rt1060"};
    static uint8_t ipv4_names[1][4];
    static crux_tls_certificate_options_t certificate_options;
    crux_tls_certificate_start_t how = CRUX_TLS_CERTIFICATE_STARTED;

    memcpy(ipv4_names[0], address.s4_addr, 4);
    certificate_options = (crux_tls_certificate_options_t){
        .names = {.common_name = "crux rt1060 management",
                  .dns_names = dns_names,
                  .dns_count = ARRAY_SIZE(dns_names),
                  .ipv4 = (const uint8_t(*)[4])ipv4_names,
                  .ipv4_count = ARRAY_SIZE(ipv4_names)},
        .not_before_s = CRUX_TLS_CERTIFICATE_DEFAULT_NOT_BEFORE_S,
        .validity_days = 0u,
    };
    /* The device key is made inside this call, from the TRNG. */
    if (crux_tls_certificate_start(&certificate_options, &how) != CRUX_TLS_CERTIFICATE_OK) {
        return failed("tls certificate");
    }
    certificate_generated = how == CRUX_TLS_CERTIFICATE_GENERATED;
    if (crux_network_settings_start() != CRUX_NETWORK_OK ||
        crux_network_settings_start_worker() != CRUX_NETWORK_OK) {
        return failed("network settings");
    }
    /* Borrowed by the service for the program's life: static. */
    static const crux_file_service_config_t file_config = {
        .areas = areas,
        .area_count = ARRAY_SIZE(areas),
        .reserved_roots = reserved_roots,
        .reserved_root_count = ARRAY_SIZE(reserved_roots),
        .no_credential_store = false,
    };
    if (crux_file_service_start(&file_config) != CRUX_FILE_SERVICE_OK) {
        return failed("file service");
    }
    /* The restart is the application's judgement. This image states that it never refuses, and it
     * runs no machine. */
    static const crux_reboot_config_t reboot = {.policy_kind = CRUX_REBOOT_POLICY_ALWAYS_ALLOW};
    if (crux_reboot_start(&reboot) != CRUX_REBOOT_OK ||
        crux_reboot_start_worker() != CRUX_REBOOT_OK) {
        return failed("reboot");
    }
    /* HTTPS only: the session module refuses "http" in a build like this one. */
    static const crux_web_session_config_t sessions = {"https", NULL, 0u};
    if (crux_web_session_init(&sessions) != CRUX_WEB_OK ||
        crux_web_session_start_worker() != CRUX_WEB_OK) {
        return failed("web session");
    }
    if (crux_web_management_init() != CRUX_WEB_OK ||
        crux_web_management_start_worker() != CRUX_WEB_OK) {
        return failed("web management");
    }
    if (tls_credentials_register(CONFIG_CRUX_WEB_TLS_SEC_TAG) != 0) {
        return failed("tls credentials");
    }
    /* Trust on first use: the user compares this with what the client shows. It is read before the
     * listener starts, so a certificate that cannot be read never has a listener. */
    char fingerprint[CRUX_TLS_CERTIFICATE_FINGERPRINT_TEXT_SIZE];
    if (crux_tls_certificate_fingerprint(fingerprint) != CRUX_TLS_CERTIFICATE_OK) {
        return failed("certificate fingerprint");
    }
    printk("MBED-MGMT certificate sha256=%s source=%s\n", fingerprint,
           certificate_generated ? "generated" : "stored");
    static const crux_web_config_t web = {
        .authenticate = crux_web_session_authenticate,
        .request_deadline_ms = CONFIG_CRUX_WEB_REQUEST_DEADLINE_MS,
        .handler_limit_ms = 100u,
    };
    if (crux_web_start(&web) != CRUX_WEB_OK) {
        return failed("https listener");
    }
    return true;
}
