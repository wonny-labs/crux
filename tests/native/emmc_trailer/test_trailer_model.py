#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tests of the MCUboot trailer model. They need no build and no MCUboot checkout."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trailer_model import (FLAG_BAD, FLAG_SET, FLAG_UNSET, MAGIC_BAD, MAGIC_GOOD,  # noqa: E402
                           MAGIC_UNSET, AlignmentError, Layout, ModelImage, Slot,
                           boot_once, confirm_writes, request_writes, swap_state)

SLOT = 64 * 1024


def erased(value=0xFF, size=SLOT):
    return bytearray([value]) * size


class LayoutTest(unittest.TestCase):
    def test_offsets_with_the_default_alignment(self):
        layout = Layout(SLOT, max_align=8, write_block=8)
        self.assertEqual(layout.magic_off, SLOT - 16)
        self.assertEqual(layout.magic_write, (SLOT - 16, 16))
        self.assertEqual(layout.image_ok_off, SLOT - 24)
        self.assertEqual(layout.copy_done_off, SLOT - 32)
        self.assertEqual(layout.swap_info_off, SLOT - 40)
        self.assertEqual(layout.flag_write_size, 8)

    def test_offsets_with_a_sector_alignment(self):
        layout = Layout(SLOT, max_align=512, write_block=512)
        self.assertEqual(layout.magic_write, (SLOT - 512, 512))
        self.assertEqual(layout.image_ok_off, SLOT - 1024)
        self.assertEqual(layout.copy_done_off, SLOT - 1536)
        self.assertEqual(layout.swap_info_off, SLOT - 2048)
        self.assertEqual(layout.flag_write_size, 512)

    def test_trailer_size_counts_the_swap_size_field_as_boot_trailer_info_sz_does(self):
        # BOOT_MAX_ALIGN * 4 (swap_info, copy_done, image_ok, swap_size) plus the magic, aligned.
        self.assertEqual(Layout(SLOT, 8, 8).trailer_size, 8 * 4 + 16)
        self.assertEqual(Layout(SLOT, 32, 32).trailer_size, 32 * 4 + 32)
        self.assertEqual(Layout(SLOT, 512, 512).trailer_size, 512 * 4 + 512)
        self.assertEqual(Layout(SLOT, 4096, 4096).trailer_size, 4096 * 4 + 4096)
        layout = Layout(SLOT, 512, 512)
        self.assertEqual(layout.trailer_start, SLOT - 2560)
        self.assertEqual(layout.trailer_start, layout.swap_info_off - 512,
                         'the swap_size field sits just below swap_info')

    def test_magic_bytes_depend_on_the_alignment(self):
        self.assertEqual(Layout(SLOT, 8, 8).magic[:4], bytes([0x77, 0xc2, 0x95, 0xf3]))
        # Above 8 the first two bytes carry the alignment, little-endian.
        self.assertEqual(Layout(SLOT, 512, 512).magic[:4], bytes([0x00, 0x02, 0x2d, 0xe1]))
        self.assertEqual(len(Layout(SLOT, 32, 32).magic), 16)

    def test_a_write_block_above_the_maximum_alignment_cannot_write_a_flag(self):
        with self.assertRaises(AlignmentError):
            Layout(SLOT, max_align=8, write_block=512).flag_write_size

    def test_swap_modes_cap_the_alignment(self):
        self.assertTrue(Layout(SLOT, 32, 32).allowed_for_swap_modes)
        self.assertFalse(Layout(SLOT, 512, 512).allowed_for_swap_modes)
        self.assertFalse(Layout(SLOT, 4, 4).allowed_for_swap_modes)


class SwapStateTest(unittest.TestCase):
    def setUp(self):
        self.layout = Layout(SLOT, 512, 512)

    def test_erased_trailer_is_unset(self):
        state = swap_state(self.layout, erased(), 0xFF)
        self.assertEqual((state.magic, state.copy_done, state.image_ok),
                         (MAGIC_UNSET, FLAG_UNSET, FLAG_UNSET))

    def test_zero_filled_trailer_is_bad_when_the_erased_value_is_0xff(self):
        state = swap_state(self.layout, erased(0x00), 0xFF)
        self.assertEqual((state.magic, state.copy_done, state.image_ok),
                         (MAGIC_BAD, FLAG_BAD, FLAG_BAD))
        # With an erased value of 0x00 the same medium reads as unset.
        state = swap_state(self.layout, erased(0x00), 0x00)
        self.assertEqual((state.magic, state.copy_done, state.image_ok),
                         (MAGIC_UNSET, FLAG_UNSET, FLAG_UNSET))

    def test_written_flags_and_magic_decode(self):
        medium = erased()
        for offset, data in request_writes(self.layout, 0xFF, permanent=False):
            medium[offset:offset + len(data)] = data
        state = swap_state(self.layout, medium, 0xFF)
        self.assertEqual((state.magic, state.image_ok), (MAGIC_GOOD, FLAG_UNSET))
        for offset, data in confirm_writes(self.layout, state, 0xFF):
            medium[offset:offset + len(data)] = data
        self.assertEqual(swap_state(self.layout, medium, 0xFF).image_ok, FLAG_SET)
        medium[self.layout.image_ok_off] = 0x02
        self.assertEqual(swap_state(self.layout, medium, 0xFF).image_ok, FLAG_BAD)

    def test_request_sequence_is_magic_then_flags(self):
        test = request_writes(self.layout, 0xFF, permanent=False)
        self.assertEqual([offset for offset, _ in test],
                         [SLOT - 512, self.layout.swap_info_off])
        permanent = request_writes(self.layout, 0xFF, permanent=True)
        self.assertEqual([offset for offset, _ in permanent],
                         [SLOT - 512, self.layout.image_ok_off, self.layout.swap_info_off])
        self.assertTrue(all(len(data) == 512 for _, data in permanent))

    def test_confirm_writes_nothing_when_image_ok_is_not_unset(self):
        medium = erased(0x00)
        medium[SLOT - 16:] = self.layout.magic
        state = swap_state(self.layout, medium, 0xFF)
        self.assertEqual((state.magic, state.image_ok), (MAGIC_GOOD, FLAG_BAD))
        self.assertEqual(confirm_writes(self.layout, state, 0xFF), [])


