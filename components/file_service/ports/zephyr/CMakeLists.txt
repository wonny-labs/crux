# The file service on Zephyr (ADR-0004 phase 0, Experimental): the portable core, which reaches the files
# only through the Crux File contract, and the provider of its event port over the security events. The
# module's CMake adds this directory only under CONFIG_CRUX_FILE_SERVICE, which needs CONFIG_CRUX_ACCESS (and
# so a Crux File provider, which that symbol's configuration check already requires).
#
# Publishes the portable target crux::file_service. The sources are
# the ones the Host build lists in components/file_service/CMakeLists.txt, and
# tests/build/test_management_module.py holds the two lists together.
get_filename_component(CRUX_FILE_SERVICE_COMPONENT_DIR "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
get_filename_component(CRUX_COMPONENTS_DIR "${CRUX_FILE_SERVICE_COMPONENT_DIR}/.." ABSOLUTE)
include("${CRUX_COMPONENTS_DIR}/../cmake/CruxAccessBoundary.cmake")

# A portable usage target, like the Host build's (ADR-0004 phase 1a, Experimental; the owner approved the
# names on 2026-11-15): the public include root and the contracts that the header includes,
# and nothing private. The library below is registered with the Zephyr link by zephyr_append_cmake_library,
# so the target does not link it. tests/build/test_service_usage_targets.py runs this definition against
# the real guards.
function(crux_file_service_public_target)
  add_library(crux_file_service INTERFACE)
  add_library(crux::file_service ALIAS crux_file_service)
  target_include_directories(crux_file_service INTERFACE "${CRUX_FILE_SERVICE_COMPONENT_DIR}/include")
  target_link_libraries(crux_file_service INTERFACE crux::access crux::file)
endfunction()

if(NOT CONFIG_CRUX_FILE_SERVICE)
  message(FATAL_ERROR "This directory is the file service selection of the module: set CONFIG_CRUX_FILE_SERVICE")
endif()

add_library(crux_file_service_zephyr STATIC
  ../../src/file_service.c
  ../../src/file_service_security_events.c
)
target_include_directories(crux_file_service_zephyr PRIVATE
  "${CRUX_FILE_SERVICE_COMPONENT_DIR}/include"
  "${CRUX_FILE_SERVICE_COMPONENT_DIR}/src"
  "${CRUX_COMPONENTS_DIR}/access/include"
  "${CRUX_COMPONENTS_DIR}/security_event/include")
zephyr_append_cmake_library(crux_file_service_zephyr)
target_link_libraries(crux_file_service_zephyr PRIVATE zephyr_interface crux::base crux::file crux::sync)
add_dependencies(crux_file_service_zephyr zephyr_generated_headers)
target_compile_options(crux_file_service_zephyr PRIVATE -Wall -Wextra -Werror)

crux_file_service_public_target()
cmake_language(DEFER CALL crux_assert_portable_usage crux::file_service)
cmake_language(DEFER CALL crux_assert_access_adapter_unreachable crux::file_service)
