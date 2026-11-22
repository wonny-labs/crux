/* SPDX-License-Identifier: Apache-2.0 */
/* Cases that the target provider on LittleFS adds to the shared suite of
 * tests/native/configuration_settings_file. They run in that suite, so they share its fixture.
 *
 * The backend compacts its file by writing a temporary, closing it and renaming it onto the
 * settings file. LittleFS replaces the destination of a rename in one metadata commit, so a
 * compaction leaves no temporary behind and the settings file is never absent. The image links no
 * FatFs and no Reliance Edge, which the gate also checks in the image's symbols. */
#include "configuration_settings.h"
#include <crux/configuration.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <zephyr/fs/fs.h>
#include <zephyr/ztest.h>

#define FIXTURE_ROOT "/MMC:"
#define SETTINGS_FILE FIXTURE_ROOT "/settings/cfg"
#define SETTINGS_TEMP FIXTURE_ROOT "/settings/cfg.cmp"

BUILD_ASSERT(IS_ENABLED(CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS));
BUILD_ASSERT(!IS_ENABLED(CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE));
BUILD_ASSERT(!IS_ENABLED(CONFIG_FAT_FILESYSTEM_ELM));

static const crux_config_spec_t spec = {
    .key = "speed",
    .schema_version = 7,
    .default_value = {.type = CRUX_CONFIG_U32, .data.u32 = 11},
};

static void set_value(crux_config_param_t *p, uint32_t value)
{
    crux_config_value_t v = {.type = CRUX_CONFIG_U32, .data.u32 = value};

    zassert_ok(crux_config_update(p, &v));
}

static void expect_value(crux_config_param_t *p, uint32_t expected)
{
    crux_config_value_t v;

    zassert_ok(crux_config_read(p, &v));
    zassert_equal(v.data.u32, expected);
}

static bool exists(const char *path)
{
    struct fs_dirent entry;

    return fs_stat(path, &entry) == 0;
}

ZTEST(configuration_settings_littlefs, test_compaction_leaves_no_cmp_file)
{
    crux_config_param_t p = {0};
    struct fs_dirent entry;
    size_t previous = 0;
    unsigned compactions = 0;

    /* Cases of the shared suite that inject a fault into a compaction leave their temporary behind,
     * and before() of the suite resets only the settings file. */
    int rc = fs_unlink(SETTINGS_TEMP);

    zassert_true(rc == 0 || rc == -ENOENT, "removing an old temporary gave %d", rc);
    zassert_ok(crux_config_init(&p, &spec));
    for (uint32_t i = 1; i <= 400; i++) {
        set_value(&p, 1000 + i);
        zassert_equal(crux_config_save(&p), CRUX_CONFIG_OK, "save %u", i);
        zassert_false(exists(SETTINGS_TEMP), "a temporary file is left after save %u", i);
        zassert_ok(fs_stat(SETTINGS_FILE, &entry));
        if (entry.size < previous) {
            compactions++;
        }
        previous = entry.size;
    }
    zassert_true(compactions > 0, "400 saves never compacted the file");
    set_value(&p, 1);
    zassert_equal(crux_config_load(&p), CRUX_CONFIG_OK);
    expect_value(&p, 1400);
}
