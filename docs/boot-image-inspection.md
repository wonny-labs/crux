# Boot image inspection: a tool to read MCUboot images and trailers

> **Status:** A developer tool, not a Crux interface. `tests/target/inspect_boot_image.py` (bench tooling, beside the capture scripts) reads files and changes nothing; it has no stable contract and no support commitment.
> **Verified:** By host tests on synthetic images and trailers built in memory ([`tests/build/test_boot_image_inspect.py`](../tests/build/test_boot_image_inspect.py)). The image header, trailer offsets, trailer magic and slot state names follow the repository's trailer model and the image state contract proposal; the TLV magics, the TLV entry layout and the hashed range are the author's reading of MCUboot's image format, with no repository record.
> **Not verified:** The tool has never run on an image from a board or from the CI build, `fit` has never been compared with what `imgtool` or MCUboot accept, and no layout is checked against upstream MCUboot source here. A mistake that the records or the author's reading share with the tests would pass.
> **Read this first / then:** the [boot overview](boot-overview.md), then the [boot composition](boot-composition.md) page.

## What it is for

- Reading what a tester captures at the bench: the first bytes of a slot, or the last bytes of a slot dump, and saying what MCUboot would see there.
- Inspecting images that a build produced (`zephyr.signed.bin`, or a padded image), without a key and without MCUboot's tools.

It uses the Python standard library only. The tool needs nothing newer than about Python 3.8; its tests need Python 3.10 or later (`sys.stdlib_module_names`), and CI uses Python 3.12. It has no board access, no flashing and no key handling.

## Three commands

### `image`

```sh
python3 tests/target/inspect_boot_image.py image zephyr.signed.bin
python3 tests/target/inspect_boot_image.py image zephyr.signed.bin --json
python3 tests/target/inspect_boot_image.py image slot1-first-32-bytes.bin --header-only
```

It prints the header (magic `0x96f3b83d`, `load_addr`, `hdr_size`, `protect_tlv_size`, `img_size`, flags, version as `major.minor.revision+build_num`), each TLV area (protected, then unprotected) with its magic, total length and entries, the SHA-256 that it computed over the header up to `hdr_size`, the payload and the protected TLV area, the `SHA256` TLV, the `KEYHASH` TLV (the SHA-256 of the public key, as the image carries it) and any padding. Only the TLV types `KEYHASH` (`0x01`), `SHA256` (`0x10`) and `ECDSA_SIG` (`0x22`) have names; other types show as hex. Long values are shortened in the text output and complete in `--json`.

The last line is `Result: digest ok`, `Result: digest MISMATCH` or `Result: structure inconsistent` (a bad magic, a length beyond the file, a missing `SHA256` TLV and similar).

**This is a digest check only and NOT a signature verification.** It does not read the `ECDSA_SIG` value as a signature and does not use a key, so an image with a changed or forged signature still reports `digest ok`. `imgtool verify` stays authoritative.

A padded image (bytes after the TLV area to the end of the file) is reported with the number of trailing bytes. When the file ends with a trailer magic, the tool reports its alignment and decodes the trailer fields with the same rules as the `trailer` command. A note says if padding bytes are not `0xFF`.

`--header-only` is for the slot 1 header check of the bench procedure (a 32-byte read of the slot): it accepts a short read of at least 4 bytes and reports only `image magic present` (the bytes `3d b8 f3 96`) or `no image`, with a remark when every byte read is `0xFF`. It exits 0 either way. A read of fewer than 4 bytes is a usage error.

### `fit`

```sh
python3 tests/target/inspect_boot_image.py fit zephyr.signed.bin --slot-size 3145728 --align 8 --slot-offset 0x20000
python3 tests/target/inspect_boot_image.py fit zephyr.signed.confirmed.bin --slot-size 3145728 --align 8 --json
```

It decides whether a signed image fits a slot, by the repository's trailer model, in five named checks:

