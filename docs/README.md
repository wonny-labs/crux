# Crux documentation map

This page finds the right page for what you want to do. Start at the [repository README](../README.md) for what Crux is and the quick start. Each page states its own status at its top; the code and CI at your revision are authoritative.

## Set up and build

- [Tutorial: your first build and sample](tutorial.md): from the Dev Container to the Crux samples on the Linux Host and CTest (Part A), then the Crux samples on `native_sim`, Twister, and changing a build (Part B) with Kconfig, Devicetree overlays and CMake options, then a sample built and flashed on your board (Part C).
- [Samples](../samples/README.md): every sample folder, whether it runs on its own, and how to run it.
- [Getting started](getting-started.md): the Git clone, the folder layout, Windows with WSL2, network and proxy access, disk and memory, the set-up that the one Dev Container runs by itself (`scripts/bootstrap.sh`), and what a board adds.
- [Boards](boards/README.md): one page per board with its target, switches and jumpers, probe and connection, flash and debug, recovery and limits.
- [J-Link board route on Linux and WSL2](board-jlink-usbipd.md): attach the probe, `scripts/bootstrap.sh board-host`, the J-Link package, then `west flash` and `west debug` from the Dev Container.
- [Build and Integration Guide](build.md): Host and Zephyr builds, external CMake applications and provider selection.
- [Test guide](../tests/README.md): every suite, what it proves, and the checks to run before a pull request.

## Build a product on Crux

