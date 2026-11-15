# The network settings service on Zephyr (ADR-0004 phase 0, Experimental): the portable core, the settings
# check and the provider of its event port over the security events. The module's CMake adds this directory
# only under CONFIG_CRUX_NETWORK_SETTINGS, which needs CONFIG_CRUX_ACCESS and CONFIG_CRUX_CONFIG_SERVICE.
#
# The apply port is the application's (ADR-0004 C3): the core calls crux_network_settings_port_apply() and
# crux_network_settings_port_running(), declared in the public
# <crux/network_settings_apply_port.h>, and an application that applies settings to an interface
# implements them. With CONFIG_CRUX_NETWORK_SETTINGS_NO_APPLY the module builds the
# port that applies nothing (src/network_settings_no_apply.c) instead, for native_sim and for an image whose
# application applies nothing. The two must not be combined: an application's own port would then define
# the same symbols twice.
#
# The serial recovery command (src/network_settings_cli.c) belongs to the command line and is not built here.
# Publishes the portable target crux::network_settings. The sources are
# the ones the Host build lists in components/network_settings/CMakeLists.txt, and
# tests/build/test_management_module.py holds the two lists together.
get_filename_component(CRUX_NETWORK_SETTINGS_COMPONENT_DIR "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
get_filename_component(CRUX_COMPONENTS_DIR "${CRUX_NETWORK_SETTINGS_COMPONENT_DIR}/.." ABSOLUTE)
include("${CRUX_COMPONENTS_DIR}/../cmake/CruxAccessBoundary.cmake")

# A portable usage target, like the Host build's (ADR-0004 phase 1a, Experimental, held for the owner's
# approval of the new target names): the public include root and the contracts that the header includes,
# and nothing private. The library below is registered with the Zephyr link by zephyr_append_cmake_library,
# so the target does not link it. tests/build/test_service_usage_targets.py runs this definition against
# the real guards.
function(crux_network_settings_public_target)
  add_library(crux_network_settings INTERFACE)
  add_library(crux::network_settings ALIAS crux_network_settings)
  target_include_directories(crux_network_settings INTERFACE "${CRUX_NETWORK_SETTINGS_COMPONENT_DIR}/include")
  target_link_libraries(crux_network_settings INTERFACE crux::access crux::config_service)
endfunction()

if(NOT CONFIG_CRUX_NETWORK_SETTINGS)
  message(FATAL_ERROR "This directory is the network settings selection of the module: set CONFIG_CRUX_NETWORK_SETTINGS")
endif()

add_library(crux_network_settings_zephyr STATIC
  ../../src/network_settings_check.c
  ../../src/network_settings.c
  ../../src/network_settings_events.c
)
if(CONFIG_CRUX_NETWORK_SETTINGS_NO_APPLY)
  target_sources(crux_network_settings_zephyr PRIVATE
    ../../src/network_settings_no_apply.c
  )
endif()
target_include_directories(crux_network_settings_zephyr PRIVATE
  "${CRUX_NETWORK_SETTINGS_COMPONENT_DIR}/include"
  "${CRUX_NETWORK_SETTINGS_COMPONENT_DIR}/src"
  "${CRUX_COMPONENTS_DIR}/access/include"
  "${CRUX_COMPONENTS_DIR}/config_service/include"
  "${CRUX_COMPONENTS_DIR}/configuration/include"
  "${CRUX_COMPONENTS_DIR}/security_event/include")
zephyr_append_cmake_library(crux_network_settings_zephyr)
target_link_libraries(crux_network_settings_zephyr PRIVATE zephyr_interface crux::base crux::sync crux::thread
  crux_service_priority_placement)
add_dependencies(crux_network_settings_zephyr zephyr_generated_headers)
target_compile_options(crux_network_settings_zephyr PRIVATE -Wall -Wextra -Werror)

crux_network_settings_public_target()
cmake_language(DEFER CALL crux_assert_portable_usage crux::network_settings)
cmake_language(DEFER CALL crux_assert_access_adapter_unreachable crux::network_settings)
