# Owned by #192.
include(sources.cmake)
add_library(crux_ssh_access STATIC ${CRUX_SSH_ACCESS_SOURCES})
target_link_libraries(crux_ssh_access PRIVATE crux_ssh_adapter crux_access_adapter)
target_compile_options(crux_ssh_access PRIVATE -Wall -Wextra -Wpedantic -Werror)

# Apart from the entry points, so that an image can log in with no credential store in it.
add_library(crux_ssh_host_key STATIC ${CRUX_SSH_HOST_KEY_SOURCES})
target_include_directories(crux_ssh_host_key PUBLIC .)
target_link_libraries(crux_ssh_host_key PUBLIC crux_ssh_provider PRIVATE crux_credential_adapter)
target_compile_options(crux_ssh_host_key PRIVATE -Wall -Wextra -Wpedantic -Werror)

# The provider of crux_ssh_access_port_event over the security events, which a composition links by name.
# An object target, so that a final link always takes it, and a second provider of the port is a duplicate
# symbol. It is absent in a build with no security event component.
if(TARGET crux_security_event_api)
    add_library(crux_ssh_security_events OBJECT crux_ssh_security_events.c)
    target_include_directories(crux_ssh_security_events PRIVATE .)
    target_link_libraries(crux_ssh_security_events PRIVATE crux_security_event_api)
    target_compile_options(crux_ssh_security_events PRIVATE -Wall -Wextra -Wpedantic -Werror)
    target_compile_features(crux_ssh_security_events PRIVATE c_std_17)
endif()
