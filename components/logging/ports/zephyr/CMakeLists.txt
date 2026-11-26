# No board, SoC or revision check: the binding selects the UART by devicetree (logging_binding.c),
# and a board revision that changes the hardware changes its devicetree.
set(CRUX_LOGGING_PROVIDER zephyr CACHE STRING "Logging provider for this composition")
if(NOT CRUX_LOGGING_PROVIDER STREQUAL "zephyr")
    message(FATAL_ERROR "Crux Logging unsupported provider: ${CRUX_LOGGING_PROVIDER}")
endif()

# Two backend shapes. By default the native UART backend owns a UART of its own. With
# CONFIG_CRUX_CLI_CONSOLE_UART_SHARED the console's backend (components/cli/ports/zephyr/cli_console_log_backend.c)
# replaces it, on the console's UART, and the native UART backend must be off.
if(CONFIG_CRUX_CLI_CONSOLE_UART_SHARED)
    if(CONFIG_LOG_BACKEND_UART)
        message(FATAL_ERROR "Crux Logging shared with the console requires CONFIG_LOG_BACKEND_UART=n: "
                            "the console's backend replaces it")
    endif()
    set(crux_logging_backend_required)
else()
    set(crux_logging_backend_required LOG_BACKEND_UART LOG_BACKEND_UART_AUTOSTART LOG_BACKEND_UART_OUTPUT_TEXT)
endif()
foreach(required LOG LOG_MODE_DEFERRED LOG_PROCESS_THREAD ${crux_logging_backend_required}
                 LOG_BACKEND_SHOW_LEVEL)
    if(NOT CONFIG_${required})
        message(FATAL_ERROR "Crux Logging requires CONFIG_${required}=y")
    endif()
endforeach()

foreach(forbidden LOG_CUSTOM_HEADER LOG_BACKEND_CRLF_NONE SHELL_LOG_BACKEND LOG_MODE_OVERFLOW LOG_BLOCK_IN_THREAD LOG_RUNTIME_FILTERING LOG_FRONTEND
                  LOG_BACKEND_UART_ASYNC LOG_FMT_SECTION_STRIP
                  LOG_BACKEND_ADSP LOG_BACKEND_ADSP_MTRACE LOG_BACKEND_BLE
                  LOG_BACKEND_EFI_CONSOLE LOG_BACKEND_FS LOG_BACKEND_IPC_SERVICE
                  LOG_BACKEND_MQTT LOG_BACKEND_NATIVE_POSIX LOG_BACKEND_NET LOG_BACKEND_RTT
                  LOG_BACKEND_SEMIHOST LOG_BACKEND_SPINEL LOG_BACKEND_SWO LOG_BACKEND_WS
                  LOG_BACKEND_XTENSA_SIM)
    if(CONFIG_${forbidden})
        message(FATAL_ERROR "Crux Logging unsupported CONFIG_${forbidden}=y")
    endif()
endforeach()
if(CONFIG_LOG_MAX_LEVEL LESS 4 OR CONFIG_LOG_OVERRIDE_LEVEL GREATER 0)
    message(FATAL_ERROR "Crux Logging requires DEBUG native ceiling and no native override filter")
endif()

get_filename_component(CRUX_LOGGING_COMPONENT_DIR "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
add_library(crux_logging_api INTERFACE)
target_include_directories(crux_logging_api INTERFACE "${CRUX_LOGGING_COMPONENT_DIR}/include")
target_link_libraries(crux_logging_api INTERFACE crux::base)
target_compile_options(crux_logging_api INTERFACE ${TOOLCHAIN_C_FLAGS})
add_library(crux_logging_zephyr STATIC ../../src/logging.c logging_zephyr.c logging_binding.c)
target_include_directories(crux_logging_zephyr PRIVATE ../../src .)
target_link_libraries(crux_logging_zephyr PRIVATE crux_logging_api zephyr_interface)
zephyr_append_cmake_library(crux_logging_zephyr)
target_compile_options(crux_logging_zephyr PRIVATE -Wall -Wextra -Werror)

set_property(TARGET crux_logging_zephyr PROPERTY INTERFACE_CRUX_LOGGING_PROVIDER zephyr)
set_property(TARGET crux_logging_zephyr APPEND PROPERTY COMPATIBLE_INTERFACE_STRING CRUX_LOGGING_PROVIDER)
add_library(crux_logging INTERFACE)
add_library(crux::logging ALIAS crux_logging)
target_link_libraries(crux_logging INTERFACE crux_logging_api)
cmake_language(DEFER CALL crux_assert_portable_usage crux::logging)
