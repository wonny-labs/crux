# A script run with `cmake -P` has no project, so it sets the policies of the CI's CMake itself:
# without this, CMake 3.28 reads IN_LIST as an argument and not as an operator (policy CMP0057).
cmake_minimum_required(VERSION 3.28)

# Boundary check of the update agent component, run as a test with `cmake -P`. It reads the sources
# and fails when the public header or the portable core names a native facility:
#
#   - the public header includes only <stdbool.h>, <stddef.h>, <stdint.h> and <crux/image_state.h>;
#   - neither the public header, the portable core nor the private port includes or names a Zephyr,
#     MCUboot, bootutil, flash-area, NVS or PSA facility, or a frozen thread or sync header;
#   - only crux/update_agent.h is under include/.
#
# Input: -DCOMPONENT_DIR=<components/update_agent>
if(NOT DEFINED COMPONENT_DIR)
    message(FATAL_ERROR "COMPONENT_DIR is required")
endif()

set(public_header "${COMPONENT_DIR}/include/crux/update_agent.h")
file(STRINGS "${public_header}" includes REGEX "^[ \t]*#[ \t]*include")
set(allowed "<stdbool.h>" "<stddef.h>" "<stdint.h>" "<crux/image_state.h>")
foreach(line IN LISTS includes)
    string(REGEX REPLACE "^[ \t]*#[ \t]*include[ \t]*" "" header "${line}")
    string(STRIP "${header}" header)
    if(NOT header IN_LIST allowed)
        message(FATAL_ERROR "the public header includes ${header}, which is outside the contract")
    endif()
endforeach()

file(GLOB core_files "${COMPONENT_DIR}/src/*.c" "${COMPONENT_DIR}/src/*.h")
set(checked ${public_header} ${core_files})
set(forbidden_patterns
    "zephyr/"
    "mcuboot"
    "MCUBOOT"
    "bootutil"
    "boot_set_next"
    "boot_write_img"
    "flash_area"
    "nvs_"
    "psa_"
    "crux/thread\\.h"
    "crux/sync\\.h"
    "crux/queue\\.h"
    "crux/serial\\.h")
foreach(file IN LISTS checked)
    file(READ "${file}" text)
    # Comments may name the bootloader, because they explain the contract. Code may not.
    string(REGEX REPLACE "/\\*([^*]|\\*+[^*/])*\\*+/" "" code "${text}")
    string(REGEX REPLACE "//[^\n]*" "" code "${code}")
    foreach(pattern IN LISTS forbidden_patterns)
        if(code MATCHES "${pattern}")
            message(FATAL_ERROR "${file} names a native facility in code: ${pattern}")
        endif()
    endforeach()
endforeach()

file(GLOB_RECURSE headers_under_include "${COMPONENT_DIR}/include/*")
foreach(header IN LISTS headers_under_include)
    get_filename_component(name "${header}" NAME)
    if(NOT name STREQUAL "update_agent.h")
        message(FATAL_ERROR "unexpected public header ${header}")
    endif()
endforeach()

message(STATUS "update agent boundary check passed")
