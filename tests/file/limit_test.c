/*
 * Root byte limits on the fake provider: the rounding rule and its overflow, a binding that finds a
 * root above its limit, provider failures, and the count after a restart. The cases that every
 * provider shares are in conformance.c.
 */
#include "fake_file.h"
#include "file_port.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

#define UNIT ((size_t)16)
#define ROOT ((crux_file_root_t)0)

static uint8_t data[8 * UNIT];

static void start(void)
{
    crux_file_fake_reset();
}

static crux_file_t *open_file(const char *name, crux_file_mode_t mode)
{
    crux_file_t *file = NULL;
    assert(crux_file_open_at(ROOT, name, mode, &file) == CRUX_FILE_OK);
    return file;
}

static void write_ok(crux_file_t *file, size_t length)
{
    size_t count = 0;
    assert(crux_file_write(file, data, length, &count) == CRUX_FILE_OK && count == length);
}

static void write_refused(crux_file_t *file, size_t length)
{
    size_t count = 99;
    unsigned calls = crux_file_fake_calls(CRUX_FILE_FAKE_WRITE);
    assert(crux_file_write(file, data, length, &count) == CRUX_FILE_ERR_NO_SPACE && count == 0);
    assert(crux_file_fake_calls(CRUX_FILE_FAKE_WRITE) == calls);
}

static void create_refused(const char *name)
{
    crux_file_t *file = NULL;
    unsigned opens = crux_file_fake_calls(CRUX_FILE_FAKE_OPEN);
    assert(crux_file_open_at(ROOT, name, CRUX_FILE_CREATE_REPLACE, &file) ==
           CRUX_FILE_ERR_NO_SPACE);
    assert(file == NULL && !crux_file_fake_exists(ROOT, name));
    assert(crux_file_fake_calls(CRUX_FILE_FAKE_OPEN) == opens);
}

static void close_file(crux_file_t **file)
{
    assert(crux_file_close(file) == CRUX_FILE_OK);
}

static void test_charge_rounds_up_with_a_minimum_and_saturates(void)
{
    assert(crux_file_limit_charge(0, 512) == 512);
    assert(crux_file_limit_charge(1, 512) == 512);
    assert(crux_file_limit_charge(512, 512) == 512);
    assert(crux_file_limit_charge(513, 512) == 1024);
    assert(crux_file_limit_charge(0, 1) == 1);
    assert(crux_file_limit_charge(7, 1) == 7);
    assert(crux_file_limit_charge(7, 0) == 7);
    assert(crux_file_limit_charge(UINT64_MAX, 1) == UINT64_MAX);
    assert(crux_file_limit_charge(UINT64_MAX - 1, 4096) == UINT64_MAX);
    assert(crux_file_limit_charge(UINT64_MAX - 4095, 4096) == UINT64_MAX - 4095);
    assert(crux_file_limit_charge(1, UINT64_MAX) == UINT64_MAX);
    assert(crux_file_limit_charge(2, UINT64_MAX) == UINT64_MAX);
}

/* A limited bind of the fake has the same argument checks as the real ones. */
static void test_a_refused_binding_leaves_the_root_unbound(void)
{
    start();
    crux_file_info_t info;
    assert(crux_file_fake_bind_root_limited(ROOT, "/v", 0, UNIT) == CRUX_FILE_ERR_INVALID_ARGUMENT);
    assert(crux_file_stat(ROOT, "x", &info) == CRUX_FILE_ERR_NOT_READY);

    /* The binding lists the root, and a failed listing leaves it unbound and free to bind again. */
    crux_file_fake_fail(CRUX_FILE_FAKE_DIR_OPEN, 0, CRUX_FILE_ERR_IO);
    assert(crux_file_fake_bind_root_limited(ROOT, "/v", 4 * UNIT, UNIT) == CRUX_FILE_ERR_IO);
    assert(crux_file_stat(ROOT, "x", &info) == CRUX_FILE_ERR_NOT_READY);
    crux_file_fake_add_file(ROOT, "seed", UNIT);
    crux_file_fake_fail(CRUX_FILE_FAKE_DIR_READ, 0, CRUX_FILE_ERR_IO);
    assert(crux_file_fake_bind_root_limited(ROOT, "/v", 4 * UNIT, UNIT) == CRUX_FILE_ERR_IO);
    assert(crux_file_fake_calls(CRUX_FILE_FAKE_DIR_CLOSE) == 1);
    crux_file_fake_fail(CRUX_FILE_FAKE_DIR_CLOSE, 0, CRUX_FILE_ERR_IO);
    assert(crux_file_fake_bind_root_limited(ROOT, "/v", 4 * UNIT, UNIT) == CRUX_FILE_ERR_IO);
    assert(crux_file_stat(ROOT, "seed", &info) == CRUX_FILE_ERR_NOT_READY);

    /* The listing needs a free listing handle. */
    assert(crux_file_fake_bind_root(1, "/w") == CRUX_FILE_OK);
    crux_file_dir_t *pool[CRUX_FILE_DIR_POOL_SIZE] = {0};
    for (size_t i = 0; i < CRUX_FILE_DIR_POOL_SIZE; i++) {
        assert(crux_file_dir_open(1, &pool[i]) == CRUX_FILE_OK);
    }
    assert(crux_file_fake_bind_root_limited(ROOT, "/v", 4 * UNIT, UNIT) ==
           CRUX_FILE_ERR_NO_RESOURCES);
    for (size_t i = 0; i < CRUX_FILE_DIR_POOL_SIZE; i++) {
        assert(crux_file_dir_close(&pool[i]) == CRUX_FILE_OK);
    }

    assert(crux_file_fake_bind_root_limited(ROOT, "/v", 4 * UNIT, UNIT) == CRUX_FILE_OK);
    assert(crux_file_stat(ROOT, "seed", &info) == CRUX_FILE_OK);
}

