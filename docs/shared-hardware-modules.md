# Shared boards and drivers across products

**Status: guidance and templates, 2026-11-16. Nothing here has been built with Zephyr.** This page tells a product team, and an organisation with several products on Crux, where a board definition or a Zephyr device driver lives, when it moves, and how products share it with west. It adds no Crux interface: Crux keeps no company's boards and builds no driver model (see [Crux keeps no boards](#crux-keeps-no-boards)). What was checked, and what was not, is in [Limits](#limits).

It builds on the [Product Composition Guide](product-composition.md), which defines the product repository, the optional organisation manifest and `west crux-pins`. Two templates go with it:

- [`templates/organisation-manifest/`](../templates/organisation-manifest/README.md): an organisation manifest (`acme-manifest`) that imports Crux and pins a shared hardware module, and a product manifest (`product-y`) that imports it.
- [`templates/hardware-module/`](../templates/hardware-module/README.md): a shared hardware module (`acme-hw`) with a fictional board, its own CI workflow template and a test.

The names `acme`, `acmeco`, `git.example`, `product-x`, `product-y` and `acme-hw` are fictional.

## Three layers

| Layer | Holds | Owner | Reaches the product through |
| --- | --- | --- | --- |
| **Product repository** | The product's own board, overlays and drivers for parts that only this product uses | The product team | Its own tree: `boards/`, `drivers/` and `dts/bindings/` beside `app/`, made a Zephyr module by its `zephyr/module.yml` |
| **Organisation hardware module** | Boards and drivers that two or more products of the organisation use | A named owner in the organisation, as for its forks | A plain project entry in the [organisation manifest](product-composition.md#structure), pinned by SHA |
| **Upstream Zephyr** | Drivers and boards for public parts that anyone can use | The Zephyr project and its maintainers | Zephyr itself, at the revision Crux pins |

The product repository is the default. A board or driver moves up a layer only when a criterion below says so, never in advance.

## Where does this board or driver live

| Situation | Where it lives | Why |
| --- | --- | --- |
| One product uses it | Product repository | No second consumer, so nothing to share and no extra pin to move |
| A second product starts using it | Organisation hardware module | One copy, one set of tests, one owner. See [Moving a driver to the shared module](#moving-a-driver-to-the-shared-module) |
| A public part with an upstream Zephyr driver | Upstream Zephyr. Use that driver with a devicetree node and an emulator test | Writing a second driver for it adds maintenance and no value |
| A public part without an upstream driver, and nothing confidential in the driver | Contribute it to Zephyr. Keep a copy in the product or module only until Zephyr has it | Upstream review and maintenance; the copy goes when the pin moves past the merge |
| Code under a confidential vendor licence or NDA | Product repository or organisation module, on a private remote | It may not leave the organisation. See [Licences and private remotes](#licences-and-private-remotes) |
| A product's own board | Product repository, with its own board name | Its schematic belongs to one product |
| A board that two products share, such as a common controller PCB | Organisation hardware module, with its own board name | One definition for both products. See [Board names](#board-names-and-board-extend) |
| A vendor's evaluation kit | Upstream Zephyr | Zephyr already defines it; overlays stay in the product |
| A Crux service, such as the configuration or management services | Crux | Policy above Zephyr, as [ADR-0001 Decision 3](decisions/0001-application-boundary-and-api-stability.md#decision-3-what-crux-will-and-will-not-abstract) lists |

### Crux keeps no boards

Crux carries no company's board definitions and no product driver. [ADR-0001 Decision 3](decisions/0001-application-boundary-and-api-stability.md#decision-3-what-crux-will-and-will-not-abstract) lists "Board support" among what Crux will not provide: Zephyr boards and the product's overlays do that. Crux's own repository holds devicetree overlays and Kconfig fragments for existing Zephyr boards ([porting guide, section 3.1](porting-to-a-new-board.md#31-zephyr-board-support)), and one fictional board, `acmeco_ctrl_a`, as a compile-only placeholder inside the [hardware module template](../templates/hardware-module/README.md). That board is an example for an organisation's module, not board support that Crux offers. So a board that two products share goes into the organisation's module, not into Crux.

## Moving a driver to the shared module

Move a driver when a second product starts using it, not before. Until then it stays in the first product.

1. **Keep the compatible string.** The devicetree `compatible` (for example `acmeco,example-sensor`) is the driver's identity in every board and overlay. Keep it, so that no product devicetree changes. The vendor prefix it uses must be in the module's `dts/bindings/vendor-prefixes.txt`.
2. **Move the binding and the driver together**, in one change: the binding from `dts/bindings/`, the source from `drivers/`, its Kconfig file, the CMake block with `zephyr_library_named`, the emulator and the tests. A binding without its driver, or the reverse, leaves one product with a device that never initialises or a duplicate binding for the same compatible.
3. **Keep the Kconfig symbol name**, so that `prj.conf` and board files of the products need no change.
4. **Run the module's CI** on every board the module carries and on `native_sim`, then tag the module (`v1.1.0`).
5. **Move the module pin** in the organisation manifest to that tag's SHA.
6. **Each product** moves its `acme-manifest` pin, removes its own copy of the binding and driver in the same change, and runs its own checks. Two bindings with the same compatible stop the devicetree step of a build that uses it ("both ... have 'compatible: ...'"), so the removal and the pin move go together.

The product driver kit (`docs/writing-a-product-driver.md`, added separately) describes how to write the driver in the first place. Its example driver is the model for the first move into [`templates/hardware-module/`](../templates/hardware-module/README.md#the-example-driver).

## Versions and pins

- **Module tags.** The module uses SemVer tags, `vMAJOR.MINOR.PATCH`. A change to a compatible string, a binding property or a Kconfig symbol that a product uses is a major change. A new driver or board is a minor change.
- **Pins.** The organisation manifest pins the module by full SHA, with the tag in a comment, as the [Product Composition Guide](product-composition.md#soft-forks) asks for forks. A product pins the organisation manifest by tag or SHA for a release.
- **One Zephyr baseline per organisation.** The module is built against one Crux revision and therefore one Zephyr revision: the ones the organisation manifest pins. Every product that imports the organisation manifest gets the same Crux and Zephyr. A product that needs another Zephyr overrides it and owns the result, as for a [Zephyr patch release](product-composition.md#taking-a-zephyr-patch-release); the module's CI does not cover that build.
- **Moving the baseline.** Run the module's CI against the new Crux pin first, fix the module, tag it, and then move the Crux and module pins in the organisation manifest together. [`ci/west.yml`](../templates/hardware-module/ci/west.yml) follows `acme-manifest` at `main`, so on its own it tests the baseline the organisation already has. To test a new Crux pin before the organisation moves, either push a branch of `acme-manifest` with the new Crux pin and set `revision:` in `ci/west.yml` to that branch on a module branch, or add a temporary `crux-pilot` entry with the new revision and `import: true` to `ci/west.yml` on a module branch (an entry in the importing manifest beats the imported one of the same name, as the [organisation manifest README](../templates/organisation-manifest/README.md) explains). Neither change is merged into the module's main branch.
- **Compatibility record.** The module's release notes name the Crux revision and the Zephyr release each tag was built and tested with.

## CI ownership

| Who | Builds and tests | With |
| --- | --- | --- |
| The module | Every test of the module on `native_sim`, with an emulator for each driver, and a cross-build of every board it carries | Its own workflow ([template](../templates/hardware-module/ci/build.yml)) and the workspace of [`ci/west.yml`](../templates/hardware-module/ci/west.yml), at the organisation's baseline |
| Each product | Its own application for its own boards, `west crux-pins`, and its release checks | Its own CI, at the module revision it pins |
| Crux | Crux and its templates | Crux's CI. It never builds an organisation's module |

The module's CI never flashes or runs a board. A board run is a hardware operation with its own authorisation.

## Licences and private remotes

- **Licence of each file.** Each source file of the module carries an SPDX line. A driver adapted from a Zephyr driver keeps Apache-2.0 and its copyright lines. Code under a vendor licence keeps that licence and its notice.
- **Confidential code.** Code under an NDA or a confidential vendor licence stays on a private remote of the organisation and never goes into a public repository, Crux included. It may go into the module only if every product that imports the module may receive it.
- **Private remotes.** The organisation manifest names the internal host as a remote (`acme`, `https://git.example/scm/acme`). CI reads it with a read-only token limited to the repositories the workspace needs. Use `https://` URLs: `ssh://` URLs lose the purl in the SBOM ([SBOM](product-composition.md#sbom)).
- **Vendor kits.** A module that compiles a vendor kit checks the kit tree against committed per-delivery hash lists and names the delivery it matched. [Vendor kits across repositories](vendor-kits.md) recommends how, together with the kit path rule and what a release records.
- **Optional groups.** A module that needs a Crux optional group, such as `crux-secure-management`, says so. Each product checks the group's licence before it enables it ([Commercial editions](product-composition.md#commercial-editions)).

## What a module changes in the checks

- **`west crux-pins`.** The module, and the organisation manifest repository itself, are not part of the Crux contract, so the command reports them as `PRODUCT` and passes. An override of a Crux pin declared in the organisation manifest keeps its `crux-override` reason in each product and reports `OVERRIDE`. The command does not compare a product with its organisation manifest: a product that pins the module at another revision still sees `PRODUCT`. See the [organisation manifest README](../templates/organisation-manifest/README.md#what-west-crux-pins-reports) and [`west crux-pins`](product-composition.md#west-crux-pins).
- **Build record and firmware identity.** The module is a west project, so the build record lists its commit with every other project. Adding the module adds its Kconfig symbols (at least `CONFIG_ACMECO_HW`) to `.config`, so `firmware_identity` changes even where the image does not. See [Identity](product-composition.md#identity).
- **SBOM.** `west spdx` lists the module as a Zephyr module, with a purl from its URL. On an internal `https://` host the purl carries the host and path, so the outward SBOM must be reduced. See [SBOM](product-composition.md#sbom).
- **Release bundle.** The lock file at the release tag lists the module's commit, so a release does not depend on the organisation manifest's later state ([Release](product-composition.md#release)).

## Board names and `board: extend:`

Zephyr's hardware model v2 names a board target `<board>[@<revision>][/<qualifiers>]` and supports revisions, SoC variants, shields and board extensions. See Zephyr's [board porting guide](https://github.com/zephyrproject-rtos/zephyr/blob/v4.4.2/doc/hardware/porting/board_porting.rst) (`doc/hardware/porting/board_porting.rst`, section "Board extensions", lines 943 to 960 at v4.4.0).

- **Give a shared board its own name**, as the template's `acmeco_ctrl_a` does. Use revisions (`@A`, `@B`) for PCB revisions of the same board and a shield for an add-on board.
- **A `board: extend:` variant keeps the existing board name.** A variant of the vendor's evaluation kit made this way is still `mimxrt1060_evk` to every check that reads the board name. Zephyr defines `BOARD_<board>` from the board name and `BOARD_<board>_<qualifiers>` from the full target (`boards/Kconfig.v2`, lines 5 to 16 at v4.4.0), and an extension adds a variant under an existing qualifier, so the target gains one more qualifier segment (`board_porting.rst`, lines 943 to 960). Read in source, not built:
  - Crux's Zephyr bindings for System, Logging and Serial accept any board with the RT1062 SoC by the SoC and the devicetree, and keep `CONFIG_BOARD_MIMXRT1060_EVK` only to narrow the evaluation kit itself: Rev B for System and Logging (CMake), Logging on LPUART1 and Serial on LPUART3 (`components/system/ports/zephyr/`, `components/logging/ports/zephyr/`, `components/serial/ports/zephyr/serial_binding.c`). An extension keeps that symbol, so it inherits those evaluation-kit limits and takes the kit's console UART and watchdog assumptions without any review, on hardware that may differ.
  - When `CONFIG_BOARD_MIMXRT1060_EVK` is set, the FatFs selections also require the full-target symbol `CONFIG_BOARD_MIMXRT1060_EVK_MIMXRT1062_QSPI` and Rev B (`components/file/ports/zephyr/CMakeLists.txt`, lines 28 to 29, used at lines 33, 66 and 87; `zephyr/Kconfig`, lines 317, 341 and 360). A variant target does not set it, so an extension would still be refused there, with a Kconfig dependency left unmet or a configure error, unless the extension defines that symbol itself, which would again skip the review.

  So the extension inherits the evaluation kit's limits in System, Logging and Serial, and is refused by the FatFs selections. Avoid it for a product board. The [porting guide, section 3.3](porting-to-a-new-board.md#33-kconfig-and-devicetree) lists the bindings that name a board.
- **A board with its own name and the RT1062 SoC is accepted by those Crux bindings** since the board-name refusals were removed (crux-pilot pull request #503, merge commit `8784389a`): System by the SoC and the devicetree WDOG1 node, Logging and Serial by any enabled `nxp,lpuart` node with the existing node checks, and the FatFs microSD selections by the SoC and their devicetree dependencies. Pin conflicts on such a board are the product's review duty, and Crux checks none: the Serial refusal of LPUART3 while a `csi` node is enabled applies to the evaluation kit only (`CONFIG_BOARD_MIMXRT1060_EVK`), where CSI shares pins with LPUART3 and LPUART8. Only checks that apply to the evaluation kit itself still name it: there System and Logging require Rev B, Logging stays on LPUART1 and Serial on LPUART3, and FatFs keeps the Rev B QSPI target; a `board: extend:` variant keeps the kit's name and so inherits those limits. Read the [porting guide, section 3.3](porting-to-a-new-board.md#33-kconfig-and-devicetree) for the current table; the evidence for the accepted case is a compile-only build of a fictional board, no hardware.

## Sysbuild and MCUboot

With sysbuild, every image (the application and MCUboot) is an ordinary Zephyr build that runs module discovery on the same workspace. Read in Zephyr v4.4.0 source, not built:

- `scripts/zephyr_module.py` writes the `board_root` and `dts_root` of each module into the build settings, and `cmake/modules/zephyr_module.cmake` reads them, in each image build.
- Sysbuild itself includes `zephyr_module` and `boards` (`share/sysbuild/cmake/modules/sysbuild_default.cmake`), so it resolves a board from a module's `board_root` before it starts the images, and `sysbuild_root.cmake` passes the roots to the images through the CMake cache.
- The module's `Kconfig` is sourced in each image. A driver symbol with `default y` and `depends on DT_HAS_<COMPAT>_ENABLED` is therefore enabled in MCUboot too when MCUboot's devicetree enables that node. Disable the node in MCUboot's overlay, or the driver in its configuration, when the boot loader must not carry it.

Not verified: a sysbuild build with the template module, and whether `-DZEPHYR_EXTRA_MODULES` given to sysbuild reaches each image.

## Local development

- **The module on its own.** `west init -l --mf ci/west.yml acme-hw` makes the module repository the manifest repository and takes the rest from the organisation manifest, with the organisation's copy of the module blocked ([module README](../templates/hardware-module/README.md#work-on-the-module)).
- **A local change in a product's workspace.** `west build ... -- -DZEPHYR_EXTRA_MODULES=/path/to/acme-hw` adds a local checkout to that build. In Zephyr v4.4.0 `scripts/zephyr_module.py` keys modules by the `name` in `zephyr/module.yml` and reads extra modules after the workspace's, so a checkout with the same name replaces the workspace's copy for that build (read in source, not built). The build record and `west crux-pins` read west projects only, so they see the pinned copy, not the one that was built. Use it for development only, never for a release.
- **All three layers in one workspace.** `west init -l product-y` with the product manifest of the template, then `west update`, gives the product, `acme-manifest`, `acme-hw`, Crux and Zephyr in one workspace (T2).

Zephyr's own documentation: [modules](https://github.com/zephyrproject-rtos/zephyr/blob/v4.4.2/doc/develop/modules.rst) (`doc/develop/modules.rst`, "Build settings" and "Using West") and [west topologies T1, T2 and T3](https://github.com/zephyrproject-rtos/zephyr/blob/v4.4.2/doc/develop/west/workspaces.rst) (`doc/develop/west/workspaces.rst`). Crux's products use T2.

## Limits

**What was run**

- `tests/build/test_shared_hardware_templates.py` checks the structure of both templates and of this page, parses the manifests, and runs real west 1.4.0 on local throwaway repositories: `west manifest --validate`, the three-layer workspace, the module's CI workspace with its blocklist, and `west crux-pins` for each row of the organisation README's table. Fake repositories stand in for Crux, Zephyr and the modules. The Host CI job installs west 1.4.0 and PyYAML, so it runs the west tests too, without a Zephyr tree.

**What was not run**

- No Zephyr build of the template module, its board or its test, on `native_sim` or as a cross-build. No CI of Crux builds them yet.
- The CI workflow template has never run.
- No sysbuild or MCUboot build with a module board.
- No real hosted git server, private remote or token.
- No board.
