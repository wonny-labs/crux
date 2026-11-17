# SPDX-License-Identifier: Apache-2.0
#
# Configure-time integrity check of a vendor kit, for a module that compiles one.
# A reference of the kit module template, not a Crux interface. Copy it into the
# kit module, next to kit_hashes.py, and call it from the module's CMakeLists.txt
# before any kit source is added to the build:
#
#   include(${CMAKE_CURRENT_LIST_DIR}/cmake/kit_integrity.cmake)
#   kit_integrity_check(NAME kit-a ENV_VAR KIT_A_PATH
#     DEFAULT_PATH ${ZEPHYR_KIT_A_MODULE_DIR}
#     HASH_DIR ${CMAKE_CURRENT_LIST_DIR}/kit-hashes
#     EXPECT_LINE ${CONFIG_ACMECO_KIT_A_LINE})
#
# Rules, all recommendations of docs/vendor-kits.md in crux-pilot:
# - The kit is read from DEFAULT_PATH, the west project path, unless the
#   environment variable named by ENV_VAR is set. That override is for local
#   development only: it is printed as a warning, and refused in a release build.
# - A release build is one configured with -DPRODUCT_RELEASE_BUILD=ON. It also
#   refuses ZEPHYR_MODULES, EXTRA_ZEPHYR_MODULES and ZEPHYR_EXTRA_MODULES, from
#   CMake or from the environment: ZEPHYR_MODULES replaces west's module discovery,
#   and a module added by the others is invisible to the build record.
# - The kit tree must match one committed list, HASH_DIR/<line>/<delivery>.sha256.
#   The match is printed. An unknown delivery warns in development and fails a
#   release build, or any build configured with -DKIT_REQUIRE_KNOWN_DELIVERY=ON.
# - EXPECT_LINE, when given, must equal the line of the matched list.
#
# Results, in the caller's scope: KIT_INTEGRITY_LINE, KIT_INTEGRITY_DELIVERY
# (or "unknown"), KIT_INTEGRITY_DIGEST, KIT_INTEGRITY_PATH and
# KIT_INTEGRITY_SOURCE ("west project" or "environment <ENV_VAR>").
#
# The check runs at configure time. In a CMake project, the kit files and hash
# lists are configure dependencies and CONFIGURE_DEPENDS globs watch for added or
# removed files, so a reused build directory runs CMake, and the check, again.
# The tool is run with Python3_EXECUTABLE (set by Zephyr), else PYTHON_EXECUTABLE,
# else python3 from the PATH.

set(KIT_INTEGRITY_TOOL "${CMAKE_CURRENT_LIST_DIR}/kit_hashes.py")

