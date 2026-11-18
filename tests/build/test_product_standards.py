"""Product standards kit: the target-code tidy profile and script, the product CONTRIBUTING template,
the driver review checklist, and the guidance that names them (WP3b).

Everything here runs on the Host with Python and Git. The tidy script is run against a stand-in for
clang-tidy, and against the real clang-tidy 18 when it is present: set CLANG_TIDY to run that case
instead of skipping it. Nothing here uses west, Docker, hardware or the network.
"""
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from test_product_style import (anchors, broken_local_links, make_repo, run, section, settings, stub)

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "templates/product"
STYLE = TEMPLATE / "style"
PROFILE = STYLE / "target.clang-tidy"
SCRIPT = STYLE / "check_target_tidy.py"
CONTRIBUTING = TEMPLATE / "CONTRIBUTING.md"
CHECKLIST = REPO / "docs/driver-review-checklist.md"
GUIDELINES = REPO / "docs/coding-guidelines.md"
DOCS_INDEX = REPO / "docs/README.md"
TESTS_README = REPO / "tests/README.md"
GIT = shutil.which("git")

TIDY_HEADING = "### Static analysis of target code"
MISRA_HEADING = "### MISRA C position"


def checks(path):
    text = path.read_text()
    match = re.search(r"^Checks:\s*>-?\n((?:[ \t]+.*\n)+)", text, re.MULTILINE)
    assert match, f"{path} has no Checks block"
    return [item for item in "".join(match.group(1).split()).split(",") if item]


def tidy(root, build, *args, env=None, cwd=None):
    return run([sys.executable, "-I", SCRIPT, build, *args], cwd=cwd or root, env=env)


def database(build, root, entries):
    """Write a compile_commands.json in build. entries are (directory, file) pairs."""
    Path(build).mkdir(parents=True, exist_ok=True)
    data = [{"directory": str(directory), "file": str(file),
             "command": f"cc -c {file}"} for directory, file in entries]
    (Path(build) / "compile_commands.json").write_text(json.dumps(data))


class ProfileTest(unittest.TestCase):
    def test_it_selects_cruxs_checks_and_drops_only_the_documented_one(self):
        crux = checks(REPO / ".clang-tidy")
        target = checks(PROFILE)
        self.assertEqual(crux, [item for item in target if item != "-bugprone-easily-swappable-parameters"])
        self.assertEqual(["-bugprone-easily-swappable-parameters"],
                         [item for item in target if item not in crux])

    def test_it_is_advisory_and_needs_no_placeholder(self):
        text = PROFILE.read_text()
        self.assertIn("# SPDX-License-Identifier: Apache-2.0", text.splitlines()[:3])
        self.assertIn("advisory", text.lower())
        self.assertIn("WarningsAsErrors: ''", settings(PROFILE))
        self.assertNotIn("<PRODUCT_ROOT>", "\n".join(settings(PROFILE)))
        self.assertFalse([line for line in settings(PROFILE) if line.startswith("HeaderFilterRegex")])

    def test_it_is_not_named_like_the_file_clang_tidy_finds_by_itself(self):
        self.assertNotEqual(".clang-tidy", PROFILE.name)
        self.assertTrue((STYLE / ".clang-tidy").is_file())


@unittest.skipUnless(GIT, "needs git")
class ScriptFilesTest(unittest.TestCase):
    def test_it_is_executable_python_with_an_spdx_line(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))
        head = SCRIPT.read_text().splitlines()[:4]
        self.assertEqual("#!/usr/bin/env python3", head[0])
        self.assertIn("# SPDX-License-Identifier: Apache-2.0", head)

    def test_help_exits_zero_and_creates_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            for option in ("--help", "-h"):
                result = run([sys.executable, "-I", SCRIPT, option], cwd=directory)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("usage:", result.stdout.lower())
                self.assertIn("advisory", result.stdout.lower())
            self.assertEqual([], list(Path(directory).iterdir()))


