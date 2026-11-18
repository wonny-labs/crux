/* A start that cannot create its semaphore. The service creates a mutex and then a semaphore, and
 * a failure of the second must not keep the first: each retry would otherwise use up one Sync
 * slot for good. --wrap=crux_semaphore_create fails the first creation, and the wraps of the
 * mutex calls count the mutexes that are alive. */
#include "reboot_test.h"

// NOLINTBEGIN(bugprone-reserved-identifier): GNU linker wrapping ABI
crux_status_t __real_crux_mutex_create(crux_mutex_t *out);
crux_status_t __wrap_crux_mutex_create(crux_mutex_t *out);
crux_status_t __real_crux_mutex_destroy(crux_mutex_t *mutex);
crux_status_t __wrap_crux_mutex_destroy(crux_mutex_t *mutex);
crux_status_t __real_crux_semaphore_create(uint32_t initial, uint32_t maximum,
                                           crux_semaphore_t *out);
crux_status_t __wrap_crux_semaphore_create(uint32_t initial, uint32_t maximum,
                                           crux_semaphore_t *out);
// NOLINTEND(bugprone-reserved-identifier)

static int live_mutexes;
static unsigned semaphore_failures_left;

crux_status_t __wrap_crux_mutex_create(crux_mutex_t *out)
{
    crux_status_t status = __real_crux_mutex_create(out);
    if (status == CRUX_OK) {
        ++live_mutexes;
    }
    return status;
}

crux_status_t __wrap_crux_mutex_destroy(crux_mutex_t *mutex)
{
    crux_status_t status = __real_crux_mutex_destroy(mutex);
    if (status == CRUX_OK) {
        --live_mutexes;
    }
    return status;
}

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters): the signature is the public one
crux_status_t __wrap_crux_semaphore_create(uint32_t initial, uint32_t maximum,
                                           crux_semaphore_t *out)
{
    if (semaphore_failures_left == 0u) {
        return __real_crux_semaphore_create(initial, maximum, out);
    }
    --semaphore_failures_left;
    return CRUX_ERR_BUSY;
}

static void a_failed_semaphore_does_not_keep_the_mutex(void)
{
    reboot_boot();
    const int before = live_mutexes;
    const crux_reboot_config_t config = reboot_config();

    semaphore_failures_left = 3u;
    for (unsigned attempt = 0; attempt < 3u; ++attempt) {
        CHECK(crux_reboot_start(&config) == CRUX_REBOOT_ERR_NOT_READY);
        CHECK(live_mutexes == before);
    }
}

int main(void)
{
    reboot_run_case("a failed semaphore does not keep the mutex",
                    a_failed_semaphore_does_not_keep_the_mutex);
    return reboot_finish("reboot_start_faults");
}
