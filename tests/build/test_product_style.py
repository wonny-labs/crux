"""Product style kit: the files and wrappers under templates/product/style, and the guidance that names them.

Everything here runs on the Host with Python, Git, Bash and Perl. Tests that need a real clang-format
or a real Zephyr checkpatch skip when the tool is absent: set CLANG_FORMAT, or ZEPHYR_BASE to a
Zephyr tree, to run them. Nothing here uses west, Docker or hardware.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "templates/product"
STYLE = TEMPLATE / "style"
GUIDELINES = REPO / "docs/coding-guidelines.md"
CHOOSING = REPO / "docs/choosing-an-api.md"
BUILD = REPO / "docs/build.md"
TESTS_README = REPO / "tests/README.md"
BASH = shutil.which("bash")
GIT = shutil.which("git")
PERL = shutil.which("perl")

GUIDELINE_HEADING = "## Zephyr and driver code in a product repository"
HARDWARE_HEADING = "### Hardware integration tests"
COMPLIANCE_CHECKS = [
    "Checkpatch", "ClangFormat", "DevicetreeBindings", "DevicetreeLinting", "BoardYml",
    "YAMLLint", "Gitlint", "Nits", "KeepSorted", "CMakeStyle", "LicenseAndCopyrightCheck",
    "DeviceAPI", "DeviceMmioCheck", "Kconfig",
]
PRODUCT_ROOT_PLACEHOLDER = "<PRODUCT_ROOT>"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def run(cmd, cwd, env=None, check=False):
    merged = dict(os.environ)
    merged.update(GIT_ENV)
    merged.pop("ZEPHYR_BASE", None)
    merged.update(env or {})
    return subprocess.run([str(part) for part in cmd], cwd=cwd, env=merged, text=True,
                          capture_output=True, check=check)


def git(cwd, *args):
    return run([GIT, *args], cwd, check=True).stdout.strip()


def make_repo(root, files):
    """Create a Git repository holding files (path -> text) in one commit, and return its root."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", ".")
    write_files(root, files)
    git(root, "add", "-A")
    git(root, "commit", "-q", "--allow-empty", "-m", "base")
    return root


def write_files(root, files):
    for name, text in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def section(path, heading):
    """Return one section of a Markdown file, from its heading to the next heading at that level or above."""
    level = len(heading.split(" ")[0])
    kept = None
    fenced = False
    for line in path.read_text().splitlines():
        if line.startswith("```") or line.startswith("~~~"):
            fenced = not fenced
        hashes = None if fenced else re.match(r"#+ ", line)
        if kept is None:
            kept = [line] if line == heading else None
        elif hashes and len(hashes.group().strip()) <= level:
            break
        else:
            kept.append(line)
    if kept is None:
        raise AssertionError(f"{path.name} has no heading {heading!r}")
    return "\n".join(kept)


def slug(heading):
    """The anchor that GitHub makes of a heading."""
    text = re.sub(r"[`*]", "", heading.lstrip("#").strip()).lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path):
    found = set()
    fenced = False
    for line in path.read_text().splitlines():
        if line.startswith("```") or line.startswith("~~~"):
            fenced = not fenced
        elif not fenced and re.match(r"#+ ", line):
            found.add(slug(line))
    return found


def broken_local_links(path, text):
    """Return the relative links in text whose file or anchor does not exist, as the docs link check reads them."""
    broken = []
    for target in re.findall(r"\]\(([^)\s]+)\)", text):
        if re.match(r"[a-z][a-z0-9+.-]*:", target):
            continue
        name, _, fragment = target.partition("#")
        resolved = (path.parent / name).resolve() if name else path
        if not resolved.exists():
            broken.append(target)
        elif fragment and resolved.suffix == ".md" and fragment not in anchors(resolved):
            broken.append(target)
    return broken


def zephyr_tree():
    """Return a Zephyr tree for the tests that read Zephyr's own documents, or None."""
    for candidate in (os.environ.get("ZEPHYR_BASE"), REPO.parent / "zephyr"):
        if candidate and (Path(candidate) / "doc/contribute/style/code.rst").is_file():
            return Path(candidate)
    return None


