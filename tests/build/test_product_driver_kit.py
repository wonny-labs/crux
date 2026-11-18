"""Check the product driver kit: the guide, the template module, the example driver and its tests.

These checks read files only. They need no west workspace, no Zephyr tree and no compiler, so Host
CI runs them. The build and the native_sim run of the example are done by
scripts/test-product-template.sh, which needs the Linux Dev Container.
"""
from pathlib import Path
import os
import re
import unittest

try:
    import yaml  # west depends on it. The Host CI job installs neither.
except ImportError:
    yaml = None

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "templates/product"
GUIDE = REPO / "docs/writing-a-product-driver.md"
SCRIPT = REPO / "scripts/test-product-template.sh"
DRIVER = TEMPLATE / "drivers/sensor/example_temp"
BINDING = TEMPLATE / "dts/bindings/sensor/vnd,example-temp.yaml"
BOARD = TEMPLATE / "boards/vnd/example_rt1062"
TESTS = TEMPLATE / "tests/drivers/sensor/example_temp"
KIT_README = TEMPLATE / "drivers/README.md"
LINK_PROBE = REPO / "tests/product_template_link"

# Every file that a team copies with the template and that the kit adds to it.
KIT_FILES = (
    "zephyr/module.yml",
    "CMakeLists.txt",
    "Kconfig",
    "drivers/README.md",
    "drivers/CMakeLists.txt",
    "drivers/Kconfig",
    "drivers/sensor/CMakeLists.txt",
    "drivers/sensor/Kconfig",
    "drivers/sensor/example_temp/CMakeLists.txt",
    "drivers/sensor/example_temp/Kconfig",
    "drivers/sensor/example_temp/example_temp.c",
    "drivers/sensor/example_temp/example_temp.h",
    "drivers/sensor/example_temp/example_temp_emul.c",
    "drivers/sensor/example_temp/example_temp_emul.h",
    "dts/bindings/vendor-prefixes.txt",
    "dts/bindings/sensor/vnd,example-temp.yaml",
    "boards/vnd/example_rt1062/board.yml",
    "boards/vnd/example_rt1062/Kconfig.example_rt1062",
    "boards/vnd/example_rt1062/CMakeLists.txt",
    "boards/vnd/example_rt1062/example_rt1062_mimxrt1062.dts",
    "boards/vnd/example_rt1062/example_rt1062_mimxrt1062_defconfig",
    "boards/vnd/example_rt1062/example_rt1062_mimxrt1062.yaml",
    "boards/vnd/example_rt1062/example_rt1062-pinctrl.dtsi",
    "tests/drivers/sensor/example_temp/CMakeLists.txt",
    "tests/drivers/sensor/example_temp/prj.conf",
    "tests/drivers/sensor/example_temp/testcase.yaml",
    "tests/drivers/sensor/example_temp/boards/native_sim.overlay",
    "tests/drivers/sensor/example_temp/boards/native_sim.conf",
    "tests/drivers/sensor/example_temp/boards/native_sim_64.overlay",
    "tests/drivers/sensor/example_temp/boards/native_sim_64.conf",
    "tests/drivers/sensor/example_temp/boards/mimxrt1060_evk_mimxrt1062_qspi_B.overlay",
    "tests/drivers/sensor/example_temp/src/emul_test.c",
    "tests/drivers/sensor/example_temp/src/hardware_test.c",
)

# A product name, a customer name, a person or an NDA item never belongs in this tree. Only generic
# markers can be listed here without naming anything. A reviewer scans the diff for the rest.
FORBIDDEN_IN_PUBLIC_TEXT = re.compile(r"codesys|\bnda\b|confidential|proprietary", re.IGNORECASE)


def kit_text_files():
    """Return every file of the kit that holds text, except the copied vendor boot data."""
    paths = [GUIDE]
    for name in KIT_FILES:
        paths.append(TEMPLATE / name)
    return [path for path in paths if path.is_file()]


def read(path):
    return Path(path).read_text()


