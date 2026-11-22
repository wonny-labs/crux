# Crux

**Crux** is a reusable embedded software platform for Zephyr firmware products, such as controllers. It gives a product tested platform services in portable C, a Zephyr module and build tooling, so that product code stays separate from operating-system and board details.

Crux is for teams that build Zephyr firmware products: application developers who compose a product on Crux, and platform contributors who extend Crux itself.

## What it provides

- **A clear rule for where code goes.** OS and hardware facilities, such as threads, queues and buses, use Zephyr directly. Platform services use Crux. Product behaviour is plain C in the product's own domain ([Choosing an API](docs/choosing-an-api.md)).
- **Platform services with written contracts:** typed time and clocks, file storage, configuration, logging, system health and reset, and network status and sockets.
- **Secure remote management:** accounts, roles and sessions, security events, HTTPS web management, a command line over serial and SSH, and services for files, configuration, network settings, certificates and reboot. It has not yet run on a board.
- **Boot and update building blocks:** an MCUboot build composition and an image-state interface.
- **A product starting point:** a product template, board and driver guides, samples, and tests that run on the Linux Host and on Zephyr `native_sim` without hardware.

The [architecture overview](docs/architecture.md) describes the public capabilities, and [Component readiness](docs/component-readiness.md) lists every component and how far each one is tested.

## Quick start

You need Git, Docker, VS Code with the Dev Containers extension, and 30 to 40 GiB of free disk. [Getting started](docs/getting-started.md) covers native Linux and Windows with WSL2.

1. Create a parent folder and clone the repository into it, as [Getting started](docs/getting-started.md#2-folder-layout) describes. You create the folder. The Dev Container only mounts it at `/workspace`, and `scripts/bootstrap-zephyr.sh` creates `.west/`, `zephyr/` and `modules/` inside it. [Getting started](docs/getting-started.md) also covers WSL2 and proxies.
2. Open the clone in VS Code and choose **Dev Containers: Reopen in Container**.
3. Inside the container, run the commands for your purpose from [Setup commands](docs/getting-started.md#6-setup-commands): Host tests only, Zephyr samples, the controller scenarios with the board cross-build, or the checks before a pull request. That table also says what each script needs.

None of these commands programs or resets a board. Next, the [Tutorial](docs/tutorial.md) runs the Crux samples on the Linux Host, then Zephyr's Hello World and the Crux samples, shows how to change a build, and ends with a sample on your board.

## Where to read next

| You want to | Read |
| --- | --- |
| Run your first builds and samples | [Tutorial: your first build and sample](docs/tutorial.md) and [Samples](samples/README.md) |
| Find any page by task | [Documentation map](docs/README.md) |
| Find your way around the repository | [Repository layout](docs/architecture.md#repository-layout) |
| Understand the layers and ownership | [Architecture overview](docs/architecture.md) and [Choosing an API](docs/choosing-an-api.md) |
| Build Crux or consume it from another CMake project | [Build and Integration Guide](docs/build.md) |
| Start, version and release a product | [Product Composition Guide](docs/product-composition.md) and the [product template](templates/product/README.md) |
| Add a board or a driver | [Porting to a new board](docs/porting-to-a-new-board.md) and [Writing a product driver](docs/writing-a-product-driver.md) |
| Add remote management or secure boot | [Secure management in a product](docs/management-in-a-product.md) and the [boot overview](docs/boot-overview.md) |
| Run the tests before a pull request | [Test guide](tests/README.md) |

## Status and limits

Crux is in development and not production-qualified. There is no release or tag yet: products pin a source revision. The [documentation map](docs/README.md#status-and-limits) gives the details.

## Contributing

Ask a question or report a gap as an [issue](https://github.com/wonny-labs/crux-pilot/issues). Read [CONTRIBUTING.md](CONTRIBUTING.md) for ownership, public interfaces and review rules, and [AGENTS.md](AGENTS.md) for the rules that AI agents follow in this repository.

## License

Crux is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
