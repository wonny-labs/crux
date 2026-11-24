"""Checks for scripts/bootstrap.sh, the one set-up entry that the Dev Container runs after it is created.

The script runs from a copy in a temporary repository whose scripts/bootstrap-host.sh and
scripts/bootstrap-zephyr.sh are stubs, with stub git, python3 and uname on PATH. Nothing is
downloaded, built or installed. They prove the order, the skipping, the failure reports and the
modes, not that the real downloads or builds work.
"""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "bootstrap.sh"
PINS = ("cmake==3.28.4", "ninja==1.11.1", "clang-format==18.1.8", "west==1.4.0", "pytest==8.3.5")


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="crux-bootstrap-test-")
        root = Path(self.temporary.name)
        self.workspace = root / "workspace"
        self.repo = self.workspace / "crux-pilot"
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy2(SCRIPT, self.repo / "scripts" / "bootstrap.sh")
        (self.repo / "west.yml").write_text("manifest: {}\n")
        self.cache = root / "cache"
        self.cache.mkdir()
        self.bin = root / "bin"
        self.bin.mkdir()
        self.log = root / "calls.log"
        self.git_config = root / "safe-directories"
        log = self.log
        self.stub(self.bin / "uname", 'echo "${FAKE_UNAME:-Linux}"\n')
        self.stub(self.bin / "git", f"""
if [ "$1 $2 $3" = "config --global --get-all" ]; then
    cat "{self.git_config}" 2>/dev/null
    exit 0
fi
if [ "$1 $2 $3 $4" = "config --global --add safe.directory" ]; then
    echo "$5" >> "{self.git_config}"
    exit 0
fi
echo "unexpected git $*" >&2
exit 3
""")
        # python3 -m venv DIR creates DIR/bin/python, whose `-m pip install` is logged.
        self.stub(self.bin / "python3", f"""
if [ "$1 $2" = "-m venv" ]; then
    echo "venv $3" >> "{log}"
    mkdir -p "$3/bin"
    printf '#!/bin/sh\\nshift 2\\necho "pip $*" >> "{log}"\\nexit "${{FAKE_PIP_STATUS:-0}}"\\n' > "$3/bin/python"
    chmod +x "$3/bin/python"
    exit 0
fi
echo "unexpected python3 $*" >&2
exit 3
""")
        self.stub(self.repo / "scripts" / "bootstrap-host.sh", f"""
echo "host CRUX_HOST_PRESET=${{CRUX_HOST_PRESET:-}}" >> "{log}"
echo "configuring the host build"
exit "${{FAKE_HOST_STATUS:-0}}"
""")
        sdk = self.cache / "sdk" / "zephyr-sdk-1.0.1"
        self.stub(self.repo / "scripts" / "bootstrap-zephyr.sh", f"""
echo "zephyr $*" >> "{log}"
echo "west update"
if [ "${{FAKE_ZEPHYR_STATUS:-0}}" != 0 ]; then
    echo "error: could not reach github.com" >&2
    exit "$FAKE_ZEPHYR_STATUS"
fi
mkdir -p "{self.workspace}/.west" "{self.workspace}/zephyr" "{sdk}/gnu/arm-zephyr-eabi/bin"
touch "{self.workspace}/.west/config"
""")
        # `west completion bash` is a Zephyr extension command: it works only in the workspace.
        self.west_cwd = root / "west-cwd"
        self.stub(self.bin / "west", f"""
if [ "$1 $2" = "completion bash" ] && [ "${{FAKE_WEST_COMPLETION_STATUS:-0}}" = 0 ]; then
    pwd > "{self.west_cwd}"
    echo "complete -W 'build flash' west"
    exit 0
fi
echo 'west: unknown command "completion"; do you need to run this inside a workspace?' >&2
exit "${{FAKE_WEST_COMPLETION_STATUS:-1}}"
""")

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def stub(path, body):
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def run_bootstrap(self, *arguments, **environment):
        env = {
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            # A J-Link installed on the test machine must not answer for the container.
            "CRUX_JLINK_EXE": "crux-test-jlink-exe",
            "HOME": self.temporary.name,
            "CRUX_WORKSPACE": str(self.workspace),
            "CRUX_REPO": str(self.repo),
            "CRUX_CACHE_DIR": str(self.cache),
            "ZEPHYR_SDK_INSTALL_DIR": str(self.cache / "sdk" / "zephyr-sdk-1.0.1"),
        }
        env.update(environment)
        return subprocess.run(["bash", str(self.repo / "scripts" / "bootstrap.sh"), *arguments],
                              env=env, capture_output=True, text=True)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def assertOk(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_script_parses(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_default_runs_tools_host_then_zephyr(self):
        result = self.run_bootstrap()
        self.assertOk(result)
        calls = self.calls()
        self.assertEqual(calls[0], f"venv {self.cache / 'venv'}")
        self.assertTrue(calls[1].startswith("pip install"), calls)
        for pin in PINS:
            self.assertIn(pin, calls[1])
        self.assertEqual(calls[2:], ["host CRUX_HOST_PRESET=host-debug", "zephyr --install-sdk"])
        self.assertIn("bootstrap: tools ok", result.stdout)
        self.assertIn("bootstrap: host ok", result.stdout)
        self.assertIn("bootstrap: zephyr ok", result.stdout)

    def test_second_run_skips_what_is_done(self):
        self.assertOk(self.run_bootstrap())
        self.log.unlink()
        result = self.run_bootstrap()
        self.assertOk(result)
        self.assertEqual(self.calls(), [])
        for step in ("tools", "host", "zephyr"):
            self.assertIn(f"bootstrap: {step} already done", result.stdout)

    def test_force_runs_every_step_again(self):
        self.assertOk(self.run_bootstrap())
        self.log.unlink()
        self.assertOk(self.run_bootstrap(CRUX_BOOTSTRAP_FORCE="1"))
        self.assertEqual(len(self.calls()), 3, self.calls())  # pip, host, zephyr; the venv exists

    def test_changed_manifest_runs_zephyr_again(self):
        self.assertOk(self.run_bootstrap())
        self.log.unlink()
        (self.repo / "west.yml").write_text("manifest: {projects: []}\n")
        self.assertOk(self.run_bootstrap())
        self.assertEqual(self.calls(), ["zephyr --install-sdk"])

    def test_missing_sdk_runs_zephyr_again(self):
        self.assertOk(self.run_bootstrap())
        self.log.unlink()
        shutil.rmtree(self.cache / "sdk")
        self.assertOk(self.run_bootstrap("zephyr"))
        self.assertEqual(self.calls(), ["zephyr --install-sdk"])

    def test_deleted_host_build_runs_host_again(self):
        self.assertOk(self.run_bootstrap())
        self.log.unlink()
        shutil.rmtree(self.repo / "build" / "linux" / "debug")
        self.assertOk(self.run_bootstrap())
        self.assertEqual(self.calls(), ["host CRUX_HOST_PRESET=host-debug"])

    def test_mode_from_environment_and_argument(self):
        self.assertOk(self.run_bootstrap(CRUX_BOOTSTRAP="host"))
        self.assertEqual(self.calls()[2:], ["host CRUX_HOST_PRESET=host-debug"])
        self.log.unlink()
        self.assertOk(self.run_bootstrap("zephyr", CRUX_BOOTSTRAP="host"))
        self.assertEqual(self.calls(), ["zephyr --install-sdk"])  # the argument wins; tools are done

    def test_unknown_mode_is_a_usage_error(self):
        result = self.run_bootstrap("everything")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage:", result.stderr)
        self.assertEqual(self.calls(), [])
        result = self.run_bootstrap(CRUX_BOOTSTRAP="nope")
        self.assertEqual(result.returncode, 2)

    def test_failure_stops_and_names_the_rerun_command(self):
        result = self.run_bootstrap(FAKE_HOST_STATUS="7")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("zephyr --install-sdk", self.calls())
        self.assertIn("bootstrap: host FAILED (exit 7)", result.stderr)
        self.assertIn("scripts/bootstrap.sh host", result.stderr)
        self.assertIn(str(self.cache / "bootstrap" / "host.log"), result.stderr)
        self.assertIn("configuring the host build", (self.cache / "bootstrap" / "host.log").read_text())

    def test_keep_going_runs_the_rest_and_exits_zero(self):
        result = self.run_bootstrap("--keep-going", FAKE_ZEPHYR_STATUS="4", FAKE_HOST_STATUS="5")
        self.assertOk(result)
        self.assertEqual([c.split()[0] for c in self.calls()], ["venv", "pip", "host", "zephyr"])
        self.assertIn("bootstrap: host FAILED (exit 5)", result.stderr)
        self.assertIn("bootstrap: zephyr FAILED (exit 4)", result.stderr)
        self.assertIn("could not reach github.com", (self.cache / "bootstrap" / "zephyr.log").read_text())
        self.assertIn("scripts/bootstrap.sh zephyr", result.stderr)
        self.assertIn("The Dev Container is usable", result.stderr)
        # The failed steps are not recorded as done, so the next run tries them again.
        self.log.unlink()
        self.assertOk(self.run_bootstrap())
        self.assertEqual(self.calls(), ["host CRUX_HOST_PRESET=host-debug", "zephyr --install-sdk"])

    def test_failed_tools_skip_the_steps_that_need_them(self):
        result = self.run_bootstrap("--keep-going", FAKE_PIP_STATUS="1")
        self.assertOk(result)
        self.assertEqual([c.split()[0] for c in self.calls()], ["venv", "pip"])
        self.assertIn("bootstrap: tools FAILED (exit 1)", result.stderr)
        self.assertIn("bootstrap: host skipped, it needs the tools step", result.stderr)

    def test_safe_directories_added_once(self):
        self.assertOk(self.run_bootstrap())
        self.assertOk(self.run_bootstrap(CRUX_BOOTSTRAP_FORCE="1"))
        entries = self.git_config.read_text().splitlines()
        self.assertIn(str(self.repo), entries)
        self.assertIn(str(self.workspace / "zephyr"), entries)
        self.assertEqual(len(entries), len(set(entries)), entries)

    def test_status_reports_without_installing(self):
        self.assertOk(self.run_bootstrap("--keep-going", FAKE_ZEPHYR_STATUS="4"))
        self.log.unlink()
        result = self.run_bootstrap("status")
        self.assertOk(result)
        self.assertEqual(self.calls(), [])
        self.assertRegex(result.stdout, r"host +ok")
        self.assertRegex(result.stdout, r"zephyr +FAILED \(exit 4\)")
        self.assertIn("scripts/bootstrap.sh zephyr", result.stdout)

    def test_status_follows_the_records(self):
        self.assertOk(self.run_bootstrap())
        shutil.rmtree(self.repo / "build" / "linux" / "debug")
        self.assertRegex(self.run_bootstrap("status").stdout, r"host +not run")
        # A deleted cache volume loses the status files; a skipped step writes its status again.
        shutil.rmtree(self.cache / "bootstrap")
        self.assertOk(self.run_bootstrap("--keep-going"))
        self.assertRegex(self.run_bootstrap("status").stdout, r"host +ok")

    def test_jlink_notice_when_the_tools_are_missing(self):
        result = self.run_bootstrap("host")
        self.assertOk(result)
        self.assertIn("J-Link software is not installed", result.stdout)
        # Behind a TLS-inspecting proxy the image's own download fails, so the notice names
        # the organisation CA first and the placed package second.
        self.assertIn(".devcontainer/certs/", result.stdout)
        self.assertIn(".devcontainer/jlink/packages/", result.stdout)
        self.assertLess(result.stdout.index(".devcontainer/certs/"),
                        result.stdout.index(".devcontainer/jlink/packages/"))
        self.stub(self.bin / "crux-test-jlink-exe", "exit 0\n")
        result = self.run_bootstrap("host")
        self.assertNotIn("J-Link software is not installed", result.stdout)

    def completion(self, base=None):
        base = Path(base) if base else Path(self.temporary.name) / ".local" / "share" / "bash-completion"
        return base / "completions" / "west.bash"

    def test_west_completion_written_to_the_user_directory_from_the_workspace(self):
        result = self.run_bootstrap()
        self.assertOk(result)
        self.assertEqual(self.completion().read_text(), "complete -W 'build flash' west\n")
        self.assertEqual(Path(self.west_cwd.read_text().strip()).resolve(), self.workspace.resolve())
        self.assertIn(str(self.completion()), result.stdout)

    def test_west_completion_follows_the_bash_completion_user_directory(self):
        xdg = Path(self.temporary.name) / "xdg"
        self.assertOk(self.run_bootstrap(XDG_DATA_HOME=str(xdg)))
        self.assertTrue(self.completion(xdg / "bash-completion").is_file())
        first, second = Path(self.temporary.name) / "first", Path(self.temporary.name) / "second"
        self.assertOk(self.run_bootstrap(BASH_COMPLETION_USER_DIR=f"{first}:{second}"))
        self.assertTrue(self.completion(first).is_file())
        self.assertFalse(second.exists())

    def test_west_completion_is_rewritten_on_every_run(self):
        self.assertOk(self.run_bootstrap())
        self.completion().write_text("stale\n")
        result = self.run_bootstrap()  # every step is already done
        self.assertOk(result)
        self.assertIn("bootstrap: zephyr already done", result.stdout)
        self.assertEqual(self.completion().read_text(), "complete -W 'build flash' west\n")

    def test_failed_west_completion_only_warns(self):
        self.assertOk(self.run_bootstrap())
        before = self.run_bootstrap("status").stdout
        for arguments in ((), ("--keep-going",)):
            result = self.run_bootstrap(*arguments, FAKE_WEST_COMPLETION_STATUS="1")
            self.assertOk(result)
            self.assertIn("warning:", result.stderr)
            self.assertIn("west", result.stderr)
            self.assertNotIn("FAILED", result.stdout + result.stderr)
            self.assertNotIn("not finished", result.stderr)
            # The script from the last good run stays, and no partial file is left beside it.
            self.assertEqual(self.completion().read_text(), "complete -W 'build flash' west\n")
            self.assertEqual(sorted(p.name for p in self.completion().parent.iterdir()), ["west.bash"])
        self.assertEqual(self.run_bootstrap("status").stdout, before)

    def test_failed_west_completion_on_the_first_run_writes_nothing(self):
        result = self.run_bootstrap(FAKE_WEST_COMPLETION_STATUS="1")
        self.assertOk(result)
        self.assertIn("bootstrap: zephyr ok", result.stdout)
        self.assertFalse(self.completion().exists())

    def test_west_completion_only_with_a_ready_workspace(self):
        self.assertOk(self.run_bootstrap("host"))
        self.assertFalse(self.west_cwd.exists())
        self.assertOk(self.run_bootstrap("--keep-going", FAKE_ZEPHYR_STATUS="4"))
        self.assertFalse(self.west_cwd.exists())

    def test_needs_linux(self):
        result = self.run_bootstrap(FAKE_UNAME="Darwin")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Dev Container", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_dev_container_runs_it_after_create(self):
        config = json.loads((REPO / ".devcontainer" / "devcontainer.json").read_text())
        self.assertEqual(config["postCreateCommand"], "bash scripts/bootstrap.sh --keep-going")
        self.assertEqual(config["postAttachCommand"], "bash scripts/bootstrap.sh status")
        # CRUX_BOOTSTRAP set on the host before the container is created picks the steps.
        self.assertEqual(config["containerEnv"]["CRUX_BOOTSTRAP"], "${localEnv:CRUX_BOOTSTRAP:all}")


if __name__ == "__main__":
    unittest.main()
