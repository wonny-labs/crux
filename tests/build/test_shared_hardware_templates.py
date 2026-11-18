"""Check the shared hardware templates: the organisation manifest, the hardware module and their guide.

The structure tests need only Python. The manifest tests need PyYAML, and the workspace tests run
real west on local throwaway repositories, so that `west crux-pins` is seen classifying a module that
arrives through an organisation manifest. Nothing here builds with Zephyr.
"""
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

try:
    # west depends on it. The Host CI job installs both into the venv that it runs python3 from.
    import yaml
except ImportError:
    yaml = None

REPO = Path(__file__).resolve().parents[2]
GUIDE = REPO / "docs/shared-hardware-modules.md"
ORG = REPO / "templates/organisation-manifest"
ORG_MANIFEST = ORG / "west.yml"
PRODUCT_MANIFEST = ORG / "product-y/west.yml"
MODULE = REPO / "templates/hardware-module"
MODULE_CI_MANIFEST = MODULE / "ci/west.yml"
COMMAND = REPO / "scripts/west_commands/crux_pins.py"
COMMAND_LIST = REPO / "scripts/west-commands.yml"
WEST = shutil.which("west")
GIT = shutil.which("git")

BOARD = "acmeco_ctrl_a"
BOARD_DIR = MODULE / "boards/acmeco/ctrl_a"
PREFIX = "acmeco"
PUBLIC_BASE = "https://github.com/wonny-labs/"
INTERNAL_BASE = "https://git.example/scm/acme/"
UPSTREAM_BASE = "https://github.com/zephyrproject-rtos/"
ALLOWED_BASES = (PUBLIC_BASE, INTERNAL_BASE, UPSTREAM_BASE)
SHA = re.compile(r"[0-9a-f]{40}")


def allowed_url(url):
    """A remote's url-base has no trailing slash, so accept a base exactly or anything below it."""
    return any(url == base.rstrip("/") or url.startswith(base) for base in ALLOWED_BASES)


def load_pins():
    # Loaded by path and without west, as in test_crux_pins.py.
    spec = importlib.util.spec_from_file_location("crux_pins", COMMAND)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def with_examples(text):
    """Uncomment the manifest examples. A comment line holding only # opens one, as in the product template."""
    lines = []
    inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "#":
            inside = True
        elif inside and stripped.startswith("# "):
            lines.append(line[:line.index("#")] + stripped[2:])
        else:
            inside = False
            lines.append(line)
    return "\n".join(lines) + "\n"


def template_files(root):
    return sorted(path for path in root.rglob("*") if path.is_file())


