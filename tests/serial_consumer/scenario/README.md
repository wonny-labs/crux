# Serial controller scenario

`controller.c` runs one bounded binary request and acknowledgement over the public `crux::serial` and `crux::time`
contracts, with short I/O loops and a nonce that the caller supplies. Queued writes alone never count as completion,
and it has no retransmission policy. It is a building block that only the Serial consumer tests compile, so it lives
beside them.

| Built by | Run by |
| --- | --- |
| `tests/serial_consumer/CMakeLists.txt` (Host, CTest `SerialConsumer.controller` and `SerialConsumer.controller_stale`) | `scripts/test-serial.sh` |
| `tests/serial_consumer/zephyr` (Twister and EVKB cross-build) | `scripts/test-serial.sh` |

Each build checks it as a portable consumer with `crux_assert_portable_consumer`, and
`scripts/check-native-interfaces.py` holds it to the native-free source rules.
