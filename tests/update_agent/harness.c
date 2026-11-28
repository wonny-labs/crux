#include "harness.h"

#include <stdio.h>

static unsigned checks;
static unsigned failures;
static const char *current_case = "(none)";

void harness_case(const char *name)
{
    current_case = name;
}

void harness_check(bool ok, const char *expression, const char *file, int line)
{
    checks++;
    if (!ok) {
        failures++;
        printf("FAIL [%s] %s:%d: %s\n", current_case, file, line, expression);
    }
}

void harness_check_int(long expected, long actual, const char *expression, const char *file,
                       int line)
{
    checks++;
    if (expected != actual) {
        failures++;
        printf("FAIL [%s] %s:%d: %s is %ld, expected %ld\n", current_case, file, line, expression,
               actual, expected);
    }
}

int harness_finish(const char *suite)
{
    printf("%s: %u checks, %u failures\n", suite, checks, failures);
    return failures == 0 ? 0 : 1;
}
