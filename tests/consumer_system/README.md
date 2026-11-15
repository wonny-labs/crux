# System consumer outside the repository (ADR-0005 T3, T4, T5)

A product that lives **outside** the Crux repository, links one public target (`crux::system`), includes public
headers only (`<crux/system.h>`, `<crux/status.h>`), and uses the simulated System watchdog of
[ADR-0005](../../docs/decisions/0005-native-sim-test-watchdog-for-system-consumers.md) route A on `native_sim`. It is the
boundary test of that record: not "does the System module build" (that is `tests/system/zephyr`), but "can a
consumer that cannot see Crux's private files show a start, a feed cycle, a missed feed with its restart, and a
second boot".

Status: **Experimental** (the symbol it uses is Experimental, ADR-0001 Decision 4). A simulated watchdog is **not
hardware evidence**: a pass says that a product calls System in the right order and handles the answers in simulated
kernel time, and says nothing about a board.

## Layout

| Path | What it is | Rules it holds |
| --- | --- | --- |
| `app/CMakeLists.txt` | The product's build | Links `crux::system` only. Names no file inside the repository. |
| `app/prj.conf` | The product's configuration | One Crux symbol, `CRUX_SYSTEM` (and `CRUX_TIME=n`, because Time defaults on where an RTC exists). |
| `app/boards/native_sim_native_64.conf` | The `native_sim` fragment | `WATCHDOG`, `HWINFO`, `REBOOT` and `CRUX_SYSTEM_NATIVE_SIM_WATCHDOG`. |
| `app/src/main.c` | The execution shell: the scenario | Public `<crux/...>` headers only, and Zephyr for sleep and console. |
| `check_build.py` | The checks, as functions | Called by `tests/build/test_consumer_system.py` and by the script. |
| `variants.json` | The T4 negative variants | Each is one change to a fresh copy that a check must refuse. |

## Run it

`scripts/test-consumer-system.sh` (Linux, in the Dev Container, after `scripts/bootstrap-zephyr.sh`) copies this
directory to a temporary directory **outside** the repository, builds it with `west build -b native_sim/native/64`
and `-DZEPHYR_EXTRA_MODULES=<repo>` as `scripts/test-product-template.sh` does, applies `check_build.py`, runs the
image until its last line, builds it again with the symbol off, and then applies each variant. `scripts/test-system.sh`
calls it, so the Zephyr runtime shard runs it. No hardware, programming, reset or board is involved.

## Use it from outside the repository

A product repository can start from this directory:

1. Copy `app/` (and `check_build.py`, `variants.json` if you want the checks) into your repository.
2. Make the Crux checkout a Zephyr module of your workspace, as `west.yml` of `templates/product` does, or pass
   `-DZEPHYR_EXTRA_MODULES=<crux checkout>`. Nothing else of this directory reads the Crux checkout. `variants.json`
   uses `${CRUX_DIR}` in its include variant, and the script passes `-DCRUX_DIR=<crux checkout>` to the variant build only.
3. Build and run on `native_sim`:

   ~~~sh
   west build -b native_sim/native/64 <your app> -- -DZEPHYR_EXTRA_MODULES=<crux checkout>
   <build>/zephyr/zephyr.exe
   ~~~

4. Put the same lines in your own `native_sim`-only fragment: `CONFIG_WATCHDOG=y`, `CONFIG_HWINFO=y`,
   `CONFIG_REBOOT=y` and `CONFIG_CRUX_SYSTEM_NATIVE_SIM_WATCHDOG=y`. The symbol is refused at configure time on every
   other board. Your own tests then see the cause POR on the first boot and SOFTWARE after a missed feed
   (never WATCHDOG on `native_sim`), and a fresh System state on the second boot.
5. Arming order and loop policy belong to your product. The scenario here feeds on the second boot, or the restart
   would repeat until the harness timeout.

## The checks (ADR-0005 T3, T5)

- No include directory of a consumer source under `components/<c>/` is anything but `include` or `ports/zephyr/include`.
- A consumer source includes no Crux header but `<crux/system.h>`, `<crux/status.h>` and `<crux/logging.h>`, and no
  private file of a component.
- Every `target_link_libraries()` item is `crux::system` or a visibility keyword.
- The consumer's CMake wraps no Crux symbol (`crux_*`, `__wrap_crux_*`, `__real_crux_*`) at link time. The consumer guard
  of `cmake/CruxConsumerBoundary.cmake` refuses that too, but cannot run on Zephyr's `app` target.
- `prj.conf` and the board fragment name no Crux symbol beyond System and its simulated watchdog.
- With the symbol on, `.config` holds it with `BOARD_NATIVE_SIM` and `NATIVE_SIM_REBOOT`, and the simulated device is in
  the image; with it off, neither (T5).
- The run shows, in order, the cause POR, the start (state ACTIVE, 2000 ms), a feed cycle, the missed feed, the
  simulator's expiry line, the cause SOFTWARE, a fresh IDLE state and a second feed cycle. The lines are those of
  `tests/system/zephyr/native_sim_watchdog`.

## T4, the negative variants

| Variant | Refused because |
| --- | --- |
| `private_include_directory` | the private directory of the System Zephyr provider on the include path |
| `private_header_in_the_shell` | a private header of the provider in a product source |
| `frozen_header_in_the_shell` | a header that is not one of the three public ones |
| `target_without_a_crux_name` | a link target with no `crux::` name |
| `wrap_of_the_binding_seam` | a link-time wrap of the System binding seam |
| `frozen_symbol_in_prj_conf` | a Thread symbol named in `prj.conf` |

A wrap of a Zephyr symbol such as `sys_reboot` is not refused: ADR-0005 S6 leaves a product's own wraps alone.
In the Host test, each variant is also run with only the check function it relies on (`header_violations`,
`link_violations`, `wrap_violations` or `conf_violations`) replaced by one that finds nothing, and the variant is then
accepted. So each refusal is that function's. The include variant needs a build, so it has no such control on the
Host; its function is tested on a hand-made compile command, and CI runs the variant. Non-vacuity of the whole
fixture also rests on the clean-fixture test (the fixture passes every check) and on the message that each variant
must produce.

## Limits of the checks

- The link check reads `target_link_libraries()` calls in `app/CMakeLists.txt` only. A link added another way
  (`target_link_options`, a variable, another file) is not seen by it; the wrap check covers `--wrap` in any text of
  that file.
- The private-file pattern for includes matches path parts and names such as `system_zephyr` and `system_binding`; a
  private header with another name is caught only by its `crux` spelling or by the include-directory check.
- The include-directory check looks at directories under the repository's `components/` only, in the compile commands
  of the consumer's own sources.
- T5 (the symbol off) is a build and a `.config` and image check. The run-time expectation of an absent provider
  rests on the existing tests (`tests/m5_integrated/zephyr/main.c`), not on a run here.
- The run is read with a deadline (90 s by default): an image that goes silent fails with a `check_build: FAIL` line
  and does not block the runner.

## What it does not show

The `WATCHDOG` cause bit, the hardware timer, WDOG1 resolution, debug pause, flag accumulation and power loss (see
[System validation](../../docs/system-validation.md#simulated-watchdog-on-native_sim-tests-only)). The Logging service is
not used here: it needs its own UART emulation configuration, and the scenario prints with `printk`.
