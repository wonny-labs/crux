"""The controller sample is gone, and every check that it carried has a home that still exists."""
import os
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[2]


class ControllerSampleRemovalTest(unittest.TestCase):
    def test_no_controller_sample_and_no_periodic_task_sample(self):
        self.assertFalse((REPO / "samples/controller").exists())
        self.assertFalse((REPO / "samples/time/periodic_task").exists())
        self.assertFalse((REPO / "samples/management_rt1060_mbed").exists())

    def test_periodic_scenario_keeps_host_native_sim_and_core_coverage(self):
        for relative in ("tests/time_periodic/core/controller.c", "tests/time_periodic/core/health.c",
                         "tests/time_periodic/include/controller.h", "tests/time_periodic/host/main.c",
                         "tests/time_periodic/zephyr/main.c", "tests/time_periodic/zephyr/testcase.yaml",
                         "tests/controller/controller_test.cpp", "tests/controller/health_test.cpp"):
            self.assertTrue((REPO / relative).is_file(), relative)
        host = (REPO / "tests/time_periodic/host/CMakeLists.txt").read_text()
        self.assertIn("TimePeriodic.HostScenario", host)
        self.assertIn("check-time-periodic.py", host)
        script = (REPO / "scripts/test-time-periodic.sh").read_text()
        for needle in ("native_sim/native/64", "missing-rtc", "mimxrt1060_evk@B//qspi",
                       "tests/time_periodic/zephyr"):
            self.assertIn(needle, script)

    def test_boot_fixture_keeps_the_sysbuild_image_name(self):
        fixture = REPO / "tests/boot_fixture/zephyr"
        self.assertEqual(fixture.name, "zephyr")
        for name in ("CMakeLists.txt", "prj.conf", "boards/native_sim.conf",
                     "boards/mimxrt1060_evk_mimxrt1062_qspi.conf"):
            self.assertTrue((fixture / name).is_file(), name)
        for script in ("scripts/test-boot-composition.sh", "tests/target/check_boot_images.sh",
                       "tests/target/compare-mcuboot-crypto-backends.sh",
                       "tests/target/check_boot_reproducibility.sh"):
            self.assertIn("tests/boot_fixture/zephyr", (REPO / script).read_text(), script)

    def test_probe_images_keep_every_configuration_and_source(self):
        probe = REPO / "tests/board_images/integration_probe"
        for name in ("device_health_probe.conf", "without_test_commands.conf", "network_probe.conf",
                     "integrated.conf", "mdio_completion_fix.conf", "mdio_failure_trace.conf",
                     "phy_diagnostic.conf", "deferred_output.conf", "native_output.conf",
                     "probe_main.c", "network_probe.c", "network_client.c", "device_input.c",
                     "native_logger.c", "mdio_completion.cmake", "Kconfig", "prj.conf", "CMakeLists.txt"):
            self.assertTrue((probe / name).is_file(), name)
        self.assertTrue((REPO / "samples/boards/nxp/mimxrt1060_evk/common/network.overlay").is_file())
        self.assertTrue((REPO / "samples/boards/nxp/mimxrt1060_evk/web_management/CMakeLists.txt").is_file())

    def test_old_script_names_stay_as_aliases_until_the_workflows_switch(self):
        for old, new in (("scripts/test-controller.sh", "scripts/test-time-periodic.sh"),
                         ("scripts/test-m3-rt1170.sh", "scripts/test-integration-probe-rt1170.sh")):
            self.assertTrue(os.access(REPO / old, os.X_OK), old)
            self.assertTrue(os.access(REPO / new, os.X_OK), new)
            self.assertIn(Path(new).name, (REPO / old).read_text(), old)
            self.assertIn("exec", (REPO / old).read_text(), old)


if __name__ == "__main__":
    unittest.main()
