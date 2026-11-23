"""Checks for the board-ready Dev Container and its optional J-Link install (ADR-0007).

They prove that the files parse and keep their safety properties: no privileged
container, USB access limited to USB character devices, no download from SEGGER, a
download only from CRUX_JLINK_URL over HTTPS with a SHA-256 pin, a udevadm stub that
exists only while the package installs, and an image that still builds, with a
warning, when no package is given. They prove nothing about a real probe, usbipd, a real J-Link package or a
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
    """The one Dev Container is board-ready: USB access and J-Link when a package is given."""

    def setUp(self):
        self.config = load(DEVCONTAINER / "devcontainer.json")

    def test_there_is_one_dev_container_configuration(self):
        configs = sorted(path.relative_to(REPO).as_posix() for path in DEVCONTAINER.rglob("devcontainer.json"))
        self.assertEqual(configs, [".devcontainer/devcontainer.json"])

    def test_jlink_is_installed_when_a_package_is_given(self):
        # auto: install a placed package or CRUX_JLINK_URL; with neither, warn and build anyway.
        # A copy of the repository may set an internal URL; this repository keeps it empty.
        self.assertEqual(self.config["build"]["args"],
                         {"CRUX_JLINK": "auto", "CRUX_JLINK_DEB": "", "CRUX_JLINK_DEB_SHA256": "",
                          "CRUX_JLINK_URL": ""})

    def test_not_privileged_and_allows_only_usb_devices(self):
        run_args = self.config["runArgs"]
        self.assertFalse(any("privileged" in argument for argument in run_args))
        self.assertFalse(any(argument.startswith(("--cap-add", "--device=/dev/", "--security-opt"))
                             for argument in run_args))
        rules = [argument for argument in run_args if argument.startswith("--device-cgroup-rule")]
        self.assertEqual(rules, ["--device-cgroup-rule=c 189:* rmw"])

    def test_usb_folder_is_bound_so_that_a_missing_folder_does_not_stop_the_start(self):
        # `docker run -v` creates a missing source folder; a `mounts` entry (--mount) refuses to start.
        # On WSL2, /dev/bus/usb exists only after the first usbipd attach.
        run_args = self.config["runArgs"]
        index = run_args.index("-v")
        self.assertEqual(run_args[index + 1], "/dev/bus/usb:/dev/bus/usb")
        self.assertFalse(any("/dev/bus" in mount for mount in self.config["mounts"]))

    def test_keeps_the_workspace_cache_and_limits(self):
        self.assertEqual(self.config["workspaceMount"], "source=${localWorkspaceFolder}/..,target=/workspace,type=bind")
        self.assertEqual(self.config["workspaceFolder"], "/workspace/crux-pilot")
        self.assertEqual(self.config["mounts"], ["source=crux-host-cache,target=/opt/crux-cache,type=volume"])
        for argument in ("--platform=linux/amd64", "--memory=4g", "--cpus=2"):
            self.assertIn(argument, self.config["runArgs"])
        self.assertEqual(self.config["remoteUser"], "vscode")

    def test_dockerfile_keeps_the_base_image_and_never_downloads_jlink(self):
        text = (DEVCONTAINER / "Dockerfile").read_text()
        from_lines = [line for line in text.splitlines() if line.startswith("FROM ")]
        self.assertEqual(from_lines, [f"FROM {BASE_IMAGE}"])
        lowered = text.lower()
        self.assertNotIn("segger.com", lowered)
        self.assertNotIn("--no-check-certificate", lowered)
        self.assertNotIn("curl -k", lowered)
        self.assertIn('if [ "$CRUX_JLINK" != 0 ]', text)
        self.assertIn("ARG CRUX_JLINK=auto", text)
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


class BoardDebugProfilesTest(unittest.TestCase):
    """The Cortex-Debug profiles for the board container and the unchanged Mac profiles."""

    ELF = "${workspaceFolder}/build/zephyr/mimxrt1060_evk_B_qspi/zephyr/zephyr.elf"

    def setUp(self):
        vscode = REPO / ".vscode"
        self.launch = {c["name"]: c for c in load(vscode / "launch.json")["configurations"]}
        self.tasks = {t["label"]: t for t in load(vscode / "tasks.json")["tasks"]}

    def commands(self, configuration, key):
        return [entry["text"] for entry in configuration.get(key, [])]

    def test_mac_profiles_are_unchanged(self):
        self.assertEqual(self.launch["EVKB QSPI: Flash"]["miDebuggerServerAddress"], "host.docker.internal:2331")
        self.assertIn("-target-select remote host.docker.internal:2331",
                      self.commands(self.launch["EVKB QSPI: Attach"], "customLaunchSetupCommands"))

    def check_jlink(self, profile):
        self.assertEqual(profile["type"], "cortex-debug")
        self.assertEqual(profile["servertype"], "jlink")
        self.assertEqual(profile["device"], "MIMXRT1062xxx6A")
        self.assertEqual(profile["interface"], "swd")
        self.assertEqual(profile["executable"], self.ELF)
        args = profile["serverArgs"]
        self.assertEqual(args[args.index("-speed") + 1], "auto")
        self.assertNotIn("host.docker.internal", json.dumps(profile))

    def test_flash_profile_builds_downloads_and_runs_to_main(self):
        flash = self.launch["Board: Flash and run to main"]
        self.check_jlink(flash)
        self.assertEqual(flash["request"], "launch")
        self.assertEqual(flash["runToEntryPoint"], "main")
        self.assertEqual(flash["preLaunchTask"], "Build firmware")

    def test_attach_profile_neither_resets_nor_downloads(self):
        attach = self.launch["Board: Attach (no reset)"]
        self.check_jlink(attach)
        self.assertEqual(attach["request"], "attach")
        text = json.dumps(attach)
        for forbidden in ("runToEntryPoint", "preLaunchTask", "monitor reset", "overrideAttachCommands"):
            self.assertNotIn(forbidden, text)

    def test_flash_task_builds_then_flashes_with_the_jlink_runner(self):
        task = self.tasks["Board: Build and flash (west flash)"]
        self.assertEqual(task["command"], "west")
        self.assertEqual(task["args"], ["flash", "-d", "build/zephyr/mimxrt1060_evk_B_qspi", "-r", "jlink"])
        self.assertEqual(task["dependsOn"], "Build firmware")
        self.assertEqual(task["options"]["cwd"], "${workspaceFolder}")
        self.assertNotIn("--erase", json.dumps(task))

    def test_sample_flash_task_offers_the_board_samples(self):
        # Part C of the tutorial flashes hello_crux first; this task builds and flashes the sample
        # picked from a list with the tutorial's own commands.
        task = self.tasks["Board: Build and flash a sample (west flash)"]
        self.assertEqual(task["options"]["cwd"], "${workspaceFolder}")
        self.assertEqual(task["args"][-1], "${input:boardSample}")
        script = " ".join(task["args"])
        self.assertIn("west build -p always -b 'mimxrt1060_evk@B//qspi' -d \"$build\" \"$app\"", script)
        self.assertIn("west flash -d \"$build\" -r jlink", script)
        self.assertNotIn("--erase", script)
        inputs = {i["id"]: i for i in load(REPO / ".vscode" / "tasks.json")["inputs"]}
        pick = inputs["boardSample"]
        self.assertEqual(pick["type"], "pickString")
        self.assertEqual(pick["default"], "samples/hello_crux")
        self.assertEqual(pick["options"], ["samples/hello_crux", "samples/time/shell"])
        for sample in pick["options"]:
            self.assertTrue((REPO / sample / "sample.yaml").is_file(), sample)
        tutorial = (REPO / "docs" / "tutorial.md").read_text()
        self.assertIn("Board: Build and flash a sample (west flash)", tutorial)

    def test_no_cppdbg_board_profiles_or_server_tasks_remain(self):
        self.assertFalse([name for name in self.launch if name.startswith("Board container:")])
        self.assertFalse([label for label in self.tasks if label.startswith("Board container:")])

    def test_the_container_adds_cortex_debug(self):
        extensions = load(DEVCONTAINER / "devcontainer.json")["customizations"]["vscode"]["extensions"]
        self.assertIn("marus25.cortex-debug", extensions)


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
        # dpkg's maintainer-script PATH reduced to the stub's folder, so a real udevadm on the
        # test machine is never found.
        self.stub("apt-get", f'''echo "$@" >> "{self.log}"
case "$1" in
install)
    test -x "{self.udevadm}" && echo "stub present" >> "{self.log}"
    PATH="{self.udevadm.parent}" udevadm control --reload-rules || exit 1
    PATH="{self.udevadm.parent}" udevadm trigger --action=add --subsystem-match=usb || exit 1
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
        self.stub("JLinkGDBServerCLExe", "")
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

    def test_required_fails_without_a_package(self):
        result = self.run_install(CRUX_JLINK="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no SEGGER J-Link package", result.stderr)
        self.assertEqual(self.apt_calls(), "")

    def test_auto_without_package_or_url_warns_and_installs_nothing(self):
        for environment in ({}, {"CRUX_JLINK": "auto"}):
            with self.subTest(environment=environment):
                result = self.run_install(**environment)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("warning: no SEGGER J-Link package", result.stderr)
                self.assertIn(".devcontainer/jlink/packages/", result.stderr)
                self.assertIn("Rebuild Container", result.stderr)
                self.assertEqual(self.apt_calls(), "")
                self.assertFalse(self.udevadm.exists())

    def test_unknown_mode_is_rejected(self):
        result = self.run_install(CRUX_JLINK="yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CRUX_JLINK", result.stderr)

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
        result = self.run_install(CRUX_JLINK="1")
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
