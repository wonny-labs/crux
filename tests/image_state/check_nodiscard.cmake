# Runs the C compiler on probe/nodiscard_probe.c with -Werror=unused-result. The probe ignores the
# result of crux_image_confirm(), so the compile must fail, and the output must name the attribute:
# a header that does not compile, or a typo in the probe, would fail it too.
#
# Input: -DC_COMPILER=<cc> -DINCLUDE_DIR=<components/image_state/include> -DPROBE=<probe source>
foreach(variable IN ITEMS C_COMPILER INCLUDE_DIR PROBE)
    if(NOT DEFINED ${variable})
        message(FATAL_ERROR "${variable} is required")
    endif()
endforeach()
execute_process(
    COMMAND "${C_COMPILER}" -std=c17 -fsyntax-only -Werror=unused-result "-I${INCLUDE_DIR}" "${PROBE}"
    RESULT_VARIABLE status
    OUTPUT_VARIABLE output
    ERROR_VARIABLE output)
if(status EQUAL 0)
    message(FATAL_ERROR "an ignored crux_image_confirm() result did not fail the build")
endif()
if(NOT output MATCHES "warn_unused_result")
    message(FATAL_ERROR "the probe failed for another reason:\n${output}")
endif()
message(STATUS "an ignored result fails the build with the attribute named")
