"""crux_web_assets() keeps Crux's private include directories to the sources it adds.

The function adds two sources to the product's target: the generated crux_web_assets.c and web_assets.c. They
need the adapter's private header, the public headers and the size of the body buffer. A product must not get
those for all of its own sources: the consumer check of ADR-0004 section 5 refuses a product whose sources see
components/web/adapter. The function attaches the directories and the definition to the two sources alone, as
per-source properties, and links no usage target to the product's target. These probes configure a small project
with the real function and read compile_commands.json, so they need cmake and Python 3 but no Zephyr.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
PROJECT = """cmake_minimum_required(VERSION 3.20)
project(probe C)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
include({repo}/cmake/CruxWebAssets.cmake)
# What the module and the Host build define: the usage target of the web header, with the body buffer size,
# and the adapter's private target, which carries the adapter directory and the usage target.
add_library(crux_web_api INTERFACE)
target_include_directories(crux_web_api INTERFACE {repo}/components/web/include {repo}/components/access/include)
target_compile_definitions(crux_web_api INTERFACE CRUX_WEB_BODY_BUFFER=1024u)
add_library(crux_web_adapter INTERFACE)
target_include_directories(crux_web_adapter INTERFACE {repo}/components/web/adapter)
target_link_libraries(crux_web_adapter INTERFACE crux_web_api)
add_library(app STATIC product.c)
{extra}
crux_web_assets(app FOLDER ${{CMAKE_CURRENT_LIST_DIR}}/site RESPONSE_DEADLINE_MS 3000)
get_target_property(probe_links app LINK_LIBRARIES)
get_target_property(probe_interface app INTERFACE_LINK_LIBRARIES)
message(STATUS "probe-links=[${{probe_links}}] probe-interface=[${{probe_interface}}]")
"""


def components_dirs(command):
    return [word[2:] for word in command.split() if word.startswith("-I") and "/components/" in word]


@unittest.skipUnless(shutil.which("cmake") and shutil.which("python3"), "needs cmake and Python 3")
class PrivateIncludesTest(unittest.TestCase):
    def configure(self, extra=""):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.assertNotIn(REPO, root.resolve().parents)
        (root / "product.c").write_text("int product;\n")
        (root / "site").mkdir()
        (root / "site/index.html").write_text("<!doctype html><title>x</title><p>x</p>\n")
        (root / "CMakeLists.txt").write_text(PROJECT.format(repo=REPO, extra=extra))
        result = subprocess.run(["cmake", "-S", str(root), "-B", str(root / "build")], capture_output=True,
                                text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.stdout = result.stdout + result.stderr
        commands = json.loads((root / "build/compile_commands.json").read_text())
        return {Path(entry["file"]).name: entry["command"] for entry in commands}

    def test_the_products_own_source_sees_no_directory_of_crux_components(self):
        self.assertEqual(components_dirs(self.configure()["product.c"]), [])

    def test_the_products_own_source_gets_no_definition_from_the_function(self):
        self.assertNotIn("CRUX_WEB_BODY_BUFFER", self.configure()["product.c"])

    def test_the_two_added_sources_see_what_they_need(self):
        commands = self.configure()
        for name in ("web_assets.c", "crux_web_assets.c"):
            seen = " ".join(components_dirs(commands[name]))
            for needed in ("components/web/assets", "components/web/adapter", "components/web/include",
                           "components/access/include"):
                self.assertIn(needed, seen, f"{name}: {needed}")
            self.assertIn("-DCRUX_WEB_BODY_BUFFER=1024u", commands[name], name)

    def test_the_function_links_nothing_of_crux_to_the_product(self):
        self.configure()
        links = re.search(r"probe-links=\[(.*?)\] probe-interface=\[(.*?)\]", self.stdout)
        self.assertIsNotNone(links, self.stdout)
        for value in links.groups():  # an unset property reads as <variable>-NOTFOUND
            self.assertTrue(value == "" or value.endswith("-NOTFOUND"), value)

    def test_a_property_the_caller_set_on_an_added_source_is_kept(self):
        extra = (f"set_property(SOURCE {REPO}/components/web/assets/web_assets.c "
                 "PROPERTY INCLUDE_DIRECTORIES /caller/own)")
        self.assertIn("-I/caller/own", self.configure(extra)["web_assets.c"])

    def test_the_two_added_sources_compile_with_the_per_source_properties_alone(self):
        # The only thing that shows the directories and the definition are enough: build the probe's target
        # with the host compiler. Nothing links the adapter to it, and nothing else supplies a directory.
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / "product.c").write_text("int product;\n")
        (root / "site").mkdir()
        (root / "site/index.html").write_text("<!doctype html><title>x</title><p>x</p>\n")
        (root / "CMakeLists.txt").write_text(PROJECT.format(repo=REPO, extra=""))
        configured = subprocess.run(["cmake", "-S", str(root), "-B", str(root / "build")], capture_output=True,
                                    text=True)
        self.assertEqual(configured.returncode, 0, configured.stdout + configured.stderr)
        built = subprocess.run(["cmake", "--build", str(root / "build")], capture_output=True, text=True)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)

    def test_the_weakened_form_shows_the_difference(self):
        # What the function did before: it linked the adapter's target to the product's target. The probe
        # reproduces that by hand, and the product's own source then sees the adapter directory and the size.
        commands = self.configure("target_link_libraries(app PRIVATE crux_web_adapter)")
        self.assertIn("components/web/adapter", " ".join(components_dirs(commands["product.c"])))
        self.assertIn("CRUX_WEB_BODY_BUFFER", commands["product.c"])


if __name__ == "__main__":
    unittest.main()
