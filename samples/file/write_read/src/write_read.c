#include "write_read.h"

crux_file_result_t write_text(const char *name, const char *text, size_t length, size_t *written)
{
    crux_file_t *file = NULL;
    *written = 0;

    crux_file_result_t result = crux_file_open(name, CRUX_FILE_CREATE_REPLACE, &file);
    if (result != CRUX_FILE_OK) {
        return result;
    }

    result = crux_file_write(file, text, length, written);
    if (result == CRUX_FILE_OK) {
        /* A write alone implies nothing about storage; sync asks the provider to flush it. */
        result = crux_file_sync(file);
    }

    /* Close always consumes the handle. Report the first failure. */
    const crux_file_result_t closed = crux_file_close(&file);
    return result != CRUX_FILE_OK ? result : closed;
}

crux_file_result_t read_text(const char *name, char *buffer, size_t capacity, size_t *length)
{
    crux_file_t *file = NULL;
    *length = 0;

    crux_file_result_t result = crux_file_open(name, CRUX_FILE_READ, &file);
    if (result != CRUX_FILE_OK) {
        return result;
    }

    result = crux_file_read(file, buffer, capacity, length);

    const crux_file_result_t closed = crux_file_close(&file);
    return result != CRUX_FILE_OK ? result : closed;
}
