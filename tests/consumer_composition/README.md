# Consumer composition (ADR-0004 T3 and T4)

A product that lives **outside** the Crux repository and composes the management services with Kconfig and
`-DZEPHYR_EXTRA_MODULES=<repo>`. It is the boundary test of [ADR-0004](../../docs/decisions/0004-product-composition-of-management-services.md)
section 5: not "does the module build" (that is `tests/native/management_module`), but "can a consumer compose the
services with public interfaces only".

Status: **Experimental, work in progress.** The skeleton builds the product's layout, its CMake, `prj.conf`,
route packaging and the checks. Its start order runs as far as the public headers allow today. Each start call
is added when the phase 1a header that carries it merges. It is not run in CI yet: the job in
`.github/workflows/zephyr.yml` is a separate, approved change that follows the first start-call headers.

## Layout

| Path | What it is | Rules it holds |
| --- | --- | --- |
| `app/CMakeLists.txt` | The product's build | Links `crux::` targets only. Names no file under `components/`. |
| `app/prj.conf` | The product's configuration | Service symbols and the capabilities under them. No `CRUX_THREAD`, `CRUX_SYNC`, `CRUX_TIME`, `CRUX_QUEUE` or `CRUX_SERIAL` (C6). The Zephyr, network, TLS and PSA symbols are the product's own, so the project reads nothing from inside the repository. |
| `app/src/main.c` | The execution shell: the start order | Public `<crux/...>` headers only. |
| `app/src/my_routes.c` | A route of the product's own | `<crux/web.h>` only. |
| `app/site/`, `app/reviewed-routes.txt` | The packaged folder and the reviewed route list | The folder goes through `crux_web_assets()`. |
| `app/tf_psa_threading/` | The Mbed profile's locks for TF-PSA-Crypto's core | Product glue (a copy of the test glue). How a product obtains it is an open question: see below. |
| `domain/` | The access policy as plain C | No Zephyr, no composition interface, no frozen header (`templates/product/check_domain_includes.py`). |
| `check_build.py` | The checks, as functions | Called by `tests/build/test_consumer_composition.py` and by the script. |
| `variants.json` | The T4 negative variants | Each is a one-line change that must be refused. |

`scripts/test-consumer-composition.sh` copies `app/` and `domain/` outside the repository, builds on `native_sim`
like `scripts/test-product-template.sh`, runs the image, applies `check_build.py`, and then applies each T4 variant to a
fresh copy.

## The checks (ADR-0004 section 5)

- No include directory of a consumer source under `components/<c>/` is anything but `include` or
  `ports/zephyr/include`. A new private directory is refused until someone names it public.
- Every `target_link_libraries()` item is a `crux::` target.
- No frozen header (`thread.h`, `sync.h`, `queue.h`, `serial.h`) in a product source, and no composition interface
  in the domain.
- `prj.conf` names no symbol that a service symbol selects.
- The image holds no wolfSSL, wolfSSH or wolfPSA symbol, and `.config` sets no `CONFIG_WOLF*` or `CONFIG_CRUX_SSH`.

## T4, the negative variants

| Variant | Refused because |
| --- | --- |
| `private_include_directory` | a private header directory on the include path |
| `target_without_a_crux_name` | a link target with no `crux::` name |
| `frozen_header_in_the_shell` | a frozen header in a product source |
| `composition_interface_in_the_domain` | a composition interface in the domain |
| `credential_adapter_directory` | the credential adapter directory |
| `frozen_symbol_in_prj_conf` | a Thread symbol named in `prj.conf` |

Each check also runs against a weakened guard in the Host test and must then pass, so that a refusal is not vacuous.

## What is missing (found while building this)

These are the gaps between this skeleton and a complete T3. They are reported, not worked around.

1. **The start calls of steps 3 and 5 to 10** need public headers and usage targets that phase 1a delivers: the
   credential store start (`<crux/credential_store_start.h>`, PR 419, used here through `__has_include`), usage targets for
   the Configuration, status, network settings, file and reboot services, the TLS certificate module, the apply port
   header, the web session and management lifecycle, and `web_zephyr`. `app/src/main.c` marks each as PENDING.
2. **The route sources of the services cannot be named by a consumer.** `web_session_routes.c` and the other route
   sources include private headers (`web_session_internal.h`, `crux_access_adapter.h`) and need the private directory of
   their component on the include path of the target that compiles them. A consumer that lists them in
   `crux_web_routes()` would have to add `components/web/session` to its include path, which the checks above refuse.
   The module builds the cores in `components/web/ports/zephyr/session` and `management` but not the route sources,
   because the route table is per image. Either the module offers the route sources as an object target that keeps
   its private directories to itself, or the consumer cannot use them. Until that is decided this fixture packages only
   its own route and the folder.
3. **The TF-PSA-Crypto locks** (`app/tf_psa_threading/`) are test glue that this fixture copies. A product needs
   them on the Mbed profile, and there is no supported way to get them yet.
4. **The Angular example** is packaged with `-DCRUX_CONSUMER_WEB_FOLDER=<dist> -DCRUX_CONSUMER_WEB_STYLE=inline` and
   `CONFIG_CRUX_WEB_RESPONSE_DEADLINE_MS=3000`; building it needs Node.js and is not part of the default run (see
   `docs/web-assets.md` and `docs/e2e-native-220.md`).
