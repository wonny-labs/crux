# Native logger count and initial observation phase

This fixture uses the pinned Zephyr kernel, actual deferred `printk` path,
production format literals and `m3_logger_resources_get`, with the native UART
backend still enabled. An additional **test-only** backend renders the same
message to a byte counter and delays completion by the resulting 115200 baud,
10-bit-per-byte serial budget. The model uses the EVKB configuration's 10000 Hz tick resolution, avoiding the native default 100 Hz
rounding of every serial delay. It does not replace or modify production logging.

`scripts/test-controller-integration.sh` runs both cases and their verifier. For a
focused check, run Twister on this directory for `native_sim/native/64`, then
run `verify_output.py` on that Twister output directory in the Linux development
environment.
