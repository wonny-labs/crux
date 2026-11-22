# Portable controller timing consumer

This directory builds and runs the portable reference-controller timing scenario in
[`scenario/controller.c`](scenario/controller.c) as an independent
C17 consumer of `crux::time` and `crux::thread`. It demonstrates absolute monotonic releases and
a consumer-owned 100 ms phase/skip rule. It does not add callback timers or modify RTC behaviour,
and it does not qualify physical target timing or stack margins.

Configure independently on the supported Linux environment:

```sh
cmake -S tests/messaging_consumer -B build/messaging-consumer -G Ninja
cmake --build build/messaging-consumer
ctest --test-dir build/messaging-consumer --output-on-failure
```

The portable object target consumes only public usage targets and runs the actual
`CruxConsumerBoundary.cmake` checks. The final executable composition selects the Host providers.

Crux Queue was removed (see [the messaging contract](../../docs/messaging-contract.md)). This
directory held the Queue runtime consumers and their Zephyr fixture until then. Their design and
verification history stays in [the messaging validation record](../../docs/messaging-validation.md)
and under `docs/evidence/m5-messaging/`. The directory keeps its name so that the Host workflow and
`scripts/test-messaging.sh` keep running the controller scenario.
