#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check tests/target/check_boot_images.sh, the check of the CI-built boot images, on the host.

The script reads the images that scripts/test-boot-composition.sh builds. This file cannot build them:
the real Zephyr build, the real imgtool and the real images are exercised only where the composition
check runs (the Linux Dev Container and CI), and the script has not run there yet. Here the script runs
end to end against

* a FAKE build tree that the test writes into a temporary directory, holding synthetic images built with
  the helpers of tests/build/test_boot_image_inspect.py, and
* a FAKE imgtool.py (clearly named inside, and not MCUboot's tool) in a fake MCUboot checkout at the path
  that the script derives from CRUX_WORKSPACE. Its `verify` answers as the test chooses and its `getpub`
  prints a PEM public key that the test chooses.

So these tests show that the script's logic does what it says (it passes, fails loudly, exits 2) when
the inspector and "imgtool" behave as the test lets them. They say nothing about whether the inspector's
reading of a real image agrees with MCUboot: that is what the script will settle when it runs on a real
build. The synthetic images share the inspector's own reading of the layouts.
The tests use the standard library only.
"""
import hashlib
import base64
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "tests/target/check_boot_images.sh"
PAGE = REPO / "docs/boot-image-inspection.md"
PROPOSAL = REPO / "docs/plans/image-state-contract-proposal.md"
SLOT_SIZE = 3145728


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The builders of the inspector's own host tests: header, TLVs, digest, and trailer fields at the
# offsets of the repository's trailer model.
helpers = load_module(REPO / "tests/build/test_boot_image_inspect.py", "boot_image_inspect_helpers")

# 91 bytes, the length of a P-256 SubjectPublicKeyInfo. Not a key.
FAKE_SPKI = bytes(range(91))
OTHER_SPKI = bytes(range(1, 92))

FAKE_IMGTOOL = '''#!/usr/bin/env python3
"""FAKE imgtool for tests/build/test_check_boot_images.py. This is NOT MCUboot's imgtool.

verify -k KEY FILE   exits as fake-mode.txt says: honest (0 only for a file whose SHA-256 is listed in
                     fake-good-sha256.txt), accept-all (0), refuse-all (1), crash (traceback)
sign ... --slot-size N IN OUT
                     refuses (exit 1, "exceeds requested size") when N is below the input plus a fixed
                     header, TLV and trailer allowance, unless the mode is accept-all (never refuses)
                     or refuse-all (always refuses); crash raises; otherwise copies IN to OUT
getpub -k KEY [-e E] prints fake-public.pem, or exits 1 when that file is absent
--help               exits 0, as the real tool does when its requirements are installed
mode no-requirements raises ModuleNotFoundError for every command, as the real tool does without them
"""
import hashlib
from pathlib import Path
import sys

here = Path(__file__).resolve().parent
mode = (here / "fake-mode.txt").read_text().strip()
command = sys.argv[1]
if mode == "no-requirements":
    raise ModuleNotFoundError("No module named 'cryptography' (FAKE imgtool)")
if command == "--help":
    print("FAKE imgtool help")
    sys.exit(0)
if command == "verify":
    data = Path(sys.argv[-1]).read_bytes()
    good = (here / "fake-good-sha256.txt").read_text().split()
    if mode == "crash":
        raise RuntimeError("FAKE imgtool crash")
    accepted = mode == "accept-all" or (mode == "honest" and hashlib.sha256(data).hexdigest() in good)
    print("FAKE imgtool verify: " + ("Image was correctly validated" if accepted else "Image is not valid"))
    sys.exit(0 if accepted else 1)
if command == "sign":
    if mode == "crash":
        raise RuntimeError("FAKE imgtool crash")
    args = sys.argv[2:]
    slot = int(args[args.index("--slot-size") + 1], 0)
    source, target = Path(args[-2]), Path(args[-1])
    needed = len(source.read_bytes()) + 0x400 + 152 + 64
    if mode == "refuse-all" or (mode != "accept-all" and slot < needed):
        print(f"FAKE imgtool sign: Image size ({needed - 64}) + trailer (64) exceeds requested size {slot}")
        sys.exit(1)
    target.write_bytes(source.read_bytes())
    sys.exit(0)
if command == "getpub":
    pem = here / "fake-public.pem"
    if not pem.is_file():
        print("FAKE imgtool getpub: no key", file=sys.stderr)
        sys.exit(1)
    sys.stdout.write(pem.read_text())
    sys.exit(0)
sys.exit(2)
'''


def pem_of(der):
    body = base64.b64encode(der).decode()
    lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    return "-----BEGIN PUBLIC KEY-----\n" + "\n".join(lines) + "\n-----END PUBLIC KEY-----\n"


def confirmed_of(image, align, **trailer):
    """The padded image of the slot size: the image, then the trailer of the repository's model."""
    return image + helpers.trailer_bytes(SLOT_SIZE, align, **trailer)[len(image):]


class ScriptShape(unittest.TestCase):
    def setUp(self):
        self.script = SCRIPT.read_text(encoding="utf-8")
        # Comments may name what the script avoids, so the rules that forbid a word read code only.
        self.code = "\n".join(l for l in self.script.splitlines() if not l.lstrip().startswith("#"))

    def test_the_script_exists_and_is_executable(self):
        self.assertTrue(SCRIPT.is_file(), f"{SCRIPT} is missing")
        self.assertTrue(SCRIPT.stat().st_mode & 0o111, "the script is not executable")
        self.assertTrue(self.script.startswith("#!/usr/bin/env bash\n"))

    def test_the_script_sits_beside_the_inspector_and_not_under_scripts(self):
        # scripts/ is a protected path (AGENTS.md); tests/target/ is not.
        self.assertTrue(SCRIPT.is_file())
        self.assertEqual(REPO / "tests/target", SCRIPT.parent)
        self.assertTrue((SCRIPT.parent / "inspect_boot_image.py").is_file())
        self.assertFalse((REPO / "scripts/check-boot-images.sh").exists())
        self.assertFalse(list((REPO / "scripts").glob("*boot*image*")))

    def test_the_script_derives_the_repository_root_from_its_depth(self):
        # tests/target/ is two levels below the repository root.
        self.assertIn('repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"', self.code)
        self.assertTrue((REPO / "tests/boot_fixture/zephyr").is_dir())
        self.assertIn('app="$repo/tests/boot_fixture/zephyr"', self.code)
        self.assertIn('inspector=("$python" "$repo/tests/target/inspect_boot_image.py")', self.code)

    def test_the_default_build_directory_is_under_the_derived_repository_root(self):
        default = REPO / "build/zephyr/boot-composition"
        if default.exists():
            self.skipTest("a local composition build exists at the default directory")
        done = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True,
                              env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
                                   "CRUX_PYTHON": sys.executable})
        self.assertEqual(2, done.returncode, done.stderr)
        self.assertIn(str(default), done.stderr)

    def test_the_script_uses_strict_mode(self):
        self.assertIn("set -euo pipefail", self.code.splitlines())

    def test_the_script_builds_nothing_and_installs_nothing(self):
        for word in ("west", "ninja", "cmake", "make", "ccache", "docker", "curl", "wget", "git"):
            self.assertIsNone(re.search(rf"\b{word}\b", self.code), f"the code uses {word}")
        for text in ("-m pip", "pip install", "pip3"):
            self.assertNotIn(text, self.code)

    def test_the_script_never_generates_a_key_or_touches_a_board(self):
        for forbidden in ("keygen", "flash", "debug", "openocd", "pyocd", "JLink", "probe", "reset"):
            self.assertNotIn(forbidden, self.code, forbidden)

    def test_the_script_finds_the_images_the_way_the_composition_check_does(self):
        self.assertIn('image="$(basename "$app")"', self.code)
        # The sysbuild layout: the images sit in $build/<image>/zephyr, not anywhere below it.
        self.assertIn('app_dir="$build/$image/zephyr"', self.code)
        self.assertIn('find "$app_dir" -maxdepth 1 -name "$name" -print', self.code)
        self.assertIn("locate zephyr.signed.bin", self.code)
        self.assertIn("locate zephyr.signed.confirmed.bin", self.code)
        self.assertNotIn("-print -quit", self.code)
        self.assertIn('mcuboot_bin="$build/mcuboot/zephyr/zephyr.bin"', self.code)
        self.assertIn('build="${1:-$repo/build/zephyr/boot-composition}"', self.code)
        self.assertIn('python="${CRUX_PYTHON:-python3}"', self.code)
        self.assertIn('workspace="${CRUX_WORKSPACE:-$(dirname "$repo")}"', self.code)

    def test_the_script_has_an_exit_2_path_that_names_the_build_script(self):
        self.assertIn("exit 2", self.code)
        self.assertIn("scripts/test-boot-composition.sh", self.code)

    def test_the_script_says_who_calls_it_and_that_it_has_not_run_on_a_real_build(self):
        # It was "NOT wired into any workflow"; scripts/test-boot-composition.sh calls it now (the owner
        # approved the edit on 2026-11-16), so the header names the caller and keeps the other statement.
        header = "\n".join(l for l in self.script.splitlines() if l.startswith("#"))
        self.assertRegex(header, r"scripts/test-boot-composition\.sh calls it")
        self.assertRegex(header, r"approved by the project owner on 2026-11-16")
        self.assertNotRegex(header, r"pending the project owner")
        self.assertRegex(header, r"never run on a real build")

    def test_the_script_names_the_v442_erratum_for_a_missing_confirmed_image(self):
        self.assertIn("v4.4.2", self.code)
        self.assertIn("docs/boot-update-investigation.md", self.code)

    def test_the_expected_states_are_in_the_proposal_table(self):
        # The states for "good magic, image_ok set, copy_done unset" come from the proposal's table, not
        # from a guess: the running slot is RUNNING_CONFIRMED, a slot that is not running is
        # PENDING_PERMANENT.
        proposal = PROPOSAL.read_text(encoding="utf-8")
        self.assertRegex(proposal, r"\| `R` \| Valid \| Good \| Set \| any \| `RUNNING_CONFIRMED` \|")
        self.assertRegex(proposal, r"\| Not `R` \| Valid \| Good \| Set \| Unset \| `PENDING_PERMANENT` \|")
        self.assertIn('EXPECTED_RUNNING = "RUNNING_CONFIRMED"', self.script)
        self.assertIn('EXPECTED_IDLE = "PENDING_PERMANENT"', self.script)
        self.assertIn("image-state-contract-proposal.md", self.script)

    def test_the_page_describes_the_check_and_its_limits(self):
        page = PAGE.read_text(encoding="utf-8")
        self.assertIn("Check of the CI-built images", page)
        self.assertIn("tests/target/check_boot_images.sh", page)
        self.assertRegex(page, r"Called by `scripts/test-boot-composition\.sh`")
        self.assertRegex(page, r"approved by the owner on 2026-11-16")
        self.assertNotRegex(page, r"pending the owner's approval")
        # The section heading must not say that the approval is still needed (review of this change).
        self.assertNotRegex(page, r"(?im)^#+ .*needs the owner's approval")
        self.assertRegex(page, r"never run on a real build")


    def test_the_page_states_the_exit_codes_the_script_uses(self):
        page = PAGE.read_text(encoding="utf-8")
        self.assertIn("both refusing, fails (exit 1)", page)
        self.assertIn("key hash NOT compared with the key", page)
        self.assertIn("check_boot_images.tmp", page)
        self.assertIn("requirements", page)
        header = "\n".join(l for l in SCRIPT.read_text(encoding="utf-8").splitlines() if l.startswith("#"))
        self.assertIn("2 the build or a tool cannot be used", header)


