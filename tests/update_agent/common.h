/* Helpers shared by the update agent suites. */
#ifndef CRUX_UPDATE_AGENT_TEST_COMMON_H
#define CRUX_UPDATE_AGENT_TEST_COMMON_H

#include "harness.h"
#include "medium.h"

#include <crux/update_agent.h>

static inline crux_update_status_t status_now(void)
{
    crux_update_status_t status = {0};
    CHECK_INT(CRUX_UPDATE_OK, crux_update_status_get(&status));
    return status;
}

static inline crux_update_state_t state_now(void)
{
    return status_now().state;
}

static inline void start_ok(void)
{
    CHECK_INT(CRUX_UPDATE_OK, crux_update_start(&medium_config));
}

/* A reset, then the agent starts again. */
static inline void reboot_and_start(void)
{
    medium_reboot();
    start_ok();
}

static inline size_t build_image(uint8_t *out, uint8_t major, uint8_t minor, uint16_t revision)
{
    medium_image_spec_t spec = medium_image_default(major, minor, revision);
    return medium_image_build(&spec, out, (size_t)MEDIUM_IMAGE_MAX);
}

static inline crux_image_slot_t running_slot_now(void)
{
    crux_image_boot_record_t record = {0};
    CHECK_INT(CRUX_IMAGE_OK, crux_image_boot_record_get(&record));
    return record.running_slot;
}

#endif /* CRUX_UPDATE_AGENT_TEST_COMMON_H */
