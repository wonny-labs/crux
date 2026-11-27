# SPDX-License-Identifier: Apache-2.0
# Link only: the File provider on LittleFS over the microSD disk (CONFIG_CRUX_FILE_LITTLEFS_BLK_DEV),
# with Configuration over CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS on the same volume.
# scripts/test-file-rt1060-compile.sh builds it for the RT1060-EVKB Rev B and checks what is linked.
# Nothing is programmed, reset or run.
cmake_minimum_required(VERSION 3.20.0)
get_filename_component(CRUX_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
list(APPEND ZEPHYR_EXTRA_MODULES "${CRUX_ROOT}")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_file_littlefs_link C)
# An unsatisfied Kconfig dependency only warns, which would build an image without the provider.
if(NOT CONFIG_CRUX_FILE_LITTLEFS_BLK_DEV OR NOT CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS)
  message(FATAL_ERROR "The link check needs CONFIG_CRUX_FILE_LITTLEFS_BLK_DEV and "
    "CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS")
endif()
target_sources(app PRIVATE main.c)
target_link_libraries(app PRIVATE crux::file crux::file_zephyr crux::configuration)
target_include_directories(app PRIVATE ${CRUX_ROOT}/components/configuration/ports/zephyr)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
