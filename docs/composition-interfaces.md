# Composition interface rules

Status: **adopted** by the owner's acceptance of [ADR-0001](decisions/0001-application-boundary-and-api-stability.md) on 12 November 2026 (D3), and written down here as its follow-up change 2. This document is guidance only. It changes no code, check, contract or protected path, and it authorises no hardware operation. The rules in the table come from [Decision 2](decisions/0001-application-boundary-and-api-stability.md#decision-2-where-zephyr-is-allowed-and-how-that-is-enforced) of the ADR. Where this page says what exists today, it was checked against the repository on the date of its change, and the checks are named.

## What a composition interface is

A **composition interface** is the one formal way for a product's platform composition code to reach a Crux provider that must be bound to Zephyr resources: a root, a device, an instance. It is not a portable contract. It names the OS on purpose, so that the [native-free consumer check](native-interface-policy.md) rejects it in portable code. The first Zephyr example is `crux::file_zephyr` with `<crux/file_zephyr.h>` and the second is `crux::web_zephyr` with `<crux/web_zephyr.h>` (see [The web start](#the-web-start)). Phase 1b proposes `crux::cli_zephyr` with `<crux/cli_zephyr.h>` (pending the owner's approval, see [The serial console start](#the-serial-console-start)). The erase of the credential store is another, `crux::credential_store_zephyr` with `<crux/credential_store_zephyr.h>` (see [The credential store erase](#the-credential-store-erase)). The supervision progress hook is `crux::service_priority_zephyr` with `<crux/service_priority_zephyr.h>` (see [The service thread progress](#the-service-thread-progress)). The File one is described in [File root binding](file-composition-interface.md). A second File header, `<crux/file_reliance_edge_zephyr.h>`, publishes the Reliance Edge file system type (Experimental, one constant and no function; see [the Reliance Edge file system type](file-composition-interface.md#the-reliance-edge-file-system-type)). No Linux Host composition target exists; see the [Linux Host nuance](#linux-host-composition-targets).

A product has two routes to Zephyr, and neither is an exception to the [three layers](architecture.md#three-layers-for-a-product-adr-0001):

1. **The product needs a Zephyr feature that Crux does not offer.** It writes an adapter behind a port that it owns. That needs no Crux change and no approval.
2. **Composition code must bind a Crux provider to Zephyr resources.** It uses a composition interface, under the rules below.

## The six rules

| # | Rule | Where it holds today (`crux::file_zephyr`) |
| --- | --- | --- |
| 1 | Target `crux::<capability>_zephyr`, and header `<crux/<capability>_zephyr.h>` under `components/<capability>/ports/zephyr/include/crux/` | Yes: target `crux::file_zephyr`, header `components/file/ports/zephyr/include/crux/file_zephyr.h`. A second header, `components/file/ports/zephyr/include/crux/file_reliance_edge_zephyr.h`, ships under the same target. That extends rule 1, which names one header per capability, and its name awaits the owner's decision ([the Reliance Edge file system type](file-composition-interface.md#the-reliance-edge-file-system-type)) |
| 2 | An INTERFACE target that adds the header's include root and links the portable target. It does not link the provider, which Kconfig selects | Yes: `crux_file_zephyr_composition` in `components/file/ports/zephyr/CMakeLists.txt` is an INTERFACE target. It adds `ports/zephyr/include` and links `crux_file`, the target behind `crux::file`. The provider `crux_file_zephyr` is a separate STATIC library that the module appends to the Zephyr link |
| 3 | The native-free consumer check rejects it by name, and by path where the target has an include root. A negative test shows that for a direct link, a transitive wrapper and the usage check | Yes: `tests/build/test_file_zephyr_boundary.py` |
| 4 | It binds, configures or selects a provider: a root, a device, an instance. It adds no behaviour that the portable contract lacks | In substance: the header publishes the three declarations that already existed ([File root binding](file-composition-interface.md#decisions-taken), decision 3) and the limited binding, which binds a root and configures its byte limit; the limit refuses growth with the existing `CRUX_FILE_ERR_NO_SPACE` ([the root byte limit](file-composition-interface.md#the-root-byte-limit)). The second header, `<crux/file_reliance_edge_zephyr.h>`, publishes one macro, `CRUX_FS_RELIANCE_EDGE`, with the value the private header had, and no function |
| 5 | It may include a Zephyr header or name a Zephyr type, such as `const struct device *`, only where the binding needs one | New in the ADR. `<crux/file_zephyr.h>` needs none: it includes only `<crux/file.h>`. `<crux/file_reliance_edge_zephyr.h>` includes `<zephyr/fs/fs.h>`, which rule 5 allows: its value is Zephyr's `FS_TYPE_EXTERNAL_BASE` |
| 6 | It follows the same stability tiers as any public interface ([Decision 4](decisions/0001-application-boundary-and-api-stability.md#decision-4-api-stability-and-change-policy)). A change forced by a Zephyr baseline move is listed as a breaking change | New in the ADR. No tier is assigned yet: the tier table is the ADR's follow-up change 5, so until it lands the [File root binding](file-composition-interface.md#what-kind-of-interface-this-is) statement of "the same naming and compatibility rules as any public Crux interface" stands. `<crux/file_reliance_edge_zephyr.h>` is the exception: its `Status:` line says Experimental |

Why rule 5 exists, in the ADR's words: composition code is Zephyr code already, so passing a device is more honest than inventing an identifier.

### Where the header lives

Rule 1 puts the header under `components/<c>/ports/zephyr/include/crux/`, not under `components/<c>/include/crux/`. The [File root binding](file-composition-interface.md#decisions-taken) justified this for one header (its decision 5): the header names a provider, so it stays with the port and reaches a product only through the composition target, while the portable `<crux/<capability>.h>` header is unchanged. Rule 1 extends that placement to every composition interface.

[CONTRIBUTING](../CONTRIBUTING.md#public-headers-and-module-dependencies) places public headers in a component's `include/crux/`, and does not name this second location. Whether it should is a follow-up change that needs the owner's approval, because CONTRIBUTING is a protected path. It is **not** part of this document's change, and until it is made the placement rests on the File root binding's recorded decision and the ADR.

### The web start

The second composition interface is the Zephyr web start (ADR-0004 section 2, phase 1a, Experimental): target `crux::web_zephyr` and header `<crux/web_zephyr.h>` under `components/web/ports/zephyr/include/crux/`. It binds the web core to the Zephyr HTTP server, its sockets and the TLS security tag, and publishes one existing declaration, `crux_web_start()`, with no new function (rule 4). The settings type `crux_web_config_t` is in the portable `<crux/web.h>`, so that a Host or Linux transport can use it too and the portable core does not include a `_zephyr` header. The INTERFACE target is `crux_web_zephyr_composition`, a name unlike the STATIC provider library `crux_web_zephyr` (rule 2: it links the portable target `crux_web` and not the provider). `tests/build/test_web_zephyr_boundary.py` is its negative test (rule 3), and `tests/build/test_web_zephyr_public.py` its header and target checks. The web session and management calls beside it are ordinary service API, not composition interfaces: `<crux/web_session.h>` and `<crux/web_management.h>`.

### The serial console start

The serial console start (ADR-0004 phase 1b, Experimental) is a composition interface: target `crux::cli_zephyr` and header `<crux/cli_zephyr.h>` under `components/cli/ports/zephyr/include/crux/`. It binds the Crux console to the UART of the devicetree alias `crux-serial0` and publishes one new function, `crux_cli_serial_start()`, which owns the console thread and takes the baud rate and the priority from Kconfig. The ADR said the first-account step needed no new symbol; it did not hold, because the console's own header (`crux_cli_console.h`) includes the frozen `<crux/serial.h>` and the private CLI adapter header, which pulls in first-account provisioning, and a product may include neither. The header includes only `<crux/cli.h>` (rule 5: no Zephyr type), the INTERFACE target `crux_cli_zephyr_composition` links the portable `crux_cli` and not the STATIC provider `crux_cli_zephyr` (rule 2), and `tests/build/test_cli_zephyr_boundary.py` is its negative test (rule 3). **It departs from rule 4 and from ADR-0004 section 4** ("A composition header publishes an existing declaration"): `crux_cli_serial_start()` is a new function, and it adds behaviour that the portable contract lacks, because it creates and places the console thread and runs a loop that never returns. The reason is that the existing declaration, `crux_cli_console_run()`, is in a header that a product cannot include (above). The alternative that keeps rule 4 is a blocking `crux_cli_serial_run()` that the product runs on a thread of its own, which puts a thread in product code. This is the owner's decision, and the pull request that proposes it states it.

### The service thread progress

The progress hook of the Crux service threads is a composition interface: target `crux::service_priority_zephyr` and header `<crux/service_priority_zephyr.h>` under `components/service_priority/ports/zephyr/include/crux/`. It publishes the identifiers of the six service threads (`crux_service_thread_t`, which were private) and one function, `crux_service_progress_register()`. Each service thread calls the registered function once per pass of its loop, and every loop waits at most about a second for work, so a product's supervisor can feed one task watchdog channel per started thread from it; the header states what a report does and does not show. The HTTP server thread and the SSH threads are not service threads and do not report. The header includes only `<crux/status.h>` (rule 5), and `tests/build/test_service_priority_zephyr_boundary.py` is its negative test (rule 3). **It departs from rule 2 and rule 4**: Service priority has no portable target, so the INTERFACE target links Base; and the function adds behaviour, a callback from Crux threads, rather than binding a provider. The alternative that keeps rule 4 is the status quo, supervision by indirect health only. The owner adopted the hook (O4), on the tier that the header's `Status:` line states.

### The credential store erase

The erase of the credential store is a composition interface: target `crux::credential_store_zephyr` and header `<crux/credential_store_zephyr.h>` under `components/credential/ports/zephyr/include/crux/`.
It publishes one existing declaration, `crux_credential_erase()`, with no new function, for a product's [factory reset](management-in-a-product.md#factory-reset).
The header includes only `<crux/credential_store.h>` (rule 5: no Zephyr type), and the INTERFACE target `crux_credential_store_zephyr_composition` links the portable `crux_credential_store` and not the STATIC provider `crux_credential_zephyr` (rule 2).
`tests/build/test_credential_zephyr_boundary.py` is its negative test (rule 3).
Its name follows the portable name `credential_store` (`crux::credential_store`, `<crux/credential_store.h>`), not the component directory `credential` (rule 1).
**It departs from rule 4**: the call binds, configures and selects nothing, and the portable header leaves it out so that application code cannot reach it.
Publishing it to the composition alone is the reason for this form.
The private adapter header keeps the same declaration for the portable build, and `tests/build/test_credential_zephyr_public.py` holds the two together.
The header's `Status:` line gives its tier.

### Linux Host composition targets

Rules 3, 4 and 6 also cover a Linux Host composition target, which names `linux` in place of `zephyr`. **Rule 2 does not apply to it.** On Linux Host no Kconfig selects a provider, so such a target is the provider itself. None exists. A new one needs a rejection by identity in the portable-consumer guard and a negative test for a direct link, an INTERFACE wrapper, a STATIC wrapper and an application alias.

## What is not an escape hatch

- **Private headers and `ports/` include paths**, such as `file_native.h`. A product never uses them, and they are not composition interfaces. A product that finds it needs one reports it.
- **A missing composition interface** is a Crux gap. It is reported as an issue against `crux-pilot`, as `crux-controller` already does.

## Adding a composition interface

Use these rules for the next one, together with the steps in [Extending Crux](architecture.md#extending-crux): a real consumer needs it, and its minimum contract can be tested. The rule against pass-through wrappers of native APIs in [AGENTS.md](../AGENTS.md#engineering-approach) applies as well. This document's reading, not the ADR's text, is that a composition interface therefore must bind or select something and add no behaviour of its own (rule 4), and that it takes the Extending Crux steps like any new public interface.

Before a new composition interface is proposed, check it against the table above, then add the same negative boundary test as `tests/build/test_file_zephyr_boundary.py` shows. A new public header, target or tier is a public interface decision, so it follows the escalation rules of [AGENTS.md](../AGENTS.md).

## Ports that the product implements

A **product-implemented port** is the inverse of a composition interface: Crux declares functions in a public header, and the product defines them in its own adapter code, with its own native calls. It binds no Crux provider to the OS, so the six rules above do not apply to it (ADR-0004 decision C3). It is still a public interface: it has a tier, a named header, documented ownership and thread context, no native type in the header, and a test that a product-style definition compiles against the header alone. The first one is `<crux/network_settings_apply_port.h>`, the network settings apply port.

## What this document does not do

- It adds no composition interface, check or test, and changes no file under `components/`, `tests/` or a protected path.
- It does not assign stability tiers (ADR follow-up 5) or add the product template's example include check and Host build of the domain (follow-up 3). The template's include check was added later, under P2 and P4 of ADR-0002.
- It does not change CONTRIBUTING (see [Where the header lives](#where-the-header-lives)).
