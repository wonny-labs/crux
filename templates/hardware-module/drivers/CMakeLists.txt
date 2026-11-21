# SPDX-License-Identifier: Apache-2.0
#
# One block per shared driver. zephyr_library_named gives each library a
# stable name; zephyr_library() would derive one from this path. The first
# driver arrives from a product, as docs/shared-hardware-modules.md says, so
# until then the block below stays a comment and the module builds no library.
#
# if(CONFIG_ACMECO_EXAMPLE_SENSOR)
#   zephyr_library_named(acmeco_example_sensor)
#   zephyr_library_sources(sensor/acmeco_example_sensor/acmeco_example_sensor.c)
#   zephyr_library_sources_ifdef(CONFIG_EMUL
#     sensor/acmeco_example_sensor/acmeco_example_sensor_emul.c)
# endif()
