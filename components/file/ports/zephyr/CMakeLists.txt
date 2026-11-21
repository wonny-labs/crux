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
if(CONFIG_CRUX_FILE_FATFS_RT1060 AND CONFIG_CRUX_FILE_FATFS_RT1060_COMPILE_CHECK)
  message(FATAL_ERROR "The RT1060 provider and its compile-only check are mutually exclusive")
endif()
if(CONFIG_CRUX_FILE_FATFS_RT1060_RAM_DISK AND
   (CONFIG_CRUX_FILE_SIMULATOR OR CONFIG_CRUX_FILE_FATFS_SIMULATOR OR CONFIG_CRUX_FILE_FATFS_RT1060 OR
    CONFIG_CRUX_FILE_FATFS_RT1060_COMPILE_CHECK OR CONFIG_CRUX_FILE_RELIANCE_EDGE))
  message(FATAL_ERROR "The RT1060 RAM disk provider cannot be combined with another File selection")
endif()
if(CONFIG_CRUX_FILE_RELIANCE_EDGE AND
   (CONFIG_CRUX_FILE_SIMULATOR OR CONFIG_CRUX_FILE_FATFS_SIMULATOR OR
    CONFIG_CRUX_FILE_FATFS_RT1060 OR CONFIG_CRUX_FILE_FATFS_RT1060_COMPILE_CHECK))
  message(FATAL_ERROR "The Reliance Edge provider cannot be combined with another File selection")
endif()
# The RT1060 selections are keyed on the RT1062 SoC and the devicetree (an enabled USDHC with an SD
# disk, checked by Kconfig), not on the board name. On the RT1060-EVK itself only the Rev B QSPI
# target is accepted, the one that has the physical evidence.
if(CONFIG_BOARD_MIMXRT1060_EVK AND
   (NOT CONFIG_BOARD_MIMXRT1060_EVK_MIMXRT1062_QSPI OR NOT CONFIG_BOARD_REVISION_B))
  set(CRUX_FILE_RT1060_EVK_VARIANT TRUE)
endif()
if(CONFIG_CRUX_FILE_FATFS_RT1060_COMPILE_CHECK)
  if(CONFIG_BOARD_NATIVE_SIM OR CRUX_FILE_RT1060_EVK_VARIANT OR
     NOT CONFIG_SOC_MIMXRT1062 OR NOT CONFIG_FAT_FILESYSTEM_ELM OR
     NOT CONFIG_FILE_SYSTEM OR NOT CONFIG_DISK_DRIVER_SDMMC OR
     NOT CONFIG_IMX_USDHC OR NOT CONFIG_FS_FATFS_LFN OR
     CONFIG_FS_FATFS_MAX_LFN LESS 127 OR NOT CONFIG_FS_FATFS_REENTRANT OR
     CONFIG_FS_FATFS_MOUNT_MKFS)
    message(FATAL_ERROR "RT1060 File check requires the RT1062 SoC (on the RT1060-EVK, the Rev B QSPI board) and the selected FatFs/SDHC build with auto-format disabled")
  endif()
  if(CONFIG_CRUX_FILE_SIMULATOR OR CONFIG_CRUX_FILE_FATFS_SIMULATOR)
    message(FATAL_ERROR "RT1060 compile check cannot be combined with simulator providers")
  endif()

  # Compile only: do not register the unqualified native File provider in the image.
  add_library(crux_file_fatfs_rt1060_compile OBJECT EXCLUDE_FROM_ALL
      "${CRUX_FILE_COMPONENT_DIR}/src/file.c" file_native.c)
  target_include_directories(crux_file_fatfs_rt1060_compile PRIVATE
      "${CRUX_FILE_COMPONENT_DIR}/include"
      "${CRUX_FILE_COMPONENT_DIR}/src"
      ".")
  target_link_libraries(crux_file_fatfs_rt1060_compile PRIVATE zephyr_interface)
  target_compile_definitions(crux_file_fatfs_rt1060_compile PRIVATE ${CRUX_FILE_POOL_DEFINITIONS})
  # The object includes kernel headers that are generated during the build.
  add_dependencies(crux_file_fatfs_rt1060_compile zephyr_generated_headers)
  target_compile_options(crux_file_fatfs_rt1060_compile PRIVATE -Wall -Wextra -Werror)
  add_custom_target(crux_file_target_compile_only ALL)
  add_dependencies(crux_file_target_compile_only crux_file_fatfs_rt1060_compile)
  return()
endif()

