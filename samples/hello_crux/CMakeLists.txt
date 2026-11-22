# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)
# The Crux module comes from the west workspace, like any other Zephyr module. Its Kconfig
# symbols (CONFIG_CRUX_*) select what it builds and which provider is used.
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})

project(hello_crux C)

if(NOT CONFIG_CRUX_TIME)
    message(FATAL_ERROR "hello_crux requires CONFIG_CRUX_TIME=y (see prj.conf)")
endif()

target_sources(app PRIVATE src/main.c src/hello_crux.c)
# The application links the public usage target only: no Crux source, port or private
# include directory.
target_link_libraries(app PRIVATE crux::time)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
