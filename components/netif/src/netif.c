#include "netif_port.h"
#include <string.h>

crux_status_t crux_netif_get_status(crux_netif_status_t *out)
{
    if (out == NULL) {
        return CRUX_ERR_INVALID_ARGUMENT;
    }

    crux_netif_status_t value = {0};
    crux_status_t result = crux_netif_observe(&value);
    if (result == CRUX_OK) {
        if (!value.ipv4_available) {
            memset(value.ipv4_address, 0, sizeof(value.ipv4_address));
        }
        *out = value;
    }

    return result;
}

bool crux_netif_ipv4_eligible(const uint8_t address[4], uint32_t netmask)
{
    if (address[0] == 0 || address[0] >= 224 || (address[0] == 169 && address[1] == 254)) {
        return false;
    }

    uint32_t ip = 0;
    for (unsigned int i = 0; i < 4; ++i) {
        ip = (ip << 8) | address[i];
    }

    /* Up to /30 the all-zero host part is the network address and the all-ones one the directed
     * broadcast. /31 and /32 have neither. */
    uint32_t hostmask = ~netmask;
    uint32_t host = ip & hostmask;
    return hostmask <= 1 || (host != 0 && host != hostmask);
}
