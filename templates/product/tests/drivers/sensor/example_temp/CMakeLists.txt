# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(example_temp_test)

# The register map and the emulator's test controls are private to the driver's folder. The module
# name in zephyr/module.yml gives the variable.
target_include_directories(app PRIVATE ${ZEPHYR_PRODUCT_X_MODULE_DIR}/drivers/sensor/example_temp)

# One test application, two scenarios (see testcase.yaml). The emulator exists only on native_sim,
# where boards/native_sim.conf turns it on. On a board the same node is the real part.
target_sources_ifdef(CONFIG_EMUL app PRIVATE src/emul_test.c)
target_sources_ifndef(CONFIG_EMUL app PRIVATE src/hardware_test.c)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
