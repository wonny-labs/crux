"""Check scripts/run-host-sample.py, the CTest driver of the Linux Host samples (label `sample`).

Each case runs the driver on a small stand-in program instead of a built sample, so it needs
no CMake build: the driver must pass stdin, require exit status 0 and every expected line, and
serve the TCP and UDP echo peer that samples/networking/echo_client/host talks to.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

REPO = Path(__file__).resolve().parents[2]
DRIVER = REPO / "scripts/run-host-sample.py"


class RunHostSample(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def program(self, body):
        path = Path(self.directory.name) / "sample"
        path.write_text("#!" + sys.executable + "\n" + textwrap.dedent(body))
        path.chmod(0o755)
        return str(path)

    def run_driver(self, *arguments):
        return subprocess.run([sys.executable, str(DRIVER), *arguments], capture_output=True,
                              text=True, timeout=30, check=False)

    def test_passes_stdin_and_accepts_matching_output(self):
        sample = self.program("""
            import sys
            print("READY")
            for line in sys.stdin:
                print("echo " + line.strip())
            """)
        result = self.run_driver(sample, "--input=one\ntwo\n", "--expect=^READY$",
                                 "--expect=^echo two$")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SAMPLE_CHECK_PASSED", result.stdout)

    def test_fails_when_an_expected_line_is_missing(self):
        sample = self.program('print("READY")\n')
        result = self.run_driver(sample, "--expect=^READY$", "--expect=^DONE$")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no output line matches '^DONE$'", result.stderr)

    def test_expectations_match_whole_lines_only_when_anchored(self):
        sample = self.program('print("NETWORK tcp=-111 udp=0")\n')
        result = self.run_driver(sample, "--expect=^NETWORK tcp=0 udp=0$")
        self.assertEqual(result.returncode, 1)

    def test_fails_on_a_nonzero_exit_status_even_if_the_output_matches(self):
        sample = self.program('import sys\nprint("READY")\nsys.exit(3)\n')
        result = self.run_driver(sample, "--expect=^READY$")
        self.assertEqual(result.returncode, 1)
        self.assertIn("exit status 3", result.stderr)

    def test_passes_arguments_after_the_binary_to_the_sample(self):
        sample = self.program('import sys\nprint("ARGS " + " ".join(sys.argv[1:]))\n')
        result = self.run_driver(sample, "127.0.0.1", "--expect=^ARGS 127.0.0.1$")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_echo_peer_answers_tcp_and_udp_on_the_sample_ports(self):
        sample = self.program("""
            import socket
            message = b"crux-portable-networking-echo".ljust(32, b"\\0")
            with socket.create_connection(("127.0.0.1", 42420), timeout=2) as tcp:
                tcp.sendall(message)
                received = b""
                while len(received) < len(message):
                    received += tcp.recv(64)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
                udp.settimeout(2)
                udp.sendto(message, ("127.0.0.1", 42421))
                datagram, _ = udp.recvfrom(64)
            print("tcp=%d udp=%d" % (received == message, datagram == message))
            """)
        result = self.run_driver(sample, "--echo-peer", "--expect=^tcp=1 udp=1$")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_sample_that_hangs_is_stopped_at_the_timeout(self):
        sample = self.program("import time\ntime.sleep(30)\n")
        result = self.run_driver(sample, "--timeout=1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("SAMPLE_CHECK_FAILED no exit within 1.0 s", result.stderr)


if __name__ == "__main__":
    os.chdir(REPO)
    unittest.main()
