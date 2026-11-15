# MCUboot crypto backend: a size comparison for plan decision D9

| Field | Value |
| --- | --- |
| Status | **Record of a measurement, for the owner's decision. It adopts nothing.** Which backend MCUboot uses is plan decision D9, taken under [ADR-0006](../decisions/0006-cryptographic-dependency-policy.md) by the project owner. |
| Date | 15 November 2026 |
| Work package | Phase 1 of the [secure boot development plan](secure-boot-development-plan.md), decision D9 ("with a size and boot-time build comparison") |
| Builds on | [Boot composition](../boot-composition.md) (RT1060-EVK Rev B, RAM load with revert, ECDSA P-256), the [boot and update investigation](../boot-update-investigation.md) (#141) |
| Evidence labels | **Verified by build** (read from a CI job that exited 0, run and commit named below), **Verified on pinned source** (read from a file at the pinned revision), **Inference**, **Not measured**, **Not verified** |
| What was run | One CI job, three times while the variant set was found (section 2). No hardware, no key generated, no manifest change. |

## 1. Question

Plan decision D9: MCUboot's ECDSA P-256 verification can use MCUboot's bundled tinycrypt, Zephyr's Mbed TLS or PSA Crypto. Which should the composition use? The plan asks for a size and boot-time build comparison first. This record gives the size comparison and states what it cannot show. It does not choose.

## 2. Method

The script [`tests/target/compare-mcuboot-crypto-backends.sh`](../../tests/target/compare-mcuboot-crypto-backends.sh) builds the composition of the boot composition page (same four board files, same arguments, application `samples/controller/zephyr`, signed with MCUboot's public test key) once per variant. Only the MCUboot image's configuration differs, through one small file per variant in [`tests/target/mcuboot-crypto/`](../../tests/target/mcuboot-crypto/). It is unwired and a one-off decision input, not a regression check.

| Input | Value | Label |
| --- | --- | --- |
| Zephyr, SDK | v4.4.2 (`dccb0959`), SDK 1.0.1 | Verified by build (job log: "Zephyr version: 4.4.2", "Found toolchain: zephyr 1.0.1") |
| MCUboot | v2.4.0, `6d3b3d2c` | Verified in repository (`west.yml`) |
| Mbed TLS, TF-PSA-Crypto | `mbedtls` `a3e190fe`, `tf-psa-crypto` `dc575a2d`, both in the opt-in group `crux-secure-management`. The script fetches only these two projects of that group, by name, and no other project of it. | Verified in repository (`west.yml`) |
| Backend choice | `BOOT_ECDSA_IMPLEMENTATION` in `boot/zephyr/Kconfig`: tinycrypt (the default), `BOOT_ECDSA_MBEDTLS` ("Use mbedTLS"), `BOOT_ECDSA_CC310` (needs an nRF part, not applicable), `BOOT_ECDSA_PSA` ("Use PSA crypto") | Verified on pinned source |
| CI runs | Run [43741573025](https://github.com/wonny-labs/crux-pilot/actions/runs/43741573025) (commit `61c47b80`): tinycrypt, Mbed TLS, PSA. Run [43743517339](https://github.com/wonny-labs/crux-pilot/actions/runs/43743517339) (`25f649cd`): two more PSA variants. **Run [43745097021](https://github.com/wonny-labs/crux-pilot/actions/runs/43745097021) (`1b68920f`): the complete set. The numbers below are from this run.** The runs used a temporary workflow file on the pull request branch, removed before merge, so no workflow change reaches `main`. | Verified by build |

The baseline is built twice: before the two crypto projects are fetched (the composition as it is on `main`), and after, to show what the presence of the modules alone does.

## 3. Results

Verified by build, run 43745097021. The sizes of the bootloader image `mcuboot/zephyr/zephyr.bin`, its headroom in the 128 KiB `mcuboot` flash partition, and the sections of its ELF file (`arm-zephyr-eabi-size`):

| Variant | Built | `zephyr.bin` (B) | Headroom in 128 KiB (B) | Against the baseline (B) | text / data / bss (B) |
| --- | --- | --- | --- | --- | --- |
| tinycrypt, crypto modules not fetched (the composition on `main`) | yes | 51,668 | 79,404 | 0 | 51,412 / 256 / 14,339 |
| tinycrypt, crypto modules fetched | yes | 51,668 | 79,404 | 0 | 51,412 / 256 / 14,339 |
| Mbed TLS, `BOOT_ECDSA_MBEDTLS` | **no**, does not configure | - | - | - | - |
| PSA, `BOOT_ECDSA_PSA` alone | **no**, does not compile | - | - | - | - |
| PSA and `CONFIG_MBEDTLS=y` | **no**, does not compile | - | - | - | - |
| PSA, `CONFIG_MBEDTLS=y`, `CONFIG_MBEDTLS_PSA_CRYPTO_C=y` | yes | 69,620 | 61,452 | +17,952 (+34.7 %) | 69,352 / 268 / 16,212 |
| the same and `CONFIG_ENTROPY_GENERATOR=y` | yes, identical | 69,620 | 61,452 | +17,952 | 69,352 / 268 / 16,212 |

The 51,668 B of the baseline equals the figure of the [boot composition page](../boot-composition.md), built earlier in another run. Having the two crypto projects in the workspace changes nothing in the tinycrypt build.

Memory regions that the MCUboot link reports (second "Memory region" block of each job log, read by hand: the script's collector keeps the application's block, which is why it is not in the script output. The script is left as it ran):

| Variant | FLASH (of 128 KB) | RAM (of 511 KB) | ITCM |
| --- | --- | --- | --- |
| tinycrypt | 51,668 B (39.42 %) | 14,656 B (2.80 %) | 8,544 B |
| PSA with the Mbed TLS module | 69,620 B (53.12 %) | 16,576 B (3.17 %) | 8,544 B |

So the PSA build uses 1,920 B more RAM and 17,952 B more flash. The SDRAM, which holds the application, is untouched by either (0 B used in the bootloader's own link). The application's signed image does not depend on the backend: it is 33,051 B and 33,050 B in the two PSA builds and 33,051 B in the baseline (the one-byte difference is the variable DER length of the randomised ECDSA signature, [Stage 8](../evidence/boot-update/stage8-reproducibility-and-signing.md)), it verifies with `imgtool verify` and the public test key in every build, and the [inspector's `fit` decision](../boot-image-inspection.md) for the 3 MiB slot at `0x20000` reads `fits` in every build. That is a check that the comparison left the application alone; it says nothing about the bootloader, whose binary has no image header (the inspector's `image` command reports "no image" for it).

### Why four variants did not build

Verified by build (the first error lines of each job log):

| Variant | First failure | Reading |
| --- | --- | --- |
| `BOOT_ECDSA_MBEDTLS` | Kconfig aborts: `MBEDTLS_ECP_NIST_OPTIM` has direct dependencies `(PSA_WANT_KEY_TYPE_ECC_KEY_PAIR_BASIC && MBEDTLS) ... with value n, but is currently being y-selected` by `BOOT_ECDSA_MBEDTLS`, and "Deprecated symbol `MBEDTLS_MD` is enabled". | The backend's `select` lines are written for the legacy Mbed TLS symbols; the Mbed TLS that Zephyr pins is the 4.x line (`MBEDTLS_VERSION_4_x`, built here), whose Kconfig no longer satisfies them. **Inference:** it would need more than settings (a change in MCUboot or Zephyr), because Mbed TLS 4.0 moved its public API to PSA. Not tried beyond the one line. |
| `BOOT_ECDSA_PSA` alone | `psa/crypto.h: No such file or directory` while compiling `bootutil` | Zephyr's `modules/mbedtls/CMakeLists.txt` at v4.4.2 adds the TF-PSA-Crypto include directories only when `CONFIG_MBEDTLS` is set, and the PSA option does not select it (Verified on pinned source, the CMake condition; the cause is the reading that the next variant confirmed). |
| PSA and `CONFIG_MBEDTLS=y` | `ssl_misc.h:24: unknown type name 'mbedtls_error_pair_t'` while compiling the Mbed TLS library (`mps_trace.c`, `debug.c`, and others) | With the module on, Zephyr builds the whole Mbed TLS library. It compiled once `CONFIG_MBEDTLS_PSA_CRYPTO_C=y` was set, which MCUboot's PSA option does not select (it selects `PSA_CRYPTO_C` of Zephyr's PSA Kconfig). **Inference** for why that symbol matters. |
| the same with `CONFIG_ENTROPY_GENERATOR=y` | the same | This variant was added in case the PSA core needed an entropy driver switched on; the build shows that it does not fail for that reason, and the later pair shows the symbol is on anyway in the working configuration (`CONFIG_ENTROPY_GENERATOR=y` appears in both resolved configurations). |

The two working PSA variants have the same resolved configuration for the symbols read (`BOOT_ECDSA_PSA`, `MBEDTLS`, `MBEDTLS_BUILTIN`, `MBEDTLS_PSA_CRYPTO_C`, `MBEDTLS_PSA_CRYPTO_LEGACY_RNG`, `ENTROPY_GENERATOR`), which is why their sizes are identical.

## 4. What this does not show

- **Boot time: Not measured.** It needs a board, and no hardware was used. No estimate is given. The verification work of the two backends (tinycrypt's P-256 code against the PSA core's) is a difference this record has no number for.
- **Whether the PSA build boots.** It links. Whether the PSA core initialises at boot, takes entropy from the board's random-number unit, and verifies a signature on the RT1060 is **Not verified**. Zephyr's `zephyr_entropy.c` is compiled unpatched in this build, while Crux replaces that file with a fail-closed copy in the management images ([ADR-0006](../decisions/0006-cryptographic-dependency-policy.md), section 1), so adopting PSA in the bootloader also raises the question which entropy glue it uses. Not examined.
- **Heap and stack use at run time.** The link reports static RAM only (+1,920 B). MCUboot's Kconfig sets a heap size only under `MBEDTLS_ENABLE_HEAP` and only for RSA and Ed25519, and the resolved configuration of the working PSA build has no `MBEDTLS_HEAP_SIZE` or `MBEDTLS_ENABLE_HEAP` line, so how the PSA core gets working memory for ECDSA was not examined. **Not verified.**
- **Other signature types and hash algorithms.** Only ECDSA P-256 with SHA-256 was built, as in the composition.
- **A measurement of the failures' fixability.** The failed variants were tried with the settings listed above and no others. That they fail with these settings is not a statement that no setting makes them build.

## 5. Facts for the decision

These are the facts that bear on D9 that the repository and the pinned sources show, without a recommendation in them.

| Fact | Source | Label |
| --- | --- | --- |
| MCUboot bundles its own copy of tinycrypt in `ext/tinycrypt` (Intel Corporation 2017, BSD licences by text) and uses it by default for ECDSA P-256. It needs no Zephyr crypto module. | Pinned MCUboot tree; [boot and update investigation](../boot-update-investigation.md), Stage 1 | Verified on pinned source |
| The upstream tinycrypt repository `intel/tinycrypt` is archived on GitHub; its last push was 5 March 2024. MCUboot's copy is vendored, so the archive does not remove it, and it means the copy gets fixes only if MCUboot makes them. | GitHub API, read on 15 November 2026 | Verified (public source) |
| Crux's crypto pins are the two Mbed TLS projects and the wolf projects. ADR-0006 (accepted 14 November 2026) sets a policy for them (a security-fix path for the two Mbed TLS pins) and lists MCUboot as a dependency that would need the same review, undecided. MCUboot's bundled tinycrypt is not one of those pins. | ADR-0006, "The recommendation in brief", section 1 and section 5 | Verified in repository |
| The Mbed TLS pair sits in the opt-in group `crux-secure-management`, which also holds GPL stacks. A bootloader built with the PSA variant needs those two projects in the workspace, and the script fetches them by name. How a product would consume that without the GPL projects is the product composition guide's group question. | `west.yml`; [product composition guide](../product-composition.md) | Verified in repository; the product consequence is an **Inference** |
| ADR-0006 notes 13 and 5 named advisories in the upstream releases newer than the Crux pins (4.1.1, 1.1.1), by title mostly about TLS, X.509 and handshake paths. A bootloader that verifies one ECDSA signature uses a small part of the library. Which of them reach that part was not reviewed. | ADR-0006, section 2 | Reported; the reach is **Not verified** |
| The size cost of PSA is 17,952 B of flash and 1,920 B of RAM in a 128 KiB partition that has 79,404 B free with tinycrypt. | Section 3 | Verified by build |

## 6. Neutral recommendation for the owner

D9 is the owner's decision; nothing here is adopted. The comparison leaves three honest options.

| Option | What it gives | What it costs or leaves open |
| --- | --- | --- |
| A. Keep tinycrypt for M8, the backend that is built and checked today | The only backend of the three that builds at the pinned revisions with the settings tried, and the smallest (51,668 B, 79,404 B free). No new pin enters the bootloader. The board evidence of M8 is for exactly the composition on `main`. | Depends on a vendored copy of an archived upstream project. No Crux policy covers it until the dependency review that ADR-0006 mentions. Revisit when MCUboot or Zephyr changes the default or when that review is done. |
| B. Adopt PSA over Zephyr's Mbed TLS | One crypto line for the bootloader and the application, inside ADR-0006's security-fix path. | +17,952 B of flash (+34.7 %) and +1,920 B of RAM. Two settings beyond the backend choice (`CONFIG_MBEDTLS=y`, `CONFIG_MBEDTLS_PSA_CRYPTO_C=y`) that MCUboot's option does not select. Boot behaviour and time unmeasured. Needs a decision on the entropy glue and on the group coupling above. A new bootloader build and its board evidence. |
| C. Decide after the M8 board evidence of option A | Takes the choice off the critical path of the first boot experiment, and the evidence then also gives a boot time for tinycrypt to compare a PSA build against. | The plan asks for D9 before M8 board evidence; this option moves that date and needs the owner's agreement. |

If the owner wants the smallest change to what is already built and reviewed, A with the dependency review as a follow-up fits. If the owner wants one crypto line and a single security-fix path across bootloader and application, B is the option, with the measurements it still needs (a boot on the board, the entropy glue). Mbed TLS through `BOOT_ECDSA_MBEDTLS` is not available at the pinned revisions with these settings. This is a reading of the numbers, not a decision, and the owner may weigh other facts.

## 7. Not verified

- Boot time of any backend, and whether the PSA build boots (section 4).
- That `BOOT_ECDSA_MBEDTLS` cannot be made to build with other settings.
- Run-time heap and stack use of the PSA path.
- Which advisories of the upstream releases reach the bootloader's use of the library.
- Any statement about hardware: nothing here ran on a board.

## 8. Reproduce

`tests/target/compare-mcuboot-crypto-backends.sh` in the Linux development environment after `scripts/bootstrap-zephyr.sh` (it changes the local workspace, as its header says), or the temporary workflow of the pull request branch at commit `1b68920f`. The host shape test is `tests/build/test_mcuboot_crypto_comparison.py`.
