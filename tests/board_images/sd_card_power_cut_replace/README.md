# microSD power cut during a file replace

A board test image, not a sample. It rewrites a settings file on the RT1060-EVKB microSD card through a temporary
file and `fs_rename`, the compaction sequence of the Settings File backend, until power is cut. The default build
touches no card; `CONFIG_SAMPLE_SD_REPLACE_TEST=y` (scenario `crux.file.sd_card_power_cut_replace.test`) writes to it.
Do not flash the test image until the physical gate is approved for the current task.

- `scripts/test-file-rt1060-compile.sh` links both scenarios (`crux.file.sd_card_power_cut_replace`, `.test`).
- `tests/native/file_sd_replace` runs its classification logic on `native_sim`, and
  `scripts/test-storage-simulators.sh` runs the unit tests of the host classifier in `host/`.
- It compiles `sd_storage.c` from `samples/boards/nxp/mimxrt1060_evk/sd_card_file` and `sd_interrupt.c` from
  `../sd_card_power_cut_append`. The image of `../sd_card_power_cut_sequence` reuses its sources.

Procedure and results: [microSD physical gate](../../../docs/microsd-physical-gate.md).

Old path: `samples/storage_sd_replace` (see the mapping in the [samples layout plan](../../../docs/plans/samples-layout-proposal.md#mapping)).
