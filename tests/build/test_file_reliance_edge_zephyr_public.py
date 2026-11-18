"""The Reliance Edge file system type has a public name, in the Zephyr File composition interface.

`<crux/file_reliance_edge_zephyr.h>` publishes the one constant that a composition needs to name the
file system in its `fs_mount_t`: `CRUX_FS_RELIANCE_EDGE`. It sits next to `<crux/file_zephyr.h>` and
reaches a product through the same target, `crux::file_zephyr`. These checks run on the host. They
compile the header against a stand-in for the one Zephyr header it includes, hold the private header
to the same single definition, and read the consumers' sources and CMake files. The Zephyr builds
that use the header are exercised by the Zephyr CI shards.
"""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PORT = ROOT / 'components/file/ports/zephyr'
PUBLIC_INCLUDE = PORT / 'include'
HEADER = PUBLIC_INCLUDE / 'crux/file_reliance_edge_zephyr.h'
PRIVATE_DIR = ROOT / 'zephyr/fs/reliance_edge'
PRIVATE_HEADER = PRIVATE_DIR / 'fs_reliance_edge.h'
DOMAIN_CHECK = ROOT / 'templates/product/check_domain_includes.py'
CC = os.environ.get('CC', 'cc')
FLAGS = ['-std=c17', '-Wall', '-Wextra', '-Wpedantic', '-Werror']

# The shape of <zephyr/fs/fs.h> that matters here: the first value after the in-tree types.
ZEPHYR_FS_STAND_IN = """
#ifndef STAND_IN_ZEPHYR_FS_FS_H
#define STAND_IN_ZEPHYR_FS_FS_H
enum { FS_FATFS = 0, FS_LITTLEFS, FS_EXT2, FS_TYPE_EXTERNAL_BASE };
#endif
"""

CONSUMER = """
#include <crux/file_reliance_edge_zephyr.h>
_Static_assert(CRUX_FS_RELIANCE_EDGE == FS_TYPE_EXTERNAL_BASE, "same value as before");
_Static_assert(CRUX_FS_RELIANCE_EDGE != FS_FATFS, "not the FatFs type");
int mount_type = CRUX_FS_RELIANCE_EDGE;
int main(void) { return mount_type == FS_TYPE_EXTERNAL_BASE ? 0 : 1; }
"""


def compile_source(source, includes, extra=()):
    with tempfile.TemporaryDirectory() as tmp:
        stand_in = Path(tmp) / 'stand_in/zephyr/fs'
        stand_in.mkdir(parents=True)
        (stand_in / 'fs.h').write_text(ZEPHYR_FS_STAND_IN)
        path = Path(tmp) / 'tu.c'
        path.write_text(source)
        roots = [Path(tmp) / 'stand_in', *includes]
        command = [CC, *FLAGS, *extra, *[arg for inc in roots for arg in ('-I', str(inc))],
                   '-fsyntax-only', str(path)]
        return subprocess.run(command, capture_output=True, text=True)


def sources(directory, patterns=('*.c', '*.h')):
    return [p for pattern in patterns for p in directory.glob(pattern)]


