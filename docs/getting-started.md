# Getting started

> **Status:** written from the scripts and `devcontainer.json`. It has not yet been run on WSL2 or on native Linux.

This page takes you from nothing to a first build and test run on native Linux or on Windows with WSL2. It states what the scripts and the Dev Container require, so that the first build does not fail for a reason that is not obvious. For the builds themselves, see the [Build and Integration Guide](build.md).

## 1. Use a Git clone

The scripts find the repository with `git rev-parse --show-toplevel`. Nearly every script in `scripts/` does this, and `scripts/check_docs.py` uses `git ls-files`. Crux must therefore be a Git working tree. Without `.git`, the first command stops with `fatal: not a git repository`.

A real clone, made inside Linux or WSL2, is the recommended form. It keeps the executable bits and the LF line endings:

~~~sh
mkdir -p ~/work/crux-ws
git clone <repository-url> ~/work/crux-ws/crux-pilot
~~~

An archive is a fallback with these caveats. If you received one, make it a Git repository from its root:

~~~sh
git init -q && git add -A && git commit -qm import
~~~

In a fresh WSL2 distribution set `git config --global user.name` and `user.email` first, or the commit fails.

Caveats of an archive:

- The executable bits that Git records (`100755`) may be lost, and then `scripts/...` fails with "Permission denied". `chmod +x scripts/*.sh` covers only part of them, because other files are executable too. Compare with a clone (`git ls-files -s | awk '$1==100755'` in a real clone lists them) or clone again.
- CRLF files in an archive stay CRLF. `.gitattributes` applies only to a fresh checkout, so a copy that already holds CRLF files has to be cloned again instead of converted by hand.

## 2. Folder layout

Three things are involved, and each has one owner:

| Who | Creates |
| --- | --- |
| You | The parent folder, with `mkdir -p`, and the clone inside it. The parent folder can have any name. Use a short one that does not repeat the repository name, such as `~/work/crux-ws` |
| The Dev Container | Nothing on your disk. It mounts the parent folder (`workspaceMount` is `${localWorkspaceFolder}/..` in [`devcontainer.json`](../.devcontainer/devcontainer.json)) at `/workspace` and opens the repository inside it |
| `scripts/bootstrap-zephyr.sh` | `.west/`, `zephyr/` and `modules/` in the parent folder. It runs `west init -l` there and then `west update`. `bootloader/` appears only when the optional west group `crux-boot` is enabled (for example by `scripts/test-boot-composition.sh`), because `west.yml` filters that group out by default |

The script stops with `Expected repo at <workspace>/crux-pilot` unless the repository folder is named exactly `crux-pilot`. So:

- Name the clone folder `crux-pilot`. A folder such as `crux-pilot-main` or `crux` does not work.
- Make the parent folder an empty folder that is used only for Crux.
- Do not clone directly into your home directory. Its parent would be your whole home directory, which would be mounted into the container and filled with west checkouts.

One layout, on the host and in the container:

~~~text
~/work/crux-ws/            # you create it; mounted as /workspace; becomes the west workspace
  crux-pilot/              # you clone the repository here; /workspace/crux-pilot
  .west/  zephyr/  modules/    # created by bootstrap-zephyr.sh (bootloader/ only with the crux-boot group)
~~~

Open `~/work/crux-ws/crux-pilot` in VS Code and choose **Dev Containers: Reopen in Container**. The container's pinned Ubuntu 24.04 amd64 environment, its tools and the arm64 caveat are described in the [Build and Integration Guide](build.md#development-environment).

## 3. Windows with WSL2

- Use Docker Desktop with the WSL2 backend, or Docker Engine inside the WSL2 distribution.
- Clone inside the WSL2 file system, for example under `~/work/crux-ws`. Do not clone under `/mnt/c`. A bind mount from the Windows drive is slow for Zephyr builds, and file modes and line endings are not reliable there.
- Set `git config --global core.autocrlf false` in WSL2 before cloning. `.gitattributes` keeps LF line endings for shell scripts and the other files that run in Linux.
- Start VS Code from WSL2 (`code ~/work/crux-ws/crux-pilot`) with the Dev Containers extension, then reopen in the container.
- Give the WSL2 virtual machine more than the container limit (see section 5). Memory and processors for WSL2 are set in `%UserProfile%\.wslconfig`.

## 4. Network and proxy prerequisites

The first set-up downloads from these places. Each one has to be reachable, directly or through a proxy.

| What | Where from | Used by |
| --- | --- | --- |
| Dev Container base image | `mcr.microsoft.com` (`.devcontainer/Dockerfile`) | Building the container |
| Ubuntu packages | The Ubuntu archive | The Dockerfile (`apt-get`) |
| Python packages | PyPI | The Dockerfile's own `pip install` (west, pytest), `postCreateCommand` in `devcontainer.json`, and the pip installs in `scripts/bootstrap-zephyr.sh` (Zephyr requirements) and `scripts/test-boot-composition.sh` (MCUboot requirements) |
| west projects | `github.com` (`zephyrproject-rtos` by default; the `wolfSSL` and `tuxera` projects only when their optional west groups are enabled, see `west.yml`) | `west update` in `scripts/bootstrap-zephyr.sh` |
| GoogleTest | A source archive from `github.com/google/googletest`, fetched by CMake (`CMakeLists.txt`) | The first Host configure with `scripts/bootstrap-host.sh` |
| Zephyr SDK | Zephyr SDK release assets on GitHub. `west sdk install` looks the release up through the GitHub REST API | `scripts/bootstrap-zephyr.sh --install-sdk` |

