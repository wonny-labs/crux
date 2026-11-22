# Secure boot board test procedure (RT1060-EVK Rev B)

> **Not yet run with this procedure.** Nothing in this procedure has been executed on a board. Every expected result below is a prediction from the sources named next to it, not an observation. Record what you see; a difference is a finding, not an error in you.
>
> **Status:** Procedure for the first bench session of the secure boot work (milestone M8, [issue #296](https://github.com/wonny-labs/crux-pilot/issues/296)). It decides nothing and adopts no interface.
> **Verified:** Only what a label below says: build facts of the [boot composition](boot-composition.md) page, and MCUboot and Zephyr source read at the pinned revisions.
> **Not verified:** Every board result, including that the boot ROM accepts the MCUboot image, that any log line below appears, and that the recovery paths work.
> **Read this first / then:** the [boot overview](boot-overview.md) and the [boot composition](boot-composition.md) page, then this page. What exists and what is open is in the [secure boot and update review](secure-boot-and-update-review.md).

Labels: **Verified on pinned source** (MCUboot v2.4.0 at `6d3b3d2c38ab20c242e5b9abb04d050086383eb2`, or Zephyr v4.4.2 at `dccb09599635bdff17633fa7e9dab014b91dce90`, file and function named; line numbers are those of that revision). **Verified by build** (a build that exited 0, as the composition page records). **Verified in repository** (a repository file or page says so; a recorded observation of an earlier session on a board is marked as such and was not repeated by this procedure). **Verified by public vendor document** (a public NXP or SEGGER document, as the repository's pages cite it). **Operator-reported** (a person told the repository's record; no tool read it). **Estimate** (a figure of this page, not a source). **Inference** (derived, not run). **Not verified.** Placeholders in angle brackets are replaced as the table in section 3 says.

## 1. Purpose and scope

This procedure tests, on a real RT1060-EVK Rev B, what the [boot composition](boot-composition.md) builds: MCUboot in RAM load with revert mode starts from the QSPI NOR, validates the signed application in slot 0, copies it to SDRAM and jumps to it. It checks that a correctly signed image boots, that unsigned, wrong-key and modified images do not, and what MCUboot does with an unpadded, an unconfirmed and a confirmed image. Its results are the board evidence that phase 1 of the [secure boot development plan](plans/secure-boot-development-plan.md) still lacks.

| Case | What | Status |
| --- | --- | --- |
| T0 | Restore point boots, identity | Runnable now |
| T1 | Flash MCUboot and the signed, confirmed application, boot | Runnable after the approvals of section 2, including the bootloader-write approval |
| T2 | Unsigned image is refused | Same |
| T3 | Image signed with a wrong key is refused (T3a same type, T3b other type) | Same |
| T4 | Image modified after signing is refused (T4a header padding, T4b payload) | Same |
| T5 | Unpadded and unconfirmed images: what MCUboot does (T5a, T5c) | Same. This is the result the case exists to find |
| T6 | Power cut during first selection and during the slot erase of a revert | Same, plus its own approval and a checked power fixture |
| T7 | Update by the application and power cut during the update | **Prepared for later.** Needs milestone M9 |

**What it deliberately does not do.** No fuse is written or read, no HAB signing or check, no closed configuration, no RT1170, no eMMC. The repository holds no signing key and has no key generation step. The tester generates a private development key at the bench with `imgtool`, outside every repository (decision 18 of the [boot and update investigation](boot-update-investigation.md)), and two throwaway keys for T3; the commands in section 4 do this.

**What cannot be tested yet.** The update agent of milestone M9 does not exist, and the controller sample has no update or confirm code and links no Flash driver ([boot and update investigation](boot-update-investigation.md), Stage 5: "Not exercised: the controller sample has no update or confirm code and no Flash driver"). So no case here can write an image from the application, set a test request, confirm an image, or cut power during such a write. These are T7. Images are placed with the probe's tools (decision 13 of the investigation).

## 2. Safety and approvals

- **Open configuration only.** No fuse operation and no HAB operation, ever. The Zephyr-built image carries no CSF and the ROM is expected to boot it in open configuration (**Inference**, plan section 3). No tool of the repository reads the fuse or lifecycle state of the board (an [open question](history/secure-boot-first-bench-session-notes.md#open-questions-for-the-first-bench-session)).
- **Which key signs what (decision 18).** MCUboot's published test key `root-ec-p256.pem` is public. The repository forbids programming anything signed with it: the [boot composition](boot-composition.md) page says "Images signed with it must never be programmed to a board", and the build script, the [boot overview](boot-overview.md) and the plan limit it to build-only signing. It is used here only for the build-only check of section 4, step 1, and nothing from that build is programmed, including its MCUboot (which embeds that key). Hardware images T1 to T7 are signed with a **development key** that the tester generates with `imgtool` at hardware approval, as decision 18 says: algorithm `ecdsa-p256` to match the composition, in a directory with mode 700 outside every repository and outside every directory shared with another machine or container, file mode 600, never committed, never shared, destroyed or kept private when the campaign ends. The bootloader embeds the public key of the key it is built with, so the hardware bootloader is built with the development key and rebuilt if the key changes. The T3 keys are throwaway keys of the same kind, deleted after T3. Never keep, share or release an image signed with a key of this procedure for a product.
- **One board, one probe, one person at the bench.** No other debugger, GDB server or serial monitor may hold the probe or the port. The device-control tool takes one lock per board ID.
- **The approval gate.** Physical programming, reset and other hardware operations need explicit authorisation for the current task ([`AGENTS.md`](../AGENTS.md)). Here: **the person who owns the board approves each hardware step in the task record.** Write the record reference down before you run the step. The tool flags `--allow-reset` and `--allow-flash=<reference>` only record a reference; they are not authority ([device-control README](../tools/device_control/README.md)). An approval from an earlier task does not carry over.
- **Bootloader NOR writes need their own approval.** Decision 16 of the investigation records that MCUboot's FlexSPI write path was found not closed against the #22 matrix, makes that a blocker for any bootloader write on hardware, and tracks the remedy in [#165](https://github.com/wonny-labs/crux-pilot/issues/165) (not started); its scope must be decided before any M8 hardware step in which the bootloader writes NOR. **Every case from T1 on lets the bootloader write NOR** (the `copy_done` flag on first selection, the whole-slot erase of an invalid or unconfirmed image; **Verified on pinned source**, section 7). Do not start T1 until the task record states the decision on #165 or approves running with the finding open. T0 involves no MCUboot.
- **Stop conditions.** Stop, power down only if a step says so, record the state and ask the maintainers when: the probe cannot connect and a retry at 100 kHz fails; a read-back differs from its backup or image; `Verify successful` is missing after a load; the board shows no console output after a restore and R2 below also fails; the console shows a fault or a restart loop; a command runs longer than its stated limit; a probe write or read would go above `0x60600000`; any step would need a fuse, an erase command, or a probe other than the approved one; **you cannot create the private key directory of section 4 outside every repository** (decision 18); the header of slot 1 carries the image magic (section 7, T1, step 1).
- **Power rules.** Power the board through J1 USB, as the repository's physical gates do. Never unplug or switch off during a load, verify or erase. Start every J-Link Commander script with `exec DisableAutoUpdateFW`, because Commander V9.86a has updated probe firmware on its own twice in the repository's records. First, during a `ShowEmuList USB` probe-list command; it ended with `New firmware booted successfully` ([baseline](baseline.md), M4 notes). Second, in a later preflight of the M3 work, an automatic update was attempted and the probe then failed to reconnect until a person reconnected it ([M3 validation](m3-validation.md), "Resumption and renewed preflight stop"). For T6 the board is powered only through J1 (the J48 supply removed) and the cut is proven first (section 7, T6).
- **ESD.** The repository's pages give no handling rules; follow the board vendor's.
- **After the campaign.** The signed test images stay on the bench machine only and are deleted after the campaign unless the maintainers decide to keep them as evidence; say where they are.

## 3. Prerequisites

| Item | What | Basis |
| --- | --- | --- |
| Board | NXP MIMXRT1060-EVKB, PCB revision B, 8 MiB QSPI NOR, no HyperFlash rework; build target `mimxrt1060_evk@B//qspi`. Read the marking yourself: the build checks the target, not the board that is fitted | Operator-reported in [baseline](baseline.md) (M4, 17 October 2026) |
| Boot switch | SW4 `OFF-OFF-ON-OFF` selects QSPI boot. Read it by eye and photograph it; no tool reads it | Operator-reported in [baseline](baseline.md). The EVKB manual's tables are cited only through a summarising fetch in [boot and update investigation](boot-update-investigation.md) (Stage 3 D3 correction) |
| Probe | SEGGER J-Link PLUS on the 20-pin J2 header with J9 and J10 removed to isolate the on-board SWD; SWD at 400 kHz, device `MIMXRT1062xxx6A`; J-Link software V9.86a. | Verified in repository ([baseline](baseline.md), recorded observation). A different probe, or only the on-board DAPLink for debug, has no recorded flow |
| USB | J1 to the host: board power and the on-board DAPLink serial bridge. The J-Link's own USB cable to the host | [baseline](baseline.md) (pages name J1 and J41 for the console path differently; use the port that enumerates) |
| Console | The DAPLink serial port, 115200 baud, other settings as pyserial defaults, opened exclusively. On macOS it is `/dev/cu.usbmodem<N>` and the number changed between sessions | Verified in repository ([tests README](../tests/README.md), physical UART) |
| Host | macOS or Linux for the probe tools. The build itself needs the Linux Dev Container ([build guide](build.md)); the repository directory is shared with the host in that layout. Windows is not covered | Verified in repository |
| Workspace | `scripts/bootstrap-zephyr.sh --install-sdk` run as [`build.md`](build.md) says (west workspace in the parent directory of the checkout, Zephyr SDK 1.0.1) | Verified in repository |
| MCUboot group | `west config manifest.group-filter -- +crux-boot`, then `west update mcuboot`. The first command **replaces** an existing filter, so list every group you use | [boot composition](boot-composition.md) |
| imgtool | A Python environment with `cryptography`, `cbor2`, `intelhex`, `click`: the Dev Container's bootstrap Python has no `cryptography` and no `cbor2` | **Inference** ([boot composition](boot-composition.md)) |
| Private key directory | A place for the development key in the Linux environment that builds: outside every repository, outside the bind-mounted workspace and every shared volume, mode 700. In the Dev Container the container user's home is outside the bind mount but disappears with the container; see the [open questions](history/secure-boot-first-bench-session-notes.md#open-questions-for-the-first-bench-session) | Decision 18 ([boot and update investigation](boot-update-investigation.md)) |
| Disk | The repository gives no figure for this build. The test images are eight files of 3 MiB (24 MiB) plus two backups of 6 MiB: allow about 50 MiB under `<bench>` beyond the build | Estimate |
| Power-cut fixture (T6 only) | A host with `uhubctl` and a hub that switches the port of the board's J1 | [microSD physical gate](microsd-physical-gate.md) |

| Placeholder | Meaning |
| --- | --- |
| `<crux>` | The checkout of this repository |
| `<workspace>` | The west workspace, the parent of `<crux>` |
| `<build>` | `<crux>/build/zephyr/boot-composition`: the build-only check, never programmed |
| `<hwbuild>` | `<crux>/build/zephyr/boot-hardware`: the build signed with the development key |
| `<keydir>` | The private key directory |
| `<mcuboot>` | `<workspace>/bootloader/mcuboot` |
| `<app-out>` | The directory that holds `zephyr.signed.bin` (step 4 of section 4 prints it) |
| `<bench>` | `<crux>/build/bench`, git-ignored (`/build/` is in `.gitignore`) |
| `<jlink>` | The `JLinkExe` of the approved installation (`/usr/local/bin/JLinkExe` on the recorded macOS host) |
| `<serial>` | The probe's USB serial number (`ShowEmuList USB` prints it) |
| `<port>` | The console serial port |
| `<case>` | The name of an evidence directory under `<bench>/evidence/`: UTC time, case and step, for example `20261116T093000Z-T1-boot1` |

```bash
export PYTHONPATH=<crux>/tools
```

## 4. Build the images

1. **Build-only check with the public test key.** Run the repository's build-and-check script in the Linux Dev Container. It enables `+crux-boot`, runs `west update mcuboot`, installs the MCUboot requirements into the Python named by `CRUX_PYTHON` (`python3` by default; point it at an environment you may change), builds, and checks the signature and the refusals of `imgtool` ([script](../scripts/test-boot-composition.sh)). It does not program, boot or reset anything. **Everything it builds is signed with, or embeds, the public test key. Nothing in `<build>` is ever programmed to a board.**

```bash
cd <crux> && scripts/test-boot-composition.sh
```

   Expected: `Boot composition: MCUboot 51668 bytes, signed application 33051 bytes (build only, not booted).` The sizes can differ by a few bytes at another revision. **Verified by build** (CI run named in the composition page).

2. **Generate the private development key** (decision 18) in `<keydir>`, in the Linux environment that builds. If you cannot make a directory outside every repository that is not shared, stop (section 2). Whether the development public key is committed is not part of this procedure: accepted decision 18 of the [boot and update investigation](boot-update-investigation.md) says: "Commit only the public key, at that point." Committing it is a separate change; the plan's target for it is `docs/evidence/boot-update/dev-public-key.pem` ([pre-M8 investigation plan](plans/pre-m8-investigation-plan.md)), under `docs/evidence/`, a protected path, so it needs a human approval ([`AGENTS.md`](../AGENTS.md)).

```bash
mkdir -m 700 <keydir>
```

```bash
python3 <mcuboot>/scripts/imgtool.py keygen -k <keydir>/dev-ec-p256.pem -t ecdsa-p256
```

```bash
chmod 600 <keydir>/dev-ec-p256.pem
```

3. **Hardware build.** The same published argument set as the script, in its own build directory, with the key argument (`SB_CONFIG_BOOT_SIGNATURE_KEY_FILE`, [boot composition](boot-composition.md), "No key argument"). `<app>` is `<crux>/samples/controller/zephyr`, `<image>` is `zephyr`, `<python>` is the Python of `CRUX_PYTHON`. The MCUboot built here embeds the public key of the development key. It takes several minutes (373 s in the emulated Dev Container for the earlier full build).

```bash
cd <workspace> && ZEPHYR_BASE=<workspace>/zephyr west build --sysbuild -p always -b 'mimxrt1060_evk@B//qspi' -d <hwbuild> <app> -- \
  -DZEPHYR_EXTRA_MODULES=<crux> \
  -DPython3_EXECUTABLE=<python> \
  -DSB_CONFIG_BOOTLOADER_MCUBOOT=y \
  -DSB_CONFIG_MCUBOOT_MODE_RAM_LOAD_WITH_REVERT=y \
  -DSB_CONFIG_BOOT_SIGNATURE_TYPE_ECDSA_P256=y \
  -DSB_CONFIG_BOOT_SIGNATURE_KEY_FILE=\"<keydir>/dev-ec-p256.pem\" \
  -Dmcuboot_EXTRA_CONF_FILE=<crux>/zephyr/boot/boards/mimxrt1060_evk_mimxrt1062_qspi_B/mcuboot.conf \
  -Dmcuboot_EXTRA_DTC_OVERLAY_FILE=<crux>/zephyr/boot/boards/mimxrt1060_evk_mimxrt1062_qspi_B/mcuboot.overlay \
  -D<image>_EXTRA_CONF_FILE=<crux>/zephyr/boot/boards/mimxrt1060_evk_mimxrt1062_qspi_B/app.conf \
  -D<image>_EXTRA_DTC_OVERLAY_FILE=<crux>/zephyr/boot/boards/mimxrt1060_evk_mimxrt1062_qspi_B/app.overlay
```

   Expected: exit 0, and no log line saying the default MCUboot signing key is used (that warning appears in the step 1 build, **Verified by build**; its absence here is an **Inference**).

4. **Locate the outputs.** `<app-out>` is the directory of the file this prints. Zephyr writes the signed files next to the unsigned `zephyr.bin` (`cmake/mcuboot.cmake`, `zephyr_mcuboot_tasks`, **Verified on pinned source**).

```bash
find <hwbuild>/zephyr -name zephyr.signed.bin
```

| Artefact | Place | Expected size | Basis |
| --- | --- | --- | --- |
| MCUboot | `<hwbuild>/mcuboot/zephyr/zephyr.bin` | about 51,700 B | Verified by build for the public-key build (51,668 B) |
| Unsigned application | `<app-out>/zephyr.bin` | about 32,900 B | Verified by build |
| Signed application, unpadded | `<app-out>/zephyr.signed.bin` | about 33,050 B | Verified by build |
| Signed, padded, confirmed | `<app-out>/zephyr.signed.confirmed.bin` | 3,145,728 B, the slot size | Verified by build in the earlier full build at Zephyr v4.4.2. `scripts/test-boot-composition.sh` fails if this file is missing or is not 3,145,728 B (wired in the change that adds this sentence, **Not verified** by a CI run until that change has run): if it is missing, stop |

5. **Check the signature and the key.** The development key must verify both signed files, and the public test key must refuse them. Expected: `Image was correctly validated` and exit 0 for the first command; non-zero for the second (`imgtool` refusing a wrong key is **Verified by build** for another key type, and an **Inference** for the same type).

```bash
python3 <mcuboot>/scripts/imgtool.py verify -k <keydir>/dev-ec-p256.pem <app-out>/zephyr.signed.confirmed.bin
```

```bash
python3 <mcuboot>/scripts/imgtool.py verify -k <mcuboot>/root-ec-p256.pem <app-out>/zephyr.signed.confirmed.bin
```

   `imgtool dumpinfo` prints the key hash TLV. It must not be `e30466f6b8470c1f29070b17f1e2d3e94d445e3f608087fdc711e4382bb538b6`, the hash of the public test key (WP1a evidence, section 2); if it is, stop.

```bash
python3 <mcuboot>/scripts/imgtool.py dumpinfo <app-out>/zephyr.signed.confirmed.bin
```

6. **Make the test images before touching hardware.** Print the signing arguments the build used and note `--version`:

```bash
grep -h imgtool <hwbuild>/zephyr/build.ninja
```

   The trial builds used `sign --version 0.0.0+0 --header-size 0x400 --slot-size 3145728 --align 1 --load-addr 0x80000000 --key <key>` (Verified by build, [Stage 5](evidence/boot-update/stage5-trial-builds.md)). Use your build's arguments if they differ. Below, `<args>` is that list without `--key`, `--pad` and `--confirm`, and `<app-bin>` is `<app-out>/zephyr.bin`, the unsigned application. Create the bench directories and copy the three build outputs into the hand-off directory:

```bash
mkdir -p <bench>/handoff <bench>/cmd <bench>/evidence <bench>/backup
```

```bash
cp <hwbuild>/mcuboot/zephyr/zephyr.bin <bench>/handoff/mcuboot.zephyr.bin
```

```bash
cp <app-out>/zephyr.signed.bin <bench>/handoff/app.signed.bin
```

```bash
cp <app-out>/zephyr.signed.confirmed.bin <bench>/handoff/app.signed.confirmed.bin
```

   T5c, signed with the development key, padded, not confirmed (`--pad` writes the trailer magic only; `imgtool` `pad_to`, **Verified on pinned source**):

```bash
python3 <mcuboot>/scripts/imgtool.py sign <args> --pad -k <keydir>/dev-ec-p256.pem <app-bin> <bench>/handoff/app.padded-unconfirmed.bin
```

   T2, unsigned, padded and confirmed. With no `-k` the image holds a hash and no signature: it passes selection, and the signature check is what refuses it.

```bash
python3 <mcuboot>/scripts/imgtool.py sign <args> --confirm <app-bin> <bench>/handoff/app.unsigned.confirmed.bin
```

   T3. Two throwaway keys in a subdirectory of `<keydir>`: T3a of the same type as the bootloader's key, T3b of another type (a type mismatch, not a same-type wrong key). Neither is the public test key.

```bash
mkdir -m 700 <keydir>/throwaway
```

```bash
python3 <mcuboot>/scripts/imgtool.py keygen -k <keydir>/throwaway/wrong-ec-p256.pem -t ecdsa-p256
```

```bash
python3 <mcuboot>/scripts/imgtool.py keygen -k <keydir>/throwaway/wrong-rsa-2048.pem -t rsa-2048
```

```bash
python3 <mcuboot>/scripts/imgtool.py sign <args> --confirm -k <keydir>/throwaway/wrong-ec-p256.pem <app-bin> <bench>/handoff/app.wrongkey-ec.confirmed.bin
```

```bash
python3 <mcuboot>/scripts/imgtool.py sign <args> --confirm -k <keydir>/throwaway/wrong-rsa-2048.pem <app-bin> <bench>/handoff/app.wrongkey-rsa.confirmed.bin
```

   Delete the throwaway keys after T3 (the test needs only the signed images). Do it at once if you prefer: nothing later needs them.

```bash
rm -r <keydir>/throwaway
```

   T4a and T4b change one byte of the confirmed image, as the build script does on its output (`0x300` is in the header padding, `0x500` in the payload):

```bash
python3 -c "import sys; d=bytearray(open(sys.argv[1],'rb').read()); d[int(sys.argv[3],16)]^=0xFF; open(sys.argv[2],'wb').write(d)" <app-out>/zephyr.signed.confirmed.bin <bench>/handoff/app.modified-0x300.confirmed.bin 0x300
```

```bash
python3 -c "import sys; d=bytearray(open(sys.argv[1],'rb').read()); d[int(sys.argv[3],16)]^=0xFF; open(sys.argv[2],'wb').write(d)" <app-out>/zephyr.signed.confirmed.bin <bench>/handoff/app.modified-0x500.confirmed.bin 0x500
```

   T5a needs a blank slot first: a file of 3,145,728 bytes of `0xFF`:

```bash
python3 -c "open('<bench>/handoff/blank-slot0.bin','wb').write(b'\xff'*3145728)"
```

7. Record the SHA-256 of every artefact and keep the output (it goes into the evidence, section 8). Also record `python3 <mcuboot>/scripts/imgtool.py dumpinfo <file>` for each image: it prints header, TLVs and trailer. When the campaign ends, destroy `<keydir>` or keep it private; the signed images stay on the bench machine only and are deleted after the campaign unless the maintainers decide to keep them.

```bash
shasum -a 256 <bench>/handoff/*.bin
```

## 5. Prepare the bench

**Command files for J-Link Commander.** The repository's wrapper starts every script with the preamble below and runs Commander with fixed arguments ([`capture_m3.py`](../tests/target/capture_m3.py)). Create these files in `<bench>/cmd/`; each is the preamble, the lines listed, then `q`.

```text
exec DisableAutoUpdateFW
usb <serial>
connect
```

| File | Lines after the preamble |
| --- | --- |
| `identify.jlink` | none |
| `backup-1.jlink`, `backup-2.jlink` | `savebin "<bench>/backup/flash-1.bin", 0x60000000, 0x600000` (and `flash-2.bin`) |
| `load-<name>.jlink` | `r`, `h`, `loadfile "<bench>/handoff/<file>", <address>` (a reset and halt before the load, as the repository's flows do) |
| `verify-<name>.jlink` | `verifybin "<bench>/handoff/<file>", <address>` |
| `slot1-head.jlink` | `savebin "<bench>/evidence/<case>/slot1-head.bin", 0x60320000, 0x20` |
| `slot0-head.jlink`, `slot0-tail.jlink` | `savebin "<bench>/evidence/<case>/slot0-head.bin", 0x60020000, 0x1000` and `...tail.bin", 0x6031F000, 0x1000` |
| `reset.jlink` | `r`, `g` (as [`tests/target/reset.jlink`](../tests/target/reset.jlink), which adds only `q`) |

Addresses: MCUboot and the restore image at `0x60000000`, slot 0 at `0x60020000` (the QSPI window starts at `0x60000000`; partitions `mcuboot` at `0x0` size `0x20000`, `image-0` at `0x20000` size `0x300000`; Verified by build in [Stage 6](evidence/boot-update/stage6-layout-and-write-analysis.md)). The `r`, `h`, `loadfile` order is that of [`capture_m3.py`](../tests/target/capture_m3.py) and the [microSD physical gate](microsd-physical-gate.md) (`h`, `loadfile`, `r`, `g`). The punctuation follows SEGGER's Commander reference and the repository's tests (`loadfile "<file>", <address>`); the repository's gate pages write `savebin` and `loadbin` without commas. If your Commander refuses one form, try the other and record which (an [open question](history/secure-boot-first-bench-session-notes.md#open-questions-for-the-first-bench-session)). The probe's serial number comes from a probe list; its script starts with `exec DisableAutoUpdateFW` like the others (the repository's baseline ran the same list with `ShowEmuList USB`, which also prints `VTref`):

```bash
printf 'exec DisableAutoUpdateFW\nShowEmuList USB\nq\n' | <jlink> -NoGui 1
```

Run any command file with one command:

```bash
<jlink> -Device MIMXRT1062xxx6A -If SWD -Speed 400 -NoGui 1 -ExitOnError 1 -AutoConnect 0 -CommandFile <bench>/cmd/<name>.jlink 2>&1 | tee <bench>/evidence/<case>/<name>.log
```

Load and verify times: the repository measured at most 4.52 s per 128 KiB range to load and about 4.9 s per range to read back ([image profiles](board-image-profiles.md), decision 26). A 3 MiB slot file is 24 ranges, so about two minutes to load and two to verify (**Inference**, extrapolated). A load is a pass only when the log is followed by a separate read-only verify run whose log contains `Verify successful`.

**Procedure P(file, address): program and verify.** (1) Create the case directory under `<bench>/evidence/`. (2) Run `load-<name>.jlink`. (3) Run `verify-<name>.jlink`. (4) Check the verify log for `Verify successful`. Never start the board between 2 and 4.

**Device-control profile and manifest.** The tool resets the board, waits for a ready marker and keeps the console bytes. It was written for this purpose and has **never run against hardware**; its README lists what is not shown (DTR and RTS behaviour on this board, tools outliving the lock). The only flow recorded on this board is J-Link Commander with a terminal, so keep that as the fallback (Procedure R, route B). Write `<bench>/profile.json` with every field of the README that applies (all required ones, the probe serial and the three commands); replace each `<...>`:

```json
{
  "board_id": "<bench-name>/board-1",
  "board": "mimxrt1060_evk@B//qspi",
  "mcu": "MIMXRT1062xxx6A",
  "port": "<port>",
  "baud": 115200,
  "dtr": false,
  "rts": false,
  "ready_marker": "CONTROLLER_COMPLETE cycles=20",
  "ready_timeout_seconds": 30,
  "write_timeout_seconds": 2,
  "lock_directory": "/var/tmp/crux-board-locks",
  "probe_serial": "<serial>",
  "reset": {"command": ["<jlink>", "-Device", "{mcu}", "-If", "SWD", "-Speed", "400", "-NoGui", "1", "-ExitOnError", "1", "-AutoConnect", "0", "-CommandFile", "<bench>/cmd/reset.jlink"], "timeout_seconds": 30},
  "flash": {"command": ["<bench>/jlink-load.sh", "{image}"], "timeout_seconds": 400},
  "verify": {"command": ["<bench>/jlink-verify.sh", "{image}"], "timeout_seconds": 400}
}
```

- `dtr` and `rts` are `false` because the repository's own capture sets neither; the README says to check them on a new board, since a USB bridge can move the lines at open (an [open question](history/secure-boot-first-bench-session-notes.md#open-questions-for-the-first-bench-session)). `ready_marker` is the last line of the controller sample (`samples/controller/zephyr/main.c`, **Verified in repository**) and is matched literally. For T0 use a copy of the profile whose marker is `CRUX_TIME_READY composition=zephyr` and whose timeout is 10 (`samples/time/time_shell/src/main.c`).
- `identity_pattern` is left out, which the README allows. If it is set, `reset` compares a printed identity with the manifest's `build_id` and fails to start without one. Neither image prints a build identifier, so identity here is the artefact hashes in the manifest and the verify runs.
- **`flash` and `verify` need two wrapper scripts that the repository does not have.** The tool requires the image path as an argument, and refuses a command whose arguments contain `erase` or `fuse`. A wrapper takes the image path, accepts only the file names of `<bench>/handoff/`, writes the matching command file (preamble, `loadfile` or `verifybin`, address by file name: `mcuboot.zephyr.bin` and `time-baseline.bin` at `0x60000000`, every `app.*` file at `0x60020000`), and runs Commander as above. Whoever approves the hardware steps also reviews these scripts. If you do not want to write them, drop the two sections and flash with Procedure P.
- The `reset` timeout of 30 s assumes the standard boot. For T5c boot 2 and T6 use a copy of the profile with `ready_timeout_seconds` 360, because the slot erase has no recorded duration (**Not verified**).

The manifest lists every file in `<bench>/handoff/` with its SHA-256; the tool checks **every listed file at the start of every run** and only the listed files. That the list is complete and current is a rule of this procedure, not something the tool enforces. Fill in the revisions from `git -C <crux> rev-parse HEAD` and `git -C <workspace>/zephyr rev-parse HEAD`, and leave out `build_id` (it is required only with `identity_pattern`):

```json
{
  "schema_version": 1,
  "board": "mimxrt1060_evk@B//qspi",
  "source_revision": "<crux revision>",
  "zephyr_revision": "<zephyr revision>",
  "files": [
    {"path": "mcuboot.zephyr.bin", "sha256": "<hash>"},
    {"path": "app.signed.confirmed.bin", "sha256": "<hash>"}
  ]
}
```

(List all other files of `<bench>/handoff/` the same way.) Nothing writes this manifest for you ([README](../tools/device_control/README.md)).

**Procedure R: reset and capture one boot.** Do it with the console free. Route A (the tool):

```bash
python3 -m device_control --profile <bench>/profile.json --manifest <bench>/handoff/manifest.json --evidence <bench>/evidence/<case>/tool-<n> reset --allow-reset
```

The tool's evidence directory (`tool-<n>`, `n` the boot number) must not exist; the tool creates missing parent directories, so `<case>` need not exist. The command exits 0 when the marker appeared and non-zero (timeout) when it did not; **a timeout is a recorded result in the refusal cases, not a fault of the tool.** `rx.bin` keeps every byte received, including after a failure. It stops reading when the marker is found. Route B: open a terminal that logs the raw port at 115200 to `<bench>/evidence/<case>/console.log`, run `reset.jlink` with the Commander command above, wait the time the case states, then stop the log. A power cycle (unplug and replug J1) replaces the reset where a case says so.

**The evidence directory of the tool** holds `rx.bin`, `events.jsonl`, `inputs.json`, `manifest.json`, `identity.json`, one log per operation (`reset.log`, `flash.log`, `verify.log`) and `result.json`. A missing or empty `result.json` means the process died ([README](../tools/device_control/README.md)). The lock is an OS lock per `board_id` in `lock_directory`; a held lock fails at once.

## 6. Restore point and recovery

**What known good means.** The board runs a Crux image of this repository that prints its readiness line on the console, and the image in the flash matches the file you programmed. The repository's physical baseline is the Time sample: it prints `CRUX_TIME_READY composition=zephyr` (**Verified in repository**, recorded observation of 17 October 2026 on this board type, [baseline](baseline.md)). The record ties the marker to the image by manifest, hash and download log, and the marker is not an identity. Two levels:

- **R1, the restore image.** Build it in the Dev Container, copy `<crux>/build/zephyr/mimxrt1060_evk_B_qspi/zephyr/zephyr.bin` to `<bench>/handoff/time-baseline.bin`, record its SHA-256, and program it with Procedure P at `0x60000000`. It replaces MCUboot and the first sectors. That it leaves slot 0 alone is an **Inference**: the Time image is about 66 KB, far below `0x20000` ([baseline](baseline.md), 65,976 B of Flash).

```bash
PATH=/opt/crux-cache/venv/bin:$PATH <crux>/scripts/build-debug-target.sh 'mimxrt1060_evk@B//qspi'
```

- **R2, the backup.** The first 6 MiB of the flash as found, read twice and compared. Programming it back restores the original contents of that range.

**Before any test (read-only except where stated; approved each).**

1. Run `identify.jlink`. Expected: connect succeeds, `VTref` about 3.3 V, SW-DP ID `0x0BD11477`, AHB-AP IDR `0x04770041`, Cortex-M7 r1p1, CPUID `0x411FC271` (**Verified in repository**, recorded observation of this board, [baseline](baseline.md)). If it fails at 400 kHz, retry once at 100 kHz and record both.
2. Run `backup-1.jlink` and `backup-2.jlink`, then compare. The top 2 MiB cannot be read reliably (an operator report, not measured in the repository) and is **not backed up**; no image and no step may erase or program above `0x60600000` ([eMMC physical gate](emmc-reliance-physical-gate.md), precondition 4). **Probe writes stay below `0x600000`**: R2 writes at most the 6 MiB it backed up, and the images of this procedure end at `0x320000`. **The bootloader's erases are bounded by the two slots**, not by the probe: slot 0 is `0x20000` to `0x320000`, slot 1 is `0x320000` to `0x620000`, and MCUboot erases an image that fails to load or validate in either slot ([Stage 6](evidence/boot-update/stage6-layout-and-write-analysis.md), write inventory, row "Failure"; B65 in [Stage 1](evidence/boot-update/stage1-pinned-source-findings.md)). The top `0x20000` of slot 1 lies above the backup and cannot be read back. Step 4 below therefore checks slot 1 before T1.

```bash
shasum -a 256 <bench>/backup/flash-1.bin <bench>/backup/flash-2.bin
```

   The two hashes must be equal. Record them. Check that the file starts with the FlexSPI configuration block: `head -c 4 <bench>/backup/flash-1.bin | xxd` should show `FCFB` for a bootable Zephyr image; if it does not, record what is there and ask whether the existing firmware is covered ([microSD physical gate](microsd-physical-gate.md), precondition 4). The backup is a record and not a tested restore until R2 has been done once and read back.
3. Program R1 with Procedure P (`time-baseline.bin`, `0x60000000`). Then reset and capture with the T0 profile.
4. Run `slot1-head.jlink` and look at the file: it must be erased (all `ff`) or must not start with the image magic `0x96f3b83d`, the bytes `3d b8 f3 96`. If it does, **stop and ask**: MCUboot would treat slot 1 as an image and could erase it, above the backup.

```bash
xxd <bench>/evidence/<case>/slot1-head.bin
```

**If the board does not boot after a restore.** In this order, one change at a time, each recorded:

1. Console: right port, 115200, nothing else has the port, the cable is in J1.
2. SW4 by eye: `OFF-OFF-ON-OFF`.
3. Power cycle once (unplug and replug J1).
4. SWD: run `identify.jlink`; at 100 kHz if needed; check J9 and J10.
5. If the probe connects: run the verify of R1. If it fails, run Procedure P for R1 again, then reset. If still no console, run R2 (a `load` command file with `loadfile "<bench>/backup/flash-1.bin", 0x60000000`, then a read-back by `savebin` and a hash compare).
6. **Stop and ask.** The planned route for a bootloader that SWD cannot repair is the ROM serial downloader. **It is not proven**: [#309](https://github.com/wonny-labs/crux-pilot/issues/309) is planned and not done. The boot ROM is expected to fall through to the serial downloader on an internal boot error, and the downloader loads a flashloader into RAM, with `blhost` programming the NOR from it (**Verified by public vendor document**, [bootloader update investigation](boot-bootloader-update-investigation.md), rows 1 to 3); that a corrupt first sector counts as such an error is **Inference**. The switch value is SW4[3:4] = `01`, written `OFF-OFF-OFF-ON` with SW4[1:2] off, which is **Inference**. Where the flashloader comes from and under what licence is **Not verified**. Do not try it, and do not change SW4, without the maintainers and the approval of the person who owns the board.

## 7. Test cases

Common to all: record the approval reference of every hardware step; keep the console free; `<case>` directories are new for every step.

### T0 Baseline: the restore point boots

**Purpose.** Show that probe, console and restore image work before any MCUboot test.
**Preconditions.** Section 3 done; approvals for the probe connection, the read-back, the programming of R1 and the reset; SW4 read and photographed.
**Steps.**
1. Section 6, "Before any test", steps 1 to 4 (identify, backup twice and compare, program and verify R1, read the slot 1 header).
2. Procedure R with the T0 profile.
**Expected result.** Read-only identification as in section 6, "Before any test", step 1 (**Verified in repository**, recorded observation). `Verify successful` after the load (**Verified in repository**: the M4 records). The console shows `CRUX_TIME_READY composition=zephyr` within 10 s of the reset (**Verified in repository**, recorded observation).
**Pass/fail.** Pass: identification as above, equal backup hashes, `Verify successful`, the marker seen, a slot 1 header without the image magic. Fail: any of them differs. Do not go on to T1. If the slot 1 header carries the image magic, stop and ask (section 6, "Before any test", step 4); section 6 otherwise covers a board that does not boot.
**Evidence.** Photo of SW4 and the board marking, `identify` log, both backup hashes, R1 hash, load and verify logs, `rx.bin` or `console.log`, `result.json`.

### T1 Flash the bootloader and the signed application, boot

**Purpose.** First boot of the composition: MCUboot starts from NOR, validates slot 0, loads it to SDRAM and jumps; the application runs.
**Preconditions.** T0 passed in this session; the approval for bootloader NOR writes of section 2; the images of section 4 exist and are listed in the manifest; the private key directory exists (section 4, step 2).
**Steps.**
1. Read the slot 1 header again with `slot1-head.jlink` and check it as in section 6, "Before any test", step 4 (erased, or no `3d b8 f3 96`). Otherwise stop and ask.
2. Procedure P with `app.signed.confirmed.bin` at `0x60020000`. Slot 0 first, so MCUboot never runs against a half-programmed slot.
3. Procedure P with `mcuboot.zephyr.bin` at `0x60000000`.
4. Procedure R, boot 1 (profile marker `CONTROLLER_COMPLETE cycles=20`, timeout 30 s).
5. Procedure R again, boot 2, without reprogramming.
**Expected result.** Console of boot 1 (the order is from `main()` and `context_boot_go()`; **Verified on pinned source**, `boot/zephyr/main.c` `main()` lines 533 to 695, `boot/bootutil/src/loader.c` `boot_get_slot_usage()` line 2091, `print_loaded_images()` line 2163, `boot/bootutil/src/ram_load.c` `boot_load_image_to_sram()` line 360, macro `BOOT_LOG_IMAGE_INFO` in `bootutil_priv.h` line 200). MCUboot's log is minimal, so a line has the form `I: <text>` (Zephyr `include/zephyr/logging/log_core.h`, `Z_LOG_TO_PRINTK`, Verified on pinned source) at level INFO (`boot/zephyr/prj.conf`, Verified on pinned source):

```text
I: Starting bootloader
I: Primary   slot: version=0.0.0+0
I: Image 0 secondary slot: image not found
I: Image 0 RAM loading to 0x80000000 is succeeded.
I: Image 0 loaded from the primary slot
I: Bootloader chainload address offset: 0x80000000
I: Image version: v0.0.0
I: Jumping to the first image slot
```

   The version digits follow the build's `--version`. Before the first line a banner starting `*** ` may appear (kernel `banner.c`); its text is **Inference**. `Image 0 secondary slot: image not found` holds only if slot 1 (`0x320000`) holds no valid header; flash left by another project may change it (**Inference**). No `E:` line. The application then prints, from `samples/controller/zephyr/main.c` (**Verified in repository**, text only): `controller composition=zephyr init=<status>`, twenty `cycle=` lines, each followed by a `schedule skipped=` line, then `controller stack_bytes=` and `CONTROLLER_COMPLETE cycles=20`. `init=0` is a prediction (`CRUX_OK` is 0 in `components/base/include/crux/status.h`, and the sample treats anything else as failure). That the application runs after an MCUboot jump is **Not verified**. Nothing is printed for the first-selection write of `copy_done` (`boot_select_or_erase()`, `loader.c`, **Verified on pinned source**: a padded image with the confirm flag has magic and `image_ok` set and `copy_done` unset, so MCUboot writes `copy_done` before it validates; a failed write is logged `W:` and boot continues). Boot 2 is the same, with no write: both flags are set (**Inference** that the flag persisted). **Not verified:** that the boot ROM accepts the MCUboot layout (FCB at offset 0, IVT at `0x1000`, DCD) and brings SDRAM up, that the log reaches this UART, and that MCUboot accepts the development key's signature (`imgtool verify` accepts it, section 4, step 5).
**Pass/fail.** Pass: the eight MCUboot lines (or the same facts in the board's exact wording), no `E:` or `W:` line, both application markers, on boot 1 and boot 2. Fail: an `E:` or `W:` line, a missing application marker, a restart loop. **No output at all is not a pass and not a result about the images:** run the checks of section 6 and record it as a finding about ROM acceptance or console routing.
**Evidence.** Hashes and `dumpinfo` of both images, load and verify logs, both boot captures, the J-Link version banner.

### T2 Unsigned image is refused

**Purpose.** An image with a hash and no signature must not run.
**Preconditions.** T1 passed (MCUboot is in place); approvals as T1.
**Steps.**
1. Procedure P with `app.unsigned.confirmed.bin` at `0x60020000`. (`imgtool verify -k <keydir>/dev-ec-p256.pem <file>` on it must exit non-zero before you flash.)
2. Procedure R with the profile whose timeout is 360 s (the board is expected to give no marker).
3. Run `slot0-head.jlink` and `slot0-tail.jlink`.
**Expected result.** Console: `I: Starting bootloader`, `I: Primary   slot: version=0.0.0+0`, `I: Image 0 secondary slot: image not found`, `I: Image 0 RAM loading to 0x80000000 is succeeded.`, then `E: Image in the primary slot is not valid!` (`loader.c` `boot_validate_slot()` line 649), `I: Removing image 0 from SRAM at address 0x80000000` (`ram_load.c` `boot_remove_image_from_sram()` line 389), `I: No slot to load for image 0` (`loader.c` `boot_load_and_validate_images()` line 2271), `E: Unable to find bootable image` (`main.c` line 658), and then silence. The last three lines come only after the whole-slot erase, so expect a pause of unknown length after the first `E:` line (**Not verified**). MCUboot loops forever and does not reset (`FIH_PANIC` is a loop in both variants, `fault_injection_hardening.h` lines 140 to 144) (**Verified on pinned source**). Because RAM load slots are equivalent, `boot_validate_slot()` erases the whole slot of an invalid image (`ARE_SLOTS_EQUIVALENT()`, `bootutil_priv.h` lines 190 to 193; `boot_scramble_slot()` erases the slot, `bootutil_area.c`) (**Verified on pinned source**). So the head and the tail of slot 0 read back as `0xFF` (**Inference**: no run has read them). The erase time is **Not verified**. No `controller` line appears. Signature failure for a missing signature is `imgtool`/MCUboot's TLV check (`image_validate.c` `bootutil_img_validate()`): that exact internal reason is not logged at INFO.
**Pass/fail.** Pass (refusal): no application line, and the `E:` lines above. Record whether slot 0 was erased; a difference from the prediction is a finding, not a failure of the refusal. Fail: any application line (the unsigned image ran: a security finding, stop and report), or no MCUboot output.
**Evidence.** `dumpinfo` of the file, `imgtool verify` exit status, capture, head and tail reads.
**After.** Slot 0 is erased. Reprogram it with the next case's file (Procedure P) before the next boot.

### T3 Image signed with a wrong key is refused

**Purpose.** A correctly formed, correctly hashed image signed by a key that is not in MCUboot must not run.
**T3a** uses `app.wrongkey-ec.confirmed.bin`, signed with a throwaway development key of the same type as the bootloader's (`ecdsa-p256`). **T3b** uses `app.wrongkey-rsa.confirmed.bin`, signed with a throwaway `rsa-2048` key: this tests a **type mismatch**, not a same-type wrong key (`imgtool verify` refuses a key of another type, **Verified by build**, with the published RSA key).
**Preconditions, steps, evidence.** As T2, with the file of the sub-case.
**Expected result.** The same console as T2: the key is looked up by the hash of the public key in the image (`bootutil_find_key()` in `bootutil_img_validate()`, `image_validate.c` lines 380 and 400, **Verified on pinned source**); an unknown key, or a signature type that is not in the build, fails validation. The signature type check may add no log line at INFO. Slot 0 is erased as in T2 (**Verified on pinned source**).
**Pass/fail.** As T2. For T3b, state in the record that the result covers a type mismatch.

### T4 Image modified after signing is refused

**Purpose.** A signed image changed by one byte must not run.
**T4a** uses `app.modified-0x300.confirmed.bin` (header padding), **T4b** `app.modified-0x500.confirmed.bin` (payload).
**Preconditions, steps, evidence.** As T2.
**Expected result.** The same console as T2. The hash covers the header and the payload and is compared with the hash TLV (`image_validate.c`, `bootutil_img_validate()`, the `IMAGE_TLV_SHA256` branch near line 343, **Verified on pinned source**); `imgtool verify` refuses the unpadded signed image changed at these two offsets (**Verified by build**, the CI script). The confirmed image differs only by padding and trailer after the payload, so the same offsets are covered (**Inference**).
**Pass/fail.** As T2, for each of T4a and T4b.

### T5 Unpadded and unconfirmed images

**Purpose.** The pages predict, as **Inference**, that under RAM load with revert the default `zephyr.signed.bin` (no trailer magic) is erased when MCUboot selects it, and that a padded image that is never confirmed is erased on the next boot ([boot and update investigation](boot-update-investigation.md), B63a and decision 13; [composition page](boot-composition.md#what-the-build-produces)). **That is the thing T5 tests.** Both predictions rest on one function, `boot_select_or_erase()` (`loader.c`, **Verified on pinned source**).
**Preconditions.** T1 passed; approvals as T1 for T5a. T5c needs the erase approval too.
**T5a, unpadded `app.signed.bin`.** Steps: (1) Procedure P with `blank-slot0.bin` at `0x60020000` (the whole slot, so no stale trailer survives; verify). (2) Procedure P with `app.signed.bin` at `0x60020000`. (3) Procedure R, 360 s timeout. (4) `slot0-head.jlink`.
Expected: the image's header is valid, so MCUboot logs `I: Primary   slot: version=0.0.0+0`, then, because the slot has no `BOOT_MAGIC_GOOD`, it erases the whole slot (the line is `D:` level and not shown), then `I: No slot to load for image 0` and `E: Unable to find bootable image`, then silence. No application line. Slot 0 head reads `0xFF` (**Verified on pinned source**, `boot_select_or_erase()`; the head read is **Inference**).
**T5c, padded, unconfirmed `app.padded-unconfirmed.bin`.** Steps: (1) Procedure P at `0x60020000`. (2) Procedure R, boot 1, marker `CONTROLLER_COMPLETE cycles=20`. (3) Procedure R again, boot 2, timeout 360 s. (4) `slot0-head.jlink`.
Expected: boot 1 prints the T1 lines and the application runs; the sample never confirms (**Verified in repository**: no confirm code). Boot 2: the trailer has magic, `copy_done` set by boot 1 and `image_ok` unset, so MCUboot treats it as an image that was started and not confirmed and erases the slot (`boot_select_or_erase()`), after the `Primary   slot` line, then prints `I: No slot to load for image 0` and `E: Unable to find bootable image`. There is no earlier image to revert to, so a revert here is an erase (**Verified on pinned source**). Time of the erase: **Not verified**; wait at least 300 s of silence before you record it as a hang, and say how long you waited.
**Pass/fail.** The prediction holds when both cases end as described. A difference (for example the unpadded image booting, or the unconfirmed image booting twice) is the finding; record it as such and do not repeat the case to make it pass.
**Evidence.** As T2, plus the console of every boot, in order.

### T6 Power cut during first selection and during a revert erase

**Purpose.** Observe what a power cut does at the two points where MCUboot writes the NOR and where this procedure can reach them without the update agent: the first selection of an image (`copy_done`) and the whole-slot erase of an unconfirmed image (the second boot of T5c). Whether either is survivable is **Not verified**.
**Preconditions.** T5c done; its own approval from the person who owns the board; decision on #165 recorded; the slot 1 header check of T1 repeated; the cut proven before it is used (below).
**The cut.** The board is powered only through J1 with J48 removed. Find the hub and port with `uhubctl`, name the hub (`-l <hub>`) in every command (a bare port number can switch that port on every smart hub), and confirm the DAPLink is the device on that port. Cut and restore as the [eMMC physical gate](emmc-reliance-physical-gate.md) does:

```bash
uhubctl -l <hub> -p <port> -a off -f
```

```bash
uhubctl -l <hub> -p <port> -a on
```

   **Every off-pause is 3 s or less**, counted as the whole time the port is off, including the command's own latency and the VTref read. That page records two bench observations, reported there without logs and without a cause: on 5 November 2026 a port cut left 3.322 V on the board when read after 3 s, and on 7 November 2026 the supply came back about 4.4 s after a port cut. So before any cut, switch the port off, read `VTref` at the end of **that same pause** (the `ShowEmuList USB` command of section 5), and require about 0.000 V, then switch on and see about 3.3 V. **If `VTref` stays at its on value, stop: that is not a power cut** ([microSD physical gate](microsd-physical-gate.md), precondition 3). A longer pause is dangerous for the result: the supply can return, the board then boots unobserved and may erase a slot, and the state is blamed on the wrong cut. Whether a J-Link start and `ShowEmuList` fit inside 3 s is not known (an [open question](history/secure-boot-first-bench-session-notes.md#open-questions-for-the-first-bench-session)).
**Cut rule.** Spread, not aimed: the console has no marker for the write or the erase (the erase line is `D:` level). A cut through J1 also removes the DAPLink serial port, which comes back after power-on and may carry another name, so **the console of a powered-on boot is not captured from its start.** The state after a cut is therefore read from the flash and from a probe reset, which keeps USB powered. (1) With the image of T5c, run one uncut sequence with Procedure R and note, from the `rx` timestamps in `events.jsonl` (or the terminal's), the time from the reset instant to `Jumping to the first image slot` in boot 1 and to `Unable to find bootable image` in boot 2. Those intervals leave out ROM and USB start-up (**Inference**), so the fractions below are approximate. (2) For each window make seven cuts, at 10, 25, 40, 55, 70, 85 and 95 per cent of its interval counted from switching power on, in a shuffled order that you record, each on a freshly programmed slot. The count and the fractions are a proposal of this procedure, not a repository rule; the maintainers may change them before the run. The `copy_done` write is a single flag write that no capture can see, so the cuts do not prove coverage of it.
**Steps per cut.** (1) Procedure P with `app.padded-unconfirmed.bin`. (2) First-selection window: switch the hub port off (3 s at most), on, and off again after the chosen delay, so the power-on boot is boot 1. Erase window: first run a probe reset and wait for `CONTROLLER_COMPLETE` (boot 1 sets `copy_done`), then switch off, on, and off after the delay, so the power-on boot is boot 2. Read `VTref` at the end of every off-pause. (3) Switch on, wait for the DAPLink port, run `slot0-head.jlink` and `slot0-tail.jlink` (read-only), then Procedure R, capturing 60 s, or 360 s in the erase window. (4) Record the console and the slot state. (5) Recover: reprogram slot 0 with Procedure P; if MCUboot does not start, section 6.
**Expected result.** Boot-1 cut, two outcomes. A cut before `copy_done` is written leaves the trailer as programmed (magic only), so the next boot is a normal first boot and runs the T1 lines. A cut after it leaves `copy_done` set and `image_ok` unset, so the next boot treats the image as started and unconfirmed and erases it (**Inference** from `boot_select_or_erase()`). Which one a given cut produced is read from the next boot, not from the cut time. A torn `copy_done` write: **Not verified**. After a cut in the erase of boot 2: the erase runs from offset 0 forwards, so the header sector goes first and the slot head reads erased (`boot_scramble_region()`, `bootutil_area.c`, **Verified on pinned source**); the bootloader at `0x0` is not in the erased range. MCUboot itself must start after every cut; if it does not (no `Starting bootloader`), stop and use section 6.
**Pass/fail.** No pass or fail for the image: record per cut the console text and the slot state. Stop at the first case where MCUboot does not start.
**Evidence.** Cut time, the interval fractions, the `VTref` readings, every capture and read-back.

### T7 Update by the application and power cut during the update: prepared for later

**Not runnable.** It needs milestone M9 ([#297](https://github.com/wonny-labs/crux-pilot/issues/297)) and more than this repository has. List of what it will need, from the [investigation](boot-update-investigation.md) and the [plan](plans/secure-boot-development-plan.md): an image-state contract decision; an update agent with a state machine that writes the inactive slot and marks it (under rank 1 application code that opens the inactive slot from `BLINFO_RUNNING_SLOT` and calls `boot_set_next`, or padded images); a Flash driver and write path in the application with its own review of the FlexSPI closure (#22, #165); confirm code (`image_ok` written on the active slot); the version policy; the boot-result record; a way to deliver an image; a programmable power fixture with timing by write phase; and a separate approval. Cases to prepare: update, test, confirm; update, no confirm, revert; cut at each write phase. Results of T1 to T6 are inputs to that design.

## 8. Evidence to capture and how to record it

For every case and step keep, in `<bench>/evidence/<case>/` (take the time from `date -u +%Y%m%dT%H%M%SZ`; use a new name for each run):

| Item | Content |
| --- | --- |
| Console | `rx.bin` from the tool, or `console.log` from the terminal. Raw bytes, never retyped |
| Tool record | The whole tool directory: `events.jsonl`, `inputs.json`, `manifest.json`, `identity.json`, `reset.log`, `flash.log`, `verify.log`, `result.json` |
| J-Link logs | The `tee` output of each Commander run, with the command file used |
| Artefacts | `shasum -a 256` of every file of `<bench>/handoff/` and of the files in `<hwbuild>`, `dumpinfo` of each image, the imgtool arguments of section 4 |
| Identity | Board marking and SW4 photographs, `<serial>`, J-Link software banner, `<port>` |
| Session | UTC date, name of the person, host (`uname -a`), `git -C <crux> rev-parse HEAD` and `git -C <crux> status --short`, Zephyr and MCUboot revisions (`git -C <workspace>/zephyr rev-parse HEAD`, `git -C <mcuboot> rev-parse HEAD`), the approval references |
| Observations | What differed from the prediction, in words, next to the raw files |

**Where the results go.** Ask the maintainers. The repository's evidence records (`docs/evidence/`, `docs/baseline.md`) are protected paths: changing them needs an explicit human approval, and a new record is not yours to add on your own. **Do not commit results under `docs/evidence/`.** Keep them under `<bench>` and give the maintainers the directory.

## 9. Results table

Copy this table to your record. Before a run, copy the prediction from the case into "Expected"; after it, fill in the rest.

| Case | Expected | Observed | Pass/fail | Evidence file | Notes |
| --- | --- | --- | --- | --- | --- |
| T0 | | | | | |
| T1 boot 1 | | | | | |
| T1 boot 2 | | | | | |
| T2 | | | | | |
| T3a | | | | | |
| T3b | | | | | |
| T4a | | | | | |
| T4b | | | | | |
| T5a | | | | | |
| T5c boot 1 | | | | | |
| T5c boot 2 | | | | | |
| T6 cuts | | | | | |
| T7 | Not runnable yet: needs the update agent work | | | | |