| Check | Fails when |
| --- | --- |
| `image` | The file is not a well-formed image with a matching digest (the `image` command's result). |
| `layout` | The slot size, or the slot offset when `--slot-offset` is given, is not a multiple of the erase unit (`--erase-unit`, 64 KiB by default, the boundary rule of decision 17 of the [boot and update investigation](boot-update-investigation.md)). Reported as **misaligned**. |
| `size` | The file is longer than the slot, or, with `--align N`, the image (header, payload, TLV areas) plus the trailer region is longer than the slot. The trailer region is the distance from the slot end to the `swap_info` byte of alignment `N`. Reported as **oversized**, with the number of bytes it is over by. Without `--align` the trailer is not counted and the row says so (`info`). |
| `padding` | The image is padded (bytes follow its TLV area) and the file is not exactly the slot size. |
| `trailer alignment` | The padded image's trailer magic is the one of another alignment than `--align`. Reported as **misaligned**. With no trailer magic, or no `--align`, the row is `info`. |

The last line is `Result: fits` or `Result: does not fit`. The exit status is 0 for `fits`, 1 for `does not fit` and 2 for a usage error (the slot size is required). **This is the repository model's decision, not imgtool's or MCUboot's:** the trailer reach comes from the model and is not checked against upstream, and which `--align` of the model corresponds to the `--align 1` of the build's `imgtool` call is the open question above. It is not a signature verification.

### `trailer`

```sh
python3 tests/target/inspect_boot_image.py trailer slot0.bin --align 8
python3 tests/target/inspect_boot_image.py trailer slot1.bin --align 512 --slot-size 3145728 --json
python3 tests/target/inspect_boot_image.py trailer slot0.bin --align 8 --running
```

It decodes the trailer at the **end** of the file: the 16-byte magic (`good`, `unset` when all `0xFF`, or `bad`), then `image_ok`, `copy_done` and `swap_info`. Each field sits one alignment unit below the previous one, going down from the magic, as the [trailer replay record](evidence/boot-emmc/trailer-replay/README.md) and its model `tests/native/emmc_trailer/trailer_model.py` record. A flag is `unset` when it reads `0xFF`, `set` when it reads `0x01` and `bad` otherwise. `swap_info` shows its type (the low nibble: 1 none, 2 test, 3 perm, which are the values the repository's model uses) and image number.

`--align N` is the alignment unit of the trailer, `BOOT_MAX_ALIGN` in the repository's model. For example, `--align 8` puts `image_ok`, `copy_done` and `swap_info` 24, 32 and 40 bytes below the end, and `--align 512` puts them 1024, 1536 and 2048 bytes below it. The magic is the one the repository records for alignment 8, and for any other alignment the alignment as a 16-bit little-endian number followed by a fixed tail. If the magic is the one of another alignment, the tool says so. **The relation between this `N` and the `--align 1` of the build's `imgtool` arguments is not established here:** the trial builds signed with `--align 1`, which is imgtool's write alignment, and which `N` a padded image from that build carries is something to read from its trailer magic (`image` reports it) and not to assume.

It names the slot state with the names of the [image state contract proposal](plans/image-state-contract-proposal.md) (section "Slot states"): `STAGED`, `PENDING_TEST`, `PENDING_PERMANENT`, `TRIED`, `STANDBY_CONFIRMED`, `RUNNING_CONFIRMED`, `RUNNING_TESTING`, `EMPTY`, `INVALID`, and `ERR_BOOT_STATE` for a running slot without a good magic. The proposal is not adopted, so these are its names, not a Crux interface. Three inputs that a file cannot give are handled openly:

- Whether the slot is the running one: pass `--running`. Without it the slot is treated as not running.
- Whether the slot holds a valid image: the image header is examined only when the file is as long as `--slot-size`, or when `--check-header` is given. "Examined" means only the 4-byte image magic at offset 0, not that the header or the image is valid. Otherwise the state assumes a valid header and a note says so. A whole-slot dump with no image magic at offset 0 reads `EMPTY`, as the table has it.
- The slot size: with `--slot-size`, the tool says whether the file is equal to it, longer or shorter. The trailer is always read at the end of the file, so a file that is only the trailer region works, and so does a whole slot.

Two cases are outside the proposal's table and are decided by this tool: a running slot whose `image_ok` is neither `0x01` nor `0xFF` reads `INVALID`, and so does a not-running slot with an unset magic and a bad flag (not `STAGED`). Both also exit 1.

A `swap_info` that disagrees with `image_ok` (a test request with `image_ok` set, or a permanent request without it) is a warning and does not change the exit status.

## Exit status

| Status | Meaning |
| --- | --- |
| 0 | `image`: the file parses and the digest matches, or `--header-only` ran. `trailer`: it decodes. `fit`: the image fits. |
| 1 | The file parses but the digest does not match, or the structure is inconsistent (`image`); the magic is bad, a flag is neither `0x01` nor `0xFF`, a field is set under an unset magic, a running slot has no good magic, or the file is too short for the trailer (`trailer`); the image does not fit (`fit`). |
| 2 | A usage error: a missing or unknown argument, an unreadable file, a `--header-only` read shorter than 4 bytes, no `--slot-size` for `fit`. |

## What it does not do

- It does not verify a signature, check a key against anything, or generate or store a key.
- It does not reach a board, a probe or a flash device, and it does not program, erase or reset anything.
- It does not tell you what MCUboot would decide at boot. It decodes bytes by the repository's trailer model and the author's reading of the image format.
- It does not read a swap trailer. The records cover RAM load with revert, where the trailer holds the magic, `image_ok`, `copy_done` and `swap_info`.

## Check of the CI-built images

> **Status:** Prepared, **NOT wired** into any workflow, and it has **never run on a real build**. Its host tests ([`tests/build/test_check_boot_images.py`](../tests/build/test_check_boot_images.py)) run it only against a fake build tree of synthetic images and a fake `imgtool`. Whether it passes on the real images is **Not verified**.

`tests/target/check_boot_images.sh [build-dir]` sits in `tests/target/` beside the inspector, so that no protected path (`scripts/`) holds it. It uses the images that the [boot composition](boot-composition.md) check builds as the ground truth for this inspector. It builds nothing, programs nothing and generates no key; it reads the build directory of `scripts/test-boot-composition.sh` (`build/zephyr/boot-composition` by default) and writes only into one temporary directory below it, `check_boot_images.tmp`, which it removes again (also after a failure). That directory holds the changed copies of the signed image, the inspector's JSON outputs and a few helper files. `CRUX_PYTHON` and `CRUX_WORKSPACE` work as in the composition script. It exits 0 when every check passed, 2 when something it needs cannot be used, and 1 when a check fails.

| Exit | Cases |
| --- | --- |
| 2 | The build directory, `zephyr.signed.bin`, the MCUboot image, `imgtool.py` or the key file is missing; Python is not available (`CRUX_PYTHON`); the inspector cannot be started (shell status 126 or 127); `imgtool` ends in a traceback on `--help`, which means its requirements are not installed. The message says to run `scripts/test-boot-composition.sh` first or to install the requirements of `bootloader/mcuboot/scripts/requirements.txt`. |
| 1 | A check fails: any value or size above, a disagreement between the inspector and `imgtool verify`, `imgtool` crashing while it verifies a file, a missing `zephyr.signed.confirmed.bin` (the Zephyr v4.4.2 erratum of the [boot and update investigation](boot-update-investigation.md)), or an image name that matches more than one file. |
| 0 | Everything passed. If the public key could not be derived, the key hash row reads `info`, not `ok`, and the last line says `key hash NOT compared with the key`. |

It finds the application's images only in the sysbuild directory `$build/zephyr/zephyr` (the first `zephyr` is the base name of `samples/controller/zephyr`, the second is sysbuild's output directory) with `find -maxdepth 1` for `zephyr.signed.bin` and `zephyr.signed.confirmed.bin`, so a stray copy deeper in the tree is not taken, and a name that matches more than one file fails, and the bootloader's image at `$build/mcuboot/zephyr/zephyr.bin`. It then checks:

| Image | Checks |
| --- | --- |
| `zephyr.signed.bin` | The inspector parses it and reads `digest ok`; header size `0x400`, load address `0x80000000`; file size is header plus image plus the TLV areas that the inspector reports, with no padding; `KEYHASH`, `SHA256` and `ECDSA_SIG` TLVs are present; the key hash is 32 bytes and equals the SHA-256 of the public key's DER `SubjectPublicKeyInfo` (or of its uncompressed point), derived from `root-ec-p256.pem` with `imgtool getpub -e pem` or, failing that, `openssl`. If neither can derive the key the check says so, compares only the length, and does not count the key hash as checked. `imgtool verify` must agree with the inspector, and both must accept: `digest ok` and a verified signature. A disagreement, or both refusing, fails (exit 1) and shows both outputs. If the public key could not be derived, the key hash row is `info` and the script says so on its last line. |
| `zephyr.signed.confirmed.bin` | File size is the slot size 3,145,728 B; the inspector reads `digest ok`; the file ends with a trailer magic; with `--slot-size 3145728` the trailer decodes for at least one alignment of 1, 8, 16 and 32 to `RUNNING_CONFIRMED` with `--running` and to `PENDING_PERMANENT` without it, with `image_ok` set and `copy_done` unset. These two names are the rows of the proposal's [slot state table](plans/image-state-contract-proposal.md#slot-states) for a good magic, `image_ok` set and `copy_done` unset. `imgtool verify` on this padded file is printed as information only, because how it treats padding is not established here. |
| Fit in the slot | `fit` on the signed and the confirmed image, with `--slot-size 3145728`, `--slot-offset 0x20000` and the alignment that the confirmed image's trailer magic carries, must read `fits`. With a slot as small as the signed image itself, `fit` must read `does not fit` (oversized) and `imgtool sign` of the build's unsigned `zephyr.bin` (`--header-size 0x400 --align 1 --version 0.0.0 --slot-size <small>`) must refuse, without a crash. A control with the real slot size must sign; if it does not, the arguments do not suit this `imgtool` and the script exits 2, not 1. Without `zephyr.bin` in the sysbuild directory the `imgtool sign` row reads `info`, not run. `imgtool`'s reaction to a misaligned layout is not asked: that row is `info`. |
| `mcuboot/zephyr/zephyr.bin` | `image --header-only` reports `no image` and the full `image` command exits 1: MCUboot's own binary carries no image header. |
| Changed bytes | A copy of the signed image with the byte at `0x300` (header padding) or `0x500` (payload) changed reads `digest MISMATCH` (exit 1) in the inspector, and `imgtool verify` refuses it too. |

The script prints a summary table and, for the confirmed image, a **survey of the alignment unit**: for each of `--align 1`, `8`, `16` and `32` the state of the magic, of `image_ok` and `copy_done`, and the slot state, with the unit that decodes consistently named. The survey is evidence for the open question above (the relation between `N` and the `--align 1` of the build's `imgtool` arguments), not a pass criterion: only a decode that reads `RUNNING_CONFIRMED` for at least one alignment is.

**What it will settle, once it has run on a real build:** whether the inspector's reading of the TLV layout (the magics `0x6908` and `0x6907`, the entry layout, the hashed range) agrees with an image that MCUboot's tool signed and verifies, which is the check that the synthetic tests cannot give; whether the key hash is of the `SubjectPublicKeyInfo` or of the point; and which alignment unit the trailer of the build's confirmed image carries. It does not verify a signature itself, does not boot anything, and a pass says nothing about MCUboot's behaviour at boot.

### Proposed workflow step (needs the owner's approval)

The script itself touches no protected path. Running it in CI still means editing `.github/workflows/zephyr.yml`, a protected file (`AGENTS.md`, protected paths). That change has **not** been approved and stays a proposal that needs the owner's approval, so the workflow is untouched. The proposal is one step directly after the composition step in the `runtime` shard, where the build directory, the MCUboot checkout and imgtool's requirements already exist:

```yaml
      - name: Check the RAM load composition images against the boot image inspector (software-only)
        if: matrix.shard == 'runtime'
        working-directory: crux-pilot
        run: tests/target/check_boot_images.sh
```

Until the step is wired and has run, the inspector remains unchecked against a real image.

## Limits

- The image header fields come from the repository's model of the image (`ModelImage`, which has no TLVs). The TLV area magics (`0x6908`, `0x6907`), the TLV entry layout and the statement of what MCUboot hashes (header up to `hdr_size`, payload, protected TLV area) are the author's reading of MCUboot's image format. The repository records only that the bootloader's image copy covers header, payload, protected TLVs and TLVs.
- The header and trailer layouts follow the repository's trailer model; the TLV magics, the TLV entry layout and the hashed range are the author's reading of MCUboot's image format. Both parts are still not checked against upstream source here. The tests build their inputs from the same records and the same reading, so they cannot find an error that these share.
- The repository holds no MCUboot-signed image, so the tests use synthetic images with fake keys and signatures. A first run on an image from a build or a board is the next check; until it has run, treat a `digest ok` on a real image as a result about the tool as well.
- The erased value is taken as `0xFF`.
