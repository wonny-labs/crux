# SPDX-License-Identifier: Apache-2.0
# Build-local HTTP server core with a header-phase deadline; never modify the pinned Zephyr checkout.
# See patches/zephyr/README.md. It replaces exactly one http_server_core.c in the server's library.
set(crux_http_original "${ZEPHYR_BASE}/subsys/net/lib/http/http_server_core.c")
set(crux_http_generated "${CMAKE_CURRENT_BINARY_DIR}/crux-http/http_server_core.c")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${crux_http_original}"
    "${CRUX_ROOT_DIR}/patches/zephyr/http-header-deadline.patch"
    "${CMAKE_CURRENT_LIST_DIR}/prepare_header_deadline.py")
execute_process(COMMAND ${PYTHON_EXECUTABLE}
    "${CMAKE_CURRENT_LIST_DIR}/prepare_header_deadline.py"
    "${ZEPHYR_BASE}" "${crux_http_generated}"
    COMMAND_ERROR_IS_FATAL ANY)
if(NOT TARGET subsys__net__lib__http)
    message(FATAL_ERROR "Pinned HTTP library is unavailable")
endif()
get_target_property(crux_http_sources subsys__net__lib__http SOURCES)
get_target_property(crux_http_source_dir subsys__net__lib__http SOURCE_DIR)
set(crux_http_remaining "")
set(crux_http_replaced 0)
foreach(crux_http_source IN LISTS crux_http_sources)
    get_filename_component(crux_http_absolute "${crux_http_source}" ABSOLUTE
        BASE_DIR "${crux_http_source_dir}")
    if(crux_http_absolute STREQUAL crux_http_original)
        math(EXPR crux_http_replaced "${crux_http_replaced} + 1")
    else()
        list(APPEND crux_http_remaining "${crux_http_source}")
    endif()
endforeach()
if(NOT crux_http_replaced EQUAL 1)
    message(FATAL_ERROR "Expected exactly one pinned HTTP server core, found ${crux_http_replaced}")
endif()
set_property(TARGET subsys__net__lib__http PROPERTY SOURCES "${crux_http_remaining}")
target_sources(subsys__net__lib__http PRIVATE "${crux_http_generated}")
# The copy includes "headers/server_internal.h" and "../../ip/net_private.h" relative to its own
# directory in the tree, so the tree's directory goes on the include path.
target_include_directories(subsys__net__lib__http PRIVATE "${ZEPHYR_BASE}/subsys/net/lib/http")
