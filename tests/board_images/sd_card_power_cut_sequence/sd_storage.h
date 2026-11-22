/* SPDX-License-Identifier: Apache-2.0 */
#pragma once

/* Maps the names that the microSD test sources of tests/board_images/sd_card_power_cut_append and
 * tests/board_images/sd_card_power_cut_replace use onto the Reliance Edge mount helper of
 * samples/boards/nxp/mimxrt1060_evk/emmc_file, so that those sources compile unchanged. It stands
 * in for samples/boards/nxp/mimxrt1060_evk/sd_card_file/sd_storage.h, which is not on this image's
 * include path; the reused sources find this header because neither of their directories holds one
 * of that name. The six constants of enum sd_storage_status have the same values as the first six
 * of enum emmc_storage_status (that enum has a seventh, which only emmc_configuration_start
 * returns). The mount point stays /MMC: whatever the disk is called; only the disk name
 * (CONFIG_SAMPLE_EMMC_DISK_NAME, "SD" here) differs. */
#include "emmc_storage.h"

#define SD_STORAGE_SETTINGS_DIR EMMC_STORAGE_SETTINGS_DIR
#define SD_STORAGE_READY EMMC_STORAGE_READY
#define sd_storage_status emmc_storage_status
#define sd_storage_start emmc_storage_start
