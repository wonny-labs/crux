/*
 * Threads sharing the store on the Linux File provider. The store lock serialises every operation,
 * so each save succeeds and each read finds a whole value. A status read takes only the short lock.
 * The sanitizer preset does not detect data races: see the pull request for a ThreadSanitizer run.
 */
#include "credential_test.h"
#include "medium_linux.h"

#include <pthread.h>
#include <stdlib.h>

#define WRITES_PER_THREAD 40u
#define VALUE_BYTES 256u

typedef struct {
    crux_credential_record_t record;
    uint8_t fill;
    unsigned failures;
} writer_t;

static volatile int stop_readers;
static unsigned reader_failures;
static unsigned status_reads;

/* A value is all one byte, so a read that mixed two saves would show. */
static void *writer_main(void *argument)
{
    writer_t *writer = argument;
    uint8_t value[VALUE_BYTES];
    for (unsigned index = 0; index < WRITES_PER_THREAD; ++index) {
        memset(value, writer->fill + (int)(index % 8u), sizeof(value));
        if (crux_credential_write(writer->record, value, sizeof(value)) != CRUX_CREDENTIAL_OK) {
            writer->failures += 1;
        }
    }
    return NULL;
}

static bool value_whole(const uint8_t *value, size_t length)
{
    for (size_t index = 1; index < length; ++index) {
        if (value[index] != value[0]) {
            return false;
        }
    }
    return length == VALUE_BYTES;
}

static void *reader_main(void *argument)
{
    (void)argument;
    uint8_t value[VALUE_BYTES];
    size_t length = 0;
    while (!__atomic_load_n(&stop_readers, __ATOMIC_ACQUIRE)) {
        crux_credential_result_t result =
            crux_credential_read(CRUX_CREDENTIAL_RECORD_ACCOUNTS, value, sizeof(value), &length);
        if (result != CRUX_CREDENTIAL_OK ||
            (result == CRUX_CREDENTIAL_OK && !value_whole(value, length))) {
            reader_failures += 1;
        }
    }
    return NULL;
}

static void *status_main(void *argument)
{
    (void)argument;
    while (!__atomic_load_n(&stop_readers, __ATOMIC_ACQUIRE)) {
        crux_credential_store_info_t info;
        if (crux_credential_store_get_info(&info) != CRUX_OK ||
            info.state != CRUX_CREDENTIAL_STATE_VALID) {
            reader_failures += 1;
        }
        status_reads += 1;
    }
    return NULL;
}

static void test_threads_share_the_store(void)
{
    uint8_t first[VALUE_BYTES];
    memset(first, 0x10, sizeof(first));
    test_fresh_empty();
    CHECK(crux_credential_write(CRUX_CREDENTIAL_RECORD_ACCOUNTS, first, sizeof(first)) ==
          CRUX_CREDENTIAL_OK);

    writer_t writers[] = {{CRUX_CREDENTIAL_RECORD_ACCOUNTS, 0x20, 0},
                          {CRUX_CREDENTIAL_RECORD_TLS_CERTIFICATE, 0x40, 0}};
    pthread_t writer_threads[2];
    pthread_t reader_thread;
    pthread_t status_thread;
    CHECK(pthread_create(&reader_thread, NULL, reader_main, NULL) == 0);
    CHECK(pthread_create(&status_thread, NULL, status_main, NULL) == 0);
    for (size_t index = 0; index < 2u; ++index) {
        CHECK(pthread_create(&writer_threads[index], NULL, writer_main, &writers[index]) == 0);
    }
    for (size_t index = 0; index < 2u; ++index) {
        CHECK(pthread_join(writer_threads[index], NULL) == 0);
        CHECK(writers[index].failures == 0);
    }
    __atomic_store_n(&stop_readers, 1, __ATOMIC_RELEASE);
    CHECK(pthread_join(reader_thread, NULL) == 0);
    CHECK(pthread_join(status_thread, NULL) == 0);
    CHECK(reader_failures == 0);
    CHECK(status_reads > 0);
    CHECK(crux_credential_test_buffers_clear());

    /* The last save of each writer is what a reset finds. */
    CHECK(test_boot() == CRUX_CREDENTIAL_OK);
    memset(first, 0x20 + (int)((WRITES_PER_THREAD - 1u) % 8u), sizeof(first));
    test_expect_record(CRUX_CREDENTIAL_RECORD_ACCOUNTS, first, sizeof(first));
    memset(first, 0x40 + (int)((WRITES_PER_THREAD - 1u) % 8u), sizeof(first));
    test_expect_record(CRUX_CREDENTIAL_RECORD_TLS_CERTIFICATE, first, sizeof(first));
}

/* A writer that records its last acknowledged value and checks that, once refused, it stays so. */
typedef struct {
    crux_credential_record_t record;
    uint8_t fill;
    int last_acknowledged; /* -1 when none was. */
    unsigned failures;
} erase_writer_t;

