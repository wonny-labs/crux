# SPDX-License-Identifier: Apache-2.0

# Zephyr includes this file when the module is part of a build (build.cmake in zephyr/module.yml).
# It adds the product's drivers. Applications and tests are separate projects with their own
# CMakeLists.txt.
add_subdirectory(drivers)
