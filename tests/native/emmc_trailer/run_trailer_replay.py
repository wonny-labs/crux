#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the MCUboot trailer replay matrix and write its record as JSON.

Every result is an observation of the models in trailer_model.py and write_path.py and of the
eMMC simulator's replay model. None of it is evidence about MCUboot on a device or about an eMMC.
Exits non-zero if any required outcome (see REQUIRED) does not hold, so the record cannot claim
more than the run shows.
"""
import argparse
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trailer_model import AlignmentError, Layout  # noqa: E402
from write_path import (DEVICES, KiB, MiB, PROPERTIES, Geometry, LayoutConfig,  # noqa: E402
                        check_layout, encode_trace, replay, run_scenario, staged_unerased_request)

PROPS = tuple(PROPERTIES)
SAFETY = ('P1', 'P2')
# Models whose torn write can reach a trailer field it is not writing, by layout.
COLLATERAL_MODELS = {'sector': {'torn-native'}, 'rmw': {'torn-native', 'torn-sector-wide'},
                     'native': set()}


def trial_cancelled(trace, cases):
    """Cuts while the trial step is in flight after which image 1 boots: the update is lost,
    which is allowed because the trial was not acknowledged. Counted per model."""
    start, mark = trace.starts['trial'], dict(trace.marks)['trial']
    counts = {}
    for case in cases:
        if start <= case.position <= mark and case.boot1 is not None and case.boot1.index == 0:
            counts[case.model] = counts.get(case.model, 0) + 1
    return counts


def summarise(cases):
    by_model = {}
    examples = {}
    for case in cases:
        entry = by_model.setdefault(case.model, {'cases': 0, **{p: 0 for p in PROPS}})
        entry['cases'] += 1
        for prop, ok in case.results.items():
            if not ok:
                entry[prop] += 1
                examples.setdefault(prop, {
                    'position': case.position, 'model': case.model, 'seed': case.seed,
                    'acked': sorted(case.acked), 'boot1': case.boot1 and list(case.boot1),
                    'boot2': case.boot2 and list(case.boot2)})
    return by_model, examples


def failed(by_model, prop, models=None):
    return sum(entry[prop] for model, entry in by_model.items()
               if models is None or model in models)


def trace_stats(trace):
    kinds = [event.kind for event in trace.events]
    return {'events': len(kinds), 'sector_writes': kinds.count('write'),
            'flushes': kinds.count('flush'), 'marks': [name for name, _ in trace.marks],
            'sha256': hashlib.sha256(encode_trace(trace.events)).hexdigest()}


def run_matrix(seeds):
    rows = []
    configs = (LayoutConfig.sector(), LayoutConfig.rmw(), LayoutConfig.native())
    variants = (('flush', True), ('flush', False), ('steps', False), ('trailer', False),
                ('none', False))
    for config in configs:
        for policy, reliable in variants:
            for path, padded in (('confirm', False), ('revert', False),
                                 ('confirm', True), ('revert', True)):
                if padded and reliable:
                    continue
                trace = run_scenario(path, config, policy=policy, reliable=reliable,
                                     padded=padded)
                for device in DEVICES:
                    cases = replay(trace, device, seeds=seeds)
                    by_model, examples = summarise(cases)
                    rows.append({'layout': config.name, 'policy': policy, 'reliable': reliable,
                                 'path': path, 'padded': padded, 'device': device.name,
                                 'trace': trace_stats(trace), 'by_model': by_model,
                                 'examples': examples,
                                 'trial_cancelled_in_flight': trial_cancelled(trace, cases)})
    return rows


def check_required(rows):
    """The outcomes the record states. Each returns a list of failures."""
    problems = []
    for row in rows:
        name = f"{row['layout']}/{row['policy']}/{'rel' if row['reliable'] else 'norel'}/" \
               f"{row['path']}{'+pad' if row['padded'] else ''}/{row['device']}"
        by_model = row['by_model']
        for prop in SAFETY:
            if failed(by_model, prop):
                problems.append(f'{name}: {prop} failed')
        extra = failed(by_model, 'P7', [m for m in by_model
                                        if m not in COLLATERAL_MODELS[row['layout']]])
        # Without a flush, a sector rewrite carries earlier unflushed fields along with it, so a
        # torn rewrite can change them under any torn model. That is not asserted.
        if extra and row['policy'] != 'none':
            problems.append(f'{name}: P7 failed under a model that should not reach it')
        if row['policy'] == 'flush' and not row['reliable'] and row['path'] == 'confirm':
            for model in COLLATERAL_MODELS[row['layout']]:
                if not by_model[model]['P7']:
                    problems.append(f'{name}: P7 did not fail under {model}')
        if row['policy'] in ('flush', 'steps') or (row['policy'] == 'trailer' and
                                                   row['device'] == 'fifo-barrier'):
            for prop in ('P3', 'P4', 'P5', 'P6'):
                if failed(by_model, prop):
                    problems.append(f"{name}: {prop} failed under {row['policy']}")
        elif row['policy'] == 'trailer':
            # A random draw finds it once in 8 on the sector layout, and not on the other.
            if (failed(by_model, 'P4') == 0 and row['path'] == 'revert' and
                    row['layout'] == 'sector' and not row['padded']):
                problems.append(f'{name}: P4 did not fail with trailer-only flushes')
            for prop in ('P3', 'P5', 'P6'):
                if failed(by_model, prop):
                    problems.append(f'{name}: {prop} failed under trailer-only flushes')
        elif row['path'] == 'confirm' and not row['padded']:
            order = 'fifo' if row['device'] == 'fifo-barrier' else 'reordered'
            for model in (order, 'lost'):
                if not by_model[model]['P3']:
                    problems.append(f'{name}: P3 did not fail under {model} without a flush')
    return problems


def controls(seeds):
    out = {}
    trace = run_scenario('confirm', LayoutConfig.sector(), policy='flush', early_marks=True)
    by_model, _ = summarise(replay(trace, DEVICES[0], seeds=seeds))
    out['early_ack'] = {'required': 'P3 fails', 'P3_failures': failed(by_model, 'P3')}

    misaligned = LayoutConfig.sector(slot_a_offset=2048)
    trace = run_scenario('confirm', misaligned, policy='flush')
    by_model, examples = summarise(replay(trace, DEVICES[0], seeds=seeds,
                                          models=('torn-native',)))
    out['misaligned_slots'] = {'required': 'P1 and P2 fail', 'P1_failures': failed(by_model, 'P1'),
                               'P2_failures': failed(by_model, 'P2'),
                               'example': examples.get('P1')}

    trace = run_scenario('revert', LayoutConfig.sector(), policy='none')
    after_trial = dict(trace.marks)['trial'] + 1
    by_model, examples = summarise(replay(trace, DEVICES[1], seeds=range(4096),
                                          models=('reordered',), positions=[after_trial]))
    out['unordered_second_trial'] = {'required': 'P4 fails', 'draws': 4096,
                                     'P4_failures': failed(by_model, 'P4'),
                                     'example': examples.get('P4')}

    rc, booted, state = staged_unerased_request(LayoutConfig.sector())
    out['unerased_request'] = {'required': 'request fails, image 1 boots', 'rc': rc,
                               'booted': list(booted) if booted else None,
                               'magic_state': state.magic}

    layouts = {}
    for write_block, max_align in ((512, 512), (512, 32), (8, 8), (32, 32)):
        layout = Layout(64 * KiB, max_align, write_block)
        try:
            flag = layout.flag_write_size
        except AlignmentError:
            flag = None
        layouts[f'wb{write_block}/align{max_align}'] = {
            'flag_write': flag, 'swap_modes_allowed': layout.allowed_for_swap_modes,
            'trailer_size': layout.trailer_size}
    out['layouts'] = layouts

    geometries = [Geometry(e, w) for e in (512 * KiB, 4 * MiB) for w in (4 * MiB, 8 * MiB)]
    plans = {'8MiB': [(16 * MiB, 8 * MiB), (24 * MiB, 8 * MiB)],
             '4MiB': [(16 * MiB, 4 * MiB), (20 * MiB, 4 * MiB)],
             '512KiB': [(16 * MiB, 512 * KiB), (16 * MiB + 512 * KiB, 512 * KiB)]}
    out['alignment'] = {plan: {f'erase{g.erase_group // KiB}K/wp{g.wp_group // MiB}M':
                               len(check_layout(slots, g, fs_volume=(32 * MiB, 64 * MiB)))
                               for g in geometries}
                        for plan, slots in plans.items()}
    return out


def check_controls(out):
    problems = []
    if not out['early_ack']['P3_failures']:
        problems.append('early acknowledgement control did not fail')
    if not out['misaligned_slots']['P1_failures'] or not out['misaligned_slots']['P2_failures']:
        problems.append('misaligned slot control did not fail')
    if not out['unordered_second_trial']['P4_failures']:
        problems.append('unordered second-trial control did not fail')
    if out['unerased_request']['rc'] == 0 or out['unerased_request']['booted'] != [0, 1]:
        problems.append('unerased request control did not come out as required')
    if any(out['alignment']['8MiB'].values()):
        problems.append('8 MiB slots did not satisfy every geometry')
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--seeds', type=int, default=8, help='draws per random model and cut')
    parser.add_argument('--out', help='JSON file to write')
    args = parser.parse_args(argv)
    seeds = range(args.seeds)
    started = time.monotonic()
    rows = run_matrix(seeds)
    ctl = controls(seeds)
    problems = check_required(rows) + check_controls(ctl)
    record = {'seeds': args.seeds, 'properties': PROPERTIES, 'rows': rows, 'controls': ctl,
              'cases': sum(e['cases'] for r in rows for e in r['by_model'].values()),
              'problems': problems, 'seconds': round(time.monotonic() - started, 1)}
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
            handle.write('\n')
    for row in rows:
        counts = {p: failed(row['by_model'], p) for p in PROPS}
        cases = sum(e['cases'] for e in row['by_model'].values())
        print(f"{row['layout']:6} {row['policy']:5} {'rel' if row['reliable'] else 'norel':5} "
              f"{row['path']:7} {row['device']:12} cases={cases:6} " +
              ' '.join(f'{p}={n}' for p, n in counts.items()) +
              f" cancelled={row['trial_cancelled_in_flight']}")
    print(json.dumps(ctl, sort_keys=True))
    print(f"{record['cases']} cases in {record['seconds']} s; "
          f"{'all required outcomes hold' if not problems else 'PROBLEMS: ' + '; '.join(problems)}")
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
