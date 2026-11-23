# microSD power-cut sequence on Reliance Edge

A board test image, not a sample. The images around the power-cut tests on one microSD card of the RT1060-EVKB,
with Reliance Edge as the file system. It needs the optional `crux-reliance` west group.

| Twister id | What the image does |
| --- | --- |
| `crux.file.sd_card_power_cut_sequence` | Nothing (no option set) |
| `.format` | Formats the card once, only when no volume mounts; run first to prepare the card |
| `.start` | Mounts without formatting and writes nothing |
| `.append` | The interrupted append of `../sd_card_power_cut_append` |
| `.replace` | The interrupted replace of `../sd_card_power_cut_replace` |
| `.native`, `.native.start`, `.native.append`, `.native.replace`, `.native.format` | The same five images for `native_sim/native/64` on the eMMC simulator, for the rehearsal |

All board scenarios are link only here. Do not flash them until the physical gate is approved for the current task.

- `scripts/test-file-emmc-compile.sh` links the five board scenarios and checks their options.
- `scripts/test-storage-emmc.sh` builds the `native` scenarios, and `tests/native/reliance_stage_a` rehearses format,
  start, append and replace on one simulator image file.
- It compiles `emmc_storage.c` from `samples/boards/nxp/mimxrt1060_evk/emmc_file` and the `main.c`, `sd_interrupt.c`
  and `sd_replace.c` of the two FatFs power-cut images unchanged, behind the shim header `sd_storage.h`.

Procedure: [eMMC and Reliance Edge physical gate](../../../docs/emmc-reliance-physical-gate.md).

Old path: `samples/storage_reliance_sd` (see the mapping in the [samples layout plan](../../../docs/plans/samples-layout-proposal.md#mapping)).
