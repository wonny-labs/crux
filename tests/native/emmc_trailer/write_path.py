# SPDX-License-Identifier: Apache-2.0
"""Power-cut replay of MCUboot's trailer sequences over a modelled flash-over-disk write path.

A Recorder models a flash-API driver on top of the eMMC disk: flash_write and flash_erase become
512-byte sector writes in the eMMC simulator's trace format. The cache is flushed after every call
under the "flush" policy; after every erase call and every call that touches a slot's trailer
under "steps"; after calls that touch a trailer only, under "trailer"; and never under "none".
Image data writes are never flushed by the last three: the next flush covers them.

The update steps of RAM load with revert (erase the inactive slot, write the image, request a
test, the bootloader's trial, then confirm or revert) run over it, with a mark after each step
returns. The simulator's replay model (tests/native/emmc_powercut/replay_model.py) then rebuilds
the medium at every cut, and the trailer model decides what boots afterwards.

Device behaviours, in generic words:
- "fifo-barrier": the cache drains in the order written and barriers are supported. What
  survives a cut since the last flush is a prefix of the writes: the medium is the one the replay
  model's "prefix" gives at an earlier position q, while the acknowledgements are those of the
  cut ("fifo", one case per q).
- "unordered": no flush-order guarantee and no barrier. Any subset survives ("reordered").
- Both: "lost" (nothing since the last flush survives), "torn-sector" (the write being made
  mixes old and new bytes of its 512-byte sector, as the simulator's replay model has it),
  "torn-sector-wide" (the whole 512-byte sector of the write being made is indeterminate), and,
  for a 4 KiB native sector behind 512-byte emulation without reliable write, "torn-native"
  (every sector of the write's 4 KiB native unit is indeterminate).
- A trace made with reliable write has no torn cases: each 512-byte sector is old or new, and
  earlier data in the native unit is kept.
A barrier orders writes without making them durable. Under "fifo-barrier" the prefix model
already keeps order, and "unordered" has no barrier, so no policy here issues one.

Erased content of the medium is 0x00, as assumed for the modelled medium. The
driver reports an erase value of 0xFF and emulates erase by writing 0xFF, so it needs explicit
erase.

Every result is an observation of these models. None of it is evidence about a device.
"""
from collections import namedtuple
import os
import random
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'emmc_powercut'))

from replay_model import SECTOR, Event, build_image  # noqa: E402
from trailer_model import (FLAG_SET, MAGIC_UNSET, Layout, ModelImage, Slot,  # noqa: E402
                           boot_once, confirm_writes, copy_done_write, magic_write,
                           request_writes, swap_state)

KiB = 1024
MiB = 1024 * KiB
NATIVE = 4 * KiB
NATIVE_SECTORS = NATIVE // SECTOR
ERASE_VALUE = 0xFF
MEDIUM_ERASED = 0x00
BOOT_EBADIMAGE = 3

Device = namedtuple('Device', 'name order barrier')
DEVICES = (Device('fifo-barrier', 'fifo', True), Device('unordered', 'reordered', False))

Geometry = namedtuple('Geometry', 'erase_group wp_group native_sector', defaults=(NATIVE,))
Case = namedtuple('Case', 'position model seed acked results boot1 boot2')  # seed: q for fifo
Trace = namedtuple('Trace', 'events marks starts baseline config reliable path policy '
                             'early_marks calls padded')

_TYPES = {'write': 1, 'flush': 2, 'cache_on': 3, 'mark': 4}


