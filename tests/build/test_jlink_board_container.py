"""Checks for the optional J-Link board Dev Container (ADR-0007).

They prove that the files parse and keep their safety properties: no privileged
container, USB access limited to USB character devices, no download of the SEGGER
package, and a default container that installs nothing. They prove nothing about a
real probe, usbipd or a board.
"""
import json
import os
import re
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
DEVCONTAINER = REPO / ".devcontainer"
BOARD = DEVCONTAINER / "jlink"
INSTALL = BOARD / "install-jlink.sh"
BASE_IMAGE = ("mcr.microsoft.com/devcontainers/base:ubuntu-24.04"
              "@sha256:d94c97dd9cacf183d0a6fd12a8e87b526e9e928307674ae9c94139139c0c6eae")


def load(path):
    return json.loads(path.read_text())


class BoardContainerConfigTest(unittest.TestCase):
    def setUp(self):
        self.board = load(BOARD / "devcontainer.json")
        self.default = load(DEVCONTAINER / "devcontainer.json")

    def test_board_container_reuses_the_default_dockerfile(self):
        build = self.board["build"]
        self.assertEqual((BOARD / build["dockerfile"]).resolve(), (DEVCONTAINER / "Dockerfile").resolve())
        self.assertEqual((BOARD / build["context"]).resolve(), REPO.resolve())
        self.assertEqual(build["args"]["CRUX_JLINK"], "1")

    def test_board_container_is_not_privileged_and_allows_only_usb_devices(self):
        run_args = self.board["runArgs"]
        self.assertFalse(any("privileged" in argument for argument in run_args))
        self.assertFalse(any(argument.startswith(("--cap-add", "--device=/dev/", "--security-opt"))
                             for argument in run_args))
        rules = [argument for argument in run_args if argument.startswith("--device-cgroup-rule")]
        self.assertEqual(rules, ["--device-cgroup-rule=c 189:* rmw"])
        self.assertIn("source=/dev/bus/usb,target=/dev/bus/usb,type=bind", self.board["mounts"])

    def test_board_container_keeps_the_default_workspace_and_limits(self):
        for key in ("workspaceMount", "workspaceFolder", "containerEnv", "remoteEnv", "remoteUser",
                    "postCreateCommand"):
            self.assertEqual(self.board[key], self.default[key], key)
        for argument in self.default["runArgs"]:
            self.assertIn(argument, self.board["runArgs"])
        for mount in self.default["mounts"]:
            self.assertIn(mount, self.board["mounts"])

    def test_default_container_has_no_usb_access_and_no_jlink(self):
        self.assertNotIn("args", self.default["build"])
        self.assertFalse(any("/dev/bus/usb" in mount for mount in self.default.get("mounts", [])))
        self.assertFalse(any("device-cgroup-rule" in argument for argument in self.default["runArgs"]))

    def test_dockerfile_keeps_the_base_image_and_never_downloads_jlink(self):
        text = (DEVCONTAINER / "Dockerfile").read_text()
        from_lines = [line for line in text.splitlines() if line.startswith("FROM ")]
        self.assertEqual(from_lines, [f"FROM {BASE_IMAGE}"])
        lowered = text.lower()
        self.assertNotIn("segger.com", lowered)
        self.assertNotIn("--no-check-certificate", lowered)
        self.assertNotIn("curl -k", lowered)
        self.assertIn('if [ "$CRUX_JLINK" = 1 ]', text)
        install = INSTALL.read_text().lower()
        for forbidden in ("curl", "wget", "segger.com", "--no-check-certificate", "insecure"):
            self.assertNotIn(forbidden, install)

    def test_install_script_deletes_nothing(self):
        # The unit tests run the script on the CI host; any rm there would act on host files.
        code = [line.strip() for line in INSTALL.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")]
        self.assertFalse([line for line in code if re.search(r"(^|[;&|]\s*)rm\s", line)])

    def test_package_folder_tracks_no_package(self):
        tracked = subprocess.run(["git", "-C", str(REPO), "ls-files", ".devcontainer/jlink/packages"],
                                 check=True, capture_output=True, text=True).stdout.split()
        self.assertTrue(tracked)
        self.assertFalse([name for name in tracked if name.endswith(".deb")])


class InstallScriptTest(unittest.TestCase):
    """Runs install-jlink.sh against stub tools; nothing is installed."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="crux-jlink-test-")
        root = Path(self.temporary.name)
        self.packages = root / "packages"
        self.packages.mkdir()
        self.bin = root / "bin"
        self.bin.mkdir()
        self.log = root / "apt.log"
        self.stub("apt-get", f'echo "$@" >> "{self.log}"\n')
        self.stub("JLinkExe", "")
        self.stub("JLinkGDBServer", "")
        self.stub("usermod", f'echo "usermod $@" >> "{self.log}"\n')

    def tearDown(self):
        self.temporary.cleanup()

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def run_install(self, **environment):
        env = {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}"}
        env.update(environment)
        return subprocess.run(["sh", str(INSTALL), str(self.packages)], env=env,
                              capture_output=True, text=True)

    def package(self, name, content=b"not a real package"):
        (self.packages / name).write_bytes(content)

    def apt_calls(self):
        return self.log.read_text() if self.log.exists() else ""

    def test_fails_without_a_package(self):
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly one", result.stderr)
        self.assertEqual(self.apt_calls(), "")

    def test_fails_with_two_packages(self):
        self.package("JLink_Linux_V800_x86_64.deb")
        self.package("JLink_Linux_V810_x86_64.deb")
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exactly one", result.stderr)
        self.assertEqual(self.apt_calls(), "")

    def test_installs_the_single_package_with_usbutils(self):
        self.package("JLink_Linux_V810_x86_64.deb")
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.apt_calls()
        self.assertIn("install -y --no-install-recommends usbutils ./JLink_Linux_V810_x86_64.deb", calls)
        self.assertIn("usermod -aG plugdev vscode", calls)

    def test_named_package_must_be_a_plain_file_name(self):
        self.package("JLink_Linux_V810_x86_64.deb")
        result = self.run_install(CRUX_JLINK_DEB="../JLink_Linux_V810_x86_64.deb")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.apt_calls(), "")

    def test_named_package_is_used(self):
        self.package("JLink_Linux_V800_x86_64.deb")
        self.package("JLink_Linux_V810_x86_64.deb")
        result = self.run_install(CRUX_JLINK_DEB="JLink_Linux_V800_x86_64.deb")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("./JLink_Linux_V800_x86_64.deb", self.apt_calls())

    def test_checksum_mismatch_stops_before_apt(self):
        self.package("JLink_Linux_V810_x86_64.deb")
        result = self.run_install(CRUX_JLINK_DEB_SHA256="0" * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SHA-256", result.stderr)
        self.assertEqual(self.apt_calls(), "")

    def test_matching_checksum_in_upper_case_is_accepted(self):
        content = b"pretend package"
        self.package("JLink_Linux_V810_x86_64.deb", content)
        digest = __import__("hashlib").sha256(content).hexdigest().upper()
        result = self.run_install(CRUX_JLINK_DEB_SHA256=digest)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
