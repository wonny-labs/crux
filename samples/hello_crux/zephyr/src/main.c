#include <crux/version.h>

#include <zephyr/sys/printk.h>

int main(void)
{
    printk("Hello from Crux %s on zephyr\n", CRUX_VERSION_STRING);
    printk("CRUX_HELLO_READY composition=zephyr\n");
    return 0;
}
