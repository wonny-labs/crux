# SPDX-License-Identifier: Apache-2.0

# Modelled on boards/nxp/mimxrt1060_evk/CMakeLists.txt of Zephyr (Copyright 2018-2022, 2025 NXP).
# The boot ROM reads the flash configuration block from the start of the external flash. This
# board has no SDRAM, so it needs no device configuration data.
if(CONFIG_NXP_IMXRT_BOOT_HEADER)
  zephyr_library()
  if(CONFIG_BOOT_FLEXSPI_NOR)
    # The block describes the flash part of the vendor board. Replace it for your own flash part.
    zephyr_library_sources(flexspi_nor_config.c)
    zephyr_library_include_directories(.)
  endif()
endif()
