# SPDX-License-Identifier: Apache-2.0
#
# hello_crux as a separate Linux CMake project that consumes Crux from its source tree, the way an
# external application does (docs/build.md, "External Linux application using Crux source"). It
# is not part of the repository's root build.

cmake_minimum_required(VERSION 3.28)
project(hello_crux_host LANGUAGES C)

# Where Crux is. An external project passes it: -DCRUX_SOURCE_DIR=/absolute/path/to/crux-pilot.
# Inside this repository the default is the checkout that holds this sample.
get_filename_component(default_crux_source "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
set(CRUX_SOURCE_DIR "${default_crux_source}" CACHE PATH "Crux source tree")

# Select only what the application uses, before adding Crux. Here: Time, with the controlled
# development clock of the Linux Host composition.
set(CRUX_BUILD_TIME ON CACHE BOOL "Use Crux Time")
set(CRUX_TIME_PROVIDER memory CACHE STRING "Controlled development realtime")
add_subdirectory("${CRUX_SOURCE_DIR}" crux)

# The portable part, the same file the Zephyr application compiles. The check fails the
# configure step if it reaches a native header, a private Crux directory or a provider target.
add_library(hello_crux_logic STATIC ../src/hello_crux.c)
target_include_directories(hello_crux_logic PUBLIC ../src)
set_target_properties(hello_crux_logic PROPERTIES
    C_STANDARD 17 C_STANDARD_REQUIRED ON C_EXTENSIONS OFF)
target_link_libraries(hello_crux_logic PRIVATE crux::time)
target_compile_options(hello_crux_logic PRIVATE -Wall -Wextra -Wpedantic -Werror)
crux_assert_portable_consumer(hello_crux_logic)

# The program: the final executable declares the Crux capability it uses.
add_executable(hello-crux-host main.c)
target_link_libraries(hello-crux-host PRIVATE hello_crux_logic crux::time)
target_compile_options(hello-crux-host PRIVATE -Wall -Wextra -Wpedantic -Werror)
