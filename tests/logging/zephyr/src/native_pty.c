/* The console harness reads these lines from the native PTY UART on stdout (testcase.yaml). */
#include <crux/logging.h>
#include <zephyr/sys/printk.h>

int main(void)
{
    if (crux_log_write(CRUX_LOG_INFO, "pty", "record on the native UART") != CRUX_OK) {
        return 1;
    }
    printk("printk after the record\n");
    return 0;
}
