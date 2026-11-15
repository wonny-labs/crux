# The management image for RT1060-EVK Rev B on the Mbed TLS profile

Status: **Experimental.** A management image that is meant to **run** on the board, built here and never flashed or reset by anything in this repository. **Nothing in this document has run on a board, and the cross-build has not run either.** What has run is the static Host checks of the image's text. A cross-build check exists (`scripts/test-management-mbed-rt1060.sh build`) and no workflow runs it yet; everything on the board is for the team that runs it. It uses no Wolf stack, no SSH and no GPL source: HTTPS only, on Mbed TLS with TF-PSA-Crypto (Apache-2.0 option).

It is a different image from the [bench image](rt1060-management-image-feasibility.md) of the Wolf profile. That image carries safety gates and **refuses to start by design**, and this one has none of them: see [what is different](#how-it-differs-from-the-bench-image).

## What it contains

| Part | In the image | Notes |
| --- | --- | --- |
| HTTPS web management | The web adapter on Zephyr's HTTP server, TLS 1.3 only, port 443, the session routes, status, configuration, network settings and reboot routes, and one packaged page | Plain HTTP is not offered. The page is a placeholder: a product serves its own frontend. |
| Access and the credential store | The Access core with three roles (`viewer`, `operator`, `administrator`) and the store with two sealed slots | The store is **not confidential** on the current basis ([credential store](credential-store.md)). |
| TLS certificate | The certificate model makes a P-256 key **on the device** at start and a self-signed certificate that names `crux-rt1060` and the board's address | The module registers nothing with Zephyr: `composition.c` hands the material to Zephyr's TLS credentials before the listener starts ([TLS certificate](tls-certificate.md)). |
| Security events | The event core, drained to Crux Logging on the console UART (LPUART1, 115,200 baud) | There is no route to read events. They appear as Logging lines and as counts in `GET /api/v1/status`. |
| Status, configuration | The status service and the Configuration service, with one reference parameter, `device.name` | A save answers `not_supported`: no save provider exists ([management APIs](web-management-apis.md)). |
| Network settings | The service and its routes, with the apply port that applies nothing | `PUT /api/v1/network` answers `501`. The address is static from Kconfig. |
| File service | One area `files` on the RAM disk | The web has no file route. |
| Reboot | `GET` and `POST /api/v1/system/reboot` with the policy "always allow" | The routes are tested on the Host only, and **a POST resets the board**. |
| Entropy | The i.MX RT TRNG through its driver, with the fail-closed correction of Zephyr's Mbed TLS glue | See [entropy](#entropy). |
| Storage | A FatFs volume on a **RAM disk** of 512 KiB in SDRAM | **Nothing persists across a reset**: accounts, keys, certificate and configuration are made again at each boot. No card driver is in the image, so no card can be mounted or formatted. |

Not in the image: SSH, SFTP, the serial console and command line (composed in no image), a first-account setup step, certificate replacement, events over HTTP, persistence of anything.

## Where it lives, and why

`samples/management_rt1060_mbed/`. The repository keeps images that are built and never run under `tests/zephyr/` (compile checks, and the bench image, whose directory name keeps the evidence of its first stage), and images that a team builds and runs under `samples/`. This one is meant to run, so it is a sample. It is also shaped as a product would be: the services come from the Zephyr module under their Kconfig symbols (ADR-0004 phase 0), and `app` compiles none of their sources. What `app` holds is its own composition (`src/composition.c`), the route sources (the route table belongs to the image, so the module cannot build it), a RAM disk mount and the entry point. It includes public `<crux/...>` headers wherever one exists. The exceptions are listed [below](#taken-from-tests-and-private-roots) and a test fails if a new one is added.

## Build

In the Linux Dev Container, with the workspace set up by `scripts/bootstrap-zephyr.sh` and the two Apache-2.0 crypto projects enabled:

```bash
west config manifest.project-filter -- +mbedtls,+tf-psa-crypto
west update
```

The default image, with no account:

```bash
west build -p always -b 'mimxrt1060_evk@B//qspi' crux-pilot/samples/management_rt1060_mbed
```

The same with the test first account ([below](#the-first-account)):

```bash
umask 077; head -c 24 /dev/urandom | base64 | tr -d '\n' > ~/crux-mbed-password   # outside every git work tree
CRUX_MBED_MGMT_PASSWORD_FILE=~/crux-mbed-password west build -p always -b 'mimxrt1060_evk@B//qspi' \
    crux-pilot/samples/management_rt1060_mbed -- -DCONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT=y
```

`scripts/test-management-mbed-rt1060.sh` builds both, checks the configuration and the linked image, and checks the refusals ([what is verified](#what-is-verified-and-what-is-not)). The static checks run alone with `scripts/test-management-mbed-rt1060.sh static`.

Kconfig settings of the image: `CRUX_MBED_MGMT_IPV4_ADDRESS` (default `192.168.77.2`), `CRUX_MBED_MGMT_IPV4_NETMASK` (default `255.255.255.0`) and the test form. The address is the only one the interface has: the image has no DHCP and no IPv6, and it stops at boot if the interface holds another IPv4 address.

## The first account

**The gap.** The first account may be created on the serial channel only, and no image composes the serial console, so there is no supported way to create one in this image. Without a first account nobody can log in. The serial setup step is not built ([management in a product](management-in-a-product.md)).

**The test form.** `CONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT` is **off by default and named as test only**. Nothing selects it. When it is on, the build reads a password from the file named by the environment variable `CRUX_MBED_MGMT_PASSWORD_FILE` and refuses a missing file, a file inside any git work tree, a length outside 16 to 128 bytes and any byte that is not printable ASCII (so no trailing newline). It embeds the bytes by an assembler `.incbin`, so the plaintext is in the binary's read-only data and in no generated source, log or configuration file. At each boot, on an empty store, the image creates the account `admin` with the role `administrator`. The password is never printed. **The plaintext is in Flash**: a bench form, not a product's.

## Flash and run

Flashing is the team's, with the standard NXP or Zephyr tools: `west flash` with a runner that supports this board (`west flash --help` lists them), or the NXP tools. The board's boot-mode switches and the dedicated link are described in [networking physical preparation](networking-physical-preparation.md). This repository's programming driver and board guards belong to the bench image's approval path and do not cover this image.

- Link: board `192.168.77.2/24` and the host `192.168.77.1/24` on one cable, unless you changed the Kconfig address.
- Console: LPUART1 at 115,200 baud. LPUART3 is left free for the Crux serial console that a later phase composes, so keep any other console off it.
- Put the board's previous image back after the run, by your own method.

### Expected console lines

In this order, each possibly behind a log prefix. The fingerprint and the TRNG node name are the board's.

```text
MBED-MGMT image=crux-mgmt-rt1060-mbed board=mimxrt1060_evk@B/mimxrt1062/qspi tls=mbedtls address=192.168.77.2 test-first-account=1
CRUX-ENTROPY first-read=ok source=random@400cc000 compatible=nxp,kinetis-trng bytes=32 status=0 device-ready=1
MBED-MGMT file-medium ram-disk 524288 B in SDRAM, formatted at this boot, mounted=1: nothing persists across a reset
MBED-MGMT TEST ONLY first account created: user=admin role=administrator
MBED-MGMT certificate sha256=AA:BB:...:FF source=generated
MBED-MGMT ready https://192.168.77.2:443/
```

Without the test form, the fourth line is `MBED-MGMT no first account: this image has no serial setup step, so nobody can log in...`. Security events follow as Logging lines when someone logs in.

A failed step prints a detail line (`MBED-MGMT step failed: <name>`, or `MBED-MGMT TEST ONLY first account failed: result=<n>` for the test form, or the `CRUX-ENTROPY first-read=failed` line for the random read) and then one `MBED-MGMT refusing to start: ...` line, and nothing after it runs. The refusals, in order: the first random read failed (no key or listener is made), the static address could not be set, a core service did not start, the first account could not be made, a service did not start. The certificate's fingerprint is read before the listener starts, so an unreadable certificate is a failed step and the listener never starts. **No `MBED-MGMT ready` line within a minute of power-up is a failure to report, not to retry blindly.**

### What a team checks

These checks are the team's to run and record. None has run.

| Check | How | Expected |
| --- | --- | --- |
| The certificate is the one the console printed | `openssl s_client -connect 192.168.77.2:443 </dev/null 2>/dev/null \| openssl x509 -noout -fingerprint -sha256` | The same SHA-256 as the console line. This is trust on first use: compare it before trusting the certificate. |
| TLS 1.3 only | `openssl s_client -connect 192.168.77.2:443 -tls1_2 </dev/null` | The handshake fails. |
| Key shares | `openssl s_client ... -tls1_3 -groups P-256`, then `-groups X25519:P-256` | The first completes. The second completes on P-256 after a HelloRetryRequest, because the Mbed profile has no X25519 (a client that offers X25519 alone is refused): [HTTPS composition](https-composition.md#helloretryrequest-on-mbed). |
| Login and status | The two-request login of [web session](web-session.md), then `GET /api/v1/status` | `202` then `success`, and a status list. |
| Wrong password | One wrong password, then the right one | A refusal, then success. Six wrong passwords put the right one inside a delay window. |
| Reboot | `POST /api/v1/system/reboot` with a session of `administrator` | The board restarts and the boot lines come again, with a new certificate and an empty store. |

## What depends on the board

The image is written for **RT1060-EVKB Rev B** (`mimxrt1060_evk@B//qspi`) and refuses to configure for any other board target. The SoC part is the i.MX RT1062, which a product board shares. This table says what is the SoC's and what is the EVKB's, so that a team with its own RT1062 board knows what to change. Nothing here has run on any board.

| Part | Where it is set | SoC (RT1062) or board | A product board with an RT1062 changes |
| --- | --- | --- | --- |
| Board check | `CMakeLists.txt` refuses any `CONFIG_BOARD_TARGET` but the EVKB's, and the RAM disk provider's Kconfig (`CRUX_FILE_FATFS_RT1060_RAM_DISK`) depends on that board | Board | The check and the provider's `depends on`, or a board file that this repository does not have |
| Entropy | The TRNG (`zephyr,entropy = &trng`, `ENTROPY_MCUX_TRNG`), the fail-closed correction and the boot check | **SoC** | Nothing, unless the board's devicetree changes the chosen entropy node |
| Device ID for the credential store | `CONFIG_HWINFO` | **SoC** (the unique ID) | Nothing |
| Flash part and boot | QSPI NOR, XIP from `0x60000000`, the boot header of the board files | Board (the flash part, its size and the boot-mode switches) | The board's flash configuration and boot data |
| RAM | All RAM of this configuration is the 32 MB SDRAM (`zephyr,sram = &sdram0`): the RAM disk, the Mbed TLS heap, the stacks and the network buffers sit there, and every size is chosen for that | Board | A board with on-chip RAM only must re-size all of them: 512 KiB for the RAM disk alone is half of the 1 MB of on-chip RAM of an RT1062 |
| Console and logging | `target.overlay`: Crux Logging and `printk` on LPUART1 at 115,200 baud. LPUART3 is left free for the Crux serial console of a later phase | Board (which pins and which UART the board brings out) | `target.overlay`: the UART node and its speed |
| Ethernet | `samples/controller/zephyr/m3-network.overlay` (the ENET MAC with a fixed local MAC address, the PHY monitor by polling because the PHY interrupt line is dropped, and the EVKB's LED removed because its GPIO is the PHY reset), `CONFIG_ETH_NXP_ENET_RX_BUFFERS` and the buffer counts of `prj.conf` | Board (the PHY part, its reset and interrupt lines, the MAC address) | The overlay for the product's PHY, MAC address and reset pin. The MAC address in that file is a fixed local one: give each unit its own |
| Static address | `CONFIG_CRUX_MBED_MGMT_IPV4_ADDRESS` and `_NETMASK` | Image setting | Both, for the product's network |
| Storage | A RAM disk (`ram_disk.overlay`), nothing persists. The SD card and eMMC are not used and the card driver is off | Board | A product that needs accounts and keys to survive a reset needs a non-volatile File provider (microSD or eMMC compositions exist in the repository and are separate, not composed here), and a decision about confidentiality of the store |
| Watchdog and reset | The `crux-watchdog0` alias to `wdog0` in `target.overlay`, used by Crux System and the reboot route | SoC peripheral, board alias | The alias, if the board uses another watchdog |

A product also replaces what this image leaves to it: the first-account step, its own frontend folder, the certificate names, the roles and the permission policy in `composition.c`, and the sizes that a run on its own board measures.

## Entropy

The image makes every key from the i.MX RT TRNG through Zephyr's entropy driver, and from nothing else. The rules, each enforced:

| Rule | Where |
| --- | --- |
| No test generator, no fake entropy source, and the TRNG driver and the PSA entropy route must be set | `CMakeLists.txt` stops the configuration, and the check script reads the resolved configuration |
| A failed TRNG read fails PSA and does not fall back to `sys_rand_get()`, which is not cryptographic on this board | `crux_mbedtls_fail_closed_entropy()` applies a build-local, hash-checked copy of Zephyr's glue ([PSA qualification, entropy failure](psa-crypto-qualification.md#entropy-failure)) |
| The first random read happens before any key, certificate or listener, and a failure stops the image | `main.c`, with the boot check `tests/zephyr/entropy_boot` and its `CRUX-ENTROPY` line |

If the TRNG is not available, the image prints the refusal line and starts nothing. The key is made inside `crux_tls_certificate_start()`, after the read.

**What stays open** ([PSA qualification](psa-crypto-qualification.md#entropy-failure)): whether a TRNG read can fail in practice, a TRNG start failure, a reseed after a good start, the quality and rate of the source, and the boot path of the Mbed TLS initialisation on this board. The Mbed profile is not qualified beyond the subset of Crux's own PSA use.

## How it differs from the bench image

| Item | Bench image (Wolf) | This image (Mbed) |
| --- | --- | --- |
| Runs | **Refuses to start**, by `CRUX_BENCH_RUN_REFUSED` | Runs |
| Guards | Declaration, three guard levels, frozen Zephyr copy, manifest, UART report | None of them. Plain checks of the configuration. |
| Zephyr | A patched copy (TLS socket patch and the TCP sequence number fail-closed patch) | The stock Zephyr of the workspace. **The TCP initial sequence number has no fail-closed patch here**: with a failed entropy source Zephyr's keyed sequence number is not guaranteed. No listener exists before the first random read passes, which narrows this and does not remove it. |
| Programming path | Profile and driver of `tests/target/` (not registered) | The team's own |
| Listener address | Bound to one address by a setting | Every address of one interface that holds one IPv4 address |
| First account | A password file, as plaintext, under the bench declaration | The same mechanism, as a test form that is off by default |
| Profile | Wolf for HTTPS, plus SSH and SFTP | Mbed, HTTPS only |

The bench image, its declaration, its refusal and its tools are not changed.

## Taken from tests, and private roots

Two pieces and three configuration files come from test directories, because no public form exists yet. A new one fails `tests/build/test_management_mbed_rt1060_image.py`.

| Taken | From | Why |
| --- | --- | --- |
| The locks of the Mbed profile's core (`crux_tf_psa_threading.c`, the user configuration) | `tests/native/management_composition/composition/tf_psa_threading` | The module refuses `CONFIG_CRUX_ACCESS` without them and has no option for them; a later phase decides how a product gets them |
| The Mbed profile, the PSA settings and the locks configuration | `tests/native/tls_offload_probe/mbed.conf`, `tests/native/management_composition/profile-psa.conf` and `mbed-threading.conf` | The settings the `native_sim` images run |
| The boot check of the random source | `tests/zephyr/entropy_boot` | One `CRUX-ENTROPY` line and a stop on failure |

| Private root | Why it remains |
| --- | --- |
| The web session and web management directories, and the web adapter's | The web lifecycle (`crux_web_session_init`, `crux_web_management_init`, `crux_web_start`) has no public header on `main` yet. ADR-0004 phase 1a publishes `<crux/web_session.h>`, `<crux/web_management.h>` and `<crux/web_zephyr.h>`; when they are on `main` this image switches to them and the list shrinks. |
| The Access adapter directory, **only with the test form** | The first account has no public header by decision (ADR-0004 section 2) |

## What is verified, and what is not

| Item | State |
| --- | --- |
| The image's static rules: Mbed profile, no Wolf or SSH symbol, no bench symbol, the services selected, entropy before any key, the listener after the certificate, only the listed private includes, the test form off and absent from `prj.conf` | **Host**, `tests/build/test_management_mbed_rt1060_image.py` |
| Cross-build for `mimxrt1060_evk@B//qspi`, the resolved configuration, the linked image's symbols, the test form's refusals | **Not run.** The check is `scripts/test-management-mbed-rt1060.sh build`; no workflow runs it yet (the pull request names the one step to add). Until it has run, treat a compile or link error as possible. |
| Everything on the board: boot, the TRNG, the handshake and its time and memory, the stack of the HTTP thread (16,384 B, a first choice), the Mbed TLS heap (120,000 B, sized on `native_sim` for three clients), the network buffers (the bench's numbers), the generated key as the listener's credential, reboot, every client | **Not run** |
| The Mbed TLS listener with the generated certificate on any target | Not run: the `native_sim` images of the Mbed profile serve the declared test certificate |

Every `native_sim` result about these services holds for the protocol and the code, and none shows that anything is fast, small or safe on the board: [management in a product](management-in-a-product.md).

## Limits to know before a run

- The listener answers on every address of the one interface. Keep it on a dedicated link.
- Nothing is persistent and there is no way to create an account without the test form.
- The reboot route resets the board on request. Its event and wait are tested on the Host only.
- A certificate and key are new at every boot, so a client sees a new fingerprint each time.
- The certificate's validity starts at the module's fixed default date because no clock is trusted, and has no expiry.
- Safari and Edge were never run against firmware, and a frontend is the product's: [management in a product](management-in-a-product.md#browsers).
