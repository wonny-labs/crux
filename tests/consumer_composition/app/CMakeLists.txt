# SPDX-License-Identifier: Apache-2.0
# ADR-0004 T3: a product outside the Crux repository that composes the management services. Build it from a
# copy outside the repository with scripts/test-consumer-composition.sh, which passes
#   -DZEPHYR_EXTRA_MODULES=<repo> -DCRUX_DIR=<repo>
# CRUX_DIR is the directory of the crux-pilot project in the product's workspace, as docs/management-in-a-product.md
# says, and the product sets it. Nothing here names a file under components/: the product links crux:: targets
# and includes <crux/...> headers.
cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(consumer_composition LANGUAGES C)

if(NOT DEFINED CRUX_DIR)
    message(FATAL_ERROR "Set CRUX_DIR to the crux-pilot project of the workspace")
endif()
if(NOT CONFIG_BOARD_NATIVE_SIM OR NOT CONFIG_FAKE_ENTROPY_NATIVE_SIM)
    message(FATAL_ERROR "This product is a native_sim test image: its entropy is test-only")
endif()

include(${CRUX_DIR}/cmake/CruxWebAssets.cmake)
include(${CRUX_DIR}/cmake/CruxWebRoutes.cmake)

# The Mbed profile's locks for TF-PSA-Crypto's core: product glue, in this project (see tf_psa_threading/).
target_sources(app PRIVATE src/main.c ../domain/product_policy.c src/my_routes.c
    tf_psa_threading/crux_tf_psa_threading.c)
zephyr_include_directories(tf_psa_threading)

# The portable usage targets of the services whose public headers this product includes, and the one
# composition interface it needs (the File root binding).
target_link_libraries(app PRIVATE crux::access crux::credential_store crux::security_event crux::web
    crux::file_zephyr crux::time crux::system)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)

# The frontend folder, with index.html at its top. The Angular example replaces the one-page default with
# -DCRUX_CONSUMER_WEB_FOLDER=<dist> -DCRUX_CONSUMER_WEB_STYLE=inline (it injects styles at run time) and
# CONFIG_CRUX_WEB_RESPONSE_DEADLINE_MS=3000: see docs/web-assets.md and docs/e2e-native-220.md.
set(CRUX_CONSUMER_WEB_FOLDER "${CMAKE_CURRENT_LIST_DIR}/site" CACHE PATH "The folder to package")
set(CRUX_CONSUMER_WEB_STYLE strict CACHE STRING "strict, or inline for the Angular example")
crux_web_assets(app FOLDER ${CRUX_CONSUMER_WEB_FOLDER} STYLE ${CRUX_CONSUMER_WEB_STYLE})
# The route sources of the Crux services are not named yet: see the README, "What is missing".
crux_web_routes(app SOURCES src/my_routes.c ZEPHYR_RESOURCES REVIEWED ${CMAKE_CURRENT_LIST_DIR}/reviewed-routes.txt)
