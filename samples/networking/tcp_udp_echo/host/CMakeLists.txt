add_executable(crux-networking-host main.c ../common/client.c)
target_include_directories(crux-networking-host PRIVATE ../common)
target_link_libraries(crux-networking-host PRIVATE crux::sockets crux::netif)
target_compile_options(crux-networking-host PRIVATE -Wall -Wextra -Wpedantic -Werror)
if(BUILD_TESTING)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    # The driver serves the TCP and UDP echo peer that the sample talks to on 127.0.0.1.
    add_test(NAME Sample.TcpUdpEchoHost
        COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/scripts/run-host-sample.py
                $<TARGET_FILE:crux-networking-host> --echo-peer
                "--expect=^NETIF admin=[01] link=-?[0-9]+ address=[01]$"
                "--expect=^NETWORK tcp=0 udp=0$")
    # The echo peer binds fixed ports, so this test never runs alongside another user of them.
    set_tests_properties(Sample.TcpUdpEchoHost PROPERTIES LABELS sample TIMEOUT 15
        RESOURCE_LOCK crux_sample_echo_ports)
endif()
