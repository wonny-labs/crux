"""The native-free consumer check rejects a consumer that links the credential store composition target.

`crux::credential_store_zephyr` is a composition interface, not a portable usage target: it declares the
erase of the credential store, which only a product's composition may call. These checks configure small
CMake projects on the host with the real guards (cmake/CruxConsumerBoundary.cmake and
cmake/CruxCredentialBoundary.cmake) and the real definition of the target, taken from
components/credential/ports/zephyr/CMakeLists.txt, without a Zephyr SDK. The same projects configure
cleanly against weakened copies of the guard, so a passing rejection is not vacuous. Rule 3 of
docs/composition-interfaces.md.
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
CREDENTIAL_GUARD = REPO / "cmake/CruxCredentialBoundary.cmake"
COMPONENT = REPO / "components/credential"
PORT_CMAKE = COMPONENT / "ports/zephyr/CMakeLists.txt"
REJECTION = "native consumer requirement"

_FUNCTION = re.search(r"function\(crux_credential_store_zephyr_composition\).*?endfunction\(\)",
                      PORT_CMAKE.read_text(), re.S)

# The mock needs only what the real function reads: the component directory and the portable target.
PROJECT = f"""cmake_minimum_required(VERSION 3.28)
project(probe LANGUAGES C)
include("@GUARD@")
set(CRUX_CREDENTIAL_COMPONENT_DIR "{COMPONENT}")
add_library(crux_credential_store INTERFACE)
add_library(crux::credential_store ALIAS crux_credential_store)
target_include_directories(crux_credential_store INTERFACE "{COMPONENT}/include")
{_FUNCTION.group(0) if _FUNCTION else ""}
crux_credential_store_zephyr_composition()
file(WRITE "${{CMAKE_BINARY_DIR}}/main.c" "int main(void) {{ return 0; }}\\n")
"""

DIRECT_LINK = """add_executable(app "${CMAKE_BINARY_DIR}/main.c")
target_link_libraries(app PRIVATE crux::credential_store crux::credential_store_zephyr)
crux_assert_portable_consumer(app)
"""
USAGE_OF_THE_TARGET = "crux_assert_portable_usage(crux::credential_store_zephyr)\n"
USAGE_THROUGH_A_WRAPPER = """add_library(product_reset INTERFACE)
target_link_libraries(product_reset INTERFACE crux::credential_store_zephyr)
add_library(product::reset ALIAS product_reset)
add_executable(app "${CMAKE_BINARY_DIR}/main.c")
target_link_libraries(app PRIVATE product::reset)
crux_assert_portable_usage(product::reset)
"""
SCENARIOS = {"a direct link of a consumer": DIRECT_LINK,
             "the usage check of the target itself": USAGE_OF_THE_TARGET,
             "a transitive wrapper": USAGE_THROUGH_A_WRAPPER}
# The portable target alone must pass, so the rejection is about the composition target. The
# composition target also leaves the private adapter header unreachable.
PORTABLE_CONSUMER = """add_executable(app "${CMAKE_BINARY_DIR}/main.c")
target_link_libraries(app PRIVATE crux::credential_store)
crux_assert_portable_consumer(app)
crux_assert_portable_usage(crux::credential_store)
"""
# The credential rule includes the real consumer guard, so only the adapter probe includes it: a weakened
# copy of the guard would be replaced by the real one.
ADAPTER_UNREACHABLE = (f'include("{CREDENTIAL_GUARD}")\n'
                       "crux_assert_credential_adapter_unreachable(crux::credential_store_zephyr)\n")


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

    def test_a_portable_consumer_of_the_credential_store_passes(self):
        result, output = self.configure(PORTABLE_CONSUMER)
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn(REJECTION, output)

    def test_the_composition_target_does_not_reach_the_adapter_header(self):
        result, output = self.configure(ADAPTER_UNREACHABLE)
        self.assertEqual(result.returncode, 0, output)

    def test_the_guard_rejects_every_use_of_the_composition_target(self):
        for name, body in SCENARIOS.items():
            with self.subTest(scenario=name):
                result, output = self.configure(body)
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn(REJECTION, output)
                self.assertRegex(output, r"credential_store_zephyr|components/credential/ports/zephyr")

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
