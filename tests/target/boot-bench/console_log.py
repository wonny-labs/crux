#!/usr/bin/env python3
"""Timestamped raw console logger for the boot-time measurement (route B of the procedure).

Start it BEFORE the reset, so every byte is read as it arrives: it opens the port exclusively with DTR and
RTS low (set before the open; a USB bridge can still move them, so check on a new board), then writes one
JSON line per received chunk with a monotonic time, in the format of a device-control events.jsonl, so that
boot_timing.py reads it. It stops when --until matches the received bytes or after --timeout seconds; the
exit status is 0 on a match and 1 on a timeout (a recorded result, not a fault). It sends nothing and never
touches a probe. Needs pyserial. Not run on a board.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import time


class LogError(Exception):
    pass


def _open_serial(port, baud):
    try:
        import serial  # pyserial, as tools/device_control uses it
    except ImportError as error:
        raise LogError('pyserial is required: python3 -m pip install -r tools/device_control/requirements.txt') from error
    connection = serial.Serial()
    connection.port = port
    connection.baudrate = baud
    connection.timeout = 0.002
    connection.exclusive = True
    connection.dtr = False
    connection.rts = False
    connection.open()
    return connection


def log(port, out, until=None, timeout=15.0, baud=115200, serial_factory=None, clock=time.monotonic):
    out = Path(out)
    if out.exists():
        raise LogError(f'{out} exists; use a new file for every boot')
    out.parent.mkdir(parents=True, exist_ok=True)
    connection = (serial_factory or _open_serial)(port, baud)
    pattern = re.compile(until.encode()) if until else None
    received = b''
    matched = False
    try:
        with out.open('w', encoding='utf-8') as events:
            deadline = clock() + timeout
            events.write(json.dumps({'monotonic': clock(), 'event': 'log_start', 'port': port}) + '\n')
            while clock() < deadline:
                data = connection.read(getattr(connection, 'in_waiting', 0) or 1)
                if not data:
                    continue
                events.write(json.dumps({'monotonic': clock(), 'event': 'rx', 'hex': data.hex()}) + '\n')
                events.flush()
                received += data
                if pattern and pattern.search(received):
                    matched = True
                    break
            events.write(json.dumps({'monotonic': clock(), 'event': 'log_end', 'matched': matched}) + '\n')
    finally:
        connection.close()
    return matched


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--port', required=True)
    parser.add_argument('--out', required=True, type=Path, help='a new events.jsonl file')
    parser.add_argument('--until', help='regular expression that ends the capture')
    parser.add_argument('--timeout', type=float, default=15.0)
    parser.add_argument('--baud', type=int, default=115200)
    args = parser.parse_args(argv)
    try:
        matched = log(args.port, args.out, args.until, args.timeout, args.baud)
    except LogError as error:
        print(f'console_log: {error}', file=sys.stderr)
        return 2
    return 0 if matched else 1


if __name__ == '__main__':
    sys.exit(main())
