/*
 * A root byte limit on the Linux provider with concurrent callers, which share the real File lock:
 * two writers that grow their own files one unit at a time, and a third caller that creates and
 * removes a file. Together they never take the root above its limit, and each refused write leaves
 * its file as it was.
 */
#include "file_linux.h"
#include <assert.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <unistd.h>

#define UNITS 48u

static uint64_t unit;
static uint8_t chunk[4096];
static volatile int writers_done;

static uint64_t charge(uint64_t size)
{
    uint64_t blocks = (size + unit - 1) / unit;
    return (blocks ? blocks : 1) * unit;
}

static void *writer(void *argument)
{
    const char *name = argument;
    crux_file_t *file = NULL;
    size_t count = 0;
    uint64_t written = 0;
    crux_file_result_t opened = crux_file_open_at(0, name, CRUX_FILE_CREATE_REPLACE, &file);
    if (opened == CRUX_FILE_ERR_NO_SPACE) {
        /* The other writer filled the root before this one started. */
        __atomic_add_fetch(&writers_done, 1, __ATOMIC_SEQ_CST);
        return NULL;
    }
    assert(opened == CRUX_FILE_OK);
    for (;;) {
        crux_file_result_t result = crux_file_write(file, chunk, (size_t)unit, &count);
        if (result == CRUX_FILE_ERR_NO_SPACE) {
            assert(count == 0);
            break;
        }
        assert(result == CRUX_FILE_OK && count == unit);
        written += unit;
    }
    uint64_t size = 0;
    assert(crux_file_size(file, &size) == CRUX_FILE_OK && size == written);
    assert(crux_file_close(&file) == CRUX_FILE_OK);
    __atomic_add_fetch(&writers_done, 1, __ATOMIC_SEQ_CST);
    return NULL;
}

/* Holds one unit at times, so the writers see the root fill and empty under them. */
static void *churn(void *argument)
{
    (void)argument;
    while (__atomic_load_n(&writers_done, __ATOMIC_SEQ_CST) < 2) {
        crux_file_t *file = NULL;
        crux_file_result_t result = crux_file_open_at(0, "churn", CRUX_FILE_CREATE_REPLACE, &file);
        assert(result == CRUX_FILE_OK || result == CRUX_FILE_ERR_NO_SPACE);
        if (result == CRUX_FILE_OK) {
            assert(crux_file_close(&file) == CRUX_FILE_OK);
            assert(crux_file_remove_at(0, "churn") == CRUX_FILE_OK);
        }
    }
    return NULL;
}

static uint64_t counted(const char *directory, const char *name)
{
    char path[128];
    struct stat st;
    assert(snprintf(path, sizeof(path), "%s/%s", directory, name) > 0);
    if (stat(path, &st) != 0) {
        return 0;
    }
    return charge((uint64_t)st.st_size);
}

int main(void)
{
    char base[] = "/tmp/crux-file-limit-XXXXXX";
    assert(mkdtemp(base));
    struct statvfs volume;
    assert(statvfs(base, &volume) == 0);
    unit = volume.f_frsize;
    assert(unit >= 1 && unit <= sizeof(chunk));
    memset(chunk, 'w', sizeof(chunk));
    assert(crux_file_linux_bind_root_limited(0, base, UNITS * unit) == CRUX_FILE_OK);

    pthread_t threads[3];
    assert(pthread_create(&threads[0], NULL, writer, "first") == 0);
    assert(pthread_create(&threads[1], NULL, writer, "second") == 0);
    assert(pthread_create(&threads[2], NULL, churn, NULL) == 0);
    for (size_t i = 0; i < 3; i++) {
        assert(pthread_join(threads[i], NULL) == 0);
    }

    /* A writer stops only when one more unit does not fit, and churn holds at most one. */
    uint64_t total = counted(base, "first") + counted(base, "second");
    assert(counted(base, "churn") == 0);
    assert(total <= UNITS * unit);
    assert(total >= (UNITS - 1) * unit);

    /* The count matches the files: exactly the room that is left can still be taken. */
    crux_file_t *file = NULL;
    size_t count = 0;
    uint64_t left = UNITS * unit - total;
    if (left > 0) {
        assert(crux_file_open_at(0, "rest", CRUX_FILE_CREATE_REPLACE, &file) == CRUX_FILE_OK);
        assert(crux_file_write(file, chunk, (size_t)unit, &count) == CRUX_FILE_OK);
        assert(crux_file_close(&file) == CRUX_FILE_OK);
    }
    assert(crux_file_open_at(0, "over", CRUX_FILE_CREATE_REPLACE, &file) == CRUX_FILE_ERR_NO_SPACE);

    const char *names[] = {"first", "second", "rest"};
    for (size_t i = 0; i < 3; i++) {
        crux_file_result_t removed = crux_file_remove_at(0, names[i]);
        assert(removed == CRUX_FILE_OK || removed == CRUX_FILE_ERR_NOT_FOUND);
    }
    assert(rmdir(base) == 0);
    puts("File root limit with concurrent callers on the Linux provider passed");
    return 0;
}