if(CONFIG_CRUX_FILE_FATFS_RT1060)
  if(CONFIG_CRUX_FILE_SIMULATOR OR CONFIG_CRUX_FILE_FATFS_SIMULATOR)
    message(FATAL_ERROR "The RT1060 provider cannot be combined with simulator providers")
  endif()
  if(NOT CONFIG_SOC_MIMXRT1062 OR CRUX_FILE_RT1060_EVK_VARIANT)
    message(FATAL_ERROR "The RT1060 File provider requires the RT1062 SoC (on the RT1060-EVK, the Rev B QSPI board)")
  endif()
  add_library(crux_file_api INTERFACE)
  target_include_directories(crux_file_api INTERFACE "${CRUX_FILE_COMPONENT_DIR}/include")
  target_compile_definitions(crux_file_api INTERFACE ${CRUX_FILE_POOL_DEFINITIONS})
  add_library(crux_file_zephyr STATIC "${CRUX_FILE_COMPONENT_DIR}/src/file.c" file_native.c)
  target_include_directories(crux_file_zephyr PRIVATE "${CRUX_FILE_COMPONENT_DIR}/src" .)
  zephyr_append_cmake_library(crux_file_zephyr)
  target_link_libraries(crux_file_zephyr PRIVATE crux_file_api zephyr_interface)
  target_compile_options(crux_file_zephyr PRIVATE -Wall -Wextra -Werror)
  add_library(crux_file INTERFACE)
  add_library(crux::file ALIAS crux_file)
  target_link_libraries(crux_file INTERFACE crux_file_api)
  crux_file_zephyr_composition()
  return()
endif()

if(CONFIG_CRUX_FILE_FATFS_RT1060_RAM_DISK)
  # The RT1060 provider over a RAM disk. The SD card driver must be absent, so that the image has no card
  # that the composition could mount or format, and the disk drivers are the RAM disk's alone.
  if(NOT CONFIG_SOC_MIMXRT1062 OR CRUX_FILE_RT1060_EVK_VARIANT OR
     NOT CONFIG_DISK_DRIVER_RAM OR CONFIG_DISK_DRIVER_SDMMC OR CONFIG_IMX_USDHC OR
     CONFIG_DISK_DRIVER_FLASH OR CONFIG_FS_FATFS_MOUNT_MKFS)
    message(FATAL_ERROR "The RT1060 RAM disk File provider requires the RT1062 SoC (on the RT1060-EVK, the Rev B QSPI board), the RAM disk as the only disk driver and auto-format disabled")
  endif()
  add_library(crux_file_api INTERFACE)
  target_include_directories(crux_file_api INTERFACE "${CRUX_FILE_COMPONENT_DIR}/include")
  target_compile_definitions(crux_file_api INTERFACE ${CRUX_FILE_POOL_DEFINITIONS})
  add_library(crux_file_zephyr STATIC "${CRUX_FILE_COMPONENT_DIR}/src/file.c" file_native.c)
  target_include_directories(crux_file_zephyr PRIVATE "${CRUX_FILE_COMPONENT_DIR}/src" .)
  zephyr_append_cmake_library(crux_file_zephyr)
  target_link_libraries(crux_file_zephyr PRIVATE crux_file_api zephyr_interface)
  target_compile_options(crux_file_zephyr PRIVATE -Wall -Wextra -Werror)
  add_library(crux_file INTERFACE)
  add_library(crux::file ALIAS crux_file)
  target_link_libraries(crux_file INTERFACE crux_file_api)
  crux_file_zephyr_composition()
  return()
endif()

if(CONFIG_CRUX_FILE_RELIANCE_EDGE)
  # Any board that has the file system. The simulator's compiler flags apply on native_sim only.
  add_library(crux_file_api INTERFACE)
  target_include_directories(crux_file_api INTERFACE "${CRUX_FILE_COMPONENT_DIR}/include")
  target_compile_definitions(crux_file_api INTERFACE ${CRUX_FILE_POOL_DEFINITIONS})
  if(CONFIG_BOARD_NATIVE_SIM)
    # Match native_sim's non-PIE CPU image, without kernel headers/definitions.
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

add_library(crux_file_api INTERFACE)
target_include_directories(crux_file_api INTERFACE "${CRUX_FILE_COMPONENT_DIR}/include")
target_compile_definitions(crux_file_api INTERFACE ${CRUX_FILE_POOL_DEFINITIONS})
# Match native_sim's non-PIE CPU image, without kernel headers/definitions.
target_compile_options(crux_file_api INTERFACE ${TOOLCHAIN_C_FLAGS} -fno-pic -fno-pie)
# native_sim's width is a compiler ABI requirement, not a kernel API requirement.
if(CONFIG_BOARD_NATIVE_SIM)
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
