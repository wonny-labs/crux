# File write and read

## Overview

Writes a short text to a file through the Crux File API and reads it back. The sample shows **provider selection
by build configuration**: two builds of the same application source use two different File providers and file
systems, and only the Kconfig fragment and the devicetree overlay differ.

| Scenario | Selected by | File provider | Storage |
| --- | --- | --- | --- |
| `crux.sample.file.basic.simulator` (default) | [`prj.conf`](zephyr/prj.conf), [`app.overlay`](zephyr/app.overlay) | `CONFIG_CRUX_FILE_SIMULATOR` | LittleFS on a partition of the `native_sim` flash simulator |
| `crux.sample.file.basic.fatfs_ram_disk` | adds [`fatfs_ram_disk.conf`](zephyr/fatfs_ram_disk.conf), [`fatfs_ram_disk.overlay`](zephyr/fatfs_ram_disk.overlay) | `CONFIG_CRUX_FILE_FATFS_SIMULATOR` | FatFs on a 1 MiB RAM disk |

Both providers are for software-only checks on `native_sim`. Neither is a product storage choice, and nothing here says anything about power loss or a real medium.

The source is split the way a product splits it:

- **Application**: [`common/basic.c`](common/basic.c) uses only `<crux/file.h>` and links only `crux::file`. It
  does not know which provider or file system the build selected. [`zephyr/CMakeLists.txt`](zephyr/CMakeLists.txt) checks that boundary with `crux_assert_portable_consumer()` (see [`hello_crux`](../../hello_crux/README.md)).
- **Platform composition**: [`zephyr/src/storage_littlefs.c`](zephyr/src/storage_littlefs.c) or
  [`zephyr/src/storage_fatfs_ram_disk.c`](zephyr/src/storage_fatfs_ram_disk.c) mounts the file system with Zephyr's API, formats
  the blank simulated medium, creates a `files` directory and binds it as the File root with
  `crux_file_zephyr_bind()` from `<crux/file_zephyr.h>` (target `crux::file_zephyr`). The File provider itself never
  mounts or formats. `zephyr/CMakeLists.txt` compiles the file that matches the selected provider.
- [`zephyr/src/main.c`](zephyr/src/main.c) runs the composition step, then the application, and prints the result.

## Requirements

The west workspace and Zephyr SDK of the [Build and Integration Guide](../../../docs/build.md), for example the Dev
Container after `scripts/bootstrap-zephyr.sh`. No board is needed; both scenarios run on `native_sim/native/64` only.

## Building and running

From the repository root (`/workspace/crux-pilot` in the Dev Container).

Default scenario (simulator provider on LittleFS):

```sh
west build -p always -b native_sim/native/64 -d build/basic samples/file/basic/zephyr -t run
```

FatFs on a RAM disk: the same command with the scenario's Kconfig fragment and overlay:

```sh
west build -p always -b native_sim/native/64 -d build/basic_fatfs \
    samples/file/basic/zephyr -t run -- \
    -DEXTRA_CONF_FILE=fatfs_ram_disk.conf -DEXTRA_DTC_OVERLAY_FILE=fatfs_ram_disk.overlay
```

The program returns from `main`, but `native_sim` keeps running; stop it with Ctrl+C. Twister builds and runs both
scenarios from [`zephyr/sample.yaml`](zephyr/sample.yaml) and checks their output:

```sh
west twister -T samples/file/basic -p native_sim/native/64
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
