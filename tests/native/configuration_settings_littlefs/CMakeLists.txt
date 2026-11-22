# SPDX-License-Identifier: Apache-2.0
# The Settings File suite of tests/native/configuration_settings_file on LittleFS over a block device
# (FS_LITTLEFS_BLK_DEV, a RAM disk named MMC), against the target provider selected by
# CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS. main.c is that suite's source, compiled with this
# directory's fixture header and under another suite name, so that every case is the same code on
# each file system. The image has no Reliance Edge and no FatFs.
cmake_minimum_required(VERSION 3.20.0)
get_filename_component(CRUX_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
list(APPEND ZEPHYR_EXTRA_MODULES "${CRUX_ROOT}")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_configuration_settings_littlefs C)
if(NOT CONFIG_BOARD_NATIVE_SIM)
  message(FATAL_ERROR "This fixture operates a RAM disk on native_sim only")
endif()
target_sources(app PRIVATE
  ${CRUX_ROOT}/tests/native/configuration_settings_file/main.c extra_cases.c)
target_compile_definitions(app PRIVATE
  FIXTURE_HEADER="fixture_littlefs.h"
  configuration_settings_file=configuration_settings_littlefs)
target_link_libraries(app PRIVATE crux::configuration)
target_include_directories(app PRIVATE ${CMAKE_CURRENT_LIST_DIR}
  ${CRUX_ROOT}/components/configuration/ports/zephyr)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
# Faults and compactions are seen at the VFS calls the backend makes, as in the FatFs suite.
target_link_options(app PUBLIC -Wl,--wrap=fs_read -Wl,--wrap=fs_write -Wl,--wrap=fs_open
  -Wl,--wrap=fs_close -Wl,--wrap=fs_stat)
