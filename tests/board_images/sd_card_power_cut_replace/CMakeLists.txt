cmake_minimum_required(VERSION 3.20.0)
get_filename_component(CRUX_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
list(APPEND ZEPHYR_EXTRA_MODULES "${CRUX_ROOT}")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_sd_card_power_cut_replace C)
# An unsatisfied Kconfig dependency only warns, which would build an image without the provider.
if(NOT CONFIG_CRUX_FILE_FATFS_SDMMC)
  message(FATAL_ERROR "The SD card File provider is not selected: it requires an enabled zephyr,sdmmc-disk node and the SD card disk driver")
endif()
target_sources(app PRIVATE main.c sd_replace.c ${CRUX_ROOT}/samples/boards/nxp/mimxrt1060_evk/sd_card_file/sd_storage.c
  ${CRUX_ROOT}/tests/board_images/sd_card_power_cut_append/sd_interrupt.c)
target_link_libraries(app PRIVATE crux::file crux::file_zephyr)
target_include_directories(app PRIVATE ${CRUX_ROOT}/samples/boards/nxp/mimxrt1060_evk/sd_card_file
  ${CRUX_ROOT}/tests/board_images/sd_card_power_cut_append)
