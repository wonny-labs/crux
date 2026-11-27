# SPDX-License-Identifier: Apache-2.0
# ADR-0005 T3: a product outside the Crux repository that uses only the public System service on native_sim.
# Build it from a copy outside the repository (scripts/test-consumer-system.sh does), with
#   west build -b native_sim/native/64 <this directory> -- -DZEPHYR_EXTRA_MODULES=<crux checkout>
# Nothing here names a file inside the Crux repository: the product links one crux:: target and includes
# <crux/...> headers.
cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(consumer_system LANGUAGES C)

target_sources(app PRIVATE src/main.c)
target_link_libraries(app PRIVATE crux::system)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
