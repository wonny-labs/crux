# SPDX-License-Identifier: Apache-2.0

# A named library. Zephyr derives the name of an unnamed zephyr_library() from the path of this
# folder, which clashes when two modules hold a folder of the same name, and the name appears in
# link errors. Give each driver library a name of its own that starts with the product's.
zephyr_library_named(product_example_temp)
zephyr_library_sources(example_temp.c)
zephyr_library_sources_ifdef(CONFIG_EMUL_EXAMPLE_TEMP example_temp_emul.c)
