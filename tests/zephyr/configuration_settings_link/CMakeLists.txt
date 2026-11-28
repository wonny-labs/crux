# SPDX-License-Identifier: Apache-2.0
# Link only: Configuration over the Settings File selection that does not depend on Reliance Edge
# (CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS), on LittleFS over the MMC disk of the RT1060 link
# overlay, with a consumer that saves a parameter. scripts/test-storage-emmc.sh builds it for the
# RT1060-EVKB Rev B and checks that crux_config_save and the provider are linked, and that neither
# the no-provider port, FatFs nor Reliance Edge is. Nothing is programmed, reset or run.
cmake_minimum_required(VERSION 3.20.0)
get_filename_component(CRUX_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
list(APPEND ZEPHYR_EXTRA_MODULES "${CRUX_ROOT}")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_configuration_settings_link C)
# An unsatisfied Kconfig dependency only warns, which would build an image without the provider.
if(NOT CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS OR NOT CONFIG_FS_LITTLEFS_BLK_DEV)
  message(FATAL_ERROR "The Settings File link check needs CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS "
    "and LittleFS on a block device")
endif()
target_sources(app PRIVATE main.c)
target_link_libraries(app PRIVATE crux::configuration crux::configuration_zephyr)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
