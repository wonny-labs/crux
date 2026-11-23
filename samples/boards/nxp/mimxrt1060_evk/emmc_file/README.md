# eMMC file (MIMXRT1060-EVKB)

Files on an eMMC disk through the Crux File API, with Reliance Edge as the file system. It is the reference
composition of the File component on eMMC: disk `MMC`, mount point `/MMC:`, mounted once at start-up.

The MIMXRT1060-EVKB has no eMMC, so this image is **link only**: it is built for the board and never flashed. It needs
the optional `crux-reliance` west group (Reliance Edge, GPLv2); without it the build stops on purpose.

## Scenarios

| Twister id | What the image does |
| --- | --- |
| `crux.sample.boards.mimxrt1060_evk.emmc_file` | Starts no mount and writes nothing |
| `crux.sample.boards.mimxrt1060_evk.emmc_file.start` | `CONFIG_SAMPLE_EMMC_START=y`: initialises the disk, mounts the volume and checks the layout |
| `crux.sample.boards.mimxrt1060_evk.emmc_file.settings` | As `.start`, then initialises Configuration on the Settings File backend under `/MMC:/settings/cfg` |

## Checks

- `scripts/test-file-emmc-compile.sh` links the three scenarios for `mimxrt1060_evk@B/mimxrt1062/qspi` and checks
  their configuration and map.
- `scripts/test-storage-emmc.sh` compiles `emmc_storage.c` and `emmc_configuration.c` into the `native_sim` tests
  `tests/native/file_emmc_composition` and `tests/native/configuration_settings_reliance`, which run the mount
  sequence on an eMMC simulator.
- The board test image `tests/board_images/sd_card_power_cut_sequence` reuses `emmc_storage.c` on the microSD disk.

No result comes from an eMMC device or from a board. See [eMMC and Reliance Edge composition](../../../../../docs/emmc-reliance-composition.md)
and the [physical gate](../../../../../docs/emmc-reliance-physical-gate.md).

Old path: `samples/storage_emmc` (see the moved-paths table in [samples/README.md](../../../../../samples/README.md#moved-board-test-images)).
