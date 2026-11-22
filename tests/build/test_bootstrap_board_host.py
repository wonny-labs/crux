"""Checks for `scripts/bootstrap.sh board-host`, the Linux-side set-up of the J-Link board route.

The script runs against stub tools (sudo, apt-get, lsusb, udevadm) and a fake
/dev/bus/usb tree in a temporary folder. Nothing is installed and no USB device is
opened. They prove nothing about a real probe, usbipd or WSL2.
"""
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "bootstrap.sh"
RULE = REPO / ".devcontainer" / "jlink" / "99-crux-jlink.rules"
SYSTEM_TOOLS = ("bash", "cat", "chmod", "cmp", "cp", "dirname", "grep", "id", "ls")
JLINK_LINE = "Bus 001 Device 004: ID 1366:1015 SEGGER J-Link\n"


class SetupBoardHostTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="crux-board-host-test-")
        root = Path(self.temporary.name)
        self.bin = root / "bin"
        self.bin.mkdir()
        # Only the stubs and the named system tools are on PATH, so a real lsusb,
        # sudo or udevadm on the test machine is never used.
        for tool in SYSTEM_TOOLS:
            (self.bin / tool).symlink_to(shutil.which(tool))
        self.usb = root / "usb"
        self.rules = root / "rules.d"
        self.rules.mkdir()
        self.log = root / "calls.log"
        self.stub("sudo", f'echo "sudo $*" >> "{self.log}"\nexec "$@"\n')
        self.stub("udevadm", f'echo "udevadm $*" >> "{self.log}"\nexit "${{FAKE_UDEVADM_STATUS:-0}}"\n')
        self.stub("apt-get", f'echo "apt-get $*" >> "{self.log}"\n'
                             f'printf \'#!/bin/sh\\ngrep " ID 1366:" "{root}/lsusb.out"\\n\' > "{self.bin}/lsusb"\n'
                             f'chmod +x "{self.bin}/lsusb"\n')
        self.lsusb_out = root / "lsusb.out"
        self.lsusb_out.write_text(JLINK_LINE)

    def tearDown(self):
        self.temporary.cleanup()

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def lsusb(self):
        # Like lsusb -d 1366:, it lists only J-Link devices.
        self.stub("lsusb", f'grep " ID 1366:" "{self.lsusb_out}"\n')

    def node(self, mode):
        node = self.usb / "001" / "004"
        node.parent.mkdir(parents=True, exist_ok=True)
        node.write_text("")
        node.chmod(mode)
        return node

    def run_script(self, **environment):
        env = {"PATH": str(self.bin), "CRUX_USB_DIR": str(self.usb),
               "CRUX_UDEV_RULES_DIR": str(self.rules), "HOME": self.temporary.name}
        env.update(environment)
        return subprocess.run([str(self.bin / "bash"), str(SCRIPT), "board-host"], env=env,
                              capture_output=True, text=True)

    def calls(self):
        return self.log.read_text() if self.log.exists() else ""

    def test_script_parses(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_installs_usbutils_when_lsusb_is_missing(self):
        self.node(0o666)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("sudo apt-get update", self.calls())
        self.assertIn("sudo apt-get install -y usbutils", self.calls())

    def test_keeps_an_installed_lsusb(self):
        self.lsusb()
        self.node(0o666)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("apt-get", self.calls())

    def test_stops_with_the_usbipd_line_when_usb_tree_is_missing(self):
        self.lsusb()
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usbipd attach --wsl --busid <BUSID>", result.stderr)
        self.assertEqual(list(self.rules.iterdir()), [])

    def test_stops_when_no_jlink_is_listed(self):
        self.lsusb()
        self.node(0o666)
        self.lsusb_out.write_text("Bus 001 Device 002: ID 1d6b:0002 Linux Foundation 2.0 root hub\n")
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("1366", result.stderr)
        self.assertEqual(list(self.rules.iterdir()), [])

    def test_installs_the_udev_rule_once(self):
        self.lsusb()
        self.node(0o666)
        first = self.run_script()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        installed = self.rules / "99-crux-jlink.rules"
        self.assertEqual(installed.read_text(), RULE.read_text())
        self.assertIn("udevadm control --reload-rules", self.calls())
        self.assertIn("udevadm trigger", self.calls())
        self.log.unlink()
        second = self.run_script()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("already installed", second.stdout)
        self.assertNotIn("sudo cp", self.calls())

    def test_world_readable_node_is_accepted_as_on_wsl2(self):
        self.lsusb()
        self.node(0o666)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("rw-rw-rw-", result.stdout)
        self.assertIn("0666", result.stdout)

    def test_plugdev_node_is_accepted_as_on_native_linux(self):
        self.lsusb()
        node = self.node(0o660)
        result = self.run_script(CRUX_PLUGDEV_GID=str(node.stat().st_gid))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("plugdev", result.stdout)
        self.assertIn("0660", result.stdout)

    def test_node_the_container_cannot_open_fails_with_advice(self):
        self.lsusb()
        self.node(0o600)
        result = self.run_script(CRUX_PLUGDEV_GID="99999")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot open", result.stderr)
        self.assertIn("usbipd attach", result.stderr)

    def test_re_enumerated_root_node_without_write_access_fails(self):
        # After a re-enumeration on WSL2 the udev rule may not apply: crw-rw-r-- root.
        self.lsusb()
        self.node(0o664)
        result = self.run_script(CRUX_PLUGDEV_GID="99999")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot open", result.stderr)
        self.assertIn("--auto-attach", result.stderr)

    def test_udevadm_failure_is_a_warning_and_the_node_decides(self):
        self.lsusb()
        self.node(0o666)
        result = self.run_script(FAKE_UDEVADM_STATUS="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("warning", result.stderr)

    def test_refused_inside_the_dev_container(self):
        self.lsusb()
        self.node(0o666)
        result = self.run_script(CRUX_REPO="/workspace/crux-pilot")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not in the Dev Container", result.stderr)
        self.assertEqual(self.calls(), "")

    def test_board_host_never_flashes_or_runs_jlink(self):
        text = SCRIPT.read_text()
        text = text[text.index("# board_host begin"):text.index("# board_host end")]
        for forbidden in ("JLink", "west ", "flash", "nrfjprog", "pyocd"):
            self.assertNotIn(forbidden, text.replace("99-crux-jlink.rules", ""))


if __name__ == "__main__":
    unittest.main()
