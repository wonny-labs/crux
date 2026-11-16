# SPDX-License-Identifier: Apache-2.0

# A named library. Zephyr derives the name of an unnamed zephyr_library() from the path of this
# folder relative to ZEPHYR_BASE, so the name depends on where the module is checked out, is long,
# and changes with the workspace layout; it also appears in build output and link errors. Give each
# driver library a fixed name that starts with the product's.
zephyr_library_named(product_example_temp)
zephyr_library_sources(example_temp.c)
zephyr_library_sources_ifdef(CONFIG_EMUL_EXAMPLE_TEMP example_temp_emul.c)
# Owned code uses the repository warning policy, privately: the flags do not reach Zephyr.
zephyr_library_compile_options(-Wall -Wextra -Werror)
