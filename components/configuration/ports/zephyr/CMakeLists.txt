# The Settings File selections: Configuration over the Zephyr Settings File backend, on Reliance Edge
# (CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE) or on another mounted file system that is not FatFs
# (CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS). Both select CONFIG_CRUX_CONFIGURATION_SETTINGS_PROVIDER,
# and the module's CMake adds this directory only under it.
get_filename_component(CRUX_CONFIGURATION_COMPONENT_DIR "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
if(NOT CONFIG_CRUX_CONFIGURATION_SETTINGS_PROVIDER)
  message(FATAL_ERROR "This directory is the Settings File selection of Configuration")
endif()

# The selection that does not depend on Reliance Edge has the same eMMC rule as Reliance Edge: a
# settings file on an MMC disk needs the cache flush correction, or a sync leaves the saved record in
# the card's cache. CRUX_EMMC_FLUSH_CONTROL lets a native_sim power-cut control build without it. It is
# the same cache variable as in zephyr/fs/reliance_edge/CMakeLists.txt: keep the two definitions equal.
set(CRUX_EMMC_FLUSH_CONTROL OFF CACHE BOOL
  "Test fixtures only: allow an MMC disk without the cache flush correction on native_sim")
if(CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS)
  # FatFs rename removes the destination first, so a power cut in a compaction can leave the
  # settings file missing. A Kconfig dependency would only drop the selection with a warning.
  if(CONFIG_FAT_FILESYSTEM_ELM)
    message(FATAL_ERROR "The Settings File selection refuses FatFs (CONFIG_FAT_FILESYSTEM_ELM): its "
      "rename can leave the settings file missing after a power cut")
  endif()
  if(CRUX_EMMC_FLUSH_CONTROL AND NOT CONFIG_BOARD_NATIVE_SIM)
    message(FATAL_ERROR "CRUX_EMMC_FLUSH_CONTROL is a native_sim test fixture setting and is "
      "refused on any other board")
  endif()
  if(CONFIG_DISK_DRIVER_MMC AND NOT CONFIG_CRUX_MMC_CACHE_FLUSH AND NOT CRUX_EMMC_FLUSH_CONTROL)
    message(FATAL_ERROR "The Settings File selection on an MMC disk requires "
      "CONFIG_CRUX_MMC_CACHE_FLUSH=y, because without it a disk sync does not flush the eMMC cache")
  endif()
endif()

add_library(crux_configuration_api INTERFACE)
target_include_directories(crux_configuration_api INTERFACE
  "${CRUX_CONFIGURATION_COMPONENT_DIR}/include")

add_library(crux_configuration_zephyr STATIC
  "${CRUX_CONFIGURATION_COMPONENT_DIR}/src/configuration.c"
  "${CRUX_CONFIGURATION_COMPONENT_DIR}/src/configuration_text.c" configuration_settings.c)
target_include_directories(crux_configuration_zephyr PRIVATE
  "${CRUX_CONFIGURATION_COMPONENT_DIR}/src" ".")
zephyr_append_cmake_library(crux_configuration_zephyr)
target_link_libraries(crux_configuration_zephyr PRIVATE crux_configuration_api zephyr_interface)
add_dependencies(crux_configuration_zephyr zephyr_generated_headers)
target_compile_options(crux_configuration_zephyr PRIVATE -Wall -Wextra -Werror)

add_library(crux_configuration INTERFACE)
add_library(crux::configuration ALIAS crux_configuration)
target_link_libraries(crux_configuration INTERFACE crux_configuration_api)
