#include "product_policy.h"

#include <crux/config_service.h>
#include <crux/management_status.h>
#include <crux/security_event.h>

#include <stddef.h>

#define COUNT(array) (sizeof(array) / sizeof((array)[0]))

static const char *const administrator_permissions[] = {
    PRODUCT_PERMISSION_DEMO,
    CRUX_ACCESS_PERMISSION_MANAGE,
    CRUX_SECURITY_EVENT_PERMISSION_READ,
    CRUX_MGMT_STATUS_PERMISSION_READ,
    CRUX_CONFIG_SERVICE_PERMISSION_SAVE,
    "config.read",
    "config.write",
    "network.read",
    "network.write",
    "system.reboot",
    "file.read",
    "file.write",
};
static const char *const guest_permissions[] = {"guest.only"};
static const crux_access_role_t roles[] = {
    {PRODUCT_ROLE_GUEST, guest_permissions, COUNT(guest_permissions)},
    {PRODUCT_ROLE_ADMINISTRATOR, administrator_permissions, COUNT(administrator_permissions)},
};
static const crux_access_policy_t policy = {roles, COUNT(roles), 15u * 60u, 8u * 3600u, NULL};

const crux_access_policy_t *product_policy(void)
{
    return &policy;
}
