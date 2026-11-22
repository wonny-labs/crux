#include "hello_crux.h"

#include <zephyr/sys/printk.h>

int main(void)
{
    printk("Hello from Crux on zephyr\n");

    const char *state = hello_crux_time_state();
    if (state == NULL) {
        printk("CRUX_HELLO_FAILED composition=zephyr\n");
        return -1;
    }

    printk("Crux Time: %s\n", state);
    printk("CRUX_HELLO_READY composition=zephyr\n");
    return 0;
}
