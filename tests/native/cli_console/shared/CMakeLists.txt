# SPDX-License-Identifier: Apache-2.0
# The serial console and Crux Logging on one emulated UART (CONFIG_CRUX_CLI_CONSOLE_UART_SHARED, Experimental),
# with the supervision progress hook of <crux/service_priority_zephyr.h>. The configuration and devicetree of
# the console fixture one level up, plus shared.conf and shared.overlay. Public targets and headers only.
# Built with the Mbed profile by tests/native/cli_console/run.sh.
cmake_minimum_required(VERSION 3.20.0)
set(CONF_FILE "${CMAKE_CURRENT_LIST_DIR}/../prj.conf;${CMAKE_CURRENT_LIST_DIR}/shared.conf")
set(DTC_OVERLAY_FILE "${CMAKE_CURRENT_LIST_DIR}/../app.overlay;${CMAKE_CURRENT_LIST_DIR}/shared.overlay")
get_filename_component(CRUX_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../.." ABSOLUTE)
list(APPEND ZEPHYR_EXTRA_MODULES "${CRUX_ROOT}")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_cli_console_shared LANGUAGES C)

if(NOT CONFIG_BOARD_NATIVE_SIM OR NOT CONFIG_FAKE_ENTROPY_NATIVE_SIM)
    message(FATAL_ERROR "This fixture is restricted to native_sim: its entropy is test-only")
endif()
# An unsatisfied choice only warns in Kconfig and would build the dedicated console.
if(NOT CONFIG_CRUX_CLI_CONSOLE_UART_SHARED)
    message(FATAL_ERROR "The shared fixture needs CONFIG_CRUX_CLI_CONSOLE_UART_SHARED")
endif()

target_sources(app PRIVATE src/main.c)
target_link_libraries(app PRIVATE crux::access crux::credential_store crux::security_event crux::cli
    crux::cli_zephyr crux::file_zephyr crux::logging crux::service_priority_zephyr crux::time)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
