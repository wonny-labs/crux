# SPDX-License-Identifier: Apache-2.0

# A link probe for the product template, not a product example. The same adapter, which calls
# kernel message queue functions, is linked in one of three ways (PROBE_VARIANT):
#   app_sources     a source of the app target
#   plain_static    a plain CMake STATIC library that app links (expected to fail to link)
#   module_library  a zephyr_library_named library of a Zephyr module (module/)
# scripts/test-product-template.sh builds each variant for native_sim and checks the outcome.
cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(product_template_link)

set(PROBE_VARIANT "app_sources" CACHE STRING "app_sources, plain_static or module_library")
set_property(CACHE PROBE_VARIANT PROPERTY STRINGS app_sources plain_static module_library)

target_sources(app PRIVATE src/main.c)
target_include_directories(app PRIVATE src)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)

if(PROBE_VARIANT STREQUAL "app_sources")
  target_sources(app PRIVATE src/queue_adapter.c)
elseif(PROBE_VARIANT STREQUAL "plain_static")
  add_library(probe_queue_adapter STATIC src/queue_adapter.c)
  target_link_libraries(probe_queue_adapter PUBLIC zephyr_interface)
  target_compile_options(probe_queue_adapter PRIVATE -Wall -Wextra -Werror)
  target_link_libraries(app PRIVATE probe_queue_adapter)
elseif(PROBE_VARIANT STREQUAL "module_library")
  # module/CMakeLists.txt builds the adapter when the module is named with ZEPHYR_EXTRA_MODULES.
  if(NOT TARGET probe_queue_module)
    message(FATAL_ERROR "module_library needs -DZEPHYR_EXTRA_MODULES=<this folder>/module")
  endif()
else()
  message(FATAL_ERROR "Unknown PROBE_VARIANT: ${PROBE_VARIANT}")
endif()
