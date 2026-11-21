/* SPDX-License-Identifier: Apache-2.0 */

#include "queue_adapter.h"

#include <zephyr/kernel.h>

/* The four calls of the reported link failure. Nothing else in a minimal image uses them, so the
 * kernel archive member that defines them is linked only if this file's references reach it. */
static char queue_buffer[4 * sizeof(int)];
static struct k_msgq queue;

int queue_adapter_roundtrip(int value)
{
    int out = -1;

    k_msgq_init(&queue, queue_buffer, sizeof(int), 4);
    if (k_msgq_put(&queue, &value, K_NO_WAIT) != 0) {
        return -1;
    }
    if (k_msgq_get(&queue, &out, K_NO_WAIT) != 0) {
        return -1;
    }
    k_msgq_purge(&queue);
    return out;
}
