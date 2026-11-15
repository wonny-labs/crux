"""The public TLS certificate target is accepted, and nothing private is reachable through it (ADR-0004, T1).

`crux::tls_certificate` is a portable usage target, not a composition interface, and ADR-0004 open point
C2 asks how publishing the start and material calls can leave the credential boundary rule intact: that
rule refuses any public target that reaches the credential adapter. The answer here is that the
declarations live in a public header under the target's own include root, so the target needs no adapter
directory, and the composition-only adapter target (which links the credential adapter on purpose) stays
refused. These checks configure small CMake projects with the real guards (cmake/Crux*Boundary.cmake) and
the real definition of the target, taken from components/tls_certificate/ports/zephyr/CMakeLists.txt,
without a Zephyr SDK. The same projects configure cleanly against weakened copies of the guards, so a
rejection is not vacuous.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
CMAKE = shutil.which("cmake")
GUARDS = {name: REPO / "cmake" / name for name in
          ("CruxConsumerBoundary.cmake", "CruxAccessBoundary.cmake", "CruxCredentialBoundary.cmake")}
COMPONENTS = REPO / "components"
_TEXT = (COMPONENTS / "tls_certificate/ports/zephyr/CMakeLists.txt").read_text()
_MATCH = re.search(r"function\(crux_tls_certificate_public_target\).*?endfunction\(\)", _TEXT, re.S)
FUNCTION = _MATCH.group(0) if _MATCH else ""

# The mock reproduces what the Host build says about the composition-only adapter target: it links the
# credential adapter publicly, on purpose, so that the credential boundary rule refuses it.
PROJECT = f"""cmake_minimum_required(VERSION 3.28)
project(probe LANGUAGES C)
include("@GUARDS@/CruxConsumerBoundary.cmake")
include("@GUARDS@/CruxAccessBoundary.cmake")
include("@GUARDS@/CruxCredentialBoundary.cmake")
set(CRUX_TLS_CERTIFICATE_COMPONENT_DIR "{COMPONENTS}/tls_certificate")
add_library(crux_access INTERFACE)
target_include_directories(crux_access INTERFACE "{COMPONENTS}/access/include")
add_library(crux::access ALIAS crux_access)
add_library(crux_credential_adapter INTERFACE)
target_include_directories(crux_credential_adapter INTERFACE "{COMPONENTS}/credential/adapter")
add_library(crux_tls_certificate_adapter INTERFACE)
target_include_directories(crux_tls_certificate_adapter INTERFACE "{COMPONENTS}/tls_certificate/adapter")
target_link_libraries(crux_tls_certificate_adapter INTERFACE crux_credential_adapter)
{FUNCTION}
crux_tls_certificate_public_target()
file(WRITE "${{CMAKE_BINARY_DIR}}/main.c" "int main(void) {{ return 0; }}\\n")
"""

PORTABLE_CONSUMER = """add_executable(app "${CMAKE_BINARY_DIR}/main.c")
target_link_libraries(app PRIVATE crux::tls_certificate)
crux_assert_portable_consumer(app)
crux_assert_portable_usage(crux::tls_certificate)
crux_assert_access_adapter_unreachable(crux::tls_certificate)
crux_assert_credential_adapter_unreachable(crux::tls_certificate)
crux_assert_access_consumer(app)
crux_assert_credential_consumer(app)
"""

ESCAPES = {
    "the composition-only adapter target": (
        """add_executable(app "${CMAKE_BINARY_DIR}/main.c")
target_link_libraries(app PRIVATE crux::tls_certificate crux_tls_certificate_adapter)
crux_assert_credential_consumer(app)
""", "Credential adapter header reachable", "CruxCredentialBoundary.cmake"),
    "a wrapper that publishes the adapter target": (
        """add_library(product_tls INTERFACE)
target_link_libraries(product_tls INTERFACE crux::tls_certificate crux_tls_certificate_adapter)
crux_assert_credential_adapter_unreachable(product_tls)
""", "Credential adapter header reachable", "CruxCredentialBoundary.cmake"),
    "the credential adapter directory on the include path": (
        f"""add_executable(app "${{CMAKE_BINARY_DIR}}/main.c")
target_link_libraries(app PRIVATE crux::tls_certificate)
target_include_directories(app PRIVATE "{COMPONENTS}/credential/adapter")
crux_assert_credential_consumer(app)
""", "Credential adapter header reachable", "CruxCredentialBoundary.cmake"),
    "the Access adapter directory on the include path": (
        f"""add_executable(app "${{CMAKE_BINARY_DIR}}/main.c")
