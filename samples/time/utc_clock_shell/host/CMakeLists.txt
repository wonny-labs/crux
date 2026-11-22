add_executable(crux-time-host main.c)
target_link_libraries(crux-time-host PRIVATE crux_time_commands crux::time)
target_compile_options(crux-time-host PRIVATE -Wall -Wextra -Wpedantic -Werror)
if(BUILD_TESTING)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    # `ctest -L sample` runs every Linux Host sample once and checks its output.
    add_test(NAME Sample.UtcClockShellHost
        COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/scripts/run-host-sample.py
                $<TARGET_FILE:crux-time-host>
                "--input=time get\ntime set 2026-10-16T14:30:00\ntime get\n"
                "--expect=^CRUX_TIME_READY composition=host-simulation$"
                "--expect=^ERR NOT_SET$"
                "--expect=^OK$"
                "--expect=^2026-10-16T14:30:00 UTC$")
    set_tests_properties(Sample.UtcClockShellHost PROPERTIES LABELS sample TIMEOUT 15)
endif()
