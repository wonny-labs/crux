# The update agent on the Host: the checks and staging path, the transition table, and the
# power-interruption table, over the Host fakes of the ports and the image state contract's Host
# double; the usage-target checks and the boundary check. The fakes, the double and the private
# ports are named only by the test targets that need them. Every executable fails closed.
set(UPDATE_AGENT_DIR ${CMAKE_CURRENT_LIST_DIR}/../../components/update_agent)
set(UPDATE_AGENT_IMAGE_STATE_DIR ${CMAKE_CURRENT_LIST_DIR}/../../components/image_state)
include(${CMAKE_CURRENT_LIST_DIR}/../../cmake/CruxConsumerBoundary.cmake)
find_package(Threads REQUIRED)

add_library(update_agent_test_medium STATIC harness.c medium.c
    $<TARGET_OBJECTS:crux_image_state_host>)
target_include_directories(update_agent_test_medium PUBLIC ${CMAKE_CURRENT_LIST_DIR}
    ${UPDATE_AGENT_DIR}/src ${UPDATE_AGENT_IMAGE_STATE_DIR}/src
    ${UPDATE_AGENT_IMAGE_STATE_DIR}/ports/host)
target_link_libraries(update_agent_test_medium PUBLIC crux::update_agent)
target_compile_options(update_agent_test_medium PRIVATE -Wall -Wextra -Wpedantic -Werror)

foreach(suite IN ITEMS gates table power_cut)
    add_executable(update_agent_${suite} test_${suite}.c)
    target_link_libraries(update_agent_${suite} PRIVATE update_agent_test_medium Threads::Threads)
    target_compile_options(update_agent_${suite} PRIVATE -Wall -Wextra -Wpedantic -Werror)
    add_test(NAME UpdateAgent.${suite} COMMAND update_agent_${suite})
endforeach()
set_tests_properties(UpdateAgent.gates UpdateAgent.table UpdateAgent.power_cut PROPERTIES
    TIMEOUT 60)

# Usage target: a C and a C++17 consumer name crux::update_agent alone, and the build asserts that
# the target carries no native include directory, definition or link requirement.
add_library(update_agent_consumer_c OBJECT consumer.c)
add_library(update_agent_consumer_cpp OBJECT consumer.cpp)
foreach(consumer IN ITEMS update_agent_consumer_c update_agent_consumer_cpp)
    target_link_libraries(${consumer} PRIVATE crux::update_agent)
    target_compile_options(${consumer} PRIVATE -Wall -Wextra -Wpedantic -Werror)
    crux_assert_portable_consumer(${consumer})
endforeach()
set_target_properties(update_agent_consumer_cpp PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF)

# A result that is ignored must warn. The probe is not a CMake target, so that no compile database
# names it: the test runs the compiler on it directly and expects that to fail.
add_test(NAME UpdateAgent.nodiscard
    COMMAND ${CMAKE_COMMAND} -DC_COMPILER=${CMAKE_C_COMPILER}
        -DINCLUDE_DIR=${UPDATE_AGENT_DIR}/include
        -DIMAGE_STATE_INCLUDE_DIR=${UPDATE_AGENT_IMAGE_STATE_DIR}/include
        -DPROBE=${CMAKE_CURRENT_LIST_DIR}/probe/nodiscard_probe.c
        -P ${CMAKE_CURRENT_LIST_DIR}/check_nodiscard.cmake)
set_tests_properties(UpdateAgent.nodiscard PROPERTIES TIMEOUT 60)

add_test(NAME UpdateAgent.boundary
    COMMAND ${CMAKE_COMMAND} -DCOMPONENT_DIR=${UPDATE_AGENT_DIR}
        -P ${CMAKE_CURRENT_LIST_DIR}/check_boundary.cmake)
set_tests_properties(UpdateAgent.boundary PROPERTIES TIMEOUT 20)
