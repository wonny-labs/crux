#include "hello_crux.h"

#include <stdio.h>

int main(void)
{
    puts("Hello from Crux on host");

    const char *state = hello_crux_time_state();
    if (state == NULL) {
        puts("CRUX_HELLO_FAILED composition=host");
        return 1;
    }

    printf("Crux Time: %s\n", state);
    puts("CRUX_HELLO_READY composition=host");
    return 0;
}
