# RT1060-EVKB with J-Link, usbipd and west

Status: **documented, not run.** No step of this route has run on hardware, on Windows, with usbipd-win or with the board Dev Container. CI checks only that the container files parse and keep their safety properties ([`tests/build/test_jlink_board_container.py`](../tests/build/test_jlink_board_container.py)). The first check to run is [section 6](#6-first-check-on-a-windows-pc).

This guide is the standard board route for the RT1060-EVKB QSPI target (`mimxrt1060_evk@B//qspi`): the SEGGER J-Link probe is attached to Linux (to WSL2 with usbipd-win on Windows), the J-Link software runs inside an optional board Dev Container, and Zephyr's own `west flash`, `west debug` and `west attach` drive it through the J-Link runner. [ADR-0007](decisions/0007-west-flash-and-debug-for-people-and-automation.md) records the decision and its conditions.

**Before any step that touches the board**, read the conditions. Each physical operation needs explicit authorisation for the current task ([AGENTS.md](../AGENTS.md)): flashing, resetting, attaching a debugger and starting a debug session are all physical operations, and attaching may halt the target. Nothing in CI flashes or attaches to a board. The [device-control tool](../tools/device_control/README.md) and its gates are unchanged and separate from this route. Confirm the board, the probe, the image and a recovery plan first.

## 1. What you need

- A RT1060-EVKB (QSPI) and a SEGGER J-Link probe on SWD.
- The repository set up as [Getting started](getting-started.md) describes: on Windows, the clone inside the WSL2 file system and Docker Engine inside WSL2 (this guide does not cover Docker Desktop).
- The SEGGER J-Link software package for Linux, the 64-bit x86 Debian file `JLink_Linux_<version>_x86_64.deb`, downloaded by you from SEGGER after accepting its licence. The Zephyr runner applies the board's QSPI flash loader only with J-Link software 7.70d or newer.
- The Zephyr workspace bootstrapped with `scripts/bootstrap-zephyr.sh`. It installs Zephyr's Python requirements, including `pylink-square`, which the J-Link runner uses to read the J-Link version.

## 2. Attach the probe to Linux

**On Windows**, install usbipd-win once, from a PowerShell window:

~~~powershell
winget install --exact --id dorssel.usbipd-win
~~~

Then find the probe and share it. `bind` needs an administrator PowerShell and is needed once per device; `attach` runs in a normal PowerShell and is needed again after the probe is replugged or WSL2 restarts:

~~~powershell
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID>
~~~

`usbipd list` shows the J-Link with USB vendor ID `1366`. While the probe is attached to WSL2, Windows tools such as J-Flash or a Windows GDB Server cannot see it. `usbipd detach --busid <BUSID>` gives it back to Windows.

**On native Linux** no usbipd is needed: the probe is already a Linux USB device.

**On the Linux side** (the WSL2 distribution, or the native Linux machine), give the `plugdev` group access to J-Link probes with the rule in [`.devcontainer/jlink/99-crux-jlink.rules`](../.devcontainer/jlink/99-crux-jlink.rules). From the repository checkout:

~~~sh
sudo cp .devcontainer/jlink/99-crux-jlink.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
~~~

On WSL2 the udev rules apply only when the distribution runs systemd, which is the default for current Ubuntu distributions (`[boot] systemd=true` in `/etc/wsl.conf`). Check the result after attaching:

~~~sh
lsusb -d 1366:                         # needs the usbutils package on the Linux side
ls -l /dev/bus/usb/*/*                 # the J-Link node shows group plugdev and crw-rw----
getent group plugdev                   # 46 on Debian and Ubuntu, the same ID as in the container
~~~

If the group ID on the Linux side is not 46, the container user cannot open the probe through the group. Use `MODE="0666"` in a local copy of the rule instead, which lets every local user of that Linux system open J-Link probes.

## 3. The board Dev Container

The board container is a second Dev Container configuration, [`.devcontainer/jlink/devcontainer.json`](../.devcontainer/jlink/devcontainer.json). The default container is unchanged for people without a board: it mounts no USB devices and installs no J-Link software.

The board container reuses the default [Dockerfile](../.devcontainer/Dockerfile) and sets the build argument `CRUX_JLINK=1`, which runs [`install-jlink.sh`](../.devcontainer/jlink/install-jlink.sh). It differs from the default container in three ways:

- It installs the J-Link package from `.devcontainer/jlink/packages/` and `usbutils`, and adds the `vscode` user to `plugdev`. The build never downloads the package and stops if the folder does not hold exactly one `JLink_Linux_*_x86_64.deb`. To pick one of several, set `CRUX_JLINK_DEB` to its file name in the `build.args` of a local copy of the configuration. To pin a package, set `CRUX_JLINK_DEB_SHA256`; the build prints the SHA-256 of the package either way.
- It bind-mounts the host's `/dev/bus/usb` and allows only USB character devices (`--device-cgroup-rule=c 189:* rmw`, major number 189). It does not use `--privileged`. Because the whole USB tree is mounted, the probe stays reachable after it re-enumerates, for example after a reset or a new `usbipd attach`.
- Its name is **Crux Pilot board, J-Link**. It uses the same workspace mount, cache volume, environment and limits as the default container.

To use it:

1. Put the J-Link package in [`.devcontainer/jlink/packages/`](../.devcontainer/jlink/packages/README.md). Git ignores it.
2. Attach the probe first ([section 2](#2-attach-the-probe-to-linux)). Docker refuses to start the container if `/dev/bus/usb` does not exist on the Linux side, which can happen in WSL2 before any USB device is attached.
3. In VS Code, run **Dev Containers: Reopen in Container** and choose **Crux Pilot board, J-Link**. With two configurations VS Code asks which one to use.
4. In the container, check that the probe is visible and the J-Link tools are installed:

   ~~~sh
   lsusb -d 1366:
   id -nG                                 # includes plugdev
   command -v JLinkExe JLinkGDBServer
   ~~~

The Dockerfile copies `.devcontainer/jlink/` into every image build, including the default container's, and deletes it in the next step. A package left in `packages/` therefore enlarges a default image that is rebuilt while it is there, without installing anything.

## 4. Read-only check: attach and compare

Do this before the first write on a new set-up, and whenever you are not sure which image is on the board. It confirms the connection and that the image on the board matches an ELF, without writing to flash. It is still a physical operation: the GDB Server halts the target while the debugger is attached.

Build the ELF that should match the board, or use the ELF that was flashed. For the Time sample:

~~~sh
scripts/build-debug-target.sh 'mimxrt1060_evk@B//qspi'
~~~

Then attach with the J-Link runner. `-r jlink` is required: for this board Zephyr's default runner is LinkServer.

~~~sh
west attach -d build/zephyr/mimxrt1060_evk_B_qspi -r jlink --speed 400
~~~

`west attach` starts the J-Link GDB Server in the container and connects GDB to it. Unlike `west debug`, it does not reset the target or load the image. At the GDB prompt:

~~~text
(gdb) compare-sections
(gdb) detach
(gdb) quit
~~~

Every loadable section should report `matched`. A mismatch means the board holds a different image than this ELF, not that the route is broken.

## 5. Flash and debug

Only with authorisation for the current task that names the operation and the image.

~~~sh
west flash -d build/zephyr/mimxrt1060_evk_B_qspi -r jlink --speed 400
west debug -d build/zephyr/mimxrt1060_evk_B_qspi -r jlink --speed 400
~~~

- `west flash` runs J-Link Commander with the device `MIMXRT1062xxx6A` and the board's QSPI loader `BankAddr=0x60000000&Loader=QSPI` (both from Zephyr's `boards/nxp/mimxrt1060_evk/board.cmake`), loads the image and starts the CPU. It does not mass-erase the flash unless `--erase` is given; do not give it.
- `west debug` starts the GDB Server and GDB, then halts, resets and **loads the image**: it writes to flash. Use `west attach` to debug an image that is already on the board.
- `west debugserver -r jlink ...` starts only the GDB Server, on port 2331 in the container. The VS Code profiles in [`.vscode/launch.json`](../.vscode/launch.json) connect to `host.docker.internal:2331` for the fallback route below and are not set up for this one.

Common options of the J-Link runner:

| Option | Use |
| --- | --- |
| `--speed <kHz>` | SWD speed. The runner's default is `auto`. The recorded value that worked on the EVKB is 400 kHz, and 100 kHz on a first connection. One board also connected at 4000 kHz, J-Link's usual default. The existing launcher uses 400 |
| `-i <serial>`, `--dev-id <serial>` | Select a probe by its serial number when more than one is attached. `lsusb -v -d 1366:` shows it as `iSerial` |
| `-O <option>`, `--tool-opt <option>` | Pass an option to the J-Link tools |

## 6. First check on a Windows PC

A short procedure for the first run of this route, on a Windows PC with WSL2 and Docker Engine in WSL2. It writes nothing to the board, so no image is flashed: it assumes the board already holds a Time sample image whose ELF is available (in the earlier GDB Server check, `compare-sections` matched all sections of such an image). It still attaches to the board, which may halt it, so it needs your authorisation for the task. Stop at the first step that does not give the expected result, record it, and do not continue with a write.

Before you start: close every Windows J-Link tool and GDB Server, and put the J-Link `.deb` in `.devcontainer/jlink/packages/`.

| # | Where | Command or action | Expected |
| --- | --- | --- | --- |
| 1 | PowerShell, administrator | `winget install --exact --id dorssel.usbipd-win`, then `usbipd list` | The J-Link is listed with VID `1366`. Note its BUSID |
| 2 | PowerShell, administrator | `usbipd bind --busid <BUSID>` | No error. `usbipd list` shows the device as shared |
| 3 | PowerShell | `usbipd attach --wsl --busid <BUSID>` | No error. `usbipd list` shows it attached |
| 4 | WSL2 shell | `lsusb -d 1366:` | One SEGGER J-Link line |
| 5 | WSL2 shell, repository checkout | The three udev commands of [section 2](#2-attach-the-probe-to-linux), then `ls -l /dev/bus/usb/*/*` and `getent group plugdev` | The J-Link node has group `plugdev` and `crw-rw----`. `plugdev` is 46 |
| 6 | VS Code | **Dev Containers: Reopen in Container**, choose **Crux Pilot board, J-Link** | The image builds. The log prints `J-Link package: <file>, SHA-256 <hash>` |
| 7 | Board container | `lsusb -d 1366:`, `id -nG`, `command -v JLinkExe JLinkGDBServer` | The J-Link is listed, `plugdev` is among the groups, both tools are found |
| 8 | Board container | The ELF of the image on the board: reuse it, or build it from the same revision with `scripts/build-debug-target.sh 'mimxrt1060_evk@B//qspi'` | `build/zephyr/mimxrt1060_evk_B_qspi/zephyr/zephyr.elf` exists |
| 9 | Board container | `west attach -d build/zephyr/mimxrt1060_evk_B_qspi -r jlink --speed 400` | The GDB Server connects to the target and GDB stops at a prompt |
| 10 | GDB prompt | `compare-sections`, then `detach` and `quit` | Every section reports `matched`. The board runs again after `detach` |
| 11 | PowerShell | `usbipd detach --busid <BUSID>` | The probe is back on Windows |

If step 9 cannot connect, retry once with `--speed 100`. If step 6 or 7 fails, the default container still works: reopen it with **Crux Pilot (Ubuntu 24.04 amd64)**. Record the results in the pull request or issue for this route, with the J-Link software version, the usbipd-win version and the speed used.

## 7. Fallback: J-Link GDB Server on the host

The earlier route stays available: the J-Link GDB Server runs on the host, outside the container, and GDB in the default container connects to it over TCP port 2331 through the VS Code profiles. On macOS it is the recorded route ([build guide](build.md#rt1060-evkb-debugging)). On Windows it needs the GDB Server opened to remote connections (`-localhostonly 0`), a firewall rule limited to the WSL2 subnet and a `host.docker.internal` entry in the container, which is more steps and more network exposure than the route above.

## 8. Not covered yet

- **Images that run from SDRAM.** They need a J-Link script that sets up SDRAM before loading, which can be passed to the runner with `--tool-opt`. Not tried, and no such script exists in Crux (the [build guide](build.md#what-the-platform-provides-for-build-and-debug) lists it as owned by the project).
- **Docker Desktop**, which handles USB devices differently.
- **VS Code debug profiles** for a GDB Server inside the board container.
