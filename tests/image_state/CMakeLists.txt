# The image state contract on the Host: the pure functions, the service over the Host double, the
# end-to-end scenarios over the double's hand model of the bootloader, the usage-target checks and
# the boundary check. The Host double and the private port are named only by the test targets that
# need them. Every executable fails closed: a failing check exits non-zero and prints its case.
set(IMAGE_STATE_DIR ${CMAKE_CURRENT_LIST_DIR}/../../components/image_state)
include(${CMAKE_CURRENT_LIST_DIR}/../../cmake/CruxConsumerBoundary.cmake)

add_library(image_state_test_harness STATIC harness.c)
target_compile_options(image_state_test_harness PRIVATE -Wall -Wextra -Wpedantic -Werror)

# The pure functions need no provider.
add_executable(image_state_pure test_pure.c)
target_link_libraries(image_state_pure PRIVATE crux::image_state image_state_test_harness)
target_compile_options(image_state_pure PRIVATE -Wall -Wextra -Wpedantic -Werror)
add_test(NAME ImageState.pure COMMAND image_state_pure)

foreach(suite IN ITEMS provider scenarios)
    add_executable(image_state_${suite} test_${suite}.c $<TARGET_OBJECTS:crux_image_state_host>)
    target_include_directories(image_state_${suite} PRIVATE ${IMAGE_STATE_DIR}/src
        ${IMAGE_STATE_DIR}/ports/host)
    target_link_libraries(image_state_${suite} PRIVATE crux::image_state image_state_test_harness)
    target_compile_options(image_state_${suite} PRIVATE -Wall -Wextra -Wpedantic -Werror)
    add_test(NAME ImageState.${suite} COMMAND image_state_${suite})
endforeach()
set_tests_properties(ImageState.pure ImageState.provider ImageState.scenarios PROPERTIES TIMEOUT 20)

# Usage target: a C and a C++17 consumer name crux::image_state alone, and the build asserts that
# the target carries no native include directory, definition or link requirement.
add_library(image_state_consumer_c OBJECT consumer.c)
add_library(image_state_consumer_cpp OBJECT consumer.cpp)
foreach(consumer IN ITEMS image_state_consumer_c image_state_consumer_cpp)
    target_link_libraries(${consumer} PRIVATE crux::image_state)
    target_compile_options(${consumer} PRIVATE -Wall -Wextra -Wpedantic -Werror)
    crux_assert_portable_consumer(${consumer})
endforeach()
set_target_properties(image_state_consumer_cpp PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON
    CXX_EXTENSIONS OFF)

# A result that is ignored must warn. The first object uses every result and builds. The probe
# ignores one, is left out of the normal build, and the test builds it with the warning as an error
# and expects the attribute to be named.
add_library(image_state_nodiscard_probe OBJECT EXCLUDE_FROM_ALL probe/nodiscard_probe.c)
target_link_libraries(image_state_nodiscard_probe PRIVATE crux::image_state)
target_compile_options(image_state_nodiscard_probe PRIVATE -Werror=unused-result)
add_test(NAME ImageState.nodiscard
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target image_state_nodiscard_probe)
set_tests_properties(ImageState.nodiscard PROPERTIES PASS_REGULAR_EXPRESSION "warn_unused_result"
    TIMEOUT 120)

add_test(NAME ImageState.boundary
    COMMAND ${CMAKE_COMMAND} -DCOMPONENT_DIR=${IMAGE_STATE_DIR} -P ${CMAKE_CURRENT_LIST_DIR}/check_boundary.cmake)
set_tests_properties(ImageState.boundary PROPERTIES TIMEOUT 20)
