# Kit module template: integrity check

Two reference files for a Zephyr module that compiles a vendor kit. They implement the kit integrity check and the kit path rule of [Vendor kits across repositories](../../docs/vendor-kits.md). They are a template, not a Crux interface, and a recommended convention that is Experimental. The kit `kit-a`, the variable `KIT_A_PATH` and the prefix `acmeco` are invented.

**Status: tested in CMake script mode and with Python only.** `tests/build/test_vendor_kit_template.py` runs both files on invented kit trees. Neither has run inside a Zephyr build.

| File | Purpose |
| --- | --- |
| `kit_hashes.py` | Writes the hash list of a kit tree, and names the committed list that a tree matches. Python 3.9 or later, standard library only |
| `kit_integrity.cmake` | `kit_integrity_check()`, called at configure time: chooses the kit path, refuses overrides in a release build, runs the check and prints the line and delivery it matched |

## Use it in a kit module

Copy both files into the module, for example to `cmake/`, and commit one hash list per accepted tree:

```text
kit-a-module/
  CMakeLists.txt
  Kconfig
  cmake/kit_hashes.py
  cmake/kit_integrity.cmake
  kit-hashes/1.x/1.1.0.sha256
  kit-hashes/1.x/1.1.1.sha256
  kit-hashes/2.x/2.0.0.sha256
  zephyr/module.yml
```

Write a list from a delivery as received, in an empty directory with the delivery unpacked:

```sh
python3 kit-a-module/cmake/kit_hashes.py generate delivery-1.1.1 > kit-a-module/kit-hashes/1.x/1.1.1.sha256
```

Call the check in the module's `CMakeLists.txt`, before any kit source is added:

```cmake
include(${CMAKE_CURRENT_LIST_DIR}/cmake/kit_integrity.cmake)
kit_integrity_check(NAME kit-a ENV_VAR KIT_A_PATH
  DEFAULT_PATH ${ZEPHYR_KIT_A_MODULE_DIR}
  HASH_DIR ${CMAKE_CURRENT_LIST_DIR}/kit-hashes
  EXPECT_LINE ${CONFIG_ACMECO_KIT_A_LINE})
# Then add sources from ${KIT_INTEGRITY_PATH}.
```

`ZEPHYR_KIT_A_MODULE_DIR` exists when the kit carries a `zephyr/module.yml` named `kit-a`. Otherwise pass the kit's west project path.

| Build | Unknown delivery | `KIT_A_PATH` set | `ZEPHYR_MODULES`, `EXTRA_ZEPHYR_MODULES` or `ZEPHYR_EXTRA_MODULES` set, in CMake or the environment |
| --- | --- | --- | --- |
| Development | Warning | Warning, the path is printed, the check runs on that tree | Not checked |
| `-DKIT_REQUIRE_KNOWN_DELIVERY=ON` | Error | As in development | Not checked |
| `-DPRODUCT_RELEASE_BUILD=ON` | Error | Error | Error |

A symbolic link or a file name with a newline in the kit stops the check in every build. The check runs at configure time; in a CMake project the kit files and hash lists are configure dependencies, so a changed, added or removed kit file runs CMake and the check again. The tool runs with `Python3_EXECUTABLE`, else `PYTHON_EXECUTABLE`, else `python3`.

Commit a `.gitattributes` with `*.sha256 -text` in the kit module, so that no line-ending conversion changes a hash list.
