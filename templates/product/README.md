# Product template

This template moved from `samples/product_template` to `templates/product` on 9 November 2026. Update a copy or a link that names the old path.

A starting point for a product repository built on Crux. The repository is its own west manifest repository. Crux and Zephyr are projects in its workspace.

The [Product Composition Guide](https://github.com/wonny-labs/crux/blob/main/docs/product-composition.md) (`docs/product-composition.md` in `crux`) explains the choices.

| File | Purpose |
| --- | --- |
| `west.yml` | Imports `crux`, with comments for the optional group, a product-only module and an override |
| `app/` | A Zephyr application, the execution shell, that links `crux::time` and calls the domain |
| `domain/` | The product's own behaviour as plain C, with one product-owned port header |
| `check_domain_includes.py` | The domain include check, and with `--product` the include check of the whole product repository |
| `RELEASE.md` | A [release record](RELEASE.md) to copy for each release: dependency inventory, routes for modified upstreams, vendor kits, build environment, support period, release steps, bundle contents, revision and checks |
| `.gitignore` | Keeps `build/` out of the source tree that the build record hashes |
| `zephyr/module.yml`, `drivers/`, `dts/bindings/`, `boards/`, `tests/` | The driver kit: the repository as a Zephyr module with an example driver, its emulator and tests, and an example board. See [drivers/README.md](drivers/README.md) and [Writing a product driver](https://github.com/wonny-labs/crux/blob/main/docs/writing-a-product-driver.md) |

## Start a product

Copy this directory into an empty workspace directory, rename `product-x` in `west.yml`, and make it a Git repository. Replace `<board>` with your board target.

~~~sh
mkdir acme-workspace
cp -R crux/templates/product acme-workspace/product-x
cd acme-workspace
git -C product-x init
git -C product-x add .
git -C product-x commit -m "feat: start product-x"
west init -l product-x
west update
west crux-pins
west build -b <board> -d product-x/build/app product-x/app
~~~

`west crux-pins` compares the workspace with the revisions Crux pins, and fails on a difference with no declared reason. The build warns if the workspace uses another Zephyr release, and stops with `-DCRUX_REQUIRE_VERIFIED_ZEPHYR=ON`. The guide lists both checks, how to modify third-party code and how to make a release.

The copied `west.yml` follows Crux `main`. Pin it to a SHA once with `python3 crux/scripts/update-crux-pin.py --manifest product-x/west.yml`, commit it, and keep it current with the pin bot of [Keeping the Crux pin current](https://github.com/wonny-labs/crux/blob/main/docs/product-composition.md#keeping-the-crux-pin-current). For each release, copy `RELEASE.md` and fill it in. For a product that compiles vendor kits, its kit section follows [Vendor kits across repositories](https://github.com/wonny-labs/crux/blob/main/docs/vendor-kits.md) (`docs/vendor-kits.md` in `crux`).

## Boards

The application is the same for every board: the board is the `-b` argument of `west build`, and `west config build.board <board>` sets a default for a workspace.
Put what one board needs in `app/boards/<board>.conf` and `app/boards/<board>.overlay`, where `<board>` is the board target with `/` replaced by `_`, and keep `prj.conf` and feature fragments free of board values.
Kconfig in this repository depends on generic or `DT_HAS_<compatible>_ENABLED` symbols, as `drivers/sensor/example_temp/Kconfig` does, never on a board or SoC symbol.
The [porting guide](https://github.com/wonny-labs/crux/blob/main/docs/porting-to-a-new-board.md#board-neutral-conventions) (`docs/porting-to-a-new-board.md` in `crux`) lists the conventions with their Zephyr references.

## Zones and the domain include check

The template has two zones, after the three questions of [Choosing an API](https://github.com/wonny-labs/crux/blob/main/docs/choosing-an-api.md).

| Zone | Where | May include | Owns |
| --- | --- | --- | --- |
| Domain | `domain/` | ISO C headers, public `<crux/NAME.h>` headers of the contracts that are not frozen (Time, Logging, File and so on) and its own headers | The product's behaviour. No thread, no lock. Whatever else it needs from outside the domain, such as a sensor, comes through a port declared in `product_port.h` |
| Shell | `app/src/` | Zephyr, public Crux headers and the domain's headers | Threads, queues, locks, the implementation of the port and the adapters that Crux services call |

Run the check from the repository root after each change to the domain. It needs Python 3.9 or later and nothing else.

~~~sh
python3 check_domain_includes.py
~~~

It fails on the frozen Crux headers, every `<zephyr/...>` header and the composition interfaces `<crux/NAME_zephyr.h>` and `<crux/NAME_linux.h>` in `domain/`, and on includes it cannot read; the script's header comment has the full rules. `<crux/file_reliance_edge_zephyr.h>`, which names the Reliance Edge file system type for a mount, is one of these composition interfaces: include it only in the platform composition, the code that also mounts the file system, and never in `domain/`.

The check is lexical and lists only these names. Other native headers (SoC, CMSIS, vendor HAL, POSIX under `CONFIG_POSIX_API`) are caught only by the Host build of the domain, because they do not exist there, so build the domain on the Linux Host with a fake of `product_port.h` as well. A lexical check cannot see an include path that CMake adds, and the template adds none, so review still matters.

### Check the whole product repository

A product repository, or a copy of this template, checks all its sources with `--product`: the domain and the adapters in the shell. Run it from the repository root, in CI and before a review.

~~~sh
python3 check_domain_includes.py --product .
~~~

It reads every C and C++ source file under the root, in the same lexical way, and applies two rules:

- **Everywhere**, adapters included, it fails on `<crux/thread.h>`, `<crux/sync.h>`, `<crux/queue.h>` and `<crux/serial.h>`. An adapter may include `<zephyr/...>` headers, the composition interfaces and the other public Crux headers.
- **In `domain/`** it keeps every rule above. `domain/` is the default and is used only if it exists. Name other plain C directories with `--domain DIR`, once for each.

Code that already uses a frozen header and has not moved yet is listed once with `--exclude PATH`, relative to the root, so that the check can run in CI and still catches every new use. Remove the entry when the code moves to Zephyr.

~~~sh
python3 check_domain_includes.py --product . --exclude app/src/legacy_threads.c
~~~

It is lexical like the domain check. For code that is compiled, the opt-in compiler warning of the frozen headers is the second layer: it sees what the preprocessor sees, including a header that a macro or another header pulls in. Define `CRUX_WARN_FROZEN_HEADERS` for a target that compiles only the product's own sources, as in [Choosing an API](https://github.com/wonny-labs/crux/blob/main/docs/choosing-an-api.md#frozen-for-new-product-code-thread-sync-and-serial).

~~~cmake
target_compile_definitions(product_adapters PRIVATE CRUX_WARN_FROZEN_HEADERS)
~~~

The warning is silent in the targets that Crux's own CMake creates. A Zephyr image usually adds the sources of Crux services to `app`. Those sources include frozen headers on purpose, so they warn if you define the macro on `app` (and fail under the template's `-Werror`). Put the product's adapters in their own library, or accept the warnings from Crux's sources, and rely on `--product` for `app`.

An adapter that calls Zephyr kernel objects (for example `k_msgq_*`) is the exception to that advice. Make it a source of the `app` target (`target_sources(app PRIVATE ...)`) and rely on `--product` for it, because the warning guard cannot be defined on `app`. Built as a plain `STATIC` library it can fail to link; see [Writing a product driver](https://github.com/wonny-labs/crux/blob/main/docs/writing-a-product-driver.md#static-libraries-and-kernel-objects).

`--domain DIR` resolves a quoted include only relative to the including file and to `DIR`, never through an include path. A layout with `include/` beside `src/`, where `#include "name.h"` is found through an include path, therefore fails, even though the header is inside `DIR`. Either spell the include relative to `DIR` (`"include/name.h"`), or leave that directory out of `--domain`. Leaving it out keeps only the frozen-header rule for it, so `<zephyr/...>` includes there are not caught.

## Shared-state example

`app/src/main.c` shows how product state is shared with threads that Crux services start. A command handler runs on the thread of its console or SSH session, a web handler on the Zephyr HTTP server thread, the reboot busy check on the reboot worker, and a status read on the caller's thread.

1. One owner thread, `product_owner_entry`, is the only code that calls the domain.
2. A status read, `product_status_read`, loads a snapshot that the owner stores in a C11 atomic after each step. It takes no lock and never calls the domain.
3. A command, `product_command_set_limit`, posts a message to the owner's `k_msgq` without waiting. The owner applies it between two steps. The queue is four messages deep: a command that arrives when it is full is refused with `-ENOMSG` and is not applied, so the handler reports "busy" to its caller and does not wait.
4. A lock would live in the shell. This example needs none, because the snapshot is one value.

`main()` stands in for the callbacks of a service, so the example needs no extra Crux component. A real handler calls the same adapter and does nothing more. It is an example, not a framework: replace the stand-in port with a driver, and replace the one command with the product's own.

Format, patch-style and include checks that run from a product root, and an advisory clang-tidy run on target code, are in [style/README.md](style/README.md). [CONTRIBUTING.md](CONTRIBUTING.md) is a contribution guide to copy to the product root: commits, pull requests, checks, independent review, protected paths and hardware operations.