/* Bind finds 5 units in a root of 4: overwriting and shrinking work, and nothing grows until the
 * files are within the limit again. */
static void test_a_root_found_above_its_limit_only_overwrites_and_shrinks(void)
{
    start();
    crux_file_fake_add_file(ROOT, "big", 4 * UNIT);
    crux_file_fake_add_file(ROOT, "small", 1);
    assert(crux_file_fake_bind_root_limited(ROOT, "/v", 4 * UNIT, UNIT) == CRUX_FILE_OK);

    crux_file_t *big = open_file("big", CRUX_FILE_READ_WRITE);
    write_ok(big, 4 * UNIT);
    write_refused(big, 1);
    close_file(&big);
    crux_file_t *small = open_file("small", CRUX_FILE_READ_WRITE);
    assert(crux_file_seek(small, 1) == CRUX_FILE_OK);
    write_ok(small, UNIT - 1); /* Inside its unit. */
    write_refused(small, 1);
    close_file(&small);
    create_refused("new");

    /* CREATE_REPLACE shrinks big to one unit: 2 units in all. */
    big = open_file("big", CRUX_FILE_CREATE_REPLACE);
    write_ok(big, UNIT + 1);
    close_file(&big);
    crux_file_t *fresh = open_file("new", CRUX_FILE_CREATE_REPLACE);
    write_refused(fresh, UNIT + 1);
    close_file(&fresh);
}

/* Counts that would pass UINT64_MAX saturate, so they never wrap to a small number. */
static void test_counts_saturate_instead_of_wrapping(void)
{
    const uint64_t half = UINT64_C(1) << 63;
    start();
    assert(crux_file_fake_bind_root_limited(ROOT, "/v", UINT64_MAX, half) == CRUX_FILE_OK);
    crux_file_t *a = open_file("a", CRUX_FILE_CREATE_REPLACE);
    close_file(&a);
    create_refused("b"); /* 2^64 does not fit, although 0 would. */

    start();
    crux_file_fake_add_file(ROOT, "a", 1);
    crux_file_fake_add_file(ROOT, "b", 1);
    crux_file_fake_add_file(ROOT, "c", 1);
    assert(crux_file_fake_bind_root_limited(ROOT, "/v", UINT64_MAX, half) == CRUX_FILE_OK);
    create_refused("d");
    a = open_file("a", CRUX_FILE_READ_WRITE);
    write_ok(a, 1);
    close_file(&a);
}

/* After a failed write the position is unknown: the next write counts as if it started at the end,
 * until a seek. */
