# Crux Time API contract

Time provides typed clocks, authority state and Gregorian UTC conversion. The
[accepted redesign](superpowers/specs/2026-10-25-time-redesign.md) replaces the
original Pilot's whole-second RTC-backed get/set contract. The initial plan and
[baseline](baseline.md) retain historical evidence; those physical results do
not qualify this redesigned API or its native system realtime implementation.

## Common status ownership

`<crux/status.h>` belongs to independent `crux::base`. Time uses its existing
status codes, including INVALID_ARGUMENT, OUT_OF_RANGE, NOT_READY, NO_DATA, IO,
NOT_SUPPORTED and INVALID_STATE. No duplicate Time status enum is introduced.

## Public Time API

The C17 API supports C++17 consumers through `extern "C"`. Link `crux::time`;
do not include private implementation directories or name backend targets.

| Header | Contract |
| --- | --- |
| `<crux/time_types.h>` | Distinct duration, monotonic timestamp and realtime value types; checked arithmetic |
| `<crux/time.h>` | Monotonic observation/deadlines, realtime init/observation and consistent snapshot |
| `<crux/time_authority.h>` | Explicit realtime set, adopt, synchronization and invalidation |
| `<crux/time_calendar.h>` | Pure Gregorian UTC/realtime conversion, including nanoseconds |

`crux_duration_t` is signed nanoseconds. `crux_monotonic_time_t` is nonnegative
provider/session-local nanoseconds, not an epoch or interchangeable clock domain.
`crux_realtime_t` contains signed POSIX epoch `seconds` and normalized uint32
`nanoseconds` in 0..999999999. Representation does not promise resolution or
accuracy. No leap seconds, implicit normalization, saturation or FOREVER encoding.
Checked failures preserve outputs; constructors and arithmetic retain the typed
foundation's overflow and signed rounding rules.

Realtime/calendar support `[2000-01-01T00:00:00, 2100-01-01T00:00:00)` UTC.
The seven-field `crux_datetime_t` adds nanoseconds to year/month/day/hour/minute/
second. Both conversion directions preserve fractions. Validate NULL, field
ranges and actual month length before the year range; malformed values are
INVALID_ARGUMENT and valid dates outside 2000..2099 are OUT_OF_RANGE. Conversion
is pure and reentrant with distinct output storage, without init/native locks.

The superseded `crux_time_instant_t`, `crux_time_get()` and `crux_time_set()`
are removed. Migrate to typed realtime and explicitly supply authority source.
No compatibility wrapper silently assigns authority or persists RTC storage.

## Typed monotonic observation and deadlines