def code(path):
    """Return a file without its comment lines, so that a rule is not tripped by the explanation."""
    return "\n".join(line for line in read(path).splitlines() if not line.lstrip().startswith("#"))


class KitFilesTest(unittest.TestCase):
    def test_every_file_of_the_kit_exists(self):
        for name in KIT_FILES:
            with self.subTest(name=name):
                self.assertTrue((TEMPLATE / name).is_file(), name)

    def test_the_guide_exists(self):
        self.assertTrue(GUIDE.is_file())

    def test_the_boot_configuration_block_of_the_example_board_is_present(self):
        # The board copies the flash configuration block of the vendor board, under its own names.
        self.assertTrue(list(BOARD.glob("*flexspi_nor_config.c")))
        self.assertTrue(list(BOARD.glob("*flexspi_nor_config.h")))

    def test_the_existing_template_files_are_unchanged_in_place(self):
        for name in ("west.yml", "RELEASE.md", ".gitignore", "check_domain_includes.py",
                     "app/CMakeLists.txt", "app/prj.conf", "app/src/main.c",
                     "domain/product_domain.c", "domain/product_domain.h", "domain/product_port.h"):
            with self.subTest(name=name):
                self.assertTrue((TEMPLATE / name).is_file())


class ModuleDeclarationTest(unittest.TestCase):
    def setUp(self):
        self.text = read(TEMPLATE / "zephyr/module.yml")

    def test_the_module_exports_its_cmake_and_kconfig_roots(self):
        self.assertRegex(self.text, r"(?m)^\s+cmake:\s+\.\s*$")
        self.assertRegex(self.text, r"(?m)^\s+kconfig:\s+Kconfig\s*$")

    def test_the_module_declares_the_board_and_devicetree_roots(self):
        self.assertRegex(self.text, r"(?m)^\s+board_root:\s+\.\s*$")
        self.assertRegex(self.text, r"(?m)^\s+dts_root:\s+\.\s*$")

    def test_the_module_points_twister_at_its_tests_and_boards(self):
        self.assertRegex(self.text, r"(?m)^tests:\s*\n\s+-\s+tests\s*$")
        self.assertRegex(self.text, r"(?m)^boards:\s*\n\s+-\s+boards\s*$")

    def test_the_module_has_a_name_that_does_not_depend_on_the_folder(self):
        self.assertRegex(self.text, r"(?m)^name:\s+product-x\s*$")

    @unittest.skipUnless(yaml, "needs PyYAML")
    def test_the_file_parses(self):
        data = yaml.safe_load(self.text)
        self.assertEqual(".", data["build"]["settings"]["board_root"])
        self.assertEqual(".", data["build"]["settings"]["dts_root"])
        self.assertEqual(["tests"], data["tests"])

    def test_the_module_cmake_and_kconfig_reach_the_driver_tree(self):
        self.assertIn("add_subdirectory(drivers)", read(TEMPLATE / "CMakeLists.txt"))
        self.assertIn('rsource "drivers/Kconfig"', read(TEMPLATE / "Kconfig"))

    def test_the_template_root_is_not_a_crux_module(self):
        # The example is a plain Zephyr module. It names no Crux target and no Crux option.
        for name in ("CMakeLists.txt", "Kconfig", "zephyr/module.yml"):
            with self.subTest(name=name):
                self.assertNotRegex(read(TEMPLATE / name), r"(?i)\bcrux\b")


class BindingTest(unittest.TestCase):
    def setUp(self):
        self.text = read(BINDING)

    def test_the_binding_uses_the_stand_in_vendor_prefix_and_standard_includes(self):
        self.assertRegex(self.text, r'(?m)^compatible:\s*"vnd,example-temp"\s*$')
        self.assertIn("i2c-device.yaml", self.text)
        self.assertIn("sensor-device.yaml", self.text)

    def test_the_binding_file_name_is_the_compatible(self):
        self.assertEqual("vnd,example-temp.yaml", BINDING.name)

    def test_the_local_vendor_prefix_file_is_parsed_the_way_zephyr_parses_it(self):
        # Zephyr's loader: blank lines and lines that start with # are skipped. Any other line is
        # <prefix><TAB><name>.
        for line in read(TEMPLATE / "dts/bindings/vendor-prefixes.txt").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            with self.subTest(line=line):
                self.assertEqual(2, len(stripped.split("\t", 1)))

    def test_the_crux_prefix_is_not_used_by_the_example(self):
        # crux is reserved for Crux. The example's compatible uses the stand-in vendor.
        self.assertNotIn("crux", self.text.lower())


