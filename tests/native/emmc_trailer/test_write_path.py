#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tests of the flash-over-disk write path model, the device models and the trailer replay."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'emmc_powercut'))

from replay_model import SECTOR, parse_trace  # noqa: E402
from trailer_model import Layout, swap_state, MAGIC_BAD  # noqa: E402
from write_path import (DEVICES, MiB, KiB, Geometry, LayoutConfig, Recorder,  # noqa: E402
                        check_layout, encode_trace, rebuild, replay, run_scenario,
                        staged_unerased_request)

FAST_SEEDS = (0, 1)


def blank(sectors=64, value=0x00):
    return bytes([value]) * (sectors * SECTOR)


class RecorderTest(unittest.TestCase):
    def test_sector_write_is_one_event_and_a_flush_under_the_flush_policy(self):
        rec = Recorder(blank(), policy='flush', write_block=512, page_size=4096)
        rec.write(1024, bytes([0xAB]) * 1024)
        self.assertEqual([(e.kind, e.sector) for e in rec.events],
                         [('cache_on', None), ('write', 2), ('write', 3), ('flush', None)])
        self.assertEqual(rec.visible[1024:2048], bytes([0xAB]) * 1024)

    def test_no_flush_under_the_none_policy(self):
        rec = Recorder(blank(), policy='none', write_block=512, page_size=4096)
        rec.write(0, bytes(512))
        self.assertNotIn('flush', [e.kind for e in rec.events])

    def test_trailer_policy_flushes_only_after_calls_that_touch_a_trailer(self):
        rec = Recorder(blank(), policy='trailer', write_block=512, page_size=4096,
                       trailer_ranges=[(6144, 8192)])
        rec.write(0, bytes(512))
        rec.erase(0, 4096)
        self.assertNotIn('flush', [e.kind for e in rec.events])
        rec.write(5632, bytes(512))     # ends at 6144, outside
        self.assertNotIn('flush', [e.kind for e in rec.events])
        rec.write(6144, bytes(512))     # inside
        self.assertEqual(rec.events[-1].kind, 'flush')
        rec.write(7680, bytes(512))
        self.assertEqual([e.kind for e in rec.events].count('flush'), 2)
        rec.erase(4096, 4096)           # pages overlapping the range
        self.assertEqual(rec.events[-1].kind, 'flush')

    def test_small_write_block_rewrites_the_whole_sector(self):
        rec = Recorder(blank(value=0x5A), policy='none', write_block=8, page_size=4096)
        rec.write(520, bytes([1]) * 8)
        writes = [e for e in rec.events if e.kind == 'write']
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0].sector, 1)
        expected = bytearray([0x5A]) * SECTOR
        expected[8:16] = bytes([1]) * 8
        self.assertEqual(writes[0].data, bytes(expected))

    def test_misaligned_access_is_rejected_without_an_event(self):
        rec = Recorder(blank(), policy='flush', write_block=512, page_size=4096)
        for offset, size in ((100, 512), (0, 100), (63 * SECTOR, 1024), (-512, 512)):
            with self.assertRaises(ValueError, msg=(offset, size)):
                rec.write(offset, bytes(size))
        for offset, size in ((512, 4096), (0, 512), (60 * SECTOR, 8192)):
            with self.assertRaises(ValueError, msg=(offset, size)):
                rec.erase(offset, size)
        self.assertEqual([e.kind for e in rec.events], ['cache_on'])

    def test_erase_writes_the_erase_value_over_whole_pages(self):
        rec = Recorder(blank(), policy='flush', write_block=512, page_size=4096)
        rec.erase(4096, 8192)
        self.assertEqual(rec.visible[4096:12288], bytes([0xFF]) * 8192)
        self.assertEqual(rec.visible[:4096], bytes(4096))
        writes = [e.sector for e in rec.events if e.kind == 'write']
        self.assertEqual(writes, list(range(8, 24)))

    def test_trace_encoding_round_trips_through_the_replay_parser(self):
        rec = Recorder(blank(), policy='flush', write_block=512, page_size=4096)
        rec.write(0, bytes([7]) * 1024)
        rec.mark('done')
        events = parse_trace(encode_trace(rec.events))
        self.assertEqual(events, rec.events)


