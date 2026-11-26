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
| Debug probe | An external SEGGER J-Link (a J-Link PLUS is recorded) on the 20-pin J2 header, with J9 and J10 removed. SWD at 400 kHz, device `MIMXRT1062xxx6A`, J-Link software at the version pinned in `.devcontainer/Dockerfile`. The first connection on a new setup failed at 1000 kHz and was made at 100 kHz after J9 and J10 had been corrected |
| Console | The serial port of the on-board DAPLink (OpenSDA) interface, 115200 baud, 8-N-1. On macOS it appears as `/dev/cu.usbmodem<N>`, and the number can change after a reconnection. Its connector is J1 in the NXP manual and in later records, and J41 in the Zephyr guide and in early records, a claim the [baseline](../baseline.md#hardware-and-range-assessment) withdraws: find the USB connector that enumerates as DAPLink on your board |
| Host | Linux, or Windows with WSL2: the probe, the J-Link software, the build and GDB are all in the Dev Container (below) |

**Linux and Windows with WSL2.** The Dev Container can open every USB device of the host, so that it can reach the probe: it binds `/dev/bus/usb`, allows USB character devices and gives `vscode` `sudo`, without `--privileged`.
If a security policy does not allow this, a configuration without that binding can be added back for work without a board ([guide](../board-jlink-usbipd.md#the-dev-container-and-the-board)).

The probe is attached to Linux, to WSL2 through usbipd-win on Windows, and the J-Link software runs in the Dev Container.
The [J-Link board route](../board-jlink-usbipd.md) guide gives the steps, lists which routes have been run and explains the failures seen.

1. PowerShell on Windows: attach the probe to WSL2 as [Getting started, section 7](../getting-started.md#7-if-you-use-a-board) says (`usbipd bind` only when `usbipd list` shows `Not shared`, then `usbipd attach --wsl --busid <BUSID>`), again whenever the probe re-enumerates and loses the attachment.
   `/dev/bus/usb` exists in WSL2 only after the attach.
2. Only where the container cannot open the probe, in a WSL2 or Linux shell in the repository checkout: install `usbutils` and the udev rule, then check the probe and its node:

   ~~~sh
   sudo apt-get update && sudo apt-get install -y usbutils
   sudo cp .devcontainer/jlink/99-crux-jlink.rules /etc/udev/rules.d/
   sudo udevadm control --reload-rules && sudo udevadm trigger
   lsusb -d 1366:
   ls -l /dev/bus/usb/*/*
   ~~~

   The J-Link's node was `crw-rw-rw-` owned by `root` before the rule applied, and `crw-rw----` with owner `root` and group `plugdev` after a reattach. The container can open either.
3. Optional: put `JLink_Linux_<version>_x86_64.deb` in `.devcontainer/jlink/packages/`. The Dev Container build downloads the pinned version by itself ([guide](../board-jlink-usbipd.md#steps)).
4. VS Code: **Dev Containers: Rebuild and Reopen in Container**.
5. In the container, from the repository root `/workspace/crux-pilot`, where every command below runs: `lsusb -d 1366:` lists the J-Link, `id -nG` includes `plugdev`, and `command -v JLinkExe JLinkGDBServer` finds both tools. The Cortex-Debug profiles also need `JLinkGDBServerCLExe`.
6. Connection check, with the switches and jumpers above: `printf 'exit\n' | JLinkExe -nogui 1 -if swd -speed 100 -device MIMXRT1062xxx6A -autoconnect 1` shows `VTref` of about 3.3 V and `Found Cortex-M7`.
7. Build and flash the Time sample:

   ~~~sh
   scripts/build-debug-target.sh 'mimxrt1060_evk@B//qspi'
   west -v flash -d build/zephyr/mimxrt1060_evk_B_qspi -r jlink --speed 400
   ~~~

   The [guide](../board-jlink-usbipd.md#steps) leaves the speed out, so the runner uses `auto`; if `auto` fails, use 4000, then 400, then 100.

8. Console on Windows: the DAPLink's COM port at 115200 baud, 8-N-1. The container gets the probe's USB device, not the serial port. After the boot banner the console shows `CRUX_TIME_READY composition=zephyr`, and `time help` answers.

To debug from VS Code in the Dev Container, which adds the Cortex-Debug extension, pick **Board: Debug** to build, download, reset and stop at `main`, or **Board: Attach** to look at the image already running (it cannot stop at `main`, which has already run). The profiles, the sample prompt and the current build link are in [VS Code debug profiles](#vs-code-debug-profiles) ([guide](../board-jlink-usbipd.md#the-dev-container-and-the-board)).

## Flash and debug

Flashing and debugging use the Dev Container route in [Probe and connection](#probe-and-connection). Confirm the exact board, probe, matching firmware image and recovery plan, and obtain task-specific approval before connecting, resetting or downloading. Attaching a debugger may halt the target.

The debug build of the Time sample:

~~~sh
scripts/build-debug-target.sh 'mimxrt1060_evk@B//qspi'
~~~

See the [debug build script](../../scripts/build-debug-target.sh) and [physical UART test instructions](../../tests/README.md#physical-uart-target). Stop the debugger, GDB Server and serial monitors before a separately authorised physical test that requires exclusive access.

### VS Code debug profiles

[`.vscode/launch.json`](../../.vscode/launch.json) has three Cortex-Debug profiles.
All three debug `build/zephyr/mimxrt1060_evk_B_qspi--current/zephyr/zephyr.elf`.

After each successful build, `scripts/build-debug-target.sh` points the link `build/zephyr/mimxrt1060_evk_B_qspi--current` at the build directory it has just built, whichever application and options it built, and prints the link's path.
A failed build leaves the link as it was.
So the profiles debug the image that `build-debug-target.sh` built last, and one set of profiles serves every sample.
Other builds, such as the `west build` of [tutorial step 14](../tutorial.md#14-flash-hello-crux), do not move the link.

| Profile | What it does |
| --- | --- |
| **Board: Debug** | Runs the task **Board: Build**, which asks for the sample directory to debug, relative to the repository. Press Enter to accept `samples/hello_crux/zephyr`, or type another directory, such as `samples/time/shell/zephyr`. The task builds that sample with `--app`; the profile then downloads the image through the J-Link GDB Server in the container, resets the board and stops at `main` |
| **Board: Attach** | Connects through the J-Link GDB Server in the container to the image already running, without build, reset or download. It cannot stop at `main`, which has already run. Connecting may still halt the target |
| **Board: Attach (external)** | Like **Board: Attach**, through a J-Link GDB Server that runs on the host on port 2331 (see [Known limits](#known-limits)) |

The two attach profiles do not build: the image on the board must be the one behind the link. The task **Board: Flash** flashes that image, and **Board: Clean** deletes `build/zephyr/mimxrt1060_evk_B_qspi`, the debug builds beside it and the link ([VS Code tasks](../build.md#vs-code)). VS Code does not remember the last directory typed into the prompt; it offers `samples/hello_crux/zephyr` each time. The settings the J-Link profiles share are listed in the [J-Link board route](../board-jlink-usbipd.md#the-dev-container-and-the-board).

### Debug builds of other applications

`scripts/build-debug-target.sh` builds the Time sample unless told otherwise. Inside the Dev Container, `--app <directory>` builds another application, and `--debug-optimizations` adds [the fragment](../../scripts/debug-optimizations.conf) that selects `-Og`:

~~~sh
scripts/build-debug-target.sh 'mimxrt1060_evk@B//qspi' --app samples/boards/nxp/mimxrt1060_evk/sd_card_file --debug-optimizations
~~~

Without either option the build directory is `build/zephyr/<board>`, here `build/zephyr/mimxrt1060_evk_B_qspi`.
With `--app` the directory is `build/zephyr/<board>--<application path>`, even for `samples/time/shell/zephyr`, and `--debug-optimizations` appends `--og`.
The script replaces each run of characters other than letters, digits, `_`, `.` and `-` with a single `_` in the board and in the path, so the example above builds in `build/zephyr/mimxrt1060_evk_B_qspi--samples_boards_nxp_mimxrt1060_evk_sd_card_file--og`.
A path outside the repository is keyed by its whole sanitised absolute path, and a relative path is resolved against the directory that the command runs in.
The script prints the build directory before it builds, and the ELF path and the [current build link](#vs-code-debug-profiles) when it finishes.

A debug build records no provenance.
A build with `--debug-optimizations` is never verification evidence: its stack use and timing may differ from the `-Os` images that the verification scripts build, and they have not been re-measured.
The M2, M3 and M5 image checks in `tests/target/` reject it: they require `CONFIG_SIZE_OPTIMIZATIONS=y` and an empty `CONFIG_COMPILER_OPT` in the image's `.config`.
The physical Time suite reads no configuration, so it does not make this check.

`--app` builds an application's base configuration only: samples and tests that need extra configuration files, overlays or modules, such as the controller and networking compositions, are built by their own scripts.
Downloading another application remains a separately authorised physical operation.

### What the platform provides for build and debug

| Provided by the platform | Owned by the project | Not provided |
|---|---|---|
| The build and debug scripts above for the RT1060-EVKB QSPI target. The J-Link GDB Server launcher and the VS Code profiles for that target. The `-Og` fragment. | The board, including its SDRAM timing and device configuration data (DCD). Any J-Link script that prepares a board other than the verified EVKB QSPI flow. Its own build, flash and debug scripts, which may reuse the pieces above. | A general flash or debug wrapper over `west flash` and `west debug`. Unattended programming. A J-Link script that initialises SEMC. |

On Linux and WSL2 the Dev Container has the J-Link software once its package is given (see [Probe and connection](#probe-and-connection)).

## Recovery

| Situation | What exists |
| --- | --- |
| The J-Link does not connect | Check that J9 and J10 are removed and the probe is on J2, then retry with `--speed 4000`, then 400, then 100, as step 7 of [Probe and connection](#probe-and-connection) says (the first connection on a new setup was made at 100 kHz). If J-Link Commander reports `VTref=0.000V`, the target has no power: check the supply before anything else |
| An image under test must be replaced by a known one | The `restore` mode of the program and restore driver loads the accepted normal image, built from `tests/board_images/integration_probe`, and verifies it twice before it starts it. It needs its own approval and evidence directory ([board image profiles](../board-image-profiles.md)) |
| The image in flash does not start | The boot ROM serial downloader (`BOOT_MODE` `01`; the switch setting is in the NXP user manual), not tested on this board. It loads an image into RAM and has no flash command ([bootloader update investigation](../boot-bootloader-update-investigation.md)) |

## Board image profiles

The board test tooling programs and restores only registered images. Each image is described by a profile; the registered profiles, the normal image and the rules for adding a profile are on [Board image profiles](../board-image-profiles.md). A new image needs its own profile, which is a reviewed change.

## Known limits

- The physical test suites have been used from macOS only. Flashing and debugging from the Dev Container on Linux and WSL2 are described in [Probe and connection](#probe-and-connection).
- Flashing and debugging are supported from the Dev Container on Linux and WSL2. For a J-Link GDB Server started on the host on port 2331, as `scripts/macos/start-jlink-gdbserver.command` starts it on a Mac, [`.vscode/launch.json`](../../.vscode/launch.json) has the Cortex-Debug profile **Board: Attach (external)**. It does not build or download: the ELF behind the [current build link](#vs-code-debug-profiles) must match the image on the board. That script listens on all interfaces (`-localhostonly 0`), so use it only on a trusted network.
- On this board CSI shares pins with LPUART3 and LPUART8 (Zephyr's `mimxrt1060_evk` pinctrl). Crux checks no pin conflict, so an image that puts a UART on either of them keeps CSI disabled and checks it itself, as `tests/serial_consumer/zephyr/CMakeLists.txt` does.
- A cross-build for this target proves that an image compiles and links, not that it boots or operates on the board ([supported environments](../getting-started.md#8-supported-environments)).
- The physical Time suite runs against an image that is already loaded and never flashes ([test guide](../../tests/README.md#physical-uart-target)).
- Hardware integration tests have no supported entry point ([Build and Integration Guide](../build.md#hardware-integration-tests)).
