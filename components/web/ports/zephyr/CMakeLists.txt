get_filename_component(CRUX_WEB_COMPONENT_DIR "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
get_filename_component(CRUX_ROOT_DIR "${CRUX_WEB_COMPONENT_DIR}/../.." ABSOLUTE)

# A project sees the public header and the access types it names, and no Zephyr.
add_library(crux_web_api INTERFACE)
target_include_directories(crux_web_api INTERFACE
    "${CRUX_WEB_COMPONENT_DIR}/include"
    "${CRUX_ROOT_DIR}/components/access/include")
target_compile_definitions(crux_web_api INTERFACE CRUX_WEB_BODY_BUFFER=${CONFIG_CRUX_WEB_BODY_BUFFER}u)
target_compile_options(crux_web_api INTERFACE ${TOOLCHAIN_C_FLAGS})

add_library(crux_web_zephyr STATIC
    "${CRUX_WEB_COMPONENT_DIR}/src/web_core.c"
    "${CRUX_WEB_COMPONENT_DIR}/src/web_response.c"
    "${CRUX_WEB_COMPONENT_DIR}/src/web_route.c"
    "${CMAKE_CURRENT_LIST_DIR}/web_http_server.c")
target_include_directories(crux_web_zephyr PRIVATE
    "${CRUX_WEB_COMPONENT_DIR}/adapter"
    "${CRUX_WEB_COMPONENT_DIR}/src"
    "${CRUX_WEB_COMPONENT_DIR}/ports/zephyr/include"
    "${CMAKE_CURRENT_LIST_DIR}")
zephyr_append_cmake_library(crux_web_zephyr)
target_link_libraries(crux_web_zephyr PRIVATE crux_web_api zephyr_interface)
target_compile_definitions(crux_web_zephyr PRIVATE
    CRUX_WEB_EXCHANGE_MAX=${CONFIG_HTTP_SERVER_MAX_CLIENTS})
target_compile_options(crux_web_zephyr PRIVATE -Wall -Wextra -Werror)

add_library(crux_web INTERFACE)
add_library(crux::web ALIAS crux_web)
target_link_libraries(crux_web INTERFACE crux_web_api)

# The composition interface of the web start (ADR-0004 phase 1a, Experimental): the header
# <crux/web_zephyr.h>, under ports/zephyr/include/crux/, and the portable web target. The name differs
# from the STATIC provider library crux_web_zephyr above, which Kconfig selects with CONFIG_CRUX_WEB and
# which this target does not link (rule 2 of docs/composition-interfaces.md). A native-free consumer check
# rejects it by name and by path (rule 3), and tests/build/test_web_zephyr_boundary.py shows that.
function(crux_web_zephyr_composition)
  add_library(crux_web_zephyr_composition INTERFACE)
  add_library(crux::web_zephyr ALIAS crux_web_zephyr_composition)
  target_include_directories(crux_web_zephyr_composition INTERFACE "${CRUX_WEB_COMPONENT_DIR}/ports/zephyr/include")
  target_link_libraries(crux_web_zephyr_composition INTERFACE crux_web)
endfunction()
crux_web_zephyr_composition()

# Only for a composition, and for the generated resources, which need the server's own headers.
add_library(crux_web_adapter INTERFACE)
target_include_directories(crux_web_adapter INTERFACE "${CRUX_WEB_COMPONENT_DIR}/adapter")
target_link_libraries(crux_web_adapter INTERFACE crux_web_api)
add_library(crux_web_zephyr_resources INTERFACE)
target_include_directories(crux_web_zephyr_resources INTERFACE "${CMAKE_CURRENT_LIST_DIR}")

zephyr_linker_sources(SECTIONS sections.ld)
zephyr_linker_section(NAME http_resource_desc_crux_web_service
    KVMA RAM_REGION GROUP RODATA_REGION)
