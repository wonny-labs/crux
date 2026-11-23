# Portable controller timing consumer

This directory builds and runs the portable reference-controller timing scenario in
[`scenario/controller.c`](scenario/controller.c) as an independent
C17 consumer of `crux::time` and `crux::thread`. The scenario is a bounded reference for existing users of Thread, not a
pattern for new product code (see [Choosing an API](../../docs/choosing-an-api.md)). It demonstrates absolute monotonic
releases and a consumer-owned 100 ms phase/skip rule, which stays application logic. It does not add callback timers or
modify RTC behaviour, and a Host run does not qualify production runtime compatibility, timing jitter, target timing or
stack margins.

Configure independently on the supported Linux environment:

```sh
cmake -S tests/messaging_consumer -B build/messaging-consumer -G Ninja
cmake --build build/messaging-consumer
ctest --test-dir build/messaging-consumer --output-on-failure
```

The portable object target consumes only public usage targets and runs the actual
`CruxConsumerBoundary.cmake` checks. The final executable composition selects the Host providers.

The directory keeps its name so that the Host workflow and `scripts/test-messaging.sh` run the controller scenario.
