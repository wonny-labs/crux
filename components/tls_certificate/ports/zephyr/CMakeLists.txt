# The TLS certificate module on Zephyr (ADR-0004 phase 0, Experimental): the portable core, the X.509
# encoder, the hash, signature and random ports over PSA Crypto, and the provider of its event port. The
# module's CMake adds this directory only under CONFIG_CRUX_TLS_CERTIFICATE, which needs CONFIG_CRUX_ACCESS
# (and so the credential store that keeps the device key).
#
# It registers nothing with Zephyr's TLS credentials: the application takes the material and calls
# tls_credential_add itself (ADR-0004 C4, A1), so the key's bytes pass through application code and no
# Zephyr call is made here.
#
# It publishes the portable target crux::tls_certificate (ADR-0004 phase 1a, Experimental). The start, the
# material calls and the fingerprint are declared in <crux/tls_certificate_start.h>, which lives under the
# target's own include root, so the target needs no adapter directory: the composition-only adapter target,
# which links the credential adapter on purpose, stays refused by cmake/CruxCredentialBoundary.cmake. The
# header carries the device's private key as PKCS #8 bytes, to the application's TLS registration only.
#
# The sources are the ones the Host build lists in components/tls_certificate/CMakeLists.txt, plus the PSA
# port that the Host composition links, and tests/build/test_management_module.py holds the lists together.
get_filename_component(CRUX_TLS_CERTIFICATE_COMPONENT_DIR "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
get_filename_component(CRUX_COMPONENTS_DIR "${CRUX_TLS_CERTIFICATE_COMPONENT_DIR}/.." ABSOLUTE)
include("${CRUX_COMPONENTS_DIR}/../cmake/CruxAccessBoundary.cmake")
include("${CRUX_COMPONENTS_DIR}/../cmake/CruxCredentialBoundary.cmake")

# A portable usage target, like the Host build's, carrying the public include root and the Access contract
# that <crux/tls_certificate.h> includes. The library below is registered with the Zephyr link by
# zephyr_append_cmake_library, so the target does not link it, and the adapter, src and credential
# directories stay private to the library. tests/build/test_tls_certificate_boundary.py runs this
# definition against the real guards.
function(crux_tls_certificate_public_target)
  add_library(crux_tls_certificate INTERFACE)
  add_library(crux::tls_certificate ALIAS crux_tls_certificate)
  target_include_directories(crux_tls_certificate INTERFACE "${CRUX_TLS_CERTIFICATE_COMPONENT_DIR}/include")
  target_link_libraries(crux_tls_certificate INTERFACE crux::access)
endfunction()

if(NOT CONFIG_CRUX_TLS_CERTIFICATE)
  message(FATAL_ERROR "This directory is the TLS certificate selection of the module: set CONFIG_CRUX_TLS_CERTIFICATE")
endif()

add_library(crux_tls_certificate_zephyr STATIC
  ../../src/tls_certificate.c
  ../../src/tls_x509.c
  ../../src/tls_certificate_events.c
  ../psa/tls_certificate_psa.c
)
target_include_directories(crux_tls_certificate_zephyr PRIVATE
  "${CRUX_TLS_CERTIFICATE_COMPONENT_DIR}/include"
  "${CRUX_TLS_CERTIFICATE_COMPONENT_DIR}/adapter"
  "${CRUX_TLS_CERTIFICATE_COMPONENT_DIR}/src"
  "${CRUX_COMPONENTS_DIR}/access/include"
  "${CRUX_COMPONENTS_DIR}/credential/include"
  "${CRUX_COMPONENTS_DIR}/credential/adapter"
  "${CRUX_COMPONENTS_DIR}/security_event/include")
zephyr_append_cmake_library(crux_tls_certificate_zephyr)
target_link_libraries(crux_tls_certificate_zephyr PRIVATE zephyr_interface crux::base crux::file crux::sync)
add_dependencies(crux_tls_certificate_zephyr zephyr_generated_headers)
target_compile_options(crux_tls_certificate_zephyr PRIVATE -Wall -Wextra -Werror)

crux_tls_certificate_public_target()
cmake_language(DEFER CALL crux_assert_portable_usage crux::tls_certificate)
cmake_language(DEFER CALL crux_assert_access_adapter_unreachable crux::tls_certificate)
cmake_language(DEFER CALL crux_assert_credential_adapter_unreachable crux::tls_certificate)
