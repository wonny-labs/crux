# The update agent: the transition table of the update agent design proposal (rows U1 to U6), its
# checks and its staging path. The core is portable C over private ports (src/update_agent_port.h)
# for the staging slot, the attempt record, the digest and signature check and a progress hook, and
# over the public image state contract. No provider is linked here: a composition links one of each.
# The Host fakes live with the tests (tests/update_agent).
if(NOT TARGET crux_image_state_api)
    message(FATAL_ERROR "CRUX_BUILD_UPDATE_AGENT needs CRUX_BUILD_IMAGE_STATE")
endif()

add_library(crux_update_agent_api INTERFACE)
target_include_directories(crux_update_agent_api INTERFACE include)
target_link_libraries(crux_update_agent_api INTERFACE crux_image_state_api)

add_library(crux_update_agent_core STATIC src/update_agent.c src/update_agent_image.c)
target_include_directories(crux_update_agent_core PRIVATE src)
target_link_libraries(crux_update_agent_core PUBLIC crux_update_agent_api crux_image_state_core)
target_compile_options(crux_update_agent_core PRIVATE -Wall -Wextra -Wpedantic -Werror)

add_library(crux_update_agent INTERFACE)
add_library(crux::update_agent ALIAS crux_update_agent)
target_link_libraries(crux_update_agent INTERFACE crux_update_agent_api crux_update_agent_core
    crux::image_state)
