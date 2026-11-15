"""The generated list of sources for clang-tidy (scripts/tidy-sources.py).

The list comes from the compile databases that the host job produces. These tests use synthetic
databases and a fake clang-tidy, so they run anywhere. A final group reads the committed
configuration (scripts/tidy-sources.conf) and checks that it cannot rot.
"""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "tidy-sources.py"
CONFIG = REPO / "scripts" / "tidy-sources.conf"


class Tree:
    """A synthetic repository: source files, compile databases and a configuration file."""

    def __init__(self, root):
        self.root = Path(root)
        self.config = self.root / "tidy-sources.conf"
        self.config.write_text("")

    def source(self, rel):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("int x;\n")
        return path

    def database(self, build, entries, relative=False):
        """Write build/<build>/compile_commands.json naming each entry (an existing or absolute path)."""
        directory = self.root / build
        directory.mkdir(parents=True, exist_ok=True)
        records = []
        for entry in entries:
            path = Path(entry)
            if not path.is_absolute():
                path = self.root / entry
            file = os.path.relpath(path, directory) if relative else str(path)
            records.append({"directory": str(directory), "command": f"cc -c {path}", "file": file})
        (directory / "compile_commands.json").write_text(json.dumps(records))

    def configure(self, text):
        self.config.write_text(textwrap.dedent(text))

    def run(self, *args, env=None):
        command = [sys.executable, str(SCRIPT), *args[:1], "--repo", str(self.root),
                   "--config", str(self.config), *args[1:]]
        return subprocess.run(command, capture_output=True, text=True, env=env)

    def listing(self, *extra):
        result = self.run("list", *extra)
        assert result.returncode == 0, result.stderr
        return [tuple(line.split("\t")) for line in result.stdout.splitlines()]

    def sources(self, *extra):
        return sorted(source for _build, source in self.listing(*extra))


class TidySourcesCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tree = Tree(Path(self._tmp.name).resolve())


class GeneratedListTest(TidySourcesCase):
    def test_the_list_is_the_database_minus_the_exclusions(self):
        t = self.tree
        names = ["components/a/src/a.c", "components/a/src/b.c", "tests/a/a_test.cpp",
                 "samples/a/main.c", "web/server/x.cc", "tests/a/probe/fails.c"]
        for name in names:
            t.source(name)
        t.database("build/linux/debug", names)
        t.configure("""\
            build ; build/linux/debug
            exclude ; tests/a/probe/fails.c ; deliberate compile-fail probe
            """)
        self.assertEqual(sorted(set(names) - {"tests/a/probe/fails.c"}), t.sources())

    def test_a_new_source_is_picked_up_without_editing_any_list(self):
        t = self.tree
        t.source("components/a/a.c")
        t.database("build/linux/debug", ["components/a/a.c"])
        t.configure("build ; build/linux/debug\n")
        self.assertEqual(["components/a/a.c"], t.sources())
        t.source("components/a/new_feature.c")
        t.database("build/linux/debug", ["components/a/a.c", "components/a/new_feature.c"])
        self.assertEqual(["components/a/a.c", "components/a/new_feature.c"], t.sources())

    def test_only_owned_roots_and_c_family_sources_are_listed(self):
        t = self.tree
        t.source("components/a/a.c")
        t.source("third_party/lib/lib.c")
        t.source("build/linux/debug/_deps/dep/dep.c")
        t.source("build/linux/debug/generated/gen.c")
        t.source("components/a/startup.S")
        t.database("build/linux/debug", [
            "components/a/a.c", "third_party/lib/lib.c", "build/linux/debug/_deps/dep/dep.c",
            "build/linux/debug/generated/gen.c", "components/a/startup.S", "/somewhere/else/outside.c"])
        t.configure("build ; build/linux/debug\n")
        self.assertEqual(["components/a/a.c"], t.sources())

    def test_a_source_in_several_databases_is_listed_once_from_the_first(self):
        t = self.tree
        t.source("components/a/a.c")
        t.source("tests/consumer/only.c")
        t.database("build/linux/debug", ["components/a/a.c"])
        t.database("build/linux/sanitize", ["components/a/a.c"])
        t.database("build/consumer", ["components/a/a.c", "tests/consumer/only.c"])
        t.configure("""\
            build ; build/linux/debug
            build ; build/linux/sanitize
            build ; build/consumer
            """)
        self.assertEqual([("build/linux/debug", "components/a/a.c"),
                          ("build/consumer", "tests/consumer/only.c")], sorted(t.listing(), key=lambda p: p[1]))

    def test_primary_moves_one_build_to_the_front(self):
        t = self.tree
        t.source("components/a/a.c")
        t.database("build/linux/debug", ["components/a/a.c"])
        t.database("build/linux/sanitize", ["components/a/a.c"])
        t.configure("build ; build/linux/debug\nbuild ; build/linux/sanitize\n")
        self.assertEqual([("build/linux/sanitize", "components/a/a.c")],
                         t.listing("--primary", "build/linux/sanitize"))

    def test_relative_paths_in_the_database_resolve_against_its_directory(self):
        t = self.tree
        t.source("components/a/a.c")
        t.database("build/linux/debug", ["components/a/a.c"], relative=True)
        t.configure("build ; build/linux/debug\n")
        self.assertEqual(["components/a/a.c"], t.sources())

    def test_a_source_named_by_the_database_but_missing_from_the_tree_fails(self):
        t = self.tree
        t.database("build/linux/debug", [t.root / "components/a/gone.c"])
        t.configure("build ; build/linux/debug\n")
        result = t.run("check")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("components/a/gone.c", result.stderr)


