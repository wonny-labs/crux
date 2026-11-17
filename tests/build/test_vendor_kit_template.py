"""Check the kit module template and the vendor kit guide.

The hash tool tests need only Python. The CMake tests run the template's CMake function in
CMake script mode (`cmake -P`), with a throwaway kit tree, and skip when cmake is missing.
Nothing here builds with Zephyr, and no real vendor kit is used.
"""
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "templates/kit-module"
TOOL = TEMPLATE / "kit_hashes.py"
CMAKE_SNIPPET = TEMPLATE / "kit_integrity.cmake"
GUIDE = REPO / "docs/vendor-kits.md"
RELEASE = REPO / "templates/product/RELEASE.md"
CMAKE = shutil.which("cmake")
SHASUM = shutil.which("sha256sum") or shutil.which("shasum")

# Names that a neutral public sample must not carry: the list of test_product_template.py.
FORBIDDEN_NAMES = (
    "codesys", "wolfssl", "wolfssh", "nxp", "mcuxpresso", "datalight", "reliance",
    "crux-controller", "crux-codesys", "bitbucket", "employer",
)


def load_tool():
    spec = importlib.util.spec_from_file_location("kit_hashes", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def make_kit(root):
    """A small invented kit tree with a nested directory, a space in a name and a .git folder."""
    write(root / "include/kit.h", b"#define KIT_VERSION 0x010100\n")
    write(root / "src/a.c", b"int a;\n")
    write(root / "src/b b.c", b"int b;\n")
    write(root / "Zed.txt", b"upper case sorts first in C order\n")
    write(root / ".git/HEAD", b"ref: refs/heads/work-1.x\n")
    return root


def expected_list(root):
    lines = []
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts[:1]):
        rel = path.relative_to(root).as_posix()
        lines.append((("./" + rel).encode(), hashlib.sha256(path.read_bytes()).hexdigest()))
    lines.sort()
    return "".join(f"{digest}  {name.decode()}\n" for name, digest in lines)