function(kit_integrity_check)
  cmake_parse_arguments(KIT "" "NAME;ENV_VAR;DEFAULT_PATH;HASH_DIR;EXPECT_LINE" "" ${ARGN})
  foreach(required NAME ENV_VAR DEFAULT_PATH HASH_DIR)
    if(NOT KIT_${required})
      message(FATAL_ERROR "kit_integrity_check: ${required} is required")
    endif()
  endforeach()

  if(PRODUCT_RELEASE_BUILD)
    foreach(var ZEPHYR_MODULES EXTRA_ZEPHYR_MODULES ZEPHYR_EXTRA_MODULES)
      if(DEFINED ${var} AND NOT "${${var}}" STREQUAL "")
        message(FATAL_ERROR "${KIT_NAME}: ${var} is set in CMake, which a release build refuses")
      endif()
      if(DEFINED ENV{${var}} AND NOT "$ENV{${var}}" STREQUAL "")
        message(FATAL_ERROR "${KIT_NAME}: ${var} is set in the environment, which a release build refuses")
      endif()
    endforeach()
  endif()

  if(DEFINED ENV{${KIT_ENV_VAR}} AND NOT "$ENV{${KIT_ENV_VAR}}" STREQUAL "")
    if(PRODUCT_RELEASE_BUILD)
      message(FATAL_ERROR "${KIT_NAME}: ${KIT_ENV_VAR} is set, which a release build refuses. "
                          "A release reads the kit from its west project path.")
    endif()
    file(TO_CMAKE_PATH "$ENV{${KIT_ENV_VAR}}" kit_path)
    set(kit_source "environment ${KIT_ENV_VAR}")
    message(WARNING "${KIT_NAME}: ${KIT_ENV_VAR}=${kit_path} replaces ${KIT_DEFAULT_PATH}, "
                    "for development only. The build record does not cover this tree.")
  else()
    file(TO_CMAKE_PATH "${KIT_DEFAULT_PATH}" kit_path)
    set(kit_source "west project")
  endif()

  if(NOT IS_DIRECTORY "${kit_path}")
    message(FATAL_ERROR "${KIT_NAME}: no kit at ${kit_path}")
  endif()

  if(Python3_EXECUTABLE)
    set(python "${Python3_EXECUTABLE}")
  elseif(PYTHON_EXECUTABLE)
    set(python "${PYTHON_EXECUTABLE}")
  else()
    find_program(python NAMES python3 python REQUIRED)
  endif()
  set(expect)
  if(KIT_EXPECT_LINE)
    set(expect --expect-line "${KIT_EXPECT_LINE}")
  endif()
  execute_process(
    COMMAND "${python}" "${KIT_INTEGRITY_TOOL}" check "${kit_path}" --lists "${KIT_HASH_DIR}" ${expect}
    RESULT_VARIABLE rc OUTPUT_VARIABLE out ERROR_VARIABLE err
    OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_STRIP_TRAILING_WHITESPACE)

  if(rc EQUAL 0 AND out MATCHES "^MATCH line=([^ ]+) delivery=([^ ]+) digest=([0-9a-f]+)$")
    set(line "${CMAKE_MATCH_1}")
    set(delivery "${CMAKE_MATCH_2}")
    set(digest "${CMAKE_MATCH_3}")
    message(STATUS "${KIT_NAME}: line ${line}, delivery ${delivery}, hash list ${digest}, "
                   "from ${kit_path} (${kit_source})")
  elseif(rc EQUAL 1 AND out MATCHES "^UNKNOWN digest=([0-9a-f]+)$")
    set(line "")
    set(delivery "unknown")
    set(digest "${CMAKE_MATCH_1}")
    set(text "${KIT_NAME}: unknown delivery at ${kit_path} (${kit_source}): its hash list "
             "${digest} matches no list in ${KIT_HASH_DIR}")
    if(PRODUCT_RELEASE_BUILD OR KIT_REQUIRE_KNOWN_DELIVERY)
      message(FATAL_ERROR ${text})
    endif()
    message(WARNING ${text} ". Development only: this build is not a release candidate.")
  else()
    message(FATAL_ERROR "${KIT_NAME}: kit check failed: ${err}${out}")
  endif()

  # In a project (not in script mode), make the kit files and the hash lists configure
  # dependencies, so that a changed file runs CMake, and so this check, again. The
  # CONFIGURE_DEPENDS globs also run CMake again when a file is added or removed. The
  # top-level .git entry is left out, as in kit_hashes.py.
  if(NOT CMAKE_SCRIPT_MODE_FILE)
    file(GLOB kit_top LIST_DIRECTORIES true CONFIGURE_DEPENDS "${kit_path}/*")
    set(kit_files)
    foreach(entry ${kit_top})
      if(entry STREQUAL "${kit_path}/.git")
        continue()
      elseif(IS_DIRECTORY "${entry}")
        file(GLOB_RECURSE entry_files LIST_DIRECTORIES false CONFIGURE_DEPENDS "${entry}/*")
        list(APPEND kit_files ${entry_files})
      else()
        list(APPEND kit_files "${entry}")
      endif()
    endforeach()
    file(GLOB_RECURSE list_files LIST_DIRECTORIES false CONFIGURE_DEPENDS "${KIT_HASH_DIR}/*.sha256")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${kit_files} ${list_files})
  endif()

  set(KIT_INTEGRITY_LINE "${line}" PARENT_SCOPE)
  set(KIT_INTEGRITY_DELIVERY "${delivery}" PARENT_SCOPE)
  set(KIT_INTEGRITY_DIGEST "${digest}" PARENT_SCOPE)
  set(KIT_INTEGRITY_PATH "${kit_path}" PARENT_SCOPE)
  set(KIT_INTEGRITY_SOURCE "${kit_source}" PARENT_SCOPE)
endfunction()
