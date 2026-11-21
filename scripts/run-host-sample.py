#!/usr/bin/env python3
"""Run a Linux Host sample once and check its output, for CTest (label `sample`).

The sample gets the text of --input on stdin, then end of file. With --echo-peer, a local
TCP (42420) and UDP (42421) echo peer on 127.0.0.1 runs for the sample's lifetime, which is
what samples/networking/host expects by default. The run passes when the sample exits with
status 0 within --timeout seconds and every --expect regular expression (multiline) matches
its combined stdout and stderr.
"""
import argparse
import re
import socket
import subprocess
import sys
import threading

ECHO_ADDRESS = "127.0.0.1"
TCP_PORT = 42420
UDP_PORT = 42421


def serve_tcp(listener, stop):
    listener.settimeout(0.2)
    while not stop.is_set():
        try:
            connection, _ = listener.accept()
        except socket.timeout:
            continue
        with connection:
            connection.settimeout(2)
            try:
                while True:
                    data = connection.recv(4096)
                    if not data:
                        break
                    connection.sendall(data)
            except OSError:
                pass


def serve_udp(endpoint, stop):
    endpoint.settimeout(0.2)
    while not stop.is_set():
        try:
            data, peer = endpoint.recvfrom(4096)
            endpoint.sendto(data, peer)
        except socket.timeout:
            continue
        except OSError:
            if stop.is_set():
                break


def start_echo_peer(stop):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((ECHO_ADDRESS, TCP_PORT))
    listener.listen(4)
    endpoint = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    endpoint.bind((ECHO_ADDRESS, UDP_PORT))
    threads = [threading.Thread(target=serve_tcp, args=(listener, stop), daemon=True),
               threading.Thread(target=serve_udp, args=(endpoint, stop), daemon=True)]
    for thread in threads:
        thread.start()
    return [listener, endpoint], threads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary")
    parser.add_argument("sample_args", nargs="*")
    parser.add_argument("--input", default="", help="text sent to the sample's stdin")
    parser.add_argument("--expect", action="append", default=[],
                        help="regular expression that the output must match (repeatable)")
    parser.add_argument("--echo-peer", action="store_true",
                        help="serve TCP and UDP echo on 127.0.0.1:42420/42421 during the run")
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()

    stop = threading.Event()
    sockets, threads = start_echo_peer(stop) if args.echo_peer else ([], [])
    try:
        result = subprocess.run([args.binary, *args.sample_args], input=args.input.encode(),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=args.timeout, check=False)
    except subprocess.TimeoutExpired as expired:
        sys.stdout.write((expired.stdout or b"").decode("utf-8", errors="replace"))
        print(f"SAMPLE_CHECK_FAILED no exit within {args.timeout} s", file=sys.stderr)
        return 1
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=1)
        for endpoint in sockets:
            endpoint.close()

    output = result.stdout.decode("utf-8", errors="replace")
    sys.stdout.write(output)
    failures = []
    if result.returncode != 0:
        failures.append(f"exit status {result.returncode}, expected 0")
    for pattern in args.expect:
        if re.search(pattern, output, re.MULTILINE) is None:
            failures.append(f"no output line matches {pattern!r}")
    for failure in failures:
        print(f"SAMPLE_CHECK_FAILED {failure}", file=sys.stderr)
    if failures:
        return 1
    print("SAMPLE_CHECK_PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
