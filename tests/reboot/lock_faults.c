/* A lock of the service that does not come in time. The server-thread calls then answer that the
 * service is busy and change nothing, and the worker's step gives up without losing the job. The
 * lock is the service's own: --wrap=crux_mutex_lock fails the wait of the length it uses for the
 * state, and the Nth of them when a case names one. A case can also run the worker just before a
 * chosen wait, which can put the end of a job between two lock sections of a request. */
#include "reboot_test.h"

// NOLINTBEGIN(bugprone-reserved-identifier): GNU linker wrapping ABI
crux_status_t __real_crux_mutex_lock(crux_mutex_t mutex, uint32_t timeout_ms);
crux_status_t __wrap_crux_mutex_lock(crux_mutex_t mutex, uint32_t timeout_ms);
// NOLINTEND(bugprone-reserved-identifier)

static uint32_t failing_wait; /* The timeout that fails, or 0 for none. */
static unsigned failing_nth;  /* Only the Nth wait of that length, counted from 1, or 0 for all. */
static unsigned seen;
static unsigned failures;
static void (*interleaved)(void); /* Runs once, before the wait that interleave_before() names. */
static unsigned waits_to_interleave;

crux_status_t __wrap_crux_mutex_lock(crux_mutex_t mutex, uint32_t timeout_ms)
{
    if (interleaved != NULL && timeout_ms == 20u && --waits_to_interleave == 0u) {
        void (*run)(void) = interleaved;

        interleaved = NULL;
        run();
    }
    if (failing_wait != 0u && timeout_ms == failing_wait) {
        ++seen;
        if (failing_nth == 0u || seen == failing_nth) {
            ++failures;
            return CRUX_ERR_TIMEOUT;
        }
    }
    return __real_crux_mutex_lock(mutex, timeout_ms);
}

// NOLINTNEXTLINE(bugprone-easily-swappable-parameters): the wait and the count differ in meaning
static void fail(uint32_t wait, unsigned nth)
{
    failing_wait = wait;
    failing_nth = nth;
    seen = 0u;
}

/* Runs `run` before the Nth wait of 20 ms from now, counted from 1. No lock is held there. */
static void interleave_before(unsigned nth, void (*run)(void))
{
    interleaved = run;
    waits_to_interleave = nth;
}

static bool job_ended;

/* Runs the worker on the pending job, once: whoever calls first ends it. */
static void end_the_job(void)
{
    if (!job_ended) {
        job_ended = true;
        CHECK(crux_reboot_work_once());
    }
}

/* A policy that allows the first call, which accepts a job, and refuses every later one. */
static void accept_a_job_that_its_second_check_refuses(void)
{
    static const bool allow_once[] = {true, false};

    reboot_start();
    reboot_policy_script(allow_once, 2u);
    reboot_policy_reason("busy", 4u);
    CHECK(crux_reboot_request(s_admin, NULL) == CRUX_REBOOT_OK);
}

static void the_server_thread_calls_say_busy(void)
{
    crux_reboot_state_t state;

    reboot_start();
    fail(20u, 0u);
    CHECK(crux_reboot_get(s_admin, &state) == CRUX_REBOOT_ERR_BUSY);
    CHECK(crux_reboot_request(s_admin, NULL) == CRUX_REBOOT_ERR_BUSY);
    CHECK(failures == 2u);
    fail(0u, 0u);
    /* Nothing was queued, asked or recorded by the refusals. */
    CHECK(!crux_reboot_work_once());
    CHECK(reboot_policy_calls() == 0u && reboot_trace_count() == 0u);
    CHECK(reboot_state_of(s_admin).state == CRUX_REBOOT_STATE_NONE);
    CHECK(crux_reboot_request(s_admin, NULL) == CRUX_REBOOT_OK);
}

static void a_lock_that_is_late_after_the_policy_changes_nothing(void)
{
    reboot_start();
    /* The first lock reads whether one is pending, and the second one records the outcome. */
    fail(20u, 2u);
    CHECK(crux_reboot_request(s_admin, NULL) == CRUX_REBOOT_ERR_BUSY);
    CHECK(reboot_events_of(CRUX_REBOOT_EVENT_REQUESTED) == 0u);
    fail(0u, 0u);
    CHECK(reboot_state_of(s_admin).state == CRUX_REBOOT_STATE_NONE);
    CHECK(!crux_reboot_work_once());
    /* The same for a refusal: no state and no event, and the refusal is not claimed. */
    reboot_policy_always(false);
    fail(20u, 2u);
    CHECK(crux_reboot_request(s_admin, NULL) == CRUX_REBOOT_ERR_BUSY);
    CHECK(reboot_events_of(CRUX_REBOOT_EVENT_REFUSED) == 0u);
    fail(0u, 0u);
    CHECK(reboot_state_of(s_admin).state == CRUX_REBOOT_STATE_NONE);
}

