# Application under the boot-composition checks. The scripts name this folder, and its basename `zephyr` is the
# sysbuild image name that `scripts/check-boot-config.py` and the boot-image checks expect. The scenario is the one
# of tests/time_periodic, compiled from there so the two do not drift.
cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_boot_fixture LANGUAGES C)
set(scenario "${CMAKE_CURRENT_LIST_DIR}/../../time_periodic")
target_sources(app PRIVATE "${scenario}/core/controller.c" "${scenario}/zephyr/main.c")
target_include_directories(app PRIVATE "${scenario}/include")
target_link_libraries(app PRIVATE crux::time)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