static void test_a_failed_write_counts_from_the_end_until_a_seek(void)
{
    start();
    assert(crux_file_fake_bind_root_limited(ROOT, "/v", 2 * UNIT, UNIT) == CRUX_FILE_OK);
    crux_file_t *a = open_file("a", CRUX_FILE_CREATE_REPLACE);
    write_ok(a, 2 * UNIT);
    assert(crux_file_seek(a, 0) == CRUX_FILE_OK);
    size_t count = 0;
    crux_file_fake_fail(CRUX_FILE_FAKE_WRITE, 0, CRUX_FILE_ERR_IO);
    assert(crux_file_write(a, data, 1, &count) == CRUX_FILE_ERR_IO);
    write_refused(a, 1);
    assert(crux_file_seek(a, 0) == CRUX_FILE_OK);
    write_ok(a, 1);
    close_file(&a);

    /* The size is read again after a failure, so a write that failed without growing costs
     * nothing. */
    a = open_file("a", CRUX_FILE_CREATE_REPLACE);
    crux_file_fake_fail(CRUX_FILE_FAKE_WRITE, 0, CRUX_FILE_ERR_IO);
    assert(crux_file_write(a, data, 2 * UNIT, &count) == CRUX_FILE_ERR_IO);
    close_file(&a);
    crux_file_t *b = open_file("b", CRUX_FILE_CREATE_REPLACE);
    close_file(&b);

    /* When the size cannot be read either, the furthest end counts: a counts 2 units while it is
     * open, which leaves no room for c. Its close counts what the file holds, and c fits. */
    start();
    assert(crux_file_fake_bind_root_limited(ROOT, "/v", 3 * UNIT, UNIT) == CRUX_FILE_OK);
    a = open_file("a", CRUX_FILE_CREATE_REPLACE);
    crux_file_fake_fail(CRUX_FILE_FAKE_WRITE, 0, CRUX_FILE_ERR_IO);
    crux_file_fake_fail(CRUX_FILE_FAKE_SIZE, 0, CRUX_FILE_ERR_IO);
    assert(crux_file_write(a, data, 2 * UNIT, &count) == CRUX_FILE_ERR_IO);
    b = open_file("b", CRUX_FILE_CREATE_REPLACE);
    close_file(&b);
    create_refused("c");
    close_file(&a);
    crux_file_t *c = open_file("c", CRUX_FILE_CREATE_REPLACE);
    close_file(&c);
    create_refused("d");

    /* Retries on a handle whose size stays unreadable, as on a LittleFS handle that keeps its
     * error, raise its count until it reaches the limit; the close gives all of it back. */
    start();
    assert(crux_file_fake_bind_root_limited(ROOT, "/v", 4 * UNIT, UNIT) == CRUX_FILE_OK);
    a = open_file("a", CRUX_FILE_CREATE_REPLACE);
    for (unsigned i = 0; i < 2; i++) {
        crux_file_fake_fail(CRUX_FILE_FAKE_WRITE, 0, CRUX_FILE_ERR_IO);
        crux_file_fake_fail(CRUX_FILE_FAKE_SIZE, 0, CRUX_FILE_ERR_IO);
        assert(crux_file_write(a, data, 2 * UNIT, &count) == CRUX_FILE_ERR_IO);
    }
    write_refused(a, 1);
    create_refused("b");
    close_file(&a);
    b = open_file("b", CRUX_FILE_CREATE_REPLACE);
    write_ok(b, 2 * UNIT);
    close_file(&b);
    assert(crux_file_remove_at(ROOT, "a") == CRUX_FILE_OK);
    c = open_file("c", CRUX_FILE_CREATE_REPLACE);
    write_ok(c, 2 * UNIT);
    close_file(&c);

    /* A partial write counts the bytes that the provider accepted. */
    start();
    assert(crux_file_fake_bind_root_limited(ROOT, "/v", 2 * UNIT, UNIT) == CRUX_FILE_OK);
    a = open_file("a", CRUX_FILE_CREATE_REPLACE);
    crux_file_fake_limit_write(UNIT);
    assert(crux_file_write(a, data, 2 * UNIT, &count) == CRUX_FILE_PARTIAL && count == UNIT);
    crux_file_fake_limit_write(SIZE_MAX);
    b = open_file("b", CRUX_FILE_CREATE_REPLACE);
    write_refused(b, UNIT + 1);
    close_file(&b);
    close_file(&a);
}

