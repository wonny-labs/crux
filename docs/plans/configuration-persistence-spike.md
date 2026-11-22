# Configuration that survives reboots and power loss: spike

Status: **spike, for review in a Draft PR. Not adopted.** It recommends a path and a next step and adopts no public
interface, backend, layout or dependency. It authorises no hardware operation. Nothing here ran on a board.

Baseline: `main` at `2c017f685e0215e0e269d4bc77272889d06a07d8`. Zephyr is pinned at v4.4.2
(`dccb09599635bdff17633fa7e9dab014b91dce90`, `west.yml`). The Zephyr source readings below were made in a local
checkout at `684c9e8f32e4373a21098559f748f06915f950c9` (v4.4.0) and should be rechecked at the pin before they are relied on.

## Question

A product keeps its configuration on its product medium: an eMMC with a file system for the main product, and on-chip
or external NOR for smaller products. What does Crux need so that an accepted, saved parameter is still there after a
reboot or a power cut, and so that a power cut never leaves the device unable to load its configuration?

## Answer in short

- **The mechanism is already there and does not need to change.** `crux/configuration.h` (per-parameter BOOL, U32 and
  bounded STRING, defaults, validation, explicit load and save) and its private read-record and write-record port are the
  right boundary. The persistent part is a private provider behind that port, chosen by the composition.
- **On eMMC one provider exists, behind one open decision.** `configuration_settings.c` over the Zephyr Settings File backend on
  Reliance Edge (`CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE`) is merged and passes on `native_sim`, including a power-cut
  replay in which the settings file was never missing. It depends on the Reliance Edge commercial licence, which is open.
- **For NOR, nothing usable exists yet.** The Settings/NVS evidence is simulator-only, the corrections it needs are
  test-only, and the RT1060 FlexSPI NOR driver has unresolved error and termination defects.
