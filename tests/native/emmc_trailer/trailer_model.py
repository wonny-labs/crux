# SPDX-License-Identifier: Apache-2.0
"""A model of MCUboot's image trailer rules in RAM load with revert, for power-cut replay.

Written from reading MCUboot 6d3b3d2c38ab20c242e5b9abb04d050086383eb2 (the revision in Zephyr
v4.4.2's west.yml) and Zephyr v4.4.2. No MCUboot code is copied or linked; each rule names the
upstream function it follows, so that a reviewer can compare it with the pinned source:

- Trailer offsets: boot_magic_off, boot_image_ok_off, boot_copy_done_off (bootutil_misc.h) and
  boot_swap_info_off (bootutil_public.c), with the alignment unit BOOT_MAX_ALIGN.
- Trailer writes: boot_write_magic writes ALIGN_UP(16, BOOT_MAX_ALIGN) bytes ending at the slot
  end; boot_write_trailer writes ALIGN_UP(1, write block) bytes padded with the erased value and
  refuses a size above BOOT_MAX_ALIGN.
- Decoding: boot_read_swap_state, boot_read_flag and boot_magic_decode. A field equal to the
  erased value throughout is unset; a flag of 1 is set; anything else is bad.
- Application requests: boot_set_next, the variant without MCUBOOT_BOOTUTIL_LIB_FOR_DIRECT_XIP,
  which Zephyr v4.4.2 uses in RAM load with revert (modules/Kconfig.mcuboot).
- Boot decision: boot_load_and_validate_images, find_slot_with_highest_version,
  boot_select_or_erase and boot_validate_slot (loader.c), boot_scramble_region (bootutil_area.c).

The image is a model too: a header with MCUboot's magic, version and size fields, a body, and a
SHA-256 digest that stands in for the hash and signature check. Validation is "the digest
matches". Nothing here is evidence about MCUboot itself or about a device.
"""
from collections import namedtuple
import hashlib
import struct

MAGIC_GOOD, MAGIC_BAD, MAGIC_UNSET = 1, 2, 3
FLAG_SET, FLAG_BAD, FLAG_UNSET = 1, 2, 3
SWAP_TYPE_TEST, SWAP_TYPE_PERM = 2, 3

_MAGIC_ALIGN_8 = bytes([0x77, 0xc2, 0x95, 0xf3, 0x60, 0xd2, 0xef, 0x7f,
                        0x35, 0x52, 0x50, 0x0f, 0x2c, 0xb6, 0x79, 0x80])
_MAGIC_TAIL = bytes([0x2d, 0xe1, 0x5d, 0x29, 0x41, 0x0b, 0x8d, 0x77,
                     0x67, 0x9c, 0x11, 0x0f, 0x1f, 0x8a])
MAGIC_SIZE = 16

SwapState = namedtuple('SwapState', 'magic swap_type copy_done image_ok')
Slot = namedtuple('Slot', 'index version')


class AlignmentError(ValueError):
    """A trailer write is larger than BOOT_MAX_ALIGN, which boot_write_trailer refuses."""


def _align_down(value, unit):
    return value - value % unit


def _align_up(value, unit):
    return _align_down(value + unit - 1, unit)


class Layout:
    """Trailer offsets of one slot for a BOOT_MAX_ALIGN and a flash write block size."""

    def __init__(self, slot_size, max_align, write_block):
        if slot_size <= 0 or max_align <= 0 or write_block <= 0:
            raise ValueError('sizes must be positive')
        self.slot_size = slot_size
        self.max_align = max_align
        self.write_block = write_block

    @property
    def magic(self):
        if self.max_align == 8:
            return _MAGIC_ALIGN_8
        return struct.pack('<H', self.max_align) + _MAGIC_TAIL

    @property
    def magic_off(self):
        return self.slot_size - MAGIC_SIZE

    @property
    def magic_write(self):
        """Offset and length of the one write that boot_write_magic makes."""
        size = _align_up(MAGIC_SIZE, self.max_align) if self.max_align > 8 else MAGIC_SIZE
        return _align_down(self.magic_off, self.max_align), size

    @property
    def image_ok_off(self):
        return _align_down(self.magic_off - self.max_align, self.max_align)

    @property
    def copy_done_off(self):
        return self.image_ok_off - self.max_align

    @property
    def swap_info_off(self):
        return self.copy_done_off - self.max_align

    @property
    def trailer_size(self):
        """boot_trailer_info_sz() for RAM load: swap_info, copy_done, image_ok and swap_size are
        one BOOT_MAX_ALIGN each, then the aligned magic. The swap_size field is reserved although
        RAM load never writes it."""
        magic = _align_up(MAGIC_SIZE, self.max_align) if self.max_align > 8 else MAGIC_SIZE
        return 4 * self.max_align + magic

    @property
    def trailer_start(self):
        return self.slot_size - self.trailer_size

    @property
    def flag_write_size(self):
        size = _align_up(1, self.write_block)
        if size > self.max_align:
            raise AlignmentError(f'a flag write of {size} bytes exceeds BOOT_MAX_ALIGN '
                                 f'{self.max_align}')
        return size

    @property
    def allowed_for_swap_modes(self):
        """Swap using move, scratch or offset static-assert 8 <= MCUBOOT_BOOT_MAX_ALIGN <= 32."""
        return 8 <= self.max_align <= 32


