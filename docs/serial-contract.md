# Portable Serial contract

**Freeze notice (13 November 2026).** Serial is frozen for new product code: no new features and no real-time extension. New product code uses Zephyr directly for threads, locks, queues and UARTs; see [Choosing an API](choosing-an-api.md). This adds no promise and removes none. The contract below and its tests and evidence stay as they are, and existing users keep working. Whether the interface is deprecated waits for a later decision under P9 of [ADR-0002](decisions/0002-platform-direction-zephyr-execution-crux-services.md). The product template's [domain include check](../templates/product/README.md#zones-and-the-domain-include-check) rejects the header in a product's domain.

The [approved design](design/serial-design.md), approved on
24 October 2026, defines the four functions in `<crux/serial.h>` and remains the
normative detailed contract. The [validation record](serial-validation.md) identifies its
implementation/evidence.

`crux::serial` exposes only Crux Base, C17-compatible values and caller buffers.
Component-owned common code validates configuration, generations and admission;
private Linux TTY and Zephyr interrupt UART providers own native execution.
There is no new OSAL or public callback/event/thread facility.

A successful nonempty read/write returns a positive, possibly short prefix.
Write success means buffer acceptance, never wire delivery. Callers preserve
buffers until return and implement framing, transaction identity and any retry
policy themselves. Poll zero returns BUSY on unavailable resources or metadata
contention. A finite timeout uses one monotonic deadline including admission;
a timed-out native wait cannot later commit. This is not a whole-call WCET bound.

One port has one owner, with one read and one write allowed concurrently.
Same-direction overlap and close during admitted work return BUSY. Close consumes
an idle handle even on native cleanup IO, discards provider buffers, and gates
cached callbacks. It cannot recall hardware/wire bytes or establish a new wire
epoch. Failed cleanup quarantines an uncertain native binding. Generation values
never wrap into stale-handle validity.

Logical port 0 must be explicitly bound by native composition. Linux binds once
before concurrent use and checks native TTY identity/exclusivity; Zephyr binds
`crux-serial0` and rejects missing/unsupported static resources and known Console,
Shell, UART Logging, management and Bluetooth owners at build time. Only native_sim
UART emulators and, on any board, enabled nodes of a reviewed UART driver selected by
compatible (`nxp,lpuart`) are admitted; no board, SoC or revision is checked, and a board
accepted this way is not qualified. UART sharing is
unsupported and is not required by the platform validation plan. `CRUX_SERIAL_PROVIDER` defaults to `host`
or `zephyr` in the respective native composition; other or empty selections fail
configuration. Host dynamic TTY binding remains a runtime bootstrap responsibility.
Direct unregistered native clients violate this composition rule.
The EVKB candidate uses LPUART3, retaining LPUART1 diagnostics. Pin conflicts are a
fact of the board, and Crux Serial checks none: the EVKB composition
(`tests/serial_consumer/zephyr/CMakeLists.txt`) refuses an enabled CSI node with Serial on
LPUART3 or LPUART8, which share pins with CSI on the EVK, and another board's pin conflicts
are the product's to review. Electrical pin/connector suitability remains unverified.

Initial resources: one port, Zephyr 256-byte RX and TX rings, Host at most
256-byte staging/commit chunks plus independent kernel TTY queues. Requests map
9600/19200/38400/57600/115200, 7/8 data bits, 1/2 stop bits and N/E/O parity, or
return NOT_SUPPORTED when native readback cannot establish them. This is not
physical qualification of every combination. Initial physical proposal is
115200 8N1 only, without flow control.

Observed UART errors and provider RX overflow latch IO until close/reopen.
An error unsupported/unreported by the native driver cannot be inferred. UART
wire disconnection usually has no observable hangup signal; a silent peer can
time out. Linux qualified PTY HUP differs from electrical UART disconnect.
Zephyr closes with a bounded native RX discard (at most 1024 bytes); continuous
incoming traffic that exhausts it yields IO and quarantine rather than unbounded
cleanup. Bytes already admitted into a hardware TX FIFO cannot be recalled.

Deferred: RS-485, USB CDC, DMA/async UART, modem/break control, dynamic port
registry, flush/drain, persistent configuration, automatic retries and protocol
resynchronisation. Hardware, merge and issue closure need separate approval.
