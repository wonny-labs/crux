"""The public web lifecycle targets are accepted, and nothing private is reachable through them (ADR-0004, T1).

`crux::web_session` and `crux::web_management` are portable usage targets. The existing guards do not name
the directories `adapter`, `session` and `management` of `components/web` (ADR-0004 section 1.3), so this
change adds `cmake/CruxWebBoundary.cmake`, in the shape of the Access and credential guards, and these
checks run it with the other guards against the real definitions of the two targets, taken from
`components/web/ports/zephyr/{session,management}/CMakeLists.txt`, in small CMake projects without a
Zephyr SDK. The same projects configure cleanly against weakened copies of the guards that are laid out
as the real ones are, so a rejection is not vacuous.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
CMAKE = shutil.which("cmake")
GUARD_NAMES = ("CruxConsumerBoundary.cmake", "CruxAccessBoundary.cmake", "CruxCredentialBoundary.cmake",
               "CruxWebBoundary.cmake")
GUARDS = {name: REPO / "cmake" / name for name in GUARD_NAMES}
COMPONENTS = REPO / "components"
WEB = COMPONENTS / "web"


def definition(path, name):
    text = path.read_text() if path.is_file() else ""
    match = re.search(rf"function\({name}_public_target\).*?endfunction\(\)", text, re.S)
    return match.group(0) if match else ""


SESSION_FUNCTION = definition(WEB / "ports/zephyr/session/CMakeLists.txt", "crux_web_session")
MANAGEMENT_FUNCTION = definition(WEB / "ports/zephyr/management/CMakeLists.txt", "crux_web_management")

# The mock reproduces what the Zephyr module says about crux::web (an INTERFACE library with the public
# include roots), and the composition-only adapter target, which links the web adapter directory on
# purpose. The two port directories set a COMPONENT_DIR variable of their own, so the mock sets it too.
PROJECT = f"""cmake_minimum_required(VERSION 3.28)
project(probe LANGUAGES C)
include("@GUARDS@/CruxConsumerBoundary.cmake")
include("@GUARDS@/CruxAccessBoundary.cmake")
include("@GUARDS@/CruxCredentialBoundary.cmake")
include("@GUARDS@/CruxWebBoundary.cmake")
set(CRUX_WEB_COMPONENT_DIR "{WEB}")
add_library(crux_web INTERFACE)
add_library(crux::web ALIAS crux_web)
target_include_directories(crux_web INTERFACE "{WEB}/include" "{COMPONENTS}/access/include")
add_library(crux_web_adapter INTERFACE)
target_include_directories(crux_web_adapter INTERFACE "{WEB}/adapter")
{SESSION_FUNCTION}
{MANAGEMENT_FUNCTION}
crux_web_session_public_target()
crux_web_management_public_target()
file(WRITE "${{CMAKE_BINARY_DIR}}/main.c" "int main(void) {{ return 0; }}\\n")
"""

GUARD_CALLS = """crux_assert_portable_usage(crux::web_session crux::web_management)
crux_assert_access_adapter_unreachable(crux::web_session crux::web_management)
crux_assert_web_internal_unreachable(crux::web_session crux::web_management)
"""

PORTABLE_CONSUMER = """add_executable(app "${CMAKE_BINARY_DIR}/main.c")
target_link_libraries(app PRIVATE crux::web_session crux::web_management)
crux_assert_portable_consumer(app)
crux_assert_access_consumer(app)
crux_assert_web_consumer(app)
""" + GUARD_CALLS


def escape_on_app(directory):
    return f"""add_executable(app "${{CMAKE_BINARY_DIR}}/main.c")
target_link_libraries(app PRIVATE crux::web_session crux::web_management)
target_include_directories(app PRIVATE "{directory}")
crux_assert_web_consumer(app)
"""


ESCAPES = {
    "the web adapter directory on the include path": (
        escape_on_app(WEB / "adapter"), "Web internal header reachable", "CruxWebBoundary.cmake"),
    "the web session directory on the include path": (
        escape_on_app(WEB / "session"), "Web internal header reachable", "CruxWebBoundary.cmake"),
    "the web management directory on the include path": (
        escape_on_app(WEB / "management"), "Web internal header reachable", "CruxWebBoundary.cmake"),
    "the web assets directory on the include path": (
        escape_on_app(WEB / "assets"), "Web internal header reachable", "CruxWebBoundary.cmake"),
    "the web component directory, from which adapter/ resolves": (
        escape_on_app(WEB), "Web internal header reachable", "CruxWebBoundary.cmake"),
    "the composition-only adapter target": (
        """add_executable(app "${CMAKE_BINARY_DIR}/main.c")
target_link_libraries(app PRIVATE crux::web_session crux_web_adapter)
crux_assert_web_consumer(app)
""", "Web internal header reachable", "CruxWebBoundary.cmake"),
    "a wrapper that publishes the adapter target": (
        """add_library(product_web INTERFACE)
