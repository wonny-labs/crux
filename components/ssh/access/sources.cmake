# Owned by #192. The Host build and the Zephyr composition both read this list.
set(CRUX_SSH_ACCESS_SOURCES "${CMAKE_CURRENT_LIST_DIR}/crux_ssh_access.c")
# Include directories the Zephyr composition adds for these sources.
get_filename_component(_crux_ssh_repository "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
set(CRUX_SSH_ACCESS_INCLUDES
    "${CMAKE_CURRENT_LIST_DIR}" "${_crux_ssh_repository}/components/access/adapter")
# A composition with a credential store adds this source and these directories.
set(CRUX_SSH_HOST_KEY_SOURCES "${CMAKE_CURRENT_LIST_DIR}/crux_ssh_host_key.c")
set(CRUX_SSH_HOST_KEY_INCLUDES
    "${CMAKE_CURRENT_LIST_DIR}" "${_crux_ssh_repository}/components/credential/adapter"
    "${_crux_ssh_repository}/components/credential/include")
# The provider of the adapter's event port, which every image that links the entry points above also links,
# once. A composition that has the security event core sets CRUX_SSH_ACCESS_SECURITY_EVENTS before including
# this file, and its reports are then recorded as ssh.auth_limit and ssh.host_key_missing. Without it a
# report is dropped, so that an image with no event core, such as the settings probe, links with none. The
# Zephyr composition sets it for CONFIG_CRUX_SSH: see ports/zephyr/wolf_ssh_settings.cmake. The Host tests
# link their own recording provider, so the Host library below holds neither.
if(CRUX_SSH_ACCESS_SECURITY_EVENTS)
    set(CRUX_SSH_ACCESS_EVENT_SOURCES "${CMAKE_CURRENT_LIST_DIR}/crux_ssh_security_events.c")
    set(CRUX_SSH_ACCESS_EVENT_INCLUDES "${_crux_ssh_repository}/components/security_event/include")
else()
    set(CRUX_SSH_ACCESS_EVENT_SOURCES "${CMAKE_CURRENT_LIST_DIR}/crux_ssh_access_events_none.c")
    set(CRUX_SSH_ACCESS_EVENT_INCLUDES "")
endif()
