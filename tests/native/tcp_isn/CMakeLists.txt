cmake_minimum_required(VERSION 3.20.0)
# A native_sim application for the fail-closed TCP initial sequence number of default images
# (patches/zephyr/tcp-isn-fail-closed.patch). The same source runs with the Crux module, which replaces
# tcp.c, and without it, on upstream tcp.c (the negative control). The provider of the hash is
# TF-PSA-Crypto through Zephyr's Mbed TLS module, as in tests/psa_entropy/zephyr.
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(crux_tcp_isn C)
target_sources(app PRIVATE src/main.c src/test_entropy.c)
# The test builds and reads TCP packets with the stack's own helpers, which are internal headers of
# subsys/net/ip, as Zephyr's tests/net/tcp does.
target_include_directories(app PRIVATE ${ZEPHYR_BASE}/subsys/net/ip)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
# A hash failure is injected at the one PSA call that tcp.c makes for its sequence number. The wrap
# applies to the partial link of the native_sim image, where tcp.c and the PSA library meet.
zephyr_ld_options(-Wl,--wrap=psa_hash_compute)
