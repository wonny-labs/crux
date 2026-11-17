/*
 * A portable consumer of the public contract, as C. It names no provider, no bootloader and no
 * native header. It is built against crux::image_state only, and the build asserts that the usage
 * target carries no native requirement. It is linked into no test: the usage requirement is what is
 * checked. A consumer that only classifies an outcome needs no provider.
 */
#include <crux/image_state.h>

crux_image_outcome_t image_state_consumer_c(const crux_image_boot_record_t *record,
                                            const crux_image_attempt_t *attempt)
{
    return crux_image_outcome(record, attempt);
}

crux_image_result_t image_state_consumer_c_update(crux_image_slot_t slot)
{
    crux_image_result_t result = crux_image_start();
    if (result != CRUX_IMAGE_OK) {
        return result;
    }
    return crux_image_request_test(slot);
}
