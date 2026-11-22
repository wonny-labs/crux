# EVKB integration probe images

Zephyr images for the RT1060-EVK Rev B that check device input, networking, diagnostics and health together. They
are test images: nothing here is a sample, and nothing in this repository programs, resets or talks to the board
(`scripts/test-controller-integration.sh` builds them and runs the `native_sim` checks). They were part of
`samples/controller`; the periodic scenario that folder also held is now [`tests/time_periodic`](../../time_periodic/README.md).
The Kconfig symbols still carry the old `CRUX_CONTROLLER_M3` and `CRUX_M3_*` names; renaming them (with the Zephyr
patch that reads them) is a separate change.

## Configurations

Each image is selected by a configuration file of this folder, composed in `scripts/test-controller-integration.sh`:

| File | Selects |
| --- | --- |
| `device_health_probe.conf` | SW5 GPIO and critical-work supervision, with test commands |
| `without_test_commands.conf` | Removes the shell and fault-injection commands |
| `network_probe.conf` | Bounded IPv4 TCP/UDP transactions |
| `integrated.conf` | Time, SW5, network, diagnostics and health together |
| `mdio_completion_fix.conf` | The ENET MDIO completion patch |
| `mdio_failure_trace.conf` | MDIO failure tracing |
| `phy_diagnostic.conf` | PHY diagnostics |
| `deferred_output.conf` | Deferred console output |
| `native_output.conf` | Native console output |

`probe_main.c` is the entry point of the device and integrated images; `network_probe.c` is that of the network
probe. The EVKB network overlay is shared with the board samples:
[`samples/boards/nxp/mimxrt1060_evk/common/network.overlay`](../../../samples/boards/nxp/mimxrt1060_evk/common/network.overlay).
These are separately selected configurations, not features executed by every build. The normal integrated image
disables development test commands and does not start network traffic or arm the watchdog.

## Device and health probe

This separate diagnostic composition uses native GPIO for the onboard
`sw0` input and observes actual critical-worker completion before allowing a
watchdog feed. It adds no Crux public interface. The basic periodic scenario and its finite UTC-step behaviour remain available.

From the documented Linux workspace, run
`scripts/test-controller-integration.sh` for the three
`native_sim` GPIO/health scenarios, native-client socket controls and EVKB
health probe/normal/network cross-builds. Outputs are
under `build/zephyr/twister-m3`, `m3-probe-evkb`, `m3-normal-evkb` and
`m3-network-evkb`; frozen inputs
are retained at `build/evidence/m3-inputs.json`. This command performs no hardware
operation. Host checks also exercise the portable readiness/freshness helper.

For a manual build in that environment:

```sh
west build -p always -b 'mimxrt1060_evk@B//qspi' \
  -d build/zephyr/m3-probe-evkb tests/board_images/integration_probe -- \
  -DZEPHYR_EXTRA_MODULES="$PWD" \
  -DEXTRA_CONF_FILE="$PWD/tests/board_images/integration_probe/device_health_probe.conf"
```

The development probe exposes `m3 status`, `m3 arm` and `m3 stall`. Arm is an
explicit physical watchdog operation and stall deliberately stops critical work;
use them only under the independently reviewed physical/recovery plan. Ordinary
boot does neither. Add `m3-normal.conf` after `m3.conf` (semicolon-separated in
`EXTRA_CONF_FILE`) for a normal image without Shell/test commands.

`M3_WORK` reports input read status and an unset/valid Time status. The standalone
health probe retains its `M3_PENDING` diagnostic and is not the qualified integrated
composition. The accepted physical results combine actual SW5, Ethernet and integrated-
controller evidence. See [the validation record](../../../docs/m3-validation.md)
for identified firmware, tests, previous failures and support limits.

## Network probe

`m3-network.conf` and `m3-network.overlay` select a separate native IPv4 client.
Do not combine them with the independent health configuration. The overlay removes
LED ownership of GPIO1.9 so PHY reset retains that pin, and selects local test MAC
02:43:52:55:58:03. It uses EVKB 192.168.77.2/24 and Mac 192.168.77.1/24, with no
DHCP, gateway or DNS. This configuration is for a direct isolated cable only.
Confirm actual interface, MAC, cabling and current physical gate before execution.
Successful cross-builds and instrumented native tests do not qualify real Ethernet.

The Shell command `m3net` requests one round: ten framed TCP exchanges to port 42420,
then ten UDP datagrams to port 42421. Each exchange has one monotonic 2 s deadline.
Partial TCP transfers retain that deadline; UDP requires an exact 32-byte response
from the connected peer, including trial/sequence and fixed payload. The same
owner closes each socket before the next transaction. A close failure retains
uncertain ownership and prevents further rounds. The probe accepts at most seven
rounds: one baseline and three failure/recovery pairs. It sends no traffic at boot.

For the Mac peer, after the separate reviewed physical/network gate:

```sh
python3 tests/target/m3_network_peer.py --mode echo --duration 60 --output peer.jsonl
```

The peer binds only 192.168.77.1, accepts only 192.168.77.2, and closes its sockets
at its declared duration or 200 events. `--mode silence` withholds responses;
`--mode close` closes TCP after receiving its frame and withholds UDP. Output files
must be new. Logs identify receive/response facts and correlated trial/sequence.
No listener should be exposed to shared networks; payloads contain no credentials
or sensitive data. Remove the validation configuration to remove the Shell/client
entry point. This is a test boundary, not production protocol/security approval.

`M3_NET_STATE` distinguishes carrier, configured address and service success.
Restored carrier alone cannot restore service readiness: a complete successful
explicit round is required. `M3_NET_RESOURCE` reports application ownership and
native context/pkt/buffer availability. These observations do not establish
leak-free operation beyond the tested conditions. Qualified network and integrated
controller results are recorded in [the validation record](../../../docs/m3-validation.md).

## Integrated controller configuration

The tested integrated scenario combines actual SW5 GPIO observations, serialised
Time access, bounded IPv4 TCP/UDP exchanges, UART diagnostics, service-readiness
observations and health supervision of the critical Time/GPIO and network owners.
The network window, fault injection and watchdog arming are deliberate development
test operations, not automatic startup behaviour. The normal configuration disables
test Shell commands and leaves watchdog arming and network traffic off at boot.

`scripts/test-controller-integration.sh` runs the applicable Twister/native
simulation and build-only
checks, including the integrated EVKB probe and normal profiles. This script does
not flash, reset or communicate with hardware. It produces images under
`build/zephyr/m3-integrated-{probe,normal}-evkb/`. Physical operation requires a
separately authorised procedure, verified firmware/configuration and the isolated
network fixture. See [M3 validation and final acceptance](../../../docs/m3-validation.md)
for the tested composition, required settings, results and restrictions.

The target evidence covers the identified RT1062 EVKB revision B/QSPI, its SW5
path and isolated Ethernet peer. It does not qualify other GPIO/I2C/SPI/EEPROM
paths, production networking, worst-case resource/timing behaviour or
long-duration concurrent-load scenarios. The Linux host continues to exercise the portable
scenario and shared health logic, not the EVKB-specific device/network composition.

The qualified integrated build explicitly selects the
[opt-in native MDIO correction](../../../patches/zephyr/README.md). Its pinned-source
and RT1062 composition limits remain applicable; the ordinary uncorrected network
probe build is not qualified by the corrected profile's physical results.
