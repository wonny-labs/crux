# Private implementation, like components/interrupt, except for one composition interface at the end. Zephyr
# only: the Crux module adds this directory, and the Linux Host builds nothing here.
#
# crux_service_priority_placement carries the private include directory and
# CRUX_SERVICE_PRIORITY_PLACEMENT. A composition or test that compiles one of the services' worker
# sources links it to the target that compiles them, so that the worker places itself at its
# CONFIG_CRUX_<SERVICE>_<ROLE>_PRIORITY (ADR-0002 P3). tests/service_priority/check_placement.py fails
# a Zephyr CMake file that lists a worker source without it. The services' Host builds call nothing.
#
# Under the same definition each worker reports the progress of its loop (crux_service_progress_report),
# and the composition interface crux::service_priority_zephyr publishes the thread identifiers and the
# registration of the product's progress function (<crux/service_priority_zephyr.h>, Experimental).
add_library(crux_service_priority_placement INTERFACE)
target_include_directories(crux_service_priority_placement INTERFACE "${CMAKE_CURRENT_LIST_DIR}/src"
    "${CMAKE_CURRENT_LIST_DIR}/ports/zephyr/include")
target_compile_definitions(crux_service_priority_placement INTERFACE CRUX_SERVICE_PRIORITY_PLACEMENT=1)
target_link_libraries(crux_service_priority_placement INTERFACE crux::base)

# The placement itself needs Crux Thread's Kconfig, as only Thread workers call it. A compile-only
# check of the sources without Thread links the interface above and no implementation.
if(CONFIG_CRUX_THREAD)
    add_library(crux_service_priority STATIC ports/zephyr/service_priority_zephyr.c src/service_progress.c)
    target_include_directories(crux_service_priority PRIVATE src ports/zephyr/include)
    target_link_libraries(crux_service_priority PRIVATE crux::base zephyr_interface)
    zephyr_append_cmake_library(crux_service_priority)
    target_compile_options(crux_service_priority PRIVATE -Wall -Wextra -Werror)
endif()

# The composition interface (rules of docs/composition-interfaces.md): an INTERFACE target that adds the
# header's include root and links Base, whose <crux/status.h> the header uses; Service priority has no
# portable target. It does not link the provider above, which the module appends to the link. A
# native-free consumer check rejects it by name and by path, as
# tests/build/test_service_priority_zephyr_boundary.py shows.
function(crux_service_priority_zephyr_composition)
  add_library(crux_service_priority_zephyr_composition INTERFACE)
  add_library(crux::service_priority_zephyr ALIAS crux_service_priority_zephyr_composition)
  target_include_directories(crux_service_priority_zephyr_composition INTERFACE
      "${CRUX_SERVICE_PRIORITY_COMPONENT_DIR}/ports/zephyr/include")
  target_link_libraries(crux_service_priority_zephyr_composition INTERFACE crux::base)
endfunction()
if(CONFIG_CRUX_THREAD)
  set(CRUX_SERVICE_PRIORITY_COMPONENT_DIR "${CMAKE_CURRENT_LIST_DIR}")
  crux_service_priority_zephyr_composition()
endif()
