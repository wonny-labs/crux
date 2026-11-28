// A portable consumer of the public header, as C++17: the header must be usable from C++, and its
// enumerations and structures must be nameable. See consumer.c.
#include <crux/update_agent.h>

static_assert(CRUX_UPDATE_OK == 0, "the header must be usable from C++");
static_assert(CRUX_UPDATE_STATE_NOT_STARTED == 0, "not started is the zero state");

extern "C" bool update_agent_consumer_cpp_waiting()
{
    crux_update_status_t status{};
    return crux_update_status_get(&status) == CRUX_UPDATE_OK &&
           status.state == CRUX_UPDATE_STATE_WAITING_RESET;
}

[[maybe_unused]] static crux_update_result_t consumer_cpp_confirm()
{
    return crux_update_confirm();
}