class CompiledButInNoListTest(TidySourcesCase):
    """A compiled source that no list covers must fail the check."""

    def test_a_database_that_is_neither_analysed_nor_ignored_fails_and_names_it(self):
        t = self.tree
        t.source("components/a/a.c")
        t.source("tests/new_consumer/consumer.c")
        t.database("build/linux/debug", ["components/a/a.c"])
        t.database("build/new-consumer", ["tests/new_consumer/consumer.c"])
        t.configure("build ; build/linux/debug\n")
        result = t.run("check", "--strict")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("build/new-consumer", result.stderr)
        self.assertIn("tests/new_consumer/consumer.c", result.stderr)

    def test_outside_strict_mode_an_unlisted_database_is_only_a_warning(self):
        t = self.tree
        t.source("components/a/a.c")
        t.database("build/linux/debug", ["components/a/a.c"])
        t.database("build/stray", ["components/a/a.c"])
        t.configure("build ; build/linux/debug\n")
        result = t.run("check")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("build/stray", result.stderr)

    def test_an_ignored_database_needs_a_reason_and_then_passes(self):
        t = self.tree
        t.source("tests/probe_consumer/probe.c")
        t.source("components/a/a.c")
        t.database("build/linux/debug", ["components/a/a.c"])
        t.database("build/access-boundary", ["tests/probe_consumer/probe.c"])
        t.configure("""\
            build ; build/linux/debug
            ignore-build ; build/*-boundary ; probe sources must fail to compile
            """)
        result = t.run("check", "--strict")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["components/a/a.c"], t.sources())

    def test_a_listed_build_that_is_absent_fails_only_in_strict_mode(self):
        t = self.tree
        t.source("components/a/a.c")
        t.database("build/linux/debug", ["components/a/a.c"])
        t.configure("build ; build/linux/debug\nbuild ; build/logging-consumer\n")
        lenient = t.run("check")
        self.assertEqual(0, lenient.returncode, lenient.stderr)
        self.assertIn("build/logging-consumer", lenient.stderr)
        strict = t.run("check", "--strict")
        self.assertEqual(1, strict.returncode, strict.stdout)
        self.assertIn("build/logging-consumer", strict.stderr)

    def test_a_database_below_a_database_is_not_a_separate_build(self):
        t = self.tree
        t.source("components/a/a.c")
        t.database("build/linux/debug", ["components/a/a.c"])
        t.database("build/linux/debug/nested", ["components/a/a.c"])
        t.configure("build ; build/linux/debug\n")
        self.assertEqual(0, t.run("check", "--strict").returncode)