class HashToolTest(unittest.TestCase):
    """The reference tool that writes and checks per-delivery hash lists."""

    def setUp(self):
        self.tool = load_tool()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.kit = make_kit(self.tmp / "kit")
        self.lists = self.tmp / "kit-hashes"

    def run_tool(self, *args):
        return subprocess.run([sys.executable, str(TOOL), *map(str, args)],
                              capture_output=True, text=True)

    def commit_list(self, line, name, text=None):
        path = self.lists / line / f"{name}.sha256"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if text is not None else self.tool.hash_list(self.kit))
        return path

    def test_the_list_is_sha256sum_format_sorted_by_path_bytes_without_git(self):
        text = self.tool.hash_list(self.kit)
        self.assertEqual(expected_list(self.kit), text)
        names = [line.split("  ", 1)[1] for line in text.splitlines()]
        self.assertEqual("./Zed.txt", names[0], "C byte order puts upper case first")
        self.assertNotIn("./.git/HEAD", names)

    @unittest.skipUnless(SHASUM and shutil.which("find") and shutil.which("sort"), "needs find, sort and a sha256 tool")
    def test_the_list_equals_the_shell_pipeline_of_the_composition_guide(self):
        tool = [SHASUM] if SHASUM.endswith("sha256sum") else [SHASUM, "-a", "256"]
        shell = subprocess.run(
            ["sh", "-c", 'find . -path ./.git -prune -o -type f -exec "$@" {} + | LC_ALL=C sort -k 2', "sh", *tool],
            cwd=self.kit, capture_output=True, text=True, check=True).stdout
        self.assertEqual(shell, self.tool.hash_list(self.kit))

    def test_the_digest_is_the_sha256_of_the_list_bytes(self):
        path = self.commit_list("1.x", "1.1.0")
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), self.tool.digest_of(path))

    def test_generate_prints_the_list(self):
        result = self.run_tool("generate", self.kit)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(self.tool.hash_list(self.kit), result.stdout)

    def test_check_names_the_line_the_delivery_and_the_digest_it_matched(self):
        self.commit_list("1.x", "1.0.0", "0" * 64 + "  ./other\n")
        path = self.commit_list("1.x", "1.1.0")
        result = self.run_tool("check", self.kit, "--lists", self.lists)
        self.assertEqual(0, result.returncode, result.stderr)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(f"MATCH line=1.x delivery=1.1.0 digest={digest}\n", result.stdout)

    def test_check_matches_a_released_working_state_by_its_own_list(self):
        self.commit_list("1.x", "1.1.0", "0" * 64 + "  ./other\n")
        self.commit_list("1.x", "1.1.0-acme1")
        result = self.run_tool("check", self.kit, "--lists", self.lists)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("line=1.x delivery=1.1.0-acme1 ", result.stdout)

    def test_check_reports_an_unknown_delivery_with_its_own_digest_and_exit_1(self):
        self.commit_list("1.x", "1.0.0", "0" * 64 + "  ./other\n")
        result = self.run_tool("check", self.kit, "--lists", self.lists)
        self.assertEqual(1, result.returncode)
        digest = hashlib.sha256(self.tool.hash_list(self.kit).encode()).hexdigest()
        self.assertEqual(f"UNKNOWN digest={digest}\n", result.stdout)

    def test_one_changed_byte_is_an_unknown_delivery(self):
        self.commit_list("1.x", "1.1.0")
        write(self.kit / "src/a.c", b"int a;;\n")
        self.assertEqual(1, self.run_tool("check", self.kit, "--lists", self.lists).returncode)

    def test_an_added_or_removed_file_is_an_unknown_delivery(self):
        self.commit_list("1.x", "1.1.0")
        write(self.kit / "src/extra.c", b"\n")
        self.assertEqual(1, self.run_tool("check", self.kit, "--lists", self.lists).returncode)
        (self.kit / "src/extra.c").unlink()
        (self.kit / "src/a.c").unlink()
        self.assertEqual(1, self.run_tool("check", self.kit, "--lists", self.lists).returncode)

    def test_a_renamed_file_is_an_unknown_delivery(self):
        self.commit_list("1.x", "1.1.0")
        (self.kit / "src/a.c").rename(self.kit / "src/c.c")
        self.assertEqual(1, self.run_tool("check", self.kit, "--lists", self.lists).returncode)

    def test_the_expected_line_must_match(self):
        self.commit_list("1.x", "1.1.0")
        ok = self.run_tool("check", self.kit, "--lists", self.lists, "--expect-line", "1.x")
        self.assertEqual(0, ok.returncode, ok.stderr)
        wrong = self.run_tool("check", self.kit, "--lists", self.lists, "--expect-line", "2.x")
        self.assertEqual(2, wrong.returncode)
        self.assertIn("expected line 2.x", wrong.stderr)

    def test_two_lists_with_the_same_content_are_an_error(self):
        self.commit_list("1.x", "1.1.0")
        self.commit_list("2.x", "2.0.0")
        result = self.run_tool("check", self.kit, "--lists", self.lists)
        self.assertEqual(2, result.returncode)
        self.assertIn("more than one", result.stderr)

    @unittest.skipUnless(hasattr(os, "symlink"), "needs symbolic links")
    def test_a_symbolic_link_in_the_kit_is_refused(self):
        os.symlink("a.c", self.kit / "src/link.c")
        result = self.run_tool("generate", self.kit)
        self.assertEqual(2, result.returncode)
        self.assertIn("symbolic link", result.stderr)

    def test_a_newline_in_a_file_name_is_refused(self):
        try:
            write(self.kit / "bad\nname", b"")
        except OSError:
            self.skipTest("the file system refuses the name")
        result = self.run_tool("generate", self.kit)
        self.assertEqual(2, result.returncode)
        self.assertIn("newline", result.stderr)

    def test_a_missing_kit_or_list_folder_is_an_error(self):
        self.assertEqual(2, self.run_tool("generate", self.tmp / "missing").returncode)
        self.assertEqual(2, self.run_tool("check", self.kit, "--lists", self.tmp / "missing").returncode)

    def test_a_list_name_outside_line_and_delivery_is_ignored_only_if_not_sha256(self):
        self.commit_list("1.x", "1.1.0")
        (self.lists / "README.txt").write_text("notes\n")
        self.assertEqual(0, self.run_tool("check", self.kit, "--lists", self.lists).returncode)
        stray = self.lists / "stray.sha256"
        stray.write_text(self.tool.hash_list(self.kit))
        result = self.run_tool("check", self.kit, "--lists", self.lists)
        self.assertEqual(2, result.returncode)
        self.assertIn("<line>/<delivery>.sha256", result.stderr)