class DriverTest(unittest.TestCase):
    def setUp(self):
        self.source = read(DRIVER / "example_temp.c")
        self.cmake = code(DRIVER / "CMakeLists.txt")
        self.kconfig = code(DRIVER / "Kconfig")

    def test_the_driver_is_bound_to_the_binding_by_its_compatible(self):
        self.assertRegex(self.source, r"(?m)^#define DT_DRV_COMPAT vnd_example_temp$")

    def test_the_driver_defines_one_device_per_enabled_node_with_a_const_api(self):
        self.assertIn("DEVICE_DT_INST_DEFINE", self.source)
        self.assertIn("DT_INST_FOREACH_STATUS_OKAY", self.source)
        self.assertRegex(self.source, r"DEVICE_API\(sensor,\s*\w+\)\s*=")

    def test_the_driver_names_an_init_level_and_a_priority(self):
        self.assertRegex(self.source, r"POST_KERNEL")
        self.assertRegex(self.source, r"CONFIG_SENSOR_INIT_PRIORITY")

    def test_the_driver_reports_errors_as_negative_errno_and_logs_them(self):
        for token in ("-ENODEV", "-EBUSY", "-ENOTSUP", "LOG_ERR(", "LOG_MODULE_REGISTER("):
            with self.subTest(token=token):
                self.assertIn(token, self.source)

    def test_the_driver_checks_the_part_identifier_and_the_bus(self):
        self.assertIn("i2c_is_ready_dt", self.source)
        self.assertIn("EXAMPLE_TEMP_ID", self.source)

    def test_the_driver_is_a_named_library_never_a_path_derived_one(self):
        self.assertRegex(self.cmake, r"zephyr_library_named\(\w+\)")
        self.assertNotRegex(self.cmake, r"zephyr_library\(\)")
        self.assertNotRegex(self.cmake, r"zephyr_library_amend")

    def test_the_driver_symbol_is_enabled_by_the_devicetree_node(self):
        self.assertRegex(self.kconfig, r"(?m)^\s+depends on DT_HAS_VND_EXAMPLE_TEMP_ENABLED$")
        self.assertRegex(self.kconfig, r"(?m)^\s+select I2C$")
        self.assertIn("EXAMPLE_TEMP_LOG_LEVEL", read(DRIVER / "Kconfig") + self.source)

    def test_the_emulator_is_built_only_with_the_emulator_option(self):
        self.assertRegex(self.cmake, r"zephyr_library_sources_ifdef\(CONFIG_EMUL_EXAMPLE_TEMP\s+"
                                      r"example_temp_emul\.c\)")
        self.assertRegex(self.kconfig, r"(?m)^\s+depends on EMUL$")

    def test_the_emulator_backs_the_sensor_emulation_api(self):
        emul = read(DRIVER / "example_temp_emul.c")
        self.assertIn("EMUL_DT_INST_DEFINE", emul)
        self.assertIn("emul_sensor_driver_api", emul)
        self.assertIn("i2c_emul_api", emul)

    def test_the_example_is_not_a_crux_interface(self):
        # ADR-0001: no HAL, no wrapper and no Crux device API. A product driver is plain Zephyr.
        for path in list(DRIVER.glob("*")) + list(TESTS.rglob("*")):
            if not path.is_file():
                continue
            with self.subTest(path=path.name):
                text = read(path)
                self.assertNotRegex(text, r"<crux/|\bcrux_\w+|\bCRUX_\w+")

    def test_the_driver_sources_carry_an_spdx_line_and_the_attribution_of_their_model(self):
        for name in ("example_temp.c", "example_temp.h", "example_temp_emul.c",
                     "example_temp_emul.h"):
            with self.subTest(name=name):
                head = "\n".join(read(DRIVER / name).splitlines()[:12])
                self.assertIn("SPDX-License-Identifier: Apache-2.0", head)
        self.assertIn("f75303", read(DRIVER / "example_temp.c"))
        self.assertIn("f75303", read(DRIVER / "example_temp_emul.c"))


