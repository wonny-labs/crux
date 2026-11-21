add_library(crux_file_api INTERFACE)
target_include_directories(crux_file_api INTERFACE include)
# The handle and listing pools. The Zephyr build takes them from CONFIG_CRUX_FILE_POOL_SIZE and
# CONFIG_CRUX_FILE_DIR_POOL_SIZE (zephyr/Kconfig), with the same defaults and ranges.
set(CRUX_FILE_POOL_SIZE 4 CACHE STRING "Crux File open-handle pool size (4 to 32)")
set(CRUX_FILE_DIR_POOL_SIZE 2 CACHE STRING "Crux File listing pool size (1 to 8)")
if(NOT CRUX_FILE_POOL_SIZE MATCHES "^[0-9]+$" OR CRUX_FILE_POOL_SIZE LESS 4 OR
   CRUX_FILE_POOL_SIZE GREATER 32)
    message(FATAL_ERROR "CRUX_FILE_POOL_SIZE must be an integer from 4 to 32: ${CRUX_FILE_POOL_SIZE}")
endif()
if(NOT CRUX_FILE_DIR_POOL_SIZE MATCHES "^[0-9]+$" OR CRUX_FILE_DIR_POOL_SIZE LESS 1 OR
   CRUX_FILE_DIR_POOL_SIZE GREATER 8)
    message(FATAL_ERROR "CRUX_FILE_DIR_POOL_SIZE must be an integer from 1 to 8: ${CRUX_FILE_DIR_POOL_SIZE}")
endif()
# Public, so that a consumer can size what it keeps free of the handle pool at build time.
target_compile_definitions(crux_file_api INTERFACE CRUX_FILE_POOL_SIZE=${CRUX_FILE_POOL_SIZE}
    CRUX_FILE_DIR_POOL_SIZE=${CRUX_FILE_DIR_POOL_SIZE})

add_library(crux_file_linux STATIC src/file.c ports/linux/file_linux.c ports/linux/file_lock.c)
find_package(Threads REQUIRED)
target_link_libraries(crux_file_linux PRIVATE crux_file_api)

# Match the supported Sync Host composition: libc supplies pthread on Ubuntu.
if(NOT CMAKE_HAVE_LIBC_PTHREAD)
    target_link_libraries(crux_file_linux PRIVATE Threads::Threads)
endif()
target_include_directories(crux_file_linux PRIVATE src ports/linux)
# _GNU_SOURCE for renameat2 and RENAME_NOREPLACE (glibc 2.28 and later).
target_compile_definitions(crux_file_linux PRIVATE _POSIX_C_SOURCE=200809L _GNU_SOURCE)
target_compile_options(crux_file_linux PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_library(crux_file INTERFACE)
add_library(crux::file ALIAS crux_file)
target_link_libraries(crux_file INTERFACE crux_file_api crux_file_linux)
