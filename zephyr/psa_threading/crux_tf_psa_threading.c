/*
 * Gives TF-PSA-Crypto's core its locks, on the Mbed profile, before anything in the image uses it.
 * Without them, the Access and store providers and TLS threads share a key table and a random
 * source with nothing to order them, and a lock of Crux's could cover only Crux's own calls.
 */
#include <mbedtls/threading.h>
#include <zephyr/init.h>
#include <zephyr/kernel.h>

#ifdef CRUX_PSA_THREADING_TEST_COUNTER
/* Native_sim test fixtures only (see CMakeLists.txt): shows that the core takes the locks. A product
 * image has no counter and no atomic on the lock path. */
static atomic_t lock_count;
#define COUNT_LOCK() atomic_inc(&lock_count)
uint32_t crux_tf_psa_threading_lock_count(void);
uint32_t crux_tf_psa_threading_lock_count(void)
{
    return (uint32_t)atomic_get(&lock_count);
}
#else
#define COUNT_LOCK() ((void)0)
#endif

static int mutex_init(mbedtls_platform_mutex_t *mutex)
{
    return k_mutex_init(mutex) == 0 ? 0 : MBEDTLS_ERR_THREADING_USAGE_ERROR;
}

static void mutex_destroy(mbedtls_platform_mutex_t *mutex)
{
    ARG_UNUSED(mutex);
}

static int mutex_lock(mbedtls_platform_mutex_t *mutex)
{
    COUNT_LOCK();
    return k_mutex_lock(mutex, K_FOREVER) == 0 ? 0 : MBEDTLS_ERR_THREADING_USAGE_ERROR;
}

static int mutex_unlock(mbedtls_platform_mutex_t *mutex)
{
    return k_mutex_unlock(mutex) == 0 ? 0 : MBEDTLS_ERR_THREADING_USAGE_ERROR;
}

static int cond_init(mbedtls_platform_condition_variable_t *condition)
{
    return k_condvar_init(condition) == 0 ? 0 : MBEDTLS_ERR_THREADING_USAGE_ERROR;
}

static void cond_destroy(mbedtls_platform_condition_variable_t *condition)
{
    ARG_UNUSED(condition);
}

static int cond_signal(mbedtls_platform_condition_variable_t *condition)
{
    return k_condvar_signal(condition) == 0 ? 0 : MBEDTLS_ERR_THREADING_USAGE_ERROR;
}

static int cond_broadcast(mbedtls_platform_condition_variable_t *condition)
{
    return k_condvar_broadcast(condition) >= 0 ? 0 : MBEDTLS_ERR_THREADING_USAGE_ERROR;
}

static int cond_wait(mbedtls_platform_condition_variable_t *condition,
                     mbedtls_platform_mutex_t *mutex)
{
    return k_condvar_wait(condition, mutex, K_FOREVER) == 0 ? 0 : MBEDTLS_ERR_THREADING_USAGE_ERROR;
}

/* Before the module's own start, which sets up the heap and initialises PSA at the default
 * priority. */
static int crux_tf_psa_threading_start(void)
{
    mbedtls_threading_set_alt(mutex_init, mutex_destroy, mutex_lock, mutex_unlock, cond_init,
                              cond_destroy, cond_signal, cond_broadcast, cond_wait);
    return 0;
}
SYS_INIT(crux_tf_psa_threading_start, POST_KERNEL, 0);
