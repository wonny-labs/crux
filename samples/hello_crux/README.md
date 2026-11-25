# Hello Crux

## Overview

The smallest application that uses Crux. It shows how a product application reaches the platform:

- The application is an ordinary Zephyr application. Crux is a **Zephyr module** in the west workspace, found
  like any other module.
- The application links a **public usage target** (`crux::base` in [`CMakeLists.txt`](CMakeLists.txt)) and
  includes its **public header** (`<crux/version.h>`). It never names a Crux source file, a port or a private
  include directory. That line is the consumer boundary.

The program prints the Crux version from that header, with the output facility of its operating system:
`printk` on Zephyr, `printf` on the Linux Host.

The [`host/`](host/CMakeLists.txt) program is a separate CMake project that consumes Crux as an external application does;
`crux_assert_portable_consumer()` checks its build boundary ([Build and Integration Guide](../../docs/build.md#external-linux-application-using-crux-source)).

| Part | Folder | Runs on |
| --- | --- | --- |
| Zephyr application | this folder (`CMakeLists.txt`, `prj.conf`, `src/`, `sample.yaml`) | `native_sim/native/64`; cross-built for the MIMXRT1060-EVKB (`mimxrt1060_evk@B//qspi`) |
| Linux Host program | [`host/`](host/CMakeLists.txt), its own CMake project | The Linux Host composition |

## Requirements

- The west workspace and Zephyr SDK of the [Build and Integration Guide](../../docs/build.md), for example the Dev
  Container after `scripts/bootstrap-zephyr.sh`.
- For the Host program: Linux with CMake 3.28 or later, Ninja and a C compiler. The Host composition is a
  development and test composition and does not build on macOS.

No board is needed. On the EVKB the same source and `prj.conf` print on the board's console UART; [Part C of the Tutorial](../../docs/tutorial.md#part-c-run-on-your-board) flashes it.

## Building and running

From the repository root (`/workspace/crux-pilot` in the Dev Container):

```sh
west build -p always -b native_sim/native/64 -d build/hello_crux samples/hello_crux -t run
```

The Linux Host program:

```sh
cmake -S samples/hello_crux/host -B build/samples/hello_crux_host -G Ninja -DCRUX_SOURCE_DIR="$PWD"
cmake --build build/samples/hello_crux_host
build/samples/hello_crux_host/hello-crux-host
```

`scripts/test-hello-crux.sh` runs both and checks their output (`--host` or `--zephyr` for one of them). Twister runs
the Zephyr application from [`sample.yaml`](sample.yaml):

```sh
west twister -T samples/hello_crux -p native_sim/native/64
```

## Sample output

The version is the one in `<crux/version.h>` of your checkout. Zephyr on `native_sim` (after the Zephyr boot banner):

```text
Hello from Crux 0.1.0-dev on zephyr
CRUX_HELLO_READY composition=zephyr
```

The Zephyr program returns from `main`, but `native_sim` keeps running; stop it with Ctrl+C.

Linux Host:

```text
Hello from Crux 0.1.0-dev on host
CRUX_HELLO_READY composition=host
```

## Next steps

- [`samples/time/shell`](../time/shell/README.md) uses a component that Kconfig enables
  (`CONFIG_CRUX_TIME`), links its usage target `crux::time` and compiles one portable command source
  on both compositions.
- [`samples/file/basic`](../file/basic/README.md) selects a File provider by build
  configuration alone, with application code that uses only the portable File API.
- [`templates/product`](../../templates/product/README.md) is the shape of a product repository on Crux.
