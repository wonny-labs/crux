# Reference controller, Zephyr application

The Zephyr composition of the [reference controller](../README.md). With the default `prj.conf` it runs the basic
periodic scenario: 20 cycles of Time observation on a 100 ms grid, then `CONTROLLER_COMPLETE cycles=20`. The other
`*.conf` files and overlays in this folder select the device, network and integrated board probes that the
[controller README](../README.md) describes; they are not part of the runnable sample.

## Run on `native_sim`

From the west workspace root (`/workspace` in the Dev Container), after `scripts/bootstrap-zephyr.sh`:

```sh
west build -p always -b native_sim/native/64 -d build/controller crux-pilot/samples/controller/zephyr -t run
```

The scenario prints one `cycle=` line per cycle and ends with `CONTROLLER_COMPLETE cycles=20`. The simulated kernel
keeps running after that line; stop it with Ctrl+C. Twister runs the same scenario from [`sample.yaml`](sample.yaml)
and stops at the completion line:

```sh
west twister -T crux-pilot/samples/controller/zephyr -p native_sim/native/64
```

`scripts/test-controller.sh` checks every cycle line, and also runs the scenario without an RTC.
The EVKB build (`-b 'mimxrt1060_evk@B//qspi'`) is a cross-build in this repository's checks.