@unittest.skipUnless(CMAKE, "cmake is required for the CMake function tests")
class CMakeFunctionTest(unittest.TestCase):
    """The CMake function a kit module calls at configure time, run in script mode."""

    def setUp(self):
        self.tool = load_tool()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.kit = make_kit(self.tmp / "modules/kit-a")
        self.other = make_kit(self.tmp / "local/kit-a")
        write(self.other / "src/a.c", b"int a_local;\n")
        self.lists = self.tmp / "kit-hashes"
        path = self.lists / "1.x/1.1.0.sha256"
        path.parent.mkdir(parents=True)
        path.write_text(self.tool.hash_list(self.kit))
        self.digest = hashlib.sha256(path.read_bytes()).hexdigest()

    def configure(self, *defines, env=None, extra_args=""):
        script = self.tmp / "configure.cmake"
        script.write_text(
            f'include("{CMAKE_SNIPPET.as_posix()}")\n'
            f'kit_integrity_check(NAME kit-a ENV_VAR KIT_A_PATH\n'
            f'  DEFAULT_PATH "{self.kit.as_posix()}" HASH_DIR "{self.lists.as_posix()}" {extra_args})\n'
            'message(STATUS "RESULT ${KIT_INTEGRITY_LINE}|${KIT_INTEGRITY_DELIVERY}|'
            '${KIT_INTEGRITY_DIGEST}|${KIT_INTEGRITY_PATH}|${KIT_INTEGRITY_SOURCE}")\n')
        environment = {k: v for k, v in os.environ.items()
                       if k not in ("KIT_A_PATH", "EXTRA_ZEPHYR_MODULES", "ZEPHYR_EXTRA_MODULES")}
        environment.update(env or {})
        args = [CMAKE, f"-DPYTHON_EXECUTABLE={sys.executable}", *defines, "-P", str(script)]
        result = subprocess.run(args, capture_output=True, text=True, env=environment)
        return result, result.stdout + result.stderr

    def test_a_known_delivery_on_the_default_path_is_named_in_the_output(self):
        result, out = self.configure()
        self.assertEqual(0, result.returncode, out)
        self.assertIn(f"kit-a: line 1.x, delivery 1.1.0, hash list {self.digest}", out)
        self.assertIn(f"RESULT 1.x|1.1.0|{self.digest}|{self.kit.as_posix()}|west project", out)

    def test_a_known_delivery_in_a_release_build_passes(self):
        result, out = self.configure("-DPRODUCT_RELEASE_BUILD=ON")
        self.assertEqual(0, result.returncode, out)
        self.assertIn("delivery 1.1.0", out)

    def test_an_unknown_delivery_warns_in_development(self):
        write(self.kit / "src/a.c", b"changed\n")
        result, out = self.configure()
        self.assertEqual(0, result.returncode, out)
        self.assertIn("CMake Warning", out)
        self.assertIn("kit-a: unknown delivery", out)
        self.assertIn("RESULT |unknown|", out)

    def test_an_unknown_delivery_fails_a_release_build(self):
        write(self.kit / "src/a.c", b"changed\n")
        result, out = self.configure("-DPRODUCT_RELEASE_BUILD=ON")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("kit-a: unknown delivery", out)

    def test_an_unknown_delivery_fails_when_the_module_requires_a_known_one(self):
        write(self.kit / "src/a.c", b"changed\n")
        result, out = self.configure("-DKIT_REQUIRE_KNOWN_DELIVERY=ON")
        self.assertNotEqual(0, result.returncode, out)

    def test_the_environment_override_is_recorded_in_development(self):
        result, out = self.configure(env={"KIT_A_PATH": str(self.other)})
        self.assertEqual(0, result.returncode, out)
        self.assertIn("CMake Warning", out)
        self.assertIn(f"kit-a: KIT_A_PATH={self.other.as_posix()} replaces", out)
        self.assertIn("development only", out)
        self.assertIn(f"|{self.other.as_posix()}|environment KIT_A_PATH", out)

    def test_the_environment_override_is_refused_in_a_release_build(self):
        result, out = self.configure("-DPRODUCT_RELEASE_BUILD=ON", env={"KIT_A_PATH": str(self.kit)})
        self.assertNotEqual(0, result.returncode)
        self.assertIn("KIT_A_PATH is set", out)
        self.assertIn("release build", out)

    def test_extra_zephyr_modules_are_refused_in_a_release_build(self):
        for name in ("EXTRA_ZEPHYR_MODULES", "ZEPHYR_EXTRA_MODULES"):
            with self.subTest(source="environment", name=name):
                result, out = self.configure("-DPRODUCT_RELEASE_BUILD=ON", env={name: str(self.other)})
                self.assertNotEqual(0, result.returncode)
                self.assertIn(name, out)
            with self.subTest(source="cmake", name=name):
                result, out = self.configure("-DPRODUCT_RELEASE_BUILD=ON", f"-D{name}={self.other}")
                self.assertNotEqual(0, result.returncode)
                self.assertIn(name, out)

    def test_the_expected_line_must_match(self):
        result, out = self.configure(extra_args="EXPECT_LINE 1.x")
        self.assertEqual(0, result.returncode, out)
        result, out = self.configure(extra_args="EXPECT_LINE 2.x")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("expected line 2.x", out)

    def test_a_missing_kit_is_an_error_in_every_build(self):
        shutil.rmtree(self.kit)
        result, out = self.configure()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("kit-a: no kit at", out)


