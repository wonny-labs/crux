# Evidence: the Mbed HTTPS image on the v4.4-branch crypto revisions (PR #416, step 7)

Recorded 15 November 2026. This is the "one recorded build of the Mbed HTTPS image keeping its full `.config`" that step 7 of
[the dependency review](../../dependency-review-mbed-tls-4.1.1.md#plan-for-the-pin-move-evidence) asks for before the pin
move merges. It is `native_sim` evidence. **Nothing physical ran**, and no board, no hardware and no GPL source was involved.

## What ran

`scripts/test-native-composition.sh e2e-mbed`, unchanged, in the Linux Dev Container image (`.devcontainer/Dockerfile`, amd64
emulated on an arm64 machine, 6 CPUs, 3.8 GiB), at Crux revision `250205e8b852b1f0ce871fd16d0b03fb7a7b29f9` (`dirty: false` in
every results file). Exit status 0. The script started 09:51:43Z and ended 10:37:21Z (45 min 38 s).

| Item | Value |
| --- | --- |
| Zephyr | `dccb09599635bdff17633fa7e9dab014b91dce90` (v4.4.2), board `native_sim/native/64` |
| `mbedtls` | `098e120afb51877ed814bdc04443890ae12e0642` |
| `tf-psa-crypto` | `fa92349590a54959ee2efc21b668e5afdb144726` |
| Tools | west 1.4.0, cmake 3.28.4, Node.js 24.22.2 (checksum verified against `SHASUMS256.txt`), Google Chrome 157.0.8103.78 (`google-chrome-stable_current_amd64.deb`, SHA-256 `4d740636b5c96f687798602c5aad6a5a270f44dd02e48db0638ae77aa4867b1b`) |

## Result

| Check | Result |
| --- | --- |
| Image check `check-composition-image.py --services`, Preact and Angular images | 50 listed symbols from their real sources, no test double, `mbed` profile, 12 component routes, one HTTP service: pass on both |
| `server_checks.py` (no browser), `server-*-results.json` | 23 checks, 0 failures, on each image |
| Browser cases against the real server in Chrome, `e2e-*-browser-results.json` | Preact: 118 cases, **46 pass, 0 fail, 72 skipped**. Angular: the same, 46 pass, 0 fail, 72 skipped. A skipped case is one that forces an answer through the mock or needs the mock control, and each carries its reason in the log |
| The mock's run of the shared cases, `e2e-mock-browser-results.json` | 218 of 218 pass. Not TLS, session or limit evidence |
| Unit tests `test_e2e_server_checks.py` and `test_project_sample.py` | 22 tests, OK |

The pass counts equal those of the earlier run at `docs/e2e-native-220.md` (Preact 46, and Angular 45 then, 46 now with the
Angular network settings screen). The skipped count is higher because the shared advanced cases of #243 skip on a device with
the reason `needs the mock control`, as that document says.

## The full resolved `.config`

`mbed-https-image-full.config` is the complete `zephyr/.config` of the Mbed-profile HTTPS image (627 set symbols among 1425 `CONFIG_` entries, SHA-256
`536c57ef0b7134fb6d8be69450915d06f659ec42517f605a54bd28bde10e5d1f`). The Preact and Angular images resolved to the same file
(`cmp` shows no difference). The symbols of the review's section 3.2, as read:

| Symbol | In the full `.config` | The review's reading |
| --- | --- | --- |
| `MBEDTLS_SSL_SESSION_TICKETS` | not set | no session tickets: **confirmed** |
| `MBEDTLS_KEY_EXCHANGE_PSK_ENABLED`, `..._ECDHE_PSK_ENABLED` | both not set (config lines 302 and 303). The ECDHE-PSK and EC J-PAKE cipher suites are not set either (for example `MBEDTLS_CIPHERSUITE_TLS_ECDHE_PSK_WITH_AES_256_CBC_SHA384` at line 390 and `MBEDTLS_CIPHERSUITE_ECJPAKE_WITH_AES_128_CCM_8` at line 393), and `PSA_WANT_ALG_JPAKE` (line 202) and `PSA_WANT_ALG_TLS12_ECJPAKE_TO_PMS` (line 229) are not set. `MBEDTLS_KEY_EXCHANGE_ECJPAKE_ENABLED` is absent from the file: it is a Kconfig symbol that `depends on PSA_WANT_ALG_JPAKE`, which is off (read in a Zephyr v4.4.0 checkout at the lines the review cites, not re-read at v4.4.2) | no PSK, no J-PAKE: **confirmed** |
| `MBEDTLS_SSL_TLS1_3_KEY_EXCHANGE_MODE_PSK_ENABLED`, `..._PSK_EPHEMERAL_ENABLED` | both not set (lines 308 and 310). Only `..._EPHEMERAL_ENABLED` is `y` (line 309) | the TLS 1.3 key exchange is ephemeral only: **confirmed** |
| `MBEDTLS_SSL_EXTENDED_MASTER_SECRET` | not set (line 318) | no extended master secret: **confirmed** |
| `MBEDTLS_SSL_PROTO_DTLS` | not set | no DTLS: **confirmed** |
| `MBEDTLS_SSL_PROTO_TLS1_2`, `..._TLS1_3` | both `y` | the profile compiles both: **confirmed** (the listener refuses TLS 1.2 by its own setting, see `docs/e2e-native-220.md`) |
| `MBEDTLS_ECP_NIST_OPTIM` | not set | row 16 does not apply at this Zephyr tag: **confirmed** |
| `MBEDTLS_CIPHER_ALL_ENABLED` | not set | ChaCha20 is not selected through it: **confirmed** |
| `PSA_WANT_ALG_CHACHA20_POLY1305`, `PSA_WANT_KEY_TYPE_CHACHA20` | not set | no ChaCha20: **confirmed** |
| `PSA_WANT_ALG_RSA_*` (OAEP, PKCS1V15 crypt and sign, PSS), `PSA_WANT_KEY_TYPE_RSA_*` | all not set | no RSA: **confirmed** |
| `PSA_WANT_ECC_MONTGOMERY_255`, `..._448` | not set | no X25519 or X448, so row 17 (Everest) has nothing to act on: **confirmed** |
| `MBEDTLS_PKCS7_C`, `MBEDTLS_RSA_C`, `MBEDTLS_PK_C` | not Kconfig symbols (absent from the file), and the file cannot show them. `MBEDTLS_PK_C` is derived in `config-tf-psa-crypto.h` from `MBEDTLS_PK_PARSE_C`, and `CONFIG_MBEDTLS_PK_PARSE_C=y` (line 367), so it is **on**. `MBEDTLS_PKCS7_C` is never defined (review section 3.2). `MBEDTLS_RSA_C` is not defined by Zephyr's headers as read in the v4.4.0 checkout. The preprocessed headers of the built image were not kept. RSA has no `PSA_WANT` symbol set | consistent with the review: no PKCS #7, no RSA. `PK_C` on is the parsing the TLS 1.3 certificate path uses, and changes no verdict |
| `PSA_WANT_ALG_ECDH`, `PSA_WANT_ECC_SECP_R1_256` | both `y` | **A fact the review did not state.** ECDH on P-256 is on, which the TLS 1.3 ephemeral key exchange needs. No advisory verdict of section 4 relied on ECDH being off: row 17 needs a Montgomery curve, which is off |
| `MBEDTLS_X509_CRT_PARSE_C` | `y` | selected by the ephemeral TLS 1.3 mode, as the review reads |

**No symbol of the full `.config` contradicts a "not applicable" verdict of section 4.** This reads the symbols the review named.
It is not a re-assessment of the advisories, and `config-mbedtls.h`'s derived macros were not dumped (the preprocessed header
was not kept).

