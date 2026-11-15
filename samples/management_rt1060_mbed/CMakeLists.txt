# SPDX-License-Identifier: Apache-2.0
# RT1060-EVK Rev B management image on the Mbed TLS profile (docs/rt1060-mbed-management-image.md): HTTPS web
# management, Access with the credential store, the TLS certificate model, security events to Logging, status,
# configuration, network settings, file and reboot services. It is meant to RUN on the board and is built here,
# never flashed or reset by anything in this repository. No Wolf, no SSH.
#
# The services come from the Zephyr module under their Kconfig symbols (ADR-0004 phase 0): this file compiles
# none of their sources into `app`. What `app` holds is its own composition and the route sources, which the module
# cannot build because the route table belongs to the image.
cmake_minimum_required(VERSION 3.20.0)
get_filename_component(CRUX_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
set(composition_dir "${CRUX_ROOT}/tests/native/management_composition")
set(EXTRA_CONF_FILE
    "${CRUX_ROOT}/tests/native/tls_offload_probe/mbed.conf"
    "${composition_dir}/profile-psa.conf")
set(DTC_OVERLAY_FILE
    "${CRUX_ROOT}/samples/controller/zephyr/m3-network.overlay"
    "${CMAKE_CURRENT_LIST_DIR}/target.overlay"
    "${CMAKE_CURRENT_LIST_DIR}/ram_disk.overlay")
list(APPEND ZEPHYR_EXTRA_MODULES "${CRUX_ROOT}")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_management_rt1060_mbed LANGUAGES C)

# An unsatisfied Kconfig dependency only warns, so each rule is also checked here.
if(NOT "${CONFIG_BOARD_TARGET}" STREQUAL "mimxrt1060_evk@B/mimxrt1062/qspi")
    message(FATAL_ERROR "This image is for mimxrt1060_evk@B//qspi only, not '${CONFIG_BOARD_TARGET}'")
endif()
if(NOT CONFIG_PSA_CRYPTO_PROVIDER_MBEDTLS OR NOT CONFIG_MBEDTLS)
    message(FATAL_ERROR "This image is the Mbed TLS profile: the PSA provider must be Mbed TLS")
endif()
if(NOT CONFIG_CRUX_PSA_THREADING)
    message(FATAL_ERROR "This image needs the locks of the Mbed profile's core: CONFIG_CRUX_PSA_THREADING=y")
endif()
# Entropy: the i.MX RT TRNG through its driver, and nothing else. A test generator or a fake source would make keys
# that mean nothing, so each is refused, and a missing TRNG driver is too.
if(CONFIG_TEST_RANDOM_GENERATOR OR CONFIG_FAKE_ENTROPY_NATIVE_SIM)
    message(FATAL_ERROR "This image must not use test entropy (CONFIG_TEST_RANDOM_GENERATOR, fake entropy)")
endif()
if(NOT CONFIG_ENTROPY_MCUX_TRNG OR NOT CONFIG_MBEDTLS_PSA_DRIVER_GET_ENTROPY)
    message(FATAL_ERROR "This image needs the i.MX RT TRNG driver (CONFIG_ENTROPY_MCUX_TRNG) as the PSA entropy "
                        "source (CONFIG_MBEDTLS_PSA_DRIVER_GET_ENTROPY)")
endif()
if(CONFIG_DISK_DRIVER_SDMMC OR CONFIG_IMX_USDHC)
    message(FATAL_ERROR "This image reaches no card: its file backend is a RAM disk, and the SD driver must be off")
endif()
if(NOT CONFIG_CRUX_FILE_FATFS_RT1060_RAM_DISK OR NOT CONFIG_CRUX_ACCESS OR NOT CONFIG_CRUX_WEB_SESSION OR
   NOT CONFIG_CRUX_WEB_MANAGEMENT OR NOT CONFIG_CRUX_TLS_CERTIFICATE OR NOT CONFIG_CRUX_REBOOT OR
   NOT CONFIG_CRUX_FILE_SERVICE OR NOT CONFIG_CRUX_NETWORK_SETTINGS OR NOT CONFIG_CRUX_CONFIG_SERVICE OR
   NOT CONFIG_CRUX_MGMT_STATUS OR NOT CONFIG_CRUX_WEB)
    message(FATAL_ERROR "A service symbol or the RAM disk provider was dropped by Kconfig: check the configuration")
endif()
if(CONFIG_WOLFSSL OR CONFIG_CRUX_SSH OR CONFIG_CRUX_WEB_PLAIN_HTTP_FOR_TESTS)
    message(FATAL_ERROR "This image is HTTPS on Mbed TLS: no Wolf stack, no SSH, no plain HTTP")
endif()

# The random read of a failed TRNG must fail PSA and not fall back to a general-purpose generator: Zephyr's glue
# for TF-PSA-Crypto answers a failed read with sys_rand_get(), which is not cryptographic on this board.
include("${CRUX_ROOT}/cmake/CruxMbedtlsEntropy.cmake")
crux_mbedtls_fail_closed_entropy()

include("${CRUX_ROOT}/components/web/session/sources.cmake")
include("${CRUX_ROOT}/components/web/management/sources.cmake")
include("${CRUX_ROOT}/cmake/CruxWebAssets.cmake")
include("${CRUX_ROOT}/cmake/CruxWebRoutes.cmake")

# The boot check of the random source comes from test code of this repository, because no public form exists yet
# (docs/rt1060-mbed-management-image.md, "Taken from tests"). The locks of the Mbed profile's core are the module's
# own provider, CONFIG_CRUX_PSA_THREADING in prj.conf.
set(entropy_boot "${CRUX_ROOT}/tests/zephyr/entropy_boot")
target_sources(app PRIVATE src/main.c src/composition.c src/medium.c "${entropy_boot}/entropy_boot.c")
target_include_directories(app PRIVATE src "${entropy_boot}")

set(route_sources ${CRUX_WEB_SESSION_ROUTES} ${CRUX_WEB_MANAGEMENT_ROUTES}
    ${CRUX_WEB_MANAGEMENT_NETWORK_ROUTES} ${CRUX_WEB_MANAGEMENT_REBOOT_ROUTES})
target_sources(app PRIVATE ${route_sources})
# The web lifecycle has no public header on main yet (ADR-0004 phase 1a PRs 4 and 5), so its two private
# directories are the only private roots this image names (the web adapter's comes with crux_web_adapter).
target_include_directories(app PRIVATE "${CRUX_WEB_SESSION_DIR}" "${CRUX_WEB_MANAGEMENT_DIR}")
# The public usage targets carry each service's include root: `app` names no component directory for them.
target_link_libraries(app PRIVATE crux::access crux::credential_store crux::security_event crux::configuration
    crux::config_service crux::mgmt_status crux::network_settings crux::tls_certificate crux::file_service
    crux::reboot crux::web crux::file_zephyr crux::system crux::time crux_web_adapter
    crux_service_priority_placement)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
crux_web_assets(app FOLDER "${CMAKE_CURRENT_LIST_DIR}/site" STYLE strict)
crux_web_routes(app SOURCES ${route_sources} ZEPHYR_RESOURCES REVIEWED "${CMAKE_CURRENT_LIST_DIR}/reviewed-routes.txt")

# The test form of the first account (off by default, and then absent from the image altogether).
if(CONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT)
    include("${CMAKE_CURRENT_LIST_DIR}/first_account_password.cmake")
    crux_mbed_mgmt_embed_password()
    target_sources(app PRIVATE src/first_account_test.c)
    target_include_directories(app PRIVATE "${CRUX_ROOT}/components/access/adapter")
endif()