class BoardTest(unittest.TestCase):
    def setUp(self):
        self.board_yml = code(BOARD / "board.yml")
        self.kconfig = code(BOARD / "Kconfig.example_rt1062")

    def test_the_board_has_its_own_name_and_is_not_an_extension_of_the_vendor_board(self):
        # A board that extends another keeps its name, so Crux would accept it as the vendor board.
        self.assertRegex(self.board_yml, r"(?m)^\s+name:\s+example_rt1062\s*$")
        self.assertNotRegex(self.board_yml, r"\bextend\b")
        self.assertNotIn("mimxrt1060_evk", self.board_yml)
        self.assertRegex(self.kconfig, r"(?m)^config BOARD_EXAMPLE_RT1062$")
        self.assertNotIn("BOARD_MIMXRT1060_EVK", self.kconfig)

    def test_the_board_names_its_vendor_with_the_stand_in_prefix(self):
        self.assertRegex(self.board_yml, r"(?m)^\s+vendor:\s+vnd\s*$")

    def test_no_file_of_the_board_is_named_after_the_vendor_board(self):
        for path in BOARD.iterdir():
            with self.subTest(path=path.name):
                self.assertNotIn("mimxrt1060_evk", path.name)

    def test_the_board_declares_the_i2c_bus_and_the_part_on_it(self):
        dts = read(BOARD / "example_rt1062_mimxrt1062.dts")
        self.assertRegex(dts, r'compatible = "vnd,example-temp";')
        self.assertRegex(dts, r"&lpi2c1\s*\{")
        self.assertRegex(dts, r"(?m)^\s+zephyr,console = &lpuart1;$")

    def test_the_board_has_its_own_twister_identifier(self):
        text = read(BOARD / "example_rt1062_mimxrt1062.yaml")
        self.assertRegex(text, r"(?m)^identifier:\s+example_rt1062/mimxrt1062\s*$")

    def test_copied_vendor_files_keep_their_licence_line(self):
        for path in BOARD.glob("*flexspi_nor_config.[ch]"):
            with self.subTest(path=path.name):
                self.assertIn("SPDX-License-Identifier: Apache-2.0", read(path))


