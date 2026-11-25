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

# Added as a subproject, Crux selects no capability by default; crux::base always exists.
add_subdirectory("${CRUX_SOURCE_DIR}" crux)

# The program links the public usage target only. The check fails the configure step if the
# target's build requirements (include directories, compile options, linked targets) name a
# native path, a private Crux directory or a provider target. It does not read #include lines.
add_executable(hello-crux-host main.c)
set_target_properties(hello-crux-host PROPERTIES
    C_STANDARD 17 C_STANDARD_REQUIRED ON C_EXTENSIONS OFF)
target_link_libraries(hello-crux-host PRIVATE crux::base)
target_compile_options(hello-crux-host PRIVATE -Wall -Wextra -Wpedantic -Werror)
crux_assert_portable_consumer(hello-crux-host)

# `cmake --build <build folder> --target run_hello_crux` builds the program and runs it.
add_custom_target(run_hello_crux COMMAND hello-crux-host USES_TERMINAL)
