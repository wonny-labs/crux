# Drivers, boards and tests (the driver kit)

The product repository is also a Zephyr module, so that a product can hold its own board, its own drivers and their tests next to the application. [Writing a product driver](https://github.com/wonny-labs/crux-pilot/blob/main/docs/writing-a-product-driver.md) (`docs/writing-a-product-driver.md` in `crux-pilot`) is the guide: when not to write a driver, the layout, the binding, the driver, the emulator, the tests and a checklist. The kit is plain Zephyr. It adds no Crux interface, and nothing in it uses the `crux_` prefix.

Paths below are relative to the root of the product repository.

| What | Where | What it shows |
| --- | --- | --- |
| Module | `zephyr/module.yml`, `CMakeLists.txt`, `Kconfig` | `board_root`, `dts_root`, and the `tests` and `boards` keys that Twister reads |
| Binding | `dts/bindings/sensor/vnd,example-temp.yaml` | A binding named after its compatible, with the stand-in vendor prefix `vnd` |
| Vendor prefixes | `dts/bindings/vendor-prefixes.txt` | Where a product adds a vendor prefix that Zephyr does not list |
| Driver | `drivers/sensor/example_temp/` | `DT_DRV_COMPAT`, `DEVICE_API`, `DT_INST_FOREACH_STATUS_OKAY`, init level and priority, errors as negative errno, a `zephyr_library_named` library, `depends on DT_HAS_VND_EXAMPLE_TEMP_ENABLED` |
| Emulator | `drivers/sensor/example_temp/example_temp_emul.c` | A model of the part's registers behind Zephyr's I2C emulator, with the sensor backend |
| Board | `boards/vnd/example_rt1062/` | A minimal copy of the files of the vendor board that it needs, with its own board name, not a `board: extend:` variant |
| Unit tests | `tests/drivers/sensor/example_temp/src/emul_test.c` | The driver against its emulator on `native_sim`, with bus errors injected through the bus emulator's `mock_api` and a wrong part identifier |
| Hardware scenario | `tests/drivers/sensor/example_temp/src/hardware_test.c` | A scenario gated on the Twister fixture `example_temp_wired`. A stub: the part is fictional |

The part, the board and the flash configuration are examples. Replace them with the product's own. When you rename the product, rename `product-x` in `zephyr/module.yml` as well as in `west.yml`: the tests find the driver folder through the module name.

Run the unit tests on `native_sim`, which needs Linux (the Dev Container). In a workspace whose manifest repository is the product, west finds the module. From any other workspace, name it:

~~~sh
ZEPHYR_EXTRA_MODULES=$PWD/product-x west twister -p native_sim -p native_sim/native/64 \
  -T product-x/tests -O build/twister --inline-logs
~~~

Build the hardware scenario for a board without running it. The run names no fixture, so Twister builds the image and runs nothing:

~~~sh
ZEPHYR_EXTRA_MODULES=$PWD/product-x west twister -p example_rt1062/mimxrt1062 \
  -T product-x/tests --build-only -O build/twister-build --inline-logs
~~~

A run of the hardware scenario on a board is a hardware operation. It needs authorisation for the current task. Do not launch it from Twister with `--device-testing`, which flashes on every launch. Crux's accepted direction is its device-control tool, which is untested on hardware, and Crux has no supported entry point for consumer hardware tests yet. The guide says why.

Build product code that calls kernel objects as a `zephyr_library_named` library of this module, or as sources of the `app` target, not as a plain CMake `STATIC` library that `app` links. The guide's section on static libraries says why and names the probe that tests it.

The `board_root` and `dts_root` of the module apply to every build that includes it, including a secondary image such as a bootloader built by sysbuild. The kit's driver is built only when the sensor subsystem is on and a node of its compatible is enabled, and a bootloader image normally has neither, but this has not been tested: no sysbuild image is built with the module.
