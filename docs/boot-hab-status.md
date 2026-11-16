# HAB status: what exists, what does not, and what each next step needs

> **Status:** A status page, not a decision and not a plan. It records what HAB-related work the repository holds on 16 November 2026, what is not started, and what each kind of next step needs. It adopts nothing and approves nothing.
> **Verified:** The repository contents named below, by reading them. The offline structure checker ([`tests/target/check_hab_structure.py`](../tests/target/check_hab_structure.py)) by host tests on synthetic images ([`tests/build/test_hab_structure.py`](../tests/build/test_hab_structure.py)).
> **Not verified:** Any HAB behaviour on a board, any HAB signing tool run, any real HAB-signed image, and the layouts the checker assumes (they are the author's reading of public descriptions and of the repository's records, see [Evidence labels](#evidence-labels)). **No HAB result of any kind exists in this repository.**
> **Read this first / then:** the [boot overview](boot-overview.md), then the [secure boot development plan](plans/secure-boot-development-plan.md) (sections 3, 4 and 6), then the [HAB open-configuration plan](plans/hab-open-configuration-plan.md) for the proposed next steps.

## In one paragraph

HAB is the boot ROM's check of the first-stage image. The repository holds desk investigations of it, a plan that puts HAB work in Phase 4 (open configuration, reporting only) and Phase 5 (closed configuration, a product decision), the owner's decisions D1, D4, D5 and D6, and, since this page, an offline checker that reads the boot structures of an image file. It holds no HAB signing step, no key, no signed image, no tool run and no board result. Phase 4 is Not started. Trust level T2 of the plan is not reached; neither is T0 shown on a board.

## Evidence labels

Labels follow the boot records: Verified on pinned source, Verified by build, Verified by public vendor document, Inference, Not verified. "Verified by public vendor document" here means the third-party copy of the RT1060 reference manual (Rev. 3) and public vendor tool documentation as the cited records read them, not the vendor's own download. A statement without a label is a citation of a record or a description of this repository. Documents under a non-disclosure agreement were not used for this page or for the checker, and none may be cited from them.

## What exists in the repository

| Item | What it is | Limits |
| --- | --- | --- |
| Desk record of #141 (stage 3 findings and the [boot and update investigation](boot-update-investigation.md)) | Read-only study: a Zephyr-built image has no CSF (`CSF_ADDRESS` is 0); the open-configuration expectation; candidate tools. | Desk result. SPSDK handling of a Zephyr image that already has an FCB and an IVT is Not verified (stage 3 A14). |
| Desk record of #298 ([eMMC boot feasibility](boot-emmc-investigation.md) and [vendor documents](evidence/boot-emmc/vendor-documents.md)) | The ROM's reading of an SD or eMMC boot area: IVT at `0x400`, DCD processed before the image copy (order is an Inference), open and closed behaviour. | Desk result. Where a CSF sits for an SD or eMMC image is Not verified (X7); so is the HAB event content for a blank SRK hash (X4). |
| Desk record of #299 ([bootloader update investigation](boot-bootloader-update-investigation.md) and [evidence B](evidence/boot-bootloader-update/b-nxp-rom-fuses-hab.md), rows B-4, B-17 to B-19, B-60 to B-69) | HAB in open and closed configuration, SRK hash and revocation fuses, the HAB API in the ROM, why a signed first stage adds no root of trust in open configuration (B-69, Inference). | Desk result from a third-party copy of the manual and generic HABv4 text. Which SRK slots are revocable on the RT1060 is Not verified (B-62); the RT1060 HAB API layout is Not verified (B-65). |
| [Secure boot development plan](plans/secure-boot-development-plan.md) | Trust levels T0 to T3; Phase 4 (HAB in open configuration, Not started) and Phase 5 (closed configuration and production, Not started); owner decisions D1 to D10. | A plan; it adopts only the decisions it cites. |
| Issues [#440](https://github.com/wonny-labs/crux-pilot/issues/440), [#296](https://github.com/wonny-labs/crux-pilot/issues/296), [#309](https://github.com/wonny-labs/crux-pilot/issues/309) | #440: sign the eMMC first-stage image for HAB in open configuration (planning item). #296: its acceptance criteria include a HAB-signed bootloader build for the NOR layout and a recorded root-of-trust decision. #309: the boot ROM serial downloader check on the EVKB (hardware, not run). All three were open on 16 November 2026. | Planning items. Publishing them authorises no investigation, implementation, hardware or fuse operation. |
| WP1a build check ([boot composition](boot-composition.md)) | Builds MCUboot and the controller sample and signs the **application** with a public test key using MCUboot's `imgtool`. Build-only. | This is MCUboot signing, not HAB signing. It writes no CSF and uses no HAB tool. |
| [Boot image inspector](boot-image-inspection.md) | Reads MCUboot image headers, TLVs and trailers. | MCUboot's format only. It does not read an IVT, a DCD or a CSF. |
| HAB structure checker (this change) | [`tests/target/check_hab_structure.py`](../tests/target/check_hab_structure.py): IVT position and header, boot data, DCD pointer and header, CSF pointer and header, for NOR (IVT at `0x1000`) and SD or eMMC (IVT at `0x400`), against a declared CSF presence. See [How to run the checker](#how-to-run-the-checker). | Structure only. Never run on a real image. A pass is not a signature verification. |
| SPSDK download approval | The owner gave approval for the SPSDK download under #141 A2 (recorded 2 November 2026). | Not used: no SPSDK result is in any record. CST and the Secure Provisioning tool have no approval. |
| Public-source tooling research | A desk summary of the public NXP tooling for RT1060 secure boot (SPSDK `nxpimage hab`, `sdphost`, `blhost`, CST, Secure Provisioning, the flashloader). It sits outside the repository; the plan's section 7 and the [HAB open-configuration plan](plans/hab-open-configuration-plan.md) carry what they use. | Public pages, summarising fetches; nothing was installed or run. |

## Not started

None of the following exists: a HAB signing step or script; a BD or YAML description of a HAB image; a CSF; any key, certificate or SRK table (throwaway or other); a run of SPSDK `nxpimage hab`, `sdphost`, `blhost` or CST; a CI step for any of them; a first-stage image for the NOR layout that carries a CSF; an eMMC first-stage image (plan issue B) to sign; a HAB event read; an SRK hash in any fuse; a closed configuration. The RT1060-EVKB has had no fuse operation. No board result about HAB exists.

## What a next step needs

| Kind | Examples | Needs |
| --- | --- | --- |
| **Board-free, no key** | The structure checker (done, this change); a plan for signing and for the hardware block ([HAB open-configuration plan](plans/hab-open-configuration-plan.md)); a licence review of the tools; fixtures and checks for the layouts of the SDP-download variant. | Nothing beyond the task's approval. |
| **Board-free, with throwaway keys** | Generating development keys; building a HAB-signed first-stage image offline; `nxpimage hab parse` of the result; running the structure checker on it; the question whether SPSDK accepts a Zephyr image with an FCB and an IVT (A14). | Explicit owner approval to generate throwaway development keys, to install and run the pinned tool, and where they are held. **Not given.** Keys stay outside every repository. |
| **Board, open configuration, no fuse write** | A HAB event read; the ROM serial downloader check (#309), which may share a session with it (#141 owner decision 8); showing that the ROM runs an image that carries a CSF in open configuration. | A separately approved hardware task with a verified target, probe and setup, a custody arrangement for the board and a stop rule. **Not given.** The RT1060-EVKB is open and stays open. |
| **Board, closed configuration** | Programming SRK hash fuses, setting SEC_CONFIG, a flashloader signed under the device's SRK, revocation, debug lockdown, a hardware anti-rollback counter. | A decision on D1 (which the owner approved as "plan for it in production") turned into a product fuse plan, key custody and a signing ceremony, and a board that may be locked ([#141 decision 11](boot-update-investigation.md) defers a dedicated board). No fuse operation is approved. **Phase 5; not started.** |

## Owner decisions on record

The decisions are in [section 6 of the plan](plans/secure-boot-development-plan.md#6-decisions-the-owner-needs-to-make). Each approves its recommendation as the table words it and nothing more.

| # | Decision (as recorded, 15 November 2026) | What it does not approve |
| --- | --- | --- |
| D1 | Products may use the closed security configuration; plan for it in production, keep development and the EVKB open. | Any fuse operation; a date; a board that may be locked. |
| D4 | Hardware anti-rollback source: an application-side check only until D1; then pick by board features. | A fuse-backed counter or any fuse operation. |
| D5 | Recovery versus lockdown in production: keep a signed-only recovery path, decided together with D1. | Closing a board or a serial-download policy for a product. |
| D6 | HAB key algorithm and size, key custody: RSA-3072 or larger, offline keys in an HSM, up to four SRK slots. Which slots are revocable stays Not verified. | Creating or provisioning any key. No key is created or provisioned by this decision. |

D6 describes production keys. It does not approve throwaway development keys; the plan lists that approval as a separate request.

## What the public sources say, in short

These statements are cited from the records above and carry their labels there.

| Statement | Label | Where |
| --- | --- | --- |
| In open configuration the ROM runs HAB, logs authentication errors and boots anyway, even when authentication data is missing or incorrect. In closed configuration an authentication error aborts the boot to the serial downloader. | Verified by public vendor document | B-4; [vendor documents](evidence/boot-emmc/vendor-documents.md) R8 |
| The IVT offset is `0x1000` for FlexSPI NOR and `0x400` for SD and eMMC. | Verified by public vendor document | [vendor documents](evidence/boot-emmc/vendor-documents.md) R4 |
| The IVT carries entry, DCD, boot data, self and CSF pointers; the boot data carries start, length and plugin. | Verified by public vendor document | B-60, B-67 |
| A Zephyr-built image has no CSF; the pinned layout puts the FCB at `0x0`, the IVT at `0x1000`, the boot data at `0x1020` and the DCD at `0x1030` for the RT1060 NOR boards. | Verified on pinned source | [pinned source findings](evidence/boot-emmc/pinned-source-findings.md) P5; [boot and update investigation](boot-update-investigation.md), Stage 7 |
| With blank SRK hash fuses, open configuration can at best show that a CSF was processed and which checks failed, not a passing authentication. | Not verified for the RT1060 | #141 stage 3 A13; B-69 |
| A signed first stage in open configuration adds checking and reporting but no root of trust. | Inference | B-69 |
| Whether SPSDK accepts a Zephyr image that already has an FCB and an IVT, and whether it fully replaces the legacy CST for the RT1060. | Not verified | #141 stage 3 A14, B6 |
| The SPSDK device data for the RT1060 is an alias chain; its memory map disagrees with the manual. | Inference | B-16 |
| What HAB event data the serial downloader returns in open configuration with a blank SRK hash. | Not verified | B-11, #141 A13 |

## How to run the checker

```sh
python3 tests/target/check_hab_structure.py check first-stage.bin --medium nor --csf absent
python3 tests/target/check_hab_structure.py check first-stage.bin --medium emmc --csf present --dcd present --json
python3 -m unittest tests/build/test_hab_structure.py
```

`--medium` sets the expected IVT offset (`nor` `0x1000`, `sd` and `emmc` `0x400`). `--csf` is required: the image is declared to carry a CSF or not, and the checker fails when the csf pointer disagrees. `--dcd` is optional and declares the DCD the same way. The checks:

| Check | Fails when |
| --- | --- |
| `ivt` | No IVT tag `0xD1` at the expected offset. The message says when an IVT-like header sits at the other medium's offset. |
| `ivt_header` | The header length is not 32 or the version is not `0x40` or `0x41`. |
| `boot_data` | The boot data pointer is zero, below the image base or beyond the file; the boot data length is zero, larger than the file, or too short to cover the IVT and boot data. |
| `self` | The self pointer minus the IVT offset differs from the boot data start. The two fields disagree and the tool cannot say which is wrong. |
| `dcd` | The declaration and the dcd pointer disagree; or the header tag is not `0xD2`; or the length is under 4, over 1,768 or runs beyond the file. |
| `csf` | The declaration and the csf pointer disagree; or the pointer is outside the file; or the region has no CSF header (tag `0xD4`), for example a reserved empty region; or its length runs beyond the file. |
| `regions` | The IVT, boot data, DCD and CSF regions overlap. |

`fcb` (NOR only, the tag `FCFB` at offset 0), `entry`, `reserved`, `plugin`, `image_length` and `csf_range` report as `ok`, `info` or `warn` and never decide the verdict. The last line is `Result: structure consistent` or `Result: structure inconsistent`; the exit status is 0, 1, and 2 for a usage error or an unreadable file.

The checker does not verify a signature, a certificate, an SRK table or a key, does not parse DCD or CSF commands, reads no vendor tool output and cannot say what the ROM or HAB would decide. It complements [`inspect_boot_image.py`](boot-image-inspection.md), which reads MCUboot's format, and shares no code with it. A first run on an image built by a real tool is the next check; until then a pass is a result about the checker as much as about the image. It is not wired into CI.

## Open points

- The layouts the checker assumes (header words, big-endian lengths, the pointer-to-offset arithmetic, the `FCFB` tag and the boot data start being the address of file offset 0) are Inference until an image from a vendor tool has been checked against them.
- Where the IVT sits inside a file that the serial downloader receives (`0x0` in the SPSDK device data, B-15; `0x400` in a BD file the SDK guide shows, B-18 as summarised). Not verified; the checker has no medium for it yet.
- The CSF placement for an SD or eMMC image (#298 X7), the HAB event content for a blank SRK hash (X4), the SRK revoke bits (B-62) and the RT1060 HAB API table layout (B-65) need sources the repository has not read and that may not be public. Material under a non-disclosure agreement stays out of the repository: say "Not verified" in any record instead of guessing.
- The licences of SPSDK's binary dependencies, of the flashloader and of CST are Not verified.