def clang_format():
    configured = os.environ.get("CLANG_FORMAT")
    if configured and (Path(configured).is_file() or shutil.which(configured)):
        return configured
    return shutil.which("clang-format-18")


def settings(path):
    """Return the lines of a configuration file that are not comments or blank."""
    return [line.rstrip() for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def stub(directory, name, body):
    path = Path(directory) / name
    path.write_text(body)
    path.chmod(0o755)
    return path


@unittest.skipUnless(BASH and GIT, "needs bash and git")
class StyleFilesTest(unittest.TestCase):
    def test_the_kit_has_its_files(self):
        for name in (".clang-format", ".clang-tidy", "check-format.sh", "check-patch.sh",
                     "check-includes.sh", "README.md"):
            self.assertTrue((STYLE / name).is_file(), name)

    def test_the_wrappers_are_executable_strict_bash(self):
        for name in ("check-format.sh", "check-patch.sh", "check-includes.sh"):
            path = STYLE / name
            self.assertTrue(os.access(path, os.X_OK), f"{name} is not executable")
            text = path.read_text()
            self.assertTrue(text.startswith("#!/usr/bin/env bash\n"), name)
            self.assertIn("set -euo pipefail", text, name)

    def test_each_wrapper_answers_help_without_touching_anything(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("check-format.sh", "check-patch.sh", "check-includes.sh"):
                for option in ("--help", "-h"):
                    result = run([BASH, STYLE / name, option], cwd=directory)
                    self.assertEqual(0, result.returncode, (name, option, result.stderr))
                    self.assertIn("Usage:", result.stdout, name)
            self.assertEqual([], list(Path(directory).iterdir()))

    def test_the_format_settings_equal_cruxs_so_the_template_sources_conform(self):
        self.assertEqual(settings(REPO / ".clang-format"), settings(STYLE / ".clang-format"))

    def test_the_tidy_selection_equals_cruxs_and_the_header_filter_names_product_directories(self):
        def block(path, key):
            text = path.read_text()
            match = re.search(rf"^{key}:\s*>-?\n((?:[ \t]+.*\n)+)", text, re.MULTILINE)
            self.assertIsNotNone(match, f"{path} has no {key}")
            return "".join(match.group(1).split())

        self.assertEqual(block(REPO / ".clang-tidy", "Checks"), block(STYLE / ".clang-tidy", "Checks"))
        product = (STYLE / ".clang-tidy").read_text()
        header_filter = re.search(r"^HeaderFilterRegex:\s*'(.*)'", product, re.MULTILINE)
        self.assertIsNotNone(header_filter)
        self.assertNotIn("components", header_filter.group(1))
        for directory in ("app", "domain", "drivers", "tests"):
            self.assertIn(directory, header_filter.group(1))
        self.assertIn("WarningsAsErrors", product)

    def header_filter(self):
        product = (STYLE / ".clang-tidy").read_text()
        return re.search(r"^HeaderFilterRegex:\s*'(.*)'", product, re.MULTILINE).group(1)

    def test_the_header_filter_is_anchored_to_a_marked_product_root_placeholder(self):
        pattern = self.header_filter()
        self.assertTrue(pattern.startswith("^" + PRODUCT_ROOT_PLACEHOLDER + "/"), pattern)
        comment = "\n".join(line for line in (STYLE / ".clang-tidy").read_text().splitlines()
                            if line.startswith("#"))
        self.assertIn(PRODUCT_ROOT_PLACEHOLDER, comment)
        self.assertIn("absolute path", comment)

    def test_the_header_filter_matches_product_headers_and_no_zephyr_crux_or_build_header(self):
        # clang-tidy searches the header's full path with the regex (llvm::Regex::match), as re.search does.
        root = "/ws/product"
        effective = re.compile(self.header_filter().replace(PRODUCT_ROOT_PLACEHOLDER, re.escape(root)))
        for path in ("/ws/product/app/src/main.h", "/ws/product/drivers/sensor/x.h",
                     "/ws/product/domain/product_port.h", "/ws/product/include/product/api.h",
                     "/ws/product/tests/unit/fake.h"):
            self.assertIsNotNone(effective.search(path), path)
        for path in ("/ws/zephyr/include/zephyr/kernel.h", "/ws/build/zephyr/include/generated/x.h",
                     "/ws/crux-pilot/components/gpio/include/crux/gpio.h",
                     "/ws/zephyr/drivers/sensor/bme280/bme280.h", "/ws/zephyr/tests/lib/x.h",
                     "/ws/product/build/zephyr/include/generated/autoconf.h",
                     "/ws/product/modules/vendor/include/x.h", "/ws/other/product/app/x.h"):
            self.assertIsNone(effective.search(path), path)

    def test_an_unedited_placeholder_reports_no_header_at_all(self):
        unedited = re.compile(self.header_filter())
        for path in ("/ws/zephyr/include/zephyr/kernel.h", "/ws/product/app/src/main.h"):
            self.assertIsNone(unedited.search(path), path)

    def test_the_kit_files_carry_an_spdx_line(self):
        for name in (".clang-format", ".clang-tidy", "check-format.sh", "check-patch.sh", "check-includes.sh"):
            head = (STYLE / name).read_text().splitlines()[:3]
            self.assertIn("# SPDX-License-Identifier: Apache-2.0", head, name)

    def test_the_checkpatch_wrapper_runs_zephyrs_tool_and_does_not_copy_it(self):
        self.assertEqual([], [path for path in TEMPLATE.rglob("*") if path.name == "checkpatch.pl"])
        text = (STYLE / "check-patch.sh").read_text()
        self.assertIn('"$ZEPHYR_BASE/scripts/checkpatch.pl"', text)
        for path in TEMPLATE.rglob("*"):
            if path.is_file():
                self.assertNotIn("GNU General Public License", path.read_text(errors="ignore"), path)

    def test_the_readme_lists_every_file_of_the_kit(self):
        text = (STYLE / "README.md").read_text()
        for name in (".clang-format", ".clang-tidy", "check-format.sh", "check-patch.sh",
                     "check-includes.sh"):
            self.assertIn(name, text)
        self.assertEqual([], broken_local_links(STYLE / "README.md", text))


@unittest.skipUnless(BASH and GIT, "needs bash and git")
class FormatWrapperTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.tmp = Path(self.directory.name)
        self.log = self.tmp / "formatter-args.txt"
        self.formatter = stub(self.tmp, "fake-clang-format", f'#!/usr/bin/env bash\nprintf \'%s\\n\' "$@" > "{self.log}"\n')

    def product(self, files, name="product"):
        return make_repo(self.tmp / name, files)

    def call(self, cwd, env=None):
        return run([BASH, STYLE / "check-format.sh"], cwd=cwd, env={"CLANG_FORMAT": self.formatter, **(env or {})})

    def test_it_formats_the_c_and_c_plus_plus_files_of_the_git_top_level_from_a_subdirectory(self):
        root = self.product({"app/src/a.c": "int a;\n", "app/inc/b.h": "int b;\n", "x/y.cpp": "int c;\n",
                             "x/y.hpp": "int d;\n", "notes.txt": "text\n", ".clang-format": "BasedOnStyle: LLVM\n"})
        write_files(root, {"app/new.c": "int e;\n"})  # untracked and not ignored: also checked
        (root / "app/src/a.c").unlink()  # tracked and deleted: skipped
        result = self.call(root / "app/src")
        self.assertEqual(0, result.returncode, result.stderr)
        args = self.log.read_text().splitlines()
        self.assertEqual(["--dry-run", "--Werror"], args[:2])
        files = sorted(Path(arg).resolve().relative_to(root.resolve()).as_posix() for arg in args[2:])
        self.assertEqual(["app/inc/b.h", "app/new.c", "x/y.cpp", "x/y.hpp"], files)

    def test_the_products_own_style_file_is_what_clang_format_finds_by_itself(self):
        root = self.product({"a.c": "int a;\n", ".clang-format": "BasedOnStyle: LLVM\n"})
        self.assertEqual(0, self.call(root).returncode)
        self.assertFalse([arg for arg in self.log.read_text().splitlines() if arg.startswith("--style")])

    def test_without_a_style_file_in_the_product_it_uses_the_copy_beside_the_script(self):
        root = self.product({"a.c": "int a;\n"})
        self.assertEqual(0, self.call(root).returncode)
        style = [arg for arg in self.log.read_text().splitlines() if arg.startswith("--style")]
        self.assertEqual([f"--style=file:{STYLE / '.clang-format'}"], style)

    def test_without_a_root_style_file_the_kit_copy_also_overrides_a_nested_one(self):
        # clang-format applies --style=file:PATH to every file, so a driver's own .clang-format counts only
        # once the product root has its copy. The README and the kit's .clang-format say so.
        root = self.product({"drivers/up/a.c": "int a;\n", "drivers/up/.clang-format": "UseTab: Always\n"})
        self.assertEqual(0, self.call(root).returncode)
        style = [arg for arg in self.log.read_text().splitlines() if arg.startswith("--style")]
        self.assertEqual([f"--style=file:{STYLE / '.clang-format'}"], style)
        for path in (STYLE / "README.md", STYLE / ".clang-format"):
            text = " ".join(path.read_text().split())
            self.assertIn("only once the copy is at the product root", text, path.name)

    def test_a_repository_without_c_files_passes_and_runs_nothing(self):
        root = self.product({"notes.txt": "text\n"})
        result = self.call(root)
        self.assertEqual(0, result.returncode)
        self.assertIn("No C/C++ files", result.stdout)
        self.assertFalse(self.log.exists())

    def test_a_formatter_failure_fails_the_wrapper(self):
        failing = stub(self.tmp, "failing-clang-format", "#!/usr/bin/env bash\nexit 1\n")
        root = self.product({"a.c": "int a;\n"})
        result = run([BASH, STYLE / "check-format.sh"], cwd=root, env={"CLANG_FORMAT": failing})
        self.assertEqual(1, result.returncode)

    def test_a_missing_formatter_is_a_usage_error_that_names_the_variable(self):
        root = self.product({"a.c": "int a;\n"})
        result = self.call(root, env={"CLANG_FORMAT": self.tmp / "absent"})
        self.assertEqual(2, result.returncode)
        self.assertIn("CLANG_FORMAT", result.stderr)

    @unittest.skipUnless(clang_format(), "needs clang-format 18: set CLANG_FORMAT")
    def test_with_the_real_formatter_conforming_code_passes_and_other_code_fails(self):
        good = "int main(void)\n{\n    return 0;\n}\n"
        bad = "int main(void) {\n  return 0;\n}\n"
        root = self.product({"src/main.c": good})
        env = {"CLANG_FORMAT": clang_format()}
        self.assertEqual(0, run([BASH, STYLE / "check-format.sh"], cwd=root, env=env).returncode)
        write_files(root, {"src/main.c": bad})
        self.assertNotEqual(0, run([BASH, STYLE / "check-format.sh"], cwd=root, env=env).returncode)

    @unittest.skipUnless(clang_format(), "needs clang-format 18: set CLANG_FORMAT")
    def test_with_the_real_formatter_the_template_sources_conform_to_the_kit(self):
        root = self.product({}, name="copy")
        shutil.copytree(TEMPLATE, root / "template", ignore=shutil.ignore_patterns("build", ".git"))
        git(root, "add", "-A")
        result = run([BASH, STYLE / "check-format.sh"], cwd=root, env={"CLANG_FORMAT": clang_format()})
        self.assertEqual(0, result.returncode, result.stderr)


@unittest.skipUnless(BASH and GIT and PERL, "needs bash, git and perl")
class PatchWrapperTest(unittest.TestCase):
    FAKE_CHECKPATCH = (
        "#!/usr/bin/env perl\n"
        "use strict; use warnings; use Cwd;\n"
        "my $log = $ENV{FAKE_CHECKPATCH_LOG};\n"
        "open(my $out, '>', $log) or die; print $out \"$_\\n\" for @ARGV; print $out 'cwd=' . getcwd() . \"\\n\"; close $out;\n"
        "open($out, '>', \"$log.stdin\") or die; print $out $_ while (<STDIN>); close $out;\n"
        "exit($ENV{FAKE_CHECKPATCH_EXIT} // 0);\n"
    )

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.tmp = Path(self.directory.name)
        self.zephyr = self.tmp / "zephyr"
        (self.zephyr / "scripts").mkdir(parents=True)
        stub(self.zephyr / "scripts", "checkpatch.pl", self.FAKE_CHECKPATCH)
        self.log = self.tmp / "checkpatch.log"
        self.root = make_repo(self.tmp / "product", {"README.md": "x\n", "src/a.c": "int a(void);\n"})
        git(self.root, "rev-parse", "HEAD")

    def commit_change(self, files):
        write_files(self.root, files)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "change")

    def call(self, *args, cwd=None, env=None):
        merged = {"ZEPHYR_BASE": self.zephyr, "FAKE_CHECKPATCH_LOG": self.log}
        merged.update(env or {})
        return run([BASH, STYLE / "check-patch.sh", *args], cwd=cwd or self.root, env=merged)

    def test_it_needs_zephyr_base_with_checkpatch(self):
        result = run([BASH, STYLE / "check-patch.sh"], cwd=self.root)
        self.assertEqual(2, result.returncode)
        self.assertIn("ZEPHYR_BASE", result.stderr)
        result = self.call(env={"ZEPHYR_BASE": self.tmp})
        self.assertEqual(2, result.returncode)
        self.assertIn("checkpatch.pl", result.stderr)

    def test_a_missing_commit_is_a_usage_error(self):
        result = self.call("no-such-base")
        self.assertEqual(2, result.returncode)
        self.assertIn("no-such-base", result.stderr)

    def test_more_than_two_arguments_is_a_usage_error(self):
        self.assertEqual(2, self.call("a", "b", "c").returncode)

    def test_a_range_without_c_changes_runs_nothing(self):
        self.commit_change({"README.md": "y\n"})
        result = self.call()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("No changed C", result.stdout)
        self.assertFalse(self.log.exists())

    def test_it_runs_zephyrs_checkpatch_from_the_product_root_on_the_changed_c_lines_for_braces(self):
        self.commit_change({"src/a.c": "int a(void);\nint b(void);\n", "README.md": "z\n"})
        result = self.call(cwd=self.root / "src")
        self.assertEqual(0, result.returncode, result.stderr)
        lines = self.log.read_text().splitlines()
        self.assertEqual("cwd=" + str(self.root.resolve()), lines[-1])
        args = lines[:-1]
        self.assertEqual(["--no-tree", "--no-signoff", "--types", "BRACES", "-"], args)
        diff = Path(f"{self.log}.stdin").read_text()
        self.assertIn("+++ b/src/a.c", diff)
        self.assertIn("+int b(void);", diff)
        self.assertNotIn("README.md", diff)

    def test_the_checked_types_can_be_widened_by_the_environment(self):
        self.commit_change({"src/a.c": "int b(void);\n"})
        self.assertEqual(0, self.call(env={"CHECKPATCH_TYPES": "BRACES,CODE_INDENT"}).returncode)
        self.assertEqual(["--no-tree", "--no-signoff", "--types", "BRACES,CODE_INDENT", "-"],
                         self.log.read_text().splitlines()[:-1])

    def test_a_checkpatch_finding_fails_the_wrapper(self):
        self.commit_change({"src/a.c": "int b(void);\n"})
        self.assertNotEqual(0, self.call(env={"FAKE_CHECKPATCH_EXIT": "1"}).returncode)

    @unittest.skipUnless(
        os.environ.get("ZEPHYR_BASE") and Path(os.environ["ZEPHYR_BASE"], "scripts/checkpatch.pl").is_file(),
        "needs a Zephyr tree: set ZEPHYR_BASE")
    def test_with_the_real_checkpatch_an_unbraced_if_fails_and_a_braced_one_passes(self):
        real = {"ZEPHYR_BASE": os.environ["ZEPHYR_BASE"]}
        self.commit_change({"src/a.c": "int f(int a)\n{\n    if (a) {\n        return 1;\n    }\n    return 0;\n}\n"})
        self.assertEqual(0, run([BASH, STYLE / "check-patch.sh"], cwd=self.root, env=real).returncode)
        self.commit_change({"src/a.c": "int f(int a)\n{\n    if (a)\n        return 1;\n    return 0;\n}\n"})
        self.assertNotEqual(0, run([BASH, STYLE / "check-patch.sh"], cwd=self.root, env=real).returncode)


@unittest.skipUnless(BASH and GIT, "needs bash and git")
class IncludesWrapperTest(unittest.TestCase):
    CHECK = TEMPLATE / "check_domain_includes.py"

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.tmp = Path(self.directory.name)
        self.log = self.tmp / "python-args.txt"
        self.python = stub(self.tmp, "fake-python", f'#!/usr/bin/env bash\nprintf \'%s\\n\' "$@" > "{self.log}"\n')

    def test_it_runs_the_documented_product_check_from_the_git_top_level(self):
        root = make_repo(self.tmp / "product", {"check_domain_includes.py": "# copy\n", "app/src/a.c": "int a;\n"})
        result = run([BASH, STYLE / "check-includes.sh", "--exclude", "app/src/legacy.c"],
                     cwd=root / "app/src", env={"PYTHON": self.python})
        self.assertEqual(0, result.returncode, result.stderr)
        top = str(Path(git(root, "rev-parse", "--show-toplevel")))
        self.assertEqual([str(Path(top, "check_domain_includes.py")), "--product", top,
                          "--exclude", "app/src/legacy.c"], self.log.read_text().splitlines())

    def test_without_a_copy_at_the_product_root_it_uses_the_template_copy(self):
        root = make_repo(self.tmp / "product", {"app/src/a.c": "int a;\n"})
        result = run([BASH, STYLE / "check-includes.sh"], cwd=root, env={"PYTHON": self.python})
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(str(STYLE.parent / "check_domain_includes.py"), self.log.read_text().splitlines()[0])

    def test_the_real_check_rejects_a_frozen_header_in_an_adapter_and_accepts_zephyr_headers(self):
        root = make_repo(self.tmp / "product", {"check_domain_includes.py": self.CHECK.read_text(),
                                                "app/src/a.c": "#include <zephyr/kernel.h>\n",
                                                "app/src/b.c": "#include <zephyr/kernel.h>\n"})
        env = {"PYTHON": shutil.which("python3")}
        self.assertEqual(0, run([BASH, STYLE / "check-includes.sh"], cwd=root, env=env).returncode)
        write_files(root, {"app/src/a.c": "#include <crux/thread.h>\n"})
        result = run([BASH, STYLE / "check-includes.sh"], cwd=root, env=env)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("crux/thread.h", result.stdout + result.stderr)
        result = run([BASH, STYLE / "check-includes.sh", "--exclude", "app/src/a.c"], cwd=root, env=env)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_the_whole_template_passes_its_own_wrapper(self):
        root = make_repo(self.tmp / "copy", {})
        shutil.copytree(TEMPLATE, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns("build", ".git"))
        git(root, "add", "-A")
        result = run([BASH, root / "style/check-includes.sh"], cwd=root, env={"PYTHON": shutil.which("python3")})
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


class GuidelineTest(unittest.TestCase):
    def setUp(self):
        self.text = section(GUIDELINES, GUIDELINE_HEADING)

    def test_the_scope_is_stated_as_guidance_for_code_that_crux_does_not_own(self):
        opening = self.text.split("\n### ")[0]
        self.assertIn("Crux-owned", opening)
        self.assertIn("not a Crux interface", opening)
        self.assertIn("no Crux check enforces", opening)

    def test_title_and_top_level_sections(self):
        text = GUIDELINES.read_text()
        self.assertTrue(text.startswith("# Coding Guidelines\n"))
        headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
        self.assertEqual(headings, ["Purpose and scope", "Coding conventions", "Public API design",
                                    "Public API documentation", "Logging", "Review and validation",
                                    "Zephyr and driver code in a product repository", "References"])
        logging = section(GUIDELINES, "## Logging")
        first = logging.split("\n\n", 2)[1]
        self.assertIn("log records and console output", first.split(". ")[0])
        self.assertNotIn("Pilot", text)

    def test_the_purpose_section_points_to_the_new_section(self):
        purpose = section(GUIDELINES, "## Purpose and scope")
        self.assertIn("(#zephyr-and-driver-code-in-a-product-repository)", purpose)

    def test_the_upstream_list_links_style_devicetree_kconfig_doxygen_and_api_design(self):
        upstream = section(GUIDELINES, "## References")
        for page in ("contribute/style/code", "contribute/style/devicetree", "contribute/style/kconfig",
                     "contribute/style/doxygen", "develop/api/design_guidelines"):
            self.assertIn(f"https://docs.zephyrproject.org/latest/{page}.html", upstream, page)

    @unittest.skipUnless(zephyr_tree(), "needs a Zephyr tree: set ZEPHYR_BASE")
    def test_every_zephyr_page_the_guideline_links_exists_in_the_zephyr_tree(self):
        pages = re.findall(r"https://docs\.zephyrproject\.org/latest/([\w/]+)\.html", GUIDELINES.read_text())
        self.assertGreaterEqual(len(pages), 5)
        for page in pages:
            self.assertTrue((zephyr_tree() / "doc" / f"{page}.rst").is_file(), page)

    def test_it_settles_what_a_link_cannot(self):
        for term in ("DEVICE_API", "DT_DRV_COMPAT", "initlevels", "LOG_MODULE_REGISTER", "errno", "-ENOTSUP",
                     "k_is_in_isr", "K_NO_WAIT", "sys_cache_data_flush_range", "sys_cache_data_invd_range",
                     "native_sim", "vendor-prefixes.txt", "crux_", "CRUX_", "CONFIG_CRUX_"):
            self.assertIn(term, self.text, term)

    def test_the_priority_range_is_the_one_of_the_pinned_zephyr_generation(self):
        self.assertIn("0 to 999", self.text)
        self.assertNotIn("0 to 99 ", self.text)

    def test_it_says_what_the_boundary_check_does_not_police(self):
        covered = section(GUIDELINES, "### What the Crux boundary check covers")
        self.assertIn("check_domain_includes.py", covered)
        self.assertIn("--product", covered)
        self.assertIn("does not", covered)
        for gap in ("DEVICE_API", "prefix", "priorities", "errno", "DMA", "devicetree", "Kconfig"):
            self.assertIn(gap, covered, gap)

    def test_the_wrappers_are_described_with_their_paths(self):
        text = section(GUIDELINES, "### Checks from a product root")
        for name in ("check-format.sh", "check-patch.sh", "check-includes.sh", ".clang-format", ".clang-tidy"):
            self.assertIn(name, text)
        self.assertIn("templates/product/style", text)

    def test_the_compliance_note_names_each_check_and_marks_what_was_not_verified(self):
        text = section(GUIDELINES, "### Zephyr compliance checks out of tree")
        for name in COMPLIANCE_CHECKS:
            self.assertIn(name, text, name)
        self.assertIn("drivers/", text)
        self.assertIn("not verified", text.lower())
        self.assertIn("-m", text)

    def test_the_compliance_note_says_what_it_reads_and_writes(self):
        text = " ".join(section(GUIDELINES, "### Zephyr compliance checks out of tree").split())
        self.assertNotIn("from the working directory only", text)
        self.assertIn("then `$HOME`, then `.scripts`", text)
        self.assertIn("dts_linter.patch", text)
        self.assertIn("only for a check that fails or warns", text)
        self.assertIn("Gitlint (`-m` is case-insensitive)", text)
        self.assertNotIn("GitLint", text)

    def test_the_binding_and_logging_rules_match_zephyr(self):
        text = " ".join(self.text.split())
        self.assertIn("`<compatible>-<bus>.yaml`", text)
        self.assertIn("LOG_MODULE_DECLARE", text)

    def test_the_new_text_has_no_broken_local_link(self):
        self.assertEqual([], broken_local_links(GUIDELINES, GUIDELINES.read_text()))


class StaleTextTest(unittest.TestCase):
    def test_the_controller_row_no_longer_says_it_keeps_crux_thread_and_queue_code(self):
        row = next(line for line in CHOOSING.read_text().splitlines() if line.startswith("| A controller workload"))
        self.assertNotIn("keeps its Crux Thread and Queue code", row)
        self.assertNotIn("until it migrates", row)
        self.assertIn("k_thread", row)
        self.assertIn("k_msgq", row)


class HardwarePathTest(unittest.TestCase):
    def setUp(self):
        self.text = section(BUILD, HARDWARE_HEADING)

    def test_it_says_plainly_what_the_sources_say(self):
        text = self.text
        self.assertIn("No supported entry point", text)
        self.assertIn("flashes on every launch", text)
        self.assertIn("never performed by a fixture or on launch", text)
        self.assertIn("step 5", text)
        self.assertIn("Decision 5", text)
        self.assertIn("harness_config", text)
        self.assertIn("fixture", text)
        self.assertIn("built", text)

    def test_it_says_where_the_device_control_tool_has_run_as_the_proposal_does(self):
        text = " ".join(self.text.split())
        self.assertNotIn("has run only against fake transports (", text)
        for phrase in ("fake transports", "scripted tools", "pseudo-terminal"):
            self.assertIn(phrase, text)
        self.assertIn("Real pyserial on one disposable pseudo-terminal",
                      (REPO / "docs/test-foundation-proposal.md").read_text())

    def test_it_offers_no_twister_device_testing_run_as_a_safe_route(self):
        lowered = self.text.lower()
        self.assertIn("--device-testing", self.text)
        self.assertRegex(lowered, r"does not offer|not offered|is not a route|do not use")
        self.assertNotRegex(self.text, r"(?m)^\s*west twister .*--device-testing")

    def test_it_links_the_existing_runners_and_gates(self):
        for target in ("board-image-profiles.md", "../tests/README.md", "../tools/device_control/README.md",
                       "test-foundation-proposal.md", "../AGENTS.md"):
            self.assertIn(target, self.text, target)
        self.assertEqual([], broken_local_links(BUILD, self.text))

    def test_the_sources_it_cites_still_say_what_it_claims(self):
        proposal = (REPO / "docs/test-foundation-proposal.md").read_text()
        self.assertIn("**`--device-type=hardware` flashes on every launch**", proposal)
        self.assertIn("An explicit `flash()`, never performed by a fixture or on launch", proposal)
        self.assertIn("5. Not started: use it from the first real consumer", proposal)
        self.assertIn("Decided: a small tool", proposal)
        self.assertIn("| Hardware | No supported entry point.", BUILD.read_text())

    def test_the_test_guide_points_to_it(self):
        text = TESTS_README.read_text()
        self.assertIn("../docs/build.md#hardware-integration-tests", text)
        self.assertEqual([], broken_local_links(TESTS_README, text))


class TemplatePointerTest(unittest.TestCase):
    def test_the_template_readme_points_to_the_kit_in_its_last_lines(self):
        readme = TEMPLATE / "README.md"
        text = readme.read_text()
        self.assertIn("style/README.md", "\n".join(text.rstrip().splitlines()[-3:]))
        self.assertEqual([], broken_local_links(readme, text))


if __name__ == "__main__":
    unittest.main()
