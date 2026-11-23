# Patches and web READMEs before the verbosity trim

Status: historical. Passages without another home, removed from `patches/zephyr/README.md`, `web/README.md` and `web/api/README.md` in the November 2026 verbosity trim, word for word from revision 57f9142 (links not adjusted). The current pages are [`patches/zephyr/README.md`](../../patches/zephyr/README.md), [`web/README.md`](../../web/README.md) and [`web/api/README.md`](../../web/api/README.md).

## `patches/zephyr/README.md`: first-failure observation and the deferred-output evaluation

## First-failure observation

The first physical corrected candidate booted but did not reach Link readiness
within the original 15-second window. No application exchange or post-round PHY
observation ran. The failure does not identify a poisoned bus or the initial cause.
A default-off `CONFIG_CRUX_M3_MDIO_FAILURE_TRACE` adds observation only to the
PHY diagnostic composition. Append `mdio_failure_trace.conf` as well as the existing
network, PHY diagnostic and completion-correction configuration files.

The native driver retains its first wait failure in CPU-accessed BSS, publishing
a valid flag last under single-core IRQ protection. A private getter copies that
record under the same protection; it is not a public Crux interface. The record
includes the actual wait branch, operation/PHY/register, result, transaction cycle
observations, a monotonic timestamp, sequential read-only MAC fields and the native
semaphore count. It performs no extra MDIO operation or register write. Later
poison errors never overwrite the first failure or reset the failed state.

The sample stays quiet until a retained failure exists, then reports native
MDIO/PHY readiness with that one complete record through its existing output path. It owns no MDIO mutex and
prints after releasing snapshot IRQ protection. It adds no thread, logging backend,
command, retry or timing limit. Ordinary images do not compile the getter/record.
The generated native translation unit uses scoped `-Wall -Wextra -Werror`; other
upstream translation units retain their warning selection.

The cycle fields are unsigned 32-bit modular observations; multiple wraps cannot
be reconstructed. The frequency is the native counter frequency at observation.
The millisecond timestamp is also 32-bit and wraps. These clocks are available in
the selected POST_KERNEL initialisation path; this is not permission to reuse the
observer in earlier boot phases. Fields are sequential, not a simultaneous hardware
snapshot or proof of IRQ history. Diagnostic output occurs after retention and can
perturb later execution. No WCET, physical cause or corrected Link behaviour is
inferred from these observations. The unchanged physical qualification remains
required after any eventual fix.


The private `deferred_output.conf` is a separate opt-in software evaluation for
that diagnostic. Native `LOG_PRINTK` queues raw records before the direct printk
spinlock path; one native UART backend performs output later. This avoids a custom
logging service but adds a finite 4096-byte buffer and 2048-byte logger stack at
priority 14. It does not change the MDIO patch, timeout or poison policy. It has
not been adopted for Ethernet or integrated qualification. Native_sim fixtures
exercise long 64-bit records and actual forced-overflow loss reporting; output
loss, incomplete records and unexpected configurations remain failures. UART wait,
IRQ dispatch and native tick rounding are relevant source hypotheses, not an
established physical cause of the earlier failure.

## `patches/zephyr/README.md`: wolfSSL derivation and licence narrative

The secure management work uses a wolfSSL backend behind the Zephyr TLS socket API. Its patch is not stored in this
repository. New files in it carry an Apache-2.0 header. The upstream repository has no licence file, and its README says
that ports of projects other than wolfSSL follow each project's own licence, which for Zephyr is Apache-2.0. It does not name
this patch, and the patch also calls wolfSSL, so Crux refers to it by revision until its terms are confirmed.

