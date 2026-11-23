# microSD card file (MIMXRT1060-EVKB)

Files on the board's microSD card through the Crux File API, with FatFs as the file system: disk `SD`, mount point
`/SD:`. The composition never formats the card and never creates directories; a host prepares the card.

The image is built for `mimxrt1060_evk@B/mimxrt1062/qspi`. This repository's checks only link it. Do not flash an
image that mounts or writes the card until the physical gate is approved for the current task.

## Scenarios

| Twister id | What the image does |
| --- | --- |
| `crux.sample.boards.mimxrt1060_evk.sd_card_file` | Touches no card |
| `crux.sample.boards.mimxrt1060_evk.sd_card_file.start` | `CONFIG_SAMPLE_SD_START=y`: initialises the disk and mounts the card |

`CONFIG_SAMPLE_SD_FILE_CHECK=y` additionally writes, reads back and checks a file after a restart.

## Checks

- `scripts/test-file-rt1060-compile.sh` links both scenarios and checks that only `.start` enables the mount.
- `scripts/test-storage-simulators.sh` runs its sources in `native_sim` tests: `tests/native/file_sd_composition`,
  `file_sd_check` and `file_sd_settings_recover`, on a RAM disk named `SD`.
- The board test images `tests/board_images/sd_card_power_cut_append`, `sd_card_power_cut_replace` and
  `sd_card_probe` compile `sd_storage.c` (and `sd_file_check.c`) from this folder.

See [microSD composition](../../../../../docs/microsd-composition.md) and the
[microSD physical gate](../../../../../docs/microsd-physical-gate.md).
