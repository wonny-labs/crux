# The static half of the per-service priority checks (ADR-0002 P3). The kernel half, which reads the
# priorities back on native_sim, is tests/service_priority/zephyr.
find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_test(NAME ServicePriority.Placement
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/check_placement.py --root ${PROJECT_SOURCE_DIR})
add_test(NAME ServicePriority.PlacementCheckCatchesDefects
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/test_check_placement.py)
set_tests_properties(ServicePriority.Placement ServicePriority.PlacementCheckCatchesDefects
    PROPERTIES TIMEOUT 30)

# The progress hook of the service threads (<crux/service_priority_zephyr.h>), which is portable C11:
# registration, reports and reports while the registration lands. The native_sim half is in
# tests/service_priority/zephyr.
find_package(Threads REQUIRED)
add_executable(service_progress_test progress.c
    ${PROJECT_SOURCE_DIR}/components/service_priority/src/service_progress.c)
target_include_directories(service_progress_test PRIVATE
    ${PROJECT_SOURCE_DIR}/components/service_priority/src
    ${PROJECT_SOURCE_DIR}/components/service_priority/ports/zephyr/include)
target_compile_definitions(service_progress_test PRIVATE CRUX_SERVICE_PROGRESS_TESTING=1)
target_link_libraries(service_progress_test PRIVATE crux::base Threads::Threads)
target_compile_options(service_progress_test PRIVATE -Wall -Wextra -Wpedantic -Werror -UNDEBUG)
add_test(NAME ServicePriority.Progress COMMAND service_progress_test)
set_tests_properties(ServicePriority.Progress PROPERTIES TIMEOUT 60)
