"""crux_web_routes() keeps Crux's private include directories to the sources that need them.

A product that names the route sources of the Crux services to crux_web_routes() must not have to put
components/web/session or components/web/ports/zephyr on the include path of its whole target: its own sources
would then see them, and the consumer check of ADR-0004 section 5 refuses that. The function attaches the
directories to the Crux route sources and to the file it generates, as per-source properties, and links no
usage target to the product's target. These probes configure a small project with the real function and read
compile_commands.json, so they need cmake and Python 3 but no Zephyr.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
SESSION_ROUTES = REPO / "components/web/session/web_session_routes.c"
REVIEWED = """public POST /api/v1/session
session DELETE /api/v1/session
public GET /api/v1/session/attempt/{id}
session GET /api/v1/session/me
session POST /api/v1/session/me/password
"""
PRODUCT_ROUTE = """#include <crux/web.h>
CRUX_WEB_ROUTE(product_ping, "/api/v1/product/ping", CRUX_WEB_GET, "product.demo", on_ping, NULL);
"""
PROJECT = """cmake_minimum_required(VERSION 3.20)
project(probe C)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
include({repo}/cmake/CruxWebRoutes.cmake)
# What the module defines for the Zephyr web port: an interface target with the port's directory.
add_library(crux_web_zephyr_resources INTERFACE)
target_include_directories(crux_web_zephyr_resources INTERFACE {repo}/components/web/ports/zephyr)
add_library(app STATIC product.c product_routes.c {session})
{extra}
crux_web_routes(app SOURCES product_routes.c {session} ZEPHYR_RESOURCES REVIEWED ${{CMAKE_CURRENT_LIST_DIR}}/reviewed.txt)
get_target_property(probe_links app LINK_LIBRARIES)
get_target_property(probe_interface app INTERFACE_LINK_LIBRARIES)
message(STATUS "probe-links=[${{probe_links}}] probe-interface=[${{probe_interface}}]")
"""


def components_dirs(command):
    return [word[2:] for word in command.split() if word.startswith("-I") and "/components/" in word]


@unittest.skipUnless(shutil.which("cmake") and shutil.which("python3"), "needs cmake and Python 3")
class PrivateIncludesTest(unittest.TestCase):
    def configure(self, extra="", session=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.assertNotIn(REPO, root.resolve().parents)
        (root / "product.c").write_text("int product;\n")
        (root / "product_routes.c").write_text(PRODUCT_ROUTE)
        (root / "reviewed.txt").write_text(REVIEWED)
        (root / "CMakeLists.txt").write_text(PROJECT.format(repo=REPO, session=session or SESSION_ROUTES,
                                                           extra=extra))
        result = subprocess.run(["cmake", "-S", str(root), "-B", str(root / "build")], capture_output=True,
                                text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.stdout = result.stdout + result.stderr
        commands = json.loads((root / "build/compile_commands.json").read_text())
        return {Path(entry["file"]).name: entry["command"] for entry in commands}

    def test_the_products_own_sources_see_no_directory_of_crux_components(self):
        commands = self.configure()
        for name in ("product.c", "product_routes.c"):
            self.assertEqual(components_dirs(commands[name]), [], name)

    def test_the_crux_route_source_sees_the_directories_it_needs(self):
        commands = self.configure()
        seen = " ".join(components_dirs(commands["web_session_routes.c"]))
        for needed in ("components/web/session", "components/web/adapter", "components/web/src",
                       "components/access/adapter", "components/access/include", "components/web/include"):
            self.assertIn(needed, seen)

    def test_the_generated_resources_see_the_web_ports_directory_and_nothing_else_does(self):
        commands = self.configure()
        self.assertIn("components/web/ports/zephyr", " ".join(components_dirs(commands["crux_web_resources.c"])))
        for name in ("product.c", "product_routes.c", "web_session_routes.c", "crux_web_routes.c"):
            self.assertNotIn("components/web/ports/zephyr", " ".join(components_dirs(commands[name])), name)

    def test_the_function_links_nothing_of_crux_to_the_product(self):
        self.configure()
        links = re.search(r"probe-links=\[(.*?)\] probe-interface=\[(.*?)\]", self.stdout)
        self.assertIsNotNone(links, self.stdout)
        # The product's own target links nothing at all here: the function adds no usage target to it.
        for value in links.groups():  # an unset property reads as <variable>-NOTFOUND
            self.assertTrue(value == "" or value.endswith("-NOTFOUND"), value)

    def test_a_property_the_caller_set_on_a_crux_route_source_is_kept(self):
        extra = f'set_property(SOURCE {SESSION_ROUTES} PROPERTY INCLUDE_DIRECTORIES /caller/own)'
        commands = self.configure(extra)
        seen = commands["web_session_routes.c"]
        self.assertIn("-I/caller/own", seen)
        self.assertIn("components/web/session", seen)

    def test_a_crux_route_source_under_another_spelling_of_the_repository_is_warned_about(self):
        with tempfile.TemporaryDirectory() as alias:
            link = Path(alias) / "alias"
            link.symlink_to(REPO)
            spelled = link / "components/web/session/web_session_routes.c"
            commands = self.configure(session=spelled)
            self.assertIn("is a Crux route source, it is not under", self.stdout)
            self.assertEqual(components_dirs(commands["web_session_routes.c"]), [])

    def test_the_weakened_form_shows_the_difference(self):
        # What the function did before: it linked the interface target to the product's target. The probe
        # reproduces that by hand, and the product's own sources then see the private directory.
        commands = self.configure("target_link_libraries(app PRIVATE crux_web_zephyr_resources)")
        self.assertIn("components/web/ports/zephyr", " ".join(components_dirs(commands["product.c"])))


if __name__ == "__main__":
    unittest.main()