The first derivation of the tree digest of the patched copy (2026-11-14, on macOS, interim, [evidence](../../docs/evidence/rt1060-patched-zephyr-first-freeze-20261114/README.md)) recorded
the facts about the core patch that this repository holds, and nothing of its text: it touches nine files (seven modified, two added, no rename,
mode change or binary hunk), and `patch` applies 3 of the 71 hunks of `sockets_tls.c` to v4.4.2 only with fuzz. The paths and the hashes of the results
are in `tests/zephyr/management_rt1060_compile/bench_declaration.json`. Recording them decides nothing about the licence.

Upstream generated these for Zephyr 4.4.1. On v4.4.2, `git apply --check` of the core patch fails in `sockets_tls.c`, and
`git apply --3way` merges it with no conflict. The result differs from the patched 4.4.1 file by exactly the upstream changes
between those tags. It runs on `native_sim` in the [TLS probe](../../docs/native-management-composition.md#tls-probe), on a patched copy of the tree that
`scripts/prepare-wolf-tls-zephyr.sh` makes for a test, and it has run on nothing else. How a product composition applies it without editing the Zephyr
checkout is decided under Issue #185. The wolfSSL, wolfSSH and wolfPSA projects are fetched only when a workspace enables the
`crux-secure-management` group. wolfSSL and wolfSSH are offered under GPL-3.0-or-later or a commercial licence. wolfPSA's source
states GPL-3.0-or-later only. A vendor article says it has the same licence options as wolfSSL, and its commercial terms need
confirming with the vendor. Binaries built with these stacks are subject to those terms when distributed. The `mbedtls` and `tf-psa-crypto` projects in the same group are
Apache-2.0 OR GPL-2.0-or-later.

## `patches/zephyr/README.md`: owner decisions and per-pull-request test notes

- Mbed TLS entropy: "Owner decision of 6 November 2026, recorded in the qualification record."
- ISN: "Owner decision D-c of 9 November 2026, row C11 of the RT1060-EVKB bench image."; "the upstream status was not checked."
- HTTP header deadline: "Owner decision of 14 November 2026, option B of Issue #268."; the results of the `native_sim` suites "are recorded in the pull request that adds the patch"; "its declared patch list has not been changed here"; "The upstream Kconfig option is the intended end state and needs its own approval."

## `web/README.md`: flows and evidence tables

## Core and Advanced flows

Core and advanced flows are in both examples and in the shared browser cases, with service tests underneath. The advanced flows
are described in [the advanced flows](../docs/web-advanced-flows.md).

| Flow | Kind | Preact example | Angular example |
| --- | --- | --- | --- |
| Sign-in and sign-out | Core | Built | Built |
| Session expiry | Core | Built | Built |
| Forced password change | Core | Built | Built |
| Status | Core | Built | Built |
| Simple configuration update | Core | Built, on the mock | Built, on the mock |
| Network settings | Advanced | Built | Built |
| Reboot | Advanced | Built | Built |

## Evidence

Each state is recorded on its own, and none stands in for another. The flow-by-flow table is in the
[implementation design](../docs/plans/web-frontend-implementation.md#core-and-advanced-evidence).

| State | What it shows | Today |
| --- | --- | --- |
| Mock | The examples and the client against the specification, over plain HTTP on the loopback address | Run in CI |
| Host | The management services in C and their web routes, through a fake transport | Run in the Host CI job |
| `native_sim` | Real TLS, sessions and limits with a browser | Both examples packaged and run over HTTPS in Chrome, #220: [end-to-end design](../docs/e2e-native-220.md) |
| Physical | RT1060-EVKB, with separate approval | Not run |

Host and `native_sim` functional completion is an interim result. Physical evidence stays tracked separately and is not
waived.


Lifecycle scripts stay off through `.npmrc`, and esbuild works without its install step.

## `web/api/README.md`: sources paragraph

The sources are the [web design](../../docs/plans/secure-management-web-design.md) and the
[access contract proposal](../../docs/plans/access-contract-proposal.md), with the status proposal, the frontend
design and the gate record as they merge. The access contract replaces the web design's login status codes, and the
frontend design and the status proposal refine its routes.


