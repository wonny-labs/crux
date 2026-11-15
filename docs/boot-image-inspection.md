# Boot image inspection: a tool to read MCUboot images and trailers

> **Status:** A developer tool, not a Crux interface. `scripts/inspect-boot-image.py` reads files and changes nothing; it has no stable contract and no support commitment.
> **Verified:** By host tests on synthetic images and trailers built in memory from the repository's records of the format ([`tests/build/test_boot_image_inspect.py`](../tests/build/test_boot_image_inspect.py)).
> **Not verified:** The tool has never run on an image from a board or from the CI build, and the layouts are not checked against upstream MCUboot source here. A mistake that the repository's records share with the tests would pass.
> **Read this first / then:** the [boot overview](boot-overview.md), then the [boot composition](boot-composition.md) page.

## What it is for

- Reading what a tester captures at the bench: the first bytes of a slot, or the last bytes of a slot dump, and saying what MCUboot would see there.
- Inspecting images that a build produced (`zephyr.signed.bin`, or a padded image), without a key and without MCUboot's tools.

It uses the Python standard library only (Python 3.11 or later) and runs anywhere. It has no board access, no flashing and no key handling.

## Two commands

### `image`

```sh
python3 scripts/inspect-boot-image.py image zephyr.signed.bin
python3 scripts/inspect-boot-image.py image zephyr.signed.bin --json
python3 scripts/inspect-boot-image.py image slot1-first-32-bytes.bin --header-only
```

It prints the header (magic `0x96f3b83d`, `load_addr`, `hdr_size`, `protect_tlv_size`, `img_size`, flags, version as `major.minor.revision+build_num`), each TLV area (protected, then unprotected) with its magic, total length and entries, the SHA-256 that it computed over the header up to `hdr_size`, the payload and the protected TLV area, the `SHA256` TLV, the `KEYHASH` TLV (the SHA-256 of the public key, as the image carries it) and any padding. Only the TLV types `KEYHASH` (`0x01`), `SHA256` (`0x10`) and `ECDSA_SIG` (`0x22`) have names; other types show as hex. Long values are shortened in the text output and complete in `--json`.

The last line is `Result: digest ok`, `Result: digest MISMATCH` or `Result: structure inconsistent` (a bad magic, a length beyond the file, a missing `SHA256` TLV and similar).

**This is a digest check only and NOT a signature verification.** It does not read the `ECDSA_SIG` value as a signature and does not use a key, so an image with a changed or forged signature still reports `digest ok`. `imgtool verify` stays authoritative.

A padded image (bytes after the TLV area to the end of the file) is reported with the number of trailing bytes. When the file ends with a trailer magic, the tool reports its alignment and decodes the trailer fields with the same rules as the `trailer` command. A note says if padding bytes are not `0xFF`.

`--header-only` is for the header check of the bench procedure: it accepts a short read of at least 4 bytes (a 32-byte read of slot 1 is the usual case) and reports only `image magic present` (the bytes `3d b8 f3 96`) or `no image`, with a remark when every byte read is `0xFF`. It exits 0 either way. A read of fewer than 4 bytes is a usage error.

### `trailer`

```sh
python3 scripts/inspect-boot-image.py trailer slot0.bin --align 8
python3 scripts/inspect-boot-image.py trailer slot1.bin --align 512 --slot-size 3145728 --json
python3 scripts/inspect-boot-image.py trailer slot0.bin --align 8 --running
```

It decodes the trailer at the **end** of the file: the 16-byte magic (`good`, `unset` when all `0xFF`, or `bad`), then `image_ok`, `copy_done` and `swap_info`. Each field sits one alignment unit below the previous one, going down from the magic, as the [trailer replay record](evidence/boot-emmc/trailer-replay/README.md) and its model `tests/native/emmc_trailer/trailer_model.py` record. A flag is `unset` when it reads `0xFF`, `set` when it reads `0x01` and `bad` otherwise. `swap_info` shows its type (the low nibble: 1 none, 2 test, 3 perm, which are the values the repository's model uses) and image number.

`--align N` is the alignment unit of the trailer, `BOOT_MAX_ALIGN` in the repository's model. For example, `--align 8` puts `image_ok`, `copy_done` and `swap_info` 24, 32 and 40 bytes below the end, and `--align 512` puts them 1024, 1536 and 2048 bytes below it. The magic is the one the repository records for alignment 8, and for any other alignment the alignment as a 16-bit little-endian number followed by a fixed tail. If the magic is the one of another alignment, the tool says so. **The relation between this `N` and the `--align 1` of the build's `imgtool` arguments is not established here:** the trial builds signed with `--align 1`, which is imgtool's write alignment, and which `N` a padded image from that build carries is something to read from its trailer magic (`image` reports it) and not to assume.

It names the slot state with the names of the [image state contract proposal](plans/image-state-contract-proposal.md) (section "Slot states"): `STAGED`, `PENDING_TEST`, `PENDING_PERMANENT`, `TRIED`, `STANDBY_CONFIRMED`, `RUNNING_CONFIRMED`, `RUNNING_TESTING`, `EMPTY`, `INVALID`, and `ERR_BOOT_STATE` for a running slot without a good magic. The proposal is not adopted, so these are its names, not a Crux interface. Three inputs that a file cannot give are handled openly:

- Whether the slot is the running one: pass `--running`. Without it the slot is treated as not running.
- Whether the slot holds a valid image: the image header is examined only when the file is as long as `--slot-size`, or when `--check-header` is given. Otherwise the state assumes a valid header and a note says so. A whole-slot dump with no image magic at offset 0 reads `EMPTY`, as the table has it.
- The slot size: with `--slot-size`, the tool says whether the file is equal to it, longer or shorter. The trailer is always read at the end of the file, so a file that is only the trailer region works, and so does a whole slot.

A `swap_info` that disagrees with `image_ok` (a test request with `image_ok` set, or a permanent request without it) is a warning and does not change the exit status.

## Exit status

| Status | Meaning |
| --- | --- |
| 0 | `image`: the file parses and the digest matches, or `--header-only` ran. `trailer`: it decodes. |
| 1 | The file parses but the digest does not match, or the structure is inconsistent (`image`); the magic is bad, a flag is neither `0x01` nor `0xFF`, a field is set under an unset magic, a running slot has no good magic, or the file is too short for the trailer (`trailer`). |
| 2 | A usage error: a missing or unknown argument, an unreadable file, a `--header-only` read shorter than 4 bytes. |

## What it does not do

- It does not verify a signature, check a key against anything, or generate or store a key.
- It does not reach a board, a probe or a flash device, and it does not program, erase or reset anything.
- It does not tell you what MCUboot would decide at boot. It decodes bytes by the repository's records of the format.
- It does not read a swap trailer. The records cover RAM load with revert, where the trailer holds the magic, `image_ok`, `copy_done` and `swap_info`.

## Limits

- The image header fields come from the repository's model of the image. The TLV area magics (`0x6908`, `0x6907`), the TLV entry layout and the statement of what MCUboot hashes (header up to `hdr_size`, payload, protected TLV area) are the author's reading of MCUboot's image format. The repository records only that the bootloader's image copy covers header, payload, protected TLVs and TLVs.
- The layouts are taken from the repository's records of MCUboot's format and are not checked against upstream source in this repository's tests. The tests build their inputs from the same records, so they cannot find an error that the records share.
- The repository holds no MCUboot-signed image, so the tests use synthetic images with fake keys and signatures. A first run on an image from a build or a board is the next check; until it has run, treat a `digest ok` on a real image as a result about the tool as well.
- The erased value is taken as `0xFF`.