class TestScenariosTest(unittest.TestCase):
    def setUp(self):
        self.text = read(TESTS / "testcase.yaml")

    def test_a_unit_scenario_runs_on_both_native_sim_platforms(self):
        self.assertRegex(self.text, r"(?m)^  product\.drivers\.sensor\.example_temp\.emul:\s*$")
        self.assertIn("native_sim", self.text)
        self.assertIn("native_sim/native/64", self.text)
        self.assertIn("harness: ztest", self.text)

    def test_a_hardware_scenario_is_gated_on_a_fixture_and_lists_both_boards(self):
        self.assertRegex(self.text, r"(?m)^  product\.drivers\.sensor\.example_temp\.hardware:\s*$")
        self.assertRegex(self.text, r"(?m)^\s+fixture:\s+example_temp_wired\s*$")
        self.assertIn("mimxrt1060_evk@B/mimxrt1062/qspi", self.text)
        self.assertIn("example_rt1062/mimxrt1062", self.text)

    def test_the_hardware_scenario_is_not_a_unit_scenario_on_a_simulator(self):
        scenario = self.text.split("example_temp.hardware:")[1]
        self.assertNotIn("native_sim", scenario)

    @unittest.skipUnless(yaml, "needs PyYAML")
    def test_the_file_parses(self):
        scenarios = yaml.safe_load(self.text)["tests"]
        unit = scenarios["product.drivers.sensor.example_temp.emul"]
        hardware = scenarios["product.drivers.sensor.example_temp.hardware"]
        self.assertEqual({"native_sim", "native_sim/native/64"}, set(unit["platform_allow"]))
        self.assertEqual("example_temp_wired", hardware["harness_config"]["fixture"])
        self.assertNotIn("build_only", hardware)

    def test_the_sources_split_by_scenario_through_the_emulator_option(self):
        cmake = read(TESTS / "CMakeLists.txt")
        self.assertIn("target_sources_ifdef(CONFIG_EMUL app PRIVATE src/emul_test.c)", cmake)
        self.assertIn("target_sources_ifndef(CONFIG_EMUL app PRIVATE src/hardware_test.c)", cmake)

    def test_the_unit_test_covers_the_error_paths(self):
        source = read(TESTS / "src/emul_test.c")
        for token in ("mock_api", "-EIO", "-EBUSY", "-ENODEV", "-ENOTSUP",
                      "emul_sensor_backend_set_channel", "ops.init"):
            with self.subTest(token=token):
                self.assertIn(token, source)

    def test_both_native_sim_platforms_get_the_same_board_files(self):
        # native_sim/native reads native_sim.*, native_sim/native/64 reads native_sim_64.*.
        boards = TESTS / "boards"
        for suffix in ("overlay", "conf"):
            with self.subTest(suffix=suffix):
                self.assertEqual(read(boards / f"native_sim.{suffix}"),
                                 read(boards / f"native_sim_64.{suffix}"))

    def test_the_unit_test_resets_the_bus_mock_after_each_test(self):
        source = read(TESTS / "src/emul_test.c")
        self.assertRegex(source, r"mock_api\s*=\s*NULL")

    def test_the_hardware_stub_says_that_it_needs_a_fixture_and_a_human_decision(self):
        source = read(TESTS / "src/hardware_test.c")
        self.assertIn("example_temp_wired", source)
        self.assertRegex(source, r"(?i)authoris")


class ScriptTest(unittest.TestCase):
    """The runner keeps everything it had and adds the build and the native_sim run of the kit."""

    def setUp(self):
        self.text = read(SCRIPT)
        # A command that continues on the next line is one command.
        self.commands = self.text.replace("\\\n", " ")

    def test_the_script_still_has_the_checks_it_had(self):
        for line in (
            "Usage: %s <validated-board-target>",
            'test_crux_pins.py -v',
            'test_product_template.py -v',
            '(cd "$workspace" && west crux-pins)',
            '(cd "$workspace" && west build -p always -b "$board" -d "$build" \\',
            '"$repo/templates/product/app" -- -DZEPHYR_EXTRA_MODULES="$repo")',
            "for output in zephyr.bin zephyr.meta; do",
            "Product template built for %s. No flash, reset, or hardware command was run.",
        ):
            with self.subTest(line=line):
                self.assertIn(line, self.text)

    def test_the_script_runs_the_kit_tests_and_twister_on_native_sim(self):
        self.assertIn("test_product_driver_kit.py", self.text)
        self.assertRegex(self.commands, r"west twister[^\n]*-p native_sim\b")
        self.assertIn("native_sim/native/64", self.text)
        self.assertIn('template="$repo/templates/product"', self.text)
        self.assertIn('-T "$template/tests"', self.text)

    def test_the_script_builds_the_hardware_scenarios_and_never_runs_them(self):
        self.assertRegex(self.commands, r"west twister[^\n]*--build-only")
        self.assertNotRegex(self.text, r"--device-testing|--device-serial|--hardware-map")
        self.assertNotRegex(self.text, r"\bwest (flash|debug|attach)\b")

    def test_the_script_proves_that_the_tests_ran_and_the_hardware_scenarios_did_not(self):
        self.assertIn("twister.json", self.text)
        self.assertIn("not run", self.text)

    def test_the_new_runs_come_after_the_old_cross_build(self):
        self.assertLess(self.text.index("west build -p always"), self.text.index("west twister"))

    def test_the_script_is_executable(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))


