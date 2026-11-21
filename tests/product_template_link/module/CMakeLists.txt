# SPDX-License-Identifier: Apache-2.0

# A Zephyr library of a module, as the product template's drivers are. Zephyr links module
# libraries inside --whole-archive, before the kernel archive.
if(PROBE_VARIANT STREQUAL "module_library")
  zephyr_library_named(probe_queue_module)
  zephyr_library_sources(../src/queue_adapter.c)
  zephyr_library_compile_options(-Wall -Wextra -Werror)
endif()
