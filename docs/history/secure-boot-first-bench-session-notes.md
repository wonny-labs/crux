# Secure boot board test procedure: first bench session notes

> **Historical record.** Moved from the [secure boot board test procedure](../secure-boot-board-test-procedure.md) when the documentation was restructured as a developer entry point. The procedure keeps the steps and the expected-results table; the open questions of the first planned bench session and the recorded observations of one board are kept here as written.

## Recorded observations removed from the steps

- "Before any test", step 1: the expected `VTref` read "about 3.3 V (3.322 to 3.34 V recorded)". The range was recorded on the one board of the project.
- Recovery, step 4 (SWD): "check J9 and J10 (the first recorded connection failure was these jumpers)."
- Prerequisites table, row Probe: "The first connection failed until J9/J10 were corrected and was made at 100 kHz", and the note "see section 10" (the open questions below).
- Results table, row T7: "Not run: needs M9" (now "Not runnable yet: needs the update agent work").

## Open questions for the first bench session

The repository does not answer these. Settle each and write the answer next to the results.

- [ ] Where, in the task record, is the decision on [#165](https://github.com/wonny-labs/crux-pilot/issues/165) or the approval to run with it open? Every case from T1 on depends on it.
- [ ] Which probe? The recorded flow is an external J-Link PLUS on J2 with J9/J10 removed and J-Link V9.86a on macOS. No flow is recorded for Linux, for the on-board DAPLink as debug probe, or for `west flash` (which would also flash the signed hex files and has not been run on a board).
- [ ] Does the installed Commander accept `savebin "<file>", <address>, <size>` with commas, or only the form without them that the gate pages use?
- [ ] DTR and RTS of the DAPLink serial port: does opening the port reset the board? The tool's README says to check on a new board.
- [ ] Who writes and reviews the two wrapper scripts (`jlink-load.sh`, `jlink-verify.sh`), or is Procedure P used instead?
- [ ] How long does a 3 MiB load, verify and slot erase take on this board? The figures here are extrapolated, and the erase duration is Not verified.
- [ ] Are the fuses and lifecycle of this board open? No tool in the repository reads them.
- [ ] Is the content of slot 1 (`0x320000` to `0x620000`) and of the storage range known? The backup stops at `0x60600000`, and slot 1 ends at `0x620000`.
- [ ] How are addresses of the sparse signed `.hex` files mapped to the QSPI window? The trial build gives `--hex-addr 0x20000`. This procedure uses the full-size `.bin` files instead.
- [ ] Is `time-baseline.bin` the right restore image, or does the board in use have another accepted normal image? The historical bench BIN of the network gates is only a reference identity.
- [ ] Does MCUboot's console go to the same UART as the application, and is the speed 115200? **Inference** for both.
- [ ] Which `--version` and arguments does the current build's `imgtool` call use (section 4, step 6)?
- [ ] How many power cuts and at which times? Section 7 T6 proposes seven per window, spread.
- [ ] Who may start the serial downloader recovery, with which flashloader, and who reviews its licence? The route is not proven and #309 is not done.
- [ ] How is the development key kept available to the Linux build without sharing it? A directory in the Dev Container user's home is outside the bind mount but is lost when the container is removed; if it is lost, the images must be remade and MCUboot rebuilt and reprogrammed with a new key.
- [ ] Can a J-Link start and `ShowEmuList USB` read `VTref` inside a pause of 3 s or less? If not, what reads it?
- [ ] Where are the results stored, and who reviews them?
- [ ] If MCUboot does not start at T1: ROM acceptance of the image layout, SDRAM start by the DCD, or console routing? That is a finding, to be recorded before anything is changed.
