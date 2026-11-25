"""Check the file layout inside each sample (samples/README.md, "Files inside a sample").

A sample root holds README.md and the folders zephyr/ (a standard Zephyr application), linux/
(a Linux program) and common/ (code both compile, or code checked as portable). samples/boards/
and samples/web/ are exempt by tree. The checks are lexical: they read paths and CMake text, so
they miss macro or transitive includes. The Linux build of common/ is the real guard.
"""
from pathlib import Path
import re
import runpy
import unittest

REPO = Path(__file__).resolve().parents[2]
SAMPLES = REPO / "samples"
EXEMPT = (SAMPLES / "boards", SAMPLES / "web")
OS_FOLDERS = {"zephyr", "linux", "common"}
ROOT_ENTRIES = OS_FOLDERS | {"README.md"}
CHECKER = REPO / "scripts/check-native-interfaces.py"


def exempt(path):
    return any(path == tree or tree in path.parents for tree in EXEMPT)


def manifests():
    return [p for name in ("sample.yaml", "testcase.yaml") for p in SAMPLES.rglob(name) if not exempt(p)]


def sample_roots():
    roots = set()
    for manifest in manifests():
        parent = manifest.parent
        roots.add(parent.parent if parent.name == "zephyr" else parent)
    for folder in SAMPLES.rglob("*"):
        if folder.is_dir() and folder.name in OS_FOLDERS and not exempt(folder):
            roots.add(folder.parent)
    return sorted(roots)


def cmake_files(folder):
    return sorted(folder.rglob("CMakeLists.txt")) + sorted(folder.rglob("*.cmake")) if folder.is_dir() else []


def rel(path):
    return path.relative_to(REPO).as_posix()


class SampleLayoutTest(unittest.TestCase):
    def test_sample_roots_hold_only_the_readme_and_os_folders(self):
        roots = sample_roots()
        self.assertGreaterEqual(len(roots), 4)
        for root in roots:
            with self.subTest(sample=rel(root)):
                self.assertTrue((root / "README.md").is_file())
                self.assertLessEqual({entry.name for entry in root.iterdir()}, ROOT_ENTRIES)

    def test_every_sample_manifest_sits_in_a_zephyr_folder(self):
        for manifest in manifests():
            with self.subTest(manifest=rel(manifest)):
                self.assertEqual(manifest.parent.name, "zephyr")
                self.assertTrue((manifest.parent / "CMakeLists.txt").is_file())

    def test_only_zephyr_folders_load_zephyr(self):
        for root in sample_roots():
            zephyr = root / "zephyr/CMakeLists.txt"
            linux = root / "linux/CMakeLists.txt"
            if zephyr.is_file():
                with self.subTest(path=rel(zephyr)):
                    self.assertIn("find_package(Zephyr", zephyr.read_text())
            if linux.is_file():
                with self.subTest(path=rel(linux)):
                    self.assertNotIn("find_package(Zephyr", linux.read_text())

    def test_no_build_names_another_os_folder(self):
        for root in sample_roots():
            for os_name, other in (("zephyr", "linux/"), ("linux", "zephyr/")):
                for path in cmake_files(root / os_name):
                    with self.subTest(path=rel(path)):
                        self.assertNotIn(other, path.read_text())
        host_builds = [REPO / "CMakeLists.txt"] + [p for p in (REPO / "tests").rglob("CMakeLists.txt")
                                                     if "find_package(Zephyr" not in p.read_text()]
        for path in host_builds:
            with self.subTest(path=rel(path)):
                self.assertNotRegex(path.read_text(), r"samples/\S*/zephyr/")

    def test_common_sources_are_shared_or_checked_as_portable(self):
        others = [REPO / "CMakeLists.txt"] + sorted((REPO / "tests").rglob("CMakeLists.txt"))
        for root in sample_roots():
            for source in sorted((root / "common").glob("*.c")):
                with self.subTest(source=rel(source)):
                    users = 0
                    asserted = False
                    for group in (cmake_files(root / "zephyr"), cmake_files(root / "linux"), others):
                        naming = [p for p in group if source.name in p.read_text()]
                        users += bool(naming)
                        asserted |= any("crux_assert_portable_consumer" in p.read_text() for p in naming)
                    self.assertTrue(users >= 2 or asserted, "compiled by fewer than two builds and not asserted")

    def test_native_interface_check_scans_every_common_source(self):
        checker = runpy.run_path(str(CHECKER))
        scanned = set()
        for pattern in checker["PORTABLE_ROOTS"]:
            for root in REPO.glob(pattern):
                candidates = root.rglob("*") if root.is_dir() else (root,)
                scanned.update(p for p in candidates if p.is_file() and p.suffix in checker["SOURCE_SUFFIXES"])
        scanned.update(REPO / name for name in checker["NETWORKING_PROFILE"])
        common = [p for pattern in ("samples/*/common", "samples/*/*/common") for folder in REPO.glob(pattern)
                  if not exempt(folder) for p in folder.rglob("*") if p.suffix in checker["SOURCE_SUFFIXES"]]
        self.assertTrue(common)
        self.assertEqual(sorted(rel(p) for p in common if p not in scanned), [])

    def test_no_include_folder_in_samples(self):
        folders = [rel(p) for p in SAMPLES.rglob("include")
                   if p.is_dir() and not exempt(p) or (p.is_dir() and SAMPLES / "boards" in p.parents)]
        self.assertEqual(folders, [])

    def test_board_samples_are_zephyr_applications_at_their_root(self):
        apps = {p.parent for name in ("sample.yaml", "testcase.yaml", "prj.conf")
                for p in (SAMPLES / "boards").rglob(name)}
        self.assertTrue(apps)
        for app in sorted(apps):
            with self.subTest(app=rel(app)):
                self.assertIn("find_package(Zephyr", (app / "CMakeLists.txt").read_text())


if __name__ == "__main__":
    unittest.main()