class ModelImage:
    """A stand-in image: MCUboot's header fields, a body and a digest in place of the TLVs."""

    HEADER_SIZE = 32
    DIGEST_SIZE = 32
    IMAGE_MAGIC = 0x96f3b83d
    _HEADER = struct.Struct('<IIHHIIBBHII')

    def __init__(self, version, body_size):
        if not 0 < version < 256 or body_size <= 0:
            raise ValueError('version must be 1 to 255 and the body non-empty')
        self.version = version
        self.body_size = body_size

    def encode(self):
        header = self._HEADER.pack(self.IMAGE_MAGIC, 0, self.HEADER_SIZE, 0, self.body_size, 0,
                                   self.version, 0, 0, 0, 0)
        body = bytes((self.version * 31 + i * 7) & 0xFF for i in range(self.body_size))
        return header + body + hashlib.sha256(header + body).digest()

    def fits(self, layout):
        return self.HEADER_SIZE + self.body_size + self.DIGEST_SIZE <= layout.trailer_start


def header_version(layout, medium):
    """The version of a valid header, or None (boot_check_header_valid, simplified)."""
    magic, _, hdr_size, _, body_size, _, major, _, _, _, _ = ModelImage._HEADER.unpack_from(medium)
    if magic != ModelImage.IMAGE_MAGIC or hdr_size != ModelImage.HEADER_SIZE:
        return None
    if hdr_size + body_size + ModelImage.DIGEST_SIZE > layout.trailer_start:
        return None
    return major


def image_valid(layout, medium):
    if header_version(layout, medium) is None:
        return False
    body_size = ModelImage._HEADER.unpack_from(medium)[4]
    end = ModelImage.HEADER_SIZE + body_size
    return hashlib.sha256(medium[:end]).digest() == bytes(medium[end:end + ModelImage.DIGEST_SIZE])


def _flag(value, erased_val):
    if value == erased_val:
        return FLAG_UNSET
    return FLAG_SET if value == 1 else FLAG_BAD


def swap_state(layout, medium, erased_val):
    magic = bytes(medium[layout.magic_off:layout.magic_off + MAGIC_SIZE])
    if magic == bytes([erased_val]) * MAGIC_SIZE:
        magic_state = MAGIC_UNSET
    else:
        magic_state = MAGIC_GOOD if magic == layout.magic else MAGIC_BAD
    swap_info = medium[layout.swap_info_off]
    swap_type = swap_info & 0x0F
    if swap_info == erased_val or swap_type > 4:
        swap_type = 1
    return SwapState(magic_state, swap_type, _flag(medium[layout.copy_done_off], erased_val),
                     _flag(medium[layout.image_ok_off], erased_val))


def _flag_write(layout, offset, value, erased_val):
    size = layout.flag_write_size
    return offset, bytes([value]) + bytes([erased_val]) * (size - 1)


def magic_write(layout, erased_val):
    offset, size = layout.magic_write
    return offset, bytes([erased_val]) * (size - MAGIC_SIZE) + layout.magic


def request_writes(layout, erased_val, permanent):
    """The writes of boot_set_next(fa, active=false, confirm=permanent) on an unset trailer."""
    writes = [magic_write(layout, erased_val)]
    if permanent:
        writes.append(_flag_write(layout, layout.image_ok_off, 1, erased_val))
    swap_type = SWAP_TYPE_PERM if permanent else SWAP_TYPE_TEST
    writes.append(_flag_write(layout, layout.swap_info_off, swap_type, erased_val))
    return writes


def confirm_writes(layout, state, erased_val):
    """The writes of boot_set_next(fa, active=true, ...): image_ok only if magic is good and
    image_ok is unset. A bad image_ok writes nothing and still returns success."""
    if state.magic == MAGIC_GOOD and state.image_ok == FLAG_UNSET:
        return [_flag_write(layout, layout.image_ok_off, 1, erased_val)]
    return []


def copy_done_write(layout, erased_val):
    return _flag_write(layout, layout.copy_done_off, 1, erased_val)


def _scramble(layout, store, slot, erased_val):
    """boot_scramble_region forward over the whole slot, for a device without explicit erase."""
    unit = layout.write_block
    for offset in range(0, layout.slot_size - layout.slot_size % unit, unit):
        store.write(slot, offset, bytes([erased_val]) * unit)


def boot_once(layout, store, erased_val):
    """One boot of MCUboot in RAM load with revert over two slots.

    `store` reads a slot's medium with read(slot) and writes with write(slot, offset, data); an
    optional scramble(slot) replaces the write-block overwrite.
    Returns the Slot that would be started, or None when no slot can be booted. The writes the
    decision makes (copy_done, scrambles) go to the store, so a caller can record them.
    """
    # A store whose device needs explicit erase scrambles by erasing pages (boot_erase_region);
    # otherwise the slot is overwritten with the erased value in write-block units.
    scramble = getattr(store, 'scramble', None) or (
        lambda slot: _scramble(layout, store, slot, erased_val))
    versions = [header_version(layout, store.read(slot)) for slot in (0, 1)]
    while True:
        candidate = None
        for slot in (0, 1):
            if versions[slot] is not None and (candidate is None or
                                               versions[slot] > versions[candidate]):
                candidate = slot
        if candidate is None:
            return None
        state = swap_state(layout, store.read(candidate), erased_val)
        if state.magic != MAGIC_GOOD or (state.copy_done == FLAG_SET and
                                         state.image_ok != FLAG_SET):
            scramble(candidate)
            versions[candidate] = None
            continue
        if state.copy_done != FLAG_SET:
            offset, data = copy_done_write(layout, erased_val)
            store.write(candidate, offset, data)
        if not image_valid(layout, store.read(candidate)):
            scramble(candidate)
            versions[candidate] = None
            continue
        return Slot(candidate, versions[candidate])