target_link_libraries(product_web INTERFACE crux::web_management crux_web_adapter)
crux_assert_web_internal_unreachable(product_web)
""", "Web internal header reachable", "CruxWebBoundary.cmake"),
    "a compile option that names the session directory": (
        f"""add_library(product_web INTERFACE)
target_link_libraries(product_web INTERFACE crux::web_session)
target_compile_options(product_web INTERFACE "-I{WEB}/session")
crux_assert_web_internal_unreachable(product_web)
""", "Web internal header reachable", "CruxWebBoundary.cmake"),
    "the Access adapter directory on the include path": (
        f"""add_executable(app "${{CMAKE_BINARY_DIR}}/main.c")
target_link_libraries(app PRIVATE crux::web_session)
target_include_directories(app PRIVATE "{COMPONENTS}/access/adapter")
crux_assert_access_consumer(app)
""", "Access adapter header reachable", "CruxAccessBoundary.cmake"),
    "a provider source directory on the include path": (
        f"""add_library(product_web INTERFACE)
target_link_libraries(product_web INTERFACE crux::web_session)
target_include_directories(product_web INTERFACE "{WEB}/src")
crux_assert_portable_usage(product_web)
""", "native consumer requirement", "CruxConsumerBoundary.cmake"),
    "the native provider library through a portable wrapper": (
        """add_library(zephyr_interface INTERFACE)
add_library(product_web INTERFACE)
target_link_libraries(product_web INTERFACE crux::web_management zephyr_interface)
crux_assert_portable_usage(product_web)
""", "native consumer requirement", "CruxConsumerBoundary.cmake"),
}


def demote(text):
    return re.sub(r'message\(FATAL_ERROR "(native consumer requirement|Access adapter header reachable'
                  r'|Credential adapter header reachable|Web internal header reachable)',
                  r'message(STATUS "\1', text)


@unittest.skipUnless(CMAKE and SESSION_FUNCTION and MANAGEMENT_FUNCTION and GUARDS["CruxWebBoundary.cmake"].is_file(),
                     "CMake, the target definitions and the web guard are required")
class PublicTargetsAreAcceptedAndNothingPrivateIsReachable(unittest.TestCase):
    def configure(self, body, weaken=None, replace=None):
        """Configure the probe. `weaken` names a guard to demote to a status line, or "copy" to run
        unchanged copies of the guards from the layout that a weakened run uses."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = REPO / "cmake"
            if weaken is not None:
                # A copied guard looks for the directories it protects at ../components of its own
                # directory, so the copy anchors them at this repository instead; otherwise it would
                # look at a directory that does not exist and accept every escape.
                directory = root / "cmake"
                directory.mkdir()
                for name, path in GUARDS.items():
                    text = path.read_text()
                    anchored = text.replace("${CMAKE_CURRENT_FUNCTION_LIST_DIR}/../", f"{REPO}/")
                    if name != "CruxConsumerBoundary.cmake":
                        self.assertNotEqual(anchored, text, "the anchoring changed nothing: " + name)
                    text = anchored
                    if name == weaken:
                        changed = demote(text)
                        self.assertNotEqual(changed, text, "the weakening changed nothing: " + name)
                        text = changed
                    (directory / name).write_text(text)
            project = PROJECT.replace("@GUARDS@", str(directory))
            if replace is not None:
                project = project.replace(*replace)
            (root / "CMakeLists.txt").write_text(project + body)
            result = subprocess.run([CMAKE, "-S", str(root), "-B", str(root / "build")],
                                    capture_output=True, text=True)
        return result, result.stdout + result.stderr

    def test_the_mock_carries_the_real_definitions(self):
        result, output = self.configure("")
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("crux::web_session ALIAS", SESSION_FUNCTION)
        self.assertIn("crux::web_management ALIAS", MANAGEMENT_FUNCTION)

    def test_a_portable_consumer_passes_every_check(self):
        result, output = self.configure(PORTABLE_CONSUMER)
        self.assertEqual(result.returncode, 0, output)
        for rejection in ("native consumer requirement", "adapter header reachable", "Web internal header"):
            self.assertNotIn(rejection, output)

    def test_every_way_past_the_public_targets_is_rejected(self):
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

    def test_the_web_guard_rejects_a_definition_that_exposes_the_adapter(self):
        exposed = ("target_link_libraries(crux_web_session INTERFACE crux_web_adapter)\n"
                   "file(WRITE")
        result, output = self.configure("crux_assert_web_internal_unreachable(crux::web_session)\n",
                                        replace=("file(WRITE", exposed))
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("Web internal header reachable", output)

    def test_the_web_guard_accepts_the_public_include_root_of_crux_web(self):
        result, output = self.configure("crux_assert_web_internal_unreachable(crux::web)\n")
        self.assertEqual(result.returncode, 0, output)

    def test_the_web_guard_names_an_unknown_target(self):
        result, output = self.configure("crux_assert_web_internal_unreachable(crux::nope)\n")
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("unknown consumer target", output)


if __name__ == "__main__":
    unittest.main()
