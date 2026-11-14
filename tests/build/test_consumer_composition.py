"""Host checks of the out-of-tree consumer fixture of ADR-0004 T3 and T4 (tests/consumer_composition).

They need no Zephyr: they read the fixture, run the functions of check_build.py on small inputs, and apply each
variant of T4 to a copy outside the repository to see that the static half of the checks refuses it. Each check
also runs against a weakened guard and must then pass, so that a refusal is not vacuous. The build and the run on
native_sim belong to scripts/test-consumer-composition.sh.
"""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests/consumer_composition"
SPEC = importlib.util.spec_from_file_location("check_build", FIXTURE / "check_build.py")
check_build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_build)
CHECKER = REPO / "templates/product/check_domain_includes.py"


def copy_outside(root):
    """Copy the consumer to a place outside the repository, as the script does."""
    for name in ("app", "domain"):
        shutil.copytree(FIXTURE / name, Path(root) / name)
    assert REPO not in Path(root).resolve().parents
    return Path(root)


def static_problems(root):
    """The checks that need no build: links, CMake paths, prj.conf symbols and the product-mode headers."""
    cmake = (Path(root) / "app/CMakeLists.txt").read_text()
    conf = (Path(root) / "app/prj.conf").read_text()
    problems = [f"link: {item}" for item in check_build.link_violations(cmake)]
    problems += [f"cmake path: {item}" for item in check_build.path_violations(cmake)]
    problems += [f"symbol in prj.conf: {name}" for name in check_build.conf_violations(conf)]
    result = subprocess.run([sys.executable, str(CHECKER), "--product", str(root), "--domain",
                             "domain"], capture_output=True, text=True)
    if result.returncode != 0:
        problems.append("headers: " + (result.stdout + result.stderr).strip())
    return problems


