/* The progress hook of the Crux service threads on the Host: one registration per boot, a report per
 * call with the thread's identifier and the context, nothing before a registration or for an unknown
 * identifier, and reports from several threads while the registration lands. */
#include "service_priority.h"

#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>

void crux_service_progress_test_reset(void);

static unsigned checks, failures;

#define CHECK(expression)                                                                          \
    do {                                                                                           \
        ++checks;                                                                                  \
        if (!(expression)) {                                                                       \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #expression);                           \
            ++failures;                                                                            \
        }                                                                                          \
    } while (0)

static atomic_uint reports[CRUX_SERVICE_THREAD_COUNT];
static atomic_uint wrong_context;
static int context_value;

static void record(crux_service_thread_t thread, void *context)
{
    if (context != &context_value) {
        atomic_fetch_add(&wrong_context, 1u);
    }
    atomic_fetch_add(&reports[thread], 1u);
}

static void other(crux_service_thread_t thread, void *context)
{
    (void)thread;
    (void)context;
    atomic_fetch_add(&wrong_context, 1u);
}

static void begin(void)
{
    crux_service_progress_test_reset();
    for (unsigned index = 0; index < CRUX_SERVICE_THREAD_COUNT; ++index) {
        atomic_store(&reports[index], 0u);
    }
    atomic_store(&wrong_context, 0u);
}

static void registration(void)
{
    begin();
    /* Nothing is called before a registration. */
    crux_service_progress_report(CRUX_SERVICE_THREAD_CLI_CONSOLE);
    CHECK(atomic_load(&reports[CRUX_SERVICE_THREAD_CLI_CONSOLE]) == 0u);

    CHECK(crux_service_progress_register(NULL, &context_value) == CRUX_ERR_INVALID_ARGUMENT);
    CHECK(crux_service_progress_register(record, &context_value) == CRUX_OK);
    /* One per boot: a second one is refused, and the first stays. */
    CHECK(crux_service_progress_register(other, NULL) == CRUX_ERR_BUSY);
    CHECK(crux_service_progress_register(record, &context_value) == CRUX_ERR_BUSY);

    for (int thread = 0; thread < CRUX_SERVICE_THREAD_COUNT; ++thread) {
        crux_service_progress_report((crux_service_thread_t)thread);
    }
    crux_service_progress_report(CRUX_SERVICE_THREAD_WEB_SESSION_WORKER);
    for (unsigned thread = 0; thread < CRUX_SERVICE_THREAD_COUNT; ++thread) {
        unsigned expected = thread == CRUX_SERVICE_THREAD_WEB_SESSION_WORKER ? 2u : 1u;
        CHECK(atomic_load(&reports[thread]) == expected);
    }
    CHECK(atomic_load(&wrong_context) == 0u);

    /* An unknown identifier calls nothing. */
    crux_service_progress_report(CRUX_SERVICE_THREAD_COUNT);
    crux_service_progress_report((crux_service_thread_t)-1);
    unsigned total = 0;
    for (unsigned thread = 0; thread < CRUX_SERVICE_THREAD_COUNT; ++thread) {
        total += atomic_load(&reports[thread]);
    }
    CHECK(total == CRUX_SERVICE_THREAD_COUNT + 1u);
}

/* The identifiers that the priority map and the documentation number. */
static void identifiers_are_stable(void)
{
    CHECK(CRUX_SERVICE_THREAD_SECURITY_EVENT_DRAIN == 0);
    CHECK(CRUX_SERVICE_THREAD_REBOOT_WORKER == 1);
    CHECK(CRUX_SERVICE_THREAD_NETWORK_SETTINGS_WORKER == 2);
    CHECK(CRUX_SERVICE_THREAD_WEB_SESSION_WORKER == 3);
    CHECK(CRUX_SERVICE_THREAD_WEB_MANAGEMENT_WORKER == 4);
    CHECK(CRUX_SERVICE_THREAD_CLI_CONSOLE == 5);
    CHECK(CRUX_SERVICE_THREAD_COUNT == 6);
}

#define REPORTERS 4
#define PASSES 200000u

static void *reporter(void *argument)
{
    crux_service_thread_t thread = (crux_service_thread_t)(long)argument;
    for (unsigned pass = 0; pass < PASSES; ++pass) {
        crux_service_progress_report(thread);
    }
    return NULL;
}

static void registration_while_threads_report(void)
{
    /* Reports run while the registration lands: each sees nothing or the whole registration. */
    begin();
    pthread_t threads[REPORTERS];
    for (long index = 0; index < REPORTERS; ++index) {
        CHECK(pthread_create(&threads[index], NULL, reporter, (void *)index) == 0);
    }
    CHECK(crux_service_progress_register(record, &context_value) == CRUX_OK);
    for (long index = 0; index < REPORTERS; ++index) {
        CHECK(pthread_join(threads[index], NULL) == 0);
    }
    CHECK(atomic_load(&wrong_context) == 0u);
    for (unsigned index = 0; index < REPORTERS; ++index) {
        CHECK(atomic_load(&reports[index]) <= PASSES);
    }
    /* After the join every report counts. */
    crux_service_progress_report(CRUX_SERVICE_THREAD_SECURITY_EVENT_DRAIN);
    CHECK(atomic_load(&reports[CRUX_SERVICE_THREAD_SECURITY_EVENT_DRAIN]) >= 1u);
}

int main(void)
{
    identifiers_are_stable();
    registration();
    registration_while_threads_report();
    printf("service progress: %u checks, %u failures\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