class FakeStore:
    """Two slots on one medium, written whole: the rules alone, no device model."""

    def __init__(self, layout, primary, secondary):
        self.layout = layout
        self.media = [bytearray(primary), bytearray(secondary)]
        self.writes = []

    def read(self, slot):
        return bytes(self.media[slot])

    def write(self, slot, offset, data):
        self.writes.append((slot, offset, len(data)))
        self.media[slot][offset:offset + len(data)] = data

    def erase(self, slot, offset, size):
        self.write(slot, offset, bytes([0xFF]) * size)


def programmed(layout, version, confirmed, copy_done=False):
    medium = erased()
    image = ModelImage(version, 3000).encode()
    medium[:len(image)] = image
    if confirmed:
        for offset, data in request_writes(layout, 0xFF, permanent=True):
            medium[offset:offset + len(data)] = data
    else:
        for offset, data in request_writes(layout, 0xFF, permanent=False):
            medium[offset:offset + len(data)] = data
    if copy_done:
        offset = layout.copy_done_off
        medium[offset:offset + layout.flag_write_size] = (
            bytes([1]) + bytes([0xFF]) * (layout.flag_write_size - 1))
    return medium


class BootOnceTest(unittest.TestCase):
    def setUp(self):
        self.layout = Layout(SLOT, 512, 512)

    def boot(self, primary, secondary):
        store = FakeStore(self.layout, primary, secondary)
        return boot_once(self.layout, store, 0xFF), store

    def test_confirmed_image_boots_and_gets_copy_done(self):
        result, store = self.boot(programmed(self.layout, 1, True), erased())
        self.assertEqual(result, Slot(0, 1))
        self.assertEqual(store.writes, [(0, self.layout.copy_done_off, 512)])
        result, store = self.boot(store.read(0), store.read(1))
        self.assertEqual(result, Slot(0, 1))
        self.assertEqual(store.writes, [])

    def test_higher_version_on_test_is_tried_once_then_erased(self):
        old = programmed(self.layout, 1, True, copy_done=True)
        result, store = self.boot(old, programmed(self.layout, 2, False))
        self.assertEqual(result, Slot(1, 2))
        self.assertEqual(store.writes, [(1, self.layout.copy_done_off, 512)])
        result, store = self.boot(store.read(0), store.read(1))
        self.assertEqual(result, Slot(0, 1))
        self.assertEqual(store.writes[0], (1, 0, 512))  # scramble starts at the header
        self.assertEqual(len(store.writes), SLOT // 512)
        self.assertEqual(store.read(1), bytes(erased()))

    def test_confirmed_new_image_stays(self):
        old = programmed(self.layout, 1, True, copy_done=True)
        new = programmed(self.layout, 2, False, copy_done=True)
        new[self.layout.image_ok_off] = 1
        result, store = self.boot(old, new)
        self.assertEqual(result, Slot(1, 2))
        self.assertEqual(store.writes, [])

    def test_image_without_good_magic_is_erased(self):
        unconfirmed = erased()
        image = ModelImage(1, 3000).encode()
        unconfirmed[:len(image)] = image
        result, store = self.boot(unconfirmed, erased())
        self.assertIsNone(result)
        self.assertEqual(store.read(0), bytes(erased()))

    def test_invalid_image_is_erased_and_the_other_slot_boots(self):
        old = programmed(self.layout, 1, True, copy_done=True)
        new = programmed(self.layout, 2, False)
        new[100] ^= 0xFF  # body damaged, header intact
        result, store = self.boot(old, new)
        self.assertEqual(result, Slot(0, 1))
        self.assertEqual(store.read(1), bytes(erased()))

    def test_header_damage_makes_a_slot_unavailable_without_a_write(self):
        old = programmed(self.layout, 1, True, copy_done=True)
        new = programmed(self.layout, 2, False)
        new[0] ^= 0xFF
        result, store = self.boot(old, new)
        self.assertEqual(result, Slot(0, 1))
        self.assertEqual(store.writes, [])

    def test_image_reaching_the_trailer_is_unavailable(self):
        old = programmed(self.layout, 1, True, copy_done=True)
        new = programmed(self.layout, 2, False)
        big = ModelImage(2, self.layout.trailer_start).encode()
        new[:ModelImage.HEADER_SIZE] = big[:ModelImage.HEADER_SIZE]
        result, store = self.boot(old, new)
        self.assertEqual(result, Slot(0, 1))
        self.assertEqual(store.writes, [])
        self.assertTrue(ModelImage(2, 3000).fits(self.layout))
        self.assertFalse(ModelImage(2, self.layout.trailer_start).fits(self.layout))
        edge = self.layout.trailer_start - ModelImage.HEADER_SIZE - ModelImage.DIGEST_SIZE
        self.assertTrue(ModelImage(2, edge).fits(self.layout))
        self.assertFalse(ModelImage(2, edge + 1).fits(self.layout))

if __name__ == '__main__':
    unittest.main()