@unittest.skipUnless(GIT, "needs git")
class ScriptTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.tmp = Path(self.directory.name).resolve()
        self.log = self.tmp / "calls.txt"
        self.tool = stub(self.tmp, "fake-clang-tidy",
                         "#!/usr/bin/env python3\nimport sys\n"
                         f"open({str(self.log)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
                         "name = sys.argv[-1]\n"
                         "if name.endswith('broken.c'):\n"
                         "    print(name + ':1:1: error: unknown argument [clang-diagnostic-error]')\n"
                         "    sys.exit(1)\n"
                         "if name.endswith('dirty.c'):\n"
                         "    print(name + ':3:5: warning: bad thing [bugprone-x]')\n"
                         "    print(name + ':4:5: warning: another [bugprone-y]')\n")
        self.root = make_repo(self.tmp / "product", {"app/main.c": "int a;\n", "README.md": "x\n"})
        self.root = self.root.resolve()
        self.build = self.root / "build"

    def env(self, **extra):
        return {"CLANG_TIDY": str(self.tool), **extra}

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_it_analyses_only_product_sources_outside_the_build_directory(self):
        database(self.build, self.root, [
            (self.root, "app/main.c"),
            (self.root / "build", self.root / "drivers/sensor/part.c"),
            (self.root / "build", self.root / "tests/unit/t.c"),
            (self.root / "build", self.root / "build/zephyr/misc/generated.c"),
            (self.tmp / "ws/zephyr", self.tmp / "ws/zephyr/drivers/gpio/gpio.c"),
            (self.root, "app/vendor.S")])
        result = tidy(self.root, self.build, env=self.env())
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        analysed = sorted(Path(call.split()[-1]).relative_to(self.root).as_posix() for call in self.calls())
        self.assertEqual(["app/main.c", "drivers/sensor/part.c", "tests/unit/t.c"], analysed)
        self.assertIn("3 source files analysed", result.stdout)

    def test_it_passes_the_profile_database_and_an_anchored_header_filter(self):
        database(self.build, self.root, [(self.root, "app/main.c")])
        self.assertEqual(0, tidy(self.root, self.build, env=self.env()).returncode)
        (call,) = self.calls()
        self.assertIn(f"-p {self.build}", call)
        self.assertIn(f"--config-file={PROFILE}", call)
        header_filter = re.search(r"--header-filter=(\S+)", call).group(1)
        pattern = re.compile(header_filter)
        self.assertTrue(pattern.search(f"{self.root}/drivers/sensor/part.h"))
        self.assertFalse(pattern.search(f"{self.tmp}/ws/zephyr/include/zephyr/kernel.h"))
        self.assertFalse(pattern.search(f"{self.root}/build/zephyr/include/generated/autoconf.h"))

    def test_findings_are_printed_counted_and_do_not_fail_the_run(self):
        database(self.build, self.root, [(self.root, "app/main.c"), (self.root, "app/dirty.c")])
        result = tidy(self.root, self.build, env=self.env())
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("bad thing", result.stdout)
        self.assertIn("2 findings", result.stdout)
        self.assertIn("advisory", result.stdout.lower())

    def test_a_file_that_does_not_compile_is_reported_and_fails_the_run(self):
        database(self.build, self.root, [(self.root, "app/main.c"), (self.root, "app/broken.c")])
        result = tidy(self.root, self.build, env=self.env())
        self.assertEqual(1, result.returncode)
        self.assertIn("1 file that did not compile", result.stdout)
        self.assertEqual(2, len(self.calls()))  # the other file was still analysed

    def test_exclude_filters_by_path_relative_to_the_product_root(self):
        database(self.build, self.root, [(self.root, "app/main.c"), (self.root, "app/legacy/old.c")])
        result = tidy(self.root, self.build, "--exclude", "^app/legacy/", env=self.env())
        self.assertEqual(0, result.returncode)
        self.assertEqual(["app/main.c"], [Path(c.split()[-1]).relative_to(self.root).as_posix()
                                          for c in self.calls()])

    def test_arguments_after_a_double_dash_go_to_clang_tidy(self):
        database(self.build, self.root, [(self.root, "app/main.c")])
        result = tidy(self.root, self.build, "--", "--extra-arg=-Wno-unknown-warning-option", env=self.env())
        self.assertEqual(0, result.returncode)
        (call,) = self.calls()
        self.assertIn("--extra-arg=-Wno-unknown-warning-option", call)

    def test_it_runs_from_a_subdirectory_and_resolves_a_relative_build_directory(self):
        database(self.build, self.root, [(self.root, "app/main.c")])
        result = run([sys.executable, "-I", SCRIPT, "../build"], cwd=self.root / "app", env=self.env())
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(1, len(self.calls()))

    def test_no_product_source_in_the_database_passes_and_runs_nothing(self):
        database(self.build, self.root, [(self.tmp, self.tmp / "ws/zephyr/x.c")])
        result = tidy(self.root, self.build, env=self.env())
        self.assertEqual(0, result.returncode)
        self.assertIn("No product source files", result.stdout)
        self.assertEqual([], self.calls())

    def test_usage_errors_exit_two_and_name_the_remedy(self):
        result = tidy(self.root, self.root / "absent", env=self.env())
        self.assertEqual(2, result.returncode)
        self.assertIn("compile_commands.json", result.stderr)
        database(self.build, self.root, [(self.root, "app/main.c")])
        result = tidy(self.root, self.build, env={"CLANG_TIDY": str(self.tmp / "no-such-tool")})
        self.assertEqual(2, result.returncode)
        self.assertIn("CLANG_TIDY", result.stderr)
        result = tidy(self.root, self.build, "--profile", str(self.tmp / "none.yaml"), env=self.env())
        self.assertEqual(2, result.returncode)
        self.assertIn("profile", result.stderr.lower())
        self.assertEqual([], self.calls())

    def test_it_does_not_modify_the_repository(self):
        database(self.build, self.root, [(self.root, "app/main.c"), (self.root, "app/dirty.c")])
        before = subprocess.run([GIT, "status", "--porcelain", "--ignored"], cwd=self.root,
                                capture_output=True, text=True).stdout
        tidy(self.root, self.build, env=self.env())
        after = subprocess.run([GIT, "status", "--porcelain", "--ignored"], cwd=self.root,
                               capture_output=True, text=True).stdout
        self.assertEqual(before, after)
        self.assertNotIn("--fix", " ".join(self.calls()))

    @unittest.skipUnless(os.environ.get("CLANG_TIDY") and shutil.which(os.environ["CLANG_TIDY"]),
                         "needs clang-tidy 18: set CLANG_TIDY")
    def test_with_the_real_tool_the_profile_loads_and_a_finding_is_reported(self):
        real = shutil.which(os.environ["CLANG_TIDY"])
        source = self.root / "app/bug.c"
        source.write_text("#include <string.h>\nint f(char *d, const char *s)\n{\n"
                          "    return (int)strlen(d) + (memcpy(d, s, 0) != 0);\n}\n"
                          "int g(int x)\n{\n    if (x == 1) { return 1; } else if (x == 1) { return 2; }\n"
                          "    return 0;\n}\n")
        build = self.root / "build"
        database(build, self.root, [(self.root, "app/bug.c")])
        result = tidy(self.root, build, env={"CLANG_TIDY": real})
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("Error parsing", result.stdout + result.stderr)
        self.assertIn("1 source file analysed", result.stdout)