1. [Choosing an API](choosing-an-api.md): the developer rule for where each kind of product code goes (Zephyr directly, a Crux service, or plain C in the product's own domain).
2. [Architecture overview](architecture.md): the three layers of a product, component ownership and the capability inventory.
3. [Product Composition Guide](product-composition.md) and the [product template](../templates/product/README.md): repository layout, west manifest, versions and release. There is no Crux release or tag yet.
4. [Component readiness](component-readiness.md): for each component, which environments and which evidence exist, its provisional tier, and what is missing.
5. [Testing a consumer application](build.md#testing-a-consumer-application) and the [test foundation decisions](test-foundation-proposal.md).
6. When several products share boards or drivers: [Shared boards and drivers across products](shared-hardware-modules.md). When products compile vendor kits delivered on more than one line: [Vendor kits across repositories](vendor-kits.md) (a recommended convention, Experimental).

**Migrating an existing controller product** (for example a PLC runtime on an i.MX RT board with eMMC storage and SPI I/O cards): read [Choosing an API](choosing-an-api.md) first. Threads, locks, queues, timers and buses use Zephyr directly, and GPIO, I2C and SPI are frozen and to be removed, so bus I/O such as an SPI backplane uses Zephyr's SPI API in an adapter. Then the product composition guide and template, the board and driver pages below, and for storage the [File composition interface](file-composition-interface.md), the [File contract](file-contract.md) and [eMMC and Reliance Edge composition](emmc-reliance-composition.md) (simulator and link-check evidence only; no eMMC hardware result exists).

## Add a board or a driver

- [Porting Crux to a new board](porting-to-a-new-board.md): the test ladder, what to review, a checklist and a first-board-run outline.
- [Writing a product driver](writing-a-product-driver.md): module layout, binding, driver, emulator and `native_sim` tests, and the hardware scenario that stays gated.
- [Zephyr and driver code in a product repository](coding-guidelines.md#zephyr-and-driver-code-in-a-product-repository) and the [driver review checklist](driver-review-checklist.md). A [contribution guide template](../templates/product/CONTRIBUTING.md) is part of the product template.
- [Board image profiles](board-image-profiles.md): the registered images that the board test tooling may program and restore.
- [Boards](boards/README.md): adding a board page once a board runs.

## Use a platform service

A contract page defines one component's public behaviour, its limits and its validation. A validation page records the tests behind it.

| Area | Pages |
| --- | --- |
| Time | [Time contract](time-contract.md), [CPU busy-wait](time-busy-wait.md) |
| Execution and messaging (frozen for new product code) | [Thread and Sync](thread-sync.md), [event and queue](messaging-contract.md) and its [validation](messaging-validation.md) (Queue removed) |
| Communication and networking | [Serial](serial-contract.md), [serial validation](serial-validation.md), [networking](networking-contract.md) |
| Storage and configuration | [File](file-contract.md), [Configuration](configuration-contract.md), [File root binding](file-composition-interface.md), [microSD composition](microsd-composition.md), [eMMC on Reliance Edge](emmc-reliance-composition.md) |
| Diagnostics and system | [Logging](logging-contract.md), [system health and reset](system-validation.md) |
| Device I/O (frozen, to be removed: use Zephyr's APIs, see [Choosing an API](choosing-an-api.md#frozen-then-removed-gpio-i2c-and-spi)) | [GPIO](gpio-contract.md), [I2C](i2c-contract.md), [SPI](spi-contract.md) |
| Boot and update | [Image state contract](image-state-contract.md) (Experimental; Host test double only) |

### Secure management

A product team that consumes Crux as a west module starts with [Secure management in a product](management-in-a-product.md): what to enable, what is not built, limits, tested clients and browsers, and the open decisions. To judge what is verified before a product relies on it, read the [secure management review guide](secure-management-review.md). Nothing in this stack has run on a board.

| Topic | Pages |
| --- | --- |
| Terms | [Glossary](management-glossary.md): session channel and access session, provider and adapter, refuse and deny, route, listener, profiles |
| Accounts, roles, sessions and security events | [Access contract](access-contract.md), [credential store](credential-store.md), [security events](security-event-contract.md) |
| Management services | [Status and configuration services](status-configuration-services.md), [file service](file-service-contract.md), [network settings](network-settings-service.md), [reboot](reboot-service.md) |
| HTTPS web management | [HTTPS composition](https-composition.md), [web contract](web-contract.md), [sessions and login](web-session.md), [management APIs](web-management-apis.md), [packaged web assets](web-assets.md), [TLS certificate](tls-certificate.md), [API specification](../web/api/openapi.yaml) |
| Browser examples | [Web guide](../web/README.md) with the Preact and Angular examples, [configuration flow](web-config-flow.md), [advanced flows](web-advanced-flows.md) and [end to end on `native_sim`](e2e-native-220.md) |
| Command line over serial and SSH | [Command line contract](cli-contract.md), [SSH provider contract](ssh-provider-contract.md), [wolfSSH provider](ssh-wolf-provider.md), [command line over SSH](cli-over-ssh.md) |
| SFTP | [SFTP design](sftp-design.md) |
| The services together on `native_sim` | [Management composition](native-management-composition.md) and [the services image](native-composition-242.md) |
| Cryptography | [PSA crypto design](psa-crypto-design.md), [PSA crypto qualification](psa-crypto-qualification.md) |

## Secure boot and firmware update

Nothing in the boot path has run on a board.

1. The [boot overview](boot-overview.md), then the [secure boot and update review](secure-boot-and-update-review.md).
2. [Boot composition](boot-composition.md) and [taking the composition to an RT1062 product board](boot-porting-rt1062.md) (its eMMC variant is section 4).
3. Developer tools, not Crux interfaces: the [boot image inspection](boot-image-inspection.md) and the [boot reproducibility check](boot-reproducibility.md). The [HAB status page](boot-hab-status.md) says what exists for HAB.
4. The [verification ladder](secure-boot-verification-ladder.md): which level of test can prove which claim.
5. The [board test procedure](secure-boot-board-test-procedure.md) and the [bench session kit](secure-boot-bench-session.md). Neither has been run on a board, and neither approves a board operation.

## Security, releases and CRA work

- SBOM and releases: the [SBOM section](product-composition.md#sbom) and [upgrades and security fixes](product-composition.md#upgrades-and-security-fixes) of the product composition guide, the [product release record](../templates/product/RELEASE.md), the [compatibility table](compatibility-table.md) and the [release bundle checker](release-bundle-checker.md) (the last two are provisional).
- Dependencies and vulnerabilities: the [dependency review procedure](dependency-review.md) and its records for [Mbed TLS](dependency-review-mbed-tls-4.1.1.md), [the wolf projects](dependency-review-wolf-pins.md) and [FatFs](dependency-review-fatfs-r0.16.md), with [ADR-0006](decisions/0006-cryptographic-dependency-policy.md) for the cryptographic dependency policy.
- Static analysis and coding rules: [static-analysis coverage](static-analysis-coverage.md), [static analysis of target code](coding-guidelines.md#static-analysis-of-target-code) and the [MISRA C position](coding-guidelines.md#misra-c-position).

Known gap: the repository has no security policy file (`SECURITY.md`) and no recorded route for reporting a vulnerability. Raise it with the maintainer before relying on one.

## Contribute to the platform

1. [CONTRIBUTING.md](../CONTRIBUTING.md): code ownership, public interfaces, Git and pull request conventions, review requirements.
2. [Composition interface rules](composition-interfaces.md), the [native-free consumer boundary](native-interface-policy.md), [coding guidelines](coding-guidelines.md) and [upstream reuse](upstream-reuse.md).
   For documentation pages, the [documentation guidelines](documentation-guidelines.md) give the review checklist, one purpose per page and one home per fact.
3. The capability contract of the component you change (see [Use a platform service](#use-a-platform-service)).
4. [AGENTS.md](../AGENTS.md) if an AI agent works on the change.

### Keep the README an entry point

The [repository README](../README.md) lets a newcomer decide in a few minutes what Crux is, whether it fits, and how to start. It holds a short description and audience, capabilities in plain words, a quick start that works as written, links to read next, one or two lines of status, contributing and the licence. Put everything else on the page that owns it:

| Do not put in the README | Put it in |
| --- | --- |
| Change history, removals and migration notes | The component's contract page, or the history pages |
| Per-component lifecycle (frozen, to be removed, Experimental) and stability tiers | [Component readiness](component-readiness.md) |
| Component and provider lists | The [capability inventory](architecture.md#current-capability-integration) and the contract pages |
| Environment caveats and evidence limits | [Getting started](getting-started.md#8-supported-environments) and [Component readiness](component-readiness.md) |

`tests/build/test_readme_scope.py` fails when the README contains the usual markers of the first two rows: change history, migration notes and lifecycle words. The other rows are checked in review.

## Decisions

Platform-wide decisions are recorded as ADRs in [`decisions/`](decisions/README.md), with the [research notes](research/platform-direction-review.md) behind them. ADR-0001 to ADR-0006 are accepted. The titles of ADR-0004 to ADR-0006 still carry the word "proposal", a leftover of their drafting.

Four approved designs live under `superpowers/specs/`, a folder named after the development tool that produced its first files; other pages link them by path. They are current contracts: [Time redesign](superpowers/specs/2026-10-25-time-redesign.md), [Logging design](superpowers/specs/2026-10-24-logging-design.md), [Serial design](superpowers/specs/2026-10-24-serial-design.md) and [System health design](superpowers/specs/2026-10-24-system-health-design.md).

## Studies, feasibility reports and history

- Investigations and feasibility reports record what a study found and which options were taken; read each page's own status line. They include the boot desk studies ([boot and update](boot-update-investigation.md), [eMMC boot](boot-emmc-investigation.md), [bootloader update](boot-bootloader-update-investigation.md)), the eMMC and microSD pages, the `rt1060-*` pages and [RT1170-EVK feasibility](rt1170-evk-a1-feasibility.md) (software only).
- The project's development history (milestone records, run records, superseded proposals and plans) is indexed in [history/README.md](history/README.md). It is not current guidance.

## Stability tiers

[ADR-0001 Decision 4](decisions/0001-application-boundary-and-api-stability.md#decision-4-api-stability-and-change-policy) defines four tiers for public interfaces:

| Tier | Meaning |
| --- | --- |
| Experimental | Being tried. It may lack a Zephyr composition outside `tests/`, and may change in any release |
| Unstable | An adopted contract with a consumer and tests. It may change in a minor release, with a release note and a migration note |
| Stable | Covered by a compatibility promise. Only from `v1.0` |
| Deprecated | Still works, with a compiler warning and a named replacement |

Nothing is Stable, because no `v1.0` exists. The tier of each component in [Component readiness](component-readiness.md) is provisional: tiers have not yet been assigned to every public interface, and only some public headers (those of the management services, Configuration, the web and command line composition interfaces, the Reliance Edge file system type and the image-state contract) carry a `Status: Experimental` line. Separately, `thread`, `sync` and `serial` are **frozen for new product code** (`queue` was frozen too and was removed on 20 November 2026), and `gpio`, `i2c` and `spi` are frozen as Experimental and to be removed (ADR-0001 decision D4). A freeze is not a tier; see [Choosing an API](choosing-an-api.md).

## Concepts glossary

| Term | Meaning |
| --- | --- |
| **Portable component** | A Crux component, under `components/`, written in C17 and independent of Zephyr, board and vendor headers. OS-specific code usually sits in its `ports/` directory |
| **Public header** | A header under a component's `include/crux/`, included as `<crux/NAME.h>`. It is the interface a product uses |
| **Usage target** | The CMake target a consumer links to use a component, such as `crux::time`. A usage target is not an installed package or a binary SDK |
| **Composition** (platform composition) | The board- or project-specific configuration and initialisation that choose OS implementations and bind hardware resources, such as Kconfig, providers and device bindings. A **composition interface** is the one formal way composition code reaches a provider that must be bound to Zephyr resources ([rules](composition-interfaces.md)) |
| **Provider** | The implementation behind a Crux interface for one environment, for example a Linux Host provider or a Zephyr provider |
| **Zephyr-direct** | Product code that uses Zephyr's own APIs for OS and hardware facilities, such as threads, locks, queues, devices and buses, instead of going through a Crux wrapper. The [developer rule](choosing-an-api.md) makes this the default for those facilities |
| **Frozen for new product code** | The status of `thread`, `sync` and `serial` (and of `queue` until its removal on 20 November 2026): no new features, existing users keep working, and any deprecation waits for a separate decision. Their public headers can print an opt-in compiler warning (`CRUX_WARN_FROZEN_HEADERS`), as can those of `gpio`, `i2c` and `spi`, which are frozen differently: ADR-0001 decision D4 freezes them as Experimental and plans their removal after the first tag |
| **Decision codes** (P3, R4, O4, D10, I5, Q2 ...) | A letter and a number name a row in one decision record or proposal. The letter depends on the document. **P1 to P10** are the platform decisions of [ADR-0002](decisions/0002-platform-direction-zephyr-execution-crux-services.md). **R1 to R6** are the results of [ADR-0003](decisions/0003-p9-result-services-keep-narrow-thread-sync.md). **D1 to D10** are the owner decisions at the end of [ADR-0001](decisions/0001-application-boundary-and-api-stability.md#owner-decisions) (other pages, such as the secure boot development plan, have their own D rows: read the document that is linked beside the code). **I1 to I9** and **Q1 to Q9** are the decisions and open questions of the [image state contract proposal](plans/image-state-contract-proposal.md). **Q1 to Q8** in ADR-0006 are its own questions. **O1 to O5** (with O4a) are the options of the [platform direction review](research/platform-direction-review.md#4-options): O1 is ADR-0001 as it is, O2 Zephyr only, O3 a full portable layer, O4a ADR-0001 with a real-time carve-out, O4 Zephyr for execution and Crux for services, O5 a documented POSIX subset. ADR-0003 later reuses O2 and O4 for the internals of the services. **C1 to C9** are the choices of ADR-0004 and **S1 to S9** those of ADR-0005. **R1 to R8** and **O1 to O8** are also used for case identifiers inside the [image state contract](image-state-contract.md); those are local to that page. A code that is local to one document is defined in that document. Follow the link next to a code to find its row; a bare code does not decide anything by itself |
| **D4** (of ADR-0001) | The owner decision to freeze the I2C, SPI and GPIO APIs now as Experimental, announce deprecation at the first tag and remove them in the next tagged release. Not to be confused with "Decision 4" of the same ADR, which is the API stability policy |
| **EVKB** | The NXP i.MX RT1060 evaluation kit, revision B (`mimxrt1060_evk@B//qspi`), the first board of the project. It has QSPI NOR and a microSD slot and no eMMC |
| **west groups `crux-boot`, `crux-reliance`, `crux-secure-management`** | Optional groups of projects in `west.yml`, all off by default: MCUboot (`crux-boot`); the Reliance Edge file system, GPLv2 (`crux-reliance`); and the TLS, PSA and SSH stacks of the management services, Mbed TLS, TF-PSA-Crypto, wolfSSL, wolfSSH and wolfPSA (`crux-secure-management`, off by default so that an ordinary workspace fetches no GPLv3 source) |
| **Mbed profile, Wolf profile** | The two sets of TLS and PSA libraries a composition can select: Mbed TLS with TF-PSA-Crypto, or wolfSSL with wolfPSA. SSH is available on the Wolf profile only. See the [management glossary](management-glossary.md) and [Secure management in a product](management-in-a-product.md) |
| **Bench image** | The management image built for the RT1060 EVKB board (`tests/zephyr/management_rt1060_compile`), planned in [the bench image plan](rt1060-bench-image-plan.md). Not a product image |
| **Sysbuild** | Zephyr's way to build several images, here MCUboot and the application, in one build |
| **RAM load, trailer** | The MCUboot mode that copies the signed application to RAM and starts it there. The trailer is the state area at the end of an image slot (magic, `image_ok`, `copy_done`) that MCUboot and the image-state contract read and write |
| **HAB** | The i.MX RT boot ROM's check of the first-stage image. See the [HAB status page](boot-hab-status.md) |
| **Host** | The Linux development and test composition on a developer machine or in CI. It is not an Embedded Linux product variant |
| **`native_sim`** | Zephyr's simulated board, which runs a Zephyr image as a process on the Host. A `native_sim` result does not prove behaviour on a board |
| **Evidence levels** | E1 Host test, E2 `native_sim`, E3 EVKB build, E4 physical board, as defined in [Component readiness](component-readiness.md#how-to-read-this). None implies another |
| **ADR** | Architecture decision record: one platform-wide decision with its context, options, trade-offs and the recorded decision ([index](decisions/README.md)) |
| **The owner** | The repository maintainer: the person who approves platform decisions and the merge of every pull request. A team that works on its own copy names its own maintainer for that role |
| **AGENTS.md and CLAUDE.md** | Instructions for AI agents that work in this repository: what they may do on their own, what needs the owner's approval, which paths are protected, and which checks to run. A human contributor reads [CONTRIBUTING.md](../CONTRIBUTING.md) |

Terms of the project's development history (the Pilot and its milestones, Build A and Build B, WP1a, Draft PR and reviewer PASS) are in the [history glossary](history/README.md#terms-of-the-development-history).

## Who to ask

Open an [issue](https://github.com/wonny-labs/crux-pilot/issues) for a missing composition interface, a documentation gap or a question about a decision. The repository records no other contact channel.

## Status and limits

Crux is not production-qualified and is not an installable SDK. Its components have different readiness, and no Crux release or tag exists. No physical-board evidence exists for the secure management services or the boot path. The first board is the RT1060-EVK Rev B; the RT1170-EVK pages are software-only records. Static analysis is clang-tidy with [`.clang-tidy`](../.clang-tidy); [static-analysis coverage](static-analysis-coverage.md) measures what it covers. The [README](../README.md#status-and-limits) states the limits in short.
