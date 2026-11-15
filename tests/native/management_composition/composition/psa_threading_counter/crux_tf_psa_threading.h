#ifndef CRUX_TF_PSA_THREADING_H
#define CRUX_TF_PSA_THREADING_H

#include <stdint.h>

/* Test only. How many times the core has taken a lock since boot, which shows that the locks
 * are in use. The module's provider (zephyr/psa_threading) compiles the counter only when a
 * native_sim fixture sets CRUX_PSA_THREADING_TEST_COUNTER before find_package(Zephyr); a product
 * image has neither the counter nor this header. */
uint32_t crux_tf_psa_threading_lock_count(void);

#endif
