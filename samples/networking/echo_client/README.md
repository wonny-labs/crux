# Echo client

## Overview

One echo client, two compositions. The client in [`common/client.c`](common/client.c) uses only the standard socket
profile of the [Networking contract](../../../docs/networking-contract.md): it sends a 32-byte message over TCP or UDP
and checks the echo. Each composition prints the Crux Netif status, then exchanges one TCP echo (port 42420) and one
UDP echo (port 42421) with a peer, and exits with status 0 only when both succeed. This sample was at
`samples/networking/` (with `zephyr/`, `host/` and `client.*`) before the samples layout change.

| Part | Folder | Runs on |
| --- | --- | --- |
| Zephyr application | this folder (`CMakeLists.txt`, `prj.conf`, `src/`, `sample.yaml`) | `mimxrt1060_evk@B//qspi` only, on an isolated network with a peer at `192.168.77.1`; the board takes `192.168.77.2/24` |
| Linux Host program | [`host/`](host/main.c), built by the repository's root `CMakeLists.txt` | The Linux Host build; peer `127.0.0.1` by default, or a numeric IPv4 address as its argument |
| Echo client | [`common/`](common/client.h) | Compiled by both parts and by the tests `tests/networking` and `tests/networking_zephyr` |

## Requirements

- Linux Host: the Host build from `scripts/bootstrap-host.sh` or `scripts/check-host.sh`.
- Zephyr: the west workspace from `scripts/bootstrap-zephyr.sh`. Running the image needs an EVKB, an isolated
  network and an echo peer; programming a board is a separate, approved procedure (see the
  [Build and Integration Guide](../../../docs/build.md)).

## Building and running

Linux Host, with an echo peer listening on ports 42420 and 42421:

```sh
build/linux/debug/samples/networking/echo_client/host/crux-networking-host [numeric-ipv4]
```

CTest `Sample.EchoClientHost` (`ctest --preset host-debug -L sample`) starts a local echo peer on `127.0.0.1` through
`scripts/run-host-sample.py --echo-peer` and checks the output.

Zephyr, cross-build only, as `scripts/test-networking.sh` does it (build directory `build/zephyr/networking-evkb`):

```sh
west build -b 'mimxrt1060_evk@B//qspi' -d build/zephyr/networking-evkb crux-pilot/samples/networking/echo_client -- \
    -DDTC_OVERLAY_FILE=$PWD/crux-pilot/samples/boards/nxp/mimxrt1060_evk/common/network.overlay
```

On the EVKB, `CMakeLists.txt` also applies the ENET MDIO completion correction from
`tests/board_images/integration_probe/mdio_completion.cmake` without changing the Zephyr checkout. Twister id
`crux.sample.networking.echo_client` in [`sample.yaml`](sample.yaml) runs the image only when the
`crux_echo_peer` fixture is supplied; otherwise Twister only builds it.

## Sample output

```text
NETIF admin=1 link=2 address=1
NETWORK tcp=0 udp=0
```

`link=2` is `CRUX_NETIF_LINK_UP`. A negative `tcp` or `udp` value is the symbolic errno of the failed exchange.
