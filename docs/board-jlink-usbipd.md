# J-Link board route on Linux and WSL2

This guide flashes and debugs a board from Linux: the SEGGER J-Link probe is attached to Linux (to WSL2 through usbipd-win on Windows), the J-Link software runs in the Dev Container, and Zephyr's `west flash`, `west debug` and `west attach` drive it through the J-Link runner. [ADR-0007](decisions/0007-west-flash-and-debug-for-people-and-automation.md) records the decision and its conditions. The commands below use the RT1060-EVKB QSPI target; its [board page](boards/mimxrt1060_evkb.md) has the switches, jumpers and recovery.

Each physical operation needs explicit authorisation for the current task ([AGENTS.md](../AGENTS.md#safety-and-workspace-boundaries)). Attaching, flashing, resetting and starting a debug session are physical operations, and attaching may halt the target. Nothing in CI touches a board, and the [device-control tool](../tools/device_control/README.md) is separate from this route.

**What has been run.** Steps 1 to 6, 8 and 9 were run once on a Windows PC with WSL2 (Ubuntu 22.04) and Docker Engine in WSL2, as reported by the maintainer: J-Link software V9.96a, the connection check at 100 kHz (`VTref` 3.322 V, Cortex-M7 found), `west -v flash` of the Time sample at 400 kHz, and the console line on Windows; `west debugserver` at 4000 kHz connected once for a VS Code attach. That run used a separate board Dev Container configuration, which bound `/dev/bus/usb` with a `mounts` entry; what `scripts/bootstrap.sh board-host` and the udevadm handling of `install-jlink.sh` do was carried out by hand, and the probe was attached without `--auto-attach`. Not run there yet: the single Dev Container described here (its `-v` binding of `/dev/bus/usb`, `CRUX_JLINK=auto` and the automatic `scripts/bootstrap.sh`), `scripts/bootstrap.sh board-host` itself, that udevadm handling, `--auto-attach`, the default speed `auto` used below, step 7 (`west attach` and `compare-sections`), `west debug`, the Cortex-Debug profiles, the VS Code flash tasks, and a console inside the container.

## What you need

- On Windows: WSL2 with Docker Engine inside it (not Docker Desktop) and the clone in the WSL2 file system, as [Getting started](getting-started.md) describes. On native Linux: Docker Engine.
- Nothing to download by hand for the J-Link software: the Dev Container build downloads the pinned version of SEGGER's Linux x86_64 Debian package itself (step 3). A package you place or a copy that your organisation hosts overrides it. The Zephyr runner applies the board's QSPI flash loader only with J-Link software 7.70d or newer.
- The Zephyr workspace, which the Dev Container sets up by itself with `scripts/bootstrap.sh` (it runs `scripts/bootstrap-zephyr.sh`, which installs `pylink-square` for the J-Link runner). `scripts/bootstrap.sh status` shows whether it finished.

## Steps

1. **Windows, PowerShell: attach the probe to WSL2.** Install usbipd-win once with `winget install --exact --id dorssel.usbipd-win`. Then:

   ~~~powershell
   usbipd list
   usbipd bind --busid <BUSID>
   usbipd attach --wsl --busid <BUSID> --auto-attach
   ~~~

   `usbipd list` shows the J-Link with vendor ID `1366`. `bind` needs an administrator PowerShell, once per device. Keep the window of `attach --auto-attach` open: it attaches the probe again when it re-enumerates, for example when J-Link software updates the probe's firmware, and the attachment is otherwise lost. Run it again after WSL2 restarts. `/dev/bus/usb` does not exist in WSL2 until a USB device is attached. While the probe is attached, Windows tools cannot see it; `usbipd detach --busid <BUSID>` gives it back. On native Linux skip this step.

2. **WSL2 or Linux shell, in the repository checkout: prepare the Linux side.**

   ~~~sh
   scripts/bootstrap.sh board-host
   ~~~

   It installs `usbutils` if `lsusb` is missing (with `sudo apt-get`), stops with the `usbipd attach` line if `/dev/bus/usb` is missing, checks that a J-Link is listed, installs the udev rule [`99-crux-jlink.rules`](../.devcontainer/jlink/99-crux-jlink.rules) once, and prints the probe's device node. Either of these results lets the container open the probe:

   - `crw-rw----` with group `plugdev`: the result when the rule applies, on native Linux and also seen on WSL2.
   - `crw-rw-rw-` with owner and group `root`: seen on WSL2 for a usbipd-attached J-Link before the rule applied.

   The script stops with advice if the node is neither. A probe that re-enumerates gets a new node, which on WSL2 may not get the rule (`crw-rw-r--` with owner `root`), so run it again after a reattach. It refuses to run inside the container. It never talks to the probe or the board.

3. **The J-Link package (optional step).** By default you do nothing here: the image build downloads the J-Link version pinned in the [Dockerfile](../.devcontainer/Dockerfile) (`CRUX_JLINK_SEGGER_VERSION`) from SEGGER's download endpoint and installs it only if its SHA-256 matches `CRUX_JLINK_SEGGER_SHA256`. **The download accepts SEGGER's terms of use for you, as clicking the download on SEGGER's page does; if you do not accept them, use one of the overrides below.** If the download fails or the SHA-256 does not match, the build prints a warning, installs nothing and finishes without the J-Link software; a plain rebuild can reuse that cached step, so use **Dev Containers: Rebuild Container Without Cache** to try the download again. This download has not been run in an image build yet. Two overrides, in this order, win over the download:
   - Put a `JLink_Linux_<version>_x86_64.deb` in [`.devcontainer/jlink/packages/`](../.devcontainer/jlink/packages/README.md); Git ignores it.
   - If your organisation hosts a copy after accepting the SEGGER licence itself, set the build arguments `CRUX_JLINK_URL` (an `https://` URL) and `CRUX_JLINK_DEB_SHA256` in [`.devcontainer/devcontainer.json`](../.devcontainer/devcontainer.json); the build downloads it and checks its SHA-256.

   To move to another J-Link version, change the two `CRUX_JLINK_SEGGER_*` values in the Dockerfile together.

4. **VS Code: open the Dev Container.** Run **Dev Containers: Rebuild and Reopen in Container** (**Rebuild Container** if it is already open), so that the image gets the J-Link software. The build log prints `J-Link package: <file>, SHA-256 <hash>`.

5. **In the container: check the probe and the tools.** Run this and every later command in the container from the repository root, the folder VS Code opens (`/workspace/crux-pilot`):

   ~~~sh
   cd /workspace/crux-pilot
   lsusb -d 1366:
   id -nG
   command -v JLinkExe JLinkGDBServer JLinkGDBServerCLExe
   ~~~

   The J-Link is listed, `plugdev` is among the groups, and all three tools are found (Cortex-Debug starts `JLinkGDBServerCLExe`).

6. **Connection check.** Before any write, set the board up as its [board page](boards/mimxrt1060_evkb.md#switches-and-jumpers) says, including its power. Then connect with J-Link Commander alone, which prints what the runner hides:

   ~~~sh
   printf 'exit\n' | JLinkExe -nogui 1 -if swd -speed 100 -device MIMXRT1062xxx6A -autoconnect 1
   ~~~

   Look for `VTref` of about 3.3 V and `Found Cortex-M7`. `VTref=0.000V` means the probe sees no target power: check the supply before anything else. This step connects to the target and may halt it.

7. **Read-only check: attach and compare.** Do this before the first write on a new set-up. Build the ELF of the image on the board, here the Time sample (`samples/time/shell`), the image that has been flashed this way; [Part C of the tutorial](tutorial.md#part-c-run-on-your-board) sets which samples to flash and in which order. Then attach without reset or load. `-r jlink` is required, because Zephyr's default runner for this board is LinkServer. The build directory is relative to the repository root.

   ~~~sh
   cd /workspace/crux-pilot
   scripts/build-debug-target.sh 'mimxrt1060_evk@B//qspi'
   west attach -d build/zephyr/mimxrt1060_evk_B_qspi -r jlink
   ~~~

   At the GDB prompt run `compare-sections`, then `detach` and `quit`. Every loadable section should report `matched`; a mismatch means the board holds another image, not that the route is broken.

8. **Flash**, only with authorisation that names the operation and the image:

   ~~~sh
   cd /workspace/crux-pilot
   west flash -d build/zephyr/mimxrt1060_evk_B_qspi -r jlink
   ~~~

   In VS Code, **Terminal > Run Task > Board: Build and flash (west flash)** runs the build of step 7 and then this command; **Board: Build and flash a sample (west flash)** builds and flashes the sample you pick from a list, `samples/hello_crux` or the Time sample, as [Part C of the tutorial](tutorial.md#13-flash-hello-crux) does. The flash runs J-Link Commander with the device `MIMXRT1062xxx6A` and the board's QSPI loader from Zephyr's `boards/nxp/mimxrt1060_evk/board.cmake`, loads the image and starts it. Do not give `--erase`, which mass-erases the flash. `west debug` with the same options also **loads the image** before it debugs; use `west attach` to debug an image that is already on the board. If `west` fails with only `JLinkExe exited with status 1`, run it again with `west -v flash ...` (or `west -v attach ...`) to see J-Link's own output.

9. **Console, on Windows.** The container gets the probe's USB device, not the board's serial port. Open the DAPLink's COM port on Windows (Device Manager lists it under Ports) in a serial terminal at 115200 baud, 8-N-1. After a reset the Time sample prints the Zephyr boot banner and then:

   ~~~text
   CRUX_TIME_READY composition=zephyr
   ~~~

   `time help` at the prompt lists the Time commands.

## If a step fails

| Symptom | What to do |
| --- | --- |
| `scripts/bootstrap.sh status` or the build log says `J-Link software is not installed` | Place the package or set the URL and checksum (step 3), then **Rebuild Container** |
| Step 5 shows an empty `/dev/bus/usb` | The container started before the probe was attached; attach it (step 1). The folder is bound, so the probe should appear without a restart, which has not been tried; if it does not, run **Dev Containers: Rebuild Container** |
| The build stops at a SHA-256 mismatch | The package is not the pinned one; check the file or the pin |
| Step 5 lists no J-Link | Attach it again (step 1) and run step 2 again; the bound folder follows a new attach |
| Step 6 shows `VTref=0.000V` | The target has no power: check the board's supply on the [board page](boards/mimxrt1060_evkb.md#switches-and-jumpers) |
| Step 7 or 8 cannot connect | Retry with `--speed 4000`, then `--speed 400`, then `--speed 100`; if step 6 fails too, check the jumpers on the [board page](boards/mimxrt1060_evkb.md#recovery) |
| J-Link reports `Cannot connect to the probe/programmer` | The probe is not attached to WSL2 or its node is not writable: attach it again (step 1, with `--auto-attach`) and run step 2 again |
| `west` reports only `JLinkExe exited with status 1` | Run step 6, then rerun `west` with `-v` to see J-Link's output |

## The Dev Container and the board

There is one Dev Container, [`.devcontainer/devcontainer.json`](../.devcontainer/devcontainer.json), and it is ready for a board. Without a probe or a J-Link package it works the same for Host and `native_sim` work. For the board it does three things:

- The build argument `CRUX_JLINK=auto` runs [`install-jlink.sh`](../.devcontainer/jlink/install-jlink.sh), which installs the J-Link package and `usbutils` and adds the `vscode` user to `plugdev` (ID 46 on Debian and Ubuntu). The package comes from a placed file, then `CRUX_JLINK_URL`, then the pinned SEGGER download (step 3); when none gives a package that passes its SHA-256 check, it prints a warning and installs nothing. `CRUX_JLINK=1` makes a missing package an error; `0` skips the step, including the download. The package's install script calls `udevadm`, which the image does not have, so `install-jlink.sh` provides a no-op `/usr/sbin/udevadm` during the install only and removes it afterwards; the udev rule acts on the Linux side, not in the container.
- It binds the host's `/dev/bus/usb` with `docker run -v` (in `runArgs`) and allows only USB character devices (`--device-cgroup-rule=c 189:* rmw`). It does not use `--privileged`. `-v` creates the folder when it does not exist yet, as on WSL2 before the first `usbipd attach`, where a `mounts` entry would stop the container from starting. A probe attached after the container started, or one that re-enumerates, should appear in the bound folder; that has not been tried. **Security:** this gives every container the host's USB device nodes, for everyone who uses it, with or without a board. The `vscode` user can become root in the container with `sudo`, and root in the container can open any of those USB devices (keyboards, security keys, storage and other devices) whatever the node's permissions, because the cgroup rule allows all USB character devices. On native Linux that means any process in the container can reach every USB device of the PC. Use the container only with code you trust, as with any Dev Container.
- It adds the Cortex-Debug extension (below).

### CI and automated image builds

CI and every other automated build of the Dev Container image pass `--build-arg CRUX_JLINK=0`, so they never download from SEGGER and accept no terms of use for anyone. They need no J-Link software, because no CI workflow flashes, resets or attaches to a board (ADR-0007, W2). An agent that flashes under W0 and W1 does so in the people's Dev Container, built with `auto`. Build the image from the repository root with:

~~~sh
docker build --platform linux/amd64 --build-arg CRUX_JLINK=0 -f .devcontainer/Dockerfile -t crux-dev .
~~~

`devcontainer.json` keeps `CRUX_JLINK=auto` for people. A job that builds or starts the image through `devcontainer.json`, for example with the Dev Container CLI, takes that `auto` and downloads; build the image with the command above instead and run the job in it. No GitHub workflow of this repository builds the Dev Container image today.

`CRUX_JLINK_DEB` picks one of several packages in the folder by file name. Build provenance hashes `devcontainer.json` and the Dockerfile; it does not record whether a J-Link package was installed. A package left in `packages/` is copied into every image build.

Options of the J-Link runner:

| Option | Use |
| --- | --- |
| `--speed <kHz>` | SWD speed. The commands above leave it out, so the runner uses its default, `auto`. If the connection fails, retry with 4000, then 400, then 100. Recorded on this board: a flash at 400 kHz (from WSL2 and in the macOS records), a `west debugserver` connection at 4000 kHz, and 100 kHz for a first connection on a new set-up. `auto` has no record yet |
| `-i <serial>`, `--dev-id <serial>` | Select a probe by serial number when more than one is attached. `lsusb -v -d 1366:` shows it as `iSerial` |
| `-O <option>`, `--tool-opt <option>` | Pass an option to the J-Link tools |

**VS Code debugging.** The Dev Container adds the [Cortex-Debug](https://github.com/Marus/cortex-debug) extension (`marus25.cortex-debug`), which starts the J-Link GDB Server itself. Pick one of two profiles in [`.vscode/launch.json`](../.vscode/launch.json); nothing needs editing. Both use the device `MIMXRT1062xxx6A`, SWD, the speed `auto` (`serverArgs`) and the Time sample's ELF under `build/zephyr/mimxrt1060_evk_B_qspi`:

- **Board: Flash and run to main** builds the Time sample, downloads it, resets the board and stops at `main`.
- **Board: Attach (no reset)** connects to the image already running, without reset or download. It cannot stop at `main`, which has already run. Connecting may still halt the target.

Neither profile has been run. As reported by the maintainer, Cortex-Debug is in use for development, also before Crux, and a VS Code attach through `west debugserver` at 4000 kHz worked once from that separate board configuration. Settings you may add to a local copy of a profile, none of them tried here:

- `svdFile`: the MIMXRT1062 SVD file, for the peripheral register view. No SVD file is in the Zephyr workspace; NXP ships one with its MCUXpresso SDK and device packs under NXP's licence.
- `rtos`: a J-Link RTOS plugin for Zephyr thread awareness, if the installed J-Link software has one, together with `CONFIG_DEBUG_THREAD_INFO=y` in the image.
- `rttConfig`: an RTT console, for an image built with Zephyr's RTT console instead of the UART.

The **EVKB QSPI** profiles connect to `host.docker.internal:2331` for the host GDB Server route on the board page and are unchanged. Stop a debug session before you use `west flash` or J-Link Commander, which need the probe.

## Not covered

- Images that run from SDRAM, which need a J-Link script that sets up SDRAM before loading. No such script exists in Crux.
- Docker Desktop, which handles USB devices differently. For people without a board, the `-v` binding was tried with Docker Desktop 29.8.2 on macOS in a plain `busybox` container, not in the Dev Container itself: `docker run -v /dev/bus/usb:/dev/bus/usb` started, and a missing `-v` source folder was created where a `--mount` bind refused to start. Docker Desktop on Windows was not tried.