class GuideTest(unittest.TestCase):
    """The guide page, its links and the release record fields."""

    def setUp(self):
        self.text = GUIDE.read_text()

    def test_the_guide_is_linked_from_the_pages_that_lead_to_it(self):
        for path in ("docs/README.md", "docs/product-composition.md",
                     "docs/shared-hardware-modules.md", "templates/product/README.md"):
            with self.subTest(path=path):
                self.assertIn("vendor-kits.md", (REPO / path).read_text())

    def test_the_guide_links_existing_sections_of_the_composition_guide(self):
        headings = re.findall(r"(?m)^#+ (.+)$", (REPO / "docs/product-composition.md").read_text())
        anchors = {re.sub(r"[^a-z0-9 -]", "", h.lower()).replace(" ", "-") for h in headings}
        cited = re.findall(r"product-composition\.md#([a-z0-9-]+)", self.text)
        self.assertTrue(cited)
        for anchor in cited:
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, anchors)

    def test_the_guide_covers_each_topic(self):
        for phrase in ("vendor-1.x", "work-1.x", "vendor-2.x", "work-2.x", "vendor/<delivery>",
                       "work/<delivery>-<org><n>", "kit-hashes/<line>/<delivery>.sha256",
                       "PRODUCT_RELEASE_BUILD", "KIT_A_PATH", "EXTRA_ZEPHYR_MODULES",
                       "Upstream-Status", "group-filter", "Where this follows or differs from common practice",
                       "Experimental"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_the_guide_names_the_template_files_and_commands(self):
        for phrase in ("templates/kit-module/", "kit_hashes.py generate", "kit_hashes.py check",
                       "kit_integrity_check("):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_the_release_record_has_the_kit_fields(self):
        text = RELEASE.read_text()
        self.assertRegex(text, r"(?m)^## Vendor kits")
        for column in ("Kit line", "Delivery tag", "Work tag", "Commit SHA", "Hash list digest"):
            with self.subTest(column=column):
                self.assertIn(column, text)
        self.assertIn("sources held outside Git", text)

    def test_no_new_file_carries_a_private_name(self):
        paths = [GUIDE, RELEASE, *sorted(p for p in TEMPLATE.rglob("*") if p.is_file())]
        for path in paths:
            text = path.read_text().lower()
            for name in FORBIDDEN_NAMES:
                with self.subTest(path=path.name, name=name):
                    self.assertNotIn(name, text)


if __name__ == "__main__":
    unittest.main()
