# SPDX-License-Identifier: Apache-2.0
cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_tls_offload_probe LANGUAGES C)
if(NOT CONFIG_BOARD_NATIVE_SIM)
  message(FATAL_ERROR "This probe is restricted to native_sim: its certificate and key are public")
endif()
target_sources(app PRIVATE src/main.c)
target_include_directories(app PRIVATE credentials)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
# The offload reports a peer FIN as POLLHUP, which Zephyr v4.5.0 needs: see src/main.c.
include(${CMAKE_CURRENT_LIST_DIR}/../web_https/nsos_rdhup.cmake)
