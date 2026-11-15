# The command line on Zephyr. Without CONFIG_CRUX_CLI_CONSOLE this is compile evidence: nothing here is
# linked into an image, and a composition that calls these functions has to supply them. No board is
# operated.
#
# Under CONFIG_CRUX_CLI_CONSOLE (ADR-0004 phase 1b, Experimental) the module registers crux_cli_zephyr with
# the Zephyr link, adds the provider of the event port over the security events and the start of the
# console (cli_serial_start.c), and defines the composition target crux::cli_zephyr for
# <crux/cli_zephyr.h>, which binds the console to the UART of the devicetree alias crux-serial0.
get_filename_component(CRUX_CLI_COMPONENT_DIR "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
get_filename_component(CRUX_ACCESS_COMPONENT_DIR "${CRUX_CLI_COMPONENT_DIR}/../access" ABSOLUTE)

add_library(crux_cli_api INTERFACE)
target_include_directories(crux_cli_api INTERFACE
    "${CRUX_CLI_COMPONENT_DIR}/include" "${CRUX_ACCESS_COMPONENT_DIR}/include")
target_link_libraries(crux_cli_api INTERFACE crux::base)
target_compile_options(crux_cli_api INTERFACE ${TOOLCHAIN_C_FLAGS})

add_library(crux_cli_adapter INTERFACE)
target_include_directories(crux_cli_adapter INTERFACE
    "${CRUX_CLI_COMPONENT_DIR}/adapter" "${CRUX_ACCESS_COMPONENT_DIR}/adapter")
target_link_libraries(crux_cli_adapter INTERFACE crux_cli_api)
target_compile_definitions(crux_cli_adapter INTERFACE
    CRUX_CLI_LINE_MAX=${CONFIG_CRUX_CLI_LINE_MAX}
    CRUX_CLI_TOKENS_MAX=${CONFIG_CRUX_CLI_TOKENS_MAX})

add_library(crux_cli_zephyr STATIC
    ../../src/cli_commands.c
    ../../src/cli_input.c
    ../../src/cli_parse.c
    ../../src/cli_registry.c
    ../../src/cli_session.c
    ../../console/cli_console.c
    ../../console/cli_console_serial.c
    cli_shell_rule.c
)
target_include_directories(crux_cli_zephyr PRIVATE ../../src ../../console)
target_link_libraries(crux_cli_zephyr PRIVATE crux_cli_adapter crux::serial crux::thread zephyr_interface)
target_compile_options(crux_cli_zephyr PRIVATE -Wall -Wextra -Werror)
if(CONFIG_CRUX_CLI_CONSOLE)
    # The start places its thread (ADR-0002 P3), and the event port is provided over the security events
    # that CONFIG_CRUX_ACCESS selects.
    target_sources(crux_cli_zephyr PRIVATE
        cli_serial_start.c
        ../../src/cli_security_events.c
    )
    target_include_directories(crux_cli_zephyr PRIVATE "${CRUX_CLI_COMPONENT_DIR}/ports/zephyr/include")
    target_link_libraries(crux_cli_zephyr PRIVATE crux::security_event crux_service_priority_placement)
    zephyr_append_cmake_library(crux_cli_zephyr)
endif()

add_library(crux_cli INTERFACE)
add_library(crux::cli ALIAS crux_cli)
target_link_libraries(crux_cli INTERFACE crux_cli_api)
cmake_language(DEFER CALL crux_assert_portable_usage crux::cli)

# The composition interface of the serial console start (ADR-0004 phase 1b, Experimental): the header
# <crux/cli_zephyr.h>, under ports/zephyr/include/crux/, and the portable CLI target. The name differs from
# the STATIC provider library crux_cli_zephyr above, which this target does not link (rule 2 of
# docs/composition-interfaces.md). A native-free consumer check rejects it by name and by path (rule 3), and
# tests/build/test_cli_zephyr_boundary.py shows that.
function(crux_cli_zephyr_composition)
  add_library(crux_cli_zephyr_composition INTERFACE)
  add_library(crux::cli_zephyr ALIAS crux_cli_zephyr_composition)
  target_include_directories(crux_cli_zephyr_composition INTERFACE "${CRUX_CLI_COMPONENT_DIR}/ports/zephyr/include")
  target_link_libraries(crux_cli_zephyr_composition INTERFACE crux_cli)
endfunction()
if(CONFIG_CRUX_CLI_CONSOLE)
  crux_cli_zephyr_composition()
endif()
