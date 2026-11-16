# Secure boot and firmware update: review package

> **Status:** A review package, current on 15 November 2026. It explains what exists for secure boot and firmware update in this repository and what is still open. It adopts nothing. Decisions are in the pages it points to, each with its status.
> **Verified:** The merged build composition for the RT1060-EVK Rev B (MCUboot RAM load with revert, signed with a public test key), by build in CI; the simulator and model results for the eMMC path, by command and `native_sim` run; the desk results, by pinned source and public vendor documents. Each row of section 9 gives its label and file.
> **Not verified:** Everything that needs a board. No boot experiment has run on any board: no signed image has been booted, no unsigned, wrong-key or modified image has been shown to be refused by the boot ROM or MCUboot, and no confirm, revert, update, power-loss or recovery step has run.
> **Read this first / then:** the [boot overview](boot-overview.md), then section 1 of this page. Then the [boot composition](boot-composition.md) page, the [secure boot development plan](plans/secure-boot-development-plan.md) and, before any bench work, the board test procedure (`secure-boot-board-test-procedure.md`, not yet run on any board).

Labels follow the repository's boot records: **Verified by build**, **Verified by command**, **Verified on pinned source**, **Verified by public vendor document**, **Verified in repository**, **Inference** and **Not verified**. A build proves that something configures, builds and signs. It never proves that a board boots. A statement without a label in this page is a pointer to a page that carries the label.

## 1. Purpose and how to use this page

You are asked to review secure boot and firmware update for a real product built on Crux, from the repository alone. This page is the map. It states the design as built, the design as proposed, the evidence behind each claim, and the decisions the team still has to take. It does not repeat the investigations.

Suggested order:

1. Read sections 2 to 5 (what is built, how images are signed, how an update would work, what the confirmed-image erratum changes). Open the [boot composition](boot-composition.md) page and the [WP1a evidence record](evidence/boot-composition/wp1a-evidence.md) beside them.
2. Read sections 6 to 8 (recovery, storage options, threat model). The sources are the [bootloader update investigation](boot-bootloader-update-investigation.md), the [eMMC investigation](boot-emmc-investigation.md) and the [boot and update investigation](boot-update-investigation.md).
3. Check section 9 against the evidence files it names. It lists what was shown by a build, by a command, by a simulator or model run, and by nothing.
4. Take the open decisions of section 10. Each row gives the current recommendation and its source.
5. Use "How to challenge this page" at the end as a list of review questions.

Who reviews what: a firmware reviewer takes sections 2, 4 and 5 and the build evidence; a security reviewer takes sections 3, 6 and 8; a storage reviewer takes section 7; the decision makers take section 10. The page for people who will run the bench tests is the board test procedure. No bench test has run.

## 2. Architecture and chain of trust as built

**What was built.** MCUboot, built with the application by Zephyr's sysbuild, in the mode RAM load with revert, for the NXP RT1060-EVK Rev B (`mimxrt1060_evk@B//qspi`, 8 MiB QSPI NOR). The recipe is the [boot composition](boot-composition.md) page. The chain, as the plan draws it, is: boot ROM, then the first stage (MCUboot), which checks the signature of the application image with ECDSA P-256, copies it to SDRAM and jumps to it ([plan, section 3](plans/secure-boot-development-plan.md)).

| Element | What the repository shows | Label |
| --- | --- | --- |
| Boot ROM | Assumed to read the boot header that MCUboot keeps (flash configuration block at offset 0, image vector table at `0x1000`, boot data and device configuration data after it) and to start MCUboot. That the ROM accepts this layout is not shown. That the ROM runs the device configuration data that brings up the SDRAM before the jump is not shown. | Header layout: **Verified by build** ([WP1a record, section 2](evidence/boot-composition/wp1a-evidence.md): `FCFB` at offset 0, IVT at `0x1000`, vectors at `0x60002000`). ROM behaviour: **Not verified**; the SDRAM order is an **Inference** from vendor text |
| MCUboot | Executes in place from the QSPI NOR in the `mcuboot` partition (128 KiB, `0x000000` to `0x020000`). Uses 51,668 B of 131,072 B of flash and 14,656 B of RAM in OCRAM2 (`0x20200000` to `0x20203940`). | **Verified by build** |
| Slots | Two image slots of 3 MiB: `image-0` `0x020000` to `0x320000`, `image-1` `0x320000` to `0x620000`. `storage` follows (`0x620000` to `0x800000`), with no owner and no writer in M8. The slot size is provisional until a product measures its image. | Partitions: **Verified on pinned source**. Signing uses `--slot-size 3145728`: **Verified by build** |
| Application | Signed image in slot 0, load address `0x80000000`. MCUboot validates the image in RAM, copies it to the SDRAM window (`0x80000000`, 32 MiB), and jumps. The application links no section into the flash range (0 B flash, 41,536 B RAM). Indirect references into flash were not checked. | **Verified by build** for the link and the configuration; the jump is **Not verified** |
| Retained boot information | A 256 B retained region at `0x2027ff00` at the top of OCRAM2, outside the SDRAM load window, named by `zephyr,bootloader-info` in both images. MCUboot writes the running slot, mode, bootloader version and more there, and the application would read it. Survival across the jump is open. | Configuration: **Verified by build**. Survival: **Not verified** |
| Revert | An image that is not confirmed is erased from its slot at the next reset, and the previous confirmed image runs. | Code path: **Verified on pinned source**. Behaviour: **Not verified** |

