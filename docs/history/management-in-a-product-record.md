# Secure management in a product: record of removed passages

> **Historical record.** Moved from [management-in-a-product.md](../management-in-a-product.md) when the documentation was restructured as a developer entry point. Kept as written; not current guidance. The link check does not read this folder.

Each passage below is the original text of a line, row or section that the guide now states in current terms or no longer carries: a revision note, owner-decision dates and option letters, phase and slice labels, a run note and the owner-decision table. Table rows are shown with their table header so that they read as tables.

## From `docs/management-in-a-product.md`: the status line

Status: a guide for a product team that uses Crux as a west module and wants HTTPS web management, the SSH command line and SFTP, without reading the code. It adds no behaviour and no decision. Each statement cites a document or a file, and says whether it is **real**, **faked** or **untested**. It was written against `origin/main` at `e1023e7`. **Stale since 159 commits:** `origin/main` was 159 commits ahead of that revision when this line was written (`git rev-list --count e1023e7..40a99210`), and the page was not re-verified. The authoritative state is the code and the CI at the revision you use.

## From `docs/management-in-a-product.md`: section "What you get, and what is not built"

| Item | State | Where it is tracked |
| --- | --- | --- |
| **User key registration.** | No command or web route registers an SSH user key, and none is planned until a consumer needs one (decided 2026-11-14, option C). **A product registers keys itself** with `crux_access_account_add_key`: [how](#registering-a-user-key). Only test code calls it today. | [Issue #318](https://github.com/wonny-labs/crux-pilot/issues/318) |
| **Certificate registration.** | No `native_sim` composition registers the device certificate with the listener, and no web route exists for it. Decided in ADR-0004 (C4): for phase 1 the product's adapter registers the material with `tls_credential_add` (option A1), which may be revisited before the certificate step ([decisions](../decisions/0004-product-composition-of-management-services.md#the-owners-decisions)). The RT1060 bench image and the [Mbed management image](../rt1060-mbed-management-image.md) do this in code that has not run on a board. | [TLS certificate](../tls-certificate.md) (status line, and "Registration with Zephyr's TLS credentials") |

## From `docs/management-in-a-product.md`: section "Steps", items 2 and 3

2. **Choose a TLS profile.** The Mbed profile gives HTTPS only. The Wolf profile gives HTTPS and SSH, because wolfSSH needs wolfSSL, and `CONFIG_CRUX_SSH` is refused with Mbed at configuration. The Wolf profile also needs a Zephyr patch for its TLS socket backend that this repository does not store, and the route a product takes is an open owner decision (option B, a Zephyr fork in your own manifest, is recommended): [HTTPS composition](../https-composition.md#how-a-product-applies-the-wolfssl-patch). The public wolfSSL and wolfSSH are offered under GPL-3.0-or-later or a commercial licence: [product composition](../product-composition.md), licence bullet.

3. **Set the Kconfig symbols.** The table [below](#kconfig) lists the web and SSH symbols that Crux defines. `zephyr/Kconfig` has others, such as `CRUX_CLI` and `CRUX_DEVELOPMENT_IMAGE`, which the command line contract describes. The network, TLS credentials, PSA algorithm, key type and file system symbols, but not the locks of the PSA core (see below), come from the profile files that the test images use, which are the reference: [`tests/native/management_composition/profile-psa.conf`](../../tests/native/management_composition/profile-psa.conf), [`tests/native/web_https/mbed.conf`](../../tests/native/web_https/mbed.conf) or [`wolf.conf`](../../tests/native/web_https/wolf.conf), and [`tests/native/management_services/prj.conf`](../../tests/native/management_services/prj.conf). **For SSH** the reference list is the one in [`tests/native/management_ssh/CMakeLists.txt`](../../tests/native/management_ssh/CMakeLists.txt): it adds [`tests/native/tls_offload_probe/wolf.conf`](../../tests/native/tls_offload_probe/wolf.conf) and [`components/ssh/ports/zephyr/wolf-ssh.conf`](../../components/ssh/ports/zephyr/wolf-ssh.conf). The module refuses `CONFIG_CRUX_SSH` unless `CONFIG_WOLFSSH_SETTINGS_FILE` is `crux_wolfssh_settings.h`, which `wolf-ssh.conf` sets. **SSH also needs the security event core at link time** (since [#317](https://github.com/wonny-labs/crux-pilot/issues/317)): the access adapter calls `crux_security_event_emit`, so an image that selects `CONFIG_CRUX_SSH` must link the core, or it does not link. `CONFIG_CRUX_ACCESS` builds it, because it selects `CONFIG_CRUX_SECURITY_EVENT`; a composition that gets Access some other way links the core itself. **The locks of the Mbed profile's PSA core** are a public module option, not a test file: set `CONFIG_CRUX_PSA_THREADING=y` (**Experimental**), as the snippet below does. `CONFIG_CRUX_ACCESS` refuses an Mbed profile image without locks, and the refusal names this option. A product that has locks of its own sets `CONFIG_TF_PSA_CRYPTO_USER_CONFIG_FILE` to its header instead and leaves this option off.

## From `docs/management-in-a-product.md`: section "Kconfig"

| Symbol | Default | What it sets | Read by |
| --- | --- | --- | --- |
| `CRUX_WEB` | off | The web adapter. Selects the Zephyr HTTP server with header capture, wildcard resources and status phrases. Needs `NETWORKING`. Defines the composition target `crux::web_zephyr` for `<crux/web_zephyr.h>` (ADR-0004 phase 1a, Experimental), which declares `crux_web_start()`; the target is rejected in a portable consumer. | Module |
| `CRUX_ACCESS` | off | **Experimental** ([ADR-0004](../decisions/0004-product-composition-of-management-services.md), phase 0). Builds Access, the credential store and the security events, which are wired to each other, and registers them with the Zephyr link. **Selects** `CRUX_CREDENTIAL`, `CRUX_SECURITY_EVENT`, `CRUX_THREAD`, `CRUX_SYNC` and `CRUX_TIME`, so a product's `prj.conf` names this one symbol (ADR-0004 C6). Starts nothing. Defines the portable targets `crux::access`, `crux::credential_store` and `crux::security_event` (ADR-0004 phase 1a). The configuration is refused unless it has the Mbed profile of PSA Crypto with its locks (`CRUX_PSA_THREADING`), a Crux File provider, `CRUX_LOGGING` and `HWINFO`. | Module |
| `CRUX_CONFIG_SERVICE` | off | **Experimental** (ADR-0004 phase 0, slice 2). Builds the Configuration service and the Configuration core. Needs `CRUX_ACCESS`. **Selects** `CRUX_CONFIGURATION_CORE` and `CRUX_SYNC` (Access already brings Thread and Time). Starts nothing. Defines the portable target `crux::config_service`. Without the Settings File selection there is no save provider: a save returns `CRUX_CONFIG_SERVICE_ERR_STORE` with `CRUX_CONFIG_ERR_NOT_SUPPORTED` in the report's `failed_result`. | Module |
| `CRUX_MGMT_STATUS` | off | **Experimental** (slice 2). Builds the status service and its System, Time, network, credential and event sources. Needs `CRUX_ACCESS`, and the configuration refuses an image without `CRUX_SYSTEM` or `CRUX_NETIF`. **Selects** `CRUX_CONFIGURATION_CORE`, `CRUX_SYNC` and `CRUX_TIME`. Defines the portable target `crux::mgmt_status` (ADR-0004 phase 1a). | Module |
| `CRUX_NETWORK_SETTINGS` | off | **Experimental** (ADR-0004 phase 0, slice 3). Builds the network settings service and its check. Needs `CRUX_ACCESS` and `CRUX_CONFIG_SERVICE`. **Selects** `CRUX_THREAD` and `CRUX_SYNC`. The apply port is the application's (ADR-0004 C3), declared in `<crux/network_settings_apply_port.h>`: an image without one does not link, unless the next symbol is set. Builds no serial command. Defines the portable target `crux::network_settings` (ADR-0004 phase 1a). | Module |
| `CRUX_TLS_CERTIFICATE` | off | **Experimental** (slice 3). Builds the TLS certificate module, its X.509 encoder and its PSA ports. Needs `CRUX_ACCESS`. **Selects** `CRUX_SYNC`. Registers nothing with Zephyr's TLS credentials: the application does (ADR-0004 C4). Starts nothing. Defines the portable target `crux::tls_certificate` for `<crux/tls_certificate.h>` and `<crux/tls_certificate_start.h>`, the header that carries the key (phase 1a). | Module |
| `CRUX_FILE_SERVICE` | off | **Experimental** (slice 3). Builds the file service core. Needs `CRUX_ACCESS`. **Selects** `CRUX_SYNC`. Defines the portable target `crux::file_service` (ADR-0004 phase 1a). | Module |
| `CRUX_REBOOT` | off | **Experimental** (slice 3). Builds the reboot service, its sleep and its reset over `crux_system_reset()`. Needs `CRUX_ACCESS`, and the configuration refuses an image without `CRUX_SYSTEM`. **Selects** `CRUX_CONFIGURATION_CORE`, `CRUX_THREAD` and `CRUX_SYNC`. The policy is the application's. Defines the portable target `crux::reboot` (ADR-0004 phase 1a). | Module |
| `CRUX_WEB_SESSION` | off | **Experimental** (ADR-0004 phase 0, slice 4). Builds login, sessions and request forgery protection, with the password verification port over PSA Crypto. Needs `CRUX_ACCESS` and `CRUX_WEB`. **Selects** `CRUX_THREAD` and `CRUX_SYNC`. The login and logout routes are the application's to name (`CRUX_WEB_SESSION_ROUTES`). Starts nothing. Defines the portable target `crux::web_session` for `<crux/web_session.h>` (ADR-0004 phase 1a): ordinary service API, not a composition interface. | Module |
| `CRUX_WEB_MANAGEMENT` | off | **Experimental** (slice 4). Builds the JSON of the status and configuration routes and the save worker, and with `CRUX_NETWORK_SETTINGS` the JSON of the network routes. Needs `CRUX_WEB_SESSION`, `CRUX_CONFIG_SERVICE` and `CRUX_MGMT_STATUS`. **Selects** `CRUX_THREAD` and `CRUX_SYNC`. The routes are the application's to name (`CRUX_WEB_MANAGEMENT_*_ROUTES`). Starts nothing. Defines the portable target `crux::web_management` for `<crux/web_management.h>` (ADR-0004 phase 1a): ordinary service API, not a composition interface. | Module |
| `CRUX_CLI_CONSOLE` | off | **Experimental** (ADR-0004 phase 1b). Needs `CRUX_CLI` and `CRUX_ACCESS`. Links the serial console with its login and first-account setup (`!setup`) and the provider of the command line's event port over the security events, and registers them with the Zephyr link. Defines the composition target `crux::cli_zephyr` for `<crux/cli_zephyr.h>`, which declares `crux_cli_serial_start()`; the target is rejected in a portable consumer. The console owns the UART of the devicetree alias `crux-serial0`. | Module |

## From `docs/management-in-a-product.md`: section "SSH"

Clients table:

| Client | What ran | Source |
| --- | --- | --- |
| PuTTY, interactive | **None.** PuTTY 0.81 `psftp` ran in the author's attempts to reproduce the per-file-limit failure, and a `psftp -sshrawlog` run was requested from the tester. | [SFTP design](../sftp-design.md#winscp) |

Algorithms table:

| Kind | Offered | Refused, and shown to be refused |
| --- | --- | --- |
| User keys | `ssh-ed25519`, `ecdsa-sha2-nistp256` (P-256 only). **No RSA**, by owner decision. | `ssh-rsa` and `rsa-sha2-256` (refused by OpenSSH in the cases), P-384 and P-521 (refused by the Host wire checks). Access accepts the same two types and refuses a P-384 or P-521 key as `INVALID_ARGUMENT` ([Issue #316](https://github.com/wonny-labs/crux-pilot/issues/316), [Access contract](../access-contract.md#user-key-types-issue-316)). |

## From `docs/management-in-a-product.md`: section "Registering a user key"

On 2026-11-14 the owner decided [Issue #318](https://github.com/wonny-labs/crux-pilot/issues/318) as option C: **now, a product registers SSH user keys itself, and this section says how; a command-line command and a web API that do it come later, only when a consumer needs one.** No such command or route exists today. Only test code calls `crux_access_account_add_key` today; no product or image code does. The test composition's call is the example below.

| Question | Answer, from `components/access/include/crux/access.h`, `components/access/src/access_accounts.c` and the test composition |
| --- | --- |
| What is the key? | An SSH public key blob, compared byte for byte, of type `ssh-ed25519` or `ecdsa-sha2-nistp256`: the wire-format blob that the base64 field of an OpenSSH public key line holds, not the text line. Access accepts only those two types, as the owner decided on [Issue #316](https://github.com/wonny-labs/crux-pilot/issues/316) (option A): a P-384 or P-521 blob is `INVALID_ARGUMENT`, because SSH never offers those curves. A store that an earlier revision saved with such a key reads as unusable, so no account can log in until it is recovered ([Access contract](../access-contract.md#user-key-types-issue-316)). The key is only checked for its form: SSH verifies the signature, and the Mbed profile has no SSH, so a key registered on an Mbed image is stored and unused. Any other type or form is also `INVALID_ARGUMENT`, and `CRUX_ACCESS_KEY_SIZE_MAX` (192 bytes by default, [Access contract](../access-contract.md)) bounds the blob |

## From `docs/management-in-a-product.md`: section "Browsers"

| Browser | What ran | Not shown |
| --- | --- | --- |
| **Safari** | **Never run against firmware.** One observation on 2026-11-08, by hand, **on the mock server of the web examples only**: a `Secure` cookie set over plain HTTP did not work in Safari. Firmware over HTTPS in Safari was not run. | Everything else. The 825-day rule for TLS server certificates is untested: [TLS certificate](../tls-certificate.md), decision A. [Web session](../web-session.md#decisions-taken-without-an-answer) |

## From `docs/management-in-a-product.md`: section "Security assumptions"

| Assumption | State | Source |
| --- | --- | --- |
| TLS 1.3 only. | Declared, an owner decision (A2) | [HTTPS composition](../https-composition.md) |

## From `docs/management-in-a-product.md`: section "What CI covers"

| Area | In CI | Only local |
| --- | --- | --- |
| Module integration of Access, the store and the events (`CRUX_ACCESS`, Experimental) | `host.yml` runs all of `tests/build`, so the static checks of `test_management_module.py`, for Access, the store, the events, the Configuration service and the status service. Existing `zephyr.yml` and `psa-crypto.yml` steps still build and pass with the module's symbols unset. | `scripts/test-management-module.sh` (the `native_sim` fixture `tests/native/management_module`, the four refusals and the default-off check) has no workflow step yet, because adding one edits `.github/`. Ran on native arm64 Linux for this change. |

## From `docs/management-in-a-product.md`: section "Owner decisions"

Decisions that need the owner and decisions the owner has already taken, with where each is recorded and its state. Nothing here is decided by this guide: a decided row records the owner's decision, and the issue holds the quote.

| Decision | Recorded in | State |
| --- | --- | --- |
| How a product applies the wolfSSL patch (option B recommended) | [HTTPS composition](../https-composition.md#how-a-product-applies-the-wolfssl-patch), approval A3 | Open |
| Criterion 1 with one case open on Wolf | [HTTPS composition](../https-composition.md#approvals-needed), approval A1, [Issue #280](https://github.com/wonny-labs/crux-pilot/issues/280) | Open |
| TLS 1.3 only | [HTTPS composition](../https-composition.md#approvals-needed), approval A2 | Open |
| A separately approved physical run on RT1060-EVKB | [HTTPS composition](../https-composition.md#approvals-needed), approval A4 | Open |
| A server deadline for trickled headers | [Issue #268](https://github.com/wonny-labs/crux-pilot/issues/268) | Decided 2026-11-14, option B (a header-phase deadline, as a build-local patch); not implemented yet |
| Certificate validity, the private key as PKCS #8 in RAM, `psa_sign_hash` outside the qualified subset, event identifiers | [TLS certificate](../tls-certificate.md#owner-decisions-needed-before-adoption), decisions A to D | Open |
| Which user key types Access accepts and SSH offers | [Issue #316](https://github.com/wonny-labs/crux-pilot/issues/316) | Decided 2026-11-14, option A (Ed25519 and P-256 only); built, and tested on the Host only. A stored P-384 or P-521 key makes the store unusable ([Access contract](../access-contract.md#user-key-types-issue-316)) |
| Emitting the SSH security events | [Issue #317](https://github.com/wonny-labs/crux-pilot/issues/317) | Decided 2026-11-14: emit `ssh.auth_limit` and `ssh.host_key_missing` (option A), refusals before the first callback stay reserved (option B); built, and tested on the Host only |
| How a product registers an SSH user key | [Issue #318](https://github.com/wonny-labs/crux-pilot/issues/318) | Decided 2026-11-14, option C: the product registers keys itself ([how](#registering-a-user-key)); a command and a web API only when a consumer needs one |
| Events for a refused CSRF token or `Origin` | [Issue #319](https://github.com/wonny-labs/crux-pilot/issues/319) | Decided 2026-11-14, option A with rate limiting; built, and tested on the Host only |
| Events for file operations refused with no identifier | [Issue #270](https://github.com/wonny-labs/crux-pilot/issues/270) | Direction accepted 2026-11-14; the row-by-row table in the [SFTP design](../sftp-design.md#each-refusal-and-its-event) was independently reviewed and merged as a proposal (#411); no event is implemented yet |
| Passing the terminal flag to the SSH `exec` callback | [Issue #269](https://github.com/wonny-labs/crux-pilot/issues/269) | Open |
| Replacing the host key and printing its fingerprint | [wolfSSH provider](../ssh-wolf-provider.md#decisions-for-review), decision 24 | Not built |
| Safari: no issue tracks running firmware in it | [Web contract](../web-contract.md#header-capture) | No issue yet |

