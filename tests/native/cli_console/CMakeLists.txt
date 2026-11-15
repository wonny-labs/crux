# SPDX-License-Identifier: Apache-2.0
# ADR-0004 phase 1b (Experimental): an application that starts the serial console with the first-account
# setup through the public composition interface <crux/cli_zephyr.h> and nothing private. It reaches Crux
# only through public targets (crux::access, crux::credential_store, crux::security_event, crux::cli,
# crux::cli_zephyr, crux::file_zephyr, crux::time) and includes no frozen header (<crux/serial.h>,
# <crux/thread.h>), no adapter header and no console header. The module builds the console and the event
# provider under CONFIG_CRUX_CLI_CONSOLE. The first account is NOT created in code: the test types `!setup`
# over an emulated UART, as a person would.
#
# Build it with the Mbed profile, as tests/native/cli_console/run.sh does:
#   -DEXTRA_CONF_FILE=../tls_offload_probe/mbed.conf;../management_composition/profile-psa.conf;../management_composition/mbed-threading.conf
#
# The TF-PSA-Crypto locks of the Mbed profile come from the module (CONFIG_CRUX_PSA_THREADING,
# Experimental), set by mbed-threading.conf above.
cmake_minimum_required(VERSION 3.20.0)
get_filename_component(CRUX_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
list(APPEND ZEPHYR_EXTRA_MODULES "${CRUX_ROOT}")
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_cli_console LANGUAGES C)

if(NOT CONFIG_BOARD_NATIVE_SIM OR NOT CONFIG_FAKE_ENTROPY_NATIVE_SIM)
    message(FATAL_ERROR "This fixture is restricted to native_sim: its entropy is test-only")
endif()
# An unsatisfied dependency only warns in Kconfig and would build an application without the console.
if(NOT CONFIG_CRUX_CLI_CONSOLE OR NOT CONFIG_CRUX_CLI OR NOT CONFIG_CRUX_ACCESS OR NOT CONFIG_CRUX_SERIAL)
    message(FATAL_ERROR "The fixture needs CONFIG_CRUX_CLI_CONSOLE, CONFIG_CRUX_CLI, CONFIG_CRUX_ACCESS and CONFIG_CRUX_SERIAL")
endif()
# The service symbol selects Thread, Sync and Time (ADR-0004 C6): the fixture names none of them.
file(READ "${CMAKE_CURRENT_LIST_DIR}/prj.conf" fixture_conf)
if(fixture_conf MATCHES "CONFIG_CRUX_(THREAD|SYNC|TIME)[A-Z_]*=")
    message(FATAL_ERROR "prj.conf must not name a CONFIG_CRUX_THREAD, CONFIG_CRUX_SYNC or CONFIG_CRUX_TIME symbol: the service symbol selects them")
endif()

# The locks of the Mbed profile's core come from the module (CONFIG_CRUX_PSA_THREADING, set by mbed-threading.conf).
target_sources(app PRIVATE src/main.c)
target_link_libraries(app PRIVATE crux::access crux::credential_store crux::security_event crux::cli
    crux::cli_zephyr crux::file_zephyr crux::time)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
