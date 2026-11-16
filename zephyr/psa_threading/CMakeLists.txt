# The locks of TF-PSA-Crypto's core on the Mbed profile (CONFIG_CRUX_PSA_THREADING, Experimental).
# The module's CMake adds this directory only under that symbol. The directory is on the global
# include path because the Mbed TLS build includes crux_tf_psa_user_config.h and threading_alt.h
# from it. The library is registered with the Zephyr link, which links Zephyr libraries as whole
# archives, so the SYS_INIT entry of the locks is kept although nothing references it.
if(NOT CONFIG_CRUX_PSA_THREADING)
  message(FATAL_ERROR "This directory is the locks selection of the module: set CONFIG_CRUX_PSA_THREADING")
endif()

zephyr_library_named(crux_psa_threading)
zephyr_library_sources(crux_tf_psa_threading.c)
zephyr_include_directories(${CMAKE_CURRENT_LIST_DIR})
target_compile_options(crux_psa_threading PRIVATE -Wall -Wextra -Werror)

# The lock counter exists for two native_sim test fixtures (the management composition and the management
# module fixture), which set CRUX_PSA_THREADING_TEST_COUNTER before find_package(Zephyr).
# It is refused on any other board, so a product image never has it, and its header is not in this directory.
if(CRUX_PSA_THREADING_TEST_COUNTER)
  if(NOT CONFIG_BOARD_NATIVE_SIM)
    message(FATAL_ERROR "CRUX_PSA_THREADING_TEST_COUNTER is a native_sim test fixture setting "
                        "and is refused on any other board")
  endif()
  target_compile_definitions(crux_psa_threading PRIVATE CRUX_PSA_THREADING_TEST_COUNTER)
endif()
