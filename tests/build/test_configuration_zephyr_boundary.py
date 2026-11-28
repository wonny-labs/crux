"""The native-free consumer check rejects a consumer that links the Configuration composition target.

`crux::configuration_zephyr` is a composition interface, not a portable usage target: it declares the start
of the Settings File provider, which only a product's composition may call. These checks configure small
CMake projects on the host with the real guard (cmake/CruxConsumerBoundary.cmake) and the real definition
of the target, taken from components/configuration/ports/zephyr/CMakeLists.txt, without a Zephyr SDK. The
same projects configure cleanly against weakened copies of the guard, so a passing rejection is not
vacuous. Rule 3 of docs/composition-interfaces.md.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
CMAKE = shutil.which("cmake")
GUARD = REPO / "cmake/CruxConsumerBoundary.cmake"
COMPONENT = REPO / "components/configuration"
PORT_CMAKE = COMPONENT / "ports/zephyr/CMakeLists.txt"
REJECTION = "native consumer requirement"

_FUNCTION = re.search(r"function\(crux_configuration_zephyr_composition\).*?endfunction\(\)",
                      PORT_CMAKE.read_text(), re.S)

# The mock needs only what the real function reads: the component directory and the portable target.
PROJECT = f"""cmake_minimum_required(VERSION 3.28)
project(probe LANGUAGES C)
include("@GUARD@")
set(CRUX_CONFIGURATION_COMPONENT_DIR "{COMPONENT}")
add_library(crux_configuration INTERFACE)
add_library(crux::configuration ALIAS crux_configuration)
target_include_directories(crux_configuration INTERFACE "{COMPONENT}/include")
{_FUNCTION.group(0) if _FUNCTION else ""}
crux_configuration_zephyr_composition()
file(WRITE "${{CMAKE_BINARY_DIR}}/main.c" "int main(void) {{ return 0; }}\\n")
"""

DIRECT_LINK = """add_executable(app "${CMAKE_BINARY_DIR}/main.c")
target_link_libraries(app PRIVATE crux::configuration crux::configuration_zephyr)
crux_assert_portable_consumer(app)
"""
USAGE_OF_THE_TARGET = "crux_assert_portable_usage(crux::configuration_zephyr)\n"
USAGE_THROUGH_A_WRAPPER = """add_library(product_storage INTERFACE)
target_link_libraries(product_storage INTERFACE crux::configuration_zephyr)
add_library(product::storage ALIAS product_storage)
add_executable(app "${CMAKE_BINARY_DIR}/main.c")
target_link_libraries(app PRIVATE product::storage)
crux_assert_portable_usage(product::storage)
"""
SCENARIOS = {"a direct link of a consumer": DIRECT_LINK,
             "the usage check of the target itself": USAGE_OF_THE_TARGET,
             "a transitive wrapper": USAGE_THROUGH_A_WRAPPER}
# The portable target alone must pass, so the rejection is about the composition target.
PORTABLE_CONSUMER = """add_executable(app "${CMAKE_BINARY_DIR}/main.c")
target_link_libraries(app PRIVATE crux::configuration)
crux_assert_portable_consumer(app)
crux_assert_portable_usage(crux::configuration)
"""


def weaken_demoting_the_error(text):
    return text.replace('message(FATAL_ERROR "native consumer requirement',
                        'message(STATUS "native consumer requirement')


def weaken_dropping_the_zephyr_patterns(text):
    # Removes the two tests that name Zephyr: the token and the component port directories.
    text = text.replace("(zephyr|boards?|soc|", "(boards?|soc|")
    return text.replace('               OR lower MATCHES "(^|/)components/[^/]+/(src|ports|host|zephyr|tests?)(/|$)"\n', "")


WEAKENINGS = {"the error is demoted to a status line": weaken_demoting_the_error,
              "the Zephyr name and port directory patterns are dropped": weaken_dropping_the_zephyr_patterns}


@unittest.skipUnless(CMAKE, "CMake is required")
class ComposeTargetIsRejected(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(_FUNCTION, "the port defines no composition target")

    def configure(self, body, guard=GUARD):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "CMakeLists.txt").write_text(PROJECT.replace("@GUARD@", str(guard)) + body)
            result = subprocess.run([CMAKE, "-S", str(root), "-B", str(root / "build")],
                                    capture_output=True, text=True)
        return result, result.stdout + result.stderr

    def test_a_portable_consumer_of_configuration_passes(self):
        result, output = self.configure(PORTABLE_CONSUMER)
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn(REJECTION, output)

    def test_the_guard_rejects_every_use_of_the_composition_target(self):
        for name, body in SCENARIOS.items():
            with self.subTest(scenario=name):
                result, output = self.configure(body)
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn(REJECTION, output)
                self.assertRegex(output, r"configuration_zephyr|components/configuration/ports/zephyr")

    def test_the_rejection_can_fail_against_a_weakened_guard(self):
        original = GUARD.read_text()
        for weakening, transform in WEAKENINGS.items():
            weakened = transform(original)
            self.assertNotEqual(weakened, original, "the weakening changed nothing: " + weakening)
            with tempfile.TemporaryDirectory() as temporary:
                guard = Path(temporary) / "CruxConsumerBoundary.cmake"
                guard.write_text(weakened)
                for name, body in SCENARIOS.items():
                    with self.subTest(weakening=weakening, scenario=name):
                        result, output = self.configure(body, guard)
                        self.assertEqual(result.returncode, 0, output)


if __name__ == "__main__":
    unittest.main()