class PublicHeader(unittest.TestCase):
    def test_a_consumer_names_the_type_with_only_the_public_include_root(self):
        result = compile_source(CONSUMER, [PUBLIC_INCLUDE])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_header_includes_one_zephyr_header_and_no_other_native_header(self):
        result = compile_source(CONSUMER, [PUBLIC_INCLUDE], ['-H'])
        self.assertEqual(result.returncode, 0, result.stderr)
        included = [line.lstrip('. ').strip() for line in result.stderr.splitlines() if line.startswith('.')]
        # The stand-in root is the only place where a <zephyr/...> header can come from here.
        zephyr = [path for path in included if '/stand_in/zephyr/' in path]
        self.assertEqual([path.split('/stand_in/')[-1] for path in zephyr], ['zephyr/fs/fs.h'])
        self.assertEqual(len([path for path in included if path.endswith('/fs.h')]), 1)
        crux = [path for path in included if '/crux/' in path]
        self.assertEqual([Path(p).name for p in crux], ['file_reliance_edge_zephyr.h'])
        for path in included:
            self.assertNotRegex(path.lower(), r'nxp|cmsis|mcux|/boards?/')

    def test_the_product_domain_check_rejects_the_header_as_a_composition_interface(self):
        spec = importlib.util.spec_from_file_location('check_domain_includes', DOMAIN_CHECK)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        reason = module.classify('crux/' + HEADER.name, True, ROOT / 'domain/x.c', ROOT)
        self.assertIsNotNone(reason)
        self.assertIn('composition interface', reason)

    def test_the_public_path_is_unique_across_components(self):
        found = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / 'components').rglob(HEADER.name))
        self.assertEqual(found, ['components/file/ports/zephyr/include/crux/file_reliance_edge_zephyr.h'])

    def test_the_header_declares_a_constant_only_and_no_function(self):
        text = HEADER.read_text()
        self.assertRegex(text, r'#define CRUX_FS_RELIANCE_EDGE FS_TYPE_EXTERNAL_BASE\b')
        code = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
        # No function, no wrapper: nothing but the guard, the one include and the one macro.
        self.assertNotIn('(', code)
        self.assertEqual(re.findall(r'^#\s*define\s+(\w+)', code, re.M),
                         ['CRUX_FILE_RELIANCE_EDGE_ZEPHYR_H', 'CRUX_FS_RELIANCE_EDGE'])
        self.assertEqual(re.findall(r'^#\s*include\s+(\S+)', code, re.M), ['<zephyr/fs/fs.h>'])

    def test_the_header_records_its_tier_and_its_rules(self):
        text = ' '.join(HEADER.read_text().replace('\n *', ' ').split())
        self.assertIn('Status: Experimental (ADR-0001 decision 4)', text)
        for word in ('composition', 'crux::file_zephyr', 'fs_mount_t', 'fs_mkfs'):
            self.assertIn(word, text, word)
        # The formatter policy is cited, not restated.
        self.assertIn('docs/emmc-reliance-physical-gate.md', text)
        self.assertIn('docs/porting-to-a-new-board.md', text)
        self.assertNotIn('never formats;', text)

    def test_lines_fit_the_column_limit_of_the_format_check(self):
        for path in (HEADER, PRIVATE_HEADER):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                self.assertLessEqual(len(line), 100, '%s:%d' % (path.name, number))


class OneDefinition(unittest.TestCase):
    def test_the_type_is_defined_once_in_the_repository(self):
        definitions = []
        for base in ('components', 'zephyr', 'samples', 'tests', 'templates'):
            for path in (ROOT / base).rglob('*'):
                if path.suffix in ('.c', '.h') and re.search(r'^\s*#\s*define\s+CRUX_FS_RELIANCE_EDGE\b',
                                                              path.read_text(), re.M):
                    definitions.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(definitions, ['components/file/ports/zephyr/include/crux/file_reliance_edge_zephyr.h'])

    def test_the_private_header_still_works_and_gives_the_same_value(self):
        # No crux include root is given: the private header finds the public one by itself.
        source = ('#include "fs_reliance_edge.h"\n'
                  '_Static_assert(CRUX_FS_RELIANCE_EDGE == FS_TYPE_EXTERNAL_BASE, "same value");\n'
                  'int main(void) { return 0; }\n')
        result = compile_source(source, [PRIVATE_DIR])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_private_header_includes_the_public_one_and_defines_nothing(self):
        text = PRIVATE_HEADER.read_text()
        self.assertRegex(text, r'#include\s+"\.\./\.\./\.\./components/file/ports/zephyr/include/crux/'
                               r'file_reliance_edge_zephyr\.h"')
        self.assertNotRegex(text, r'#\s*define\s+CRUX_FS_RELIANCE_EDGE\b')

    def test_both_headers_can_be_included_together_in_either_order(self):
        for first, second in (('"fs_reliance_edge.h"', '<crux/file_reliance_edge_zephyr.h>'),
                              ('<crux/file_reliance_edge_zephyr.h>', '"fs_reliance_edge.h"')):
            with self.subTest(first=first):
                source = '#include %s\n#include %s\nint main(void) { return CRUX_FS_RELIANCE_EDGE != 0; }\n' % (
                    first, second)
                result = compile_source(source, [PRIVATE_DIR, PUBLIC_INCLUDE])
                self.assertEqual(result.returncode, 0, result.stderr)