What the code does about the network:

- `scripts/check-host.sh` runs with dependency resolution off, so it needs the first `scripts/bootstrap-host.sh` run to have fetched GoogleTest.
- `scripts/bootstrap-zephyr.sh` reads `CRUX_GITHUB_TOKEN`. When it is set, the script passes it to `west sdk install` as `--personal-access-token`. Use it when the unauthenticated GitHub API rate limit stops the SDK download:

  ~~~sh
  export CRUX_GITHUB_TOKEN=<read-only token>
  scripts/bootstrap-zephyr.sh --install-sdk
  ~~~

- A proxy allowlist may also need `api.github.com`, `codeload.github.com` and the hosts of the SDK release files.
- The scripts set no proxy. Behind a proxy, configure Docker's proxy settings for the image build, and pass `HTTP_PROXY`, `HTTPS_PROXY` and `NO_PROXY` into the container yourself. If the proxy re-signs TLS, its certificate authority has to be trusted by the image and by Git. Neither the Dockerfile nor the scripts do this for you. No proxy set-up has been run for this guide.

## 5. Disk and memory

These figures are estimates. No minimum has been measured.

- **Container limits.** `devcontainer.json` starts the container with `--memory=4g` and `--cpus=2`. Docker Desktop or WSL2 must offer at least that. Full Zephyr suites are slow at 2 CPUs; a draft pull request runs them in CI instead.
- **Disk.** Plan for 30 to 40 GiB free before the SDK installation, and more if you keep several build directories. One early run went from 41 GiB to 31 GiB free after the image, the SDK and the west workspace, and to 26 GiB after an image rebuild for the sanitizer runtime ([baseline](baseline.md)). Builds were smaller then, so treat the 10 GiB drop as a lower bound.
- **WSL2.** The Docker disk lives in a virtual disk file that grows and does not shrink by itself. Check the free space of the Windows drive that holds it.
- **Where it goes.** The SDK, the Python virtual environment and the caches are in the Docker volume `crux-host-cache`, mounted at `/opt/crux-cache`. The west checkouts are in the parent folder of the repository. Builds go to `build/` in the repository, which Git ignores.

## 6. What to run first

Inside the container, from `/workspace/crux-pilot`. Pick the row that fits what you want. Each script states its own prerequisite in the last column.

| What you want | Run | Needs | Disk and time |
| --- | --- | --- | --- |
| Host tests only | `scripts/bootstrap-host.sh` | Nothing else | Not yet measured |
| Zephyr samples | `scripts/bootstrap-zephyr.sh --install-sdk` once, then the [first-hour guide](first-hour.md) | Nothing else. It does not need the Host script. The SDK download is the longest step | Not yet measured |
| Full validation, including the board cross-build | Both bootstrap scripts, then `scripts/test-controller.sh` | `scripts/test-controller.sh` itself needs only the Zephyr bootstrap and its SDK. The Host script adds the Host tests | Not yet measured |
| Before a pull request | `scripts/check-host.sh`, then the [test guide](../tests/README.md#before-you-open-a-pull-request) | One earlier `scripts/bootstrap-host.sh`, because it works without network access | Not yet measured |

None of these commands programs or resets a board.

## 7. Boards and debug probes

The only host on which debugging and physical tests have been run is macOS. `scripts/macos/start-jlink-gdbserver.command` (it prefers `/usr/local/bin/JLinkGDBServer` and falls back to a SEGGER `JLinkGDBServerCLExe`) and `scripts/test-target.sh` both exit on any other system, and `.vscode/launch.json` connects to `host.docker.internal:2331`. No Linux or Windows route has been run. On native Linux, Docker does not resolve `host.docker.internal` unless the container is started with `--add-host=host.docker.internal:host-gateway`; this too has not been tried. On WSL2, USB forwarding to the distribution is needed only if the GDB server runs inside WSL2; running the server on Windows is the other option. Both are untried. Any operation on a board needs approval for the task. See [RT1060-EVKB debugging](build.md#rt1060-evkb-debugging).

Most work does not need a board. Host tests, `native_sim` runs and EVKB cross-builds run without one, and none of them proves physical operation.

## 8. Supported environments

| Environment | Scope |
| --- | --- |
| Linux Host (amd64) | Development and tests, including sanitizer builds and source-tree consumers. Not an Embedded Linux product variant |
| Zephyr `native_sim` | Zephyr component and integration tests without hardware |
| MIMXRT1060-EVKB Rev B (`mimxrt1060_evk@B//qspi`) | First physical target. Results are limited to the documented firmware and configurations |
| RT1170-EVK Rev A1, Cortex-M7 | Software only: cross-build, probe identification and review. Not verified on hardware |
| Embedded Linux | Not implemented. It will be designed at the service boundary when a first product needs it |

A Host test, a `native_sim` run, a target cross-build and a physical-board run each prove different things, and none implies another. [Component readiness](component-readiness.md) records which of them exist for each component.
