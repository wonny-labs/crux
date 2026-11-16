// A portable consumer of the public contract, as C++17: the header must be usable from C++, and its
// enumerations and structures must be nameable. See consumer.c.
#include <crux/image_state.h>

static_assert(CRUX_IMAGE_OK == 0, "the header must be usable from C++");
static_assert(CRUX_IMAGE_SLOT_COUNT == 2u, "one image, two slots");
static_assert(CRUX_IMAGE_SLOT_EMPTY == 0, "an erased slot is the zero state");
static_assert(CRUX_IMAGE_OUTCOME_NONE == 0, "no attempt is the zero outcome");

extern "C" crux_image_outcome_t image_state_consumer_cpp(const crux_image_boot_record_t &record)
{
    const crux_image_attempt_t attempt{1u, crux_image_version_t{1u, 1u, 0u, 0u}, true};
    return crux_image_outcome(&record, &attempt);
}

[[maybe_unused]] static crux_image_result_t consumer_cpp_confirm()
{
    return crux_image_confirm();
}
