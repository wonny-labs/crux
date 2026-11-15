/* SPDX-License-Identifier: Apache-2.0 */
/* TEST ONLY: the first account of the image, from a password file embedded at build time. This file
 * is compiled only when CONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT is set, which is off by default
 * (Kconfig, CMakeLists.txt).
 *
 * Why it exists: the first account may be created on the serial channel only, and no image composes
 * the serial console (docs/management-in-a-product.md), so without this form the image has no
 * account and nobody can log in. A product does not do this: it creates its first account in a
 * serial setup step, from a password a person types.
 *
 * The bytes are read in place and never copied, printed or logged: the lines below name the account
 * and a result code only. Access takes a plaintext password, so the plaintext is in the image's
 * read-only data. */
#ifndef CONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT
#error "The embedded first account is declared only with CONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT"
#endif

#include "composition.h"

#include <crux_access_adapter.h>

#include <stdint.h>
#include <zephyr/sys/printk.h>

#define TEST_ACCOUNT_USER "admin"
#define TEST_ACCOUNT_ROLE "administrator"

/* Defined by the assembler file that CMake writes beside the build, from the password file. */
extern const uint8_t crux_mbed_mgmt_test_password[];
extern const uint32_t crux_mbed_mgmt_test_password_size;

bool composition_first_account_test(void)
{
    static const crux_access_origin_t serial = {.channel = CRUX_ACCESS_CHANNEL_SERIAL};
    crux_access_result_t result = crux_access_provision_first_account(
        TEST_ACCOUNT_USER, (const char *)crux_mbed_mgmt_test_password,
        crux_mbed_mgmt_test_password_size, TEST_ACCOUNT_ROLE, &serial);

    if (result != CRUX_ACCESS_OK) {
        printk("MBED-MGMT TEST ONLY first account failed: result=%d\n", (int)result);
        return false;
    }
    printk("MBED-MGMT TEST ONLY first account created: user=%s role=%s\n", TEST_ACCOUNT_USER,
           TEST_ACCOUNT_ROLE);
    return true;
}
