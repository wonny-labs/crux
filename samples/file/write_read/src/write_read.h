#ifndef FILE_WRITE_READ_H
#define FILE_WRITE_READ_H

/*
 * The application part of the sample. It uses only the public File API (<crux/file.h>) and does
 * not know which provider or file system the build selected.
 */

#include <crux/file.h>

#include <stddef.h>

/**
 * Create or replace a file and write a text to it.
 *
 * @param name Flat file name in the default File root.
 * @param text Bytes to write.
 * @param length Number of bytes in text.
 * @param[out] written Bytes the provider accepted.
 * @return CRUX_FILE_OK when every byte was written and flushed, otherwise the first failure.
 */
crux_file_result_t write_text(const char *name, const char *text, size_t length, size_t *written);

/**
 * Read a file from its start into a buffer.
 *
 * @param name Flat file name in the default File root.
 * @param[out] buffer Destination.
 * @param capacity Size of buffer in bytes.
 * @param[out] length Bytes read; at most capacity.
 * @return CRUX_FILE_OK or the first failure.
 */
crux_file_result_t read_text(const char *name, char *buffer, size_t capacity, size_t *length);

#endif
