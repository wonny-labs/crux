# Native integrated output fixture

This finite native_sim fixture uses actual production format literals, native
LOG_PRINTK with one UART backend, a 16 KiB drop-new buffer, and the existing
native logger resource helper. Main priority 0 publishes 10 Hz feed payloads and
1 Hz observer/stack/logger groups; worker priority 5 and network priority 6 publish
finite Time/GPIO and pair-burst payloads. The verifier requires every record in
per-producer order, allowing cross-producer interleaving. A separate finite
high-priority burst must expose native message loss. Six mutations of the actual
lossless handler reject whitespace, ANSI, duplication, truncation and sequence
corruption; a seventh rejects producer work moved across the explicit fixture
fault/boot boundary.

Except the logger resource query, the payload values are synthetic, and the fixture touches no hardware. It is an output-path and bounded-workload check; the
target oracles and limits are in [the controller validation record](../../../docs/m3-validation.md).