- **Recommended path:** keep one provider, `configuration_settings.c`, and pick the Settings backend per medium: Settings
  File on the product's transactional file system for eMMC, and Settings NVS in a dedicated partition for NOR. The
  smallest next step makes the Settings File selection independent of Reliance Edge and proves it on LittleFS over a
  block device on `native_sim`. Then a refused licence costs a backend swap, not a redesign. See
  [Smallest next step](#smallest-next-step).

## What exists today

| Piece | Where | State and evidence | Satisfies the need? |
| --- | --- | --- | --- |
| Configuration mechanism | `components/configuration`, [contract](../configuration-contract.md) | Approved for software-only development. The canonical record encoding is 5, 8 or 4+n bytes. The port tells "missing", a complete record and an error apart. E1 (`Configuration.*`) and E2 suites | Yes, as the portable boundary. It promises no multi-parameter atomicity. Each save is one record |
| No-provider port | `src/configuration_no_provider.c` | Load and save return `NOT_SUPPORTED`. Parameters keep their defaults. The management services link it today | No. Nothing persists |
| Settings provider, eMMC target | `ports/zephyr/configuration_settings.c` under `CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE` (merged in #306) | Needs `CRUX_FS_RELIANCE_EDGE`. It stages corrected `settings_file.c`, `settings_line.c` and `settings_store.c` from `tests/native/configuration_settings_file/candidate.cmake`, because the pinned backend can report a failed write or read as success or as a missing key. `tests/native/configuration_settings_reliance`: 28 cases pass and 1 is skipped. The control on the unpatched backend fails 12. RT1060 link check of `crux.sample.storage_emmc.settings`. [Composition](../emmc-reliance-composition.md) | Partly. The behaviour is right on the simulator. But it is tied to one file system, takes sources from `tests/`, no image links `crux_config_save` together with this provider (the RT1060 management image links it over the no-provider port, and `samples/storage_emmc` has no Configuration consumer), and it has never run on a device. Its tier is Experimental ([readiness](../component-readiness.md)) |
| Power-cut replay of settings saves (W4) | [replay record](../evidence/emmc-reliance/replay-settings/README.md) | 2,174 cut cases on two cache profiles. Invariants I1 to I5 held. The active settings file was never missing. 864 cuts left a `.cmp` temporary, which is not a failure. The record calls this a simulator model, not device evidence | Yes on the model, for Reliance Edge only |
| eMMC composition | [composition](../emmc-reliance-composition.md) (#305) | Mounts `/MMC:`, requires `/MMC:/files` and `/MMC:/settings`, and never formats or creates directories. `CONFIG_CRUX_MMC_CACHE_FLUSH` makes sync reach the medium. Simulator and link evidence only. "There is no physical eMMC evidence" | Yes, as the place the settings file lives |
| File component on Reliance Edge | `CONFIG_CRUX_FILE_RELIANCE_EDGE` (#304), `tests/native/file_reliance` | Simulator only | Not needed by Configuration directly. It shares the volume |
| Settings File on FatFs | `tests/native/configuration_settings_file`, [microSD replace-pattern run](../evidence/microsd-replace-cut/README.md) | A physical run on the EVKB microSD with 100 power cuts. The image did not run the Settings File backend: it repeated the backend's compaction order (write the temporary, close it, `fs_rename`) in a tight loop. 29 of the cuts left no settings file and a complete `.cmp`, because FatFs rename removes the destination first. The record says this rate is not the risk of a deployment, which replaces far less often. With the corrected backend that state loads as an I/O error. A recovery step that renames the `.cmp` exists (`tests/native/file_sd_settings_recover`), but no image calls it | Not for a product. FAT has a known window in which the settings file is missing |
| Settings/NVS candidate, NOR | `tests/native/configuration_settings`, [native validation](../configuration-native-validation.md), [NVS capacity](../nvs-capacity-investigation.md), [NVS start-up read](../nvs-startup-read-investigation.md), [Settings errors](../settings-error-investigation.md) | Simulator-only provider build (`#error` outside `native_sim` with the flash simulator, NVS and data CRC). The NVS and Settings error corrections are unadopted patches. Capacity and CRC were measured on a 16 × 4 KiB simulated partition | No. There is no target selection and no adopted correction |
| RT1060 FlexSPI NOR writes | [storage assessment](../storage-configuration-assessment.md) (historical) | The pinned driver ignores program and erase results, and it polls busy without a deadline while interrupts are locked. The assessment states the XIP closure, allocation and boot-protection gates | No. It blocks writable NOR on this SoC until the driver is fixed or replaced. The reading was made at Zephyr v4.4.0 and needs a recheck at the v4.4.2 pin |
| ZMS | [storage assessment, ZMS row](../storage-configuration-assessment.md#file-system-and-settings-trade-offs) | Settings ZMS exists in Zephyr (`subsys/settings/src/settings_zms.c`). Crux has no test of it. The storage assessment has a source and documentation reading that rates it a viable alternative to NVS | Not yet |
| Issue #16 | GitHub | Open: "Validate and persist controller parameters with Zephyr Settings" | Open |

**Missing for a product:** (1) a provider selection that does not depend on one file system and does not take sources
from `tests/`; (2) a NOR selection; (3) any device evidence of a save surviving a restart or a power cut; (4) an image that links `crux_config_save` over a persistent provider; (5) the licence decision.

## Options

The table compares backends behind the same provider and port. Each row leaves `crux/configuration.h` unchanged.

| | A. Settings File on Reliance Edge (eMMC) | B. Settings File on LittleFS over a block device (eMMC) | C. Settings File on FatFs (eMMC or SD) | D. Settings NVS on a NOR partition | E. Settings ZMS on a NOR partition |
| --- | --- | --- | --- | --- | --- |
| Exists in Crux | Yes, merged, simulator and link evidence | No. LittleFS is in the west allowlist and `tests/native/file_littlefs` runs it over the flash simulator. Zephyr has `FS_LITTLEFS_BLK_DEV` for a disk | Test fixture and a microSD physical run. No target provider | Simulator candidate only | No |
| Power loss | Transactional commit. Rename over the settings file is atomic in the W4 model. The fsync depends on the flush option | Copy-on-write metadata, and rename is atomic by design. Not tested in Crux on a block device. Needs the same flush rule as A | **Known window**: in a tight replace loop on one card, 29 % of cuts left no settings file. It needs the `.cmp` recovery step. FAT orphans clusters | Append-only with ATEs, and data CRC is available. Error propagation needs the unadopted corrections | Append-only. Error propagation is not tested in Crux. Read from source and documentation only |
| Wear | The FTL of the eMMC does the wear levelling. Writes are small. Compaction rewrites the file (`CONFIG_SETTINGS_FILE_MAX_LINES`, default 32) | Same FTL, plus LittleFS block cycling | Same FTL. Same compaction cost | NVS rotates sectors. Endurance has to be estimated from the part, the save rate and GC amplification. Not measured | Similar to NVS. Not measured |
| Licence | Public source is **GPLv2 only**. A product needs the commercial kit ([design D6](emmc-reliance-design.md#d6-licence-boundary)). **Open** | BSD-3-Clause (LittleFS) and Apache-2.0 (Zephyr) | FatFs licence, reviewed in [dependency review](../dependency-review-fatfs-r0.16.md) | Apache-2.0 | Apache-2.0 |
| Portability rules | The provider uses Zephyr Settings only. The file system is the composition's choice | Same provider. A composition choice | Same | Same provider with a different Settings backend. No new HAL | Same |
| Test reach | `native_sim`: shared suite, extra cases and W4 replay, all exist. 32-bit runs in CI | `native_sim`: the shared suite and W4 could run on a LittleFS RAM disk or the eMMC simulator. Not done | `native_sim` plus one board run | `native_sim` with the flash simulator. Fault and capacity suites exist | `native_sim` with the flash simulator. Nothing exists |
| Shared failure domain | Settings share the volume with `/MMC:/files`: space, mount failure and wear are shared, and a directory is not capacity isolation | Same as A | Same as A | A separate partition, no file system | Same as D |
| Main risk | The licence. No device run | Unproven in Crux. LittleFS metadata cost on a large volume. Mount time | The missing-file window | NOR driver defects on RT1060 (writes and XIP). Unadopted Settings and NVS patches | No test evidence. A source reading only |

Not considered further:

- A raw record store on an eMMC partition, without a file system. It would be new Crux code with its own power-loss
  design, which is the "storage manager" that the composition rules avoid. Escalate only if both A and B fail.
- RPMB or reliable write. These are out of scope of the eMMC design (D8).

### If the commercial licence is refused

Option A cannot ship. The provider, the port and the contract stay as they are. Only the file system under the
settings file changes:

1. **B becomes the eMMC path.** It is the only free option whose design gives an atomic rename. It also changes the
   File component's backend, and the atomic replace gap of the File service ([File service assessment](../emmc-reliance-file-service-assessment.md#atomic-replace-through-file)) depends on the same choice, so the two decisions
   should be taken together.
2. C is a fallback only if the `.cmp` recovery step runs at every start, and if the product accepts that the newest save can
   be lost and that FAT leaks clusters after cuts.
3. The Reliance Edge selection stays as an evaluation profile. Images that link it stay test images that are never
   distributed (D6).

What does not change either way: the record encoding, the validation rules, the Settings error corrections, and the
"never format, never create directories" start rules.

## Recommendation

**One provider, a Settings backend per medium.**

- eMMC: `configuration_settings.c` over Settings File on the product's transactional file system. That is Reliance Edge if
  the licence is granted, LittleFS over the block device if it is refused. Do not use FatFs for a product's
  configuration.
- NOR: `configuration_settings.c` over Settings NVS in a dedicated partition with data CRC. NVS has the existing
  capacity, fault and error-correction evidence. ZMS is the alternative if NVS's limits matter. It cannot start before the
  NOR driver and the XIP gates of the storage assessment are settled for the product's SoC.
- Keep the Settings error corrections, but move them out of `tests/` into a module-owned place before any product
  build depends on them. Offer them upstream as a separate decision.

Reasons: the boundary that the contract already approved is reused, so no public interface changes. The provider is
written and tested once. The licence risk is limited to one composition choice. The NOR work depends on a driver fix
that is a separate decision, and it should not hold up eMMC.

## Smallest next step

**Make the Settings File selection independent of Reliance Edge, and prove it on LittleFS over a block device on
`native_sim`.** This is software only. It adds no public interface. It changes a Kconfig dependency and the test
compositions.

Acceptance criteria:

1. A Kconfig selection (name to be agreed) links `configuration_settings.c` with the corrected Settings File sources
   on any file system that the composition mounts, except as decision 4 settles for FatFs. The existing Reliance Edge scenario keeps its behaviour and its case
   counts (28 executed and 1 skipped, then 1 executed and 3 skipped).
2. The shared Settings File suite runs on LittleFS over a RAM disk or the eMMC simulator with
   `FS_LITTLEFS_BLK_DEV`, against the real provider. All shared cases pass, or each failure is explained by a
   recorded LittleFS difference. The unpatched-backend control fails the same characterised set.
3. The W4 power-cut replay runs on the LittleFS profile. I1 to I5 hold, the active settings file is never missing,
   and the controls fail as they do for Reliance Edge.
4. The selection refuses FatFs, or warns at CMake that FatFs needs the `.cmp` recovery step. The owner chooses which in decision 4.
5. An RT1060 link check of an image that has both the Settings File provider and a Configuration consumer, and that
   requires `crux_config_save` in it. Today the management image links it over the no-provider port only, and
   `samples/storage_emmc` has no consumer.
6. The gates are `scripts/test-storage-emmc.sh` and `scripts/test-storage-simulators.sh`, with any new cases added
   there. Results are recorded in the PR with revision, commands and skipped checks.

Out of this step: moving the corrections out of `tests/` (protected hash record and frozen evidence, see the
composition document), NOR, board runs and the commercial kit.

The step after it, behind a board approval: a restart-and-power-cut run of a Configuration consumer on a device with an
eMMC, under the existing [physical gate procedure](../emmc-reliance-physical-gate.md).

## Owner decisions

1. **Reliance Edge commercial licence.** Granted or refused. This note assumes it is open. The recommendation holds
   either way, but a refusal makes B the eMMC path. Recommended: decide it together with the File service's atomic replace work.
2. **Adopt the per-medium shape** (one provider, Settings File for eMMC, Settings NVS for NOR) as the direction for issue
   #16. Recommended: yes. Alternative: wait for a device run first.
3. **Approve the smallest next step** as a work package, including a new Kconfig selection name. It adds cases to the
   protected gate scripts `scripts/test-storage-emmc.sh` and `scripts/test-storage-simulators.sh`, which `AGENTS.md`
   allows for an approved package that changes the component; that PR lists them with the approval. Recommended: yes.
4. **FatFs for configuration.** Refuse it in the selection, or allow it with a mandatory recovery step. Recommended:
   refuse it for products and keep it for the EVKB microSD evaluation profile.
5. **Where the Settings File corrections live.** Move them out of `tests/` (this touches the protected hash record and
   frozen evidence) or offer them upstream first. Recommended: plan the move as its own protected-path change, and
   send them upstream in parallel.
6. **NOR scope.** Which NOR products and SoCs need configuration first, so that the driver work (RT1060 FlexSPI NOR
   errors and deadlines) can be scoped. Recommended: no NOR work until a NOR product names its SoC.

## Probes

No new probe was run for this note. The free disk space was at the stop limit for container work (about 6 GB), and
the existing evidence answered the questions. The B option is unproven until acceptance criteria 2 and 3 run.

## Sources

The contract, composition, readiness, assessment and evidence pages linked above. Zephyr: `subsys/settings/src/settings_file.c`
(compaction writes a temporary and calls `fs_rename`), `subsys/settings/src/settings_zms.c`, and
`subsys/fs/Kconfig.littlefs` (`FS_LITTLEFS_BLK_DEV`), read at v4.4.0.
