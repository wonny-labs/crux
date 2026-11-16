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

## Proposed workflow step (needs the owner's approval; see also the proposal at the end of this page)

The tools touch no protected path. Running the check in CI still means editing `.github/workflows/zephyr.yml`, a protected file (`AGENTS.md`, protected paths). That change has **not** been approved and stays a proposal. Two sysbuilds take about twice the time of the composition step, so the step is better placed in its own job or shard than inside the `runtime` shard. The step text, for the owner's decision:

```yaml
      - name: Check that two builds of the MCUboot RAM load composition reproduce (software-only)
        working-directory: crux-pilot
        run: tests/target/check_boot_reproducibility.sh --build
```

Until the step is wired and has run, reproducibility of the committed composition stays **Not verified**.

## Proposal: comparing two real builds in CI

Labels: **Verified** (read from a CI record or a file in this repository), **Inference** (derived, not run), **Not verified**.

**Nothing is wired.** This section proposes; it adds no job, step or script call, and no workflow or script runs `check_boot_reproducibility.sh`. Any of the options below edits a protected path (`.github/workflows/zephyr.yml`, or `scripts/`), so each needs the owner's explicit approval before it is made.

**Cost, measured.** **Verified** from the CI run 43898428480 (`zephyr.yml` on `main`, 16 November 2026, read with `gh run view --json jobs`): the composition step of the `runtime` shard ran from 15:55:45 to 15:56:47 UTC, about 62 s, inside a job of about 19 minutes. The step runs `west update mcuboot`, `pip install` and one pristine sysbuild (`-p always`) on a workspace that the earlier steps had prepared. The older sentence of this page that two sysbuilds "take about twice the time of the composition step, so the step is better placed in its own job" assumed a larger step; at 62 s a separate job costs more (runner start, workspace bootstrap) than the second build itself. **Not verified:** that this one run is typical, and the time of the first run without a warm cache.

| Option | What runs | Extra time (**Inference**) | What it would show | What it would not show |
| --- | --- | --- | --- | --- |
| A. A step in the `runtime` shard after the composition step | `tests/target/check_boot_reproducibility.sh --build`, which runs `scripts/test-boot-composition.sh` twice more (`--build` does not reuse the build of the step before it) | About two further runs of 62 s plus the comparison, so about 2 to 3 minutes on a job of about 19 | Whether two builds of the committed composition in one container, with the same input and path, give identical unsigned binaries and signed images that differ at most in the signature (the definition above); that both signed images verify with the public test key | Path independence (both builds use one path), another container or host, another SDK or MCUboot revision, a later date, anything about booting |
| B. As A, but compare the build of the existing step with one new build | A small change to `check_boot_reproducibility.sh` (a mode that takes the first build as given) and one extra composition run | About 1 to 1.5 minutes | The same as A | The same as A |
| C. As A with a second checkout at another path | A second clone and workspace, or the build directory of a copy, compared with `check_boot_reproducibility.sh BUILD_A BUILD_B` | More: a second workspace and clone, so probably 3 to 5 minutes and more disk | The same as A, and whether the output depends on the build path (the ELF files do; the images should not) | The same as A except path independence |

Two further costs are **Inference**: the composition script now also runs the build configuration check and the image check ([boot image inspection](boot-image-inspection.md)) in each run, so a repetition repeats them (a few seconds); and a reproducibility failure of the signed image's signature alone is expected and tolerated by the definition above, so only a difference in a header, payload, TLV other than the signature, trailer or an unsigned binary fails.

**Recommendation (Inference):** option A as the first step, in the `runtime` shard, because it needs no new script and costs a few minutes; option B if the time matters; option C only if path independence is wanted as a claim. The step text would be:

```yaml
      - name: Check that two builds of the MCUboot RAM load composition reproduce (software-only)
        if: matrix.shard == 'runtime'
        working-directory: crux-pilot
        run: tests/target/check_boot_reproducibility.sh --build
```

It would be placed directly after the composition step, so the build directory that `--build` moves and recreates is the one the composition step wrote. A first run on a real build may fail for a reason that is a finding (an input that differs, a tool that is not deterministic); that is the point of running it, and it is not a reason to re-run until green. Until a step like this has run, reproducibility of the committed composition stays **Not verified**.