class OrganisationManifestStructureTest(unittest.TestCase):
    def test_the_template_holds_the_organisation_and_product_manifests_and_a_readme(self):
        for path in (ORG_MANIFEST, PRODUCT_MANIFEST, ORG / "README.md"):
            with self.subTest(path=path.relative_to(REPO)):
                self.assertTrue(path.is_file())

    def test_the_readme_covers_what_a_reader_needs_to_choose_the_layer(self):
        text = (ORG / "README.md").read_text()
        for phrase in ("first definition", "name-allowlist", "name-blocklist", "crux-override",
                       "group-filter", "two or more products", "west crux-pins"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_urls_are_public_or_on_the_fictional_host(self):
        for path in (ORG_MANIFEST, PRODUCT_MANIFEST, MODULE_CI_MANIFEST):
            for url in re.findall(r"https?://[^\s\"')>]+", path.read_text()):
                with self.subTest(path=path.name, url=url):
                    self.assertTrue(allowed_url(url), url)
            self.assertNotRegex(path.read_text(), r"git@|ssh://")


class HardwareModuleStructureTest(unittest.TestCase):
    REQUIRED = (
        "README.md", "zephyr/module.yml", "CMakeLists.txt", "Kconfig",
        "dts/bindings/vendor-prefixes.txt", "drivers/CMakeLists.txt", "drivers/Kconfig",
        "ci/west.yml", "ci/build.yml",
        f"boards/acmeco/ctrl_a/board.yml", f"boards/acmeco/ctrl_a/board.cmake",
        f"boards/acmeco/ctrl_a/Kconfig.{BOARD}", f"boards/acmeco/ctrl_a/{BOARD}_defconfig",
        f"boards/acmeco/ctrl_a/{BOARD}.dts", f"boards/acmeco/ctrl_a/{BOARD}.yaml",
        "tests/module/smoke/CMakeLists.txt", "tests/module/smoke/prj.conf",
        "tests/module/smoke/testcase.yaml", "tests/module/smoke/src/main.c",
    )

    def test_the_skeleton_has_every_required_file(self):
        for relative in self.REQUIRED:
            with self.subTest(path=relative):
                self.assertTrue((MODULE / relative).is_file())

    def test_module_yml_exports_build_files_board_and_dts_roots_and_tests(self):
        text = (MODULE / "zephyr/module.yml").read_text()
        self.assertRegex(text, r"(?m)^name: acme-hw$")
        for key in ("cmake: .", "kconfig: Kconfig", "board_root: .", "dts_root: .", "tests:"):
            with self.subTest(key=key):
                self.assertIn(key, text)

    def test_cmake_wiring_adds_drivers_and_shows_named_libraries_as_a_comment_until_a_driver_moves_in(self):
        self.assertIn("add_subdirectory(drivers)", (MODULE / "CMakeLists.txt").read_text())
        drivers = (MODULE / "drivers/CMakeLists.txt").read_text()
        named = [line for line in drivers.splitlines() if "zephyr_library_named(" in line]
        self.assertTrue(named, "the example block names its library")
        for line in named:
            with self.subTest(line=line):
                self.assertTrue(line.lstrip().startswith("#"), "no driver yet, so the block is a comment")
        active = [line for line in drivers.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(active, [], "the module builds no library until the first driver arrives")

    def test_url_check_refuses_a_lookalike_owner(self):
        self.assertTrue(allowed_url("https://github.com/wonny-labs"))
        self.assertTrue(allowed_url("https://github.com/wonny-labs/crux-pilot"))
        self.assertFalse(allowed_url("https://github.com/wonny-labs-other/crux-pilot"))
        self.assertFalse(allowed_url("https://git.example/scm/acme-other"))

    def test_kconfig_sources_the_driver_menu(self):
        self.assertIn('rsource "drivers/Kconfig"', (MODULE / "Kconfig").read_text())

    def test_vendor_prefix_is_fictional_and_not_the_real_acme_prefix(self):
        entries = [line.split("\t") for line in
                   (MODULE / "dts/bindings/vendor-prefixes.txt").read_text().splitlines()
                   if line and not line.startswith("#")]
        self.assertEqual([PREFIX], [entry[0] for entry in entries])
        # Zephyr's own list already gives "acme" to a real company.
        self.assertNotIn("acme", [entry[0] for entry in entries])

    def test_the_board_has_its_own_name_and_does_not_extend_another(self):
        text = (BOARD_DIR / "board.yml").read_text()
        self.assertRegex(text, rf"(?m)^\s+name: {BOARD}$")
        self.assertRegex(text, r"(?m)^\s+full_name: \S")
        self.assertRegex(text, rf"(?m)^\s+vendor: {PREFIX}$")
        self.assertNotRegex(text, r"(?m)^\s*extend:")
        self.assertNotIn("mimxrt1060_evk", text)

    def test_board_kconfig_twister_and_dts_agree_on_the_name(self):
        self.assertIn(f"config BOARD_{BOARD.upper()}", (BOARD_DIR / f"Kconfig.{BOARD}").read_text())
        self.assertRegex((BOARD_DIR / f"{BOARD}.yaml").read_text(), rf"(?m)^identifier: {BOARD}$")
        dts = (BOARD_DIR / f"{BOARD}.dts").read_text()
        self.assertIn(f'compatible = "{PREFIX},ctrl-a"', dts)
        self.assertIn("zephyr,console", dts)

    def test_smoke_test_runs_on_native_sim_and_builds_the_board(self):
        text = (MODULE / "tests/module/smoke/testcase.yaml").read_text()
        self.assertIn("native_sim", text)
        self.assertIn(BOARD, text)

    def test_ci_template_is_outside_dot_github_and_runs_twister_and_the_cross_build(self):
        self.assertFalse((MODULE / ".github").exists())
        text = (MODULE / "ci/build.yml").read_text()
        for phrase in ("west twister", "native_sim", BOARD, "west init -l --mf ci/west.yml"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_readme_defers_the_example_driver_to_the_product_driver_kit(self):
        text = (MODULE / "README.md").read_text()
        self.assertIn("writing-a-product-driver.md", text)
        self.assertIn("ZEPHYR_EXTRA_MODULES", text)

    def test_sources_carry_an_spdx_header(self):
        kinds = (".c", ".h", ".dts", ".dtsi", ".cmake", ".txt", ".yml", ".yaml", ".conf")
        for path in template_files(MODULE):
            if path.name == "vendor-prefixes.txt":
                continue
            if path.suffix in kinds or path.name.startswith("Kconfig") or path.name.endswith("_defconfig"):
                with self.subTest(path=path.relative_to(REPO)):
                    self.assertIn("SPDX-License-Identifier: Apache-2.0", path.read_text()[:400])


class GuideTest(unittest.TestCase):
    def setUp(self):
        self.text = GUIDE.read_text()

    def test_guide_names_the_three_layers_and_the_decision_table(self):
        for phrase in ("Product repository", "Organisation hardware module", "Upstream Zephyr",
                       "Where does this board or driver live"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_guide_covers_every_topic_of_the_work_package(self):
        for phrase in ("second product", "compatible", "Zephyr baseline", "native_sim", "licence",
                       "west crux-pins", "firmware_identity", "SBOM", "sysbuild", "MCUboot",
                       "ZEPHYR_EXTRA_MODULES", "board: extend:", "ADR-0001"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_guide_links_the_zephyr_documents_it_relies_on(self):
        for path in ("doc/develop/modules.rst", "doc/develop/west/workspaces.rst",
                     "doc/hardware/porting/board_porting.rst"):
            with self.subTest(path=path):
                self.assertIn(path, self.text)

    def test_guide_links_existing_sections_of_the_composition_guide(self):
        headings = re.findall(r"(?m)^#+ (.+)$", (REPO / "docs/product-composition.md").read_text())
        anchors = {re.sub(r"[^a-z0-9 -]", "", heading.lower()).replace(" ", "-") for heading in headings}
        cited = re.findall(r"product-composition\.md#([a-z0-9-]+)", self.text)
        self.assertTrue(cited)
        for anchor in cited:
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, anchors)

    def test_index_and_composition_guide_point_to_the_new_guide(self):
        for path in ("docs/README.md", "docs/product-composition.md"):
            with self.subTest(path=path):
                self.assertIn("shared-hardware-modules.md", (REPO / path).read_text())


class PinClassificationTest(unittest.TestCase):
    """The pure comparison sees an organisation module like any project outside the contract."""

    def setUp(self):
        self.pins = load_pins()

    def test_projects_of_the_organisation_layer_are_product(self):
        sha = "d" * 40
        projects = [{"name": name, "revision": sha, "active": True, "userdata": None}
                    for name in ("acme-manifest", "acme-hw")]
        results = self.pins.compare_pins({"zephyr": "z" * 40}, projects, lambda name, rev, role: sha)
        self.assertEqual([("PRODUCT", "acme-manifest"), ("PRODUCT", "acme-hw")],
                         [(r["status"], r["name"]) for r in results])


@unittest.skipUnless(yaml, "PyYAML is required to parse the manifests; west installs it")
class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.org = yaml.safe_load(ORG_MANIFEST.read_text())["manifest"]
        self.product = yaml.safe_load(PRODUCT_MANIFEST.read_text())["manifest"]
        self.module_ci = yaml.safe_load(MODULE_CI_MANIFEST.read_text())["manifest"]
        self.crux = yaml.safe_load((REPO / "west.yml").read_text())["manifest"]

    @staticmethod
    def by_name(manifest):
        return {entry["name"]: entry for entry in manifest["projects"]}

    def test_organisation_manifest_imports_crux_and_pins_the_module(self):
        projects = self.by_name(self.org)
        self.assertIs(True, projects["crux-pilot"]["import"])
        module = projects["acme-hw"]
        self.assertRegex(str(module["revision"]), SHA)
        self.assertNotIn("import", module)
        self.assertEqual("acme-manifest", self.org["self"]["path"])

    def test_organisation_manifest_repeats_no_crux_pin(self):
        pinned = {entry["name"] for entry in self.crux["projects"]}
        zephyr = next(entry for entry in self.crux["projects"] if entry["name"] == "zephyr")
        pinned.update(zephyr["import"]["name-allowlist"])
        self.assertEqual(set(), (set(self.by_name(self.org)) - {"crux-pilot"}) & pinned)

    def test_product_imports_the_organisation_manifest_and_not_crux(self):
        projects = self.by_name(self.product)
        self.assertIs(True, projects["acme-manifest"]["import"])
        self.assertNotIn("crux-pilot", projects)
        self.assertNotIn("acme-hw", projects)
        self.assertEqual("product-y", self.product["self"]["path"])

    def test_module_ci_manifest_imports_the_organisation_and_blocks_its_own_copy(self):
        projects = self.by_name(self.module_ci)
        self.assertEqual({"name-blocklist": ["acme-hw"]}, projects["acme-manifest"]["import"])
        self.assertEqual("acme-hw", self.module_ci["self"]["path"])

    def test_commented_examples_parse(self):
        for path in (ORG_MANIFEST, PRODUCT_MANIFEST):
            with self.subTest(path=path.name):
                examples = yaml.safe_load(with_examples(path.read_text()))["manifest"]
                self.assertGreater(len(examples["projects"]), len(
                    yaml.safe_load(path.read_text())["manifest"]["projects"]))
                self.assertIn("group-filter", examples)


def pin(text, name, revision):
    """Replace the revision of an uncommented project entry, as a release would pin it."""
    pattern = rf"(?m)^([ ]+- name: {re.escape(name)}\n(?:[ ]+[a-z-]+:.*\n)*?[ ]+revision: )\S+"
    replaced, count = re.subn(pattern, rf"\g<1>{revision}", text)
    if count != 1:
        raise AssertionError(f"expected one active entry for {name}, found {count}")
    return replaced


def git(directory, *arguments, env=None):
    return subprocess.run(["git", "-C", str(directory), *arguments], check=True,
                          capture_output=True, text=True, env=env).stdout.strip()


@unittest.skipUnless(WEST and GIT and yaml, "west, git and PyYAML are required for the workspace tests")
class OrganisationWorkspaceTest(unittest.TestCase):
    """Run the templates through real west. Local repositories stand in for every remote."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="crux-shared-hw-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for name in ("config", "public", "internal", "upstream"):
            (self.root / name).mkdir()
        git_config = self.root / "config/gitconfig"
        git_config.write_text(
            "[user]\n\tname = Shared HW Test\n\temail = shared-hw@example.invalid\n"
            "[init]\n\tdefaultBranch = main\n"
            "[protocol \"file\"]\n\tallow = always\n"
            f'[url "{(self.root / "public").as_uri()}/"]\n\tinsteadOf = {PUBLIC_BASE}\n'
            f'[url "{(self.root / "internal").as_uri()}/"]\n\tinsteadOf = {INTERNAL_BASE}\n'
            f'[url "{(self.root / "upstream").as_uri()}/"]\n\tinsteadOf = {UPSTREAM_BASE}\n')
        # GIT_ALLOW_PROTOCOL makes a rule that fails to apply an error, never a network call.
        self.env = {**os.environ, "GIT_CONFIG_GLOBAL": str(git_config),
                    "GIT_CONFIG_SYSTEM": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_ALLOW_PROTOCOL": "file",
                    "WEST_CONFIG_GLOBAL": str(self.root / "config/westconfig"),
                    "WEST_CONFIG_SYSTEM": str(self.root / "config/west-system")}
        self.env.pop("WEST_CONFIG_LOCAL", None)
        self.env.pop("ZEPHYR_BASE", None)
        self.build_upstream()

    def commit(self, directory, files, message, tag=None):
        for name, content in files.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        git(directory, "add", "-A", env=self.env)
        git(directory, "commit", "-q", "-m", message, env=self.env)
        if tag:
            git(directory, "tag", tag, env=self.env)
        return git(directory, "rev-parse", "HEAD", env=self.env)

    def init(self, relative):
        directory = self.root / relative
        directory.mkdir(parents=True)
        git(directory, "init", "-q", env=self.env)
        return directory

    def build_upstream(self):
        module = self.init("upstream/fake-module")
        self.module_v1 = self.commit(module, {"m.txt": "1"}, "module one")
        self.module_v2 = self.commit(module, {"m.txt": "2"}, "module two")
        zephyr = self.init("upstream/zephyr")
        self.zephyr = self.commit(zephyr, {"west.yml": (
            "manifest:\n"
            "  projects:\n"
            "    - name: fake-module\n"
            f"      url: {UPSTREAM_BASE}fake-module\n"
            f"      revision: {self.module_v1}\n"
            "      path: modules/fake\n"
            "  self:\n"
            "    path: zephyr\n")}, "zephyr")
        crux = self.init("public/crux-pilot")
        shutil.copytree(REPO / "scripts/west_commands", crux / "scripts/west_commands")
        shutil.copy(COMMAND_LIST, crux / "scripts/west-commands.yml")
        self.crux = self.commit(crux, {"west.yml": (
            "manifest:\n"
            "  projects:\n"
            "    - name: zephyr\n"
            f"      url: {UPSTREAM_BASE}zephyr\n"
            f"      revision: {self.zephyr}\n"
            "      import:\n"
            "        name-allowlist: [fake-module]\n"
            "  self:\n"
            "    path: crux-pilot\n"
            "    west-commands: scripts/west-commands.yml\n")}, "crux manifest")
        hardware = self.init("internal/acme-hw")
        self.hw_v1 = self.commit(hardware, {"zephyr/module.yml": "name: acme-hw\n"}, "hw one", tag="v1.0.0")
        self.hw_v2 = self.commit(hardware, {"README.md": "two\n"}, "hw two", tag="v1.1.0")
        self.org_repo = self.init("internal/acme-manifest")
        self.org = self.publish_org(ORG_MANIFEST.read_text())

    def publish_org(self, text, extra_projects=""):
        text = pin(pin(text, "crux-pilot", self.crux), "acme-hw", self.hw_v1)
        if extra_projects:
            text = text.replace("\n  self:\n", "\n" + extra_projects + "\n  self:\n", 1)
        return self.commit(self.org_repo, {"west.yml": text}, "organisation manifest")

    def product(self, text=None, org_revision=None, extra_projects=""):
        text = text if text is not None else PRODUCT_MANIFEST.read_text()
        text = pin(text, "acme-manifest", org_revision or self.org)
        if extra_projects:
            text = text.replace("\n  self:\n", "\n" + extra_projects + "\n  self:\n", 1)
        workspace = self.root / "workspace"
        shutil.rmtree(workspace, ignore_errors=True)
        directory = workspace / "product-y"
        directory.mkdir(parents=True)
        git(directory, "init", "-q", env=self.env)
        (directory / "west.yml").write_text(text)
        git(directory, "add", "west.yml", env=self.env)
        git(directory, "commit", "-q", "-m", "product manifest", env=self.env)
        self.west("init", "-l", str(directory), cwd=workspace, check=True)
        self.west("update", cwd=workspace, check=True)
        return workspace

    def west(self, *arguments, cwd, check=False):
        result = subprocess.run(["west", *arguments], cwd=cwd, env=self.env, capture_output=True, text=True)
        if check and result.returncode:
            self.fail(f"west {' '.join(arguments)} failed:\n{result.stdout}\n{result.stderr}")
        return result

    def projects(self, workspace):
        listing = self.west("list", "-f", "{name} {path} {sha}", cwd=workspace, check=True).stdout
        return {line.split()[0]: line.split()[1:] for line in listing.splitlines()}

    def test_the_product_manifest_validates_and_resolves_all_three_layers(self):
        workspace = self.product()
        self.west("manifest", "--validate", cwd=workspace, check=True)
        projects = self.projects(workspace)
        for name in ("acme-manifest", "acme-hw", "crux-pilot", "zephyr", "fake-module"):
            with self.subTest(name=name):
                self.assertIn(name, projects)
        self.assertEqual(self.hw_v1, projects["acme-hw"][1])

    def test_crux_pins_reports_the_organisation_layer_as_product(self):
        result = self.west("crux-pins", cwd=self.product())
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(f"CONTRACT crux-pilot {self.crux[:12]}\n", result.stdout)
        self.assertIn(f"OK zephyr {self.zephyr[:12]}", result.stdout)
        self.assertIn(f"OK fake-module {self.module_v1[:12]}", result.stdout)
        self.assertIn(f"PRODUCT acme-manifest {self.org[:12]}", result.stdout)
        self.assertIn(f"PRODUCT acme-hw {self.hw_v1[:12]}", result.stdout)

    def test_an_override_declared_in_the_organisation_manifest_reaches_the_product(self):
        override = ("    - name: fake-module\n"
                    f"      url: {UPSTREAM_BASE}fake-module\n"
                    f"      revision: {self.module_v2}\n"
                    "      path: modules/fake\n"
                    "      userdata:\n"
                    "        crux-override: \"acme fix 7, drop when upstream has it\"")
        result = self.west("crux-pins", cwd=self.product(org_revision=self.publish_org(
            ORG_MANIFEST.read_text(), override)))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(f"OVERRIDE fake-module {self.module_v2[:12]} (contract {self.module_v1[:12]}): "
                      "acme fix 7, drop when upstream has it", result.stdout)

    def test_an_organisation_difference_without_a_reason_fails_the_product(self):
        drift = ("    - name: fake-module\n"
                 f"      url: {UPSTREAM_BASE}fake-module\n"
                 f"      revision: {self.module_v2}\n"
                 "      path: modules/fake")
        result = self.west("crux-pins", cwd=self.product(org_revision=self.publish_org(
            ORG_MANIFEST.read_text(), drift)))
        self.assertNotEqual(0, result.returncode)
        self.assertIn(f"MISMATCH fake-module {self.module_v2[:12]} (contract {self.module_v1[:12]})",
                      result.stdout)

    def test_a_product_that_moves_the_module_pin_is_still_product_and_passes(self):
        # Finding for the owner: west crux-pins checks the Crux contract only. A product that
        # leaves the organisation's module pin is not reported, so an organisation check owns it.
        moved = ("    - name: acme-hw\n"
                 "      remote: acme\n"
                 f"      revision: {self.hw_v2}\n"
                 "      path: modules/acme/acme-hw")
        workspace = self.product(extra_projects=moved)
        result = self.west("crux-pins", cwd=workspace)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(f"PRODUCT acme-hw {self.hw_v2[:12]}", result.stdout)

    def test_a_blocklist_on_the_organisation_import_also_filters_what_it_imports(self):
        text = PRODUCT_MANIFEST.read_text().replace(
            "      import: true\n", "      import:\n        name-blocklist: [acme-hw, fake-module]\n", 1)
        projects = self.projects(self.product(text=text))
        self.assertNotIn("acme-hw", projects)
        self.assertNotIn("fake-module", projects)
        self.assertIn("crux-pilot", projects)

    def test_the_module_ci_manifest_blocks_the_organisation_copy_of_the_module(self):
        workspace = self.root / "module-ci"
        directory = workspace / "acme-hw"
        directory.mkdir(parents=True)
        git(directory, "init", "-q", env=self.env)
        text = pin(MODULE_CI_MANIFEST.read_text(), "acme-manifest", self.org)
        self.commit(directory, {"ci/west.yml": text, "zephyr/module.yml": "name: acme-hw\n"}, "module")
        self.west("init", "-l", "--mf", "ci/west.yml", str(directory), cwd=workspace, check=True)
        self.west("update", cwd=workspace, check=True)
        projects = self.projects(workspace)
        self.assertEqual("acme-hw", projects["manifest"][0])
        self.assertNotIn("acme-hw", projects)
        self.assertIn("crux-pilot", projects)
        result = self.west("crux-pins", cwd=workspace)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(f"OK fake-module {self.module_v1[:12]}", result.stdout)
        self.assertNotIn("acme-hw", result.stdout)


if __name__ == "__main__":
    unittest.main()
