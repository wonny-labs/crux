/*
 * Not a CMake target. The UpdateAgent.nodiscard test compiles it directly and expects the compile
 * to fail on the ignored result.
 */
#include <crux/update_agent.h>

void update_agent_nodiscard_probe(const crux_update_source_t *source)
{
    crux_update_begin(source);
}