## What was not run, and how this differs from the recorded script

- **Not run:** `e2e-wolf`, any wolf profile, any RT1060-EVKB build or board run, the Twister tests and the other `native-composition`
  modes. The `psa-crypto` workflow of the PR runs the `mbed` mode and the PSA qualification on the same pins: its result is in the PR's checks, not here.
- **`run.log` is an excerpt:** the script prints only a few lines of each browser run (the full per-case output is in the three `e2e-*-browser.log` files). The module revisions in the table above come from `west.yml` at `250205e8` and the `west update`, and `west list` output was not kept.
- **The script was not edited.** It deletes each build directory and keeps no `.config`. A shell function that copies
  `zephyr/.config` out before the `rm` ran, loaded through `BASH_ENV` for this run only, kept the files. The copy is the
  resolved `.config` of the images the script built and tested.
- **West workspace:** `west init -l`, `west config manifest.project-filter -- +mbedtls,+tf-psa-crypto`, and
  `west update --narrow --fetch-opt=--depth=1` in a private Docker volume with a clone of this branch at `250205e8`
  (shallow fetches, so the module history is not present). The wolf projects were not fetched.
- **Downloads:** Node.js 24.22.2 from nodejs.org (checksum verified), the Chrome stable deb from dl.google.com
  (147,497,676 bytes), the Python tools and `npm ci` packages from PyPI and the npm registry, and the project clones from GitHub.
- **One run only.** No repetition, and no timing claim beyond the numbers above: other work shared the machine.
