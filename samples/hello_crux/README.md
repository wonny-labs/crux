# Hello Crux

## Overview

The smallest application that uses Crux. It shows how a product application reaches the platform:

- The application is an ordinary Zephyr application. Crux is a **Zephyr module** in the west workspace, found
  like any other module.
- A **Kconfig symbol** (`CONFIG_CRUX_TIME=y` in [`prj.conf`](prj.conf)) tells the module to build a component and
  its Zephyr provider.
- The application links the component's **public usage target** (`crux::time` in
  [`CMakeLists.txt`](CMakeLists.txt)) and includes its **public header** (`<crux/time.h>`). It never names a Crux
  source file, a port or a private include directory. That line is the consumer boundary.

The program makes one public read after initialisation: it prepares Crux Time and reads the realtime clock. Right after start the clock
is ready but unset, because Crux never invents a time of day, so the sample prints `unset`.

The same portable source, [`src/hello_crux.c`](src/hello_crux.c), also builds on the Linux Host composition. The
[`host/`](host/CMakeLists.txt) program is a separate CMake project that consumes Crux from its source tree, as an
external Linux application does. There, `crux_assert_portable_consumer()` fails the configure step if the build
requirements of the portable target (include directories, compile options, linked targets) name a native or vendor
path, a private Crux directory or a provider or composition target. It checks the build graph only, not the
source's `#include` lines; those stay a review matter.

| Part | Folder | Runs on |
| --- | --- | --- |
| Zephyr application | this folder (`CMakeLists.txt`, `prj.conf`, `src/`, `sample.yaml`) | `native_sim/native/64` |
| Linux Host program | [`host/`](host/CMakeLists.txt), its own CMake project | The Linux Host composition |

Crux has no version API, so the sample prints no Crux version.

## Requirements

- The west workspace and Zephyr SDK of the [Build and Integration Guide](../../docs/build.md), for example the Dev
  Container after `scripts/bootstrap-zephyr.sh`.
- For the Host program: Linux with CMake 3.28 or later, Ninja and a C compiler. The Host composition is a
  development and test composition and does not build on macOS.

No board is needed.

## Building and running

From the west workspace root (`/workspace` in the Dev Container), where `crux-pilot` is this repository:

```sh
west build -p always -b native_sim/native/64 -d build/hello_crux crux-pilot/samples/hello_crux -t run
```

The Linux Host program, from `crux-pilot`:

```sh
cmake -S samples/hello_crux/host -B build/samples/hello_crux_host -G Ninja -DCRUX_SOURCE_DIR="$PWD"
cmake --build build/samples/hello_crux_host
build/samples/hello_crux_host/hello-crux-host
```

`scripts/test-hello-crux.sh` runs both and checks their output (`--host` or `--zephyr` for one of them). Twister runs
the Zephyr application from [`sample.yaml`](sample.yaml):

```sh
west twister -T crux-pilot/samples/hello_crux -p native_sim/native/64
```

## Sample output

Zephyr on `native_sim` (after the Zephyr boot banner):

```text
Hello from Crux on zephyr
Crux Time: unset
CRUX_HELLO_READY composition=zephyr
```

The Zephyr program returns from `main`, but `native_sim` keeps running; stop it with Ctrl+C.

Linux Host:

```text
Hello from Crux on host
Crux Time: unset
CRUX_HELLO_READY composition=host
```

## Next steps

- [`samples/file/file_write_read`](../file/file_write_read/README.md) selects a File provider by build
  configuration alone.
- [`samples/time/utc_clock_shell`](../time/utc_clock_shell/README.md) reads and sets the UTC clock from shell
  commands on both compositions.
- [`templates/product`](../../templates/product/README.md) is the shape of a product repository on Crux.