class Consumers(unittest.TestCase):
    PUBLIC_ONLY = ('samples/storage_emmc', 'samples/storage_reliance_sd',
                   'tests/native/file_emmc_composition', 'tests/native/configuration_settings_reliance')

    def test_the_compositions_name_the_type_through_the_public_header(self):
        for name in self.PUBLIC_ONLY:
            directory = ROOT / name
            with self.subTest(consumer=name):
                for source in sources(directory):
                    self.assertNotIn('fs_reliance_edge.h', source.read_text(), source.name)
                self.assertNotIn('zephyr/fs/reliance_edge', (directory / 'CMakeLists.txt').read_text())

    def test_each_of_them_links_the_public_target_that_carries_the_header(self):
        for name in self.PUBLIC_ONLY:
            with self.subTest(consumer=name):
                self.assertIn('crux::file_zephyr', (ROOT / name / 'CMakeLists.txt').read_text())

    def test_the_sample_compositions_include_the_public_header_in_format_order(self):
        for relative in ('samples/storage_emmc/emmc_storage.c', 'samples/storage_reliance_sd/format.c'):
            with self.subTest(source=relative):
                lines = (ROOT / relative).read_text().splitlines()
                self.assertIn('#include <crux/file_reliance_edge_zephyr.h>', lines)
                angle = [line for line in lines if line.startswith('#include <')]
                self.assertEqual(angle, sorted(angle))

    def test_the_native_test_of_a_consumer_mount_uses_the_public_header(self):
        text = (ROOT / 'tests/native/file_emmc_composition/main.c').read_text()
        self.assertIn('#include <crux/file_reliance_edge_zephyr.h>', text)
        self.assertNotIn('fs_reliance_edge.h', text)

    def test_one_native_test_still_includes_the_private_header(self):
        # The provider's own test keeps the private spelling, so the private header stays covered.
        text = (ROOT / 'tests/native/file_reliance/main.c').read_text()
        self.assertIn('#include "fs_reliance_edge.h"', text)

    def test_the_provider_includes_its_private_header(self):
        self.assertIn('fs_reliance_edge.h', (PRIVATE_DIR / 'fs_reliance_edge.c').read_text())


class Documents(unittest.TestCase):
    def test_the_composition_interface_document_names_the_header_and_its_tier(self):
        text = ' '.join((ROOT / 'docs/file-composition-interface.md').read_text().split())
        self.assertIn('`<crux/file_reliance_edge_zephyr.h>`', text)
        self.assertIn('`CRUX_FS_RELIANCE_EDGE`', text)
        self.assertIn('Experimental', text)

    def test_the_decisions_say_whose_choices_they_are(self):
        text = ' '.join((ROOT / 'docs/file-composition-interface.md').read_text().split())
        section = text.split('## The Reliance Edge file system type')[-1]
        self.assertIn("The author's choices within the owner's approval", section)
        self.assertIn('name is pending the owner', section)
        self.assertNotIn('follows the `<crux/NAME_zephyr.h>` pattern of the [composition interface rules]', section)
        self.assertIn('extends rule 1', section)
        self.assertIn('templates/product/check_domain_includes.py', section)

    def test_the_verification_table_does_not_claim_a_host_ci_run(self):
        text = ' '.join((ROOT / 'docs/file-composition-interface.md').read_text().split())
        section = text.split('## The Reliance Edge file system type')[-1]
        self.assertIn('Host CI had not run when this was written', section)

    def test_the_rules_table_names_the_header_in_rules_1_4_5_and_6(self):
        lines = (ROOT / 'docs/composition-interfaces.md').read_text().splitlines()
        for number in ('1', '4', '5', '6'):
            row = [line for line in lines if line.startswith('| %s |' % number)]
            self.assertEqual(len(row), 1, number)
            with self.subTest(rule=number):
                self.assertIn('file_reliance_edge_zephyr.h', row[0])
        self.assertIn('Experimental', [line for line in lines if line.startswith('| 6 |')][0])
        self.assertIn('<zephyr/fs/fs.h>', [line for line in lines if line.startswith('| 5 |')][0])

    def test_the_product_guide_says_the_header_is_composition_code_only(self):
        text = ' '.join((ROOT / 'templates/product/README.md').read_text().split())
        self.assertIn('`<crux/file_reliance_edge_zephyr.h>`', text)

    def test_the_readiness_table_records_the_tier_of_the_header(self):
        text = (ROOT / 'docs/component-readiness.md').read_text()
        row = [line for line in text.splitlines() if line.startswith('| `file` on Reliance Edge')]
        self.assertEqual(len(row), 1)
        self.assertIn('`<crux/file_reliance_edge_zephyr.h>`', row[0])
        self.assertIn('Experimental', row[0])


if __name__ == '__main__':
    unittest.main()
