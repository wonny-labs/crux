# Owned by #192. Its tests go here, so it has no need to change tests/ssh/CMakeLists.txt.

# The entry points call crux_access, which needs a provider. Every test that links them, such as the
# callback table's, gets the test composition. This runs only when Crux builds its own tests.
target_link_libraries(crux_ssh_access INTERFACE crux_access_test_composition crux_ssh_port_fake)

# A recording provider of the adapter's event port. Every Host test that links the adapter or the host
# key gets it, since the adapter's reports need a provider, and the tests read what was reported.
add_library(crux_ssh_port_fake STATIC ssh_port_fake.c)
target_include_directories(crux_ssh_port_fake PUBLIC . ../../../components/ssh/access)
target_compile_options(crux_ssh_port_fake PRIVATE -Wall -Wextra -Wpedantic -Werror)
target_compile_features(crux_ssh_port_fake PRIVATE c_std_17)

add_executable(ssh_access_adapter_test adapter_test.c)
target_link_libraries(ssh_access_adapter_test PRIVATE crux_ssh_access crux_ssh_adapter)
target_include_directories(ssh_access_adapter_test PRIVATE .. ../../../components/ssh/access)
target_compile_options(ssh_access_adapter_test PRIVATE -Wall -Wextra -Wpedantic -Werror -UNDEBUG)
target_compile_features(ssh_access_adapter_test PRIVATE c_std_17)
add_test(NAME Ssh.access_adapter COMMAND ssh_access_adapter_test)

add_executable(ssh_host_key_test host_key_test.c ../../credential/medium_fake.c)
target_link_libraries(ssh_host_key_test PRIVATE crux_ssh_host_key crux_ssh_provider
    crux_credential_test_composition crux_file_fake crux_ssh_port_fake)
target_include_directories(ssh_host_key_test PRIVATE .. ../../../components/ssh/access)
target_compile_options(ssh_host_key_test PRIVATE -Wall -Wextra -Wpedantic -Werror -UNDEBUG)
target_compile_features(ssh_host_key_test PRIVATE c_std_17)
add_test(NAME Ssh.host_key COMMAND ssh_host_key_test)
set_tests_properties(Ssh.access_adapter Ssh.host_key PROPERTIES TIMEOUT 30)

# The real provider of the event port on the recording fake of the event contract. It compiles the adapter's
# own source rather than linking crux_ssh_access, which would bring in the recording port of the tests above
# as a second provider.
if(TARGET crux_ssh_security_events AND TARGET crux_security_event_fake)
    add_executable(ssh_security_events_test security_events_test.c
        ../../../components/ssh/access/crux_ssh_access.c $<TARGET_OBJECTS:crux_ssh_security_events>)
    target_link_libraries(ssh_security_events_test PRIVATE crux_ssh_adapter crux_access_test_composition
        crux_security_event_fake)
    target_include_directories(ssh_security_events_test PRIVATE .. ../../../components/ssh/access
        ../../../components/ssh/src)
    target_compile_options(ssh_security_events_test PRIVATE -Wall -Wextra -Wpedantic -Werror -UNDEBUG)
    target_compile_features(ssh_security_events_test PRIVATE c_std_17)
    add_test(NAME Ssh.security_events COMMAND ssh_security_events_test)
    set_tests_properties(Ssh.security_events PROPERTIES TIMEOUT 30)
else()
    message(WARNING "Ssh.security_events is not built: the security event component or its fake is missing")
endif()


add_test(NAME Ssh.ProviderTypes
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/check_provider_types.py
            --root ${PROJECT_SOURCE_DIR})
add_test(NAME Ssh.ProviderTypesControl
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/check_provider_types_test.py
            --root ${PROJECT_SOURCE_DIR})
set_tests_properties(Ssh.ProviderTypes Ssh.ProviderTypesControl PROPERTIES TIMEOUT 30)
