# microSD probes

A board test image, not a sample. Two physical-gate probes for the RT1060-EVKB microSD card: stack use after a FatFs
workload (`.stack`, `CONFIG_SAMPLE_SD_STACK_PROBE=y`) and a card-removal probe that retries a mount
(`.removal`, `CONFIG_SAMPLE_SD_REMOVAL_PROBE=y`). The default build touches no card. Both probes write to the card:
do not flash them until the physical gate is approved for the current task.

- `scripts/test-file-rt1060-compile.sh` links the three scenarios (`crux.file.sd_card_probe`, `.stack`, `.removal`)
  and checks the option each one sets.
- `tests/native/file_sd_probe` runs the workload and the removal state machine on `native_sim`.
- It compiles `sd_storage.c` and `sd_file_check.c` from `samples/boards/nxp/mimxrt1060_evk/sd_card_file`.

Procedure and results: [microSD physical gate](../../../docs/microsd-physical-gate.md).
