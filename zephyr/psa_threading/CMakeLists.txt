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