The four board files hold only this placement: MCUboot's RAM moved to OCRAM2, its executable window set to SDRAM, the retained region, and the share-data settings. Nothing in them is an application (**Verified in repository**: [the four files](../zephyr/boot/boards/mimxrt1060_evk_mimxrt1062_qspi_B/), and `tests/build/test_boot_composition.py`, which keeps them identical to the trial inputs of [evidence/boot-update/trial-inputs/](evidence/boot-update/trial-inputs/)).

**The build route.** The argument set of the composition page selects MCUboot and the mode through `SB_CONFIG_*` options, adds the four files per image, and names no key. MCUboot comes from the optional west group `crux-boot` in [`west.yml`](../west.yml) (MCUboot `6d3b3d2c38ab20c242e5b9abb04d050086383eb2`, v2.4.0, the revision in Zephyr's own manifest), which is off by default. The builds ran on Zephyr v4.4.2 with SDK 1.0.1 and GCC 14.3.0. **Verified by command** for the group, its fetch and `west crux-pins`; **Verified by build** for the argument set.

**What is assumed about the ROM.** Only what the pages state, each with its label: the ROM reads the header and starts the first image (vendor document, **Not verified** on a board); in open configuration authentication errors are logged and the image runs, in closed configuration an authentication error aborts to the serial downloader (**Verified by public vendor document**, not run); a Zephyr-built image carries no signature structure for the ROM, because `CSF_ADDRESS` is `0` (**Verified on pinned source**). This work uses no fuse and no ROM authentication. Trust level T0 is the level this work aims at; it has not been shown on a board (section 8).

| Merged component | Where it lives | Status |
| --- | --- | --- |
| MCUboot in the optional group `crux-boot` | [`west.yml`](../west.yml), [Product Composition Guide](product-composition.md) | merged (#339) |
| Composition recipe | [boot-composition.md](boot-composition.md) | merged (#340) |
| Board files for the RT1060-EVK Rev B | [`zephyr/boot/boards/mimxrt1060_evk_mimxrt1062_qspi_B/`](../zephyr/boot/boards/mimxrt1060_evk_mimxrt1062_qspi_B/) | merged (#437) |
| Build, sign and verify check | [`scripts/test-boot-composition.sh`](../scripts/test-boot-composition.sh), run by the `runtime` shard of [`.github/workflows/zephyr.yml`](../.github/workflows/zephyr.yml) | merged (#437) |
| File and wiring tests | [`tests/build/test_boot_composition.py`](../tests/build/test_boot_composition.py) | merged (#437) |
| Trailer replay on the eMMC simulator | `tests/native/emmc_trailer/`, [record](evidence/boot-emmc/trailer-replay/README.md) | merged (issue #310) |
| eMMC flush correction and simulator | [`patches/zephyr/mmc-cache-flush.patch`](../patches/zephyr/mmc-cache-flush.patch), [M14 design](plans/emmc-reliance-design.md) | merged |

## 3. Image format and signing

**What the pages state.** The application is signed by `imgtool` through sysbuild with `--header-size 0x400 --slot-size 3145728 --align 1 --load-addr 0x80000000`, with the RAM-load flag set. The signed image carries a SHA256 digest, a KEYHASH (the SHA-256 of the public key) and an ECDSA P-256 signature. Signed image size: 33,051 B at Zephyr v4.4.2. An ECDSA signature varies in length by one byte and is randomised, so two signatures of the same payload differ and a signed file cannot be compared by hash; unsigned images reproduce byte for byte (all **Verified by build**: [WP1a record, section 2](evidence/boot-composition/wp1a-evidence.md), [Stage 8](evidence/boot-update/stage8-reproducibility-and-signing.md); the reproducibility result is from the Zephyr v4.4.0 trial builds).

**Trailer.** In RAM load with revert, the slot trailer is a state machine of a magic, `image_ok`, `copy_done` and `swap_info`, each one `BOOT_MAX_ALIGN` below the last. MCUboot's CMake estimates are 198 B (image footer) and 48 B (upgrade footer) in the Zephyr v4.4.0 trial build ([Stage 5](evidence/boot-update/stage5-trial-builds.md)); the real trailer use was not measured (**Verified on pinned source** for the layout rules, [replay record](evidence/boot-emmc/trailer-replay/README.md); estimates **Verified by build** at v4.4.0, effective use **Not verified**).

**Keys: the public test key for builds; a private development key for bench tests (decision 18).**

- The sysbuild default key at v4.4.2 is MCUboot's published test key `root-ec-p256.pem`. The CI check uses it and the build log warns that it is for debug use. **It is public. Images signed with it must never be programmed to a board.** It signs no release (**Verified by build**, [boot composition](boot-composition.md)).
- This repository holds no signing key and no script or build step that generates an image-signing key; a tester generates a private development key at the bench (decision 18). A test checks that no key or certificate file sits beside the board files (**Verified in repository**). A product passes its own key with `-DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE`.
- The Zephyr MCUboot port holds exactly one key, so a leaked signing key can only be answered by a new bootloader with another key (**Verified on pinned source**; the upstream statement of the problem is an open proposal, not a shipped feature).
- For board tests, the project owner decided on 2 November 2026 that a fixed development key is generated outside the repository, in a directory that is not shared, when a hardware test is approved, and that only its public key is committed then ([boot and update investigation, owner decision 18](boot-update-investigation.md)). No such key exists yet.
- `imgtool` is Apache-2.0. It imports `cryptography`, `cbor2`, `intelhex` and `click`; the Python of the unmodified Dev Container bootstrap has no `cryptography` and no `cbor2`, so a signing build needs its own environment (**Inference**, WP1a finding F5).

**What production key handling must decide.** No page decides these; they are questions for the team, and the plan's rows that touch them are cited in section 10.

1. Algorithm and size, for the application key (this work uses ECDSA P-256) and for the ROM's authentication key, which is a separate root (plan D6).
2. Key custody: who holds the key and where it is kept.
3. How many keys: the Zephyr port embeds one; the plan records up to four ROM key slots (plan D6; which slots are revocable on the RT1060 is **Not verified**).
4. Rotation and revocation: how a key is replaced, and how units in service get a bootloader that trusts the new key (section 6).
5. Where signing happens, and who may start it.
6. How a build proves that it was signed with the production key. No page defines this. The CI check shows only that `imgtool verify` accepts the test key and refuses a key of another type and an image changed after signing; that checks the signing tool on build output, not a boot result.

## 4. The update flow as designed

**Mode.** Rank 1, RAM load with revert, is the mode the composition builds. The owner accepted on 7 November 2026 that RAM load into SDRAM is the M8 reference execution model; the ranking of modes itself is a recommendation that the plan does not adopt ([plan, section 2](plans/secure-boot-development-plan.md); [boot and update investigation](boot-update-investigation.md)). Reason for rank 1 (**Verified on pinned source**): it is the only stock mode in which the application does not execute from NOR while it writes NOR.

**How an image reaches the inactive slot.** The recommended path is that the application receives the whole image, optionally into an SDRAM buffer, checks size, signature and version, and then writes the inactive NOR slot in one bounded phase with network activity stopped (staging variant (c), a recommendation). Staging on microSD is deferred (accepted 7 November 2026). Accepted on 7 November 2026: the application rejects an older image before any NOR write, and a network-facing update needs authenticated and authorised requests and an application-side check before any NOR write. No code implements any of this.

**Test request, confirm, revert** (all **Verified on pinned source**, not run):

| Step | What the code does |
| --- | --- |
| Test request | The application marks the new image as pending. The stock `boot_request_upgrade()` always opens slot 1. When the application runs from slot 1 and writes slot 0, the request writes nothing and the bootloader later erases the new image without an error (the effect is an **Inference**). Remedies: application code that marks the inactive slot, or an image signed with `--pad` so that writing it is the request. |
| First selection | The bootloader picks the valid slot with the highest version. If the trailer magic is not good, or `copy_done` is set without `image_ok`, it erases the whole slot. Otherwise it writes `copy_done`, copies the image to SDRAM, validates it there and jumps. |
| Confirm | The running application writes `image_ok` on its own slot. |
| Revert | An unconfirmed image is erased at the next reset (a whole 3 MiB slot) and the previous confirmed image runs. |

**Owner decision 13** (2 November 2026): M8 test images are signed with `--pad` and placed with development tools; the application-driven path is designed in M9, where application code that marks the inactive slot is preferred.

**What exists in code today.** Very little. The controller sample has no update code and no confirm code, and links no flash driver (`CONFIG_FLASH` is not set), so no application write path was built (**Verified by build**, [Stage 5](evidence/boot-update/stage5-trial-builds.md)). A search outside `docs/` finds no call of `boot_request_upgrade`, `boot_write_img_confirmed` or `boot_set_next` (**Verified by command**, 15 November 2026). The bootloader's own flash writes (`copy_done`, whole-slot erase) happen while it executes from the same NOR. The data-closure failure that issue #22 found is present in that MCUboot write path, so the scope of issue #165 must be decided before any M8 hardware step that lets the bootloader write the NOR (decision 16, 2 November 2026; **Verified by build**, author disassembly, [flash XIP evidence](flash-xip-evidence.md)).

**What M9 proposes.** The [image-state contract proposal](plans/image-state-contract-proposal.md) (status: adopted as Experimental by the owner for rows I1 to I7 on 15 November 2026, I8 and I9 open; no code is merged) describes a narrow public header `crux/image_state.h`, Experimental at first, with a Linux Host provider and a Zephyr provider over MCUboot's own calls. It has three operations on state (query, request a test boot, confirm), refuses a test request unless the image in the slot is strictly newer than the running one (major, minor, revision; the build number is ignored), fails closed when the shared boot data is missing, and derives "reverted" as an outcome from a boot record plus an attempt record that the update agent persists. Its conformance cases run on the Host, on `native_sim` and, for what only a board shows, on the target. Nothing of it exists in code. Section 10 gives its decisions.

## 5. Revert, confirmation and the Zephyr v4.4.2 confirmed-image erratum

The [boot and update investigation](boot-update-investigation.md) was written from builds of Zephyr v4.4.0. It says in three places that the default build writes no confirmed image and that RAM load with revert does not imply one. That was true at v4.4.0. At v4.4.2, which Crux pins, it is not:

- RAM load with revert implies `MCUBOOT_GENERATE_CONFIRMED_IMAGE` (`modules/Kconfig.mcuboot:274`, commit `c219dde148e` of 1 July 2026), so the build runs a second imgtool command with `--pad --confirm` (**Verified on pinned source**).
- The build therefore also writes `zephyr.signed.confirmed.bin`, 3,145,728 B, the slot size, with MCUboot's trailer magic and the confirm flag at the end (**Verified by build**, [WP1a record, finding F4](evidence/boot-composition/wp1a-evidence.md)).
- `zephyr.signed.bin` is still unpadded (33,051 B) and carries no trailer magic. The CI check does not test for the confirmed file.
- How MCUboot treats the confirmed file is **Not verified**. It is expected to treat it as already confirmed (**Inference**); nothing was booted.

**Which file a revert test must use.** Not the confirmed file, because an image that is already confirmed cannot show a revert (**Inference**). The [boot composition](boot-composition.md) page says to use the unconfirmed `zephyr.signed.bin`. Note the tension with owner decision 13 and with Stage 5 section 9 of the investigation: `zephyr.signed.bin` has no trailer magic, and the investigation infers that under rank 1 the bootloader erases such a slot at first selection unless the application writes the magic or the image is padded. No page names a build output that is padded and unconfirmed (**Verified in repository**), so which file a bench revert test uses is open until the board test procedure fixes it. The procedure's cases T5a (the unpadded `zephyr.signed.bin`) and T5c (a padded, unconfirmed image that the tester builds by hand with `imgtool sign --pad`, not a build output) together test the decision 13 tension. A reviewer should treat that as an open point (section 10).

## 6. Recovery

**State plainly: recovery work has not started.** The plan (Phase 1) requires a non-destructive recovery path to be proved before any physical boot experiment. That path is not built (a design note on the options is a Draft, #459, not merged), and the ROM serial downloader check (issue #309) is planned and has not run.

What the pages state:

- **One bootloader copy.** Stock MCUboot cannot update itself, and the `mcuboot` partition is not an image slot. The project owner decided on 7 November 2026 (issues #297 and #299, as recorded in the [plan](plans/secure-boot-development-plan.md), section 2) on service recovery for M8 and M9 through the ROM serial downloader: a single bootloader copy that is not field-updatable. The decision is revisited after #165, #298 and the M8 hardware results.
- **ROM serial downloader as the service route.** The vendor manual, read in a third-party-hosted copy, says an error during internal boot falls through to the serial downloader, and boot-mode pins can select it. It needs physical access and, to program NOR, a flashloader loaded through it. In closed configuration it needs a flashloader signed under the device's key (**Verified by public vendor document**; applying it to a corrupt first sector is an **Inference**; it was not run).
- **A valid but defective bootloader** is not caught by the fall-through. With no bootable slot image MCUboot logs and loops, and no watchdog resets it unless one is enabled (the logging and the loop are **Verified on pinned source**; the watchdog effect is **Inference**, [bootloader update investigation](boot-bootloader-update-investigation.md)).
- **Conclusions of the [bootloader update investigation](boot-bootloader-update-investigation.md)** (a desk record, nothing adopted unless decided): no option becomes a milestone now; M9 should declare the bootloader's update and recovery level and carry the bootloader version in the boot-result record; a bounded ROM recovery check on the EVKB, without fuse writes, needs its own hardware approval; a two-stage design (a small first stage that never writes flash, plus an updatable second stage in two banks) stays the candidate if a field-update requirement is confirmed. Every option that writes NOR still depends on #165.

**Unknown:** whether a corrupt flash configuration block or vector table falls through to the serial downloader; the source and licence of the flashloader; what the serial downloader does when disabled by fuse; whether the ROM's secondary-image mechanism works for NOR; how many root-key slots are revocable. All **Not verified**; most need a board and some need documents the investigations could not read.

## 7. Storage options

| Option | What exists | What it shows | What it does not show |
| --- | --- | --- | --- |
| QSPI NOR for the slots (today) | The composition of sections 2 and 3, build only. | A signed image builds, links for SDRAM and verifies with the signing tool (**Verified by build**). | Any boot, any write by the bootloader on hardware (blocked by #22 and #165). |
| eMMC as the slot medium | Desk investigation, [eMMC boot and update feasibility](boot-emmc-investigation.md). | The MCUboot port reads slots only through Zephyr flash-API devices, so slots on eMMC need a new flash-API driver over the MMC disk layer, and no such driver is in the pinned tree (**Verified on pinned source**). | Whether the ROM boots an eMMC with a Zephyr-built header, where the first stage sits in a boot partition, the SDRAM and card state at hand-over (**Not verified**). |
| Flash-API driver prototype | A Draft prototype, pull request #435, not merged. The project owner approved on 14 November 2026 a read/write prototype tested on the `native_sim` eMMC simulator, with adoption left to a later decision (plan, section 2). | Nothing in this page relies on it. | Its text is not in the repository; adoption is decision D2 (section 10). |
| Trailer replay on the eMMC simulator | Merged. [Record](evidence/boot-emmc/trailer-replay/README.md). | In models of two cache behaviours, MCUboot's trailer sequences for RAM load with revert kept the safety properties (a valid image boots, the confirmed slot stays unchanged) in all 566,692 cases when slots are aligned to the native unit. Acknowledged confirms and requests are lost without a flush. | It runs no MCUboot, no C simulator, no device. Swap modes were not replayed. **Verified by command, models only.** |
| Reliance Edge, a data file system | M14 design and replay records ([design](plans/emmc-reliance-design.md), [replay](evidence/emmc-reliance/replay-reliance/README.md)). | After modelled power cuts a replaced file is whole old or whole new, in the simulator's model on `native_sim`. | It is for application data, not for images. It does not prove atomic image activation, which is a trailer state machine on raw slots. Boot partitions are out of its scope. |

Further facts, with labels. At the pinned Zephyr a disk sync does not flush the eMMC cache; a build-local correction is on `main` (**Verified on pinned source**, **Verified in repository**). Reliance Edge is GPLv2 only and sits in the opt-in group `crux-reliance` (**Verified in repository**). No eMMC-bearing RT1060 target exists, and the owner decided on 7 November 2026 that eMMC adds no M8 or M9 exit criterion (plan, section 2). The replay lists what a driver must do, as a result for models: emulate erase by writing `0xFF` and report that erase value, flush after every call that touches a trailer and every erase, report write block and `BOOT_MAX_ALIGN` consistently, and place slots on native-unit boundaries.

## 8. Threat model summary and assumptions

The plan defines trust levels, declared per result and never implied ([plan, section 3](plans/secure-boot-development-plan.md)):

| Level | What holds | Reached |
| --- | --- | --- |
| T0 | MCUboot verifies the application with a development key on every boot. No hardware root of trust. | Intended for M8; not shown on a board |
| T1 | T0 plus the application-side version policy and test, confirm and revert. | M9; not started |
| T2 | T1 plus a HAB-signed first stage in open configuration, which adds checking and reporting but no root of trust. | Phase 4; not started |
| T3 | Closed configuration: the ROM aborts to the serial downloader on an authentication error. | Phase 5; a product decision |

**What the design protects against.** An application image that does not verify against the key in MCUboot is not run, because MCUboot validates the image on every boot in RAM load (**Verified on pinned source**; nothing was run). An unconfirmed image is erased and the previous one runs (code path only). A torn image is caught by the validation of the image hash and signature, not by a store (**Inference** from pinned source; in the replay models the safety properties held).

**What it does not protect against** (T0, from the [boot and update investigation](boot-update-investigation.md), **Inference** unless noted):

- Anyone with flash or debug access can replace the bootloader and its embedded key. The ROM does not authenticate the bootloader in open configuration (errors are logged, **Verified by public vendor document**).
- In every stock mode an older signed image can boot under some condition. RAM load has no bootloader rejection, so the application's own version policy (accepted) is the only check (**Verified on pinned source**). There is no hardware anti-rollback counter at the pin.
- An unauthenticated update request could still cause NOR writes and erases or mark an image pending. Authentication of requests is required before any network-facing update (accepted); none is built.
- There is no image confidentiality. BEE stays out of M8 (accepted 7 November 2026). MCUboot image encryption is permitted with RAM load but is not built, and protection of its key is open.
- Interrupted writes by the bootloader on real NOR, bus masters and cache state at the jump are not examined on hardware.

**Assumptions.** Each is stated so a reviewer can reject it.

| Assumption | Label |
| --- | --- |
| An attacker may have physical access, and flash or debug access. The EVKB stays in the open configuration and debug is not locked. | Plan D1 row; consequence **Inference** |
| No fuse is programmed and no closed configuration is used in M8 or M9. | **Verified in repository** (no fuse operation in any record) |
| The ROM starts MCUboot from the header as built, runs the SDRAM configuration data first, and leaves the SDRAM usable. | **Not verified** |
| The retained boot information survives the jump to the SDRAM image. | **Not verified** |
| Cache and MPU state at the jump are safe after the CPU copy into cached SDRAM (both trial builds of the Zephyr v4.4.0 trial set `BOOT_DISABLE_CACHES=y` and `MCUBOOT_CLEANUP_ARM_CORE=y`, [Stage 5](evidence/boot-update/stage5-trial-builds.md)). | Configuration **Verified by build**; behaviour **Not verified** |
| A whole-slot erase at revert completes in an acceptable time and the watchdog (none configured in MCUboot) does not interfere. | **Not verified** |
| The erase size the update path may rely on (4 KiB in the devicetree, 64 KiB in the flash algorithm used on the board). Boundaries stay 64 KiB aligned until measured. | **Not verified** |
| MCUboot's public test key never reaches a board. | Procedural; **Verified by build** that CI uses only the public key |

## 9. What is verified by build, by run, by nothing

"By board" is empty for every boot claim: nothing has run on a board. "By run" means a command, `native_sim` or model run on a host.

| Statement | Label | Kind | Evidence |
| --- | --- | --- | --- |
| The argument set configures, builds MCUboot (51,668 B) and the application, and signs it (33,051 B) | Verified by build | Build, CI `runtime` shard, run 43665141488 | [boot composition](boot-composition.md), [WP1a record](evidence/boot-composition/wp1a-evidence.md) |
| `imgtool verify` with the public test key passes; a key of another type and a byte changed after signing are refused | Verified by build | Build plus tool run, CI | [`scripts/test-boot-composition.sh`](../scripts/test-boot-composition.sh) |
| MCUboot is configured for RAM load, revert, ECDSA P-256 and the SDRAM window | Verified by build | `.config` check in CI | same script |
| The application links for SDRAM; no section in the flash range | Verified by build | Trial build, Zephyr v4.4.0 tree | [Stage 5](evidence/boot-update/stage5-trial-builds.md) |
| The build also writes the padded confirmed image at v4.4.2 | Verified by build | Full build, not checked by CI | [WP1a record, F4](evidence/boot-composition/wp1a-evidence.md) |
| Twelve M7 reference builds still exit 0 at `1447750`; not repeated at later `main` | Verified by build | Cross-builds and `native_sim` builds | [m7-baseline-1447750.json](evidence/boot-composition/m7-baseline-1447750.json) |
| Unsigned images reproduce; ECDSA signatures are randomised | Verified by build | Two clean trial builds | [Stage 8](evidence/boot-update/stage8-reproducibility-and-signing.md) |
| The MCUboot write path has the #22 data-closure failure | Verified by build | Author disassembly outside the Dev Container | [Stage 6](evidence/boot-update/stage6-layout-and-write-analysis.md), [flash XIP evidence](flash-xip-evidence.md) |
| The group `crux-boot` fetches MCUboot; `west crux-pins` reports it | Verified by command | `west` in a scratch workspace | [WP1a record, section 5](evidence/boot-composition/wp1a-evidence.md) |
| Board files equal the trial inputs; no key file beside them | Verified in repository | Host tests | [`tests/build/test_boot_composition.py`](../tests/build/test_boot_composition.py) |
| Trailer sequences keep the safety properties in the models | Verified by command | Python model run, 566,692 cases; not `native_sim` | [trailer replay](evidence/boot-emmc/trailer-replay/README.md) |
| Power-cut replays of FatFs and Reliance Edge on the eMMC simulator | Verified by command | `native_sim`, simulator model | [replay record](evidence/emmc-reliance/replay-reliance/README.md) |
| MCUboot selection, erase, confirm and revert rules | Verified on pinned source | Source reading | [image-state proposal](plans/image-state-contract-proposal.md) |
| ROM fall-through, open and closed behaviour | Verified by public vendor document | Vendor statement, not run | [bootloader update investigation](boot-bootloader-update-investigation.md) |
| Boot, refusal of bad images, confirm, revert, update, power loss, recovery | Not verified | Nothing has run | none |
| Shared boot information survives the jump; ROM accepts the layout | Not verified | Needs a board | none |
| Rejection of an oversized or misaligned image | Verified by command for the inspector's `fit` decision on synthetic images (a model decision). Not verified for `imgtool` and MCUboot: the check against the real images and `imgtool sign` is called by the composition script (approved by the owner on 2026-11-16, #489) and has not run on a real build | Host tests only | [boot image inspection](boot-image-inspection.md) |
| Reproducibility of the committed composition | Not verified. The comparison logic is Verified by command on synthetic build trees; the check of two real builds is prepared and not wired | Host tests only | [boot reproducibility](boot-reproducibility.md) |
| RT1170-EVK composition | Not verified | Not built | none |
| HAB structure, closed configuration, eMMC hardware | Not verified | Not started | none |

## 10. Open decisions for the team

Unless a row says otherwise, nothing below is adopted. Recommendations are the ones in the cited pages.

| Decision | Current recommendation | Source |
| --- | --- | --- |
| Image-state contract (M9, issue #297): adopt `crux/image_state.h` as an Experimental public contract, or use the slot-aware stock call in each product adapter (Option 2). **The owner approved rows I1 to I7 as recommended on 15 November 2026 (no implementation is approved); I8 and I9 stay open** | I1: adopt, narrowly. I2: three operations only (query, test request, confirm). I3: "reverted" is an outcome from a boot record plus an attempt record. I4: refuse a request unless strictly newer. I5: compare major, minor, revision. I6: fail closed. I7: Experimental until the update agent and a second consumer use it, else fold it into the update agent. I8: Host and `native_sim` conformance plus target evidence. I9: bootloader version from the bootloader build, with a "not known" flag. Rejecting I1 revises #297's acceptance criterion, the M9 exit evidence and #191 | [Image-state contract proposal](plans/image-state-contract-proposal.md), Decisions. Its open questions Q1 to Q9 carry their own recommendations |
| Which file a bench revert test uses (section 5) | Use the unconfirmed `zephyr.signed.bin`, as the composition page and the investigation's erratum say. The tension with decision 13 and with Stage 5 section 9 (an unpadded image has no trailer magic and is inferred to be erased at first selection) is open; the board test procedure records the outcome for both the unconfirmed and the confirmed file, and its cases T5a (the unpadded `zephyr.signed.bin`) and T5c (a hand-built padded, unconfirmed image) together test the decision 13 tension | [Boot composition](boot-composition.md), [boot and update investigation](boot-update-investigation.md) |
| eMMC flash-API driver (plan D2): adopt, and where it lives | The Draft prototype is chosen. If adopted, Crux module first behind an off-by-default option, upstream later; adoption needs its own scope decision | [Plan, section 6](plans/secure-boot-development-plan.md) |
| eMMC validation hardware (D3), product inputs for eMMC (D8), a separate milestone (D10) | D3: EVKB with an eMMC adapter for software, a product-class board for ROM boot. D8: collect before the slot layout and provisioning profile are fixed. D10: no, track under M8 and M9 | Plan, section 6 |
| RT1170-EVK composition: the project owner set it aside for now on 15 November 2026. A design note with four questions (#445) and its starting files (#460, Draft) are not merged. RT1: the starting values (executable window, MCUboot RAM, retained region, slots); RT2: which application the RT1170 build uses; RT3: where the RT1170 build runs in CI; RT4: how the check script handles a second board | The recommendations are in the unmerged note, not on `main`, and are not repeated here | The RT1170 facts in the repository are desk only: [Stage 7](evidence/boot-update/stage7-rt1170-delta.md) (**Not verified** for any build) |
| Closed configuration and production keys (plan D1, D4, D5, D6) | D1: plan for closed configuration in production, keep development and the EVKB open. D4: application-side check only until D1, then pick by board features. D5: keep a signed-only recovery path, decide with D1. D6: RSA-3072 or larger, offline keys in an HSM, up to four slots; revocable slots **Not verified** | [Plan, section 6](plans/secure-boot-development-plan.md) |
| MCUboot crypto backend (D9) | Decide under ADR-0006 with a size and boot-time build comparison, before M8 board evidence. ADR-0006 was accepted on 14 November 2026 and decides no MCUboot backend | [Plan, D9](plans/secure-boot-development-plan.md), [ADR-0006](decisions/0006-cryptographic-dependency-policy.md) |
| Field-updatable bootloader (D7) | Keep service recovery; decide again after #165, #298 and the M8 hardware results; the two-stage design stays the candidate | [Plan, D7](plans/secure-boot-development-plan.md), [bootloader update investigation](boot-bootloader-update-investigation.md) |
| Other rows of plan section 6 and the investigations | Where the boot code's Kconfig and CMake hooks go is not decided (plan, section 8). Rows 12 and 15 of the [boot and update investigation](boot-update-investigation.md) are not decided | Pages named |

## 11. Where to look

| Page | One line |
| --- | --- |
| [boot-overview.md](boot-overview.md) | Orientation, phases and what is merged |
| [boot-composition.md](boot-composition.md) | The build recipe, the argument set, what the build produces |
| [evidence/boot-composition/wp1a-evidence.md](evidence/boot-composition/wp1a-evidence.md) | WP1a builds, sysbuild mechanisms, layout decision, M7 baseline |
| [plans/secure-boot-development-plan.md](plans/secure-boot-development-plan.md) | Phases, decisions D1 to D10, trust levels, tooling, risks |
| [boot-update-investigation.md](boot-update-investigation.md) | Why RAM load with revert, modes, trial builds, owner decisions, the v4.4.2 erratum; evidence in [evidence/boot-update/](evidence/boot-update/README.md) |
| [boot-bootloader-update-investigation.md](boot-bootloader-update-investigation.md) | Updating or recovering a deployed bootloader; evidence in [evidence/boot-bootloader-update/](evidence/boot-bootloader-update/README.md) |
| [boot-emmc-investigation.md](boot-emmc-investigation.md) | eMMC boot and update feasibility; evidence in [evidence/boot-emmc/](evidence/boot-emmc/README.md) |
| [plans/image-state-contract-proposal.md](plans/image-state-contract-proposal.md) | The M9 proposal |
| [plans/emmc-reliance-design.md](plans/emmc-reliance-design.md) | The data file system on eMMC (M14) |
| [decisions/0006-cryptographic-dependency-policy.md](decisions/0006-cryptographic-dependency-policy.md) | The crypto dependency policy |
| [flash-xip-evidence.md](flash-xip-evidence.md) | Flash writes while executing from the same NOR (#22) |
| [product-composition.md](product-composition.md) | How a product adds the `crux-boot` group |

**Glossary**, as the pages use the terms.

- **Slot:** a flash partition that holds one application image (`image-0`, `image-1`).
- **Trailer:** the last bytes of a slot, where MCUboot keeps the magic, `image_ok`, `copy_done` and `swap_info`.
- **Confirm:** the running application writes `image_ok`; without it the image is on trial.
- **Revert:** an unconfirmed image is erased at the next reset and the previous confirmed image runs.
- **RAM load:** MCUboot validates the image, copies it to RAM (here SDRAM) and runs it from there.
- **Sysbuild:** Zephyr's build of several images, here MCUboot and the application, with signing.
- **HAB:** the boot ROM's authentication of the first-stage image. In open configuration errors are logged and the image runs; in closed configuration an error aborts to the serial downloader. This work uses neither.
- **SRK:** the root-key hash held in fuses that the ROM checks in closed configuration. No fuse is written in this work.

## Known inconsistencies in the records

These are places where two pages of the repository disagree or where an older record is out of date. They are listed so that a reviewer is not surprised. The older records are accepted evidence or decisions and are not edited to fix them.

| Where | What | How to read it |
| --- | --- | --- |
| [WP1a evidence record](evidence/boot-composition/wp1a-evidence.md) | Says a full signing build without the key argument was not run, and that the board files are added by the next task | Both were done later: the [composition page](boot-composition.md) records the signing build without a key argument as Verified by build in CI, and the board files exist. The composition page is the current statement |
| [Boot and update investigation](boot-update-investigation.md) | Says RAM load with revert implies no confirmed image | True for Zephyr v4.4.0 only. The erratum under its Status table says so; section 5 of this page explains it |
| [Boot and update investigation](boot-update-investigation.md) and the composition page | Decision 13 says M8 test images are signed with `--pad`; the composition page says a revert test uses the unconfirmed `zephyr.signed.bin`, which is unpadded; no page names a padded but unconfirmed build output | Which file a bench revert test uses is open. The [board test procedure](secure-boot-board-test-procedure.md) tests the unpadded, the padded unconfirmed and the confirmed image and records what happens |
| [Image state contract proposal](plans/image-state-contract-proposal.md) | Says `west.yml` does not import MCUboot | MCUboot is now in the optional group `crux-boot` |
| [ADR-0006](decisions/0006-cryptographic-dependency-policy.md) | Calls the pull request that adds MCUboot to the manifest open | It is merged. The policy text is an accepted decision and is not edited |
| [Updating or recovering a deployed bootloader](boot-bootloader-update-investigation.md), [eMMC feasibility](boot-emmc-investigation.md) | Pin Zephyr v4.4.0 and an older MCUboot; the eMMC page's repository statements were checked at one older revision | The repository pins Zephyr v4.4.2 and MCUboot v2.4.0 at `6d3b3d2c`; the eMMC page's status block says what was and was not re-derived; the bootloader update page does not, so treat its Zephyr and MCUboot statements as v4.4.0 readings |

## How to challenge this page

| Question | Answer |
| --- | --- |
| What stops an unsigned or wrongly signed image from running? | MCUboot validates on every boot (section 8) and the signing tool refuses such images in CI (section 3). No refusal was shown by MCUboot or the ROM on a board, and anyone with flash access can replace the bootloader at T0. Open. |
| What happens if power fails during the first selection of a new image? | The bootloader writes `copy_done` and may erase a slot while executing from NOR (section 4). Only the model replay of section 7 and the code reading exist; the bootloader write path is blocked on hardware by #22 and #165. Open. |
| Who holds the production key, and what happens if it leaks? | Undecided (section 3, plan D6). The port embeds one key, so a leak needs a new bootloader and a route to install it (section 6). Open. |
| Does an update really reach the inactive slot, and which file tests a revert? | The stock request can be a silent no-op from slot 1, and the file question is open (sections 4 and 5). |
| How does a unit recover from a damaged bootloader? | Service recovery through the ROM serial downloader is the accepted level; not started, not run (section 6). |
