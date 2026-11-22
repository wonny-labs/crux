# File write and read

## Overview

Writes a short text to a file through the Crux File API and reads it back. The sample shows **provider selection
by build configuration**: two builds of the same application source use two different File providers and file
systems, and only the Kconfig fragment and the devicetree overlay differ.

| Scenario | Selected by | File provider | Storage |
| --- | --- | --- | --- |
| `crux.sample.file.write_read.simulator` (default) | [`prj.conf`](prj.conf), [`app.overlay`](app.overlay) | `CONFIG_CRUX_FILE_SIMULATOR` | LittleFS on a partition of the `native_sim` flash simulator |
| `crux.sample.file.write_read.fatfs_ram_disk` | adds [`fatfs_ram_disk.conf`](fatfs_ram_disk.conf), [`fatfs_ram_disk.overlay`](fatfs_ram_disk.overlay) | `CONFIG_CRUX_FILE_FATFS_SIMULATOR` | FatFs on a 1 MiB RAM disk |

**Both providers are simulator candidates** (their status is in [component readiness](../../../docs/component-readiness.md)). `zephyr/Kconfig` calls them that too. They exist for software-only
validation on `native_sim`, and this sample is their first consumer outside the tests. Neither is a product storage
choice, and nothing here says anything about power loss or a real medium.

The source is split the way a product splits it:

- **Application**: [`src/write_read.c`](src/write_read.c) uses only `<crux/file.h>` and links only `crux::file`. It
  does not know which provider or file system the build selected. `crux_assert_portable_consumer()` in
  [`CMakeLists.txt`](CMakeLists.txt) fails the configure step if the target's build requirements (include
  directories, compile options, linked targets) name a native or vendor path, a private Crux directory or a provider
  or composition target. It does not read the `#include` lines; those stay a review matter.
- **Platform composition**: [`src/storage_littlefs.c`](src/storage_littlefs.c) or
  [`src/storage_fatfs_ram_disk.c`](src/storage_fatfs_ram_disk.c) mounts the file system with Zephyr's API, formats
  the blank simulated medium, creates a `files` directory and binds it as the File root with
  `crux_file_zephyr_bind()` from `<crux/file_zephyr.h>` (target `crux::file_zephyr`). The File provider itself never
  mounts or formats. `CMakeLists.txt` compiles the file that matches the selected provider.
- [`src/main.c`](src/main.c) runs the composition step, then the application, and prints the result.

## Requirements

The west workspace and Zephyr SDK of the [Build and Integration Guide](../../../docs/build.md), for example the Dev
Container after `scripts/bootstrap-zephyr.sh`. No board is needed; both scenarios run on `native_sim/native/64` only.

## Building and running

From the west workspace root (`/workspace` in the Dev Container), where `crux-pilot` is this repository.

Default scenario (simulator provider on LittleFS):

```sh
west build -p always -b native_sim/native/64 -d build/write_read crux-pilot/samples/file/write_read -t run
```

FatFs on a RAM disk: the same command with the scenario's Kconfig fragment and overlay:

```sh
west build -p always -b native_sim/native/64 -d build/write_read_fatfs \
    crux-pilot/samples/file/write_read -t run -- \
    -DEXTRA_CONF_FILE=fatfs_ram_disk.conf -DEXTRA_DTC_OVERLAY_FILE=fatfs_ram_disk.overlay
```

The program returns from `main`, but `native_sim` keeps running; stop it with Ctrl+C. Twister builds and runs both
scenarios from [`sample.yaml`](sample.yaml) and checks their output:

```sh
west twister -T crux-pilot/samples/file/write_read -p native_sim/native/64
```

`scripts/test-hello-crux.sh --zephyr` runs this sample together with `hello_crux`.

## Sample output

Default scenario (after the Zephyr boot banner):

```text
Storage: LittleFS on the flash simulator, bound at /lfs/files
Wrote 25 bytes to greeting.txt
Read 25 bytes: Hello from Crux File API!
CRUX_FILE_WRITE_READ_OK provider=simulator
```

FatFs on a RAM disk:

```text
Storage: FatFs on a RAM disk, bound at /RAM:/files
Wrote 25 bytes to greeting.txt
Read 25 bytes: Hello from Crux File API!
CRUX_FILE_WRITE_READ_OK provider=fatfs_ram_disk
```

The application lines are the same in both: only the composition line and the provider name differ.

## See also

- The [File contract](../../../docs/file-contract.md) for what the File API promises, and the
  [File root binding](../../../docs/file-composition-interface.md) for `crux::file_zephyr` and its rules.
- [`samples/hello_crux`](../../hello_crux/README.md) for the consumer boundary in its smallest form.
