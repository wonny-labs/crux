# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})

project(basic C)

# The Kconfig selection of the File provider decides which composition file is compiled.
# The application source is the same for both.
if(CONFIG_CRUX_FILE_SIMULATOR)
    set(storage_source src/storage_littlefs.c)
elseif(CONFIG_CRUX_FILE_FATFS_SIMULATOR)
    set(storage_source src/storage_fatfs_ram_disk.c)
else()
    message(FATAL_ERROR "basic needs CONFIG_CRUX_FILE_SIMULATOR=y (prj.conf) or "
        "CONFIG_CRUX_FILE_FATFS_SIMULATOR=y (fatfs_ram_disk.conf)")
endif()

# The application part links the public File target only. The check fails the configure step
# if the target's build requirements (include directories, compile options, linked targets)
# name a native path, a private Crux directory or a provider target. It does not read
# #include lines.
add_library(basic_logic OBJECT src/basic.c)
target_link_libraries(basic_logic PRIVATE crux::file)
set_target_properties(basic_logic PROPERTIES
    C_STANDARD 17 C_STANDARD_REQUIRED ON C_EXTENSIONS OFF)
target_compile_options(basic_logic PRIVATE -Wall -Wextra -Werror)
crux_assert_portable_consumer(basic_logic)

# The composition part may use Zephyr and binds the File root through crux::file_zephyr, the
# composition target of the Zephyr File provider.
target_sources(app PRIVATE src/main.c ${storage_source}
    $<TARGET_OBJECTS:basic_logic>)
target_link_libraries(app PRIVATE crux::file crux::file_zephyr)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
