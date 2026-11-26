get_filename_component(CRUX_FILE_COMPONENT_DIR "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)

# The handle and listing pools come from CONFIG_CRUX_FILE_POOL_SIZE and CONFIG_CRUX_FILE_DIR_POOL_SIZE
# (zephyr/Kconfig), the same for every provider below.
set(CRUX_FILE_POOL_DEFINITIONS CRUX_FILE_POOL_SIZE=${CONFIG_CRUX_FILE_POOL_SIZE}
    CRUX_FILE_DIR_POOL_SIZE=${CONFIG_CRUX_FILE_DIR_POOL_SIZE})

# The Zephyr root binding is a composition interface (see include/crux/file_zephyr.h). The target gives a
# product's platform composition the header and crux::file; it is not a portable usage target and the
# native-free consumer check rejects it by name. The provider library is added to Zephyr separately.
function(crux_file_zephyr_composition)
  add_library(crux_file_zephyr_composition INTERFACE)
  add_library(crux::file_zephyr ALIAS crux_file_zephyr_composition)
  target_include_directories(crux_file_zephyr_composition INTERFACE "${CRUX_FILE_COMPONENT_DIR}/ports/zephyr/include")
  target_link_libraries(crux_file_zephyr_composition INTERFACE crux_file)
endfunction()
# The provider library and the public targets, the same for every selection. On native_sim the public
# target also carries the simulator's non-PIE CPU image flags and width, without kernel headers or
# definitions, because portable consumers link it outside Zephyr's own flags.
function(crux_file_zephyr_provider)
  add_library(crux_file_api INTERFACE)
  target_include_directories(crux_file_api INTERFACE "${CRUX_FILE_COMPONENT_DIR}/include")
  target_compile_definitions(crux_file_api INTERFACE ${CRUX_FILE_POOL_DEFINITIONS})
  if(CONFIG_BOARD_NATIVE_SIM)
    target_compile_options(crux_file_api INTERFACE ${TOOLCHAIN_C_FLAGS} -fno-pic -fno-pie)
    if(CONFIG_64BIT)
      target_compile_options(crux_file_api INTERFACE -m64)
    else()
      target_compile_options(crux_file_api INTERFACE -m32)
    endif()
  endif()
  add_library(crux_file_zephyr STATIC "${CRUX_FILE_COMPONENT_DIR}/src/file.c" file_native.c)
  target_include_directories(crux_file_zephyr PRIVATE "${CRUX_FILE_COMPONENT_DIR}/src" .)
  zephyr_append_cmake_library(crux_file_zephyr)
  target_link_libraries(crux_file_zephyr PRIVATE crux_file_api zephyr_interface)
  target_compile_options(crux_file_zephyr PRIVATE -Wall -Wextra -Werror)
  add_library(crux_file INTERFACE)
  add_library(crux::file ALIAS crux_file)
  target_link_libraries(crux_file INTERFACE crux_file_api)
  crux_file_zephyr_composition()
endfunction()

# The selections are keyed on generic disk and devicetree facts, the same as their Kconfig
# dependencies, never on a SoC or board name. Kconfig only warns about an unmet dependency, so each
# fact is checked again here.
if(CONFIG_CRUX_FILE_FATFS_SDMMC AND CONFIG_CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK)
  message(FATAL_ERROR "The SD card File provider and its compile-only check are mutually exclusive")
endif()
if(CONFIG_CRUX_FILE_FATFS_RAM_DISK AND
   (CONFIG_CRUX_FILE_SIMULATOR OR CONFIG_CRUX_FILE_FATFS_SIMULATOR OR CONFIG_CRUX_FILE_FATFS_SDMMC OR
    CONFIG_CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK OR CONFIG_CRUX_FILE_RELIANCE_EDGE))
  message(FATAL_ERROR "The RAM disk File provider cannot be combined with another File selection")
endif()
if(CONFIG_CRUX_FILE_RELIANCE_EDGE AND
   (CONFIG_CRUX_FILE_SIMULATOR OR CONFIG_CRUX_FILE_FATFS_SIMULATOR OR
    CONFIG_CRUX_FILE_FATFS_SDMMC OR CONFIG_CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK))
  message(FATAL_ERROR "The Reliance Edge provider cannot be combined with another File selection")
endif()
if((CONFIG_CRUX_FILE_FATFS_SDMMC OR CONFIG_CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK) AND
   (CONFIG_CRUX_FILE_SIMULATOR OR CONFIG_CRUX_FILE_FATFS_SIMULATOR))
  message(FATAL_ERROR "The SD card File selections cannot be combined with simulator providers")
endif()
# The FatFs settings that every FatFs selection needs: long names that hold an encoded File name,
# reentrancy, and no format at mount.
set(CRUX_FILE_FATFS_SETTINGS_OK TRUE)
if(NOT CONFIG_FAT_FILESYSTEM_ELM OR NOT CONFIG_FILE_SYSTEM OR NOT CONFIG_FS_FATFS_LFN OR
   CONFIG_FS_FATFS_MAX_LFN LESS 127 OR NOT CONFIG_FS_FATFS_REENTRANT OR CONFIG_FS_FATFS_MOUNT_MKFS)
  set(CRUX_FILE_FATFS_SETTINGS_OK FALSE)
endif()

if(CONFIG_CRUX_FILE_FATFS_SDMMC OR CONFIG_CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK)
  if(NOT CRUX_FILE_FATFS_SETTINGS_OK OR NOT CONFIG_DISK_DRIVER_SDMMC OR
     NOT CONFIG_DT_HAS_ZEPHYR_SDMMC_DISK_ENABLED)
    message(FATAL_ERROR "The SD card File provider requires an enabled zephyr,sdmmc-disk node, the SD card "
                        "disk driver and FatFs with long names of at least 127, reentrancy and auto-format "
                        "disabled")
  endif()
endif()

if(CONFIG_CRUX_FILE_FATFS_SDMMC_COMPILE_CHECK)
  # Compile only: do not register the unqualified native File provider in the image.
  add_library(crux_file_fatfs_sdmmc_compile OBJECT EXCLUDE_FROM_ALL
      "${CRUX_FILE_COMPONENT_DIR}/src/file.c" file_native.c)
  target_include_directories(crux_file_fatfs_sdmmc_compile PRIVATE
      "${CRUX_FILE_COMPONENT_DIR}/include"
      "${CRUX_FILE_COMPONENT_DIR}/src"
      ".")
  target_link_libraries(crux_file_fatfs_sdmmc_compile PRIVATE zephyr_interface)
  target_compile_definitions(crux_file_fatfs_sdmmc_compile PRIVATE ${CRUX_FILE_POOL_DEFINITIONS})
  # The object includes kernel headers that are generated during the build.
  add_dependencies(crux_file_fatfs_sdmmc_compile zephyr_generated_headers)
  target_compile_options(crux_file_fatfs_sdmmc_compile PRIVATE -Wall -Wextra -Werror)
  add_custom_target(crux_file_target_compile_only ALL)
  add_dependencies(crux_file_target_compile_only crux_file_fatfs_sdmmc_compile)
  return()
endif()

if(CONFIG_CRUX_FILE_FATFS_SDMMC)
  crux_file_zephyr_provider()
  return()
endif()

if(CONFIG_CRUX_FILE_FATFS_RAM_DISK)
  # The provider over a RAM disk. The SD card driver, the SD host controller drivers and the flash
  # disk must be absent, so that the image has no card that the composition could mount or format,
  # and the disk drivers are the RAM disk's alone.
  if(NOT CRUX_FILE_FATFS_SETTINGS_OK OR NOT CONFIG_DISK_DRIVER_RAM OR
     NOT CONFIG_DT_HAS_ZEPHYR_RAM_DISK_ENABLED OR CONFIG_DISK_DRIVER_SDMMC OR CONFIG_SDHC OR
     CONFIG_DISK_DRIVER_FLASH)
    message(FATAL_ERROR "The RAM disk File provider requires an enabled zephyr,ram-disk node as the only "
                        "disk, no SD card driver, no SD host controller driver, no flash disk, and FatFs "
                        "with long names of at least 127, reentrancy and auto-format disabled")
  endif()
  crux_file_zephyr_provider()
  return()
endif()

if(CONFIG_CRUX_FILE_RELIANCE_EDGE)
  # Any board that has the file system.
  crux_file_zephyr_provider()
  return()
endif()

if(NOT CONFIG_BOARD_NATIVE_SIM OR
   NOT (CONFIG_CRUX_FILE_SIMULATOR OR CONFIG_CRUX_FILE_FATFS_SIMULATOR))
  message(FATAL_ERROR "Crux File native provider requires an approved simulator composition")
endif()
if(CONFIG_CRUX_FILE_SIMULATOR AND CONFIG_CRUX_FILE_FATFS_SIMULATOR)
  message(FATAL_ERROR "Crux File simulator compositions must be mutually exclusive")
endif()
if(CONFIG_CRUX_FILE_FATFS_SIMULATOR AND
   (NOT CONFIG_FS_FATFS_LFN OR CONFIG_FS_FATFS_MAX_LFN LESS 127 OR
    NOT CONFIG_FS_FATFS_REENTRANT OR CONFIG_FS_FATFS_MOUNT_MKFS))
  message(FATAL_ERROR "FatFs simulator requires LFN >= 127, reentrancy and auto-format disabled")
endif()

crux_file_zephyr_provider()
