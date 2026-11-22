"""Checks for the optional J-Link board Dev Container (ADR-0007).

They prove that the files parse and keep their safety properties: no privileged
container, USB access limited to USB character devices, no download from SEGGER, a
download only from CRUX_JLINK_URL over HTTPS with a SHA-256 pin, a udevadm stub that
exists only while the package installs, and a default container that installs
nothing. They prove nothing about a real probe, usbipd, a real J-Link package or a
board.
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

    def test_board_container_leaves_the_package_url_empty(self):
        # The company copy substitutes an internal URL at export; GitHub keeps it empty.
        args = self.board["build"]["args"]
        self.assertEqual(args["CRUX_JLINK_URL"], "")
        self.assertEqual(args["CRUX_JLINK_DEB_SHA256"], "")

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
        self.assertIn("ARG CRUX_JLINK_URL=", text)
        self.assertNotIn("curl ", lowered)

    def test_install_script_downloads_only_over_https_from_the_configured_url(self):
        install = INSTALL.read_text()
        lowered = install.lower()
        for forbidden in ("wget", "segger.com", "--no-check-certificate", "insecure", "curl -k",
                          "--accept-license", "accept_license"):
            self.assertNotIn(forbidden, lowered)
        curl_lines = [line.strip() for line in install.splitlines()
                      if re.match(r"\s*curl\s", line)]
        self.assertEqual(len(curl_lines), 1, curl_lines)
        for flag in ("--fail", "--proto '=https'", "--proto-redir '=https'"):
            self.assertIn(flag, curl_lines[0])
        self.assertIn('"$url"', curl_lines[0])

    def test_install_script_deletes_only_its_udevadm_stub(self):
        # The unit tests run the script on the CI host; any other rm there would act on host files.
        code = [line.strip() for line in INSTALL.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")]
        removals = [line for line in code if re.search(r"(^|[;&|{]\s*)rm\s", line)]
        self.assertTrue(removals)
        for line in removals:
            self.assertRegex(line, r'rm -f "\$stub"')

    def test_udevadm_stub_defaults_to_the_maintainer_script_path(self):
        # /usr/local/bin was not on the PATH of dpkg's maintainer scripts in the first run.
        self.assertIn("${CRUX_JLINK_UDEVADM:-/usr/sbin/udevadm}", INSTALL.read_text())

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
        self.udevadm = root / "sbin" / "udevadm"
        self.udevadm.parent.mkdir()
        self.server = root / "server"
        self.server.mkdir()
        # A fake apt-get: "install" runs what the J-Link package's postinst runs, with
        # dpkg's maintainer-script PATH reduced to the stub's folder and the system tools.
        self.stub("apt-get", f'''echo "$@" >> "{self.log}"
case "$1" in
install)
    test -x "{self.udevadm}" && echo "stub present" >> "{self.log}"
    PATH="{self.udevadm.parent}:/usr/bin:/bin" udevadm control --reload-rules || exit 1
    PATH="{self.udevadm.parent}:/usr/bin:/bin" udevadm trigger --action=add --subsystem-match=usb || exit 1
    echo "postinst done" >> "{self.log}"
    exit "${{FAKE_APT_STATUS:-0}}"
    ;;
esac
''')
        # A fake curl: copies server/<last path segment of the URL> to --output.
        self.stub("curl", f'''out=; url=
while [ "$#" -gt 0 ]; do
    case "$1" in --output) out=$2; shift ;; https://*|http://*) url=$1 ;; esac
    shift
done
echo "curl $url" >> "{self.log}"
cp "{self.server}/${{url##*/}}" "$out"
''')
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
        env = {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
               "CRUX_JLINK_UDEVADM": str(self.udevadm)}
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
        self.assertIn("no SEGGER J-Link package", result.stderr)
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

    def test_udevadm_stub_lets_the_postinst_pass_and_is_removed(self):
        self.package("JLink_Linux_V996a_x86_64.deb")
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.apt_calls()
        self.assertIn("stub present", calls)
        self.assertIn("postinst done", calls)
        self.assertFalse(self.udevadm.exists())

    def test_udevadm_stub_is_removed_when_the_install_fails(self):
        self.package("JLink_Linux_V996a_x86_64.deb")
        result = self.run_install(FAKE_APT_STATUS="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stub present", self.apt_calls())
        self.assertFalse(self.udevadm.exists())

    def test_without_the_stub_the_postinst_fails(self):
        # Guards the fake: a missing udevadm must fail it, as in the first real run.
        self.package("JLink_Linux_V996a_x86_64.deb")
        self.udevadm.parent.rmdir()
        result = self.run_install(CRUX_JLINK_UDEVADM=str(self.udevadm.parent / "missing" / "udevadm"))
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("postinst done", self.apt_calls())

    def test_an_existing_udevadm_is_kept(self):
        self.package("JLink_Linux_V996a_x86_64.deb")
        self.udevadm.write_text("#!/bin/sh\n# real udevadm\nexit 0\n")
        self.udevadm.chmod(0o755)
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.udevadm.read_text(), "#!/bin/sh\n# real udevadm\nexit 0\n")

    def test_fails_with_a_clear_message_without_package_or_url(self):
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(".devcontainer/jlink/packages/", result.stderr)
        self.assertIn("CRUX_JLINK_URL", result.stderr)
        self.assertNotIn("curl", self.apt_calls())

    def serve(self, name, content):
        (self.server / name).write_bytes(content)
        return __import__("hashlib").sha256(content).hexdigest()

    def test_downloads_from_the_url_when_no_package_is_placed(self):
        digest = self.serve("JLink_Linux_V996a_x86_64.deb", b"hosted copy")
        result = self.run_install(CRUX_JLINK_URL="https://artifacts.example.invalid/jlink/JLink_Linux_V996a_x86_64.deb",
                                  CRUX_JLINK_DEB_SHA256=digest)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.apt_calls()
        self.assertIn("curl https://artifacts.example.invalid/jlink/JLink_Linux_V996a_x86_64.deb", calls)
        self.assertIn("usbutils ./JLink_Linux_download_x86_64.deb", calls)
        self.assertNotIn("artifacts.example.invalid", result.stdout + result.stderr)

    def test_url_needs_a_checksum(self):
        self.serve("JLink_Linux_V996a_x86_64.deb", b"hosted copy")
        result = self.run_install(CRUX_JLINK_URL="https://artifacts.example.invalid/jlink/JLink_Linux_V996a_x86_64.deb")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CRUX_JLINK_DEB_SHA256", result.stderr)
        self.assertEqual(self.apt_calls(), "")

    def test_url_must_use_https(self):
        digest = self.serve("JLink_Linux_V996a_x86_64.deb", b"hosted copy")
        result = self.run_install(CRUX_JLINK_URL="http://artifacts.example.invalid/jlink/JLink_Linux_V996a_x86_64.deb",
                                  CRUX_JLINK_DEB_SHA256=digest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("https://", result.stderr)
        self.assertEqual(self.apt_calls(), "")

    def test_downloaded_package_with_a_wrong_checksum_is_not_installed(self):
        self.serve("JLink_Linux_V996a_x86_64.deb", b"tampered copy")
        result = self.run_install(CRUX_JLINK_URL="https://artifacts.example.invalid/jlink/JLink_Linux_V996a_x86_64.deb",
                                  CRUX_JLINK_DEB_SHA256="0" * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SHA-256", result.stderr)
        self.assertNotIn("install", self.apt_calls())

    def test_a_placed_package_wins_over_the_url(self):
        self.package("JLink_Linux_V810_x86_64.deb")
        result = self.run_install(CRUX_JLINK_URL="https://artifacts.example.invalid/jlink/JLink_Linux_V996a_x86_64.deb")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("curl", self.apt_calls())
        self.assertIn("./JLink_Linux_V810_x86_64.deb", self.apt_calls())

    def test_matching_checksum_in_upper_case_is_accepted(self):
        content = b"pretend package"
        self.package("JLink_Linux_V810_x86_64.deb", content)
        digest = __import__("hashlib").sha256(content).hexdigest().upper()
        result = self.run_install(CRUX_JLINK_DEB_SHA256=digest)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