/* Failed opens and removes count what the file system holds afterwards. */
static void test_failed_opens_and_removes_count_what_is_left(void)
{
    start();
    crux_file_fake_add_file(ROOT, "seed", 3 * UNIT);
    assert(crux_file_fake_bind_root_limited(ROOT, "/v", 4 * UNIT, UNIT) == CRUX_FILE_OK);
    crux_file_t *file = NULL;

    /* A truncate that fails leaves the seed as it was, and it still counts 3 units. */
    crux_file_fake_fail(CRUX_FILE_FAKE_TRUNCATE, 0, CRUX_FILE_ERR_IO);
    assert(crux_file_open_at(ROOT, "seed", CRUX_FILE_CREATE_REPLACE, &file) == CRUX_FILE_ERR_IO);
    crux_file_t *x = open_file("x", CRUX_FILE_CREATE_REPLACE);
    close_file(&x);
    create_refused("y");

    /* A stat that fails before a writer opens refuses the open and touches nothing. */
    crux_file_fake_fail(CRUX_FILE_FAKE_STAT, 0, CRUX_FILE_ERR_IO);
    unsigned opens = crux_file_fake_calls(CRUX_FILE_FAKE_OPEN);
    assert(crux_file_open_at(ROOT, "y", CRUX_FILE_CREATE_REPLACE, &file) == CRUX_FILE_ERR_IO);
    assert(crux_file_fake_calls(CRUX_FILE_FAKE_OPEN) == opens);

    /* A remove that reports an error after the entry went gives the space back. */
    crux_file_fake_remove_then_fail(CRUX_FILE_ERR_IO);
    assert(crux_file_remove_at(ROOT, "x") == CRUX_FILE_ERR_IO);
    x = open_file("x", CRUX_FILE_CREATE_REPLACE);
    close_file(&x);

    /* A remove that fails and leaves the file keeps its count. */
    crux_file_fake_fail(CRUX_FILE_FAKE_REMOVE, 0, CRUX_FILE_ERR_IO);
    assert(crux_file_remove_at(ROOT, "seed") == CRUX_FILE_ERR_IO);
    create_refused("y");

    /* Readers and unlimited roots make no extra provider calls. */
    unsigned stats = crux_file_fake_calls(CRUX_FILE_FAKE_STAT);
    crux_file_t *reader = open_file("seed", CRUX_FILE_READ);
    close_file(&reader);
    assert(crux_file_fake_bind_root(1, "/w") == CRUX_FILE_OK);
    assert(crux_file_open_at(1, "free", CRUX_FILE_CREATE_REPLACE, &file) == CRUX_FILE_OK);
    close_file(&file);
    assert(crux_file_remove_at(1, "free") == CRUX_FILE_OK);
    assert(crux_file_fake_calls(CRUX_FILE_FAKE_STAT) == stats);
}

static void cut_now(void)
{
    _exit(3);
}

static int run_child(void (*body)(void))
{
    fflush(NULL);
    pid_t child = fork();
    assert(child >= 0);
    if (child == 0) {
        body();
        _exit(0);
    }
    int status = 0;
    assert(waitpid(child, &status, 0) == child);
    assert(WIFEXITED(status));
    return WEXITSTATUS(status);
}

/* Two units reach the medium, then the power goes during a write that is not synced. */
static void first_boot(void)
{
    assert(crux_file_fake_bind_root_limited(ROOT, "/v", 4 * UNIT, UNIT) == CRUX_FILE_OK);
    crux_file_t *log = open_file("log", CRUX_FILE_CREATE_REPLACE);
    write_ok(log, 2 * UNIT);
    assert(crux_file_sync(log) == CRUX_FILE_OK);
    write_ok(log, UNIT);
    crux_file_fake_cut_after(0, cut_now);
    (void)crux_file_sync(log);
}

/* The new binding counts the two units on the medium, not the three that the first boot saw. */
static void second_boot(void)
{
    assert(crux_file_fake_bind_root_limited(ROOT, "/v", 4 * UNIT, UNIT) == CRUX_FILE_OK);
    crux_file_info_t info;
    assert(crux_file_stat(ROOT, "log", &info) == CRUX_FILE_OK && info.size == 2 * UNIT);
    crux_file_t *other = open_file("other", CRUX_FILE_CREATE_REPLACE);
    write_ok(other, 2 * UNIT);
    write_refused(other, 1);
    close_file(&other);
}

static void test_a_restart_counts_what_reached_the_medium(void)
{
    start();
    assert(run_child(first_boot) == 3);
    crux_file_fake_power_on();
    crux_file_fake_unbind_all();
    assert(run_child(second_boot) == 0);
}

int main(void)
{
    memset(data, 'd', sizeof(data));
    test_charge_rounds_up_with_a_minimum_and_saturates();
    test_a_refused_binding_leaves_the_root_unbound();
    test_a_root_found_above_its_limit_only_overwrites_and_shrinks();
    test_counts_saturate_instead_of_wrapping();
    test_a_failed_write_counts_from_the_end_until_a_seek();
    test_failed_opens_and_removes_count_what_is_left();
    test_a_restart_counts_what_reached_the_medium();
    puts("File root limits on the fake provider passed");
    return 0;
}
