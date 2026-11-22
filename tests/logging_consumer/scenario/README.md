# Logging controller scenario

`controller.c` emits one controller state record through the public `crux::logging` contract, with no native
header. A successful return is not a delivery acknowledgement. It is a building block that only the Logging consumer
tests compile, so it lives beside them; it was `samples/logging/` until the samples layout change.

| Built by | Run by |
| --- | --- |
| `tests/logging_consumer/CMakeLists.txt` (Host, CTest `LoggingConsumer.ActualHost`) | `scripts/test-logging.sh` |
| `tests/logging_consumer/zephyr` (EVKB cross-build) and `tests/logging/zephyr` (`native_sim`, through `consumers.cmake`) | `scripts/test-logging.sh` |

Each build checks it as a portable consumer with `crux_assert_portable_consumer`, and
`scripts/check-native-interfaces.py` holds it to the native-free source rules.
