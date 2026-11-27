# SPDX-License-Identifier: Apache-2.0
# Cross-build evidence for the console that shares its UART with Crux Logging
# (CONFIG_CRUX_CLI_CONSOLE_UART_SHARED, Experimental) on the RT1060-EVKB, with the console on LPUART1. It takes
# the shared mode's selection from the native_sim fixture, tests/native/cli_console/shared/shared.conf. Built and
# checked by run.sh; nothing here flashes or runs the image, and it starts no service that a console needs.
cmake_minimum_required(VERSION 3.20.0)
get_filename_component(CRUX_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
set(CONF_FILE
    "${CMAKE_CURRENT_LIST_DIR}/prj.conf;${CRUX_ROOT}/tests/native/cli_console/shared/shared.conf")
list(APPEND ZEPHYR_EXTRA_MODULES "${CRUX_ROOT}")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_cli_console_shared_compile LANGUAGES C)

if(NOT "${CONFIG_BOARD_TARGET}" STREQUAL "mimxrt1060_evk@B/mimxrt1062/qspi")
    message(FATAL_ERROR "This fixture is for mimxrt1060_evk@B//qspi only, not '${CONFIG_BOARD_TARGET}'")
endif()
# An unsatisfied dependency or choice only warns in Kconfig and would build another console, or none.
if(NOT CONFIG_CRUX_CLI_CONSOLE)
    message(FATAL_ERROR "The fixture needs CONFIG_CRUX_CLI_CONSOLE")
endif()
if(NOT CONFIG_CRUX_CLI_CONSOLE_UART_SHARED)
    message(FATAL_ERROR "The fixture needs CONFIG_CRUX_CLI_CONSOLE_UART_SHARED")
endif()
# A failed read of the TRNG must fail PSA, as in the RT1060 management image (cmake/CruxMbedtlsEntropy.cmake).
include("${CRUX_ROOT}/cmake/CruxMbedtlsEntropy.cmake")
crux_mbedtls_fail_closed_entropy()

target_sources(app PRIVATE main.c)
target_link_libraries(app PRIVATE crux::cli crux::cli_zephyr)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
