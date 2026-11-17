/*
 * A small check harness for the table-driven conformance cases. It counts every check, names the
 * current case in a failure, and never aborts, so that one run shows every failing row.
 */
#ifndef CRUX_IMAGE_STATE_TEST_HARNESS_H
#define CRUX_IMAGE_STATE_TEST_HARNESS_H

#include <stdbool.h>

void harness_case(const char *name);
void harness_check(bool ok, const char *expression, const char *file, int line);
void harness_check_int(long expected, long actual, const char *expression, const char *file,
                       int line);
/* Prints the totals and returns the process exit code: 0 when every check held. */
int harness_finish(const char *suite);

#define CASE(name) harness_case(name)
#define CHECK(condition) harness_check((condition), #condition, __FILE__, __LINE__)
#define CHECK_INT(expected, actual)                                                                \
    harness_check_int((long)(expected), (long)(actual), #actual, __FILE__, __LINE__)

#endif /* CRUX_IMAGE_STATE_TEST_HARNESS_H */
