#include "conformance.h"
#include "fake_file.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void add_directory(crux_file_root_t root, const char *name)
{
    crux_file_fake_add_directory(root, name);
}

static void add_foreign_files(crux_file_root_t root)
{
    crux_file_fake_add_raw(root, "has space");
    crux_file_fake_add_raw(root,
                           "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy");
}

#define FAKE_UNIT 16u

static crux_file_result_t bind_root_limited(crux_file_root_t root, const char *path,
                                            uint64_t max_bytes)
{
    return crux_file_fake_bind_root_limited(root, path, max_bytes, FAKE_UNIT);
}

/* The fake keeps entries by root index, and the limit case binds the seeded path as root 5. */
static void add_seed(const char *path, uint64_t unit)
{
    assert(strcmp(path, "/seeded") == 0);
    crux_file_fake_add_file(5, "seed", (size_t)(2 * unit + 1));
    crux_file_fake_add_file(5, "has space", (size_t)unit);
    crux_file_fake_add_directory(5, "sub");
}

int main(void)
{
    crux_file_fake_reset();
    assert(crux_file_fake_bind_root(0, "/volume/a") == CRUX_FILE_OK);
    assert(crux_file_fake_bind_root(1, "/volume/b") == CRUX_FILE_OK);
    const crux_file_conformance_env_t env = {
        .add_directory = add_directory,
        .add_foreign_files = add_foreign_files,
        .bind_root = crux_file_fake_bind_root,
        .path_0 = "/volume/a",
        .path_0_parent = "/volume",
        .path_0_child = "/volume/a/inner",
        .path_free = "/other",
        .path_0_prefix = "/volume/a2",
        .bind_root_limited = bind_root_limited,
        .limit_unit = FAKE_UNIT,
        .path_limited = "/limited",
        .path_seeded = "/seeded",
        .add_seed = add_seed,
    };
    crux_file_conformance_roots(&env);
    crux_file_conformance_stat(&env);
    crux_file_conformance_size();
    crux_file_conformance_rename(&env);
    crux_file_conformance_listing(&env);
    crux_file_conformance_limit(&env);
    /* The top of the tree is a parent of everything. */
    assert(crux_file_fake_bind_root(2, "/") == CRUX_FILE_ERR_INVALID_STATE);
    crux_file_conformance_binding(&env);
    puts("File conformance on the fake provider passed");
    return 0;
}
