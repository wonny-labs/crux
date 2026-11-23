# Crux documentation map

This page finds the right page for what you want to do. Start at the [repository README](../README.md) for what Crux is and the quick start. The code and CI at your revision are authoritative.

## Set up and build

- [Tutorial: your first build and sample](tutorial.md): from the Dev Container to samples on the Host, on `native_sim` and on your board.
- [Samples](../samples/README.md): every sample folder, whether it runs on its own, and how to run it.
- [Getting started](getting-started.md): the clone, folder layout, Windows with WSL2, proxies, and the Dev Container set-up.
- [Boards](boards/README.md): one page per board with its target, switches and jumpers, probe and connection, flash and debug, recovery and limits.
- [J-Link board route on Linux and WSL2](board-jlink-usbipd.md): attach the probe, `scripts/bootstrap.sh board-host`, the J-Link package, then `west flash` and `west debug` from the Dev Container.
- [Build and Integration Guide](build.md): Host and Zephyr builds, external CMake applications and provider selection.
- [Test guide](../tests/README.md): every suite, what it proves, and the checks to run before a pull request.

## Build a product on Crux

1. [Choosing an API](choosing-an-api.md): the developer rule for where each kind of product code goes (Zephyr directly, a Crux service, or plain C in the product's own domain).
2. [Architecture overview](architecture.md): the three layers of a product, component ownership and the capability inventory.
3. [Product Composition Guide](product-composition.md) and the [product template](../templates/product/README.md): repository layout, west manifest, versions and release.
4. [Component readiness](component-readiness.md): for each component, which environments and which evidence exist, its provisional tier, and what is missing.
5. [Testing a consumer application](build.md#testing-a-consumer-application) and the [test foundation decisions](test-foundation-proposal.md).
6. When several products share boards or drivers: [Shared boards and drivers across products](shared-hardware-modules.md). When products compile vendor kits delivered on more than one line: [Vendor kits across repositories](vendor-kits.md).

**Migrating a controller product:** start with [Choosing an API](choosing-an-api.md), then the product guide, the template and the storage pages ([File composition interface](file-composition-interface.md), [File contract](file-contract.md), [eMMC and Reliance Edge composition](emmc-reliance-composition.md)).

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
| Execution and messaging | [Thread and Sync](thread-sync.md), [event and queue](messaging-contract.md) and its [validation](messaging-validation.md) |
| Communication and networking | [Serial](serial-contract.md), [serial validation](serial-validation.md), [networking](networking-contract.md) |
| Storage and configuration | [File](file-contract.md), [Configuration](configuration-contract.md), [File root binding](file-composition-interface.md), [microSD composition](microsd-composition.md), [eMMC on Reliance Edge](emmc-reliance-composition.md) |
| Diagnostics and system | [Logging](logging-contract.md), [system health and reset](system-validation.md) |
| Device I/O (use Zephyr's APIs: see [Choosing an API](choosing-an-api.md)) | [GPIO](gpio-contract.md), [I2C](i2c-contract.md), [SPI](spi-contract.md) |
| Boot and update | [Image state contract](image-state-contract.md) |

### Secure management

A product team that consumes Crux as a west module starts with [Secure management in a product](management-in-a-product.md): what to enable, what is not built, limits, tested clients and browsers, and the open decisions. To judge what is verified before a product relies on it, read the [secure management review guide](secure-management-review.md).

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

1. The [boot overview](boot-overview.md), then the [secure boot and update review](secure-boot-and-update-review.md).
2. [Boot composition](boot-composition.md) and [taking the composition to an RT1062 product board](boot-porting-rt1062.md) (its eMMC variant is section 4).
3. Developer tools, not Crux interfaces: the [boot image inspection](boot-image-inspection.md) and the [boot reproducibility check](boot-reproducibility.md). The [HAB status page](boot-hab-status.md) says what exists for HAB.
4. The [verification ladder](secure-boot-verification-ladder.md): which level of test can prove which claim.
5. The [board test procedure](secure-boot-board-test-procedure.md) and the [bench session kit](secure-boot-bench-session.md). Neither approves a board operation.

## Security, releases and CRA work

- SBOM and releases: the [SBOM section](product-composition.md#sbom) and [upgrades and security fixes](product-composition.md#upgrades-and-security-fixes) of the product composition guide, the [product release record](../templates/product/RELEASE.md), the [compatibility table](compatibility-table.md) and the [release bundle checker](release-bundle-checker.md).
- Dependencies and vulnerabilities: the [dependency review procedure](dependency-review.md) and its records for [Mbed TLS](dependency-review-mbed-tls-4.1.1.md), [the wolf projects](dependency-review-wolf-pins.md) and [FatFs](dependency-review-fatfs-r0.16.md), with [ADR-0006](decisions/0006-cryptographic-dependency-policy.md) for the cryptographic dependency policy.
- Static analysis and coding rules: [static-analysis coverage](static-analysis-coverage.md), [static analysis of target code](coding-guidelines.md#static-analysis-of-target-code) and the [MISRA C position](coding-guidelines.md#misra-c-position).

Known gap: the repository has no security policy file (`SECURITY.md`) and no recorded route for reporting a vulnerability. Raise it with the maintainer before relying on one.

## Contribute to the platform

1. [CONTRIBUTING.md](../CONTRIBUTING.md): code ownership, public interfaces, Git and pull request conventions, review requirements.
2. [Composition interface rules](composition-interfaces.md), the [native-free consumer boundary](native-interface-policy.md), [coding guidelines](coding-guidelines.md) and [upstream reuse](upstream-reuse.md).
   For documentation pages, the [documentation guidelines](documentation-guidelines.md) give the review checklist, one purpose per page and one home per fact.
3. The capability contract of the component you change (see [Use a platform service](#use-a-platform-service)).
4. [AGENTS.md](../AGENTS.md) if an AI agent works on the change.

## Decisions

Platform-wide decisions are recorded as ADRs in [`decisions/`](decisions/README.md), with the [research notes](research/platform-direction-review.md) behind them.

Four approved designs live under `superpowers/specs/`; other pages link them by path. They are current contracts: [Time redesign](superpowers/specs/2026-10-25-time-redesign.md), [Logging design](superpowers/specs/2026-10-24-logging-design.md), [Serial design](superpowers/specs/2026-10-24-serial-design.md) and [System health design](superpowers/specs/2026-10-24-system-health-design.md).

## Studies, feasibility reports and history

- Investigations and feasibility reports record what a study found and which options were taken; read each page's own status line. They include the boot desk studies ([boot and update](boot-update-investigation.md), [eMMC boot](boot-emmc-investigation.md), [bootloader update](boot-bootloader-update-investigation.md)), the eMMC and microSD pages, the `rt1060-*` pages and [RT1170-EVK feasibility](rt1170-evk-a1-feasibility.md) (software only).
- The project's development history (milestone records, run records, superseded proposals and plans) is indexed in [history/README.md](history/README.md). It is not current guidance.

## Stability and terms

[ADR-0001 Decision 4](decisions/0001-application-boundary-and-api-stability.md#decision-4-api-stability-and-change-policy) defines the stability tiers, and [Component readiness](component-readiness.md) gives each component's tier. The [glossary](glossary.md) defines the terms and decision codes that the pages use. Terms of the project's development history (the Pilot and its milestones, Build A and Build B, WP1a, Draft PR and reviewer PASS) are in the [history glossary](history/README.md#terms-of-the-development-history).

## Who to ask

Open an [issue](https://github.com/wonny-labs/crux-pilot/issues) for a missing composition interface, a documentation gap or a question about a decision. The repository records no other contact channel.

## Status and limits

Crux is not production-qualified, not an installable SDK, and has no release tag. Per-component evidence is in [Component readiness](component-readiness.md). The [README](../README.md#status-and-limits) states the limits in short.
