#!/usr/bin/env python3
"""Time between two console lines of one boot, from an events.jsonl of received chunks.

Use the file of console_log.py (a logger that is already reading when the board resets). Do NOT use the
events.jsonl of a device-control `reset`: that operation reads the port only after the reset command has
exited, so the lines MCUboot printed meanwhile are read together in one burst with nearly one time. This
module refuses an interval whose start or end line was completed in the first chunk read after a
`tool_done` event (the burst), unless --allow-buffered is given, and then reports the result as buffered.
A line gets the time of the chunk that carried its last byte, so the resolution is that of the reader and
the USB serial bridge, not of the target's clock: a coarse host-side figure that excludes the boot ROM.
Several boots go in as several --events files and are summarised. It reads files only and never touches a
board. Not run on a board.
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
    """[(time, text, burst)] of every complete line received, in order. `burst` is true when the chunk that
    completed the line was the first one read after a tool_done event."""
    result = []
    pending = b''
    after_tool = False
    try:
        records = [json.loads(line) for line in Path(events).read_text(encoding='utf-8').splitlines() if line]
    except (OSError, ValueError) as error:
        raise TimingError(f'cannot read {events}: {error}') from error
    for record in records:
        if record.get('event') == 'tool_done':
            after_tool = True
            continue
        if record.get('event') != 'rx':
            continue
        burst = after_tool
        after_tool = False
        pending += bytes.fromhex(record['hex'])
        while b'\n' in pending:
            raw, pending = pending.split(b'\n', 1)
            result.append((float(record['monotonic']), raw.decode('latin-1').rstrip('\r'), burst))
    return result


def interval(events, start_pattern, end_pattern, allow_buffered=False):
    lines = lines_with_times(events)
    start_regex, end_regex = re.compile(start_pattern), re.compile(end_pattern)
    for index, (start_time, text, start_burst) in enumerate(lines):
        if start_regex.search(text):
            for end_time, end_text, end_burst in lines[index + 1:]:
                if end_regex.search(end_text):
                    buffered = start_burst or end_burst
                    if buffered and not allow_buffered:
                        raise TimingError(
                            f'{events}: a line was read in the first chunk after a tool_done event, so its time is '
                            'the time of the read, not of the print; capture with console_log.py instead')
                    return {'seconds': end_time - start_time, 'start_line': text, 'end_line': end_text,
                            'buffered': buffered}
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
    parser.add_argument('--allow-buffered', action='store_true', help='accept lines read in a burst; the result says so')
    args = parser.parse_args(argv)
    try:
        runs = [interval(path, args.start, args.end, args.allow_buffered) for path in args.events]
        summary = summarise([run['seconds'] for run in runs])
    except TimingError as error:
        print(f'boot_timing: {error}', file=sys.stderr)
        return 2
    print(json.dumps({'runs': runs, 'summary': summary}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
