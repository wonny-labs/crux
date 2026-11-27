# SPDX-License-Identifier: Apache-2.0
# TEST ONLY: the password of the first account, for CONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT.
#
# The password is in a file that is NOT in the repository. The environment variable CRUX_MBED_MGMT_PASSWORD_FILE names
# it (its value is a path and is not stored in CMake's cache). The file is checked here and its bytes are embedded by an
# assembler `.incbin`, so the plaintext is in no generated source, header or configuration file: it is in the object
# that holds it, the archive, the ELF and the binary. Access takes a plaintext password and derives its own record, so
# there is no pre-derived form to embed. Make a file with:
#
#   umask 077; head -c 24 /dev/urandom | base64 | tr -d '\n' > <path outside every git work tree>
#
# The reason of a refusal says what is wrong with the file and never what is in it.

function(crux_mbed_mgmt_embed_password)
    set(path "$ENV{CRUX_MBED_MGMT_PASSWORD_FILE}")
    if("${path}" STREQUAL "")
        message(FATAL_ERROR "CONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT needs the environment variable "
                            "CRUX_MBED_MGMT_PASSWORD_FILE: the path of a file with the password, outside the repository")
    endif()
    if(NOT EXISTS "${path}" OR IS_DIRECTORY "${path}")
        message(FATAL_ERROR "CRUX_MBED_MGMT_PASSWORD_FILE does not name a file")
    endif()
    if("${path}" MATCHES "[\"\\\;\n]")
        message(FATAL_ERROR "CRUX_MBED_MGMT_PASSWORD_FILE has a character that this check does not allow in a path")
    endif()
    file(REAL_PATH "${path}" real)
    file(REAL_PATH "${CRUX_ROOT}" root)
    cmake_path(IS_PREFIX root "${real}" NORMALIZE inside)
    if(inside)
        message(FATAL_ERROR "The password file is inside the repository: keep it outside every git work tree")
    endif()
    cmake_path(GET real PARENT_PATH directory)
    find_program(git_program git)
    if(git_program)
        execute_process(COMMAND "${git_program}" -C "${directory}" rev-parse --is-inside-work-tree
                        RESULT_VARIABLE git_status OUTPUT_QUIET ERROR_QUIET)
        if(git_status EQUAL 0)
            message(FATAL_ERROR "The password file is inside a git work tree: keep it outside every one")
        endif()
    endif()
    file(READ "${real}" hex HEX)
    string(LENGTH "${hex}" hex_length)
    math(EXPR length "${hex_length} / 2")
    if(length LESS 16 OR length GREATER 128)
        message(FATAL_ERROR "The password file must hold 16 to 128 bytes, and it holds ${length}")
    endif()
    # Printable ASCII only: 0x20 to 0x7e. A trailing newline is not, so it is refused too.
    if(NOT "${hex}" MATCHES "^(([2-6][0-9a-f])|(7[0-9a-e]))+$")
        message(FATAL_ERROR "The password file must hold printable ASCII only, with no trailing newline")
    endif()

    set(text "")
    string(APPEND text "\t.section .rodata.crux_mbed_mgmt_test_password,\"a\",%progbits\n")
    string(APPEND text "\t.balign 4\n")
    string(APPEND text "\t.global crux_mbed_mgmt_test_password\n")
    string(APPEND text "\t.type crux_mbed_mgmt_test_password, %object\n")
    string(APPEND text "crux_mbed_mgmt_test_password:\n")
    string(APPEND text "\t.incbin \"${real}\"\n")
    string(APPEND text "crux_mbed_mgmt_test_password_end:\n")
    string(APPEND text "\t.size crux_mbed_mgmt_test_password, . - crux_mbed_mgmt_test_password\n")
    string(APPEND text "\t.balign 4\n")
    string(APPEND text "\t.global crux_mbed_mgmt_test_password_size\n")
    string(APPEND text "\t.type crux_mbed_mgmt_test_password_size, %object\n")
    string(APPEND text "crux_mbed_mgmt_test_password_size:\n")
    string(APPEND text "\t.long crux_mbed_mgmt_test_password_end - crux_mbed_mgmt_test_password\n")
    string(APPEND text "\t.size crux_mbed_mgmt_test_password_size, 4\n")
    set(asm_file "${CMAKE_BINARY_DIR}/crux_mbed_mgmt_test_password.S")
    set(existing "")
    if(EXISTS "${asm_file}")
        file(READ "${asm_file}" existing)
    endif()
    if(NOT "${existing}" STREQUAL "${text}")
        file(WRITE "${asm_file}" "${text}")
    endif()
    target_sources(app PRIVATE "${asm_file}")
    set_source_files_properties("${asm_file}" PROPERTIES OBJECT_DEPENDS "${real}")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${real}")
    message(STATUS "TEST ONLY first account: password file checked (${length} bytes)")
endfunction()
