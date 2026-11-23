cmake_minimum_required(VERSION 3.20.0)
get_filename_component(CRUX_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
list(APPEND ZEPHYR_EXTRA_MODULES "${CRUX_ROOT}")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_file_sd_interrupt C)
target_sources(app PRIVATE main.c ${CRUX_ROOT}/samples/boards/nxp/mimxrt1060_evk/sd_card_file/sd_storage.c
  ${CRUX_ROOT}/tests/board_images/sd_card_power_cut_append/sd_interrupt.c)
target_link_libraries(app PRIVATE crux::file crux::file_zephyr)
target_include_directories(app PRIVATE ${CRUX_ROOT}/samples/boards/nxp/mimxrt1060_evk/sd_card_file
  ${CRUX_ROOT}/tests/board_images/sd_card_power_cut_append ${CRUX_ROOT}/components/file/ports/zephyr)