class LinkProbeTest(unittest.TestCase):
    """The probe that tests the static library finding of the template README."""

    def test_the_probe_links_one_adapter_three_ways(self):
        text = code(LINK_PROBE / "CMakeLists.txt")
        for variant in ("app_sources", "plain_static", "module_library"):
            with self.subTest(variant=variant):
                self.assertIn(f'PROBE_VARIANT STREQUAL "{variant}"', text)
        self.assertIn("add_library(probe_queue_adapter STATIC", text)
        self.assertIn("zephyr_library_named(probe_queue_module)", read(LINK_PROBE / "module/CMakeLists.txt"))
        self.assertTrue((LINK_PROBE / "module/zephyr/module.yml").is_file())

    def test_the_adapter_makes_the_four_calls_of_the_reported_failure(self):
        text = read(LINK_PROBE / "src/queue_adapter.c")
        for call in ("k_msgq_init", "k_msgq_put", "k_msgq_get", "k_msgq_purge"):
            with self.subTest(call=call):
                self.assertIn(call + "(", text)

    def test_the_script_builds_every_variant_and_expects_only_the_plain_library_to_fail(self):
        text = read(SCRIPT)
        self.assertIn('probe="$repo/tests/product_template_link"', text)
        self.assertIn("for variant in app_sources plain_static module_library; do", text)
        self.assertIn("undefined reference to .k_msgq_init", text)
        self.assertIn('-DZEPHYR_EXTRA_MODULES="$probe/module"', text)


class GuideTest(unittest.TestCase):
    def setUp(self):
        self.text = read(GUIDE)

    def test_the_guide_has_the_sections_a_product_team_needs(self):
        headings = re.findall(r"(?m)^#{1,3} (.+)$", self.text)
        joined = "\n".join(headings).lower()
        for topic in ("when not to write a driver", "layout", "module", "binding", "the driver",
                      "error", "logging", "emulator", "hardware", "checklist"):
            with self.subTest(topic=topic):
                self.assertIn(topic, joined)

    def test_the_guide_states_the_zephyr_version_and_what_changes_at_the_lts_move(self):
        self.assertIn("v4.4", self.text)
        self.assertIn("4.6", self.text)

    def test_every_relative_link_resolves(self):
        for target in re.findall(r"\]\((?!https?://|#|mailto:)([^)#\s]+)(?:#[^)\s]*)?\)", self.text):
            with self.subTest(target=target):
                self.assertTrue((GUIDE.parent / target).resolve().exists(), target)

    def test_every_repository_path_in_a_code_span_exists(self):
        roots = ("templates/", "docs/", "scripts/", "tests/")
        found = set()
        for span in re.findall(r"`([^`\n]+)`", self.text):
            token = span.strip()
            if token.startswith(roots) and not re.search(r"[<>*{}$\s]", token):
                found.add(token.rstrip("/"))
        self.assertTrue(found, "the guide names no repository path")
        for path in sorted(found):
            with self.subTest(path=path):
                # Paths of the layout table are relative to the template, the others to Crux.
                self.assertTrue((REPO / path).exists() or (TEMPLATE / path).exists(), path)

    def test_every_template_path_named_in_a_code_span_without_the_prefix_exists(self):
        # Paths in the layout table are relative to the product repository root.
        for name in ("zephyr/module.yml", "dts/bindings/vendor-prefixes.txt",
                     "boards/vnd/example_rt1062", "drivers/sensor/example_temp/example_temp.c",
                     "tests/drivers/sensor/example_temp/testcase.yaml"):
            with self.subTest(name=name):
                self.assertIn(f"`{name}`", self.text)
                self.assertTrue((TEMPLATE / name).exists())

    def test_the_guide_quotes_the_driver_it_ships(self):
        # The skeleton in the guide is the first lines of the real file, so it cannot drift.
        source = read(DRIVER / "example_temp.c")
        for token in re.findall(r"(?m)^(#define DT_DRV_COMPAT \w+)$", self.text):
            self.assertIn(token, source)
        for token in ("DEVICE_API(sensor,", "DT_INST_FOREACH_STATUS_OKAY(",
                      "zephyr_library_named(", "DT_HAS_VND_EXAMPLE_TEMP_ENABLED"):
            with self.subTest(token=token):
                self.assertIn(token, self.text)

    def test_the_guide_does_not_offer_a_twister_device_run_as_a_safe_hardware_route(self):
        self.assertIn("No supported entry point", self.text)
        self.assertIn("test-foundation-proposal.md", self.text)
        self.assertIn("flashes on every launch", self.text)
        # A device-testing flag may be named only to warn against it.
        for line in self.text.splitlines():
            if "--device-testing" in line or "--device-type=hardware" in line:
                with self.subTest(line=line):
                    self.assertRegex(line, r"(?i)\b(not|never|flash|warn|do not)\b")

    def test_the_guide_names_every_way_the_fixture_gate_opens(self):
        # A hardware map entry that lists the fixture opens the gate as well as the command line.
        self.assertIn("hardware map", self.text)
        self.assertIn("--device-testing", self.text)

    def test_the_guide_does_not_say_the_devicetree_sets_the_init_order(self):
        self.assertNotIn("devicetree already orders", self.text)
        self.assertIn("CONFIG_CHECK_INIT_PRIORITIES", self.text)

    def test_the_guide_keeps_the_boundary_with_crux(self):
        self.assertIn("ADR-0001", self.text)
        self.assertIn("choosing-an-api.md", self.text)
        self.assertRegex(self.text, r"(?i)never use `crux_`|not use the `crux_` prefix|never.*`crux_`")

    def test_the_guide_links_the_zephyr_documentation_it_defers_to(self):
        self.assertRegex(self.text, r"https://docs\.zephyrproject\.org/")


