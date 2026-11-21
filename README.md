# Crux

**Crux** is a reusable embedded software platform for controller and firmware applications. It provides portable C components (the language standard is in the [coding guidelines](docs/coding-guidelines.md)) and selected standard APIs, with OS-specific integration, build tools and tests. Portable application code stays separate from operating-system and board details.

Crux is for teams that build Zephyr firmware products: application developers who compose a product on Crux, and platform contributors who extend Crux itself.

## What it provides

Products choose where each kind of code goes with the [developer rule](docs/choosing-an-api.md): OS and hardware facilities use Zephyr directly, platform services use Crux, and product behaviour is plain C in the product's own domain.

| Area | Components |
| --- | --- |
| Foundation and timing | `base`, `time` |
| Execution and synchronisation (frozen for new product code) | `thread`, `sync`, `queue` |
| Communication and networking | `serial` (frozen for new product code), `sockets`, `netif` |
| Storage and configuration | `file` (FatFs, Reliance Edge), `configuration` |
| Diagnostics and system | `logging`, `system` |
| Device I/O (frozen, to be removed: use Zephyr's APIs) | `gpio`, `i2c`, `spi` |
| Boot and update | `image_state` (Experimental), an MCUboot build composition |
| Secure management | `access`, `credential`, `security_event`, `cli`, `file_service`, `config_service`, `mgmt_status`, `network_settings`, `reboot`, `tls_certificate`, `web`, `ssh` |

The [capability inventory](docs/architecture.md#current-capability-integration) gives each component's contract and providers, and [Component readiness](docs/component-readiness.md) gives its environments, evidence and stability tier.

## Development and target environments

| Environment | Scope |
| --- | --- |
| Linux Host (amd64) | Development and tests, including sanitizer builds and source-tree consumers. Not an Embedded Linux product variant |
| Zephyr `native_sim` | Zephyr component and integration tests without hardware |
| MIMXRT1060-EVKB Rev B (`mimxrt1060_evk@B//qspi`) | First physical target. Results are limited to the documented firmware and configurations |
| RT1170-EVK Rev A1, Cortex-M7 | Software only: cross-build, probe identification and review. Not verified on hardware |
| Embedded Linux | Not implemented. It will be designed at the service boundary when a first product needs it |

A Host test, a `native_sim` run, a target cross-build and a physical-board run each prove different things, and none implies another.

## Quick start

1. Clone into an empty parent folder; the folder name `crux-pilot` is required: `git clone <repository-url> ~/work/crux-ws/crux-pilot`. [Getting started](docs/getting-started.md) explains the layout, Windows with WSL2, proxies and disk space (about 30 GiB).
2. Open the folder in VS Code and choose **Dev Containers: Reopen in Container**.
3. Inside the container, from the repository root, build and test:

```sh
scripts/bootstrap-host.sh                    # Host build and tests (CTest)
scripts/check-host.sh                        # later Host builds and tests
scripts/bootstrap-zephyr.sh --install-sdk    # pinned west workspace and Zephyr SDK
scripts/test-controller.sh                   # native_sim scenarios and the EVKB cross-build
```

CI runs most of the same scripts on each pull request; the test guide says which runs stay local. None of these commands programs or resets a board. Debugging, resets and programming need a separately approved procedure: see [RT1060-EVKB debugging](docs/build.md#rt1060-evkb-debugging). The [test guide](tests/README.md) lists the other suites and the checks to run before a pull request.

## Where to read next

| You want to | Read |
| --- | --- |
| Find any page by task | [Documentation map](docs/README.md) |
| Understand the layers and ownership | [Architecture overview](docs/architecture.md) and [Choosing an API](docs/choosing-an-api.md) |
| Build, integrate or consume Crux from another CMake project | [Build and Integration Guide](docs/build.md) |
| Start, version and release a product | [Product Composition Guide](docs/product-composition.md) and the [product template](templates/product/README.md) |
| Add a board or a driver | [Porting to a new board](docs/porting-to-a-new-board.md) and [Writing a product driver](docs/writing-a-product-driver.md) |
| Add remote management or secure boot | [Secure management in a product](docs/management-in-a-product.md) and the [boot overview](docs/boot-overview.md) |
| Look up a platform-wide decision | [Decision records](docs/decisions/README.md) |

## Repository layout

| Path | Purpose |
| --- | --- |
| `components/` | Public interfaces, shared implementations and OS-specific ports |
| `samples/` | Capability examples and reference controller applications |
| `zephyr/` | Out-of-tree Zephyr module integration |
| `templates/` | Copy-and-start skeletons for product, hardware and kit repositories |
| `tests/` | Host, Zephyr, build-policy and target tests |
| `web/` | Management API specification and browser examples ([web guide](web/README.md)) |
| `scripts/`, `tools/` | Setup, build, analysis and test commands; board test tooling outside the runtime build |
| `.devcontainer/` | Development environment |
| `docs/` | Guides, contracts and decision records |

## Status and limits

- Not production-qualified, and not an installable SDK: no `find_package(Crux)` and no binary package.
- No release or tag yet. Products pin a source revision (a west project or a source tree).
- Stability tiers are provisional and nothing is Stable ([Component readiness](docs/component-readiness.md)).
- Secure management and the boot path have not run on a board.

## Contributing

Ask a question or report a documentation gap or a missing interface as an [issue](https://github.com/wonny-labs/crux-pilot/issues). Read [CONTRIBUTING.md](CONTRIBUTING.md) for ownership, public interfaces and review rules, and [AGENTS.md](AGENTS.md) for the rules that AI agents follow in this repository.

## License

Crux is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
