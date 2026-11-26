# SPDX-License-Identifier: Apache-2.0
# Build-local TCP stack whose RFC 6528 initial sequence number fails closed; never modify the pinned Zephyr
# checkout. See patches/zephyr/README.md. It replaces exactly one tcp.c in the IP stack's library.
get_filename_component(crux_tcp_isn_repo "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
set(crux_tcp_isn_original "${ZEPHYR_BASE}/subsys/net/ip/tcp.c")
set(crux_tcp_isn_generated "${CMAKE_CURRENT_BINARY_DIR}/crux-tcp-isn/tcp.c")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${crux_tcp_isn_original}"
    "${crux_tcp_isn_repo}/patches/zephyr/tcp-isn-fail-closed.patch"
    "${crux_tcp_isn_repo}/scripts/prepare-tcp-isn.py")
execute_process(COMMAND ${PYTHON_EXECUTABLE}
    "${crux_tcp_isn_repo}/scripts/prepare-tcp-isn.py"
    "${ZEPHYR_BASE}" "${crux_tcp_isn_generated}"
    COMMAND_ERROR_IS_FATAL ANY)
if(NOT TARGET subsys__net__ip)
    message(FATAL_ERROR "Pinned IP stack library is unavailable")
endif()
get_target_property(crux_tcp_isn_sources subsys__net__ip SOURCES)
get_target_property(crux_tcp_isn_source_dir subsys__net__ip SOURCE_DIR)
set(crux_tcp_isn_remaining "")
set(crux_tcp_isn_replaced 0)
foreach(crux_tcp_isn_source IN LISTS crux_tcp_isn_sources)
    get_filename_component(crux_tcp_isn_absolute "${crux_tcp_isn_source}" ABSOLUTE
        BASE_DIR "${crux_tcp_isn_source_dir}")
    if(crux_tcp_isn_absolute STREQUAL crux_tcp_isn_original)
        math(EXPR crux_tcp_isn_replaced "${crux_tcp_isn_replaced} + 1")
    else()
        list(APPEND crux_tcp_isn_remaining "${crux_tcp_isn_source}")
    endif()
endforeach()
if(NOT crux_tcp_isn_replaced EQUAL 1)
    message(FATAL_ERROR "Expected exactly one pinned TCP source, found ${crux_tcp_isn_replaced}")
endif()
set_property(TARGET subsys__net__ip PROPERTY SOURCES "${crux_tcp_isn_remaining}")
target_sources(subsys__net__ip PRIVATE "${crux_tcp_isn_generated}")
# The library's include path already holds subsys/net/ip, where the copy's private headers are.
