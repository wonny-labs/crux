# J-Link board route on Linux and WSL2

This guide flashes and debugs a board from Linux: the SEGGER J-Link probe is attached to Linux (to WSL2 through usbipd-win on Windows), the J-Link software runs in the optional board Dev Container, and Zephyr's `west flash`, `west debug` and `west attach` drive it through the J-Link runner. [ADR-0007](decisions/0007-west-flash-and-debug-for-people-and-automation.md) records the decision and its conditions. The commands below use the RT1060-EVKB QSPI target; its [board page](boards/mimxrt1060_evkb.md) has the switches, jumpers and recovery.

Each physical operation needs explicit authorisation for the current task ([AGENTS.md](../AGENTS.md#safety-and-workspace-boundaries)). Attaching, flashing, resetting and starting a debug session are physical operations, and attaching may halt the target. Nothing in CI touches a board, and the [device-control tool](../tools/device_control/README.md) is separate from this route.

**What has been run.** Steps 1 to 5 were run on a Windows PC with WSL2 (Ubuntu 22.04) and Docker Engine in WSL2, with what `scripts/setup-board-host.sh` and the udevadm handling of `install-jlink.sh` do carried out by hand; the script, that handling and `--auto-attach` themselves have not been run there yet. Steps 6 to 8 have not been run.

## What you need

- On Windows: WSL2 with Docker Engine inside it (not Docker Desktop) and the clone in the WSL2 file system, as [Getting started](getting-started.md) describes. On native Linux: Docker Engine.
- The SEGGER J-Link software for Linux, the 64-bit x86 Debian package `JLink_Linux_<version>_x86_64.deb`, downloaded by you from SEGGER after accepting its licence, or the URL and SHA-256 of a copy that your organisation hosts (step 3). The Zephyr runner applies the board's QSPI flash loader only with J-Link software 7.70d or newer.
- The Zephyr workspace bootstrapped with `scripts/bootstrap-zephyr.sh`, which installs `pylink-square` for the J-Link runner.

## Steps

1. **Windows, PowerShell: attach the probe to WSL2.** Install usbipd-win once with `winget install --exact --id dorssel.usbipd-win`. Then:

   ~~~powershell
   usbipd list
   usbipd bind --busid <BUSID>
   usbipd attach --wsl --busid <BUSID> --auto-attach
   ~~~

   `usbipd list` shows the J-Link with vendor ID `1366`. `bind` needs an administrator PowerShell, once per device. Keep the window of `attach --auto-attach` open: it attaches the probe again when it re-enumerates, for example after a reset or when J-Link software updates the probe's firmware, and the attachment is otherwise lost. Run it again after WSL2 restarts. `/dev/bus/usb` does not exist in WSL2 until a USB device is attached. While the probe is attached, Windows tools cannot see it; `usbipd detach --busid <BUSID>` gives it back. On native Linux skip this step.

2. **WSL2 or Linux shell, in the repository checkout: prepare the Linux side.**

   ~~~sh
   scripts/setup-board-host.sh
   ~~~

   It installs `usbutils` if `lsusb` is missing (with `sudo apt-get`), stops with the `usbipd attach` line if `/dev/bus/usb` is missing, checks that a J-Link is listed, installs the udev rule [`99-crux-jlink.rules`](../.devcontainer/jlink/99-crux-jlink.rules) once, and prints the probe's device node. Either of these results lets the container open the probe:

   - `crw-rw----` with group `plugdev`: the expected result on native Linux, where the rule applies.
   - `crw-rw-rw-` with owner and group `root`: seen on WSL2 for the usbipd-attached J-Link.

   The script stops with advice if the node is neither. A probe that re-enumerates gets a new node, which on WSL2 may not get the rule (`crw-rw-r--` with owner `root`), so run the script again after a reattach. It never talks to the probe or the board.

3. **The J-Link package.** Put `JLink_Linux_<version>_x86_64.deb` in [`.devcontainer/jlink/packages/`](../.devcontainer/jlink/packages/README.md); Git ignores it. If your organisation hosts a copy after accepting the SEGGER licence itself, set the build arguments `CRUX_JLINK_URL` (an `https://` URL) and `CRUX_JLINK_DEB_SHA256` in `.devcontainer/jlink/devcontainer.json` instead, and the build downloads it and checks its SHA-256. A placed package wins over the URL. Without either, the build stops and says which file to place where. Nothing is downloaded from SEGGER, and no licence is accepted for you.

4. **VS Code: open the board Dev Container.** Run **Dev Containers: Rebuild and Reopen in Container** and choose **Crux Pilot board, J-Link**. The build log prints `J-Link package: <file>, SHA-256 <hash>`.

5. **In the container: check the probe and the tools.** Run this and every later command in the container from the repository root, the folder VS Code opens (`/workspace/crux-pilot`):

   ~~~sh
   cd /workspace/crux-pilot
   lsusb -d 1366:
   id -nG
   command -v JLinkExe JLinkGDBServer
   ~~~

   The J-Link is listed, `plugdev` is among the groups, and both tools are found.

6. **Connection check.** Before any write, check the board as its page says: on the EVKB the J-Link on J2, J9 and J10 removed, SW4 OFF–OFF–ON–OFF, and the board powered ([board page](boards/mimxrt1060_evkb.md#switches-and-jumpers)). Then connect with J-Link Commander alone, which prints what the runner hides:

   ~~~sh
   printf 'exit\n' | JLinkExe -nogui 1 -if swd -speed 100 -device MIMXRT1062xxx6A -autoconnect 1
   ~~~

   Look for `VTref` of about 3.3 V and `Found Cortex-M7`. `VTref=0.000V` means the probe sees no target power: check the supply before anything else. This step connects to the target and may halt it.

7. **Read-only check: attach and compare.** Do this before the first write on a new set-up. Build the ELF of the image on the board, here the Time sample, then attach without reset or load. `-r jlink` is required, because Zephyr's default runner for this board is LinkServer. The build directory is relative to the repository root.

   ~~~sh
   cd /workspace/crux-pilot
   scripts/build-debug-target.sh 'mimxrt1060_evk@B//qspi'
   west attach -d build/zephyr/mimxrt1060_evk_B_qspi -r jlink --speed 400
   ~~~

   At the GDB prompt run `compare-sections`, then `detach` and `quit`. Every loadable section should report `matched`; a mismatch means the board holds another image, not that the route is broken.

8. **Flash**, only with authorisation that names the operation and the image:

   ~~~sh
   cd /workspace/crux-pilot
   west flash -d build/zephyr/mimxrt1060_evk_B_qspi -r jlink --speed 400
   ~~~

   It runs J-Link Commander with the device `MIMXRT1062xxx6A` and the board's QSPI loader from Zephyr's `boards/nxp/mimxrt1060_evk/board.cmake`, loads the image and starts it. Do not give `--erase`, which mass-erases the flash. `west debug` with the same options also **loads the image** before it debugs; use `west attach` to debug an image that is already on the board. If `west` fails with only `JLinkExe exited with status 1`, run it again with `west -v flash ...` (or `west -v attach ...`) to see J-Link's own output.

## If a step fails

| Symptom | What to do |
| --- | --- |
| Docker refuses to start the board container because `/dev/bus/usb` is missing | Attach the probe first (step 1), then rebuild |
| The build stops with `no SEGGER J-Link package` | Place the package or set the URL and checksum (step 3) |
| The build stops at a SHA-256 mismatch | The package is not the pinned one; check the file or the pin |
| Step 5 lists no J-Link | Attach it again (step 1) and run step 2 again; the bind mount follows a new attach |
| Step 6 shows `VTref=0.000V` | The target has no power: check the board's supply on the [board page](boards/mimxrt1060_evkb.md#switches-and-jumpers) |
| Step 6 or 7 cannot connect | Retry with `-speed 100` or `--speed 100`, then check the jumpers on the [board page](boards/mimxrt1060_evkb.md#recovery) |
| J-Link reports `Cannot connect to the probe/programmer` | The probe is not attached to WSL2 or its node is not writable: attach it again (step 1, with `--auto-attach`) and run step 2 again |
| `west` reports only `JLinkExe exited with status 1` | Run step 6, then rerun `west` with `-v` to see J-Link's output |

The default Dev Container still works for builds: reopen it with **Crux Pilot (Ubuntu 24.04 amd64)**.

## The board Dev Container

[`.devcontainer/jlink/devcontainer.json`](../.devcontainer/jlink/devcontainer.json) reuses the default [Dockerfile](../.devcontainer/Dockerfile) with the build argument `CRUX_JLINK=1`, which runs [`install-jlink.sh`](../.devcontainer/jlink/install-jlink.sh). The default container is unchanged for people without a board: it mounts no USB devices and installs no J-Link software. The board container differs in these ways:

- It installs the J-Link package and `usbutils` and adds the `vscode` user to `plugdev` (ID 46 on Debian and Ubuntu). The package's install script calls `udevadm`, which the image does not have, so `install-jlink.sh` provides a no-op `/usr/sbin/udevadm` during the install only and removes it afterwards; the udev rule acts on the Linux side, not in the container.
- It bind-mounts the host's `/dev/bus/usb` and allows only USB character devices (`--device-cgroup-rule=c 189:* rmw`). It does not use `--privileged`. A probe that re-enumerates after a reset or a new attach stays reachable.
- `CRUX_JLINK_DEB` picks one of several packages in the folder by file name.

Build provenance records the default `.devcontainer/devcontainer.json` and the Dockerfile, not the board configuration, so use the default container for builds whose provenance matters. A package left in `packages/` is copied into every image build, including the default one, and enlarges it without installing anything.

Options of the J-Link runner:

| Option | Use |
| --- | --- |
| `--speed <kHz>` | SWD speed. The runner's default is `auto`. Make the first connection at 100 to 400 kHz; 400 kHz is the recorded value on the EVKB and the documented default here, and 100 kHz on a first connection. 4000 kHz, J-Link's usual value, should work once connected but has no record on this board yet |
| `-i <serial>`, `--dev-id <serial>` | Select a probe by serial number when more than one is attached. `lsusb -v -d 1366:` shows it as `iSerial` |
| `-O <option>`, `--tool-opt <option>` | Pass an option to the J-Link tools |

`west debugserver -r jlink ...` starts only the GDB Server, on port 2331 in the container. The VS Code profiles in [`.vscode/launch.json`](../.vscode/launch.json) belong to the host GDB Server route on the board page and are not set up for this container.

## Not covered

- Images that run from SDRAM, which need a J-Link script that sets up SDRAM before loading. No such script exists in Crux.
- Docker Desktop, which handles USB devices differently.
- VS Code debug profiles for a GDB Server inside the board container.