class ExclusionTest(TidySourcesCase):
    def setUp(self):
        super().setUp()
        t = self.tree
        t.source("components/a/a.c")
        t.source("tests/a/probe.c")
        t.database("build/linux/debug", ["components/a/a.c", "tests/a/probe.c"])

    def test_an_exclusion_without_a_reason_is_refused(self):
        self.tree.configure("build ; build/linux/debug\nexclude ; tests/a/probe.c\n")
        result = self.tree.run("check")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("reason", result.stderr)
        self.assertIn("tidy-sources.conf:2", result.stderr)

    def test_an_exclusion_with_an_empty_reason_is_refused(self):
        self.tree.configure("build ; build/linux/debug\nexclude ; tests/a/probe.c ;   \n")
        self.assertEqual(1, self.tree.run("check").returncode)

    def test_an_ignored_build_without_a_reason_is_refused(self):
        self.tree.configure("build ; build/linux/debug\nignore-build ; build/other\n")
        result = self.tree.run("check")
        self.assertEqual(1, result.returncode)
        self.assertIn("reason", result.stderr)

    def test_an_exclusion_for_a_file_that_does_not_exist_is_refused(self):
        self.tree.configure("build ; build/linux/debug\nexclude ; tests/a/removed.c ; was a probe\n")
        result = self.tree.run("check")
        self.assertEqual(1, result.returncode)
        self.assertIn("tests/a/removed.c", result.stderr)

    def test_an_exclusion_nothing_compiles_fails_in_strict_mode_only(self):
        self.tree.source("tests/a/not_built.c")
        self.tree.configure(
            "build ; build/linux/debug\nexclude ; tests/a/not_built.c ; compiled by no listed build\n")
        self.assertEqual(0, self.tree.run("check").returncode)
        strict = self.tree.run("check", "--strict")
        self.assertEqual(1, strict.returncode, strict.stdout)
        self.assertIn("tests/a/not_built.c", strict.stderr)

    def test_an_exclusion_is_one_explicit_path_not_a_pattern(self):
        self.tree.configure("build ; build/linux/debug\nexclude ; tests/a/*.c ; everything\n")
        result = self.tree.run("check")
        self.assertEqual(1, result.returncode)
        self.assertIn("pattern", result.stderr)

    def test_an_excluded_source_is_not_listed(self):
        self.tree.configure("build ; build/linux/debug\nexclude ; tests/a/probe.c ; deliberate probe\n")
        self.assertEqual(["components/a/a.c"], self.tree.sources())


class ConfigurationSyntaxTest(TidySourcesCase):
    def test_comments_and_blank_lines_are_ignored(self):
        t = self.tree
        t.source("components/a/a.c")
        t.database("build/linux/debug", ["components/a/a.c"])
        t.configure("""\
            # a comment

            build ; build/linux/debug   # trailing comment
            """)
        self.assertEqual(["components/a/a.c"], t.sources())

    def test_an_unknown_kind_is_refused_with_its_line_number(self):
        self.tree.configure("build ; build/linux/debug\nanalyse ; build/x\n")
        result = self.tree.run("check")
        self.assertEqual(1, result.returncode)
        self.assertIn("tidy-sources.conf:2", result.stderr)
        self.assertIn("analyse", result.stderr)

    def test_a_missing_configuration_file_is_a_usage_error(self):
        self.tree.config.unlink()
        self.assertEqual(2, self.tree.run("check").returncode)

    def test_a_build_outside_the_build_directory_is_refused(self):
        self.tree.configure("build ; ../elsewhere\n")
        self.assertEqual(1, self.tree.run("check").returncode)


FAKE_TIDY = """\
#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
log = os.environ["FAKE_TIDY_LOG"]
with open(log, "a") as handle:
    handle.write(" ".join(args) + "\\n")
source = args[-1]
if source.endswith("bad.c"):
    print(f"{source}:3:5: error: something is off [bugprone-fake-check,-warnings-as-errors]")
    print("    int x;")
    sys.exit(1)
if source.endswith("noisy.c"):
    header = os.path.join(os.path.dirname(source), "shared.h")
    print(f"{header}:9:1: error: shared problem [bugprone-shared,-warnings-as-errors]")
    sys.exit(1)
"""


