# System controller scenario

`controller_system.c` keeps a controller's boot diagnostics and feeds a watchdog only while the Time and network
work both make progress, through the public `crux::system` contract and the controller health helper in
`tests/time_periodic/include`. It does not clear the reset cause, reset or arm a watchdog by itself. It is a building
block that only the System consumer tests compile, so it lives beside them; it was `samples/controller/system/` until
the samples layout change.

| Built by | Run by |
| --- | --- |
| `tests/system_consumer/consumers.cmake`, for the Host test (CTest `SystemConsumer.ActualHost`) and `tests/system_consumer/zephyr` (Twister and EVKB cross-build) | `scripts/test-system.sh` |

Each build checks it as a portable consumer with `crux_assert_portable_consumer`, and
`scripts/check-native-interfaces.py` holds it to the native-free source rules.
