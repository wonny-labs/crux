# Secure management: a review guide

Status: a guide for a reviewer who must judge the secure communication and management stack of Crux for a real product, from the documents alone. It adds no behaviour and no decision. Each claim cites the code, a test or a document that was read on `origin/main` for this guide, and a claim that could not be checked is marked **unverified**. The bench checks that go with it are in the [board test procedure](secure-management-board-test-procedure.md). Terms are in [the glossary](management-glossary.md), and the product integration steps are in [secure management in a product](management-in-a-product.md).

**Nothing in the management stack has run on a board.** Every result is a Host test, a `native_sim` run or a compile for RT1060-EVKB. The one board composition, the RT1060-EVKB bench image, refuses to start in `main()` and has never been programmed: [what is verified, and where](#what-is-verified-and-where).

| Word | Meaning here |
| --- | --- |
| **Host** | A Host test, usually on fakes of the layers around the code under test |
| **`native_sim`** | The code a product links ran on Zephyr's `native_sim`, with real cryptography and real clients, on the host's TCP stack and a **test-only entropy source** ([what "real" means there](psa-crypto-design.md#what-real-means-on-native_sim)) |
| **Compile** | Compiled (and for the bench image, linked) for `mimxrt1060_evk@B//qspi`. Nothing ran. |
| **Board** | Ran on a physical board. **No management result has this level.** |

## The security model as built

### Trust boundaries

```mermaid
flowchart LR
    subgraph net["Network: untrusted"]
        browser["Browser or curl"]
        sshc["SSH and SFTP client"]
    end
    subgraph local["Local access: trusted for setup"]
        serialc["Serial console user"]
        reader["Anyone who can read Flash, the medium or the chip ID"]
    end
    subgraph device["Device image"]
        https["HTTPS listener<br/>TLS 1.3, one suite"]
        sshl["SSH listener<br/>wolfSSH, Wolf profile only"]
        console["Serial console<br/>composed in no image"]
        access["Access: accounts, roles,<br/>8 session slots, delays"]
        events["Security events<br/>RAM ring, to Logging"]
        store[("Credential store<br/>two sealed slots<br/>NOT confidential")]
    end
    browser -->|"TLS"| https
    sshc -->|"SSH"| sshl
    serialc -.->|"not built"| console
    https --> access
    sshl --> access
    console -.-> access
    access --> store
    access --> events
    reader -.->|"reads every secret"| store
```

| Boundary | What protects it | Source |
| --- | --- | --- |
| Network to HTTPS | TLS 1.3 only, `TLS_AES_128_GCM_SHA256`, no plain listener and no redirect; a missing certificate means nothing listens | [HTTPS composition](https-composition.md#declared-tls-profile), [no plain listener](https-composition.md#no-plain-http-listener-and-no-redirect) |
| Network to SSH | wolfSSH with a fixed algorithm list, `max_auth_attempts` 3, a 30 s login timer, 4 connections | [Product guide, SSH](management-in-a-product.md#ssh), [Kconfig](management-in-a-product.md#kconfig) |
| Channels to Access | Every channel logs in through Access, which holds one session table, one delay table and the role check | [Access contract](access-contract.md) |
| Access to storage | The credential store seals each slot with a key derived from the device ID; it is **not confidential** against someone with the medium and the chip ID | [Credential store](credential-store.md#limits) |
| Serial | Provisioning of the first account is refused on every origin but serial | `components/access/adapter/crux_access_adapter.h` (`crux_access_provision_first_account`), [ADR-0004, phasing](decisions/0004-product-composition-of-management-services.md#phasing-and-the-licence-boundary) |

### Accounts, roles and sessions

| Item | As built | Source |
| --- | --- | --- |
| Roles | Crux holds the mechanism; the **product supplies the role table** (`crux_access_policy_t`). The test compositions define `guest`, `viewer`, `operator` and `administrator`, with an idle limit of 15 min and an absolute limit of 8 h. | `tests/native/management_composition/composition/crux_native_management.c` (`roles`, `policy`) |
| Permissions | Strings compared exactly, for example `status.read`, `events.read`, `access.manage`, `tls.manage` | `components/mgmt_status/include/crux/management_status.h`, `components/security_event/include/crux/security_event.h`, [TLS permissions](tls-certificate.md#permissions) |
| Session slots | 8, slot 0 reserved for serial, so 7 shared by HTTPS and SSH; 3 per account across both channels, a fourth ends the oldest | `components/access/src/access_port.h`, [session limits](ssh-integrated-image.md#session-limits-when-both-listeners-are-busy) (`native_sim`) |
| Password verifier | PBKDF2 through PSA; `CRUX_ACCESS_VERIFIER_ITERATIONS` is 10,000, **an unmeasured placeholder** | [Access bounds](access-contract.md#bounds) |
| Login delays | 5 free failures, then delays from a 1 s base up to a 60 s cap, kept in tables per source and per name (32 buckets each) | [Access bounds](access-contract.md#bounds), `tests/access/security.c` |
| Equal treatment | A wrong password, an unknown name and a disabled account give the same answer on every channel | [Web rules](web-session.md#rules), [serial console](cli-contract.md#serial-console), `tests/access/security.c` |
| User keys for SSH | Access accepts Ed25519 and ECDSA P-256, **and also P-384 and P-521**, which SSH never offers ([open item](#open-items)). No command or route registers a key; the product calls `crux_access_account_add_key` itself. | `components/access/src/access_record.c`, [registering a user key](management-in-a-product.md#registering-a-user-key) |

### Web login, CSRF and `Origin`

A login is two requests: `POST /api/v1/session` queues the attempt and answers `202` with an identifier, and the client polls `GET /api/v1/session/attempt/{id}` with `X-Crux-Request: 1`. Password verification runs on one worker, one attempt at a time. The full flow is in [web session](web-session.md#how-a-login-flows).

```mermaid
sequenceDiagram
    participant B as Browser
    participant S as Session layer
    participant A as Access
    B->>S: POST /api/v1/session (Origin checked before the body)
    S-->>B: 202 {"id"}, connection closed (password cleared)
    S->>A: verify on the worker
    B->>S: GET .../attempt/{id}, X-Crux-Request: 1
    S-->>B: success, Set-Cookie crux_session (HttpOnly) and XSRF-TOKEN
    B->>S: state change: cookie, Origin, X-XSRF-TOKEN
    S->>S: session, then Origin, then token, then idle refresh
```

| Control | As built | Shown by |
| --- | --- | --- |
| Cookies | `Secure; SameSite=Strict; Path=/`, the session cookie `HttpOnly`, no persistent expiry | `tests/web/session/login.c`, `tests/native/web_session/test_driver.py` |
| Tokens | 256 bits from the PSA random port; stored as SHA-256 hashes | [Web rules](web-session.md#rules) |
| CSRF | Every method but `GET` needs `X-XSRF-TOKEN` equal to the `XSRF-TOKEN` cookie; else `403 csrf_rejected` | `tests/web/session/sessions.c` |
| `Origin` | Scheme, `://` and the request's own `Host`, compared whole, or an exact list from the composition; else `403 origin_rejected` | `tests/web/session/sessions.c`, `login.c` |
| Headers | CSP, `nosniff`, `no-referrer`, `no-store`; **no HSTS and no CORS header** | [Web rules](web-session.md#rules) |
| Events for a refused CSRF token or `Origin` | **None on `main`.** An open pull request, #449, emits `web.csrf_rejected` (0x0601) and a new `web.origin_rejected` (0x0605), at most 3 per kind in 60 s. **It was not merged when this guide was written.** | [Issue #319](https://github.com/wonny-labs/crux-pilot/issues/319), [PR #449](https://github.com/wonny-labs/crux-pilot/pull/449) |

### The credential store

| Item | As built | Source |
| --- | --- | --- |
| Contents | Accounts, device keys (the TLS key and the SSH host key) and the certificate, in two sealed slots on a Crux File provider | [Credential store](credential-store.md) |
| Confidentiality basis | `BASIS_DEVICE_ID_KEY`, declared with **no confidentiality**: someone who can read the medium and the chip ID can read every secret | `test_info_carries_the_declaration` in `tests/credential/conformance.c`, [limits](credential-store.md#limits) |
| Rollback | Not detected; losing both directory entries reads as empty and **reopens provisioning** (S6) | `test_accepted_limits`, `test_lost_directory_entries_reopen_provisioning` |
| Power loss | Walked byte by byte on a fake medium only; no real card under a cut | `tests/credential/faults.c`, [what is untested](credential-store.md#what-is-untested) |

### The TLS certificate

| Item | As built | Source |
| --- | --- | --- |
| Key and certificate | P-256 key from the store, self-signed certificate at first boot, valid from 2026-01-01 to 9999-12-31 by default | [What the device generates](tls-certificate.md#what-the-device-generates) |
| Upload | One DER certificate, checked for **format and key match only**: no chain, no signature, no dates, no revocation | [What an upload is checked for](tls-certificate.md#what-an-upload-is-checked-for), `tests/tls_certificate/install.c` |
| Private key in RAM | One PKCS #8 copy for the life of the program, handed to Zephyr's TLS credentials | [The private key](tls-certificate.md#the-private-key) |
| First connection | Trust on first use: compare the SHA-256 fingerprint that the composition prints | [The first connection](tls-certificate.md#the-first-connection) |
| Routes and commands | **None.** No web route and no command requests, installs or regenerates a certificate, or shows its fingerprint. | [Routes](management-in-a-product.md#routes), [CLI contract](cli-contract.md#what-exists) (`device fingerprint` not built) |
| What a listener serves | Every `native_sim` composition serves the **declared test certificate, whose key is public**. Only the bench image registers a generated certificate (`tests/zephyr/management_rt1060_compile/src/mgmt_start.c`, `tls_credential_add`), and it has not run. | [TLS certificate](tls-certificate.md#what-is-built-faked-and-untested) |

### Security events and the flood bound

Records go into a RAM ring and a low-priority thread writes each as one Logging line with the tag `crux.security`, for example `evt=access.login_failed seq=184 ... res=denied` ([log line](security-event-contract.md#log-line)). Nothing persists across a reset, and nothing is tamper-evident. `GET /api/v1/events` is **not built**; the read function it would use, `crux_security_event_read`, exists and needs `events.read`.

| Bound | Value | Source |
| --- | --- | --- |
| Ring | 32 records; routine (R) records dropped from 24 pending, change (C) records admitted until full | [Admission](security-event-contract.md#admission), `tests/security_event/ring.c` |
| Loss | Counted, reported as an `event.lost` line with `first` and `count` | [Loss](security-event-contract.md#loss) |
| Drain pacing | 4 lines, then a 100 ms pause | [Pacing](security-event-contract.md#pacing), `tests/security_event/drain.c` |
| Secrets | No password, key, salt or verifier in any record or line | `tests/security_event/secrets.c`, `tests/access/secrets.c` |
| Per-identifier rate limit | **None on `main`.** `ssh.auth_limit` has no rate bound of its own; the ring is the bound. | [SSH adapter port](security-event-contract.md#from-the-ssh-adapter-port) |
| Logging threshold | Must stay at `INFO` or more verbose (E6); **nothing enforces it** | [Limits](security-event-contract.md#limits) |

## The channels

| Channel | Stack | State | Licence note |
| --- | --- | --- | --- |
| HTTPS web | Zephyr HTTP server behind the Crux route table, on **either** TLS profile: Mbed TLS with TF-PSA-Crypto, or wolfSSL with wolfPSA | `native_sim` on both profiles. In CI on Mbed only. | Mbed TLS and TF-PSA-Crypto are Apache-2.0 OR GPL-2.0-or-later ([patches README](../patches/zephyr/README.md#wolfssl-tls-socket-backend)) |
| Command line over serial | `crux_cli` login loop and `!setup` over `crux_serial` | **Host only. Composed in no image.** LPUART3 wiring compiles for RT1060-EVKB (`tests/zephyr/cli_serial_compile`). | |
| SSH command line and SFTP | wolfSSH provider, Wolf profile only; `CONFIG_CRUX_SSH` is refused with Mbed | `native_sim` with OpenSSH 9.6; two recorded WinSCP runs ([SFTP design](sftp-design.md#winscp)) | See below |

**Licence of the Wolf profile.** wolfSSL and wolfSSH are offered under GPL-3.0-or-later or a commercial licence, and wolfPSA's source states GPL-3.0-or-later only. The Wolf profile also needs a Zephyr TLS socket patch from `wolfSSL/osp` that this repository does not store, because its terms are unconfirmed ([patches README](../patches/zephyr/README.md#wolfssl-tls-socket-backend)). A closed product that wants SSH or SFTP from this stack therefore needs a commercial licence, or another SSH stack. The route for applying the patch is open, with option B (a Zephyr fork in the product's own manifest) recommended ([HTTPS composition](https-composition.md#how-a-product-applies-the-wolfssl-patch)). **This guide does not decide any licence question.** The RT1060-EVKB bench image is built on the Wolf profile, so even its HTTPS checks need the Wolf stack; no board image on the Mbed profile exists in this repository.

## Threat model summary

| Threat | Control | Residual risk, as documented |
| --- | --- | --- |
| Password guessing over the network | Shared delay table, equal answers, one verification at a time | Four uncollected login results hold every attempt slot for 20 s, so one client can keep logins at `503` ([web decision 2](web-session.md#decisions-taken-without-an-answer)) |
| Cross-site request forgery | `SameSite=Strict`, synchronizer token, `Origin` check | No event on `main` ([#319](https://github.com/wonny-labs/crux-pilot/issues/319)) |
| Eavesdropping, downgrade | TLS 1.3 only, one suite; SSH without CBC, SHA-1 or `diffie-hellman` | Clients without TLS 1.3 cannot connect (by published support, not tested) |
| Impersonation of the device | Trust on first use of a printed fingerprint | No route shows the fingerprint; the composition must print it |
| Slow or silent clients | Bounds, not defences: 3 HTTP clients, a 2 s handshake stall each, 4 SSH connections held for 30 s | Trickled headers can hold a web slot for days ([#268](https://github.com/wonny-labs/crux-pilot/issues/268)); four silent SSH clients lock SSH out |
| Event flood hiding other records | Class R and C admission, counted loss | A flood costs other routine records; nothing is persisted |
| Physical access to the medium or Flash | None: the store is not confidential | Every secret is readable. The bench image also holds its first-account password in plaintext in Flash ([bench first account](rt1060-bench-first-account.md#what-the-image-holds)). |

The model rests on these **assumptions**, each from the cited document and none tested on a target:

1. An attacker on the network cannot read the device's medium, Flash or chip ID ([credential store](credential-store.md#limits)).
2. The entropy source of the target is sound. Every run so far used a test-only source, so no token or key strength is shown ([web session](web-session.md#what-is-not-verified)).
3. The person at the serial console during setup is trusted, and the first account comes from a password that person types, with nothing in the image ([what a product does instead](rt1060-bench-first-account.md#what-a-product-does-instead)).
4. Users compare the certificate and host key fingerprints on first connection.
5. The product binds the listeners to a management interface (`CONFIG_CRUX_WEB_BIND_ADDRESS`, `CONFIG_CRUX_SSH_BIND_ADDRESS`); by default they listen on every address.
6. The image has no Zephyr shell: the shell rule refuses `CONFIG_SHELL` in a management image that is not marked as a development image ([shell rule](cli-contract.md#zephyr-shell-rule)). No document records the image check on an image that sets `CONFIG_CRUX_WEB` or `CONFIG_CRUX_SSH`.

## What is verified, and where

| Area | Host | `native_sim` | Target compile | Board |
| --- | --- | --- | --- | --- |
| Access, roles, delays | Yes, `tests/access/` | Yes, real PSA ports | Inside the bench image | **No** |
| Credential store | Yes, `tests/credential/` | Yes, FatFs over a RAM disk | Inside the bench image | **No** |
| Security events | Yes, `tests/security_event/` | Yes: counts only, nothing on a wire | Inside the bench image, to LPUART1 | **No** |
| HTTPS, login, CSRF, `Origin` | Yes, `tests/web/session/` | Yes, both TLS profiles; browser runs in Chrome | Web adapter on Mbed in CI (`scripts/test-web.sh target mbedtls`); the bench image on Wolf, locally | **No** |
| TLS certificate | Yes, `tests/tls_certificate/` | Yes, generated and reloaded, but **not served** | Registration in the bench image only | **No** |
| Serial console, `!setup` | Yes, `tests/cli/` | **No** | LPUART3 wiring only, in CI | **No** |
| SSH command line, SFTP | Yes, fake provider | Yes, OpenSSH 9.6, local only (no workflow) | Inside the bench image | **No** |
| `ssh.auth_limit`, `ssh.host_key_missing` | Yes, `tests/ssh/access/security_events_test.c` | **No run shows a record** | Compiled in | **No** |

What exists for a board, exactly:

- **One bench image**, `tests/zephyr/management_rt1060_compile`: HTTPS, the command line over SSH and SFTP on the Wolf profile, address `192.168.77.2/24`, with four declared bench test forms: a test host key form, no time source, a RAM disk (nothing persists), and a first-account password embedded from a file. `CRUX_BENCH_RUN_REFUSED` is `ON` (`CMakeLists.txt`), so the image prints its banner and the `CRUX-ENTROPY` line and stops; `tests/build/test_management_bench_declaration.py` pins this. One local cross-build is recorded, not in CI ([bench plan](rt1060-bench-image-plan.md#the-image-that-was-built)).
- **A plan for a board run**, which is not an approval and has not run; nine blockers are listed, including the approval itself ([what blocks the plan](rt1060-bench-image-plan.md#what-blocks-the-plan-today)).
- No record under `docs/evidence/` shows a management image running on a board.

## Test evidence matrix

| Claim | Backed by | Level |
| --- | --- | --- |
| The CSRF token and `Origin` are checked on every method but `GET` | `tests/web/session/sessions.c`; `tests/native/web_session/test_driver.py` | Host, `native_sim` |
| Login replies do not reveal whether a user exists | `tests/web/session/login.c`; [web cases](web-session.md#tests) | Host, `native_sim` |
| The password does not stay in the server's buffers | `tests/web/session/login.c` (marker password) | Host |
| Sessions are shared and capped across HTTPS and SSH | `case_slots_with_both_busy`, `case_sessions_across_channels` in `tests/native/management_ssh/driver.py` | `native_sim` |
| No plain HTTP listener | [Listener check](https-composition.md#no-plain-http-listener-and-no-redirect); `case_ports` | `native_sim` |
| The store declares no confidentiality | `test_info_carries_the_declaration` | Host |
| A product core refuses the test-only store ports | `tests/credential/production_refuses.c` | Host |
| A malformed or mismatched certificate upload is refused and logged | `tests/tls_certificate/install.c`, `events.c`, `differential.c` | Host |
| No secret in an event | `tests/security_event/secrets.c` | Host |
| A routine flood cannot evict change records | `tests/security_event/ring.c`, `ring_small` | Host |
| SSH offers no RSA, CBC or SHA-1 | [Provider results](ssh-wolf-provider.md#results) | `native_sim` |
| `ssh.auth_limit` is reported once at the limit | `case_auth_limit_is_reported_at_the_limit` in `tests/ssh/conformance.c` | Host, fake provider only |
| No Zephyr shell in a management image | `scripts/check-management-shell.py`, `tests/build/test_management_shell.py` | Host, builds |
| The bench image refuses to start | `tests/build/test_management_bench_declaration.py` | Host |

## Open items

| Item | Current position | Status |
| --- | --- | --- |
| User key types ([#316](https://github.com/wonny-labs/crux-pilot/issues/316)) | Decided: option A, Access accepts only `ssh-ed25519` and `ecdsa-sha2-nistp256` | Not implemented: Access still accepts P-384 and P-521. Register only the two offered types. |
| Header deadline ([#268](https://github.com/wonny-labs/crux-pilot/issues/268)) | Decided: option B, a header-phase deadline as a build-local Zephyr patch; a reconnecting client still holds a slot for one period | Not implemented |
| Events for refused file operations ([#270](https://github.com/wonny-labs/crux-pilot/issues/270)) | Direction accepted: no event for an ordinary client's refusal, one rate-limited event for a session's bound of open files; the row table is in the [SFTP design](sftp-design.md#each-refusal-and-its-event) | The first criterion, a decision per row, is still open; no event implemented |
| A possibly false `ssh.auth_limit` on wolfSSH ([#317](https://github.com/wonny-labs/crux-pilot/issues/317)) | Emitting both SSH identifiers is built. A changed user name or a fatal `key_verified` result may end a connection with the same wolfSSH error, which would report a limit that was not reached; whether wolfSSH counts a refusal before a callback is also unknown | **Unverified** on wolfSSH ([decision 29](ssh-wolf-provider.md#decisions-for-review)); recommendation there: run `scripts/test-ssh-provider.sh` or a `native_sim` image |
| CSRF and `Origin` events ([#319](https://github.com/wonny-labs/crux-pilot/issues/319)) | Decided: option A with rate limiting | In open pull request #449, not on `main` at the time of writing |
| First account on a product | Accepted in [ADR-0004](decisions/0004-product-composition-of-management-services.md#phasing-and-the-licence-boundary) (C5): the serial first-account step comes before any board image ("phase 1b") | Not built: no image composes the serial console. The bench image's plaintext password is a bench test form only. |
| SSH user key registration ([#318](https://github.com/wonny-labs/crux-pilot/issues/318)) | Decided: option C, the product registers keys itself; a command and a route only when a consumer needs one | Documented; only test code calls `crux_access_account_add_key` |
| Host key holding and replacement | The test images keep the key in a static buffer that is never wiped; no command shows its fingerprint or replaces it | Not built ([provider decision 24](ssh-wolf-provider.md#decisions-for-review)) |
| Certificate registration in a product | The product's adapter registers the material with Zephyr's TLS credentials (ADR-0004 C4, option A1) | Only the bench image does it, compile only |
| TLS certificate decisions A to D | Validity, PKCS #8 in RAM, `psa_sign_hash` outside the qualified subset, event identifiers | Open ([TLS certificate](tls-certificate.md#owner-decisions-needed-before-adoption)) |
| HTTPS approvals A1 to A4 | Wolf late first read ([#280](https://github.com/wonny-labs/crux-pilot/issues/280)), TLS 1.3 only, the patch route, a physical run | Open ([HTTPS composition](https-composition.md#approvals-needed)) |
| wolfPSA conformance in CI ([#247](https://github.com/wonny-labs/crux-pilot/issues/247)) | Deferred until the wolfSSL patch question is settled; default CI fetches no GPL-3.0 stack | Open. The Wolf profile, SSH and SFTP have no CI run. |
| Terminal flag for SSH `exec` ([#269](https://github.com/wonny-labs/crux-pilot/issues/269)) | `ssh -t host command` gets LF only | Open |
| Integrated validation ([#197](https://github.com/wonny-labs/crux-pilot/issues/197)), client audit ([#195](https://github.com/wonny-labs/crux-pilot/issues/195)) | Need sizing of the web defaults, control jitter, a port scan, an algorithm audit, and board evidence | Open |
| Not built | `GET /api/v1/events`, web file transfer ([#188](https://github.com/wonny-labs/crux-pilot/issues/188)), a browser console ([#204](https://github.com/wonny-labs/crux-pilot/issues/204)), firmware upload over HTTPS or SFTP ([#191](https://github.com/wonny-labs/crux-pilot/issues/191), [#196](https://github.com/wonny-labs/crux-pilot/issues/196)), persisting a configuration or network change | Open |

The contract issues of milestone M10 (#177 to #182) and the web issues of M11 (#184 to #190) are still open although their code is merged. This guide did not check each one's remaining acceptance criteria: read the issue before treating its component as complete.

## What a reviewer should not assume

- That `native_sim` results say anything about speed, stack use, entropy or safety on a device. Stack sizes such as the 8,192 B Crux thread stack equal the tested images and are **not measured**.
- That the bench image is a product image. Its host key form, embedded password, RAM disk and missing time source are declared test forms, refused outside its declaration.
- That anything here is approved for a board. A board operation needs its own approval, which this guide does not give.
