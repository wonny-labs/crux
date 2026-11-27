add_executable(crux-time-host main.c)
target_link_libraries(crux-time-host PRIVATE crux_time_commands crux::time)
target_compile_options(crux-time-host PRIVATE -Wall -Wextra -Wpedantic -Werror)
# `cmake --build --preset host-debug --target run_time_shell` builds the sample and runs it with
# the terminal as its console, like `west build -t run` on native_sim. The clock is controlled:
# it starts unset and does not advance by itself.
add_custom_target(run_time_shell COMMAND crux-time-host USES_TERMINAL)
if(BUILD_TESTING)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    # `ctest -L sample` runs every Linux Host sample once and checks its output.
    add_test(NAME Sample.TimeShellHost
        COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/scripts/run-host-sample.py
                $<TARGET_FILE:crux-time-host>
                "--input=time get\ntime set 2026-10-16T14:30:00\ntime get\n"
                "--expect=^CRUX_TIME_READY composition=host-simulation$"
                "--expect=^ERR NOT_SET$"
                "--expect=^OK$"
                "--expect=^2026-10-16T14:30:00 UTC$")
    set_tests_properties(Sample.TimeShellHost PROPERTIES LABELS sample TIMEOUT 15)
endif()
