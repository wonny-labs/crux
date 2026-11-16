# SPDX-License-Identifier: Apache-2.0
#
# Entry point of the acme-hw module for the Zephyr build. Boards need no
# CMake here: board_root in zephyr/module.yml makes them visible.

add_subdirectory(drivers)
