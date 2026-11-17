/* SPDX-License-Identifier: Apache-2.0 */

#include "queue_adapter.h"

#include <zephyr/sys/printk.h>

int main(void)
{
    printk("queue round trip: %d\n", queue_adapter_roundtrip(7));
    return 0;
}
