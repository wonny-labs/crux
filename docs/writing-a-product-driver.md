# Writing a product driver

**Status: developer guidance, not a contract.** It describes how a product repository holds its own board, its own Zephyr drivers and devicetree bindings, and their tests. It adds no Crux interface and no Crux device model. The kit it describes is the Zephyr module in [`templates/product/`](../templates/product/README.md), written against **Zephyr v4.4** (Crux pins v4.4.2, see [`west.yml`](../west.yml)).

What runs: `scripts/test-product-template.sh`, which Crux's Zephyr CI runs, builds the example driver and runs its unit tests on `native_sim`, and builds its hardware scenario for two boards without running it. Nothing of the kit has run on a board. The example part is fictional.

## What this guide covers, and what it leaves to Zephyr

[ADR-0001](decisions/0001-application-boundary-and-api-stability.md) decides that Crux builds no driver model and no hardware abstraction layer. [Choosing an API](choosing-an-api.md) puts a device, a bus or a pin on the Zephyr side of the line: a product driver is **plain Zephyr code in the product's adapters**, behind a Zephyr API class such as sensor, and the domain reaches it through a port that the product owns. Do not use the `crux_` prefix in a product driver, a binding or a Kconfig symbol: the prefix is reserved for Crux ([CONTRIBUTING.md](../CONTRIBUTING.md)).

This guide does not restate Zephyr. It tells you where the pieces go, what the example shows and what to check, and links the Zephyr page that has the rules:

- [Device driver model](https://docs.zephyrproject.org/latest/kernel/drivers/index.html) and [devicetree bindings](https://docs.zephyrproject.org/latest/build/dts/bindings.html)
- [Modules](https://docs.zephyrproject.org/latest/develop/modules.html) and [board porting](https://docs.zephyrproject.org/latest/hardware/porting/board_porting.html)
- [Emulators](https://docs.zephyrproject.org/latest/hardware/emulator/index.html), [Ztest](https://docs.zephyrproject.org/latest/develop/test/ztest.html) and [Twister](https://docs.zephyrproject.org/latest/develop/test/twister.html)
- [Sensor API](https://docs.zephyrproject.org/latest/hardware/peripherals/sensor/index.html), the class of the example

## When not to write a driver

A driver is code that the product owns for the life of the product. Take the cheaper route first:

1. **An upstream driver exists for the part.** Describe the part in the board's devicetree with the upstream binding, enable its Kconfig symbol, and test the product's use of it against an emulator on `native_sim`. Zephyr ships bus emulators for I2C and SPI, and emulators for some parts, such as the AT24-class EEPROM (`drivers/eeprom/eeprom_at2x_emul.c`, 8-bit addressing only). This costs a node, a symbol and a test.
2. **An upstream driver nearly fits.** Fix it upstream, or carry a small reviewed patch with a stated reason (the [product composition guide](product-composition.md) says how to modify third-party code). Do not copy the driver into the product.
3. **No upstream driver exists.** Write one behind the Zephyr class that fits the part (sensor, GPIO, ADC and so on). Application code that uses the class API then works on any board and against the emulator. The example in this kit is this case.
4. **No Zephyr class fits.** Write a driver with the class that is closest and say in its header what it does not offer. Start a design discussion before you add a product-specific API that several products will call.

## Layout of a product repository

The template is the repository root. Paths are relative to it, and every path exists in [`templates/product/`](../templates/product/README.md).

| Path | Holds |
| --- | --- |
| `zephyr/module.yml` | Makes the repository a Zephyr module and declares its roots |
| `CMakeLists.txt`, `Kconfig` | The module's build and configuration entry points |
| `drivers/sensor/example_temp/example_temp.c` | The driver, with its `CMakeLists.txt` and `Kconfig` beside it, one folder for each part, one folder for each class above it |
| `dts/bindings/sensor/vnd,example-temp.yaml` | The binding of the part, named after its compatible |
| `dts/bindings/vendor-prefixes.txt` | The vendor prefixes of the product's own bindings |
| `boards/vnd/example_rt1062` | The product's board, `boards/<vendor>/<board>` |
| `tests/drivers/sensor/example_temp/testcase.yaml` | The tests of the driver and the Twister scenarios that select them |
| `app/`, `domain/` | The application and the domain of the [template](../templates/product/README.md), unchanged by the kit |

The kit's own overview, with the commands to run its tests from a product workspace, is [`templates/product/drivers/README.md`](../templates/product/drivers/README.md).

## The module file

`zephyr/module.yml` is what Zephyr reads. The kit's file has three parts:

```yaml
name: product-x
build:
  cmake: .
  kconfig: Kconfig
  settings:
    board_root: .
    dts_root: .
tests:
  - tests
boards:
  - boards
```

- `name` fixes the module's name, so a renamed folder does not rename the CMake variables. Rename `product-x` when you rename the product: the tests use `ZEPHYR_PRODUCT_X_MODULE_DIR`.
- `board_root` makes `<root>/boards` a place where Zephyr looks for boards, and `dts_root` makes `<root>/dts` and `<root>/dts/bindings` places where it looks for devicetree files and bindings. Both are relative to the module.
- `tests` and `boards` are read by Twister, not by the build.

A west workspace whose manifest repository is the product finds the module by itself. A build that is not in such a workspace, such as Crux's own CI, passes it with `-DZEPHYR_EXTRA_MODULES=<path>`, or the environment variable of the same name, which Twister reads too.

## The binding

A binding says what a devicetree node of the part may contain. The kit's file is `dts/bindings/sensor/vnd,example-temp.yaml`.

- **The file is named after the compatible**, and the compatible is `<vendor>,<part>`. The vendor prefix is the part maker's, not the product's.
- **Examples and tests use `vnd`**, the prefix that Zephyr lists as a stand-in for a real vendor. A binding for a real part uses its maker's prefix. If Zephyr does not list it, add a line to `dts/bindings/vendor-prefixes.txt` of the product, in the format that the file explains.
- **Include the bus binding**: `i2c-device.yaml` for a part on I2C, `spi-device.yaml` for SPI, and the class binding (`sensor-device.yaml`) where one exists. They bring `reg`, the bus properties and the common ones.
- **Describe what the part is, not what the board does.** A property that only one board needs belongs in that board's overlay as a node property, not in the binding.

## The driver

The skeleton is `drivers/sensor/example_temp/example_temp.c`. Its parts, in the order that a reader meets them:

```c
#define DT_DRV_COMPAT vnd_example_temp
```

`DT_DRV_COMPAT` is the compatible with every non-alphanumeric character turned into an underscore. The `DT_INST_*` macros need it, and it must be defined before the first `DT_INST_*` use; defining it first in the file is the convention.

```c
static DEVICE_API(sensor, example_temp_api) = {
    .sample_fetch = example_temp_sample_fetch,
    .channel_get = example_temp_channel_get,
};
```

`DEVICE_API` declares the class API structure in an iterable section so that Zephyr can check the class of a device at run time. Zephyr asks for it in out-of-tree drivers since v4.1 ([migration guide](https://docs.zephyrproject.org/latest/releases/migration-guide-4.1.html)).

```c
DT_INST_FOREACH_STATUS_OKAY(EXAMPLE_TEMP_INST)
```

`EXAMPLE_TEMP_INST` defines one data block, one config block and one device for each node of the compatible whose status is `okay`. The device comes from `SENSOR_DEVICE_DT_INST_DEFINE`, the sensor class's form of the generic `DEVICE_DT_INST_DEFINE`. It names the init function, the **init level** and the **priority**:

- `POST_KERNEL` is the level of a device that talks to a bus. `PRE_KERNEL_1` and `PRE_KERNEL_2` cannot use kernel services and run on the interrupt stack.
- The priority orders devices within a level, lower first. A sensor uses `CONFIG_SENSOR_INIT_PRIORITY`, as Zephyr's sensor drivers do. The devicetree does not set the order. `CONFIG_CHECK_INIT_PRIORITIES`, on by default, compares the priorities with the dependencies that the devicetree gives and fails the build if a device would start before the bus it sits on; by default `CONFIG_SENSOR_INIT_PRIORITY` is 90, above the I2C and SPI controller priorities (50, from `CONFIG_KERNEL_INIT_PRIORITY_DEVICE`).

The build side is two files next to the driver.

```cmake
zephyr_library_named(product_example_temp)
zephyr_library_sources(example_temp.c)
zephyr_library_sources_ifdef(CONFIG_EMUL_EXAMPLE_TEMP example_temp_emul.c)
```

Use `zephyr_library_named` and give the library a name of its own that starts with the product's. An unnamed `zephyr_library()` takes its name from the path of the folder relative to `ZEPHYR_BASE` (`cmake/modules/extensions.cmake`), so the name depends on where the module is checked out, is long, and changes with the workspace layout; it is also what shows up in build output and link errors. A fixed name that starts with the product's name is stable and easy to search for. See [Static libraries](#static-libraries-and-kernel-objects) for a finding about libraries built another way.

```kconfig
config EXAMPLE_TEMP
	bool "Example temperature sensor"
	default y
	depends on DT_HAS_VND_EXAMPLE_TEMP_ENABLED
	select I2C
```

`DT_HAS_VND_EXAMPLE_TEMP_ENABLED` is generated from the devicetree: it is true when a node of the compatible is `okay`. With `default y` and this `depends on`, a board that has the node gets the driver and a board that does not, does not. Put a log level symbol beside it, as the kit does with `Kconfig.template.log_config`.

### Errors and logging

- **Return a negative errno from every function that can fail**, and pass a bus error up unchanged (the example returns `-EIO` or whatever the bus returned). Use `-ENODEV` for a part that is missing or has the wrong identifier, `-EBUSY` for a result that is not ready yet, `-ENOTSUP` for a channel or an attribute that the part does not have, and `-ERANGE` for a value that does not fit. A caller can then tell "try again" from "not supported" from a fault.
- **Check what init can check**: the bus is ready (`i2c_is_ready_dt`), the part answers, and the identifier matches. A failed init leaves `device_is_ready()` false, and the application checks that before use.
- **Log with `LOG_MODULE_REGISTER` and a level symbol of your own** (`CONFIG_<NAME>_LOG_LEVEL`). Log failures at `LOG_ERR`, once, where they are detected. Do not log in the normal path of a fast read, and never use `printk` in a driver.
- **Keep the error visible to the test.** An error that the driver only logs cannot be tested.

Zephyr's driver pages cover what the example leaves out: power management, interrupts and callbacks, DMA and cache coherency, userspace and the asynchronous sensor API. Read them before you copy the example for a part that needs one.

## The emulator and the unit tests

An emulator is a model of the part behind Zephyr's bus emulator. The kit's is `drivers/sensor/example_temp/example_temp_emul.c`, modelled on `drivers/sensor/f75303/f75303_emul.c` of Zephyr. It is built only with `CONFIG_EMUL_EXAMPLE_TEMP`, which needs `CONFIG_EMUL`. `CONFIG_EMUL` has no board or test dependency in Zephyr, so only the test configurations of this kit enable it; a product keeps it out of its firmware configurations. It answers only the transfers that the driver makes and refuses any other, so a driver change that adds a transfer shows up in the tests.

The tests are `tests/drivers/sensor/example_temp/src/emul_test.c`. They use four tools, each in one place of the file:

1. The emulator's **sensor backend** sets a temperature in SI units (`emul_sensor_backend_set_channel`), so a test does not know the registers.
2. The emulator's **test controls** (`example_temp_emul_set_reg`) put a register in a state that the backend cannot, such as a wrong part identifier.
3. The bus emulator's **`mock_api`** injects a bus error for one register. The mock returns `-ENOSYS` for every other transfer, and the model then answers. A test removes the mock afterwards.
4. **`dev->ops.init(dev)`** runs the init function again, for the failures that only init has: a bus error, a wrong identifier, a failed configuration write.

The error paths are most of the file: a fetch before data is ready, a bus error on each register, a value out of range, a channel that the part does not have, and a failed fetch that must keep the last sample.

Run the tests where `native_sim` runs: **on Linux, in the Dev Container**. `native_sim` does not run on macOS, and the build scripts refuse other hosts. From the repository root of Crux:

```sh
scripts/test-product-template.sh 'mimxrt1060_evk@B//qspi'
```

That is the command that CI runs. It also builds the application of the template, which takes longest. To run only the driver tests, use the line that the script uses, with the path of the template or of your product:

```sh
ZEPHYR_EXTRA_MODULES=<path-to-the-module> west twister -p native_sim -p native_sim/native/64 \
  -T <path-to-the-module>/tests -O <output-directory> --inline-logs
```

On Apple Silicon the Dev Container is an amd64 image under emulation and a full Zephyr build is slow. Push to a draft pull request and read CI instead.

## The hardware scenario

A driver is not qualified by its emulator: the emulator is a model written by the same hand as the driver. A product needs a scenario that runs against the part on a board, and that scenario must not run by accident.

The kit's second scenario, `product.drivers.sensor.example_temp.hardware` in `testcase.yaml`, is **gated on a Twister fixture** named `example_temp_wired`. Without `--device-testing`, and without the fixture on the command line or in an entry of a hardware map, Twister builds the image for the board and does not run it. A hardware map whose entry lists the fixture, used with `--device-testing`, makes the scenario runnable and flashes the board, which is why the gate is not a safety route on its own (below). CI builds it for the vendor board and for the example board and checks that it was built and not run. The part is fictional, so there is nothing to wire: the file `tests/drivers/sensor/example_temp/src/hardware_test.c` is a documented stub that a product replaces.

**Do not read the fixture as a way to run on a board from Twister.** The sources say otherwise:

- [`docs/build.md`](build.md#testing-a-consumer-application) lists the hardware level of consumer tests as "No supported entry point".
- The accepted [test foundation decision 5](test-foundation-proposal.md#decisions) routes hardware through a small Crux device-control tool, [`tools/device_control`](../tools/device_control/README.md), because its gates, evidence and lock sit outside the harness. The tool is untested on hardware.
- The Twister harness's hardware type flashes on every launch, which conflicts with the rule that flashing never happens on launch ([findings](test-foundation-proposal.md#pytest-twister-harness-findings)). Do not use `--device-testing` or `--device-type=hardware` as a safety claim.

A run on a board is a hardware operation. It needs authorisation for the current task, a verified board, probe and flash configuration, and a safe setup ([AGENTS.md](../AGENTS.md#safety-and-workspace-boundaries)). Past approvals do not carry over.

## The example board

`boards/vnd/example_rt1062` is a fictional board with an i.MX RT1062, a QSPI flash, a console UART and the I2C bus that carries the example part. It is a minimal copy of the files that it needs from two NXP boards of Zephyr, `mimxrt1062_fmurt6` for the board skeleton and `mimxrt1060_evk` for the flash node and the rest, with **a name of its own**. The flash configuration block is copied from the vendor board and describes its flash part: replace it for yours. Copied files keep their licence line and name their source.

The board is not a variant added with `board: extend:`. A variant keeps the name of the board it extends, so `CONFIG_BOARD_MIMXRT1060_EVK` stays set and code that tests for that name accepts the variant, whether or not its hardware is the vendor's. Several Crux Zephyr bindings test for a board name and refuse any other, as [Porting Crux to a new board](porting-to-a-new-board.md#33-kconfig-and-devicetree) lists. **The kit does not say that Crux's bindings accept the example board.** It proves the board definition, and the driver on it, with Zephyr alone.

## Static libraries and kernel objects

The [template README](../templates/product/README.md#check-the-whole-product-repository) records that an adapter built as a `STATIC` library failed to link in one product with undefined references to `k_msgq_init` and other kernel message queue functions, while `k_thread` calls in the same file linked, and that the cause was not understood.

The cause is the order of Zephyr's link line (Zephyr v4.4, top-level `CMakeLists.txt` and `cmake/linker/ld/target.cmake`). Zephyr links its own libraries, `app` included, inside `--whole-archive`, and then the kernel archive outside it. The linker takes from the kernel archive only the members that something linked before it refers to. A plain CMake `STATIC` library that `app` links is a dependency of `app`, so CMake places it after those items, after the kernel archive. A kernel function that only this library calls, such as `k_msgq_init` in a small image, is then never taken from the archive and stays undefined. `k_thread` functions are referenced by the kernel itself, so they are linked anyway.

Two forms do not have the problem:

- **A `zephyr_library_named` library of a Zephyr module**, such as the kit's driver. Zephyr adds it to its own libraries, inside `--whole-archive`, before the kernel archive.
- **Sources of the `app` target** (`target_sources(app PRIVATE ...)`), the workaround that the template README gives.

`zephyr_library_named` called from an application's own `CMakeLists.txt` is not the first form: Zephyr warns that in application mode the library is not treated as a Zephyr library.

The probe `tests/product_template_link` tests this. `scripts/test-product-template.sh` links the same adapter, which makes the four message queue calls of the report, in the three ways for `native_sim`, and requires that the plain `STATIC` library fails on an undefined `k_msgq_init` and the other two link. The probe covers `native_sim` only; the report also named the RT1060-EVKB cross-build, which has the same link line.

## Zephyr versions

This guide and the kit are written against Zephyr v4.4. Crux plans to move its pin to Zephyr 4.6 when it is released (planned, not decided or dated; see [ADR-0006](decisions/0006-cryptographic-dependency-policy.md)); the move is a change of its own. A product that follows the pin does the same. When it moves:

- Re-run the kit's tests: they are the check that the example still builds and passes with the new tree.
- Read the Zephyr migration guides for each release between the two, for the classes that your drivers use. The sensor API and the board model have both changed in recent releases.
- Re-check the names that this guide quotes: `DEVICE_API`, `SENSOR_DEVICE_DT_INST_DEFINE`, the `mock_api` field and the emulator backend structure.

Do not rely on this page for a version it does not name.

## Checklist

For each new driver in a product repository:

- [ ] The part has no upstream driver that could be used, or fixed upstream (see [When not to write a driver](#when-not-to-write-a-driver)).
- [ ] The binding is named after its compatible, uses a real vendor prefix, and includes the bus and class bindings.
- [ ] The driver has `DT_DRV_COMPAT`, `DEVICE_API`, `DT_INST_FOREACH_STATUS_OKAY`, and a stated init level and priority.
- [ ] Kconfig has `depends on DT_HAS_<COMPAT>_ENABLED`, and the library is `zephyr_library_named`.
- [ ] No identifier, include or Kconfig symbol uses the `crux_` prefix or a Crux header.
- [ ] Init checks the bus and the part's identifier. Every error is a negative errno, and each is tested.
- [ ] An emulator and unit tests run on `native_sim` in CI, including bus errors and a wrong identifier.
- [ ] The hardware scenario is gated on a Twister fixture, builds in CI, and nothing runs it without authorisation.
- [ ] A reviewer other than the author has checked the registers against the datasheet: the emulator only agrees with the driver.
- [ ] The product's format and static-analysis checks run on the driver sources.