class RunTest(TidySourcesCase):
    def setUp(self):
        super().setUp()
        t = self.tree
        self.log = t.root / "tidy.log"
        tidy = t.root / "fake-tidy"
        tidy.write_text(FAKE_TIDY)
        tidy.chmod(tidy.stat().st_mode | stat.S_IXUSR)
        self.tidy = tidy
        for name in ("components/a/a.c", "components/a/bad.c", "tests/a/ok.c", "tests/a/noisy.c",
                     "tests/a/other_noisy.c", "tests/a/probe.c"):
            t.source(name)
        t.database("build/linux/debug", ["components/a/a.c", "components/a/bad.c", "tests/a/ok.c",
                                         "tests/a/probe.c"])
        t.database("build/consumer", ["tests/a/noisy.c", "tests/a/other_noisy.c"])
        t.configure("""\
            build ; build/linux/debug
            build ; build/consumer
            exclude ; tests/a/probe.c ; deliberate probe
            """)
        self.env = dict(os.environ, FAKE_TIDY_LOG=str(self.log))

    def run_tidy(self, *extra):
        return self.tree.run("run", "--tidy", str(self.tidy), "--jobs", "2", *extra, env=self.env)

    def invocations(self):
        return sorted(self.log.read_text().splitlines())

    def test_every_listed_source_is_analysed_once_with_its_own_build_directory(self):
        self.run_tidy("--report-only")
        root = self.tree.root
        called = self.invocations()
        self.assertEqual(5, len(called), called)
        self.assertTrue(any(line.endswith(f"{root}/tests/a/noisy.c") and f"-p {root}/build/consumer" in line
                            for line in called), called)
        self.assertTrue(any(line.endswith(f"{root}/components/a/a.c") and f"-p {root}/build/linux/debug" in line
                            for line in called), called)

    def test_an_excluded_source_is_never_passed_to_clang_tidy(self):
        self.run_tidy("--report-only")
        self.assertFalse(any("probe.c" in line for line in self.invocations()))

    def test_a_diagnostic_fails_the_run_and_names_the_source(self):
        result = self.run_tidy()
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("components/a/bad.c", result.stdout + result.stderr)
        self.assertIn("bugprone-fake-check", result.stdout + result.stderr)

    def test_report_only_exits_zero_and_prints_counts_per_directory(self):
        result = self.run_tidy("--report-only")
        self.assertEqual(0, result.returncode, result.stderr)
        out = result.stdout
        self.assertIn("components/a", out)
        self.assertRegex(out, r"components/a\s+1\b")
        self.assertIn("bugprone-fake-check", out)
        self.assertNotIn("warnings-as-errors", out)
        # The same header diagnostic reported through two sources is counted once.
        self.assertRegex(out, r"tests/a\s+1\b")
        self.assertIn("2 diagnostics", out)

    def test_the_run_stops_before_clang_tidy_when_the_check_fails(self):
        self.tree.configure("build ; build/linux/debug\nbuild ; build/consumer\nexclude ; tests/a/probe.c\n")
        result = self.run_tidy()
        self.assertEqual(1, result.returncode)
        self.assertFalse(self.log.exists())

    def test_a_clean_run_exits_zero(self):
        self.tree.configure("""\
            build ; build/linux/debug
            build ; build/consumer
            exclude ; tests/a/probe.c ; deliberate probe
            exclude ; components/a/bad.c ; fake failure
            exclude ; tests/a/noisy.c ; fake failure
            exclude ; tests/a/other_noisy.c ; fake failure
            """)
        result = self.run_tidy()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("2 sources", result.stdout)

    def test_a_clang_tidy_that_cannot_start_is_a_failure_even_in_report_only_mode_output(self):
        result = self.tree.run("run", "--tidy", str(self.tree.root / "no-such-tidy"), "--report-only",
                               env=self.env)
        self.assertIn("no-such-tidy", result.stdout + result.stderr)
        self.assertNotEqual("", result.stdout + result.stderr)

    def test_json_output_lists_the_diagnostics(self):
        out = self.tree.root / "report.json"
        self.run_tidy("--report-only", "--json", str(out))
        report = json.loads(out.read_text())
        self.assertEqual(5, report["sources"])
        checks = sorted(item["check"] for item in report["diagnostics"])
        self.assertEqual(["bugprone-fake-check", "bugprone-shared"], checks)


class CommittedConfigurationTest(unittest.TestCase):
    """The configuration in the repository must stay valid and honest."""

    def parse(self):
        entries = []
        for number, line in enumerate(CONFIG.read_text().splitlines(), 1):
            text = line.split("#", 1)[0].strip()
            if text:
                entries.append((number, [part.strip() for part in text.split(";")]))
        return entries

    def test_the_file_exists_and_names_the_primary_host_build_first(self):
        builds = [fields[1] for _n, fields in self.parse() if fields[0] == "build"]
        self.assertEqual("build/linux/debug", builds[0])

    def test_every_excluded_source_exists_and_has_a_reason(self):
        excluded = [(n, fields) for n, fields in self.parse() if fields[0] == "exclude"]
        for number, fields in excluded:
            with self.subTest(line=number):
                self.assertEqual(3, len(fields), fields)
                self.assertTrue(fields[2], "an exclusion needs a reason")
                self.assertTrue((REPO / fields[1]).is_file(), fields[1])
                self.assertEqual(fields[1], fields[1].strip("/"))

    def test_every_ignored_build_has_a_reason(self):
        for number, fields in self.parse():
            if fields[0] == "ignore-build":
                with self.subTest(line=number):
                    self.assertEqual(3, len(fields), fields)
                    self.assertTrue(fields[2])

    def test_the_checker_accepts_the_committed_file_on_an_empty_build_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(SCRIPT), "check", "--repo", str(REPO),
                                     "--config", str(CONFIG), "--build-root", tmp],
                                    capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