target_link_libraries(app PRIVATE crux::tls_certificate)
target_include_directories(app PRIVATE "{COMPONENTS}/access/adapter")
crux_assert_access_consumer(app)
""", "Access adapter header reachable", "CruxAccessBoundary.cmake"),
    "a provider source directory on the include path": (
        f"""add_library(product_tls INTERFACE)
target_link_libraries(product_tls INTERFACE crux::tls_certificate)
target_include_directories(product_tls INTERFACE "{COMPONENTS}/tls_certificate/src")
crux_assert_portable_usage(product_tls)
""", "native consumer requirement", "CruxConsumerBoundary.cmake"),
    "the native provider library through a portable wrapper": (
        """add_library(zephyr_interface INTERFACE)
add_library(product_tls INTERFACE)
target_link_libraries(product_tls INTERFACE crux::tls_certificate zephyr_interface)
crux_assert_portable_usage(product_tls)
""", "native consumer requirement", "CruxConsumerBoundary.cmake"),
}


def demote(text):
    return re.sub(r'message\(FATAL_ERROR "(native consumer requirement|Access adapter header reachable'
                  r'|Credential adapter header reachable)', r'message(STATUS "\1', text)


@unittest.skipUnless(CMAKE and FUNCTION, "CMake and the target definition are required")
class PublicTargetIsAcceptedAndNothingPrivateIsReachable(unittest.TestCase):
    def configure(self, body, weaken=None, definition=None):
        """Configure the probe. `weaken` names a guard to demote to a status line, or "copy" to run
        unchanged copies of the guards from the layout that a weakened run uses."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = REPO / "cmake"
            if weaken is not None:
                # The adapter checks anchor the directory they protect at ../components of the
                # guard's own directory. A copy elsewhere would look at a directory that does not
                # exist and accept every escape, so the copy anchors at this repository instead.
                directory = root / "cmake"
                directory.mkdir()
                for name, path in GUARDS.items():
                    text = path.read_text().replace("${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../",
                                                    f"{REPO}/")
                    if name == weaken:
                        changed = demote(text)
                        self.assertNotEqual(changed, text, "the weakening changed nothing: " + name)
                        text = changed
                    (directory / name).write_text(text)
            project = PROJECT.replace("@GUARDS@", str(directory))
            if definition is not None:
                project = project.replace("crux_tls_certificate_public_target()\nfile(", definition + "file(")
            (root / "CMakeLists.txt").write_text(project + body)
            result = subprocess.run([CMAKE, "-S", str(root), "-B", str(root / "build")],
                                    capture_output=True, text=True)
        return result, result.stdout + result.stderr

    def test_the_mock_carries_the_real_definition(self):
        result, output = self.configure("")
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("/include\"", FUNCTION)

    def test_a_portable_consumer_passes_every_check(self):
        result, output = self.configure(PORTABLE_CONSUMER)
        self.assertEqual(result.returncode, 0, output)
        for rejection in ("native consumer requirement", "adapter header reachable"):
            self.assertNotIn(rejection, output)

    def test_every_way_past_the_public_target_is_rejected(self):
        for name, (body, message, _guard) in ESCAPES.items():
            with self.subTest(escape=name):
                result, output = self.configure(body)
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn(message, output)

    def test_an_unweakened_copy_of_the_guards_still_rejects_each_escape(self):
        # The control for the weakened runs below: the copy is laid out as they are, and it checks.
        for name, (body, message, _guard) in ESCAPES.items():
            with self.subTest(escape=name):
                result, output = self.configure(body, weaken="copy")
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn(message, output)

    def test_each_escape_passes_against_the_guard_that_it_needs_weakened(self):
        for name, (body, _message, guard) in ESCAPES.items():
            with self.subTest(escape=name, weakened=guard):
                result, output = self.configure(body, weaken=guard)
                self.assertEqual(result.returncode, 0, output)

    def test_the_guard_rejects_a_definition_that_exposes_the_credential_adapter(self):
        exposed = ("crux_tls_certificate_public_target()\n"
                   "target_link_libraries(crux_tls_certificate INTERFACE crux_credential_adapter)\n")
        result, output = self.configure("crux_assert_credential_adapter_unreachable(crux::tls_certificate)\n",
                                        definition=exposed)
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("Credential adapter header reachable", output)


if __name__ == "__main__":
    unittest.main()
