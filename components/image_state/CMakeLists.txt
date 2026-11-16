# The image state contract: the state of two firmware image slots, a test request and a confirm. The
# core is portable C over a private port (src/image_state_port.h) for the medium, so that no
# bootloader type reaches the public header. No provider is linked here, so that an image links one
# only when a composition chooses it. The Host double in ports/host is a test double that exists
# only when Crux builds its own tests.
add_library(crux_image_state_api INTERFACE)
target_include_directories(crux_image_state_api INTERFACE include)

set(CRUX_IMAGE_STATE_SOURCES src/image_state.c src/image_state_pure.c src/image_state_slot.c)
list(TRANSFORM CRUX_IMAGE_STATE_SOURCES PREPEND "${CMAKE_CURRENT_LIST_DIR}/")
set(CRUX_IMAGE_STATE_SOURCES "${CRUX_IMAGE_STATE_SOURCES}" CACHE INTERNAL "Portable image state sources")

add_library(crux_image_state_core STATIC ${CRUX_IMAGE_STATE_SOURCES})
target_include_directories(crux_image_state_core PRIVATE src)
target_link_libraries(crux_image_state_core PUBLIC crux_image_state_api)
target_compile_options(crux_image_state_core PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_library(crux_image_state INTERFACE)
add_library(crux::image_state ALIAS crux_image_state)
target_link_libraries(crux_image_state INTERFACE crux_image_state_api crux_image_state_core)

# The Host double. It is an object library that a test composition links by name, so that a second
# provider is a duplicate symbol. Its controls (ports/host/image_state_host.h) and the private port
# are private to it and to the targets that name these directories.
add_library(crux_image_state_host OBJECT ports/host/image_state_host.c)
target_include_directories(crux_image_state_host PRIVATE src ports/host)
target_link_libraries(crux_image_state_host PUBLIC crux_image_state_api)
target_compile_options(crux_image_state_host PRIVATE -Wall -Wextra -Wpedantic -Werror)
