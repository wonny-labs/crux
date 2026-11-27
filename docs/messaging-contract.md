# Messaging contract

This page tells a product developer what Crux offers for queues and events between threads.

Crux has no queue or event API.
A product uses Zephyr's `k_msgq` for message queues, and Zephyr semaphores, events or condition variables for notification, in its own Zephyr code ([Choosing an API](choosing-an-api.md)).
The product template's [domain include check](../templates/product/README.md#zones-and-the-domain-include-check) and `style/check-includes.sh` reject `<crux/queue.h>`.
`CRUX_BUILD_QUEUE` stops the Host configure with a message that names `k_msgq`.

## Migration notes

Crux Queue was removed: `components/queue`, `<crux/queue.h>`, the `crux::queue` and `crux::queue_linux` targets, `CONFIG_CRUX_QUEUE`, `CRUX_BUILD_QUEUE` and its tests and runners ([ADR-0003](decisions/0003-p9-result-services-keep-narrow-thread-sync.md) R3).
Its last contract and code are in Git history before commit `cd66b9e5`.

Crux Queue was not a thin copy of `k_msgq`.
A product keeps the following properties after the move only if its adapter provides them ([platform direction review](research/platform-direction-review.md#56-what-it-asks-of-each-consumer), section 5.6):

- It was a ring buffer in common code, under one metadata `k_mutex` with a `k_condvar` per queue on Zephyr.
- Handles carried a slot and a generation, so stale handles were rejected.
- Destroy returned BUSY while calls were active or waiting.
- Waits were finite: zero polled, there was no forever, and one deadline covered lock admission and the wait.
- It was thread context only. The default was a cooperative stop, and a purge was not an abort.
- The pool was fixed at 4 × 16 × 64 bytes.
