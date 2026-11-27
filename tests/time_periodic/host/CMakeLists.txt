add_executable(crux-time-periodic-host main.c)
target_link_libraries(crux-time-periodic-host PRIVATE crux_time_periodic_core crux::time)
target_compile_definitions(crux-time-periodic-host PRIVATE _POSIX_C_SOURCE=200809L)
target_compile_options(crux-time-periodic-host PRIVATE -Wall -Wextra -Wpedantic -Werror)
if(BUILD_TESTING)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_test(NAME TimePeriodic.HostScenario
        COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/scripts/check-time-periodic.py
                $<TARGET_FILE:crux-time-periodic-host>
                --log ${CMAKE_CURRENT_BINARY_DIR}/controller.log)
    set_tests_properties(TimePeriodic.HostScenario PROPERTIES LABELS scenario TIMEOUT 15)
endif()
