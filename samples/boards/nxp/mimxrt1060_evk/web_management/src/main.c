/* SPDX-License-Identifier: Apache-2.0 */
/*
 * RT1060-EVK Rev B management image on the Mbed TLS profile (docs/rt1060-mbed-management-image.md):
 * HTTPS web management with Access, the credential store and the TLS certificate model, security
 * events to Logging on the console UART. Built here and meant to run on the board: nothing in this
 * repository flashes or resets one.
 *
 * Boot order, and what stops the image: every refusal ends in an MBED-MGMT refusing-to-start line
 * (a failed step prints its own detail line first), and nothing after it runs.
 *   1. The first random read, before anything makes a key. A failed TRNG read stops the image: no
 * key, certificate or listener is made. There is no fallback source and no test entropy.
 *   2. The static address.
 *   3. The core services: events, time, RAM disk, credential store, Access, configuration, status.
 *   4. The first account, only on an empty store, and only with the test form, which is off by
 * default.
 *   5. The services that need a key and an account store, and then the HTTPS listener.
 */
#include "composition.h"

#include "entropy_boot.h"

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

static int image_main(void)
{
    printk("MBED-MGMT evaluation image, not a product: image=crux-mgmt-rt1060-mbed board=%s "
           "tls=mbedtls address=%s test-first-account=%d\n",
           CONFIG_BOARD_TARGET, CONFIG_CRUX_MBED_MGMT_IPV4_ADDRESS,
           IS_ENABLED(CONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT));
    /* The first random read, through the same function that makes every key, and one CRUX-ENTROPY
     * line that says which device answered. tests/zephyr/entropy_boot,
     * docs/psa-crypto-qualification.md (Entropy failure). */
    if (!crux_entropy_boot_check()) {
        printk(
            "MBED-MGMT refusing to start: the first random read failed, no key or listener made\n");
        return 1;
    }
    if (!composition_address_up()) {
        printk("MBED-MGMT refusing to start: the static address could not be set\n");
        return 1;
    }
    if (!composition_core_start()) {
        printk("MBED-MGMT refusing to start: a core service did not start\n");
        return 1;
    }
    if (composition_store_state_at_start() == CRUX_CREDENTIAL_STATE_EMPTY) {
#if defined(CONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT)
        if (!composition_first_account_test()) {
            printk("MBED-MGMT refusing to start: the first account could not be made\n");
            return 1;
        }
#else
        printk("MBED-MGMT no first account: this image has no serial setup step, so nobody can log "
               "in. "
               "Build with CONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT for a bench account\n");
#endif
    }
    if (!composition_services_start()) {
        printk("MBED-MGMT refusing to start: a service did not start\n");
        return 1;
    }
    printk("MBED-MGMT ready https://%s:%d/\n", CONFIG_CRUX_MBED_MGMT_IPV4_ADDRESS,
           CONFIG_CRUX_WEB_PORT);
    return 0;
}

int main(void)
{
    return image_main();
}