static void *erase_writer_main(void *argument)
{
    erase_writer_t *writer = argument;
    uint8_t value[VALUE_BYTES];
    bool refused = false;
    writer->last_acknowledged = -1;
    for (unsigned index = 0; index < WRITES_PER_THREAD; ++index) {
        memset(value, writer->fill + (int)(index % 8u), sizeof(value));
        crux_credential_result_t result =
            crux_credential_write(writer->record, value, sizeof(value));
        if (result == CRUX_CREDENTIAL_OK && !refused) {
            writer->last_acknowledged = (int)(index % 8u);
        } else if (result == CRUX_CREDENTIAL_ERR_UNUSABLE) {
            refused = true;
        } else {
            writer->failures += 1;
        }
    }
    return NULL;
}

static void *erase_reader_main(void *argument)
{
    const crux_credential_record_t *record = argument;
    uint8_t value[VALUE_BYTES];
    size_t length = 0;
    while (!__atomic_load_n(&stop_readers, __ATOMIC_ACQUIRE)) {
        crux_credential_result_t result =
            crux_credential_read(*record, value, sizeof(value), &length);
        if (!(result == CRUX_CREDENTIAL_ERR_UNUSABLE ||
              (result == CRUX_CREDENTIAL_OK && value_whole(value, length)))) {
            reader_failures += 1;
        }
    }
    return NULL;
}

static void *erase_status_main(void *argument)
{
    (void)argument;
    while (!__atomic_load_n(&stop_readers, __ATOMIC_ACQUIRE)) {
        crux_credential_store_info_t info;
        if (crux_credential_store_get_info(&info) != CRUX_OK ||
            (info.state != CRUX_CREDENTIAL_STATE_VALID &&
             info.state != CRUX_CREDENTIAL_STATE_UNUSABLE)) {
            reader_failures += 1;
        }
        status_reads += 1;
    }
    return NULL;
}

/*
 * An account-only erase while other users of the store write and read: it waits for the store lock,
 * takes effect between two operations, and every later write is refused. A reset then finds no
 * accounts, and the certificate that the last acknowledged write saved.
 */
static void test_erase_accounts_while_others_use_the_store(void)
{
    uint8_t first[VALUE_BYTES];
    test_fresh_empty();
    memset(first, 0x10, sizeof(first));
    CHECK(crux_credential_write(CRUX_CREDENTIAL_RECORD_ACCOUNTS, first, sizeof(first)) ==
          CRUX_CREDENTIAL_OK);
    memset(first, 0x30, sizeof(first));
    CHECK(crux_credential_write(CRUX_CREDENTIAL_RECORD_TLS_CERTIFICATE, first, sizeof(first)) ==
          CRUX_CREDENTIAL_OK);
    __atomic_store_n(&stop_readers, 0, __ATOMIC_RELEASE);
    reader_failures = 0;
    status_reads = 0;

    erase_writer_t writers[] = {{CRUX_CREDENTIAL_RECORD_ACCOUNTS, 0x20, -1, 0},
                                {CRUX_CREDENTIAL_RECORD_TLS_CERTIFICATE, 0x40, -1, 0}};
    static const crux_credential_record_t read_records[] = {
        CRUX_CREDENTIAL_RECORD_ACCOUNTS, CRUX_CREDENTIAL_RECORD_TLS_CERTIFICATE};
    pthread_t writer_threads[2];
    pthread_t reader_threads[2];
    pthread_t status_thread;
    CHECK(pthread_create(&status_thread, NULL, erase_status_main, NULL) == 0);
    for (size_t index = 0; index < 2u; ++index) {
        CHECK(pthread_create(&reader_threads[index], NULL, erase_reader_main,
                             (void *)&read_records[index]) == 0);
        CHECK(pthread_create(&writer_threads[index], NULL, erase_writer_main, &writers[index]) ==
              0);
    }
    CHECK(crux_credential_erase_accounts() == CRUX_CREDENTIAL_OK);
    CHECK(crux_credential_state() == CRUX_CREDENTIAL_STATE_UNUSABLE);
    for (size_t index = 0; index < 2u; ++index) {
        CHECK(pthread_join(writer_threads[index], NULL) == 0);
        CHECK(writers[index].failures == 0);
    }
    __atomic_store_n(&stop_readers, 1, __ATOMIC_RELEASE);
    for (size_t index = 0; index < 2u; ++index) {
        CHECK(pthread_join(reader_threads[index], NULL) == 0);
    }
    CHECK(pthread_join(status_thread, NULL) == 0);
    CHECK(reader_failures == 0);
    CHECK(status_reads > 0);
    CHECK(crux_credential_write(CRUX_CREDENTIAL_RECORD_ACCOUNTS, first, sizeof(first)) ==
          CRUX_CREDENTIAL_ERR_UNUSABLE);

    CHECK(test_boot() == CRUX_CREDENTIAL_OK);
    size_t length = 0;
    CHECK(crux_credential_read(CRUX_CREDENTIAL_RECORD_ACCOUNTS, first, sizeof(first), &length) ==
          CRUX_CREDENTIAL_ERR_NOT_FOUND);
    int last = writers[1].last_acknowledged;
    memset(first, last < 0 ? 0x30 : 0x40 + last, sizeof(first));
    test_expect_record(CRUX_CREDENTIAL_RECORD_TLS_CERTIFICATE, first, sizeof(first));
}

int main(void)
{
    credential_medium_linux_open();
    test_threads_share_the_store();
    test_erase_accounts_while_others_use_the_store();
    int status = credential_test_finish("credential concurrency");
    credential_medium_linux_close();
    return status;
}
