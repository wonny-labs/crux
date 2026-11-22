# MIMXRT1060-EVKB

This page holds everything specific to the NXP MIMXRT1060-EVKB, revision B: its board target, switches and jumpers, probe and connection, flash and debug, recovery, image profiles and known limits. [Getting started](../getting-started.md) and the [Tutorial](../tutorial.md#part-c-run-on-your-board) link here for these steps.

Any operation on the board, such as connecting a probe, a reset or a download, needs approval for the task ([AGENTS.md](../../AGENTS.md#safety-and-workspace-boundaries)). Which components have evidence on this board is recorded in [Component readiness](../component-readiness.md).

## Board target

| Item | Value |
| --- | --- |
| `-b` target | `mimxrt1060_evk@B//qspi` |
| Build directory key | `mimxrt1060_evk_B_qspi`, the target with each run of other characters replaced by `_` (see [Debug builds of other applications](#debug-builds-of-other-applications)) |
| SoC and memory | i.MX RT1062 (Cortex-M7), standard 8 MiB QSPI NOR boot flash, a microSD slot and no eMMC. The target assumes no HyperFlash rework |
| Zephyr board guide | [`mimxrt1060_evk`](https://github.com/zephyrproject-rtos/zephyr/blob/v4.4.0/boards/nxp/mimxrt1060_evk/doc/index.rst) (Zephyr v4.4.0) |

Check the revision on the board's silkscreen. A DAPLink volume named `RT1060-EVK` does not identify the revision or the flash ([baseline](../baseline.md#hardware-and-range-assessment)).

## Switches and jumpers

| Part | Setting | Purpose |
| --- | --- | --- |
| SW4 (boot mode) | OFF–OFF–ON–OFF | Boot from the QSPI flash. This is the setting the target expects |
| J9 and J10 | Removed | Isolate the on-board SWD circuit while an external J-Link is on J2 |
| J11 and J13 | Shorted (default) | UART routing to the on-board debug interface |
| J40 | Pins 5–6 (default) | Power selection |

Operator practice from bench sessions, not a repository record: check all four SW4 switches by eye after every change, because one switch in the wrong position changes the boot mode. The jumper settings come from NXP's [external J-Link instructions](https://community.nxp.com/t5/i-MX-RT-Crossover-MCUs-Knowledge/Using-J-Link-with-MIMXRT1060-EVKB-or-MIMXRT1040-EVK/ta-p/1452717) and the [MIMXRT1060-EVKB user manual](https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/mcuxpresso-ide/9718/1/MIMXRT1060EVKBUM%20%282%29.pdf); verify the labels on your board before you change anything.

**Power.** The USB connection of the on-board DAPLink interface also powers the board. Unplugging it is a power-off only when it is the only supply. Switching off the hub port of the DAPLink did not remove target power in one recorded check ([eMMC physical gate](../emmc-reliance-physical-gate.md)), so a hub port switch does not prove a power cycle: measure the target reference voltage.

## Probe and connection

| Connection | What is used |
| --- | --- |
| Debug probe | An external SEGGER J-Link (a J-Link PLUS is recorded) on the 20-pin J2 header, with J9 and J10 removed. SWD at 400 kHz, device `MIMXRT1062xxx6A`, J-Link software V9.86a. The first connection on a new setup failed at 1000 kHz and was made at 100 kHz after J9 and J10 had been corrected |
| Console | The serial port of the on-board DAPLink (OpenSDA) interface, 115200 baud, 8-N-1. On macOS it appears as `/dev/cu.usbmodem<N>`, and the number can change after a reconnection. Its connector is J1 in the NXP manual and in later records, and J41 in the Zephyr guide and in early records, a claim the [baseline](../baseline.md#hardware-and-range-assessment) withdraws: find the USB connector that enumerates as DAPLink on your board |
| Host | On macOS, a Mac runs the J-Link GDB Server and the Dev Container runs the build and GDB, connecting to the server at `host.docker.internal:2331`. On Linux and WSL2, everything runs in the Dev Container (below) |

**Linux and Windows with WSL2.** The probe is attached to Linux, to WSL2 through usbipd-win on Windows, and the J-Link software runs in the Dev Container. The steps below were run once on a Windows PC with WSL2 (Ubuntu 22.04) and Docker Engine in WSL2, as reported by the maintainer, with J-Link software V9.96a, using a separate board Dev Container configuration; the image was built with a no-op `/usr/sbin/udevadm` added by hand, which `install-jlink.sh` adds itself. The [J-Link board route](../board-jlink-usbipd.md) guide gives the current path, with the single Dev Container, `scripts/bootstrap.sh board-host`, `usbipd attach --auto-attach` and an organisation-hosted package URL, which have not been run, and explains the failures seen.

1. PowerShell on Windows: `usbipd list`, then `usbipd bind --busid <BUSID>` (administrator, once per device), then `usbipd attach --wsl --busid <BUSID>`, again whenever the probe re-enumerates and loses the attachment. `/dev/bus/usb` exists in WSL2 only after the attach.
2. WSL2 shell, in the repository checkout: install `usbutils` and the udev rule, then check the probe and its node:

   ~~~sh
   sudo apt-get update && sudo apt-get install -y usbutils
   sudo cp .devcontainer/jlink/99-crux-jlink.rules /etc/udev/rules.d/
   sudo udevadm control --reload-rules && sudo udevadm trigger
   lsusb -d 1366:
   ls -l /dev/bus/usb/*/*
   ~~~

   The J-Link's node was `crw-rw-rw-` owned by `root` before the rule applied, and `crw-rw----` with owner `root` and group `plugdev` after a reattach. The container can open either.
3. Put `JLink_Linux_<version>_x86_64.deb` in `.devcontainer/jlink/packages/`.
4. VS Code: **Dev Containers: Rebuild and Reopen in Container**. That run used a separate board configuration; the [guide](../board-jlink-usbipd.md#steps) uses the one Dev Container.
5. In the container, from the repository root `/workspace/crux-pilot`, where every command below runs: `lsusb -d 1366:` lists the J-Link, `id -nG` includes `plugdev`, and `command -v JLinkExe JLinkGDBServer` finds both tools. The Cortex-Debug profiles also need `JLinkGDBServerCLExe`, which was not checked in that run.
6. Connection check, with the switches and jumpers above: `printf 'exit\n' | JLinkExe -nogui 1 -if swd -speed 100 -device MIMXRT1062xxx6A -autoconnect 1` shows `VTref` of about 3.3 V and `Found Cortex-M7`.
7. Build and flash the Time sample:

   ~~~sh
   scripts/build-debug-target.sh 'mimxrt1060_evk@B//qspi'
   west -v flash -d build/zephyr/mimxrt1060_evk_B_qspi -r jlink --speed 400
   ~~~

   The run used `--speed 400`. The [guide](../board-jlink-usbipd.md#steps) leaves the speed out, so the runner uses `auto`, which has not been run yet; if `auto` fails, use 4000, then 400, then 100. `west debugserver` at 4000 kHz connected once.

8. Console on Windows: the DAPLink's COM port at 115200 baud, 8-N-1. The container gets the probe's USB device, not the serial port. After the boot banner the console shows `CRUX_TIME_READY composition=zephyr`, and `time help` answers.

To debug from VS Code in the Dev Container, which adds the Cortex-Debug extension, pick **Board: Flash and run to main** to build, download, reset and stop at `main`, or **Board: Attach (no reset)** to look at the image already running (it cannot stop at `main`, which has already run) ([guide](../board-jlink-usbipd.md#the-dev-container-and-the-board)). As reported by the maintainer, an attach through `west debugserver` at 4000 kHz worked once; the two Cortex-Debug profiles have not been run.

Not run on this route: the speed `auto`, the Cortex-Debug profiles, the read-only `west attach` check with `compare-sections`, `west debug`, and a console inside the container (it would need the serial device, such as `/dev/ttyACM0`, passed to the container).

## Flash and debug

The existing EVKB QSPI debugging setup uses a SEGGER J-Link connected to a Mac. This is not a general firmware-programming procedure. Confirm the exact board, probe, matching firmware image and recovery plan, and obtain task-specific approval before connecting, resetting or downloading. Starting the GDB Server or attaching a debugger may halt the target.

On the approved macOS host, from the repository checkout (not the Dev Container), start the existing server:

~~~sh
bash scripts/macos/start-jlink-gdbserver.command
~~~

The script prefers `/usr/local/bin/JLinkGDBServer` and falls back to a `JLinkGDBServerCLExe` under `/Applications/SEGGER`. It starts the server with `-device MIMXRT1062xxx6A -if SWD -speed 400 -endian little -port 2331 -localhostonly 0`: SWD at 400 kHz, GDB on TCP port 2331. It accepts remote connections rather than restricting access to localhost, so use it only on a trusted network. Stop it with Ctrl-C when debugging is finished.

The existing VS Code [debug configurations](../../.vscode/launch.json) connect from the Dev Container to `host.docker.internal:2331`:

- **EVKB QSPI: Attach** uses an ELF matching the image already on the board and does not download firmware. The connection may still halt the target.
- **EVKB QSPI: Flash** builds the **Time sample**, then resets the board and downloads that image. It must not be used to flash arbitrary applications or unapproved storage candidates. Its `stopAtEntry` setting stops the debugger at the reset entry (`reset.S`) after the download; Continue (F5) starts the image.

The profile's build is the same as this command in the Dev Container:

~~~sh
scripts/build-debug-target.sh 'mimxrt1060_evk@B//qspi'
~~~

The Time sample prints `CRUX_TIME_READY composition=zephyr` on the console after the Zephyr boot banner. That line was recorded after a download with GDB and a reset with J-Link Commander in the [M4 UART run](../baseline.md#m4-physical-uart-and-rtc-acceptance-2026-10-17); the recorded run of the Flash profile stopped at `main` and did not read the console ([VS Code debugging record](../baseline.md#fix-and-actual-verification)). The chain of the Flash profile, Continue and the console line has no record of its own.

See the [debug build script](../../scripts/build-debug-target.sh) and [physical UART test instructions](../../tests/README.md#physical-uart-target). Stop the debugger, GDB Server and serial monitors before a separately authorised physical test that requires exclusive access.

### Debug builds of other applications

`scripts/build-debug-target.sh` builds the Time sample unless told otherwise. Inside the Dev Container, `--app <directory>` builds another application, and `--debug-optimizations` adds [the fragment](../../scripts/debug-optimizations.conf) that selects `-Og`:

~~~sh
scripts/build-debug-target.sh 'mimxrt1060_evk@B//qspi' --app samples/storage_sd --debug-optimizations
~~~

Without either option the build directory is the one that the VS Code profile and the clean task name. With `--app` the directory is `build/zephyr/<board>--<application path>`, even for `samples/time/clock_shell`, and `--debug-optimizations` appends `--og`. The script replaces each run of characters other than letters, digits, `_`, `.` and `-` with a single `_` in the board and in the path, so the example above builds in `build/zephyr/mimxrt1060_evk_B_qspi--samples_storage_sd--og`. A path outside the repository is keyed by its whole sanitised absolute path, and a relative path is resolved against the directory that the command runs in. The script prints the build directory before it builds and the ELF path when it finishes. A debug build records no provenance. A build with `--debug-optimizations` is never verification evidence: its stack use and timing may differ from the `-Os` images that the verification scripts build, and they have not been re-measured. The M2, M3 and M5 image checks in `tests/target/` reject it: they require `CONFIG_SIZE_OPTIMIZATIONS=y` and an empty `CONFIG_COMPILER_OPT` in the image's `.config`. The physical Time suite reads no configuration, so it does not make this check. `--app` builds an application's base configuration only: samples and tests that need extra configuration files, overlays or modules, such as the controller and networking compositions, are built by their own scripts. The **EVKB QSPI: Flash** profile still downloads only the Time sample. Downloading another application remains a separately authorised physical operation.

### What the platform provides for build and debug

| Provided by the platform | Owned by the project | Not provided |
|---|---|---|
| The build and debug scripts above for the RT1060-EVKB QSPI target. The J-Link GDB Server launcher and the VS Code profiles for that target. The `-Og` fragment. | The board, including its SDRAM timing and device configuration data (DCD). Any J-Link script that prepares a board other than the verified EVKB QSPI flow. Its own build, flash and debug scripts, which may reuse the pieces above. | A general flash or debug wrapper over `west flash` and `west debug`. Unattended programming. A J-Link script that initialises SEMC. |

The Zephyr J-Link runner needs a local J-Link Commander even when it is given a remote GDB host. On macOS the probe stays on the Mac, so the split between the Mac-hosted server and the container GDB stays. On Linux and WSL2 the Dev Container has the J-Link software once its package is given (see [Probe and connection](#probe-and-connection)).

## Recovery

| Situation | What exists |
| --- | --- |
| The J-Link does not connect | Check that J9 and J10 are removed and the probe is on J2, then lower the SWD speed (the first connection on a new setup was made at 100 kHz). If J-Link Commander reports `VTref=0.000V`, the target has no power: check the supply before anything else |
| An image under test must be replaced by a known one | The `restore` mode of the program and restore driver loads the accepted normal image, built from `tests/board_images/integration_probe`, and verifies it twice before it starts it. It needs its own approval and evidence directory ([board image profiles](../board-image-profiles.md)) |
| The image in flash does not start | The boot ROM serial downloader (`BOOT_MODE` `01`; the switch setting is in the NXP user manual), not tested on this board. It loads an image into RAM and has no flash command ([bootloader update investigation](../boot-bootloader-update-investigation.md)) |

## Board image profiles

The board test tooling programs and restores only registered images. Each image is described by a profile; the registered profiles, the normal image and the rules for adding a profile are on [Board image profiles](../board-image-profiles.md). A new image needs its own profile, which is a reviewed change.

## Known limits

- Debugging and the physical test suites have been used from macOS only. From Windows with WSL2 one flash and console check of the Time sample is reported ([Probe and connection](#probe-and-connection)).
- The **EVKB QSPI: Flash** profile downloads only the Time sample. `samples/hello_crux` is built and run on `native_sim` only.
- A cross-build for this target proves that an image compiles and links, not that it boots or operates on the board ([supported environments](../getting-started.md#8-supported-environments)).
- The physical Time suite runs against an image that is already loaded and never flashes ([test guide](../../tests/README.md#physical-uart-target)).
- Hardware integration tests have no supported entry point ([Build and Integration Guide](../build.md#hardware-integration-tests)).
