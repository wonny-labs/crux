cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_m3_composition_tests LANGUAGES C)
target_sources(app PRIVATE src/main.c src/network_request.c ../time_periodic/core/health.c)
target_include_directories(app PRIVATE ../time_periodic/include
    ../board_images/integration_probe ../../components/base/include ../../components/time/include)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
