/* SPDX-License-Identifier: Apache-2.0 */

#ifndef PRODUCT_TEMPLATE_LINK_QUEUE_ADAPTER_H_
#define PRODUCT_TEMPLATE_LINK_QUEUE_ADAPTER_H_

/* Puts value through a kernel message queue and returns what comes out, or -1. */
int queue_adapter_roundtrip(int value);

#endif /* PRODUCT_TEMPLATE_LINK_QUEUE_ADAPTER_H_ */
