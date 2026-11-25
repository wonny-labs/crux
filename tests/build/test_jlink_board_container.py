"""Checks for the board-ready Dev Container and its optional J-Link install (ADR-0007).

They prove that the files parse and keep their safety properties: no privileged
container, USB access limited to USB character devices, downloads only over HTTPS and
always checked against a SHA-256 pin, the order placed package, CRUX_JLINK_URL, then the
version pinned in the Dockerfile from SEGGER's download endpoint, a udevadm stub that
exists only while the package installs, and an image that still builds, with a
warning, when no package can be had. The download is stubbed: they prove nothing about
SEGGER's endpoint, a real probe, usbipd, a real J-Link package or a board.
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
DOCKERFILE = DEVCONTAINER / "Dockerfile"
SEGGER_ENDPOINT = "https://www.segger.com/downloads/jlink/"
CI_IMAGE_BUILD = ("docker build --platform linux/amd64 --build-arg CRUX_JLINK=0 "
                  "-f .devcontainer/Dockerfile -t crux-dev .")
BASE_IMAGE = ("mcr.microsoft.com/devcontainers/base:ubuntu-24.04"
              "@sha256:d94c97dd9cacf183d0a6fd12a8e87b526e9e928307674ae9c94139139c0c6eae")


def load(path):
    return json.loads(path.read_text())


def dockerfile_arg(name):
    match = re.search(rf"^ARG {name}=(\S*)$", DOCKERFILE.read_text(), re.MULTILINE)
    return match.group(1) if match else None


class BoardContainerConfigTest(unittest.TestCase):
    """The one Dev Container is board-ready: USB access and J-Link when a package is given."""

    def setUp(self):
        self.config = load(DEVCONTAINER / "devcontainer.json")

    def test_there_is_one_dev_container_configuration(self):
        configs = sorted(path.relative_to(REPO).as_posix() for path in DEVCONTAINER.rglob("devcontainer.json"))
        self.assertEqual(configs, [".devcontainer/devcontainer.json"])

    def test_jlink_is_installed_when_a_package_is_given(self):
        # auto: a placed package, then CRUX_JLINK_URL, then the SEGGER version pinned in the
        # Dockerfile; when none gives a package, warn and build anyway.
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
        self.assertEqual(self.config["mounts"], [
            "source=crux-host-cache,target=/opt/crux-cache,type=volume",
            "source=crux-vscode-extensions,target=/home/vscode/.vscode-server/extensions,type=volume",
        ])
        for argument in ("--platform=linux/amd64", "--memory=4g", "--cpus=2"):
            self.assertIn(argument, self.config["runArgs"])
        self.assertEqual(self.config["remoteUser"], "vscode")

    def test_dockerfile_keeps_the_base_image_and_leaves_downloads_to_the_script(self):
        text = DOCKERFILE.read_text()
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

    def test_ci_and_automated_image_builds_skip_jlink(self):
        # CI and other automated image builds never download from SEGGER: the documented build
        # command passes CRUX_JLINK=0, and every docker build line in the current docs does too.
        guide = (REPO / "docs" / "board-jlink-usbipd.md").read_text()
        self.assertIn(CI_IMAGE_BUILD, guide)
        self.assertIn("--build-arg CRUX_JLINK=0", DOCKERFILE.read_text())
        skipped = ("docs/evidence/", "docs/history/", "docs/plans/", "docs/baseline.md")
        documented = []
        for path in sorted(REPO.glob("docs/**/*.md")) + sorted(REPO.glob("*.md")):
            rel = path.relative_to(REPO).as_posix()
            if rel.startswith(skipped):
                continue
            for line in path.read_text().splitlines():
                if re.search(r"\bdocker build\b.*\.devcontainer/Dockerfile", line):
                    documented.append((rel, line.strip()))
        self.assertTrue(documented)
        for rel, line in documented:
            self.assertIn("--build-arg CRUX_JLINK=0", line, rel)
        # People's Dev Container builds keep auto.
        self.assertEqual(self.config["build"]["args"]["CRUX_JLINK"], "auto")

    def test_segger_version_and_checksum_are_pinned_once_in_the_dockerfile(self):
        # A bump changes these two values and nothing else.
        version = dockerfile_arg("CRUX_JLINK_SEGGER_VERSION")
        digest = dockerfile_arg("CRUX_JLINK_SEGGER_SHA256")
        self.assertRegex(version or "", r"^V[0-9]+[a-z]?$")
        self.assertRegex(digest or "", r"^[0-9a-f]{64}$")
        holders = subprocess.run(["git", "-C", str(REPO), "grep", "-l", "-F", digest],
                                 capture_output=True, text=True).stdout.split()
        self.assertEqual(holders, [".devcontainer/Dockerfile"])
        build_args = self.config["build"]["args"]
        self.assertNotIn("CRUX_JLINK_SEGGER_VERSION", build_args)
        self.assertNotIn("CRUX_JLINK_SEGGER_SHA256", build_args)

    def test_install_script_downloads_only_over_https(self):
        install = INSTALL.read_text()
        lowered = install.lower()
        for forbidden in ("wget", "--no-check-certificate", "insecure", "curl -k"):
            self.assertNotIn(forbidden, lowered)
        curl_lines = [line.strip() for line in install.splitlines()
                      if re.match(r"(if\s+)?curl\s", line.strip())]
        self.assertEqual(len(curl_lines), 2, curl_lines)
        for line in curl_lines:
            for flag in ("--fail", "--proto '=https'", "--proto-redir '=https'"):
                self.assertIn(flag, line)
        self.assertIn('"$url"', curl_lines[0])
        self.assertIn('"$segger_url"', curl_lines[1])
        self.assertIn("--data 'accept_license_agreement=accepted'", curl_lines[1])
        self.assertIn(f'segger_url="{SEGGER_ENDPOINT}', install)

    def test_install_script_notes_that_the_download_accepts_the_terms(self):
        self.assertIn("accepts SEGGER's terms of use", INSTALL.read_text())

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
    """The Cortex-Debug profiles: J-Link in the container, or a GDB server on the host."""

    # The link that scripts/build-debug-target.sh points at the build it made last.
    ELF = "${workspaceFolder}/build/zephyr/mimxrt1060_evk_B_qspi--current/zephyr/zephyr.elf"

    def setUp(self):
        vscode = REPO / ".vscode"
        self.launch = {c["name"]: c for c in load(vscode / "launch.json")["configurations"]}
        self.tasks = {t["label"]: t for t in load(vscode / "tasks.json")["tasks"]}

    def commands(self, configuration, key):
        return [entry["text"] for entry in configuration.get(key, [])]

    def test_host_server_profile_attaches_to_an_external_gdb_server(self):
        # Cortex-Debug's "external" server type: the user starts the J-Link GDB Server on the host.
        host = self.launch["Board: Attach (external)"]
        self.assertEqual(host["type"], "cortex-debug")
        self.assertEqual(host["request"], "attach")
        self.assertEqual(host["servertype"], "external")
        self.assertEqual(host["gdbTarget"], "host.docker.internal:2331")
        self.assertEqual(host["executable"], self.ELF)
        text = json.dumps(host)
        for forbidden in ("serverpath", "serverArgs", "preLaunchTask", "monitor reset", "overrideAttachCommands"):
            self.assertNotIn(forbidden, text)

    def test_no_evkb_qspi_profile_remains(self):
        self.assertFalse([name for name in self.launch if name.startswith("EVKB QSPI")])
        self.assertNotIn("inputs", load(REPO / ".vscode" / "launch.json"))

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
        flash = self.launch["Board: Debug"]
        self.check_jlink(flash)
        self.assertEqual(flash["request"], "launch")
        self.assertEqual(flash["runToEntryPoint"], "main")
        # A hidden task checks that a J-Link is attached, then runs Board: Build.
        self.assertEqual(flash["preLaunchTask"], "Board: Check probe and build")

    def test_board_build_asks_for_the_sample_and_defaults_to_hello_crux(self):
        task = self.tasks["Board: Build"]
        self.assertEqual(task["type"], "process")
        self.assertEqual(task["command"], "${workspaceFolder}/scripts/build-debug-target.sh")
        self.assertEqual(task["args"], ["mimxrt1060_evk@B//qspi", "--app", "${input:sample}"])
        self.assertEqual(task["options"]["cwd"], "${workspaceFolder}")
        self.assertEqual(task["group"], "build")
        inputs = {i["id"]: i for i in load(REPO / ".vscode" / "tasks.json")["inputs"]}
        prompt = inputs["sample"]
        self.assertEqual(prompt["type"], "promptString")
        self.assertEqual(prompt["description"], "Sample directory, relative to the repository")
        self.assertEqual(prompt["default"], "samples/hello_crux")
        self.assertTrue((REPO / prompt["default"] / "CMakeLists.txt").is_file())

    def test_every_pre_launch_task_exists(self):
        for name, profile in self.launch.items():
            if "preLaunchTask" in profile:
                with self.subTest(profile=name):
                    self.assertIn(profile["preLaunchTask"], self.tasks)

    def test_docs_name_the_debug_profile_and_the_current_link(self):
        tutorial = (REPO / "docs" / "tutorial.md").read_text()
        self.assertIn("Board: Debug", tutorial)
        self.assertIn("samples/hello_crux", tutorial)
        board = (REPO / "docs" / "boards" / "mimxrt1060_evkb.md").read_text()
        self.assertIn("build/zephyr/mimxrt1060_evk_B_qspi--current", board)
        for profile in self.launch:
            if profile.startswith("Board:"):
                self.assertIn(profile, board)

    def test_attach_profile_neither_resets_nor_downloads(self):
        attach = self.launch["Board: Attach"]
        self.check_jlink(attach)
        self.assertEqual(attach["request"], "attach")
        text = json.dumps(attach)
        for forbidden in ("runToEntryPoint", "monitor reset", "overrideAttachCommands"):
            self.assertNotIn(forbidden, text)
        # Its only pre-launch step checks that a J-Link is attached; it builds nothing.
        self.assertEqual(attach["preLaunchTask"], "Board: Check probe")

    def test_flash_task_flashes_the_last_board_build_with_the_jlink_runner(self):
        # The task flashes the build behind the link that the debug profiles use, so Board: Build
        # then Board: Flash puts on the board the image that Board: Attach expects.
        # The probe check runs in the same bash process, before west flash.
        task = self.tasks["Board: Flash"]
        self.assertEqual(task["command"], "bash")
        current = self.ELF.removeprefix("${workspaceFolder}/").removesuffix("/zephyr/zephyr.elf")
        self.assertEqual(task["args"][0], "-c")
        script = task["args"][1]
        self.assertTrue(script.endswith(f"; exec west flash -d {current} -r jlink"), script)
        self.assertTrue(script.startswith(self.tasks["Board: Check probe"]["args"][1]), script)
        self.assertNotIn("dependsOn", task)
        self.assertEqual(task["options"]["cwd"], "${workspaceFolder}")
        self.assertNotIn("--erase", json.dumps(task))

    def test_no_cppdbg_board_profiles_or_server_tasks_remain(self):
        self.assertFalse([name for name in self.launch if name.startswith("Board container:")])
        self.assertFalse([label for label in self.tasks if label.startswith("Board container:")])

    def test_the_container_adds_cortex_debug(self):
        extensions = load(DEVCONTAINER / "devcontainer.json")["customizations"]["vscode"]["extensions"]
        self.assertIn("marus25.cortex-debug", extensions)

    def test_extensions_volume_is_owned_by_the_remote_user(self):
        # A new named volume copies owner and mode from the image folder; without the folder it
        # is root-owned and the vscode user cannot install extensions into it.
        config = load(DEVCONTAINER / "devcontainer.json")
        self.assertEqual(config["remoteUser"], "vscode")
        self.assertIn("source=crux-vscode-extensions,target=/home/vscode/.vscode-server/extensions,type=volume",
                      config["mounts"])
        dockerfile = (DEVCONTAINER / "Dockerfile").read_text()
        self.assertIn("install -d -o vscode -g vscode /home/vscode/.vscode-server /home/vscode/.vscode-server/extensions", dockerfile)

    def test_cortex_debug_dependencies_come_before_it(self):
        # Cortex-Debug lists these four as extensionDependencies (checked against its
        # package.json, v1.12.1). Fetched after it, it activates first and VS Code asks for
        # a window reload on the first creation of the container.
        extensions = load(DEVCONTAINER / "devcontainer.json")["customizations"]["vscode"]["extensions"]
        position = extensions.index("marus25.cortex-debug")
        for dependency in (
            "mcu-debug.debug-tracker-vscode",
            "mcu-debug.memory-view",
            "mcu-debug.rtos-views",
            "mcu-debug.peripheral-viewer",
        ):
            self.assertIn(dependency, extensions)
            self.assertLess(extensions.index(dependency), position, dependency)

    def test_each_debug_extension_serves_a_profile(self):
        # Cortex-Debug runs every board profile and the C/C++ extension (cppdbg) the native_sim
        # profile; no other debug front-end is installed.
        extensions = load(DEVCONTAINER / "devcontainer.json")["customizations"]["vscode"]["extensions"]
        types = {name: profile["type"] for name, profile in self.launch.items()}
        self.assertEqual({t for n, t in types.items() if n.startswith("Board:")}, {"cortex-debug"})
        self.assertEqual({t for n, t in types.items() if not n.startswith("Board:")}, {"cppdbg"})
        self.assertIn("marus25.cortex-debug", extensions)
        self.assertIn("ms-vscode.cpptools", extensions)
        self.assertNotIn("Arm.vscode-cmsis-debugger", extensions)


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
        # A fake curl: copies server/<last path segment of the URL> to --output, logs the
        # URL and any posted form data, and fails with FAKE_CURL_STATUS. No network is used.
        self.stub("curl", f'''out=; url=; data=
while [ "$#" -gt 0 ]; do
    case "$1" in
    --output) out=$2; shift ;;
    --data) data="$data $2"; shift ;;
    https://*|http://*) url=$1 ;;
    esac
    shift
done
echo "curl $url$data" >> "{self.log}"
if [ "${{FAKE_CURL_STATUS:-0}}" != 0 ]; then
    echo "curl: (22) The requested URL returned error: 503" >&2
    exit "$FAKE_CURL_STATUS"
fi
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

    # The SEGGER route: the pinned version, downloaded when no package is placed and no
    # CRUX_JLINK_URL is set. The values below are test values; the Dockerfile holds the pin.
    SEGGER_VERSION = "V996a"
    SEGGER_FILE = "JLink_Linux_V996a_x86_64.deb"

    def segger(self, content=b"package from the vendor endpoint", digest=None):
        served = self.serve(self.SEGGER_FILE, content)
        return {"CRUX_JLINK_SEGGER_VERSION": self.SEGGER_VERSION,
                "CRUX_JLINK_SEGGER_SHA256": digest if digest is not None else served}

    def test_downloads_the_pinned_version_from_segger_when_nothing_else_is_given(self):
        result = self.run_install(**self.segger())
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.apt_calls()
        self.assertIn(f"curl {SEGGER_ENDPOINT}{self.SEGGER_FILE} accept_license_agreement=accepted", calls)
        self.assertIn(f"install -y --no-install-recommends usbutils ./{self.SEGGER_FILE}", calls)
        self.assertIn("terms of use", result.stdout + result.stderr)
        self.assertFalse(self.udevadm.exists())

    def test_order_a_placed_package_wins_over_the_url_and_segger(self):
        # CRUX_JLINK_DEB_SHA256, when set, checks the placed package, so it is left out here.
        self.package("JLink_Linux_V810_x86_64.deb")
        self.serve("JLink_Linux_V990_x86_64.deb", b"hosted copy")
        result = self.run_install(CRUX_JLINK_URL="https://artifacts.example.invalid/jlink/JLink_Linux_V990_x86_64.deb",
                                  **self.segger())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("curl", self.apt_calls())
        self.assertIn("./JLink_Linux_V810_x86_64.deb", self.apt_calls())

    def test_order_the_url_wins_over_segger(self):
        hosted = self.serve("JLink_Linux_V990_x86_64.deb", b"hosted copy")
        result = self.run_install(CRUX_JLINK_URL="https://artifacts.example.invalid/jlink/JLink_Linux_V990_x86_64.deb",
                                  CRUX_JLINK_DEB_SHA256=hosted, **self.segger())
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.apt_calls()
        self.assertIn("curl https://artifacts.example.invalid/jlink/JLink_Linux_V990_x86_64.deb", calls)
        self.assertNotIn("segger.com", calls)
        self.assertIn("usbutils ./JLink_Linux_download_x86_64.deb", calls)

    def test_failed_segger_download_warns_and_builds_without_jlink(self):
        result = self.run_install(FAKE_CURL_STATUS="22", **self.segger())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("warning: the J-Link download from SEGGER failed", result.stderr)
        self.assertIn("built without the J-Link software", result.stderr)
        self.assertIn(".devcontainer/jlink/packages/", result.stderr)
        calls = self.apt_calls()
        self.assertIn("curl ", calls)
        self.assertNotIn("install", calls)
        self.assertNotIn("usermod", calls)
        self.assertFalse(self.udevadm.exists())

    def test_segger_download_with_a_wrong_checksum_warns_and_installs_nothing(self):
        result = self.run_install(**self.segger(content=b"changed upstream", digest="0" * 64))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SHA-256", result.stderr)
        self.assertIn("0" * 64, result.stderr)
        self.assertIn("built without the J-Link software", result.stderr)
        self.assertNotIn("install", self.apt_calls())
        self.assertFalse(self.udevadm.exists())

    def test_required_mode_fails_when_the_segger_download_fails(self):
        result = self.run_install(CRUX_JLINK="1", FAKE_CURL_STATUS="22", **self.segger())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("J-Link download from SEGGER failed", result.stderr)
        self.assertNotIn("install", self.apt_calls())

    def test_required_mode_fails_on_a_segger_checksum_mismatch(self):
        result = self.run_install(CRUX_JLINK="1", **self.segger(digest="0" * 64))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SHA-256", result.stderr)
        self.assertNotIn("install", self.apt_calls())

    def test_malformed_segger_pin_is_not_downloaded(self):
        for environment in ({"CRUX_JLINK_SEGGER_VERSION": "V996a/../x", "CRUX_JLINK_SEGGER_SHA256": "a" * 64},
                            {"CRUX_JLINK_SEGGER_VERSION": "V996a", "CRUX_JLINK_SEGGER_SHA256": "abc"},
                            {"CRUX_JLINK_SEGGER_VERSION": "V996a"}):
            with self.subTest(environment=environment):
                result = self.run_install(**environment)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("warning:", result.stderr)
                self.assertNotIn("curl", self.apt_calls())

    def test_matching_checksum_in_upper_case_is_accepted(self):
        content = b"pretend package"
        self.package("JLink_Linux_V810_x86_64.deb", content)
        digest = __import__("hashlib").sha256(content).hexdigest().upper()
        result = self.run_install(CRUX_JLINK_DEB_SHA256=digest)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
