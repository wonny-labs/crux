# SPDX-License-Identifier: Apache-2.0
# ADR-0004 phase 0: an application that enables the management service cores with Kconfig and
# ZEPHYR_EXTRA_MODULES, and compiles none of the cores into its own target. Compare
# tests/native/management_composition, which lists them in `app`. What it does compile into `app` are the
# route sources that the application names to crux_web_routes() (the module builds none of them, since the route
# table is per image).
#
# Build it with the Mbed profile, as scripts/test-management-module.sh does:
#   -DEXTRA_CONF_FILE=../tls_offload_probe/mbed.conf;../management_composition/profile-psa.conf;../management_composition/mbed-threading.conf
#
# What this fixture still reaches by include path: the Access first-account call, which no public
# header carries by decision (ADR-0004 section 2); and the credential store's start and the TLS
# certificate module's start, which <crux/credential_store.h> with crux::credential_store and
# <crux/tls_certificate_start.h> with crux::tls_certificate now carry (phase 1a), but this fixture has
# not moved to yet. For the three route sources it also reaches the private directories of the web
# component: components/web/session, components/web/management and components/web/src, and the private
# target crux_web_adapter (components/web/adapter). A product outside the repository cannot do that and
# keep to the include rule of ADR-0004 section 5; crux_web_routes() and crux_web_assets() no longer
# hand those directories to a product's own sources (PRs 425 and 427), and the T3 fixture uses them. The
# TF-PSA-Crypto locks of the Mbed profile come from the management composition's
# test glue, which a later phase decides how a product obtains.
cmake_minimum_required(VERSION 3.20.0)
get_filename_component(CRUX_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
list(APPEND ZEPHYR_EXTRA_MODULES "${CRUX_ROOT}")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_management_module LANGUAGES C)

if(NOT CONFIG_BOARD_NATIVE_SIM OR NOT CONFIG_FAKE_ENTROPY_NATIVE_SIM)
    message(FATAL_ERROR "This fixture is restricted to native_sim: its entropy is test-only")
endif()
# The fixture must show C6: it asks for the service symbol and for nothing else of Thread or Sync.
file(READ "${CMAKE_CURRENT_LIST_DIR}/prj.conf" fixture_conf)
if(fixture_conf MATCHES "CONFIG_CRUX_(THREAD|SYNC|TIME)[A-Z_]*=")
    message(FATAL_ERROR "prj.conf must not name a CONFIG_CRUX_THREAD, CONFIG_CRUX_SYNC or CONFIG_CRUX_TIME symbol: the service symbol selects them")
endif()
if(NOT CONFIG_CRUX_THREAD OR NOT CONFIG_CRUX_SYNC OR NOT CONFIG_CRUX_TIME)
    message(FATAL_ERROR "CONFIG_CRUX_ACCESS did not select Thread, Sync and Time")
endif()

if(NOT CONFIG_CRUX_CONFIG_SERVICE OR NOT CONFIG_CRUX_MGMT_STATUS OR NOT CONFIG_CRUX_NETWORK_SETTINGS OR
   NOT CONFIG_CRUX_TLS_CERTIFICATE OR NOT CONFIG_CRUX_FILE_SERVICE OR NOT CONFIG_CRUX_REBOOT OR
   NOT CONFIG_CRUX_WEB OR NOT CONFIG_CRUX_WEB_SESSION OR NOT CONFIG_CRUX_WEB_MANAGEMENT)
    message(FATAL_ERROR "The fixture needs the symbols of slices 2, 3 and 4")
endif()

# The locks of the Mbed profile's core come from the module (CONFIG_CRUX_PSA_THREADING, set by mbed-threading.conf).
# Its header is on the global include path and src/main.c reads the lock count through it.
target_sources(app PRIVATE src/main.c)
target_include_directories(app PRIVATE
    "${CRUX_ROOT}/components/access/include" "${CRUX_ROOT}/components/access/adapter"
    "${CRUX_ROOT}/components/credential/include" "${CRUX_ROOT}/components/credential/adapter"
    "${CRUX_ROOT}/components/security_event/include"
    "${CRUX_ROOT}/components/config_service/include" "${CRUX_ROOT}/components/configuration/include"
    "${CRUX_ROOT}/components/mgmt_status/include" "${CRUX_ROOT}/components/network_settings/include"
    "${CRUX_ROOT}/components/tls_certificate/include" "${CRUX_ROOT}/components/tls_certificate/adapter"
    "${CRUX_ROOT}/components/file_service/include" "${CRUX_ROOT}/components/reboot/include")
target_link_libraries(app PRIVATE crux::file_zephyr crux::system crux::time crux_web_adapter
    crux_service_priority_placement)

# The route sources are the application's: it names the ones it wants, and only those are in the table. The
# module builds the session and management cores, not these (ADR-0004 phase 0, slice 4).
include("${CRUX_ROOT}/components/web/session/sources.cmake")
include("${CRUX_ROOT}/components/web/management/sources.cmake")
include("${CRUX_ROOT}/cmake/CruxWebRoutes.cmake")
set(route_sources ${CRUX_WEB_SESSION_ROUTES} ${CRUX_WEB_MANAGEMENT_ROUTES}
    ${CRUX_WEB_MANAGEMENT_NETWORK_ROUTES})
target_sources(app PRIVATE ${route_sources})
target_include_directories(app PRIVATE "${CRUX_WEB_SESSION_DIR}" "${CRUX_WEB_MANAGEMENT_DIR}"
    "${CRUX_ROOT}/components/web/src")
crux_web_routes(app SOURCES ${route_sources} ZEPHYR_RESOURCES REVIEWED reviewed-routes.txt)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