class CruxTemplateTest(unittest.TestCase):
    def setUp(self):
        self.text = CONTRIBUTING.read_text()

    def test_it_has_the_sections_a_product_needs(self):
        headings = [line for line in self.text.splitlines() if line.startswith("## ")]
        for name in ("Making changes", "Commit messages", "Pull requests", "Checks", "Review",
                     "Protected paths", "Hardware", "What this file does not decide"):
            self.assertTrue([h for h in headings if name in h], name)

    def test_it_uses_a_placeholder_for_the_product_name(self):
        self.assertIn("<PRODUCT>", self.text)

    def test_it_keeps_the_crux_rules_it_adopts_and_does_not_invent_new_ones(self):
        for needle in ("Conventional Commits", "PASS", "REVISE", "ESCALATE",
                       "did not author", "explicit human", "Never use `crux_`"):
            self.assertIn(needle, " ".join(self.text.split()), needle)
        flat = " ".join(self.text.split())
        self.assertIn("blocking finding", flat)
        self.assertIn("per-task", flat)

    def test_a_product_can_use_it_where_crux_docs_do_not_exist(self):
        for target in re.findall(r"\]\(([^)\s]+)\)", self.text):
            self.assertRegex(target, r"^(https://|#|style/)", f"link {target} breaks outside Crux")
        self.assertEqual([], broken_local_links(CONTRIBUTING, self.text))

    def test_it_points_at_the_checklist_the_style_kit_and_the_guideline(self):
        for needle in ("driver-review-checklist.md", "style/", "coding-guidelines.md"):
            self.assertIn(needle, self.text)

    def test_it_is_linked_from_the_template_readme(self):
        readme = (TEMPLATE / "README.md").read_text()
        self.assertIn("(CONTRIBUTING.md)", readme)


