/*
 * Not a CMake target. The ImageState.nodiscard test compiles it directly and expects the compile to
 * fail on the ignored result.
 */
#include <crux/image_state.h>

void image_state_nodiscard_probe(void)
{
    crux_image_confirm();
}