`crux_monotonic_now()` and `crux_monotonic_deadline_after()` need neither
realtime init nor RTC. Linux uses CLOCK_MONOTONIC; Zephyr uses uptime ticks.
Concurrent thread callers use distinct output storage; ISR is NOT_SUPPORTED.
Negative duration is INVALID_ARGUMENT. Zero returns the unadjusted observation.
Positive duration compensates clock quantisation from one internal sample, not
from function return. Zephyr uses the upper bound of the next tick boundary.
Overflow/failure preserves output. Pure `crux_monotonic_add()` adds no
padding. [Thread sleep](thread-sync.md#current-thread-sleep) owns native wait
encoding limits and rechecks one original absolute deadline after early wakes.
A valid Time comparison deadline can exceed Thread's native finite timeout range.

## Header and build ownership

Follow the [repository dependency rules](../CONTRIBUTING.md#public-headers-and-module-dependencies).

| Implementation | Selection and visibility |
| --- | --- |
| `components/time/src/` | Common state, types/calendar/clock logic and separately selected OS-independent memory store |
| `components/time/src/realtime_port.h` | Private realtime init/read/write/lock contract; native lock rejects ISR |
| `components/time/src/monotonic_port.h` | Private raw-nanosecond observation and single-sample conservative upper bound |
| `components/time/src/busy_wait_port.h` | Private optional native wait or explicitly disabled implementation |
| `components/interrupt/src/interrupt.h` | Shared private ISR mechanism, no public usage target or native header leakage |
| `components/time/ports/linux/` | Native monotonic clock, pthread lock and optional CLOCK_REALTIME provider |
| `components/time/ports/zephyr/` | Native uptime/system realtime/lock and optional RTC adapter |
| `tests/time/*.h` | Private test controls, excluded from public usage roots |
| `samples/time/include/` | Sample-owned command interface |

External Linux applications select `CRUX_BUILD_TIME=ON` and explicitly choose
`CRUX_TIME_PROVIDER=memory` or `linux`. Top-level development builds default to
memory. Exactly one realtime provider is composed; Linux cannot silently fall
back to memory. Native lock/clock requirements stay private, and the established
consumer boundary checker remains enforced. Current supported glibc resolves
pthread operations in libc, as for Thread/Sync; other toolchains retain their
actual link requirements. This is not an installed package/ABI promise or
production Linux qualification.

Memory realtime is a controlled, non-progressing development/test store. It never
reads/writes the OS wall clock. Only private test controls advance it or inject
failures; these require serialized test use. Controlled Host shell/controller
samples require memory, so choosing the Linux system provider cannot silently
turn their demonstration writes into operating-system clock changes.

Zephyr `CONFIG_CRUX_TIME=y` provides native system realtime (`SYS_CLOCK_REALTIME`)
and monotonic uptime without RTC. Thread selects Time for sleep. Time does not
depend on Thread or public Sync. Optional `CONFIG_CRUX_TIME_RTC=y` additionally
requires RTC and compiles a trusted native adapter for the `rtc` devicetree alias;
it is not selected automatically. There is no runtime provider registry.

## State and error precedence

The first successful `crux_realtime_init()` enters ready-but-unset. It never writes a
default, adopts native time or loads RTC. Failed init is retryable; repeated
successful init preserves authority state. Public realtime operations require
thread context and share a private native mutex across clock access and metadata.
They support concurrent callers with distinct outputs. ISR is NOT_SUPPORTED;
validated argument errors precede context/readiness/native access. Do not re-enter
Time from provider operations while the lock is held.

`crux_realtime_now()` returns NO_DATA without a native read when invalid.
`crux_realtime_get_snapshot()` instead returns OK with a zero timestamp,
retained `last_source`, validity false and synchronization false. Before init,
both return NOT_READY and preserve output.

| Native observation | Result and state |
| --- | --- |
| OK, normalized and in range | Commit timestamp and metadata from one locked transaction |
| NO_DATA | Invalidate time/sync; getter returns NO_DATA, snapshot returns OK/invalid/zero |
| OUT_OF_RANGE or observed seconds outside supported range | Invalidate time/sync, retain source, return OUT_OF_RANGE and preserve output |
| Other read error, including malformed native nanoseconds mapped to IO | Preserve output and authority state |

The lock guarantees consistency among Crux operations. It cannot serialize native
clock setters outside Crux or guarantee snapshot consistency for those changes.
The designated product Time Authority must coordinate native clock changes with
any external NTP/PTP time manager and owns source selection and stale
synchronization callbacks. Separating the authority header is not a runtime
permission or authentication mechanism.

On Linux, setting CLOCK_REALTIME requires appropriate system permissions,
normally [CAP_SYS_TIME](https://man7.org/linux/man-pages/man7/capabilities.7.html).
Selecting the Linux provider or calling the Time Authority API does not grant
those permissions. Automated tests must not modify the real Host system clock.
Linux realtime-write tests use the controlled Memory provider or wrapped native
setters.

## Time Authority

`last_source` is NONE (0), UNKNOWN (1), RTC (2), MANUAL (3) or EXTERNAL (4).
It records the last successful establishment; it is not an accuracy estimate.
Valid time has a non-NONE source. Active synchronization implies valid time and
EXTERNAL source.

| Operation | Effect |
| --- | --- |
| `crux_realtime_adopt()` | Read/validate native clock without writing; success sets UNKNOWN, valid, unsynchronized |
| `crux_realtime_set(&value, source, sync)` | Set system clock and metadata as one transaction; accepts RTC/MANUAL/EXTERNAL and sync=true only with EXTERNAL |
| `crux_realtime_set_synchronized(sync)` | Metadata only, no clock write; invalid time gives NO_DATA; true with non-EXTERNAL valid source gives INVALID_STATE |
| `crux_realtime_invalidate()` | Clear validity/sync, retain previous source, no native read/write |

Reject malformed values/sources before native access and preserve state. An
actual native write failure invalidates time/sync because the clock might have
changed, while retaining the **previous** source. Lock/context/readiness failures
do not attempt a native write. Set success says nothing about RTC persistence.

## Private port and link selection

Common realtime state and selected native clock access share a provider-owned
lock initialized independently of Time readiness. Linux uses a statically
initialized pthread mutex. Zephyr uses a static kernel mutex; with multithreading
disabled the sole non-ISR context cannot interleave. No allocation or new public
synchronization service is required. Monotonic reads remain independent of this
realtime lock and initialization.

The optional native-only `time_rtc_zephyr.h` adapter offers explicit RTC read/store.
It reuses existing error mapping and calendar conversion, preserves read outputs
on failure and never accesses common authority state. Application composition
chooses when to read, establish system time with source RTC, or separately store
it. A failed store does not invalidate a successful system realtime update.
Current RTC storage accepts whole seconds only; normalized nonzero fractions
return NOT_SUPPORTED before any write rather than being silently truncated.
Missing/unready RTC returns NOT_READY. No generic public RTC framework is added.

## Loading the RTC at boot (product recipe)

This section is guidance. It restates the contract above and adds no interface, option or
behaviour.

**Where it belongs.** Crux never loads the RTC. `crux_realtime_init()` leaves Time ready but
unset, and it never writes a default, adopts native time or loads RTC
([`<crux/time.h>`](../components/time/include/crux/time.h), and [State and error
precedence](#state-and-error-precedence)). Whether to load, from which device, whether to trust
the value and what to do when there is none are application policy
(`components/time/ports/zephyr/time_rtc_zephyr.h:6-10`; [Private port and link
selection](#private-port-and-link-selection)). A product therefore reads the RTC in its own Zephyr
code, in an adapter or in composition, and calls the public Time Authority API. This is route 1
of [Composition interface rules](composition-interfaces.md): a Zephyr feature that Crux does not
offer, behind code the product owns, with no Crux change.

**Do not include `time_rtc_zephyr.h`.** It is a private port header, not a composition
interface. It sits beside the port in `components/time/ports/zephyr/`, and no usage target
publishes it: `crux::time` exposes only `components/time/include`, and there is no
`crux::time_zephyr` target or header under `ports/zephyr/include/crux/` as the
[composition rules](composition-interfaces.md#the-six-rules) require. Private headers and `ports/`
include paths are named as not being an escape hatch
([composition-interfaces.md](composition-interfaces.md#what-is-not-an-escape-hatch)), and Zephyr
calls stay in adapters ([ADR-0001](decisions/0001-application-boundary-and-api-stability.md), D2).
Crux's own Zephyr test includes it, which a test may do and a product may not
(`tests/time/zephyr/main.c`). `CONFIG_CRUX_TIME_RTC` is not needed for this recipe: it only
compiles that private adapter.

**Recipe.** Run once in thread context, after the devicetree and the RTC driver are up and before
code that needs valid realtime:

1. `crux_realtime_init()`. `crux_realtime_set()` returns NOT_READY before it.
2. Check the product's RTC device with `device_is_ready()`, then read it with Zephyr's
   `rtc_get_time()`. In `struct rtc_time`, `tm_year` counts from 1900 and `tm_mon` runs 0 to 11
   (`include/zephyr/drivers/rtc.h:62-73` in Zephyr). Zephyr returns -ENODATA when the RTC time has
   not been set (`rtc.h:267`).
3. Fill a `crux_datetime_t` from the fields (year `tm_year + 1900`, month `tm_mon + 1`) and call
   `crux_realtime_from_utc()`. Crux's own adapter treats the RTC fields as UTC; use the same
   convention for what the product stores in the RTC.
4. `crux_realtime_set(&value, CRUX_REALTIME_SOURCE_RTC, false)`. Synchronized is false, because
   true is accepted only with EXTERNAL.

```c
/* Product Zephyr adapter, called once from the boot sequence. `rtc` is the
 * device the product chose (for example DEVICE_DT_GET(DT_ALIAS(rtc))). */
crux_status_t product_adopt_rtc_at_boot(const struct device *rtc)
{
    crux_status_t status = crux_realtime_init();
    if (status != CRUX_OK) {
        return status;
    }
    if (!device_is_ready(rtc)) {
        return CRUX_ERR_NOT_READY; /* time stays invalid */
    }

    struct rtc_time native = {0};
    if (rtc_get_time(rtc, &native) != 0) { /* -ENODATA: never set */
        return CRUX_ERR_NO_DATA;          /* time stays invalid */
    }

    const crux_datetime_t utc = {
        .year = native.tm_year + 1900,
        .month = native.tm_mon + 1,
        .day = native.tm_mday,
        .hour = native.tm_hour,
        .minute = native.tm_min,
        .second = native.tm_sec,
        .nanoseconds = (uint32_t)native.tm_nsec,
    };
    crux_realtime_t value;
    status = crux_realtime_from_utc(&utc, &value);
    if (status != CRUX_OK) {
        return status; /* INVALID_ARGUMENT or OUT_OF_RANGE: do not set */
    }
    return crux_realtime_set(&value, CRUX_REALTIME_SOURCE_RTC, false);
}
```

The function needs `<crux/time.h>`, `<crux/time_authority.h>`, `<crux/time_calendar.h>`,
`<zephyr/device.h>` and `<zephyr/drivers/rtc.h>`, and the product's Kconfig needs `CONFIG_RTC`
with a driver for its device. Crux's own test does the same sequence with the private adapter's
read (`tests/time/zephyr/main.c:182-185` and `:200-204`).

**Errors and what they leave behind.** The product decides what to do after each one. Crux's part
is this:

| Step | Failure | State after |
| --- | --- | --- |
| Device not ready, or `rtc_get_time()` fails | The product returns without calling set | Time stays unset or invalid. `crux_realtime_now()` returns NO_DATA, and the snapshot is OK with validity false ([State and error precedence](#state-and-error-precedence)) |
| `crux_realtime_from_utc()` | INVALID_ARGUMENT for malformed fields, OUT_OF_RANGE for a valid date outside 2000 to 2099 | Pure conversion, nothing changed |
| `crux_realtime_set()` | INVALID_ARGUMENT or OUT_OF_RANGE, NOT_READY before init, NOT_SUPPORTED in an ISR | Rejected before native access, state preserved |
| `crux_realtime_set()` | The native clock write fails | Validity and synchronization are cleared, and the previous source is kept (the clock might have changed) |

- A date inside 2000 to 2099 passes the range check. An RTC that restarted at a hardware default
  in that range reads as a valid value, so any plausibility floor is the product's policy. This
  follows from the supported range above. It is not a statement about any particular RTC part.
- Success says nothing about RTC persistence, and `CRUX_REALTIME_SOURCE_RTC` records the last
  establishment, not accuracy ([Time Authority](#time-authority)).
- Later sources, such as a user or a network time client, call `crux_realtime_set()` with MANUAL or
  EXTERNAL. Writing the time back to the RTC is also the product's choice, with Zephyr's
  `rtc_set_time()`. Crux's adapter stores whole seconds only
  (`time_rtc_zephyr.h:9-10`), so a product that stores fractions owns that decision.

**Not verified.** The snippet was checked only for syntax against the Crux headers and stand-in
declarations of the two Zephyr headers. It has not been built in a Zephyr image or run on a board.
Historical RTC measurements do not apply to the redesigned Time API
([Host command composition](#host-command-composition)).

## Host command composition

The portable sample still accepts `time set YYYY-MM-DDTHH:MM:SS`, `time get` and
`help`. Set supplies zero fractional seconds and MANUAL/unsynchronized authority.
Get renders whole seconds; the underlying typed API/calendar retain fractions.
No-data remains NO_DATA in the API and `ERR NOT_SET` in the command presentation.
Host and Zephyr Shell adapters share this parser and initialize Time explicitly.
The upstream RTC Shell stays disabled. Zephyr commands now use native system
realtime and do not implicitly persist RTC. Native simulation, wrapped Linux
writes and software cross-builds provide software evidence only; historical
physical RTC measurements are not evidence for the new implementation.

## Unified Time migration (Issue #87)

Time also owns [optional CPU Busy-wait](time-busy-wait.md). `crux_busy_wait()` is
always declared in `<crux/time.h>` when Time is available, regardless of native
Busy-wait selection. There is no separate Delay component/header/usage target or
maximum query. Thread retains sleep; Time does not depend on Thread or Sync.

| Previous API | Current API |
| --- | --- |
| `crux_time_get_monotonic`, `crux_time_make_deadline_after` | `crux_monotonic_now`, `crux_monotonic_deadline_after` |
| `crux_monotonic_add_duration` | `crux_monotonic_add(base, delta, out)` |
| `crux_time_init`, `crux_time_get_realtime`, `crux_time_get_realtime_snapshot` | `crux_realtime_init`, `crux_realtime_now`, `crux_realtime_get_snapshot` |
| `crux_time_adopt_realtime`, `crux_time_set_realtime` | `crux_realtime_adopt`, `crux_realtime_set` |
| `crux_time_notify_sync_state`, `crux_time_invalidate_realtime` | `crux_realtime_set_synchronized`, `crux_realtime_invalidate` |
| `crux_time_source_t`, `CRUX_TIME_SOURCE_*` | `crux_realtime_source_t`, `CRUX_REALTIME_SOURCE_*` (numeric values retained) |
| snapshot `is_time_valid`, `is_actively_synchronized` | `is_valid`, `is_synchronized` |
| `crux_time_utc_t`, `crux_time_from_utc`, `crux_time_to_utc` | `crux_datetime_t`, `crux_realtime_from_utc`, `crux_realtime_to_utc` |

`crux_datetime_t` contains calendar fields without timezone data. The UTC
conversions interpret those fields as UTC; no timezone or leap-second support is
added. This is an intentional source migration without permanent wrappers or an
installed ABI guarantee. Existing signed arithmetic, quantization compensation,
realtime metadata/error transitions and output-preservation rules are retained.
Touched private OS boundaries use `_impl_` names with `monotonic_port.h`,
`realtime_port.h`, `busy_wait_port.h` and `thread_sleep_port.h`. The common private
ISR query is shared without exposing its header to public consumers.
