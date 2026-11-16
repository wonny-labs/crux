/*
 * SPDX-License-Identifier: Apache-2.0
 */

#include <zephyr/ztest.h>

ZTEST_SUITE(acme_hw_module, NULL, NULL, NULL, NULL, NULL);

ZTEST(acme_hw_module, test_module_kconfig_is_sourced)
{
	zassert_true(IS_ENABLED(CONFIG_ACMECO_HW), "the acme-hw module was not found by the build");
}
