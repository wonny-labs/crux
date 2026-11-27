# SPDX-License-Identifier: Apache-2.0
# The File provider on LittleFS over a block device (a RAM disk named SD), with Configuration saving
# on the same volume through CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS. The only workspace
# module is LittleFS, so the image cannot reach Reliance Edge or FatFs.
cmake_minimum_required(VERSION 3.20.0)
get_filename_component(CRUX_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
list(APPEND ZEPHYR_EXTRA_MODULES "${CRUX_ROOT}")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_file_littlefs_blk C)
if(NOT CONFIG_BOARD_NATIVE_SIM)
  message(FATAL_ERROR "This fixture formats a RAM disk on native_sim only")
endif()
# An unsatisfied Kconfig dependency only warns, which would build an image without the provider.
if(NOT CONFIG_CRUX_FILE_LITTLEFS_BLK_DEV)
  message(FATAL_ERROR "The LittleFS block device File provider is not selected")
endif()
target_sources(app PRIVATE main.c ${CRUX_ROOT}/tests/file/conformance.c)
target_link_libraries(app PRIVATE crux::file crux::file_zephyr crux::configuration)
target_include_directories(app PRIVATE ${CRUX_ROOT}/components/file/src ${CRUX_ROOT}/tests/file
  ${CRUX_ROOT}/components/configuration/ports/zephyr)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
# The disk can refuse a write, so that a File write fails inside LittleFS.
target_link_options(app PUBLIC -Wl,--wrap=disk_access_write)
