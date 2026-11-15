# The web management cores on Zephyr (ADR-0004 phase 0, Experimental): the JSON of the status and
# configuration routes, the save worker, and, with the network settings service, the JSON of its routes. The
# module's CMake adds this directory only under CONFIG_CRUX_WEB_MANAGEMENT, which needs
# CONFIG_CRUX_WEB_SESSION, CONFIG_CRUX_CONFIG_SERVICE and CONFIG_CRUX_MGMT_STATUS.
#
# The route sources (web_management_routes.c, web_management_network.c, web_management_reboot.c) are not
# compiled here: they hold CRUX_WEB_ROUTE uses, and the application names the ones it wants to
# crux_web_routes(), through CRUX_WEB_MANAGEMENT_ROUTES, CRUX_WEB_MANAGEMENT_NETWORK_ROUTES and
# CRUX_WEB_MANAGEMENT_REBOOT_ROUTES of components/web/management/sources.cmake. The save worker's priority
# is the Kconfig symbol of ADR-0002 P3, CONFIG_CRUX_WEB_MANAGEMENT_WORKER_PRIORITY.
#
# It publishes the portable target crux::web_management (ADR-0004 phase 1a, Experimental). The init, the
# worker start and the save query are declared in <crux/web_management.h>, under the include root of crux::web
# that the target links, so the target needs no management, adapter or src directory. It is ordinary service
# API and not a composition interface: nothing in it binds a Crux provider to a Zephyr resource. The sources
# are the ones components/web/management/sources.cmake lists, and tests/build/test_management_module.py
# holds the lists together.
get_filename_component(CRUX_WEB_COMPONENT_DIR "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
get_filename_component(CRUX_COMPONENTS_DIR "${CRUX_WEB_COMPONENT_DIR}/.." ABSOLUTE)
include("${CRUX_COMPONENTS_DIR}/../cmake/CruxAccessBoundary.cmake")
include("${CRUX_COMPONENTS_DIR}/../cmake/CruxWebBoundary.cmake")

# A portable usage target, like the Host build's: the public include roots of crux::web, which carry
# <crux/web_management.h> and <crux/web.h>, and nothing private. The library below is registered with the
# Zephyr link by zephyr_append_cmake_library, so the target does not link it, and the adapter, management and
# src directories stay private to it. tests/build/test_web_lifecycle_boundary.py runs this definition
# against the real guards.
function(crux_web_management_public_target)
  if(NOT TARGET crux::web)
    message(FATAL_ERROR "crux::web_management needs crux::web: set CONFIG_CRUX_WEB")
  endif()
  add_library(crux_web_management INTERFACE)
  add_library(crux::web_management ALIAS crux_web_management)
  target_link_libraries(crux_web_management INTERFACE crux::web)
endfunction()

if(NOT CONFIG_CRUX_WEB_MANAGEMENT)
  message(FATAL_ERROR "This directory is the web management selection of the module: set CONFIG_CRUX_WEB_MANAGEMENT")
endif()

add_library(crux_web_management_zephyr STATIC
  ../../../management/web_management_json.c
  ../../../management/web_management_save.c
)
# The JSON of the network routes needs the network settings service.
if(CONFIG_CRUX_NETWORK_SETTINGS)
  target_sources(crux_web_management_zephyr PRIVATE
    ../../../management/web_management_network_json.c
  )
endif()
target_include_directories(crux_web_management_zephyr PRIVATE
  "${CRUX_WEB_COMPONENT_DIR}/management"
  "${CRUX_WEB_COMPONENT_DIR}/adapter"
  "${CRUX_WEB_COMPONENT_DIR}/src"
  "${CRUX_COMPONENTS_DIR}/config_service/include"
  "${CRUX_COMPONENTS_DIR}/configuration/include"
  "${CRUX_COMPONENTS_DIR}/mgmt_status/include"
  "${CRUX_COMPONENTS_DIR}/network_settings/include")
zephyr_append_cmake_library(crux_web_management_zephyr)
# crux::system gives <crux/system.h>, which <crux/management_status.h> includes. CONFIG_CRUX_WEB_MANAGEMENT
# needs CONFIG_CRUX_MGMT_STATUS, and the module refuses an image without crux::system.
target_link_libraries(crux_web_management_zephyr PRIVATE zephyr_interface crux_web_api crux::base crux::sync
  crux::system crux::thread crux_service_priority_placement)
add_dependencies(crux_web_management_zephyr zephyr_generated_headers)
target_compile_options(crux_web_management_zephyr PRIVATE -Wall -Wextra -Werror)

crux_web_management_public_target()
cmake_language(DEFER CALL crux_assert_portable_usage crux::web_management)
cmake_language(DEFER CALL crux_assert_access_adapter_unreachable crux::web_management)
cmake_language(DEFER CALL crux_assert_web_internal_unreachable crux::web_management)
