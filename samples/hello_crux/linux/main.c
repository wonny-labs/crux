#include <crux/version.h>

#include <stdio.h>

int main(void)
{
    printf("Hello from Crux %s on host\n", CRUX_VERSION_STRING);
    puts("CRUX_HELLO_READY composition=host");
    return 0;
}