class ChecklistTest(unittest.TestCase):
    def setUp(self):
        self.text = CHECKLIST.read_text()

    def test_it_covers_each_topic_of_the_plan(self):
        headings = "\n".join(line for line in self.text.splitlines() if line.startswith("#")).lower()
        for topic in ("binding", "kconfig", "init level and priority", "error paths", "isr and blocking",
                      "dma and cache", "power management", "emulator", "hardware scenario",
                      "licence and spdx", "logging", "prefixes"):
            self.assertIn(topic, headings, topic)

    def test_its_links_and_anchors_resolve(self):
        self.assertEqual([], broken_local_links(CHECKLIST, self.text))

    def test_every_rule_it_applies_exists_in_the_guideline(self):
        guideline = section(GUIDELINES, "### Rules for driver and adapter code")
        for bold in re.findall(r"^- \*\*([^*]+)\.\*\*", guideline, re.MULTILINE):
            self.assertIn(bold.lower(), self.text.lower(), f"checklist skips the rule {bold!r}")

    def test_it_records_a_verdict_in_the_agents_md_vocabulary_and_claims_no_result(self):
        flat = " ".join(self.text.split())
        for word in ("PASS", "REVISE", "ESCALATE", "blocking"):
            self.assertIn(word, flat, word)
        self.assertIn("native_sim", flat)
        self.assertIn("not hardware evidence", flat)

    def test_it_is_linked_from_the_docs_index_and_the_guideline(self):
        self.assertIn("(driver-review-checklist.md)", DOCS_INDEX.read_text())
        self.assertIn("(driver-review-checklist.md)", section(GUIDELINES, "## Zephyr and driver code in a product repository"))


class GuidelineTest(unittest.TestCase):
    def test_the_tidy_subsection_names_the_script_profile_and_limits(self):
        text = " ".join(section(GUIDELINES, TIDY_HEADING).split())
        for needle in ("check_target_tidy.py", "target.clang-tidy", "compile_commands.json",
                       "advisory", "Not run", "ZEPHYR_SCA_VARIANT", "--exclude"):
            self.assertIn(needle, text, needle)

    def test_the_misra_subsection_keeps_misra_advisory_and_claims_no_compliance(self):
        text = " ".join(section(GUIDELINES, MISRA_HEADING).split())
        for needle in ("advisory", "not a gate", "no compliance claim", "--addon", "rule texts",
                       "certification", "customer"):
            self.assertIn(needle, text, needle)
        self.assertNotIn("MISRA-compliant", text)

    def test_the_new_subsections_sit_inside_the_product_section(self):
        product = section(GUIDELINES, "## Zephyr and driver code in a product repository")
        self.assertIn(TIDY_HEADING, product)
        self.assertIn(MISRA_HEADING, product)

    def test_the_guideline_still_resolves_all_of_its_local_links(self):
        self.assertEqual([], broken_local_links(GUIDELINES, GUIDELINES.read_text()))

    def test_the_style_readme_lists_the_new_files_and_resolves(self):
        readme = STYLE / "README.md"
        text = readme.read_text()
        for name in ("target.clang-tidy", "check_target_tidy.py"):
            self.assertIn(name, text)
        self.assertEqual([], broken_local_links(readme, text))

    def test_the_tests_readme_names_this_suite(self):
        self.assertIn("test_product_standards.py", TESTS_README.read_text())

    def test_the_docs_index_and_templates_resolve(self):
        self.assertEqual([], broken_local_links(DOCS_INDEX, DOCS_INDEX.read_text()))
        readme = TEMPLATE / "README.md"
        self.assertEqual([], broken_local_links(readme, readme.read_text()))


if __name__ == "__main__":
    unittest.main()
