# Shared hardware module template

A starting point for an organisation's shared hardware module: a Zephyr module that holds the boards and drivers that two or more products use. The organisation `acme`, its prefix `acmeco`, the module `acme-hw` and the board `acmeco_ctrl_a` are fictional.

Read [Shared boards and drivers across products](../../docs/shared-hardware-modules.md) first. It says when a board or driver belongs here rather than in a product repository or in upstream Zephyr. The products import this module through the [organisation manifest](../organisation-manifest/README.md), or [pin it directly](#without-an-organisation-manifest).

The board files are placeholders: the image does not boot, because the board carries no flash configuration block and no device configuration data.

| Path | Purpose |
| --- | --- |
| `zephyr/module.yml` | Names the module `acme-hw`, and exports its CMake and Kconfig entry points, `board_root`, `dts_root` and its tests |
| `CMakeLists.txt`, `Kconfig` | Entry points for the Zephyr build. They include `drivers/` |
| `drivers/` | One subdirectory per shared driver, each built as a named library with `zephyr_library_named` and enabled from devicetree. Empty until the first driver moves here |
| `dts/bindings/` | One binding per shared driver, and `vendor-prefixes.txt` with the fictional prefix `acmeco` |
| `boards/acmeco/ctrl_a/` | A fictional i.MX RT1062 board in Zephyr's hardware model v2, with its own board name `acmeco_ctrl_a` |
| `tests/module/smoke/` | A Twister test: proves on `native_sim` that the build found the module, and builds the board |
| `ci/west.yml` | The workspace for the module's own CI and for local work on the module, at the organisation's baseline |
| `ci/west-direct.yml` | The same workspace [without an organisation manifest](#without-an-organisation-manifest) |
| `ci/build.yml` | A CI workflow template: Twister on `native_sim` and the cross-build of every board. Copy it to `.github/workflows/` of the module's repository |

## Start the module

Copy this directory into a new repository on the organisation's host, then:

1. Replace `acme`, `acmeco`, `git.example` and the board in every file. Check that the vendor prefix is not in Zephyr's `dts/bindings/vendor-prefixes.txt`: Zephyr already gives `acme` to a real company. Check that the board name is not a Zephyr board name either.
2. Fill in the board from its schematic: console, flash part and size, memory, and the flash configuration block and device configuration data that the defconfig turns off.
3. Pin the new module in the organisation manifest and tag it `v0.1.0`.
4. Set up `ci/build.yml` in the module's repository, with a read-only token for the organisation's repositories.

## Work on the module

The module's own workspace uses the organisation's baseline and blocks the copy of the module that the organisation manifest pins:

```sh
mkdir acme-hw-workspace && cd acme-hw-workspace
git clone https://git.example/scm/acme/acme-hw
west init -l --mf ci/west.yml acme-hw
west update
west crux-pins
west twister -T acme-hw/tests -p native_sim
west twister -T acme-hw/tests -p acmeco_ctrl_a --build-only
```

To try a local change of the module in a product's workspace without moving its pin, point the build at the local checkout:

```sh
west build -b acmeco_ctrl_a product-y/app -- -DZEPHYR_EXTRA_MODULES=/path/to/acme-hw
```

The module keeps its name, `acme-hw`, from `zephyr/module.yml`, so this checkout replaces the workspace's copy in that build. The build record and `west crux-pins` do not see it, so never release such a build. The guide has the details: [Local development](../../docs/shared-hardware-modules.md#local-development).

## Without an organisation manifest

If the organisation has no manifest repository, the module's manifest pins Crux itself. The module repository stays the manifest repository, so `west init` and `west update` work as above.

1. Replace `ci/west.yml` with `ci/west-direct.yml`, under the name `ci/west.yml`, so that `ci/build.yml` and every command stay as they are.
2. Set the `crux-pilot` revision to a full Crux commit SHA. Add each other component the module needs as its own entry, also by full SHA.
3. Keep the Zephyr, SDK and west versions in `ci/build.yml` equal to what that Crux commit uses.
4. Remove the token step of `ci/build.yml` if the manifest names no private repository.

In place of step 3 under [Start the module](#start-the-module), tag the module `v0.1.0`, and in each product's `west.yml` add the module with its remote, full SHA and path, as the `acme-hw` entry of the [organisation manifest](../organisation-manifest/west.yml) does.

## The example driver

The product driver kit (`docs/writing-a-product-driver.md` and the module skeleton in `templates/product/`) adds an example I2C sensor driver with an emulator and tests. `drivers/CMakeLists.txt` and `drivers/Kconfig` show the wiring as comments, and this template carries no driver code.