class PublicTextTest(unittest.TestCase):
    def test_no_marker_of_private_material_is_in_the_kit(self):
        for path in kit_text_files():
            with self.subTest(path=str(path.relative_to(REPO))):
                self.assertIsNone(FORBIDDEN_IN_PUBLIC_TEXT.search(read(path)))

    def test_only_one_file_of_the_kit_is_named_after_the_vendor_board(self):
        # Zephyr finds the overlay of the hardware scenario for the vendor board by that name.
        named = [path.name for path in kit_text_files() if "mimxrt1060_evk" in path.name]
        self.assertEqual(["mimxrt1060_evk_mimxrt1062_qspi_B.overlay"], named)


class PointerTest(unittest.TestCase):
    def test_the_docs_index_points_to_the_guide(self):
        self.assertIn("writing-a-product-driver.md", read(REPO / "docs/README.md"))

    def test_the_readme_points_to_the_guide(self):
        self.assertIn("docs/writing-a-product-driver.md", read(REPO / "README.md"))

    def test_the_template_readme_points_to_the_kit_and_the_guide(self):
        text = read(TEMPLATE / "README.md")
        self.assertIn("(drivers/README.md)", text)
        self.assertIn("writing-a-product-driver.md", text)

    def test_the_kit_readme_describes_the_module(self):
        text = read(KIT_README)
        self.assertIn("writing-a-product-driver.md", text)
        for name in ("zephyr/module.yml", "drivers/", "dts/bindings/", "boards/", "tests/"):
            with self.subTest(name=name):
                self.assertIn(name, text)

    def test_the_guide_records_the_static_library_finding_and_its_probe(self):
        text = read(GUIDE)
        self.assertIn("zephyr_library_named", text)
        self.assertIn("--whole-archive", text)
        self.assertIn("tests/product_template_link", text)

    def test_the_guide_is_reached_without_an_edit_of_contributing(self):
        # When the kit was added, CONTRIBUTING.md (a protected file) was not changed: the guide is
        # reached from README.md and docs/README.md. A later reviewed change may link it there.
        self.assertNotIn("writing-a-product-driver", read(REPO / "CONTRIBUTING.md"))


if __name__ == "__main__":
    unittest.main()
