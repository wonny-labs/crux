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
# No crux:: target and no public header: see components/access/ports/zephyr/CMakeLists.txt. The sources are
# the ones components/web/session/sources.cmake lists, plus its PSA port, and
# tests/build/test_management_module.py holds the lists together.
get_filename_component(CRUX_WEB_COMPONENT_DIR "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
get_filename_component(CRUX_COMPONENTS_DIR "${CRUX_WEB_COMPONENT_DIR}/.." ABSOLUTE)

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
