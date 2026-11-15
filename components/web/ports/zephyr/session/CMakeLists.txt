# Web sessions on Zephyr (ADR-0004 phase 0, Experimental): login, sessions and request forgery protection,
# with the password verification port over PSA Crypto. The module's CMake adds this directory only under
# CONFIG_CRUX_WEB_SESSION, which needs CONFIG_CRUX_ACCESS and CONFIG_CRUX_WEB.
#
# The route source (components/web/session/web_session_routes.c) is not compiled here: it holds
# CRUX_WEB_ROUTE uses, and the application names it to crux_web_routes() as before, through
# CRUX_WEB_SESSION_ROUTES of components/web/session/sources.cmake, so that a route that is not named is
# not in the table. The worker's priority is the Kconfig symbol of ADR-0002 P3,
# CONFIG_CRUX_WEB_SESSION_WORKER_PRIORITY, through crux_service_priority_placement.
#
# It publishes the portable target crux::web_session (ADR-0004 phase 1a, Experimental). The settings type, the
# init, the worker start and the authentication function are declared in <crux/web_session.h>, under the
# include root of crux::web that the target links, so the target needs no session, adapter or src directory.
# It is ordinary service API and not a composition interface: nothing in it binds a Crux provider to a Zephyr
# resource. The sources are the ones components/web/session/sources.cmake lists, plus its PSA port, and
# tests/build/test_management_module.py holds the lists together.
get_filename_component(CRUX_WEB_COMPONENT_DIR "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
get_filename_component(CRUX_COMPONENTS_DIR "${CRUX_WEB_COMPONENT_DIR}/.." ABSOLUTE)
include("${CRUX_COMPONENTS_DIR}/../cmake/CruxAccessBoundary.cmake")
include("${CRUX_COMPONENTS_DIR}/../cmake/CruxWebBoundary.cmake")

# A portable usage target, like the Host build's: the public include roots of crux::web, which carry
# <crux/web_session.h>, <crux/web.h> and the Access types that they name, and nothing private. The library
# below is registered with the Zephyr link by zephyr_append_cmake_library, so the target does not link it, and
# the adapter, session and src directories stay private to it. tests/build/test_web_lifecycle_boundary.py runs
# this definition against the real guards.
function(crux_web_session_public_target)
  if(NOT TARGET crux::web)
    message(FATAL_ERROR "crux::web_session needs crux::web: set CONFIG_CRUX_WEB")
  endif()
  add_library(crux_web_session INTERFACE)
  add_library(crux::web_session ALIAS crux_web_session)
  target_link_libraries(crux_web_session INTERFACE crux::web)
endfunction()

if(NOT CONFIG_CRUX_WEB_SESSION)
  message(FATAL_ERROR "This directory is the web session selection of the module: set CONFIG_CRUX_WEB_SESSION")
endif()

add_library(crux_web_session_zephyr STATIC
  ../../../session/web_session.c
  ../../../session/web_session_attempt.c
  ../../../session/web_session_json.c
  ../../psa/web_session_psa.c
)
target_include_directories(crux_web_session_zephyr PRIVATE
  "${CRUX_WEB_COMPONENT_DIR}/session"
  "${CRUX_WEB_COMPONENT_DIR}/adapter"
  "${CRUX_WEB_COMPONENT_DIR}/src"
  "${CRUX_COMPONENTS_DIR}/access/adapter")
zephyr_append_cmake_library(crux_web_session_zephyr)
target_link_libraries(crux_web_session_zephyr PRIVATE zephyr_interface crux_web_api crux::base crux::sync
  crux::thread crux_service_priority_placement)
add_dependencies(crux_web_session_zephyr zephyr_generated_headers)
target_compile_options(crux_web_session_zephyr PRIVATE -Wall -Wextra -Werror)

crux_web_session_public_target()
cmake_language(DEFER CALL crux_assert_portable_usage crux::web_session)
cmake_language(DEFER CALL crux_assert_access_adapter_unreachable crux::web_session)
cmake_language(DEFER CALL crux_assert_web_internal_unreachable crux::web_session)