static void the_worker_keeps_its_job_when_its_lock_is_late(void)
{
    reboot_start();
    CHECK(crux_reboot_request(s_admin, NULL) == CRUX_REBOOT_OK);
    /* The worker waits 1000 ms to take the job. A failure there leaves it pending. */
    fail(1000u, 1u);
    CHECK(!crux_reboot_work_once());
    fail(0u, 0u);
    CHECK(reboot_sleeps() == 0u && reboot_reset_calls() == 0u);
    CHECK(reboot_state_of(s_admin).state == CRUX_REBOOT_STATE_PENDING);
    CHECK(crux_reboot_work_once());
    CHECK(reboot_reset_calls() == 1u);
}

static void the_worker_ends_its_job_when_the_lock_is_late_at_the_end(void)
{
    reboot_start();
    CHECK(crux_reboot_request(s_admin, NULL) == CRUX_REBOOT_OK);
    /* The first wait of 1000 ms takes the job, and the second one ends it, and is tried again. */
    fail(1000u, 2u);
    CHECK(crux_reboot_work_once());
    CHECK(failures == 1u);
    fail(0u, 0u);
    CHECK(reboot_state_of(s_admin).state == CRUX_REBOOT_STATE_FAILED);
    CHECK(reboot_events_of(CRUX_REBOOT_EVENT_FAILED) == 1u);
}

static void a_job_that_ends_during_a_request_leaves_no_job_without_a_first_check(void)
{
    crux_reboot_state_t state;

    accept_a_job_that_its_second_check_refuses();
    /* The request finds the job pending. The worker runs before a second wait, if it makes one. */
    interleave_before(2u, end_the_job);
    CHECK(crux_reboot_request(s_rebooter, NULL) == CRUX_REBOOT_OK);
    interleaved = NULL;
    end_the_job();
    /* The request joined that job: it asked no policy, and no other job is left. */
    CHECK(!crux_reboot_work_once());
    CHECK(reboot_policy_calls() == 2u && reboot_reset_calls() == 0u);
    CHECK(reboot_events_of(CRUX_REBOOT_EVENT_REQUESTED) == 2u);
    CHECK(reboot_events_of(CRUX_REBOOT_EVENT_REFUSED) == 1u);
    state = reboot_state_of(s_admin);
    CHECK(state.state == CRUX_REBOOT_STATE_REFUSED && strcmp(state.reason, "busy") == 0);
}

static void a_job_that_ends_before_a_request_reads_the_state_leaves_it_to_the_policy(void)
{
    char reason[CRUX_REBOOT_REASON_SIZE];

    accept_a_job_that_its_second_check_refuses();
    interleave_before(1u, end_the_job);
    CHECK(crux_reboot_request(s_rebooter, reason) == CRUX_REBOOT_ERR_REFUSED);
    CHECK(job_ended && strcmp(reason, "busy") == 0);
    CHECK(!crux_reboot_work_once());
    CHECK(reboot_policy_calls() == 3u && reboot_reset_calls() == 0u);
    CHECK(reboot_events_of(CRUX_REBOOT_EVENT_REQUESTED) == 1u);
    CHECK(reboot_events_of(CRUX_REBOOT_EVENT_REFUSED) == 2u);
}

int main(void)
{
    reboot_run_case("the server-thread calls say busy", the_server_thread_calls_say_busy);
    reboot_run_case("a lock that is late after the policy changes nothing",
                    a_lock_that_is_late_after_the_policy_changes_nothing);
    reboot_run_case("the worker keeps its job when its lock is late",
                    the_worker_keeps_its_job_when_its_lock_is_late);
    reboot_run_case("the worker ends its job when the lock is late at the end",
                    the_worker_ends_its_job_when_the_lock_is_late_at_the_end);
    reboot_run_case("a job that ends during a request leaves no job without a first check",
                    a_job_that_ends_during_a_request_leaves_no_job_without_a_first_check);
    reboot_run_case("a job that ends before a request reads the state leaves it to the policy",
                    a_job_that_ends_before_a_request_reads_the_state_leaves_it_to_the_policy);
    return reboot_finish("reboot_lock_faults");
}
