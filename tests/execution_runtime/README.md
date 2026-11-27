# Independent synthetic runtime consumer

This original C17 fixture models a small runtime task/session adapter. It is not production runtime integration or
evidence of compatibility with any proprietary runtime.

`crux_runtime_fixture_run()` is callable from a standalone runner or firmware app.
Only ISO C, `<crux/thread.h>` and `<crux/sync.h>` appear in the portable source. The fixture uses
its own task priorities and stack-word requests, translates these to public Crux
options, and adapts a runtime argument to the portable task entry. Host functional
priority acceptance is tested, not native scheduling equivalence.

Each of twelve sessions creates its own mutex and three bounded signal channels. The owner and a worker hand off through
gates and handshakes to check poll contention, finite lock expiry and finite join timeout, then the owner joins before
inspecting results. Four reservation cycles create gated tasks until capacity is rejected, then release and join all of
them; later sessions verify reclamation. The fixture bounds its reservation array at eight entries and expects the four
thread slots of the qualification profile. Checks print source lines and status values and stay active with `NDEBUG`.
A failed call ends the run; the fixture has one caller, is not reentrant and has no cancellation policy. The cases check
timeout outcomes, not elapsed time; the outer test deadline is only a liveness guard.

## Standalone Linux Host composition

Configure the consumer itself, supplying the Crux root explicitly. The consumer
turns off Crux internal testing and samples and obtains capability headers and
provider linkage solely from `crux::thread` and `crux::sync`:

```sh
cmake -S tests/execution_runtime -B build/runtime-consumer \
  -DCRUX_SOURCE_DIR="$PWD"
cmake --build build/runtime-consumer
ctest --test-dir build/runtime-consumer --output-on-failure
```

The Crux Host root selects the supported Host execution provider. No native library
or private include directory is added by the consumer. Sanitizer flags can be
supplied to this independently configured build, without changing its source.

## Independent Zephyr composition

The `zephyr/` application owns its own `prj.conf`, enables `CONFIG_CRUX_THREAD` and `CONFIG_CRUX_SYNC`
and `CONFIG_ZTEST`, and disables unrelated Time capability initialization. Its
Zephyr-only runner calls the fixture from one ztest. The portable fixture is built
as a separate strict C17 static library linking only the public usage target. Use
the configured west workspace with this Crux repository discovered as its module:

```sh
west build -b native_sim/native/64 tests/execution_runtime/zephyr \
  -d build/runtime-consumer-native --pristine
# Run the native executable under an external liveness deadline:
timeout 60s build/runtime-consumer-native/zephyr/zephyr.exe
west build -b 'mimxrt1060_evk@B//qspi' tests/execution_runtime/zephyr \
  -d build/runtime-consumer-evkb --pristine
```

If the active west manifest registers another Crux checkout, use the repository's
`scripts/test-portable-execution.sh`; it explicitly selects this module and the
pinned dependencies through `ZEPHYR_MODULES` to avoid duplicate discovery. The module
owns provider selection and resource configuration; this application does not
include its private build files or name private targets. The EVKB command is a
cross-build only. No flashing, reset, probe or hardware execution is included.

