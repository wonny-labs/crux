/*
 * A portable consumer of the public header, as C. It names no provider and no native header. It
 * is built against crux::update_agent only, and the build asserts that the usage target carries no
 * native requirement. It is linked into no test: the usage requirement is what is checked.
 */
#include <crux/update_agent.h>

crux_update_result_t update_agent_consumer_c(const void *data, size_t size)
{
    static const crux_update_config_t config = {0x400u, 0x80000000u};
    crux_update_memory_source_t memory;
    crux_update_source_t source = crux_update_source_memory(&memory, data, size);
    crux_update_result_t result = crux_update_start(&config);
    if (result != CRUX_UPDATE_OK) {
        return result;
    }
    return crux_update_begin(&source);
}
