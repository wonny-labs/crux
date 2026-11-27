cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_controller_native_tests LANGUAGES C)
if(NOT CT_GPIO_SCENARIO MATCHES "^(emulated|missing|fault)$")
    message(FATAL_ERROR "Select an explicit CT_GPIO_SCENARIO")
endif()
target_compile_definitions(app PRIVATE
    CT_EXPECT_MISSING=$<STREQUAL:${CT_GPIO_SCENARIO},missing>
    CT_EXPECT_READ_ERROR=$<STREQUAL:${CT_GPIO_SCENARIO},fault>)
target_sources(app PRIVATE src/main.c src/fault_gpio.c
    ../time_periodic/core/health.c
    ../board_images/integration_probe/device_input.c)
target_include_directories(app PRIVATE ../time_periodic/include
    ../board_images/integration_probe .)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
