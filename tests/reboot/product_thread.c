/* A composition that runs the worker on a thread of its own, so that its policy callback knows the
 * second check, the one just before the reset, by the calling thread. See "A final check before the
 * reset" in docs/reboot-service.md. Requests come from other threads, as from a server thread. */
#include "reboot_test.h"

#include <pthread.h>

/* True on the product's reboot thread only. */
static _Thread_local bool on_reboot_thread;

/* A stand-in for a marker in retained memory. */
static bool marked;
static size_t marker_writes, second_checks;

static bool product_policy(void *context, crux_reboot_refusal_t *refusal)
{
    bool allow = reboot_policy_callback(context, refusal);

    if (on_reboot_thread) {
        ++second_checks;
        if (allow) {
            marked = true;
            ++marker_writes;
        }
    }
    return allow;
}

typedef struct {
    bool worked;
    bool marked_at_return;
} pass_t;

static void *reboot_thread_pass(void *argument)
{
    pass_t *pass = argument;

    on_reboot_thread = true;
    pass->worked = crux_reboot_work_once();
    /* It returned, so no reset happened. */
    pass->marked_at_return = marked;
    marked = false;
    return NULL;
}

/* One pass of the product's loop, on a thread that is not the requester's. */
static pass_t run_pass(void)
{
    pthread_t thread;
    pass_t pass = {false, false};

    CHECK(pthread_create(&thread, NULL, reboot_thread_pass, &pass) == 0);
    CHECK(pthread_join(thread, NULL) == 0);
    return pass;
}

static void product_start(void)
{
    crux_reboot_config_t config = reboot_config();

    reboot_boot();
    config.policy = product_policy;
    CHECK(crux_reboot_start(&config) == CRUX_REBOOT_OK);
}

static void request(void)
{
    CHECK(crux_reboot_request(s_rebooter, NULL) == CRUX_REBOOT_OK);
}

static void only_the_second_check_runs_on_the_product_thread(void)
{
    pass_t pass;
    size_t count;

    product_start();
    pass = run_pass();
    CHECK(!pass.worked && second_checks == 0u);
    request();
    CHECK(reboot_policy_calls() == 1u && second_checks == 0u && !marked);
    pass = run_pass();
    CHECK(pass.worked && pass.marked_at_return);
    CHECK(reboot_policy_calls() == 2u && second_checks == 1u && marker_writes == 1u);
    /* The reset follows the allowing check directly. The last step is the failure event. */
    count = reboot_trace_count();
    CHECK(count >= 3u);
    if (count >= 3u) {
        CHECK(reboot_trace_get(count - 3u)->kind == STEP_POLICY);
        CHECK(reboot_trace_get(count - 2u)->kind == STEP_RESET);
    }
    CHECK(reboot_state_of(s_admin).failure == CRUX_REBOOT_FAILURE_RESET_RETURNED);
}

static void a_refusing_second_check_writes_no_marker(void)
{
    const bool script[] = {true, false};
    pass_t pass;

    product_start();
    reboot_policy_script(script, 2u);
    request();
    pass = run_pass();
    CHECK(pass.worked && !pass.marked_at_return);
    CHECK(second_checks == 1u && marker_writes == 0u && reboot_reset_calls() == 0u);
}

static void expect_no_second_check(crux_reboot_failure_t failure)
{
    pass_t pass = run_pass();

    CHECK(pass.worked && !pass.marked_at_return);
    CHECK(second_checks == 0u && marker_writes == 0u && reboot_reset_calls() == 0u);
    CHECK(reboot_state_of(s_admin).failure == failure);
}

static void a_save_in_flight_makes_no_second_check(void)
{
    product_start();
    request();
    reboot_source_busy(0u, REBOOT_FOREVER);
    expect_no_second_check(CRUX_REBOOT_FAILURE_SAVE_IN_FLIGHT);
    /* The first check of the next request is the policy's second call, and is not taken for a
     * second check. */
    reboot_source_busy(0u, 0u);
    request();
    CHECK(reboot_policy_calls() == 2u && second_checks == 0u && !marked);
    CHECK(run_pass().marked_at_return);
    CHECK(second_checks == 1u && marker_writes == 1u);
}

static void a_job_that_cannot_sleep_makes_no_second_check(void)
{
    product_start();
    reboot_sleep_fails_from(1u);
    request();
    expect_no_second_check(CRUX_REBOOT_FAILURE_NO_TIMER);
}

static void *post_again(void *argument)
{
    (void)argument;
    request();
    return NULL;
}

static void post_from_another_thread(uint64_t elapsed_ms)
{
    pthread_t thread;

    (void)elapsed_ms;
    CHECK(pthread_create(&thread, NULL, post_again, NULL) == 0);
    CHECK(pthread_join(thread, NULL) == 0);
}

static void a_request_while_pending_adds_no_check(void)
{
    product_start();
    request();
    /* Inside the delay, the only sleep of this job. */
    reboot_sleep_hook(post_from_another_thread);
    CHECK(run_pass().marked_at_return);
    CHECK(reboot_events_of(CRUX_REBOOT_EVENT_REQUESTED) == 2u);
    CHECK(reboot_policy_calls() == 2u && second_checks == 1u && marker_writes == 1u);
}

int main(void)
{
    reboot_run_case("only the second check runs on the product thread",
                    only_the_second_check_runs_on_the_product_thread);
    reboot_run_case("a refusing second check writes no marker",
                    a_refusing_second_check_writes_no_marker);
    reboot_run_case("a save in flight makes no second check",
                    a_save_in_flight_makes_no_second_check);
    reboot_run_case("a job that cannot sleep makes no second check",
                    a_job_that_cannot_sleep_makes_no_second_check);
    reboot_run_case("a request while pending adds no check", a_request_while_pending_adds_no_check);
    return reboot_finish("reboot_product_thread");
}