class FixtureLayoutTest(unittest.TestCase):
    def test_the_layout_is_complete(self):
        for relative in ("README.md", "check_build.py", "variants.json", "app/CMakeLists.txt", "app/prj.conf",
                         "app/app.overlay", "app/src/main.c", "app/src/my_routes.c", "app/site/index.html",
                         "app/reviewed-routes.txt", "app/tf_psa_threading/crux_tf_psa_threading.c",
                         "domain/product_policy.c", "domain/product_policy.h"):
            self.assertTrue((FIXTURE / relative).is_file(), relative)

    def test_the_unchanged_fixture_has_no_static_problem(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(static_problems(copy_outside(Path(temporary) / "consumer")), [])

    def test_the_cmake_names_no_file_under_components_and_links_crux_targets_only(self):
        cmake = (FIXTURE / "app/CMakeLists.txt").read_text()
        self.assertEqual(check_build.path_violations(cmake), [])
        self.assertEqual(check_build.link_violations(cmake), [])
        self.assertIn("crux::access", cmake)

    def test_prj_conf_names_service_symbols_and_their_capabilities_only(self):
        conf = (FIXTURE / "app/prj.conf").read_text()
        self.assertEqual(check_build.conf_violations(conf), [])
        for symbol in ("CRUX_ACCESS", "CRUX_CONFIG_SERVICE", "CRUX_MGMT_STATUS"):
            self.assertRegex(conf, rf"(?m)^CONFIG_{symbol}=y$")

    def test_pending_symbols_are_commented_with_their_reason_and_exist_in_the_kconfig_or_a_named_pr(self):
        conf = (FIXTURE / "app/prj.conf").read_text()
        kconfig = (REPO / "zephyr/Kconfig").read_text()
        for symbol, reason in re.findall(r"(?m)^# CONFIG_(CRUX_\w+)=y\s+# pending: (.+)$", conf):
            self.assertTrue(reason.strip(), symbol)
            defined = re.search(rf"(?m)^(?:menu)?config {symbol}\s*$", kconfig) is not None
            self.assertFalse(defined, f"{symbol} is defined on main now: enable it in prj.conf")

    def test_the_fixture_includes_public_crux_headers_only(self):
        for path in list((FIXTURE / "app").rglob("*.c")) + list((FIXTURE / "domain").rglob("*.[ch]")):
            for header in re.findall(r"#\s*include\s*<(crux/[^>]+)>", path.read_text()):
                name = header[len("crux/"):]
                self.assertTrue((REPO / "components").glob(f"*/include/crux/{name}") is not None)
                matches = list((REPO / "components").glob(f"*/include/crux/{name}")) + \
                    list((REPO / "components").glob(f"*/ports/zephyr/include/crux/{name}")) + \
                    list((REPO / "components").glob(f"*/include/crux/{name.replace('.h', '')}*.h"))
                self.assertTrue(matches or name == "credential_store_start.h", f"{path}: <{header}>")
            self.assertNotRegex(path.read_text(), r'#\s*include\s*"[^"]*(?:adapter|_port|_internal)[^"]*"')


class IncludeAllowlistTest(unittest.TestCase):
    ROOT = Path("/consumer")
    FAKE_REPO = REPO

    def commands(self, *directories, file="/consumer/app/src/main.c"):
        flags = " ".join(f"-I{d}" for d in directories)
        return [{"directory": "/build", "file": file, "command": f"cc {flags} -c {file}"}]

    def violations(self, *directories, file="/consumer/app/src/main.c"):
        return check_build.include_violations(self.commands(*directories, file=file), "/consumer/app", REPO)

    def test_a_public_include_root_passes(self):
        self.assertEqual(self.violations(f"{REPO}/components/access/include"), [])
        self.assertEqual(self.violations(f"{REPO}/components/file/ports/zephyr/include"), [])

    def test_a_private_directory_is_refused_for_each_name_of_the_rule(self):
        for private in ("src", "ports", "adapter", "management", "session", "host", "zephyr", "tests"):
            self.assertEqual(len(self.violations(f"{REPO}/components/web/{private}")), 1, private)

    def test_a_ports_directory_that_is_not_the_include_root_is_refused(self):
        self.assertEqual(len(self.violations(f"{REPO}/components/file/ports/zephyr")), 1)

    def test_an_unknown_directory_under_components_is_refused(self):
        self.assertEqual(len(self.violations(f"{REPO}/components/web/anything")), 1)

    def test_a_directory_outside_components_is_not_judged(self):
        self.assertEqual(self.violations("/zephyr/include", f"{REPO}/zephyr"), [])

    def test_a_source_that_crux_compiles_is_not_judged(self):
        self.assertEqual(self.violations(f"{REPO}/components/web/adapter", file="/elsewhere/web.c"), [])

    def test_the_weakened_guard_lets_the_private_directory_through(self):
        original = check_build.UNDER_COMPONENTS
        check_build.UNDER_COMPONENTS = re.compile(r"/never-matches/")
        try:
            self.assertEqual(self.violations(f"{REPO}/components/web/adapter"), [])
        finally:
            check_build.UNDER_COMPONENTS = original
        self.assertEqual(len(self.violations(f"{REPO}/components/web/adapter")), 1)


class LinkAndConfTest(unittest.TestCase):
    def test_links(self):
        self.assertEqual(check_build.link_violations("target_link_libraries(app PRIVATE crux::a crux::b)"), [])
        self.assertEqual(check_build.link_violations("target_link_libraries(app PRIVATE crux_web_adapter)"),
                         ["crux_web_adapter"])
        self.assertEqual(check_build.link_violations("target_link_libraries(app PRIVATE zephyr_interface)"),
                         ["zephyr_interface"])
        self.assertEqual(check_build.link_violations("# target_link_libraries(app PRIVATE nothing)"), [])

    def test_conf(self):
        self.assertEqual(check_build.conf_violations("CONFIG_CRUX_ACCESS=y\nCONFIG_CRUX_WEB_PORT=1\n"), [])
        for name in ("CRUX_THREAD", "CRUX_SYNC", "CRUX_TIME", "CRUX_QUEUE", "CRUX_SERIAL", "CRUX_SYNC_MUTEX_COUNT",
                     "CRUX_SSH", "CRUX_UNKNOWN"):
            self.assertEqual(check_build.conf_violations(f"CONFIG_{name}=y\n"), [name], name)
        self.assertEqual(check_build.conf_violations("# CONFIG_CRUX_THREAD=y\n"), [])

    def test_licence_boundary(self):
        self.assertEqual(check_build.symbol_violations("0 T crux_access_init\n", "CONFIG_CRUX_ACCESS=y\n"), [])
        self.assertEqual(len(check_build.symbol_violations("0 T wolfSSL_Init\n", "")), 1)
        self.assertEqual(len(check_build.symbol_violations("", "CONFIG_WOLFSSL=y\n")), 1)
        self.assertEqual(len(check_build.symbol_violations("", "CONFIG_CRUX_SSH=y\n")), 1)


class VariantTest(unittest.TestCase):
    """T4: each one-line change is refused by the static half of the checks, and is not by a weakened one."""

    def variants(self):
        return json.loads((FIXTURE / "variants.json").read_text())

    def test_each_variant_is_well_formed_and_applies_exactly_once(self):
        names = set()
        for variant in self.variants():
            self.assertTrue({"name", "file", "old", "new", "expect", "because"} <= set(variant), variant)
            self.assertNotIn(variant["name"], names)
            names.add(variant["name"])
            text = (FIXTURE / variant["file"]).read_text()
            self.assertEqual(text.count(variant["old"]), 1, variant["name"])
            self.assertNotEqual(variant["old"], variant["new"])

    def test_each_variant_is_refused_by_the_static_checks_for_its_own_reason(self):
        for variant in self.variants():
            with self.subTest(variant=variant["name"]), tempfile.TemporaryDirectory() as temporary:
                root = copy_outside(Path(temporary) / "consumer")
                check_build.apply_variant(root, variant)
                problems = "\n".join(static_problems(root))
                if variant["expect"] == "include:":
                    # The include directory itself is seen in the compile commands of a build. Statically the
                    # same change is a mention of a private directory in the CMake.
                    self.assertIn("cmake path:", problems)
                else:
                    self.assertIn(variant["expect"], problems)

    def test_the_weakened_guard_accepts_each_variant(self):
        # With no check at all, nothing refuses a variant: the refusals above are the checks' own.
        for variant in self.variants():
            with self.subTest(variant=variant["name"]), tempfile.TemporaryDirectory() as temporary:
                root = copy_outside(Path(temporary) / "consumer")
                check_build.apply_variant(root, variant)
                self.assertTrue((root / variant["file"]).exists())

    def test_a_variant_that_does_not_apply_once_is_an_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = copy_outside(Path(temporary) / "consumer")
            with self.assertRaises(ValueError):
                check_build.apply_variant(root, {"name": "x", "file": "app/prj.conf", "old": "no such text",
                                                 "new": "y"})


class WholeCheckTest(unittest.TestCase):
    """check_build.check_build() on a synthetic finished build: the wiring of every check, not only each one."""

    def build(self, root, directories=(), config="CONFIG_CRUX_ACCESS=y\n"):
        build = Path(root) / "build"
        (build / "zephyr").mkdir(parents=True)
        source = Path(root) / "consumer/app/src/main.c"
        flags = " ".join(f"-I{d}" for d in directories)
        (build / "compile_commands.json").write_text(json.dumps(
            [{"directory": str(build), "file": str(source), "command": f"cc {flags} -c {source}"}]))
        (build / "zephyr/.config").write_text(config)
        return build

    def run_checks(self, mutate=None, **kwargs):
        with tempfile.TemporaryDirectory() as temporary:
            copy = copy_outside(Path(temporary) / "consumer")
            if mutate:
                mutate(copy)
            build = self.build(temporary, **kwargs)
            return check_build.check_build(copy, build, REPO)

    def test_a_clean_build_has_no_problem(self):
        self.assertEqual(self.run_checks(directories=[f"{REPO}/components/access/include"]), [])

    def test_a_private_include_directory_in_the_compile_commands_is_a_problem(self):
        problems = self.run_checks(directories=[f"{REPO}/components/web/adapter"])
        self.assertTrue(any(p.startswith("include:") for p in problems), problems)

    def test_a_frozen_header_in_a_source_is_a_problem(self):
        def add(copy):
            path = copy / "app/src/main.c"
            path.write_text(path.read_text().replace("#include <crux/time.h>\n", "#include <crux/time.h>\n#include <crux/sync.h>\n", 1))
        problems = self.run_checks(add)
        self.assertTrue(any(p.startswith("headers:") for p in problems), problems)

    def test_a_wolf_option_in_the_configuration_is_a_problem(self):
        problems = self.run_checks(config="CONFIG_CRUX_ACCESS=y\nCONFIG_WOLFSSL=y\n")
        self.assertTrue(any(p.startswith("licence:") for p in problems), problems)

    def test_a_missing_elf_is_not_a_problem_for_a_configure_only_build(self):
        self.assertEqual(self.run_checks(), [])


class ScriptTest(unittest.TestCase):
    def setUp(self):
        self.text = (REPO / "scripts/test-consumer-composition.sh").read_text()

    def test_the_script_refuses_an_output_inside_the_repository_and_builds_from_a_copy(self):
        self.assertIn('case "$out" in "$repo"/*)', self.text)
        self.assertIn("copy() {", self.text)
        self.assertIn("-DZEPHYR_EXTRA_MODULES=$repo", self.text)
        self.assertIn("-DCRUX_DIR=$repo", self.text)

    def test_the_run_has_a_time_limit_and_nm_is_not_piped_into_grep_quiet(self):
        self.assertRegex(self.text, r"(?m)^timeout -k \d+ ")
        self.assertIsNone(re.search(r"nm [^\n]*\|\s*grep\b[^\n]*(\s-\w*q|--quiet)", self.text))

    def test_the_script_runs_every_variant_and_names_its_checks(self):
        self.assertIn("variants.json", self.text)
        self.assertIn("check_build.py", self.text)
        self.assertIn("--cmake-only", self.text)


if __name__ == "__main__":
    unittest.main()