class BehaviourTest(unittest.TestCase):
    """Run the script against a fake build tree and a fake imgtool."""

    @classmethod
    def setUpClass(cls):
        cls.image = helpers.build_image(key=FAKE_SPKI)
        cls.confirmed8 = confirmed_of(cls.image, 8, image_ok=1)
        cls.confirmed1 = confirmed_of(cls.image, 1, image_ok=1)
        cls.mcuboot_bin = bytes(range(256)) * 8

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        root = Path(self._dir.name)
        self.workspace = root / "workspace"
        self.tool_dir = self.workspace / "bootloader/mcuboot/scripts"
        self.tool_dir.mkdir(parents=True)
        (self.workspace / "bootloader/mcuboot/root-ec-p256.pem").write_text("FAKE KEY FILE\n")
        (self.tool_dir / "imgtool.py").write_text(FAKE_IMGTOOL)
        self.build = root / "build"
        self.app = self.build / "zephyr/zephyr"
        self.app.mkdir(parents=True)
        (self.build / "mcuboot/zephyr").mkdir(parents=True)
        self.set_images(self.image, self.confirmed8)
        self.set_fake("honest", good=[self.image], public=FAKE_SPKI)
        (self.app / "zephyr.bin").write_bytes(bytes(range(256)) * 6)
        (self.build / "mcuboot/zephyr/zephyr.bin").write_bytes(self.mcuboot_bin)

    def set_images(self, signed, confirmed):
        (self.app / "zephyr.signed.bin").write_bytes(signed)
        confirmed_path = self.app / "zephyr.signed.confirmed.bin"
        if confirmed is None:
            confirmed_path.unlink(missing_ok=True)
        else:
            confirmed_path.write_bytes(confirmed)

    def set_fake(self, mode, good=(), public=None):
        (self.tool_dir / "fake-mode.txt").write_text(mode)
        (self.tool_dir / "fake-good-sha256.txt").write_text(
            "\n".join(hashlib.sha256(g).hexdigest() for g in good) + "\n")
        pem = self.tool_dir / "fake-public.pem"
        if public is None:
            pem.unlink(missing_ok=True)
        else:
            pem.write_text(pem_of(public))

    def run_script(self, build=None, expect=None, python=None):
        done = subprocess.run(
            ["bash", str(SCRIPT), str(build if build is not None else self.build)],
            capture_output=True, text=True,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "CRUX_WORKSPACE": str(self.workspace),
                 "CRUX_PYTHON": python or sys.executable})
        if expect is not None:
            self.assertEqual(expect, done.returncode, f"stdout:\n{done.stdout}\nstderr:\n{done.stderr}")
        # Temporary copies are removed after a pass and after a failure.
        self.assertFalse((self.build / "check_boot_images.tmp").exists())
        return done

    # ---- passing ----

    def test_a_consistent_build_passes_and_prints_the_summary_and_the_alignment_survey(self):
        done = self.run_script(expect=0)
        for text in ("Boot image check passed", "signed image: TLV layout", "confirmed image: digest, trailer",
                     "MCUboot zephyr.bin: no image", "changed byte at 0x300", "changed byte at 0x500",
                     "RUNNING_CONFIRMED", "at --align 8", "alignment  1:", "alignment  8:",
                     "alignment 16:", "alignment 32:", "SubjectPublicKeyInfo", "signed image: key hash"):
            self.assertIn(text, done.stdout)
        self.assertRegex(done.stdout, r"signed image: key hash +ok ")
        self.assertNotIn("NOT compared", done.stdout)

    def test_a_confirmed_image_with_the_trailer_of_alignment_1_passes_and_names_it(self):
        self.set_images(self.image, self.confirmed1)
        done = self.run_script(expect=0)
        self.assertIn("at --align 1", done.stdout)

    def test_the_key_hash_of_the_uncompressed_point_is_also_accepted_and_named(self):
        image = helpers.build_image(key=FAKE_SPKI[-65:])
        self.set_images(image, confirmed_of(image, 8, image_ok=1))
        self.set_fake("honest", good=[image], public=FAKE_SPKI)
        done = self.run_script(expect=0)
        self.assertIn("uncompressed point", done.stdout)

    def test_without_a_derivable_public_key_the_check_passes_and_says_what_it_did_not_compare(self):
        # No fake public key, and the key file is not a key, so openssl cannot derive one either.
        self.set_fake("honest", good=[self.image], public=None)
        done = self.run_script(expect=0)
        # The row is info, not ok, so that an uncompared key hash does not look like a pass, and the
        # last line says it again.
        self.assertRegex(done.stdout, r"signed image: key hash +info .*NOT compared with the key")
        self.assertNotRegex(done.stdout, r"signed image: key hash +ok ")
        self.assertEqual("key hash NOT compared with the key", done.stdout.strip().splitlines()[-1])
        self.assertRegex(done.stdout, r"signed image: TLV layout +ok ")

    # ---- failing loudly ----

    def test_a_key_hash_that_is_not_the_hash_of_the_public_key_fails(self):
        self.set_fake("honest", good=[self.image], public=OTHER_SPKI)
        done = self.run_script(expect=1)
        self.assertIn("boot image check failed", done.stderr)
        self.assertIn("equals neither", done.stderr)

    def test_a_changed_signed_image_fails_because_neither_tool_accepts_it(self):
        changed = bytearray(self.image)
        changed[0x500] ^= 0xFF
        self.set_images(bytes(changed), self.confirmed8)
        done = self.run_script(expect=1)
        self.assertIn("neither the inspector nor imgtool accepts", done.stderr)
        self.assertIn("digest MISMATCH", done.stderr)
        self.assertIn("FAKE imgtool verify: Image is not valid", done.stderr)

    def test_an_inspector_that_reads_ok_where_imgtool_refuses_is_a_loud_disagreement(self):
        self.set_fake("refuse-all", public=FAKE_SPKI)
        done = self.run_script(expect=1)
        self.assertIn("the inspector and imgtool disagree", done.stderr)
        self.assertIn("--- inspector (exit 0) ---", done.stderr)
        self.assertIn("--- imgtool verify (exit 1) ---", done.stderr)
        self.assertIn("FAKE imgtool verify: Image is not valid", done.stderr)
        self.assertIn('"result": "digest ok"', done.stderr)

    def test_imgtool_accepting_what_the_inspector_rejects_is_a_loud_disagreement(self):
        changed = bytearray(self.image)
        changed[0x500] ^= 0xFF
        self.set_images(bytes(changed), self.confirmed8)
        self.set_fake("accept-all", public=FAKE_SPKI)
        done = self.run_script(expect=1)
        self.assertIn("the inspector and imgtool disagree", done.stderr)
        self.assertIn("--- imgtool verify (exit 0) ---", done.stderr)

    def test_imgtool_accepting_a_changed_copy_is_a_loud_disagreement_for_that_offset(self):
        # A tool that accepts every file passes the first check on the real signed image, and shows
        # itself at the changed copy, which the inspector reads as a digest mismatch.
        self.set_fake("accept-all", public=FAKE_SPKI)
        done = self.run_script(expect=1)
        self.assertIn("changed at 0x300", done.stderr)
        self.assertIn("imgtool", done.stderr)

    def test_a_crash_of_imgtool_is_not_a_refusal(self):
        self.set_fake("crash", public=FAKE_SPKI)
        done = self.run_script(expect=1)
        self.assertIn("imgtool crashed", done.stderr)

    def test_a_missing_confirmed_image_names_the_erratum(self):
        self.set_images(self.image, None)
        done = self.run_script(expect=1)
        self.assertIn("zephyr.signed.confirmed.bin", done.stderr)
        self.assertIn("v4.4.2", done.stderr)
        self.assertIn("docs/boot-update-investigation.md", done.stderr)

    def test_a_confirmed_image_that_is_not_the_slot_size_fails(self):
        self.set_images(self.image, self.confirmed8[:-4096])
        done = self.run_script(expect=1)
        self.assertIn("expected the slot size 3145728", done.stderr)

    def test_a_padded_image_without_the_trailer_magic_fails(self):
        self.set_images(self.image, self.image + b"\xff" * (SLOT_SIZE - len(self.image)))
        done = self.run_script(expect=1)
        self.assertIn("known trailer magic", done.stderr)

    def test_a_confirmed_image_with_a_changed_payload_fails(self):
        changed = bytearray(self.confirmed8)
        changed[0x500] ^= 0xFF
        self.set_images(self.image, bytes(changed))
        done = self.run_script(expect=1)
        self.assertIn("confirmed image", done.stderr)
        self.assertIn("digest", done.stderr)

    def test_flags_at_the_offsets_of_another_alignment_fail_with_the_survey(self):
        # The magic of alignment 8, but image_ok one byte-aligned slot below it (the offset an alignment
        # of 1 would use): no alignment gives a consistent decode that reads RUNNING_CONFIRMED.
        data = bytearray(confirmed_of(self.image, 8))
        data[SLOT_SIZE - 17] = 1
        self.set_images(self.image, bytes(data))
        done = self.run_script(expect=1)
        self.assertIn("RUNNING_CONFIRMED", done.stderr)
        self.assertIn("Alignment survey of the confirmed image", done.stderr)
        self.assertIn("alignment  1:", done.stderr)

    def test_an_mcuboot_image_that_starts_with_an_image_magic_fails(self):
        (self.build / "mcuboot/zephyr/zephyr.bin").write_bytes(self.image)
        done = self.run_script(expect=1)
        self.assertIn("image magic at the start of the MCUboot image", done.stderr)

    # ---- the fit of the images in the slot, and an oversized signing request ----

    def test_the_fit_rows_and_the_oversized_row_are_in_the_summary(self):
        done = self.run_script(expect=0)
        for text in ("fit: images in the slot", "oversized: inspector", "oversized: imgtool sign",
                     "misaligned layout"):
            self.assertIn(text, done.stdout)
        self.assertRegex(done.stdout, r"oversized: imgtool sign +ok ")
        self.assertRegex(done.stdout, r"misaligned layout +info ")

    def test_the_fit_check_uses_the_alignment_read_from_the_confirmed_image(self):
        self.set_images(self.image, self.confirmed1)
        done = self.run_script(expect=0)
        self.assertRegex(done.stdout, r"fit: images in the slot +ok .*alignment 1")

    def test_a_signing_tool_that_never_refuses_an_oversized_slot_fails(self):
        script = (self.tool_dir / "imgtool.py").read_text()
        (self.tool_dir / "imgtool.py").write_text(
            script.replace('mode != "accept-all" and slot < needed', 'False'))
        done = self.run_script(expect=1)
        self.assertIn("imgtool signed", done.stderr)
        self.assertIn("slot", done.stderr)

    def test_a_signing_tool_that_cannot_sign_the_control_is_a_missing_tool_not_a_verdict(self):
        script = (self.tool_dir / "imgtool.py").read_text()
        (self.tool_dir / "imgtool.py").write_text(
            script.replace('(mode != "accept-all" and slot < needed)', '(slot > 0)'))
        done = self.run_script(expect=2)
        self.assertIn("control", done.stderr)
        self.assertNotIn("Traceback", done.stderr)

    def test_a_crash_of_imgtool_sign_is_not_a_refusal(self):
        script = (self.tool_dir / "imgtool.py").read_text()
        (self.tool_dir / "imgtool.py").write_text(
            script.replace('if command == "sign":\n    if mode == "crash":',
                           'if command == "sign":\n    if True:'))
        done = self.run_script(expect=1)
        self.assertIn("imgtool crashed", done.stderr)

    def test_without_the_unsigned_binary_the_signing_check_is_reported_not_run(self):
        (self.app / "zephyr.bin").unlink()
        done = self.run_script(expect=0)
        self.assertRegex(done.stdout, r"oversized: imgtool sign +info +not run")
        # The inspector part does not need the unsigned binary.
        self.assertRegex(done.stdout, r"oversized: inspector +ok ")

    def test_the_unsigned_binary_is_taken_only_from_the_sysbuild_directory(self):
        (self.app / "deeper").mkdir()
        (self.app / "zephyr.bin").replace(self.app / "deeper/zephyr.bin")
        done = self.run_script(expect=0)
        self.assertRegex(done.stdout, r"oversized: imgtool sign +info +not run")

    # ---- missing inputs ----

    def test_a_missing_build_directory_exits_2_and_says_to_run_the_composition_check(self):
        done = self.run_script(build=self._dir.name + "/no-such-build", expect=2)
        self.assertIn("scripts/test-boot-composition.sh", done.stderr)
        self.assertIn("no-such-build", done.stderr)

    def test_a_missing_signed_image_exits_2(self):
        (self.app / "zephyr.signed.bin").unlink()
        done = self.run_script(expect=2)
        self.assertIn("scripts/test-boot-composition.sh", done.stderr)

    def test_a_missing_mcuboot_image_exits_2(self):
        (self.build / "mcuboot/zephyr/zephyr.bin").unlink()
        self.run_script(expect=2)

    def test_a_missing_imgtool_exits_2(self):
        (self.tool_dir / "imgtool.py").unlink()
        done = self.run_script(expect=2)
        self.assertIn("imgtool", done.stderr)

    def test_a_missing_python_exits_2(self):
        done = self.run_script(python="/no/such/python", expect=2)
        self.assertIn("python", done.stderr)
        self.assertIn("scripts/test-boot-composition.sh", done.stderr)

    def test_imgtool_without_its_requirements_exits_2_and_names_them(self):
        self.set_fake("no-requirements", public=FAKE_SPKI)
        done = self.run_script(expect=2)
        self.assertIn("requirements", done.stderr)
        self.assertIn("scripts/test-boot-composition.sh", done.stderr)

    def test_a_missing_build_directory_creates_nothing_and_does_not_crash(self):
        # Sharpens the exit 2 case above: the script only reads, so a missing directory stays missing,
        # and the message is the script's, not a traceback.
        done = self.run_script(build=self._dir.name + "/no-such-build", expect=2)
        self.assertFalse((Path(self._dir.name) / "no-such-build").exists())
        self.assertNotIn("Traceback", done.stderr)

    # ---- where the images are looked for ----

    def test_a_stray_signed_image_deeper_in_the_tree_is_not_picked_up(self):
        # A changed copy in a subdirectory would fail if the script took it; the file of the sysbuild
        # layout is the one that counts.
        deeper = self.app / "deeper"
        deeper.mkdir()
        changed = bytearray(self.image)
        changed[0x500] ^= 0xFF
        (deeper / "zephyr.signed.bin").write_bytes(bytes(changed))
        (deeper / "zephyr.signed.confirmed.bin").write_bytes(b"not an image")
        self.run_script(expect=0)

    def test_a_signed_image_only_deeper_in_the_tree_counts_as_missing(self):
        (self.app / "deeper").mkdir()
        (self.app / "zephyr.signed.bin").replace(self.app / "deeper/zephyr.signed.bin")
        done = self.run_script(expect=2)
        self.assertIn("no zephyr.signed.bin", done.stderr)

    def test_a_confirmed_image_only_deeper_in_the_tree_counts_as_missing(self):
        (self.app / "deeper").mkdir()
        (self.app / "zephyr.signed.confirmed.bin").replace(self.app / "deeper/zephyr.signed.confirmed.bin")
        done = self.run_script(expect=1)
        self.assertIn("v4.4.2", done.stderr)


if __name__ == "__main__":
    unittest.main()
