# microSD power cut during an append

A board test image, not a sample. It appends checked records to a file on the RT1060-EVKB microSD card (FatFs) until
power is cut, so that a host can judge what survives each cut. The default build touches no card;
`CONFIG_SAMPLE_SD_INTERRUPT_TEST=y` (scenario `crux.file.sd_card_power_cut_append.test`) writes to it. Do not flash
the test image until the physical gate is approved for the current task.

- `scripts/test-file-rt1060-compile.sh` links both scenarios (`crux.file.sd_card_power_cut_append`, `.test`).
- `tests/native/file_sd_interrupt` runs the record format and recovery logic on `native_sim`, and
  `scripts/test-storage-simulators.sh` runs the unit tests of the host capture helper in `host/`.
- It compiles `sd_storage.c` from `samples/boards/nxp/mimxrt1060_evk/sd_card_file`. The images of
  `../sd_card_power_cut_replace` and `../sd_card_power_cut_sequence` reuse its sources.

Procedure and results: [microSD physical gate](../../../docs/microsd-physical-gate.md).

Old path: `samples/storage_sd_interrupt` (see the mapping in the [samples layout plan](../../../docs/plans/samples-layout-proposal.md#mapping)).