class Recorder:
    """A flash-API driver over the disk, as seen from the host, recording each disk command."""

    def __init__(self, baseline, policy, write_block, page_size, reliable=False,
                 trailer_ranges=()):
        if policy not in ('flush', 'steps', 'trailer', 'none'):
            raise ValueError(f'unknown policy {policy!r}')
        if page_size % SECTOR or write_block > SECTOR and write_block % SECTOR:
            raise ValueError('pages are whole sectors and write blocks divide or fill them')
        self.policy = policy
        self.write_block = write_block
        self.page_size = page_size
        self.reliable = reliable
        self.trailer_ranges = tuple(trailer_ranges)
        self.visible = bytearray(baseline)
        self.events = [Event('cache_on', None, None, None)]
        self.marks = []
        self.calls = []  # (first event, end event, byte offset, byte length) of each call

    def _check(self, offset, size, unit):
        if offset < 0 or size <= 0 or offset % unit or size % unit or \
                offset + size > len(self.visible):
            raise ValueError(f'access of {size} bytes at {offset} is not aligned to {unit} '
                             'or outside the device')

    def _sectors(self, offset, data, erase=False):
        first = len(self.events)
        self.visible[offset:offset + len(data)] = data
        for sector in range(offset // SECTOR, (offset + len(data) - 1) // SECTOR + 1):
            start = sector * SECTOR
            self.events.append(Event('write', sector, bytes(self.visible[start:start + SECTOR]),
                                     None))
        self.calls.append((first, len(self.events), offset, len(data)))
        touches = any(offset < end and start < offset + len(data)
                      for start, end in self.trailer_ranges)
        if (self.policy == 'flush' or (self.policy == 'steps' and (touches or erase)) or
                (self.policy == 'trailer' and touches)):
            self.events.append(Event('flush', None, None, None))

    def write(self, offset, data):
        self._check(offset, len(data), self.write_block)
        self._sectors(offset, bytes(data))

    def erase(self, offset, size):
        self._check(offset, size, self.page_size)
        self._sectors(offset, bytes([ERASE_VALUE]) * size, erase=True)

    def mark(self, name):
        self.events.append(Event('mark', None, None, len(self.marks) + 1))
        self.marks.append((name, len(self.events) - 1))


def encode_trace(events):
    """The events in the eMMC simulator's trace format, one record per event."""
    out = bytearray()
    for event in events:
        kind = _TYPES[event.kind]
        if event.kind == 'write':
            out += struct.pack('<4I', kind, event.sector, 1, 0) + event.data
        else:
            out += struct.pack('<4I', kind, 0, 0, event.mark or 0)
    return bytes(out)


def window_start(events, position):
    """The first position after the last flush (or the cache being turned on) before `position`."""
    for index in range(position - 1, -1, -1):
        if events[index].kind in ('flush', 'cache_on'):
            return index + 1
    return 0


def rebuild(baseline, events, position, model, seed, order='prefix'):
    """The medium after a cut at `position`. For "fifo", `seed` is the drain position q, from
    window_start to `position`: every write before q survives and none after it. Torn models
    apply to the next write, on top of the device's order model with nothing else lost."""
    if model == 'fifo':
        if not window_start(events, position) <= seed <= position:
            raise ValueError(f'drain position {seed} is outside the window of {position}')
        return build_image(baseline, events, seed, 'prefix', 0)
    if model in ('lost', 'prefix', 'reordered'):
        return build_image(baseline, events, position, model, seed)
    if model not in ('torn-sector', 'torn-sector-wide', 'torn-native'):
        raise ValueError(f'unknown model {model!r}')
    base_order = 'prefix' if order == 'fifo' else order
    image = bytearray(build_image(baseline, events, position, base_order, seed))
    if position >= len(events) or events[position].kind != 'write':
        return bytes(image)
    event = events[position]
    draw = random.Random(seed)
    if model == 'torn-sector':
        start = event.sector * SECTOR
        mask = draw.getrandbits(SECTOR)
        image[start:start + SECTOR] = bytes(
            new if mask >> i & 1 else old
            for i, (old, new) in enumerate(zip(image[start:start + SECTOR], event.data)))
    elif model == 'torn-sector-wide':
        start = event.sector * SECTOR
        image[start:start + SECTOR] = draw.randbytes(SECTOR)
    else:
        first = event.sector // NATIVE_SECTORS * NATIVE_SECTORS * SECTOR
        image[first:first + NATIVE] = draw.randbytes(NATIVE)
    return bytes(image)


class LayoutConfig(namedtuple('LayoutConfig', 'name max_align write_block page_size slot_size '
                                              'slot_a_offset')):
    """Two slots on one disk: BOOT_MAX_ALIGN, the driver's write block and page size."""

    @classmethod
    def sector(cls, slot_a_offset=0, slot_size=32 * KiB):
        page = NATIVE if slot_a_offset % NATIVE == 0 else SECTOR
        name = 'sector' if slot_a_offset == 0 else f'sector-a@{slot_a_offset}'
        return cls(name, 512, 512, page, slot_size, slot_a_offset)

    @classmethod
    def rmw(cls, slot_size=32 * KiB):
        return cls('rmw', 8, 8, NATIVE, slot_size, 0)

    @classmethod
    def native(cls, slot_size=32 * KiB):
        """BOOT_MAX_ALIGN of one native unit: each trailer field in a unit of its own. Allowed
        only outside the swap modes, which cap it at 32 bytes."""
        return cls('native', NATIVE, NATIVE, NATIVE, slot_size, 0)

    @property
    def layout(self):
        return Layout(self.slot_size, self.max_align, self.write_block)

    @property
    def offsets(self):
        return (self.slot_a_offset, self.slot_a_offset + self.slot_size)

    @property
    def disk_size(self):
        end = self.slot_a_offset + 2 * self.slot_size
        return (end + NATIVE - 1) // NATIVE * NATIVE + NATIVE


def _put(medium, offset, data):
    medium[offset:offset + len(data)] = data


def baseline_medium(config):
    """Slot A: image 1 programmed padded to the whole slot, confirmed, after its first boot.
    Everything else reads as the medium's erased value, 0x00."""
    medium = bytearray([MEDIUM_ERASED]) * config.disk_size
    layout = config.layout
    a = config.slot_a_offset
    _put(medium, a, bytes([ERASE_VALUE]) * config.slot_size)
    _put(medium, a, ModelImage(1, 3000).encode())
    for offset, data in request_writes(layout, ERASE_VALUE, permanent=True):
        _put(medium, a + offset, data)
    offset, data = copy_done_write(layout, ERASE_VALUE)
    _put(medium, a + offset, data)
    return bytes(medium)


class SlotStore:
    """The two slots through the driver, as MCUboot's flash areas see them."""

    def __init__(self, recorder, config):
        self.rec = recorder
        self.config = config

    def read(self, slot):
        base = self.config.offsets[slot]
        return bytes(self.rec.visible[base:base + self.config.slot_size])

    def write(self, slot, offset, data):
        self.rec.write(self.config.offsets[slot] + offset, data)

    def scramble(self, slot):
        """boot_erase_region on a device that needs explicit erase: page by page, forward."""
        base = self.config.offsets[slot]
        for offset in range(0, self.config.slot_size, self.rec.page_size):
            self.rec.erase(base + offset, self.rec.page_size)


class _Durable:
    """A store without a cache, for the boots after a cut."""

    def __init__(self, medium, config):
        self.medium = bytearray(medium)
        self.config = config

    def read(self, slot):
        base = self.config.offsets[slot]
        return bytes(self.medium[base:base + self.config.slot_size])

    def write(self, slot, offset, data):
        _put(self.medium, self.config.offsets[slot] + offset, data)

    def scramble(self, slot):
        _put(self.medium, self.config.offsets[slot], bytes([ERASE_VALUE]) * self.config.slot_size)


def _write_image(store, layout, slot, image, chunk=4 * KiB):
    unit = layout.write_block
    padded = image + bytes([ERASE_VALUE]) * (-len(image) % unit)
    for offset in range(0, len(padded), chunk):
        store.write(slot, offset, padded[offset:offset + chunk])


def padded_image(layout, image, erased_val):
    """imgtool --pad: the image, the erased value up to the trailer, and the trailer magic as
    boot_write_magic would write it (assumed to be the same bytes)."""
    slot = bytearray([erased_val]) * layout.slot_size
    slot[:len(image)] = image
    offset, data = magic_write(layout, erased_val)
    slot[offset:offset + len(data)] = data
    return bytes(slot)


def run_scenario(path, config, policy, reliable=False, early_marks=False, padded=False):
    """Record one update of slot B with the given driver policy.

    path "confirm": erase B, write image 2, request a test, the bootloader's trial, confirm.
    path "revert": the same, then the image fails before confirming and the next boot reverts.
    padded: the image is signed with --pad, so writing it is the request: it carries the trailer
    magic, is written in ascending order and no request call follows (owner decision 13 of the
    update investigation).
    early_marks puts each mark before its step, a control that acknowledges too soon.
    """
    if path not in ('confirm', 'revert'):
        raise ValueError(f'unknown path {path!r}')
    layout = config.layout
    baseline = baseline_medium(config)
    trailers = [(base + layout.trailer_start, base + config.slot_size)
                for base in config.offsets]
    rec = Recorder(baseline, policy, config.write_block, config.page_size, reliable, trailers)
    store = SlotStore(rec, config)
    starts = {}

    def step(name, action):
        starts[name] = len(rec.events)
        if early_marks:
            rec.mark(name)
        action()
        if not early_marks:
            rec.mark(name)

    def erase():
        for offset in range(0, config.slot_size, config.page_size):
            rec.erase(config.offsets[1] + offset, config.page_size)

    def request():
        if swap_state(layout, store.read(1), ERASE_VALUE).magic != MAGIC_UNSET:
            raise RuntimeError('the request found a trailer that is not unset')
        for offset, data in request_writes(layout, ERASE_VALUE, permanent=False):
            store.write(1, offset, data)

    def expect_boot(expected):
        def action():
            booted = boot_once(layout, store, ERASE_VALUE)
            if booted != expected:
                raise RuntimeError(f'expected {expected}, booted {booted}')
        return action

    def confirm():
        state = swap_state(layout, store.read(1), ERASE_VALUE)
        for offset, data in confirm_writes(layout, state, ERASE_VALUE):
            store.write(1, offset, data)

    step('erased', erase)
    if padded:
        image = padded_image(layout, ModelImage(2, 3000).encode(), ERASE_VALUE)
        step('image', lambda: _write_image(store, layout, 1, image))
        step('requested', lambda: None)
    else:
        step('image', lambda: _write_image(store, layout, 1, ModelImage(2, 3000).encode()))
        step('requested', request)
    step('trial', expect_boot(Slot(1, 2)))
    if path == 'confirm':
        step('confirmed', confirm)
    else:
        step('reverted', expect_boot(Slot(0, 1)))
    return Trace(rec.events, rec.marks, starts, baseline, config, reliable, path, policy,
                 early_marks, rec.calls, padded)


def _field_ranges(layout):
    """Byte ranges of the four trailer fields as MCUboot writes them, relative to the slot."""
    magic_off, magic_len = layout.magic_write
    flag = layout.flag_write_size
    return [(magic_off, magic_off + magic_len),
            (layout.image_ok_off, layout.image_ok_off + flag),
            (layout.copy_done_off, layout.copy_done_off + flag),
            (layout.swap_info_off, layout.swap_info_off + flag)]


def collateral_free(trace, medium, base, position):
    """No trailer field changed between `base`, the medium without the torn write, and
    `medium`, except fields the in-flight call was writing. Slot A is never being written."""
    if base is None:
        return True
    config = trace.config
    flight = [(offset, offset + length) for first, end, offset, length in trace.calls
              if first <= position < end]
    for slot, origin in enumerate(config.offsets):
        for start, end in _field_ranges(config.layout):
            lo, hi = origin + start, origin + end
            if slot == 1 and any(lo < f_hi and f_lo < hi for f_lo, f_hi in flight):
                continue
            if medium[lo:hi] != base[lo:hi]:
                return False
    return True


def _evaluate(trace, medium, acked, position, model, base=None):
    config = trace.config
    layout = config.layout
    a, b = config.offsets
    size = config.slot_size
    v2_confirmed = swap_state(layout, medium[b:b + size], ERASE_VALUE).image_ok == FLAG_SET
    store = _Durable(medium, config)
    boot1 = boot_once(layout, store, ERASE_VALUE)
    boot2 = boot_once(layout, store, ERASE_VALUE)  # another reset, nothing confirmed meanwhile
    new, old = Slot(1, 2), Slot(0, 1)
    # No write of the trial has been issued. A torn model at the trial's first position tears
    # that write, so the trial is in flight there.
    start = trace.starts['trial']
    before_trial = position < start or (position == start and not model.startswith('torn'))
    results = {
        'P1': boot1 is not None and boot2 is not None,
        'P2': medium[a:a + size] == trace.baseline[a:a + size],
        'P3': 'confirmed' not in acked or (boot1 == new and boot2 == new),
        'P4': not ('trial' in acked and 'confirmed' not in acked and boot1 == new and
                   not v2_confirmed),
        'P5': not ('requested' in acked and before_trial) or boot1 == new,
        'P6': 'reverted' not in acked or boot1 == old,
        'P7': collateral_free(trace, medium, base, position),
    }
    return results, boot1, boot2


PROPERTIES = {
    'P1': 'a valid image boots after the cut and after one more reset (safety)',
    'P2': 'slot A, the confirmed old image, is byte-identical to the baseline (safety)',
    'P3': 'an acknowledged confirm survives: image 2 boots, twice',
    'P4': 'after an acknowledged trial, unconfirmed image 2 is not started again',
    'P5': 'an acknowledged test request survives until the trial starts: image 2 is tried '
          '(liveness)',
    'P6': 'an acknowledged revert survives: image 1 boots (liveness)',
    'P7': 'a torn write changes no trailer field other than the ones it was writing',
}


def models_for(trace, device, models=None):
    chosen = models or ('lost', device.order, 'torn-sector', 'torn-sector-wide', 'torn-native')
    if trace.reliable:
        chosen = tuple(m for m in chosen if not m.startswith('torn'))
    return chosen


def _trailer_sectors(config):
    """Sectors of the last native unit of each slot, where the trailer lives."""
    sectors = set()
    for base in config.offsets:
        end = (base + config.slot_size) // SECTOR
        sectors.update(range(end - NATIVE_SECTORS, end))
    return sectors


def drain_positions(trace, position, seeds):
    """Drain positions q for a "fifo" case: every q in a window of up to 64 events; otherwise
    each side of every trailer write, the window's ends, and one seeded draw per seed."""
    start = window_start(trace.events, position)
    if position - start <= 64:
        return list(range(start, position + 1))
    trailer = _trailer_sectors(trace.config)
    chosen = {start, position}
    for index in range(start, position):
        event = trace.events[index]
        if event.kind == 'write' and event.sector in trailer:
            chosen.update((index, index + 1))
    for seed in seeds:
        chosen.add(random.Random(seed * 7919 + position).randint(start, position))
    return sorted(chosen)


def replay(trace, device, seeds=(0, 1, 2, 3), models=None, positions=None):
    """Every cut position under each model of the device; random models once per seed, and
    "fifo" once per drain position."""
    cases = []
    mark_at = [index for _, index in trace.marks]
    names = [name for name, _ in trace.marks]
    for position in (positions if positions is not None else range(len(trace.events) + 1)):
        acked = frozenset(name for name, index in zip(names, mark_at) if index < position)
        for model in models_for(trace, device, models):
            if model == 'fifo':
                draws = drain_positions(trace, position, seeds)
            elif model in ('reordered', 'torn-sector', 'torn-sector-wide', 'torn-native'):
                draws = seeds
            else:
                draws = (0,)
            for seed in draws:
                medium = rebuild(trace.baseline, trace.events, position, model, seed,
                                 order=device.order)
                base = None
                if model.startswith('torn'):
                    base = build_image(trace.baseline, trace.events, position,
                                       'prefix' if device.order == 'fifo' else device.order, seed)
                results, boot1, boot2 = _evaluate(trace, medium, acked, position, model, base)
                cases.append(Case(position, model, seed, acked, results, boot1, boot2))
    return cases


def staged_unerased_request(config):
    """Image 2 written to a natively erased slot B without a driver erase, as an agent would
    if the driver reported no explicit erase. Returns the request's result code, what boots,
    and the trailer state the request saw."""
    layout = config.layout
    rec = Recorder(baseline_medium(config), 'flush', config.write_block, config.page_size)
    store = SlotStore(rec, config)
    _write_image(store, layout, 1, ModelImage(2, 3000).encode())
    state = swap_state(layout, store.read(1), ERASE_VALUE)
    rc = 0 if state.magic == MAGIC_UNSET else BOOT_EBADIMAGE  # boot_set_next, MAGIC_BAD case
    booted = boot_once(layout, store, ERASE_VALUE)
    return rc, booted, state


def check_layout(slots, geometry, fs_volume=None):
    """Alignment problems of slots given as (offset, size) in bytes on the user area."""
    problems = []
    rules = ((geometry.native_sector, 'the native sector (needed so that a torn write cannot '
              'reach another slot)'),
             (geometry.erase_group, 'the erase group (needed only if slots are erased natively)'),
             (geometry.wp_group, 'the write-protect group (needed only for per-slot write '
              'protection)'))
    for number, (offset, size) in enumerate(slots):
        for unit, why in rules:
            if offset % unit or size % unit:
                problems.append(f'slot {number} at {offset} of {size} bytes is not aligned to '
                                f'{why}, {unit} bytes')
        if fs_volume and offset < fs_volume[0] + fs_volume[1] and fs_volume[0] < offset + size:
            problems.append(f'slot {number} overlaps the file-system volume')
    for i, (off_i, size_i) in enumerate(slots):
        for j in range(i + 1, len(slots)):
            off_j, size_j = slots[j]
            if off_i < off_j + size_j and off_j < off_i + size_i:
                problems.append(f'slots {i} and {j} overlap')
    return problems
