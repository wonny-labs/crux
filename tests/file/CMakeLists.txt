add_executable(file_fault fault_test.c ../../components/file/src/file.c)
target_link_libraries(file_fault PRIVATE crux_file_api)
target_include_directories(file_fault PRIVATE ../../components/file/src)
add_executable(file_host host_test.c)
target_link_libraries(file_host PRIVATE crux::file)
target_include_directories(file_host PRIVATE ../../components/file/ports/linux)
target_compile_definitions(file_host PRIVATE _POSIX_C_SOURCE=200809L)
foreach(test IN ITEMS file_fault file_host)
    target_compile_options(${test} PRIVATE -Wall -Wextra -Wpedantic -Werror -UNDEBUG)
    add_test(NAME File.${test} COMMAND ${test})
    set_tests_properties(File.${test} PROPERTIES TIMEOUT 10)
endforeach()

# The link wraps fstatat so that the test can create a rename's destination after the provider has
# looked at the names. The wrap reaches the provider's object because crux_file_linux is a static
# library linked into this executable.
add_executable(file_rename_race rename_race_test.c)
target_link_libraries(file_rename_race PRIVATE crux::file)
target_include_directories(file_rename_race PRIVATE ../../components/file/ports/linux)
target_compile_definitions(file_rename_race PRIVATE _POSIX_C_SOURCE=200809L)
target_link_options(file_rename_race PRIVATE -Wl,--wrap=fstatat)
target_compile_options(file_rename_race PRIVATE -Wall -Wextra -Wpedantic -Werror -UNDEBUG)
add_test(NAME File.RenameRace COMMAND file_rename_race)
set_tests_properties(File.RenameRace PROPERTIES TIMEOUT 10)

# The pools hold the configured number: crux::file with the CMake cache values, and a copy of the
# Linux provider built with larger pools, as a build with CRUX_FILE_POOL_SIZE=8 would be.
add_executable(file_pool pool_test.c)
target_link_libraries(file_pool PRIVATE crux::file)
target_include_directories(file_pool PRIVATE ../../components/file/ports/linux)
target_compile_definitions(file_pool PRIVATE _POSIX_C_SOURCE=200809L
    CRUX_FILE_EXPECTED_POOL=${CRUX_FILE_POOL_SIZE} CRUX_FILE_EXPECTED_DIR_POOL=${CRUX_FILE_DIR_POOL_SIZE})
add_executable(file_pool8 pool_test.c ../../components/file/src/file.c
    ../../components/file/ports/linux/file_linux.c ../../components/file/ports/linux/file_lock.c)
target_include_directories(file_pool8 PRIVATE ../../components/file/include ../../components/file/src
    ../../components/file/ports/linux)
target_compile_definitions(file_pool8 PRIVATE _POSIX_C_SOURCE=200809L _GNU_SOURCE
    CRUX_FILE_POOL_SIZE=8 CRUX_FILE_DIR_POOL_SIZE=3 CRUX_FILE_EXPECTED_POOL=8
    CRUX_FILE_EXPECTED_DIR_POOL=3)
if(NOT CMAKE_HAVE_LIBC_PTHREAD)
    target_link_libraries(file_pool8 PRIVATE Threads::Threads)
endif()
foreach(test IN ITEMS file_pool file_pool8)
    target_compile_options(${test} PRIVATE -Wall -Wextra -Wpedantic -Werror -UNDEBUG)
    add_test(NAME File.${test} COMMAND ${test})
    set_tests_properties(File.${test} PROPERTIES TIMEOUT 10)
endforeach()

add_executable(file_lock lock_test.c ../../components/file/ports/linux/file_lock.c)
target_include_directories(file_lock PRIVATE ../../components/file/src)
target_link_libraries(file_lock PRIVATE crux_file_api Threads::Threads)
target_link_options(file_lock PRIVATE -Wl,--wrap=pthread_mutex_lock)
target_compile_options(file_lock PRIVATE -Wall -Wextra -Wpedantic -Werror -UNDEBUG)
add_test(NAME File.SleepableLock COMMAND file_lock)
set_tests_properties(File.SleepableLock PROPERTIES TIMEOUT 20)

# The File additions, with the same cases on each provider. The fake is shared with the consumers of
# File in this repository, which need its faults and its power cut.
add_executable(file_conformance_linux conformance_linux.c conformance.c)
target_link_libraries(file_conformance_linux PRIVATE crux::file)
target_include_directories(file_conformance_linux PRIVATE ../../components/file/src
    ../../components/file/ports/linux)
target_compile_definitions(file_conformance_linux PRIVATE _POSIX_C_SOURCE=200809L)

add_library(crux_file_fake STATIC fake_file.c ../../components/file/src/file.c)
target_link_libraries(crux_file_fake PUBLIC crux_file_api)
target_include_directories(crux_file_fake PUBLIC . PRIVATE ../../components/file/src)
target_compile_definitions(crux_file_fake PRIVATE _DEFAULT_SOURCE)
target_compile_options(crux_file_fake PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_executable(file_conformance_fake conformance_fake.c conformance.c)
target_link_libraries(file_conformance_fake PRIVATE crux_file_fake)
target_include_directories(file_conformance_fake PRIVATE ../../components/file/src)

add_executable(file_fake_faults fake_faults_test.c)
target_link_libraries(file_fake_faults PRIVATE crux_file_fake)
target_compile_definitions(file_fake_faults PRIVATE _DEFAULT_SOURCE)

# Root byte limits: the cases of the fake provider, and concurrent callers on the Linux provider.
add_executable(file_limit limit_test.c)
target_link_libraries(file_limit PRIVATE crux_file_fake)
target_include_directories(file_limit PRIVATE ../../components/file/src)
target_compile_definitions(file_limit PRIVATE _DEFAULT_SOURCE)

add_executable(file_limit_linux limit_linux_test.c)
target_link_libraries(file_limit_linux PRIVATE crux::file Threads::Threads)
target_include_directories(file_limit_linux PRIVATE ../../components/file/ports/linux)
target_compile_definitions(file_limit_linux PRIVATE _POSIX_C_SOURCE=200809L)

foreach(test IN ITEMS file_conformance_linux file_conformance_fake file_fake_faults file_limit
        file_limit_linux)
    target_compile_options(${test} PRIVATE -Wall -Wextra -Wpedantic -Werror -UNDEBUG)
    add_test(NAME File.${test} COMMAND ${test})
    set_tests_properties(File.${test} PROPERTIES TIMEOUT 20)
endforeach()
