# Boot composition reproducibility: a check of two builds

> **Status:** Prepared, **NOT wired** into any workflow, and it has **never run on a real build**. `tests/target/compare_boot_builds.py` and `tests/target/check_boot_reproducibility.sh` are developer tools, not a Crux interface, with no stable contract. They decide nothing about the composition.
> **Verified:** By host tests on synthetic build trees ([`tests/build/test_compare_boot_builds.py`](../tests/build/test_compare_boot_builds.py) and [`tests/build/test_check_boot_reproducibility.py`](../tests/build/test_check_boot_reproducibility.py)): what the tools decide when two trees differ in a chosen way. Earlier, by build: two clean trial builds of the older trial tree gave identical unsigned binaries and signed images that differ in the ECDSA signature ([Stage 8](evidence/boot-update/stage8-reproducibility-and-signing.md)).
> **Not verified:** That two builds of the committed composition ([boot composition](boot-composition.md)) reproduce. Nothing here has compared two real builds of it. Path independence, another container, another host, another SDK installation and a later date are not covered by anything. Whether the signature of this toolchain is randomised is a measurement of the Stage 8 trial toolchain (imgtool 2.4.0, `cryptography` 50.0.2) and an Inference for any other.
> **Read this first / then:** the [boot overview](boot-overview.md) and the [boot composition](boot-composition.md) page, then this page; the [boot image inspection](boot-image-inspection.md) page for the sibling check of the images themselves.

## What "reproducible" means here

The acceptance text of [issue #296](https://github.com/wonny-labs/crux-pilot/issues/296) asks that the bootloader and a signed reference image "build reproducibly from documented inputs" and that signed outputs "verify against the documented public verification key". It does not ask for byte-identical signed images. The definition used here is the one of Stage 8 of the boot and update investigation:

| Artifact | Must be | Why |
| --- | --- | --- |
| MCUboot `zephyr.bin`, application `zephyr.bin` (unsigned) | Byte-identical | Stage 8: identical in all four trial pairs. |
| `zephyr.signed.bin` | Identical header, payload, protected TLVs, digest (`SHA256`) and key hash (`KEYHASH`), and every byte after the TLV areas. Each image has exactly one `ECDSA_SIG` TLV, at the same position among the TLVs. Only its value may differ, and its length (and so the file size) by at most two bytes (the DER length of an ECDSA signature varies; the two-byte bound is this tool's choice, not a Stage 8 figure). | Stage 8: the signature differed in both trial pairs and the sizes differed by one byte. |
| `zephyr.signed.confirmed.bin` | The same rule, the same padded length, and an identical tail: the padding and the trailer, lined up from the end of the file, where the bytes a shorter signature leaves in front must be erased (`0xFF`). Absent from both builds is reported with a note that this is not the composition of the composition page, and passes; present in one build only fails. | It is the padded image that Zephyr v4.4.2 writes for RAM load with revert (the erratum of the [boot and update investigation](boot-update-investigation.md)). |
| ELF files, maps, logs | Not compared | Stage 8: the ELF files differ in debug sections that hold the build path. |

With `--strict-signature` the signed images must also be byte-identical, which asks for a deterministic signature. Both signed images must in addition verify with the public test key under `imgtool verify`; the comparison does not verify a signature.

## The tools

`tests/target/compare_boot_builds.py BUILD_A BUILD_B [--image NAME] [--strict-signature] [--json]` reads two build directories of the composition (the layout of `scripts/test-boot-composition.sh`: `mcuboot/zephyr/zephyr.bin`, and `<image>/zephyr/` with `zephyr.bin`, `zephyr.signed.bin` and `zephyr.signed.confirmed.bin`, where `<image>` is `zephyr` for `samples/controller/zephyr`). It uses the [inspector](boot-image-inspection.md) to parse the signed images, so a difference is named: `header`, `payload`, `protected TLVs`, `TLVs other than the signature`, `trailer`, `padded length`. Each artifact has a status: `identical`, `equivalent` (only the signature differs), `differs`, `missing` or `absent`. Exit 0 reproducible, 1 not reproducible, 2 usage error (an unreadable directory, the same directory twice) or an unexpected failure of the tool, which is not a verdict. It uses the Python standard library only and has no key, board or flash access.

`tests/target/check_boot_reproducibility.sh` wraps it:

- `check_boot_reproducibility.sh BUILD_A BUILD_B` compares two existing build directories, for example from two checkouts, which gives different build paths.
- `check_boot_reproducibility.sh --build [BUILD_DIR]` runs `scripts/test-boot-composition.sh` (or `CRUX_COMPOSITION_COMMAND`) from the repository root, moves its build directory to `BUILD_DIR.first`, runs it again and compares the two. `BUILD_DIR` must be the directory that the composition command writes: `scripts/test-boot-composition.sh` always writes `build/zephyr/boot-composition` of the repository, so with another `BUILD_DIR` the check ends with exit 2 after a full build. It refuses an existing `BUILD_DIR.first`. Both builds use the same path, so it does not test path independence, and it runs two full sysbuilds.

It then runs `imgtool verify` with the public test key on the signed image of each build, and fails on a refusal or a crash (a traceback is a crash, not a refusal). The padded confirmed image is verified for information only, as in the [image check](boot-image-inspection.md). Exit status: 0 reproducible and verified, 1 not reproducible or an image that imgtool refuses or crashes on, 2 the inputs or a tool cannot be used (a missing directory, Python, imgtool or key, imgtool without its requirements, a failing composition command). It generates no key, programs and boots nothing, and `--build` writes only `BUILD_DIR.first` besides what the composition command writes.

## What it will and will not settle once it has run

It will settle whether two builds of the committed composition in one container reproduce by the definition above, which Stage 8 showed only for an older trial tree. It will not settle path independence (unless run with two checkouts), another container or host, the effect of a changed SDK or MCUboot revision, or anything about booting. A pass says nothing about MCUboot's behaviour.

## Proposed workflow step (needs the owner's approval)

The tools touch no protected path. Running the check in CI still means editing `.github/workflows/zephyr.yml`, a protected file (`AGENTS.md`, protected paths). That change has **not** been approved and stays a proposal. Two sysbuilds take about twice the time of the composition step, so the step is better placed in its own job or shard than inside the `runtime` shard. The step text, for the owner's decision:

```yaml
      - name: Check that two builds of the MCUboot RAM load composition reproduce (software-only)
        working-directory: crux-pilot
        run: tests/target/check_boot_reproducibility.sh --build
```

Until the step is wired and has run, reproducibility of the committed composition stays **Not verified**.
