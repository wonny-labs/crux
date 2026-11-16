#!/usr/bin/env python3
"""Time between two console lines of one boot, from the events.jsonl of a device-control run.

device_control keeps every received chunk with a monotonic time. A line gets the time of the chunk that
carried its last byte, so the resolution is that of the USB serial bridge's chunking, not of the target's
clock; the result is a coarse host-side figure. It excludes the boot ROM and everything before the first
byte. Several boots go in as several --events files and are summarised. It reads files only and never
touches a board. Not run on a board.
"""
import argparse
import json
from pathlib import Path
import re
import statistics
import sys


class TimingError(Exception):
    pass


def lines_with_times(events):
    """[(time, text)] of every complete line received, in order."""
    result = []
    pending = b''
    try:
        records = [json.loads(line) for line in Path(events).read_text(encoding='utf-8').splitlines() if line]
    except (OSError, ValueError) as error:
        raise TimingError(f'cannot read {events}: {error}') from error
    for record in records:
        if record.get('event') != 'rx':
            continue
        pending += bytes.fromhex(record['hex'])
        while b'\n' in pending:
            raw, pending = pending.split(b'\n', 1)
            result.append((float(record['monotonic']), raw.decode('latin-1').rstrip('\r')))
    return result


def interval(events, start_pattern, end_pattern):
    lines = lines_with_times(events)
    start_regex, end_regex = re.compile(start_pattern), re.compile(end_pattern)
    for index, (start_time, text) in enumerate(lines):
        if start_regex.search(text):
            for end_time, end_text in lines[index + 1:]:
                if end_regex.search(end_text):
                    return {'seconds': end_time - start_time, 'start_line': text, 'end_line': end_text}
            raise TimingError(f'no line matching {end_pattern!r} after the start line in {events}')
    raise TimingError(f'no line matching {start_pattern!r} in {events}')


def summarise(values):
    if not values:
        raise TimingError('no values to summarise')
    return {'count': len(values), 'min': min(values), 'median': statistics.median(values), 'max': max(values)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--events', required=True, nargs='+', type=Path)
    parser.add_argument('--start', required=True, help='regular expression of the first line')
    parser.add_argument('--end', required=True, help='regular expression of the second line')
    args = parser.parse_args(argv)
    try:
        runs = [interval(path, args.start, args.end) for path in args.events]
        summary = summarise([run['seconds'] for run in runs])
    except TimingError as error:
        print(f'boot_timing: {error}', file=sys.stderr)
        return 2
    print(json.dumps({'runs': runs, 'summary': summary}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