class RebuildTest(unittest.TestCase):
    def setUp(self):
        self.rec = Recorder(blank(value=0x11), policy='none', write_block=512, page_size=4096)
        self.rec.write(9 * SECTOR, bytes([0x99]) * SECTOR)  # sector 9, native unit 1 (8 to 15)
        self.base = blank(value=0x11)

    def test_torn_native_damages_only_its_native_unit(self):
        position = 1  # the write to sector 9 is next
        for seed in range(8):
            image = rebuild(self.base, self.rec.events, position, 'torn-native', seed)
            changed = {i // SECTOR for i in range(len(image)) if image[i] != self.base[i]}
            self.assertTrue(changed <= set(range(8, 16)), changed)
            self.assertTrue(changed, f'seed {seed} changed nothing')

    def test_torn_sector_damages_only_the_sector(self):
        for seed in range(8):
            image = rebuild(self.base, self.rec.events, 1, 'torn-sector', seed)
            changed = {i // SECTOR for i in range(len(image)) if image[i] != self.base[i]}
            self.assertEqual(changed, {9})

    def test_lost_and_ordered_models(self):
        end = len(self.rec.events)
        self.assertEqual(rebuild(self.base, self.rec.events, end, 'lost', 0), self.base)
        self.assertEqual(rebuild(self.base, self.rec.events, end, 'prefix', 0)[9 * SECTOR],
                         0x99)


def violations(cases, prop):
    return [case for case in cases if not case.results[prop]]


class ScenarioTest(unittest.TestCase):
    def test_marks_follow_the_update_steps(self):
        for path, last in (('confirm', 'confirmed'), ('revert', 'reverted')):
            trace = run_scenario(path, LayoutConfig.sector(), policy='flush')
            self.assertEqual([name for name, _ in trace.marks],
                             ['erased', 'image', 'requested', 'trial', last])

    def test_flush_at_every_call_holds_every_property_on_both_devices(self):
        for config in (LayoutConfig.sector(), LayoutConfig.rmw()):
            for path in ('confirm', 'revert'):
                trace = run_scenario(path, config, policy='flush')
                for device in DEVICES:
                    cases = replay(trace, device, seeds=FAST_SEEDS)
                    self.assertGreater(len(cases), 100)
                    for prop in ('P1', 'P2', 'P3', 'P4', 'P5', 'P6'):
                        bad = violations(cases, prop)
                        self.assertEqual(bad, [], f'{config.name} {path} {device.name} {prop} '
                                         f'{bad[:1]}')

    def test_flush_and_reliable_write_hold_every_property(self):
        for config in (LayoutConfig.sector(), LayoutConfig.rmw()):
            for path in ('confirm', 'revert'):
                trace = run_scenario(path, config, policy='flush', reliable=True)
                for device in DEVICES:
                    cases = replay(trace, device, seeds=FAST_SEEDS)
                    for prop in ('P1', 'P2', 'P3', 'P4', 'P5', 'P6'):
                        self.assertEqual(violations(cases, prop), [],
                                         f'{config.name} {path} {device.name} {prop}')

    def test_no_flush_loses_acknowledged_steps_but_keeps_a_bootable_image(self):
        for device in DEVICES:
            # A random subset rarely keeps magic and drops copy_done, so draw more of them.
            seeds = FAST_SEEDS if device.order == 'fifo' else range(48)
            confirm = replay(run_scenario('confirm', LayoutConfig.sector(), policy='none'),
                             device, seeds=seeds)
            revert = replay(run_scenario('revert', LayoutConfig.sector(), policy='none'),
                            device, seeds=seeds)
            for cases in (confirm, revert):
                self.assertEqual(violations(cases, 'P1'), [], device.name)
                self.assertEqual(violations(cases, 'P2'), [], device.name)
            self.assertTrue(violations(confirm, 'P3'), device.name)
            if device.order == 'fifo':
                # A drain that stops before copy_done loses the trial and the revert.
                self.assertTrue(violations(revert, 'P4'), device.name)
                self.assertTrue(violations(revert, 'P6'), device.name)
            self.assertTrue(violations(confirm, 'P5'), device.name)
        trace = run_scenario('revert', LayoutConfig.sector(), policy='none')
        # A second trial needs the image and magic kept and copy_done dropped, about one draw
        # in 512, so it is searched for right after the trial is acknowledged.
        after_trial = dict(trace.marks)['trial'] + 1
        second_trial = replay(trace, DEVICES[1], seeds=range(2048), models=('reordered',),
                              positions=[after_trial])
        self.assertTrue(violations(second_trial, 'P4'))

    def test_flush_after_erases_and_trailer_calls_is_enough(self):
        for config in (LayoutConfig.sector(), LayoutConfig.rmw()):
            for path in ('confirm', 'revert'):
                trace = run_scenario(path, config, policy='steps')
                flushes = sum(1 for e in trace.events if e.kind == 'flush')
                full = sum(1 for e in run_scenario(path, config, policy='flush').events
                           if e.kind == 'flush')
                self.assertLess(flushes, full)
                for device in DEVICES:
                    seeds = FAST_SEEDS if device.order == 'fifo' else range(8)
                    cases = replay(trace, device, seeds=seeds)
                    for prop in ('P1', 'P2', 'P3', 'P4', 'P5', 'P6'):
                        self.assertEqual(violations(cases, prop), [],
                                         f'{config.name} {path} {device.name} {prop}')

    def test_flush_after_trailer_calls_only_is_enough_with_a_barrier_but_not_without(self):
        trace = run_scenario('revert', LayoutConfig.sector(), policy='trailer')
        fifo = replay(trace, DEVICES[0], seeds=FAST_SEEDS)
        for prop in ('P1', 'P2', 'P3', 'P4', 'P5', 'P6'):
            self.assertEqual(violations(fifo, prop), [], prop)
        # Without an order guarantee the scramble's last erases can persist while its first,
        # the header's, is dropped: the slot keeps a valid header with copy_done erased, and
        # the unconfirmed image is tried a second time.
        unordered = replay(trace, DEVICES[1], seeds=range(8))
        self.assertTrue(violations(unordered, 'P4'))
        for prop in ('P1', 'P2', 'P3', 'P6'):
            self.assertEqual(violations(unordered, prop), [], prop)

    def test_collateral_damage_depends_on_what_the_alignment_isolates(self):
        def p7(config, device, model, reliable=False):
            trace = run_scenario('confirm', config, policy='flush', reliable=reliable)
            cases = replay(trace, device, seeds=range(4), models=(model,))
            return len(cases), len(violations(cases, 'P7'))

        for device in DEVICES:
            n, bad = p7(LayoutConfig.sector(), device, 'torn-sector')
            self.assertGreater(n, 0)
            self.assertEqual(bad, 0, 'one field per sector: a torn sector hurts only itself')
            self.assertGreater(p7(LayoutConfig.sector(), device, 'torn-native')[1], 0)
            # The replay model's torn sector mixes old and new bytes, so it cannot damage bytes
            # that the write leaves unchanged. A sector that is wholly indeterminate can.
            self.assertEqual(p7(LayoutConfig.rmw(), device, 'torn-sector')[1], 0)
            self.assertGreater(p7(LayoutConfig.rmw(), device, 'torn-sector-wide')[1], 0)
            self.assertEqual(p7(LayoutConfig.sector(), device, 'torn-sector-wide')[1], 0)
            self.assertGreater(p7(LayoutConfig.rmw(), device, 'torn-native')[1], 0)
            self.assertEqual(p7(LayoutConfig.native(), device, 'torn-native')[1], 0)
            self.assertEqual(p7(LayoutConfig.native(), device, 'torn-sector')[1], 0)
            self.assertEqual(p7(LayoutConfig.native(), device, 'torn-sector-wide')[1], 0)
            # Models without a torn write never report collateral damage.
            self.assertEqual(p7(LayoutConfig.sector(), device, 'lost')[1], 0)

    def test_native_unit_alignment_holds_every_property(self):
        for path in ('confirm', 'revert'):
            trace = run_scenario(path, LayoutConfig.native(), policy='flush')
            for device in DEVICES:
                cases = replay(trace, device, seeds=FAST_SEEDS)
                for prop in ('P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7'):
                    self.assertEqual(violations(cases, prop), [], f'{path} {device.name} {prop}')

    def test_padded_image_is_the_test_request(self):
        config = LayoutConfig.sector()
        layout = config.layout
        trace = run_scenario('confirm', config, policy='flush', padded=True)
        self.assertEqual([name for name, _ in trace.marks],
                         ['erased', 'image', 'requested', 'trial', 'confirmed'])
        marks = dict(trace.marks)
        self.assertEqual(marks['requested'], marks['image'] + 1, 'no write separates the two')
        # No call writes swap_info before the trial: the padded image carries the magic only.
        swap_info = config.offsets[1] + layout.swap_info_off
        before_trial = [c for c in trace.calls if c[0] < trace.starts['trial']]
        self.assertFalse([c for c in before_trial if c[2] == swap_info and c[3] <= 512 and
                          c[0] > trace.starts['image']])
        # The last write of the image call is the one that holds the magic, in ascending order.
        image_calls = [c for c in trace.calls
                       if trace.starts['image'] <= c[0] < trace.starts['requested']]
        self.assertEqual([c[2] for c in image_calls], sorted(c[2] for c in image_calls))
        self.assertEqual(image_calls[-1][2] + image_calls[-1][3],
                         config.offsets[1] + config.slot_size)

    def test_padded_flow_holds_every_property_with_flushes_and_loses_acks_without(self):
        for path in ('confirm', 'revert'):
            trace = run_scenario(path, LayoutConfig.sector(), policy='flush', padded=True)
            for device in DEVICES:
                cases = replay(trace, device, seeds=FAST_SEEDS)
                for prop in ('P1', 'P2', 'P3', 'P4', 'P5', 'P6'):
                    self.assertEqual(violations(cases, prop), [], f'{path} {device.name} {prop}')
        trace = run_scenario('confirm', LayoutConfig.sector(), policy='none', padded=True)
        for device in DEVICES:
            seeds = FAST_SEEDS if device.order == 'fifo' else range(16)
            cases = replay(trace, device, seeds=seeds)
            self.assertEqual(violations(cases, 'P1'), [], device.name)
            self.assertEqual(violations(cases, 'P2'), [], device.name)
            self.assertTrue(violations(cases, 'P5') or violations(cases, 'P3'), device.name)

    def test_early_acknowledgement_control_fails(self):
        trace = run_scenario('confirm', LayoutConfig.sector(), policy='flush', early_marks=True)
        cases = replay(trace, DEVICES[0], seeds=FAST_SEEDS)
        self.assertTrue(violations(cases, 'P3'))

    def test_slot_boundary_inside_a_native_unit_can_brick(self):
        misaligned = LayoutConfig.sector(slot_a_offset=2048)
        cases = replay(run_scenario('confirm', misaligned, policy='flush'), DEVICES[0],
                       seeds=range(4), models=('torn-native',))
        self.assertTrue(violations(cases, 'P2'))
        self.assertTrue(violations(cases, 'P1'))
        aligned = replay(run_scenario('confirm', LayoutConfig.sector(), policy='flush'),
                         DEVICES[0], seeds=range(4), models=('torn-native',))
        self.assertEqual(violations(aligned, 'P1') + violations(aligned, 'P2'), [])

    def test_reliable_write_removes_torn_cases(self):
        trace = run_scenario('confirm', LayoutConfig.sector(), policy='flush', reliable=True)
        models = {case.model for case in replay(trace, DEVICES[1], seeds=FAST_SEEDS)}
        self.assertNotIn('torn-native', models)
        self.assertNotIn('torn-sector', models)


class StagedTest(unittest.TestCase):
    def test_request_on_a_natively_erased_slot_without_driver_erase_fails(self):
        rc, booted, state = staged_unerased_request(LayoutConfig.sector())
        self.assertNotEqual(rc, 0)
        self.assertEqual(state.magic, MAGIC_BAD)
        self.assertEqual(booted.index, 0)


class LayoutCheckTest(unittest.TestCase):
    def geometries(self):
        return [Geometry(erase_group=e, wp_group=w) for e in (512 * KiB, 4 * MiB)
                for w in (4 * MiB, 8 * MiB)]

    def test_eight_mib_alignment_satisfies_every_geometry(self):
        for geometry in self.geometries():
            self.assertEqual(check_layout([(16 * MiB, 8 * MiB), (24 * MiB, 8 * MiB)],
                                          geometry, fs_volume=(32 * MiB, 64 * MiB)), [])

    def test_smaller_alignment_fails_the_larger_groups(self):
        geometry = Geometry(erase_group=4 * MiB, wp_group=8 * MiB)
        problems = check_layout([(4 * MiB, 4 * MiB), (8 * MiB, 4 * MiB)], geometry)
        self.assertTrue(any('write-protect' in p for p in problems))
        self.assertFalse(any('erase group' in p for p in problems))
        problems = check_layout([(512 * KiB, 512 * KiB)], geometry)
        self.assertTrue(any('erase group' in p for p in problems))
        problems = check_layout([(2048, 64 * KiB)], geometry)
        self.assertTrue(any('native sector' in p for p in problems))

    def test_overlap_with_the_file_system_volume_is_reported(self):
        geometry = Geometry(erase_group=512 * KiB, wp_group=4 * MiB)
        problems = check_layout([(8 * MiB, 8 * MiB)], geometry, fs_volume=(12 * MiB, 4 * MiB))
        self.assertTrue(any('file-system volume' in p for p in problems))
        problems = check_layout([(8 * MiB, 8 * MiB), (12 * MiB, 8 * MiB)], geometry)
        self.assertTrue(any('overlap' in p for p in problems))


class RunnerTest(unittest.TestCase):
    def test_required_outcomes_of_the_record_hold(self):
        import contextlib
        import io
        import json
        import tempfile
        import run_trailer_replay
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            out = os.path.join(tmp, 'record.json')
            self.assertEqual(run_trailer_replay.main(['--seeds', '8', '--out', out]), 0)
            with open(out, encoding='utf-8') as handle:
                record = json.load(handle)
        self.assertEqual(record['problems'], [])
        self.assertEqual(len(record['rows']), 108)


if __name__ == '__main__':
    unittest.main()
