# SPDX-License-Identifier: Apache-2.0

# One folder for each Zephyr driver class, as in Zephyr's own drivers/ folder.
add_subdirectory_ifdef(CONFIG_SENSOR sensor)
