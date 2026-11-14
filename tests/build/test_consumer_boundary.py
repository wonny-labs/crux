"""Build consumers independently and reject native public usage requirements."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
CMAKE = shutil.which("cmake")


@unittest.skipUnless(CMAKE, "CMake is required")
class ConsumerBoundaryTest(unittest.TestCase):
    def configure(self, body, guard=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "CMakeLists.txt").write_text(
                'cmake_minimum_required(VERSION 3.28)\nproject(probe LANGUAGES C)\n'
                f'include("{guard or REPO / "cmake/CruxConsumerBoundary.cmake"}")\n' + body)
            return subprocess.run([CMAKE, "-S", str(root), "-B", str(root / "build")],
                                  capture_output=True, text=True)

    def test_system_provider_selection(self):
        for provider in ('', 'unsupported', 'host;zephyr'):
            with self.subTest(provider=provider):
                result = self.configure(
                    f'add_subdirectory("{REPO}/components/base" base)\n'
                    f'set(CRUX_SYSTEM_PROVIDER "{provider}" CACHE STRING "")\n'
                    f'add_subdirectory("{REPO}/components/system" system)\n')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Crux System unsupported provider", result.stdout + result.stderr)

    def test_system_usage_rejects_private_leakage(self):
        result = self.configure(
            f'add_subdirectory("{REPO}/components/base" base)\n'
            f'add_subdirectory("{REPO}/components/system" system)\n'
            f'target_include_directories(crux_system_api INTERFACE "{REPO}/components/system/ports/zephyr")\n'
            'crux_assert_portable_usage(crux::system)\n')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("native consumer requirement", result.stdout + result.stderr)

    def test_logging_provider_selection(self):
        for provider in ('', 'unsupported', 'host;zephyr'):
            with self.subTest(provider=provider):
                result = self.configure(
                    'set(CRUX_BUILD_LOGGING ON CACHE BOOL "Required capability")\n'
                    f'set(CRUX_LOGGING_PROVIDER "{provider}" CACHE STRING "")\n'
                    f'add_subdirectory("{REPO}" crux)\n')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Crux Logging unsupported provider", result.stdout + result.stderr)

    def test_serial_provider_selection(self):
        for provider in ('', 'unsupported', 'host;zephyr'):
            with self.subTest(provider=provider):
                result = self.configure(
                    'set(CRUX_BUILD_SERIAL ON CACHE BOOL "Required capability")\n'
                    f'set(CRUX_SERIAL_PROVIDER "{provider}" CACHE STRING "")\n'
                    f'add_subdirectory("{REPO}" crux)\n')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Crux Serial unsupported provider", result.stdout + result.stderr)

    def test_independent_c_and_cpp_consumers(self):
        with tempfile.TemporaryDirectory() as temporary:
            subprocess.run([CMAKE, "-S", str(REPO / "tests/consumer_boundary"),
                            "-B", temporary, f"-DCRUX_SOURCE_DIR={REPO}"], check=True,
                           capture_output=True)
            subprocess.run([CMAKE, "--build", temporary], check=True, capture_output=True)
            for name in ("consumer_c", "consumer_cpp"):
                subprocess.run([str(Path(temporary) / name)], check=True)

    def test_transitive_native_requirements_are_rejected(self):
        for edge in ('zephyr_interface', '$<BUILD_INTERFACE:zephyr_interface>',
                     '$<$<BOOL:1>:zephyr_interface>',
                     '$<IF:$<CONFIG:Debug>,zephyr_interface,portable>',
                     '$<LINK_ONLY:zephyr_interface>',
                     '$<TARGET_NAME_IF_EXISTS:zephyr_interface>', '-lzephyr',
                     '/sdk/lib/libzephyr.a'):
            with self.subTest(edge=edge):
                result = self.configure('add_library(zephyr_interface INTERFACE)\n'
                                        'add_library(portable INTERFACE)\n'
                                        'add_library(wrapper INTERFACE)\n'
                                        f'target_link_libraries(wrapper INTERFACE "{edge}")\n'
                                        'crux_assert_portable_usage(wrapper)\n')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("native consumer requirement", result.stdout + result.stderr)

    def test_superseded_monotonic_composition_is_unavailable(self):
        result = self.configure('set(CRUX_BUILD_TIME ON CACHE BOOL "")\n'
                                'set(CRUX_TIME_PROVIDER memory CACHE STRING "")\n'
                                f'add_subdirectory("{REPO}" crux)\n'
                                'if(TARGET crux::monotonic OR TARGET crux_monotonic '
                                'OR TARGET crux::monotonic_linux OR TARGET crux_monotonic_linux)\n'
                                'message(FATAL_ERROR "superseded Monotonic composition remains")\n'
                                'endif()\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((REPO / 'components/monotonic/CMakeLists.txt').exists())

    def test_linux_composition_targets_are_rejected_in_portable_consumers(self):
        for target in ('crux::queue_linux', 'crux_queue_linux'):
            for route in ('direct', 'interface', 'static_private', 'alias'):
                with self.subTest(target=target, route=route):
                    body = ('set(CRUX_BUILD_QUEUE ON CACHE BOOL "")\n'
                            f'add_subdirectory("{REPO}" crux)\n'
                            'file(WRITE "${CMAKE_BINARY_DIR}/probe.c" "int probe(void) { return 0; }")\n'
                            'add_library(consumer STATIC "${CMAKE_BINARY_DIR}/probe.c")\n')
                    if route == 'interface':
                        body += ('add_library(wrapper INTERFACE)\n'
                                 f'target_link_libraries(wrapper INTERFACE {target})\n')
                        edge = 'wrapper'
                    elif route == 'static_private':
                        body += ('add_library(wrapper STATIC "${CMAKE_BINARY_DIR}/probe.c")\n'
                                 f'target_link_libraries(wrapper PRIVATE {target})\n')
                        edge = 'wrapper'
                    elif route == 'alias':
                        implementation = 'crux_queue_linux'
                        body += f'add_library(application_alias ALIAS {implementation})\n'
                        edge = 'application_alias'
                    else:
                        edge = target
                    body += (f'target_link_libraries(consumer PRIVATE {edge})\n'
                             'crux_assert_portable_consumer(consumer)\n')
                    result = self.configure(body)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('native consumer requirement', result.stdout + result.stderr)

    def test_linux_composition_builds_and_runs_with_portable_facades(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(REPO / 'tests/external_application', root / 'application')
            build = root / 'build'
            for command in (
                    [CMAKE, '-S', str(root / 'application'), '-B', str(build), '-G', 'Ninja',
                     f'-DCRUX_SOURCE_DIR={REPO}', '-DPROFILE=messaging',
                     '-DFETCHCONTENT_FULLY_DISCONNECTED=ON'],
                    [CMAKE, '--build', str(build), '--parallel', '2'],
                    [str(build / 'external_app')]):
                result = subprocess.run(command, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_typed_time_native_composition_builds_and_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            for command in (
                    [CMAKE, '-S', str(REPO / 'tests/external_application'), '-B', temporary, '-G', 'Ninja',
                     f'-DCRUX_SOURCE_DIR={REPO}', '-DPROFILE=time'],
                    [CMAKE, '--build', temporary, '--parallel', '2'],
                    ['ctest', '--test-dir', temporary, '--output-on-failure']):
                result = subprocess.run(command, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_direct_link_injection_is_rejected(self):
        result = self.configure('add_library(zephyr_interface INTERFACE)\n'
                                'add_library(wrapper INTERFACE)\n'
                                'set_property(TARGET wrapper PROPERTY INTERFACE_LINK_LIBRARIES_DIRECT zephyr_interface)\n'
                                'crux_assert_portable_usage(wrapper)\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("native consumer requirement", result.stdout + result.stderr)

    def test_transitive_private_or_native_include_is_rejected(self):
        for path in ('/sdk/zephyr/include', '/sdk/modules/hal/nxp/include',
                     f'{REPO}/components/time/src',
                     f'{REPO}/components/time/ports/linux',
                     f'{REPO}/components/time/ports/zephyr',
                     f'{REPO}/components/netif/host',
                     f'{REPO}/components/netif/zephyr',
                     f'{REPO}/components/netif/ports/linux',
                     f'{REPO}/components/netif/ports/zephyr',
                     f'{REPO}/components/file/ports/linux',
                     f'{REPO}/components/sockets/ports/zephyr'):
            with self.subTest(path=path):
                result = self.configure('add_library(provider INTERFACE)\n'
                                        f'target_include_directories(provider INTERFACE "{path}")\n'
                                        'add_library(wrapper INTERFACE)\n'
                                        'target_link_libraries(wrapper INTERFACE provider)\n'
                                        'crux_assert_portable_usage(wrapper)\n')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("native consumer requirement", result.stdout + result.stderr)

    def test_component_private_port_includes_are_rejected(self):
        for component in ('thread', 'sync', 'queue', 'time', 'delay'):
            for port in ('src', 'host', 'zephyr', 'ports/linux', 'ports/zephyr'):
                for public in (False, True):
                    with self.subTest(component=component, port=port, public=public):
                        path = f'{REPO}/components/{component}/{port}'
                        if public:
                            body = ('add_library(provider INTERFACE)\n'
                                    f'target_include_directories(provider INTERFACE "{path}")\n'
                                    'add_library(wrapper INTERFACE)\n'
                                    'target_link_libraries(wrapper INTERFACE provider)\n'
                                    'crux_assert_portable_usage(wrapper)\n')
                        else:
                            body = ('file(WRITE "${CMAKE_BINARY_DIR}/main.c" "int main(void) { return 0; }")\n'
                                    'add_executable(consumer "${CMAKE_BINARY_DIR}/main.c")\n'
                                    f'target_include_directories(consumer PRIVATE "{path}")\n'
                                    'crux_assert_portable_consumer(consumer)\n')
                        result = self.configure(body)
                        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertIn("native consumer requirement", result.stdout + result.stderr)

    def test_opaque_generator_expression_is_rejected(self):
        result = self.configure('add_library(wrapper INTERFACE)\n'
                                'target_link_libraries(wrapper INTERFACE "$<TARGET_PROPERTY:other,LINK_LIBRARIES>")\n'
                                'crux_assert_portable_usage(wrapper)\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported consumer expression", result.stdout + result.stderr)

    def test_private_native_requirements_on_provider_are_allowed(self):
        result = self.configure('file(WRITE "${CMAKE_BINARY_DIR}/provider.c" "int provider(void) { return 0; }")\n'
                                'add_library(zephyr_interface INTERFACE)\n'
                                'add_library(provider SHARED "${CMAKE_BINARY_DIR}/provider.c")\n'
                                'target_link_libraries(provider PRIVATE zephyr_interface)\n'
                                'target_include_directories(provider PRIVATE /sdk/zephyr/include)\n'
                                'add_library(wrapper INTERFACE)\n'
                                'target_link_libraries(wrapper INTERFACE provider)\n'
                                'crux_assert_portable_usage(wrapper)\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_consumer_private_native_requirements_are_rejected(self):
        for requirement in ('target_link_libraries(consumer PRIVATE zephyr_interface)',
                            'target_link_libraries(consumer PRIVATE nxp_sdk)',
                            'target_include_directories(consumer PRIVATE /sdk/zephyr/include)',
                            f'target_include_directories(consumer PRIVATE {REPO}/components/netif/ports/linux)',
                            f'target_include_directories(consumer PRIVATE {REPO}/components/netif/ports/zephyr)'):
            with self.subTest(requirement=requirement):
                result = self.configure('file(WRITE "${CMAKE_BINARY_DIR}/main.c" "int main(void) { return 0; }")\n'
                                        'add_library(zephyr_interface INTERFACE)\n'
                                        'add_library(nxp_sdk INTERFACE)\n'
                                        'add_executable(consumer "${CMAKE_BINARY_DIR}/main.c")\n'
                                        + requirement + '\ncrux_assert_portable_consumer(consumer)\n')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("native consumer requirement", result.stdout + result.stderr)

    def test_native_threading_requirements_are_rejected(self):
        requirements = [('target_link_libraries', value) for value in
                        ('Threads::Threads', 'pthread', '-pthread', '-lpthread',
                         '/usr/lib/libpthread.so')]
        requirements += [('target_compile_options', '-pthread'),
                         ('target_link_options', '-pthread'),
                         ('target_link_options', 'LINKER:-lpthread'),
                         ('target_compile_options', 'SHELL:-pthread')]
        for command, value in requirements:
            for public in (False, True):
                with self.subTest(command=command, value=value, public=public):
                    body = ('find_package(Threads REQUIRED)\n'
                            'file(WRITE "${CMAKE_BINARY_DIR}/main.c" "int main(void) { return 0; }")\n')
                    if public:
                        body += ('add_library(wrapper INTERFACE)\n'
                                 'add_library(facade INTERFACE)\n'
                                 'target_link_libraries(facade INTERFACE wrapper)\n'
                                 f'{command}(wrapper INTERFACE "{value}")\n'
                                 'crux_assert_portable_usage(facade)\n')
                    else:
                        body += ('add_executable(consumer "${CMAKE_BINARY_DIR}/main.c")\n'
                                 f'{command}(consumer PRIVATE "{value}")\n'
                                 'crux_assert_portable_consumer(consumer)\n')
                    result = self.configure(body)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("native consumer requirement", result.stdout + result.stderr)

    def test_static_provider_native_link_only_is_rejected(self):
        for native in ('zephyr_interface', 'Threads::Threads'):
            with self.subTest(native=native):
                result = self.configure('find_package(Threads REQUIRED)\n'
                                        'file(WRITE "${CMAKE_BINARY_DIR}/provider.c" "int provider(void) { return 0; }")\n'
                                        'add_library(zephyr_interface INTERFACE)\n'
                                        'add_library(provider STATIC "${CMAKE_BINARY_DIR}/provider.c")\n'
                                        f'target_link_libraries(provider PRIVATE {native})\n'
                                        'add_library(facade INTERFACE)\n'
                                        'target_link_libraries(facade INTERFACE provider)\n'
                                        'crux_assert_portable_usage(facade)\n')
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("native consumer requirement", result.stdout + result.stderr)

    def test_static_provider_private_native_composition_builds_and_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native_include = root / "native" / "zephyr"
            native_include.mkdir(parents=True)
            (native_include / "detail.h").write_text('#define NATIVE_RESULT 42\n')
            public_include = root / "public"
            public_include.mkdir()
            (public_include / "api.h").write_text('int provider(void);\nint portable_consumer(void);\n')
            (root / "provider.c").write_text(
                '#include "api.h"\n#include <zephyr/detail.h>\n#include <pthread.h>\n'
                '#ifndef CRUX_PROVIDER_NATIVE\n#error missing provider flag\n#endif\n'
                'static void *run(void *value) { return value; }\n'
                'int provider(void) { pthread_t thread; void *out; int value = NATIVE_RESULT;\n'
                'if (pthread_create(&thread, 0, run, &value) || pthread_join(thread, &out)) return 0;\n'
                'return *(int *)out; }\n')
            (root / "consumer.c").write_text(
                '#include "api.h"\n#ifdef CRUX_PROVIDER_NATIVE\n#error leaked provider flag\n#endif\n'
                'int portable_consumer(void) { return provider(); }\n')
            (root / "main.c").write_text(
                '#include "api.h"\nint main(void) { return portable_consumer() == 42 ? 0 : 1; }\n')
            (root / "CMakeLists.txt").write_text(
                'cmake_minimum_required(VERSION 3.28)\nproject(static_composition LANGUAGES C)\n'
                f'include("{REPO}/cmake/CruxConsumerBoundary.cmake")\n'
                'set(CMAKE_EXPORT_COMPILE_COMMANDS ON)\nfind_package(Threads REQUIRED)\n'
                'add_library(api INTERFACE)\n'
                'target_include_directories(api INTERFACE "${CMAKE_CURRENT_SOURCE_DIR}/public")\n'
                'add_library(zephyr_interface INTERFACE)\n'
                'target_include_directories(zephyr_interface INTERFACE "${CMAKE_CURRENT_SOURCE_DIR}/native")\n'
                'target_compile_definitions(zephyr_interface INTERFACE CRUX_PROVIDER_NATIVE)\n'
                'add_library(provider STATIC provider.c)\n'
                'target_link_libraries(provider PRIVATE api zephyr_interface Threads::Threads)\n'
                'target_compile_options(provider PRIVATE -pthread)\n'
                'add_library(consumer STATIC consumer.c)\n'
                'target_link_libraries(consumer PRIVATE api)\n'
                'crux_assert_portable_usage(api)\ncrux_assert_portable_consumer(consumer)\n'
                '# The native composition independently selects the implementation.\n'
                'add_executable(composition main.c)\n'
                'target_link_libraries(composition PRIVATE api consumer provider)\n')
            build = root / "build"
            for command in ([CMAKE, "-S", str(root), "-B", str(build)],
                            [CMAKE, "--build", str(build)], [str(build / "composition")]):
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            commands = json.loads((build / "compile_commands.json").read_text())
            consumer = next(item['command'] for item in commands
                            if Path(item['file']).name == 'consumer.c')
            provider = next(item['command'] for item in commands
                            if Path(item['file']).name == 'provider.c')
            for private in ('/native', 'CRUX_PROVIDER_NATIVE', '-pthread'):
                self.assertNotIn(private, consumer)
                self.assertIn(private, provider)

    def test_real_zephyr_facade_has_no_native_transitives(self):
        result = self.configure(f'include("{REPO}/tests/consumer_boundary/mock_zephyr.cmake")\n'
                                f'add_subdirectory("{REPO}/zephyr" zephyr-module)\n'
                                'crux_assert_portable_usage(crux::base crux::time)\n'
                                'get_property(libraries GLOBAL PROPERTY ZEPHYR_LIBS)\n'
                                'if(NOT "crux_time_common" IN_LIST libraries OR NOT "crux_time_zephyr" IN_LIST libraries)\n'
                                '  message(FATAL_ERROR "missing native image registration")\nendif()\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_selected_sysroot_is_only_a_standard_compile_option(self):
        cases = (
            ("/sdk/zephyr/standard", "INTERFACE_COMPILE_OPTIONS", "--sysroot=/sdk/zephyr/standard", True),
            ("/sdk/zephyr/standard", "INTERFACE_COMPILE_OPTIONS", "--sysroot=/sdk/zephyr/./standard", True),
            ("/sdk/zephyr/standard", "INTERFACE_COMPILE_OPTIONS", "--sysroot=/sdk/zephyr/other", False),
            ("/sdk/zephyr/standard", "INTERFACE_COMPILE_OPTIONS", "--sysroot=/sdk/zephyr/standard/child", False),
            ("/sdk/zephyr/standard", "INTERFACE_COMPILE_OPTIONS", "--sysroot=/sdk/zephyr/standard -include board.h", False),
            ("/sdk/zephyr/standard", "INTERFACE_COMPILE_OPTIONS", "SHELL:--sysroot=/sdk/zephyr/standard", False),
            ("/sdk/zephyr/standard", "INTERFACE_INCLUDE_DIRECTORIES", "/sdk/zephyr/standard", False),
            ("/sdk/zephyr/standard", "INTERFACE_LINK_OPTIONS", "--sysroot=/sdk/zephyr/standard", False),
            (None, "INTERFACE_COMPILE_OPTIONS", "--sysroot=/sdk/zephyr/standard", False),
            ("relative", "INTERFACE_COMPILE_OPTIONS", "--sysroot=/sdk/zephyr/standard", False),
        )
        for root, prop, value, valid in cases:
            with self.subTest(root=root, prop=prop, value=value):
                body = f'set(SYSROOT_DIR "{root}")\n' if root else ''
                body += ('add_library(portable INTERFACE)\n'
                         f'set_property(TARGET portable PROPERTY {prop} "{value}")\n'
                         'crux_assert_portable_usage(portable)\n')
                result = self.configure(body)
                self.assertEqual(result.returncode == 0, valid, result.stdout + result.stderr)
                if not valid:
                    self.assertIn("native consumer requirement", result.stdout + result.stderr)

    def test_real_messaging_facades_preserve_selected_toolchain_flags(self):
        result = self.configure(f'include("{REPO}/tests/consumer_boundary/mock_zephyr.cmake")\n'
                                'set(CONFIG_CRUX_TIME ON)\nset(CONFIG_CRUX_THREAD ON)\nset(CONFIG_CRUX_SYNC ON)\n'
                                'set(CONFIG_CRUX_QUEUE ON)\n'
                                'add_custom_target(zephyr_generated_headers)\n'
                                'function(zephyr_append_cmake_library name)\n'
                                'set_property(GLOBAL APPEND PROPERTY ZEPHYR_LIBS "${name}")\n'
                                'endfunction()\n'
                                'set(SYSROOT_DIR "/sdk/zephyr/standard")\n'
                                'set(TOOLCHAIN_C_FLAGS "--sysroot=/sdk/zephyr/standard;-mcpu=cortex-m7")\n'
                                f'add_subdirectory("{REPO}/zephyr" zephyr-module)\n'
                                'crux_assert_portable_usage(crux::thread crux::sync crux::queue crux::time)\n'
                                'get_property(libraries GLOBAL PROPERTY ZEPHYR_LIBS)\n'
                                'foreach(component IN ITEMS thread sync)\n'
                                'if(NOT "crux_${component}_zephyr" IN_LIST libraries)\n'
                                'message(FATAL_ERROR "missing native ${component} registration")\nendif()\n'
                                'get_target_property(includes crux_${component}_api INTERFACE_INCLUDE_DIRECTORIES)\n'
                                f'if(NOT includes STREQUAL "{REPO}/components/${{component}}/include")\n'
                                'message(FATAL_ERROR "${component} public include path is not canonical")\nendif()\n'
                                'get_target_property(flags crux_${component}_api INTERFACE_COMPILE_OPTIONS)\n'
                                'if(NOT "--sysroot=/sdk/zephyr/standard" IN_LIST flags OR NOT "-mcpu=cortex-m7" IN_LIST flags)\n'
                                'message(FATAL_ERROR "${component} toolchain flags lost")\nendif()\n'
                                'get_target_property(sources crux_${component}_zephyr SOURCES)\n'
                                'if(NOT "${sources}" MATCHES "src/${component}[.]c" OR NOT "${sources}" MATCHES "ports/zephyr/${component}_native[.]c")\n'
                                'message(FATAL_ERROR "missing native ${component} implementation")\nendif()\n'
                                'endforeach()\n'
                                'get_target_property(flags crux_queue INTERFACE_COMPILE_OPTIONS)\n'
                                'if(NOT "--sysroot=/sdk/zephyr/standard" IN_LIST flags OR NOT "-mcpu=cortex-m7" IN_LIST flags)\n'
                                'message(FATAL_ERROR "toolchain flags lost")\nendif()\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_real_zephyr_networking_facades_are_portable(self):
        result = self.configure(f'include("{REPO}/tests/consumer_boundary/mock_zephyr.cmake")\n'
                                'set(CONFIG_CRUX_SOCKETS ON)\nset(CONFIG_CRUX_NETIF ON)\n'
                                'add_custom_target(zephyr_generated_headers)\n'
                                f'add_subdirectory("{REPO}/zephyr" zephyr-module)\n'
                                'crux_assert_portable_usage(crux::sockets crux::netif)\n'
                                'get_property(libraries GLOBAL PROPERTY ZEPHYR_LIBS)\n'
                                'if(NOT "crux_netif_provider" IN_LIST libraries)\n'
                                'message(FATAL_ERROR "missing native netif registration")\nendif()\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_close_declaration_exception_does_not_allow_other_private_requirements(self):
        header = REPO / "components/sockets/ports/zephyr/close_declaration.h"
        for target, option in (("other", f"SHELL:-include {header}"),
                               ("crux_sockets", f"SHELL:-include {header} -pthread"),
                               ("crux_sockets", f"SHELL:-include {header.parent}/other.h")):
            with self.subTest(target=target, option=option):
                result = self.configure(f'add_library({target} INTERFACE)\n'
                                        f'target_compile_options({target} INTERFACE "{option}")\n'
                                        f'crux_assert_portable_usage({target})\n')
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("native consumer requirement", result.stdout + result.stderr)

    def test_close_declaration_exception_rejects_modified_header(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "cmake").mkdir()
            shutil.copy2(REPO / "cmake/CruxConsumerBoundary.cmake", root / "cmake")
            header = root / "components/sockets/ports/zephyr/close_declaration.h"
            header.parent.mkdir(parents=True)
            header.write_text('int close(int descriptor);\n#include <zephyr/kernel.h>\n')
            (root / "CMakeLists.txt").write_text(
                'cmake_minimum_required(VERSION 3.28)\nproject(modified_declaration LANGUAGES C)\n'
                f'include("{root}/cmake/CruxConsumerBoundary.cmake")\n'
                'add_library(crux_sockets INTERFACE)\n'
                f'target_compile_options(crux_sockets INTERFACE "SHELL:-include {header}")\n'
                'crux_assert_portable_usage(crux_sockets)\n')
            result = subprocess.run([CMAKE, "-S", str(root), "-B", str(root / "build")],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("unreviewed socket close declaration", result.stdout + result.stderr)

    def test_host_time_rejects_conflicting_provider(self):
        result = self.configure('set(CRUX_BUILD_TIME ON CACHE BOOL "")\n'
                                'set(CRUX_TIME_PROVIDER memory CACHE STRING "")\n'
                                f'add_subdirectory("{REPO}" crux)\n'
                                'add_library(other_backend INTERFACE)\n'
                                'set_property(TARGET other_backend PROPERTY INTERFACE_CRUX_TIME_BACKEND zephyr_rtc)\n'
                                'file(WRITE "${CMAKE_BINARY_DIR}/main.c" "int main(void) { return 0; }")\n'
                                'add_executable(consumer "${CMAKE_BINARY_DIR}/main.c")\n'
                                'target_link_libraries(consumer PRIVATE crux::time other_backend)\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("INTERFACE_CRUX_TIME_BACKEND", result.stdout + result.stderr)

    def test_time_common_cannot_link_without_selected_provider(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "main.c").write_text('#include <crux/time.h>\n'
                                          'int main(void) { return crux_realtime_init(); }\n')
            (root / "CMakeLists.txt").write_text(
                'cmake_minimum_required(VERSION 3.28)\nproject(missing_time_provider LANGUAGES C)\n'
                'set(CRUX_BUILD_TIME ON CACHE BOOL "")\n'
                'set(CRUX_TIME_PROVIDER memory CACHE STRING "")\n'
                f'add_subdirectory("{REPO}" crux)\n'
                'add_executable(consumer main.c)\n'
                'target_link_libraries(consumer PRIVATE crux_time_common)\n')
            subprocess.run([CMAKE, "-S", str(root), "-B", str(root / "build")],
                           check=True, capture_output=True)
            result = subprocess.run([CMAKE, "--build", str(root / "build"), "--target", "consumer"],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("crux_realtime_impl_", result.stdout + result.stderr)

    def test_zephyr_time_excludes_memory_and_test_controls(self):
        result = self.configure(f'include("{REPO}/tests/consumer_boundary/mock_zephyr.cmake")\n'
                                f'add_subdirectory("{REPO}/zephyr" zephyr-module)\n'
                                'get_property(libraries GLOBAL PROPERTY ZEPHYR_LIBS)\n'
                                'foreach(library IN LISTS libraries)\n'
                                '  get_target_property(sources ${library} SOURCES)\n'
                                '  get_target_property(definitions ${library} COMPILE_DEFINITIONS)\n'
                                '  if("${sources}" MATCHES "time_port_memory" OR\n'
                                '     "${definitions}" MATCHES "CRUX_TIME_TESTING")\n'
                                '    message(FATAL_ERROR "development Time implementation in production")\n'
                                '  endif()\n'
                                'endforeach()\n'
                                'get_target_property(provider crux_time_zephyr SOURCES)\n'
                                'if(NOT "${provider}" MATCHES "ports/zephyr/time_port_zephyr.c")\n'
                                '  message(FATAL_ERROR "missing native Time implementation")\n'
                                'endif()\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_zephyr_rtc_adapter_requires_explicit_selection(self):
        for enabled in ('ON', 'OFF'):
            with self.subTest(enabled=enabled):
                result = self.configure(
                    f'include("{REPO}/tests/consumer_boundary/mock_zephyr.cmake")\n'
                    f'set(CONFIG_CRUX_TIME_RTC {enabled})\n'
                    f'add_subdirectory("{REPO}/zephyr" zephyr-module)\n'
                    'get_target_property(sources crux_time_zephyr SOURCES)\n'
                    'if(CONFIG_CRUX_TIME_RTC)\n'
                    '  if(NOT "${sources}" MATCHES "time_rtc_zephyr.c")\n'
                    '    message(FATAL_ERROR "explicit RTC adapter missing")\n'
                    '  endif()\n'
                    'elseif("${sources}" MATCHES "time_rtc_zephyr.c")\n'
                    '  message(FATAL_ERROR "RTC adapter selected implicitly")\n'
                    'endif()\n')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_zephyr_facade_preserves_backend_conflict(self):
        result = self.configure(f'include("{REPO}/tests/consumer_boundary/mock_zephyr.cmake")\n'
                                f'add_subdirectory("{REPO}/zephyr" zephyr-module)\n'
                                'add_library(other_backend INTERFACE)\n'
                                'set_property(TARGET other_backend PROPERTY INTERFACE_CRUX_TIME_BACKEND host)\n'
                                'set_property(TARGET other_backend APPEND PROPERTY COMPATIBLE_INTERFACE_STRING CRUX_TIME_BACKEND)\n'
                                'file(WRITE "${CMAKE_BINARY_DIR}/main.c" "int main(void) { return 0; }")\n'
                                'add_executable(consumer "${CMAKE_BINARY_DIR}/main.c")\n'
                                'target_link_libraries(consumer PRIVATE crux::time other_backend)\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("INTERFACE_CRUX_TIME_BACKEND", result.stdout + result.stderr)


WRAP_GUARD_FUNCTION = "_crux_refuse_crux_link_wrap"

# Spellings of a link-time wrap of one symbol, as the build of a consumer can write them.
WRAP_FORMS = {
    "wl_equals": "-Wl,--wrap={symbol}",
    "wl_comma": "-Wl,--wrap,{symbol}",
    "wl_single_dash": "-Wl,-wrap={symbol}",
    "wl_abbreviated": "-Wl,--wra={symbol}",
    "wl_second_of_two": "-Wl,--wrap=sys_reboot,--wrap={symbol}",
    "wl_after_other_option": "-Wl,-Map=probe.map,--wrap={symbol}",
    "linker_equals": "LINKER:--wrap={symbol}",
    "linker_comma": "LINKER:--wrap,{symbol}",
    "shell_xlinker": "SHELL:-Xlinker --wrap -Xlinker {symbol}",
    "shell_wl": "SHELL:-Wl,--wrap={symbol}",
    "bare_equals": "--wrap={symbol}",
    "split_linker": "LINKER:--wrap;LINKER:{symbol}",
    "split_xlinker": "-Xlinker;--wrap;-Xlinker;{symbol}",
    "split_wl": "-Wl,--wrap;-Wl,{symbol}",
    "genex_build_interface": "$<BUILD_INTERFACE:-Wl,--wrap={symbol}>",
    "genex_condition": "$<$<BOOL:1>:-Wl,--wrap={symbol}>",
}


@unittest.skipUnless(CMAKE, "CMake is required")
class LinkTimeWrapTest(unittest.TestCase):
    """ADR-0005 S6: the guard refuses a link-time wrap of a Crux symbol, by symbol identity."""

    PROBE = ('file(WRITE "${CMAKE_BINARY_DIR}/probe.c" "int probe(void) { return 0; }")\n'
             'add_library(consumer STATIC "${CMAKE_BINARY_DIR}/probe.c")\n')

    def configure(self, body, guard=None):
        # Reuse ConsumerBoundaryTest.configure, which includes the guard in a throwaway project.
        return ConsumerBoundaryTest.configure(self, body, guard)

    def project(self, route, option):
        body = self.PROBE
        if route == "private":
            body += f'target_link_options(consumer PRIVATE "{option}")\n'
            return body + 'crux_assert_portable_consumer(consumer)\n'
        if route == "link_library":
            body += f'target_link_libraries(consumer PRIVATE "{option}")\n'
            return body + 'crux_assert_portable_consumer(consumer)\n'
        if route == "interface":
            body += ('add_library(wrapper INTERFACE)\n'
                     f'target_link_options(wrapper INTERFACE "{option}")\n'
                     'target_link_libraries(consumer PRIVATE wrapper)\n')
            return body + 'crux_assert_portable_usage(wrapper)\n'
        if route == "interface_consumer":
            body += ('add_library(wrapper INTERFACE)\n'
                     f'target_link_options(wrapper INTERFACE "{option}")\n'
                     'target_link_libraries(consumer PRIVATE wrapper)\n')
            return body + 'crux_assert_portable_consumer(consumer)\n'
        raise ValueError(route)

    ROUTES = ("private", "link_library", "interface", "interface_consumer")

    def weakened_guard(self, directory):
        # The real guard with the rule's function replaced by an empty one, defined last.
        weak = Path(directory) / "weak.cmake"
        weak.write_text((REPO / "cmake/CruxConsumerBoundary.cmake").read_text()
                        + f"\nfunction({WRAP_GUARD_FUNCTION})\nendfunction()\n")
        return weak

    def assertRefusedWrap(self, route, option, symbol):
        result = self.configure(self.project(route, option))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("native consumer requirement", output)
        # CMake wraps long messages at 80 columns.
        self.assertIn(f"link-time wrap of Crux symbol {symbol}", " ".join(output.split()))

    def test_a_wrap_of_a_crux_symbol_is_refused_in_every_spelling(self):
        for name, form in WRAP_FORMS.items():
            with self.subTest(form=name):
                self.assertRefusedWrap("private", form.format(symbol="crux_system_probe"),
                                       "crux_system_probe")

    def test_a_wrap_of_a_crux_symbol_is_refused_in_every_route(self):
        for route in self.ROUTES:
            with self.subTest(route=route):
                self.assertRefusedWrap(route, "-Wl,--wrap=sys_reboot,--wrap=crux_system_probe",
                                       "crux_system_probe")

    def test_the_real_and_wrap_prefixed_names_of_a_crux_symbol_are_refused(self):
        for symbol in ("__wrap_crux_system_probe", "__real_crux_system_probe"):
            with self.subTest(symbol=symbol):
                self.assertRefusedWrap("private", f"-Wl,--wrap={symbol}", symbol)

    def test_the_two_system_seam_symbols_are_refused_as_wraps_of_crux_symbols(self):
        # Refused today only by the token `zephyr` in their names; the rule now names them.
        for symbol in ("crux_watchdog_zephyr_device", "crux_watchdog_zephyr_running"):
            with self.subTest(symbol=symbol):
                result = self.configure(self.project("private", f"-Wl,--wrap={symbol}"))
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(f"link-time wrap of Crux symbol {symbol}",
                              " ".join((result.stdout + result.stderr).split()))

    def test_a_wrap_of_a_product_or_zephyr_symbol_is_left_alone(self):
        for symbol in ("sys_reboot", "z_impl_hwinfo_get_reset_cause", "clock_settime", "my_crux_helper",
                       "cruxsym", "CRUX_UPPER"):
            with self.subTest(symbol=symbol):
                result = self.configure(self.project("private", f"-Wl,--wrap={symbol}"))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_wrap_of_a_product_symbol_is_left_alone_in_every_spelling_and_route(self):
        for name, form in WRAP_FORMS.items():
            if name == "wl_second_of_two" or name == "wl_after_other_option":
                option = form.format(symbol="fs_read")
            else:
                option = form.format(symbol="sys_reboot")
            for route in self.ROUTES:
                with self.subTest(form=name, route=route):
                    result = self.configure(self.project(route, option))
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_other_linker_options_naming_crux_are_left_alone(self):
        for option in ("-Wl,-Map=crux_probe.map", "-Wl,--undefined=crux_system_probe",
                       "LINKER:--wrap=sys_reboot", "-Wl,--gc-sections"):
            with self.subTest(option=option):
                result = self.configure(self.project("private", option))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_refusal_is_the_rule_and_not_vacuous(self):
        # Against a guard with the rule removed, every refused probe configures cleanly, and the real guard
        # refuses the same probe: so each refusal above is the rule's. Every spelling and every prefixed name
        # is a probe; the routes are covered by the loop over ROUTES below with one spelling.
        probes = [form.format(symbol="crux_system_probe") for form in WRAP_FORMS.values()]
        probes += [f"-Wl,--wrap={symbol}" for symbol in ("__wrap_crux_system_probe", "__real_crux_system_probe")]
        with tempfile.TemporaryDirectory() as directory:
            weak = self.weakened_guard(directory)
            for option in probes:
                with self.subTest(option=option, route="private"):
                    self.assertAcceptedByWeakAndRefusedByRule("private", option, weak)
            for route in self.ROUTES:
                with self.subTest(option="routes", route=route):
                    self.assertAcceptedByWeakAndRefusedByRule(
                        route, "-Wl,--wrap=sys_reboot,--wrap=crux_system_probe", weak)

    def assertAcceptedByWeakAndRefusedByRule(self, route, option, weak):
        accepted = self.configure(self.project(route, option), guard=weak)
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
        refused = self.configure(self.project(route, option))
        self.assertNotEqual(refused.returncode, 0, refused.stdout + refused.stderr)
        self.assertIn("link-time wrap of Crux symbol", " ".join((refused.stdout + refused.stderr).split()))

    def test_the_two_system_seam_symbols_are_refused_by_name_even_without_the_rule(self):
        # ADR-0005 T4: "refused today by the name". The token `zephyr` in these two names is refused by the
        # older pattern, so a weakened rule does not accept them; the failure is then not the rule's message.
        with tempfile.TemporaryDirectory() as directory:
            weak = self.weakened_guard(directory)
            for symbol in ("crux_watchdog_zephyr_device", "crux_watchdog_zephyr_running"):
                with self.subTest(symbol=symbol):
                    result = self.configure(self.project("private", f"-Wl,--wrap={symbol}"), guard=weak)
                    output = " ".join((result.stdout + result.stderr).split())
                    self.assertNotEqual(result.returncode, 0, output)
                    self.assertIn("native consumer requirement", output)
                    self.assertNotIn("link-time wrap of Crux symbol", output)

    def test_the_rule_is_in_the_guard_and_is_called_per_property(self):
        text = (REPO / "cmake/CruxConsumerBoundary.cmake").read_text()
        self.assertIn(f"function({WRAP_GUARD_FUNCTION}", text)
        self.assertRegex(text, rf"(?m)^\s+{WRAP_GUARD_FUNCTION}\(")
