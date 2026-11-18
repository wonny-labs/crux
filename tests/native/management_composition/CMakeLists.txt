# SPDX-License-Identifier: Apache-2.0
# The management composition's own test, on the profile that EXTRA_CONF_FILE selects:
#   mbed: ../tls_offload_probe/mbed.conf;profile-psa.conf;mbed-threading.conf
#   wolf: ../tls_offload_probe/wolf.conf;profile-psa.conf, with a patched ZEPHYR_BASE
cmake_minimum_required(VERSION 3.20.0)
get_filename_component(CRUX_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
list(APPEND ZEPHYR_EXTRA_MODULES "${CRUX_ROOT}")
# The module's lock provider counts locks for this fixture only (zephyr/psa_threading/CMakeLists.txt).
set(CRUX_PSA_THREADING_TEST_COUNTER ON)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_native_management_composition LANGUAGES C)
include("${CMAKE_CURRENT_LIST_DIR}/composition/composition.cmake")
crux_native_management_compose()
target_sources(app PRIVATE src/main.c)
