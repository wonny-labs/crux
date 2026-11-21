/* The handle and listing pools hold exactly the configured number. CRUX_FILE_EXPECTED_POOL and
 * CRUX_FILE_EXPECTED_DIR_POOL come from the build: the CMake cache values for crux::file, or 8
 * and 3 for the copy of the provider that this directory builds with larger pools. */
#include "file_linux.h"
#include <assert.h>
#include <crux/file.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

_Static_assert(CRUX_FILE_POOL_SIZE == CRUX_FILE_EXPECTED_POOL, "handle pool follows the build");
_Static_assert(CRUX_FILE_DIR_POOL_SIZE == CRUX_FILE_EXPECTED_DIR_POOL,
               "listing pool follows the build");

int main(void)
{
    char root[] = "/tmp/crux-file-pool-XXXXXX";
    assert(mkdtemp(root));
    assert(crux_file_linux_bind(root) == CRUX_FILE_OK);

    crux_file_t *files[CRUX_FILE_POOL_SIZE] = {NULL};
    char name[CRUX_FILE_POOL_SIZE][16];
    for (size_t i = 0; i < CRUX_FILE_POOL_SIZE; i++) {
        assert(snprintf(name[i], sizeof(name[i]), "pool%zu", i) > 0);
        assert(crux_file_open(name[i], CRUX_FILE_CREATE_REPLACE, &files[i]) == CRUX_FILE_OK);
    }
    crux_file_t *extra = NULL;
    assert(crux_file_open("extra", CRUX_FILE_CREATE_REPLACE, &extra) == CRUX_FILE_ERR_NO_RESOURCES);
    assert(!extra);

    crux_file_dir_t *dirs[CRUX_FILE_DIR_POOL_SIZE] = {NULL};
    for (size_t i = 0; i < CRUX_FILE_DIR_POOL_SIZE; i++) {
        assert(crux_file_dir_open(0, &dirs[i]) == CRUX_FILE_OK);
    }
    crux_file_dir_t *extra_dir = NULL;
    assert(crux_file_dir_open(0, &extra_dir) == CRUX_FILE_ERR_NO_RESOURCES);
    assert(!extra_dir);

    for (size_t i = 0; i < CRUX_FILE_DIR_POOL_SIZE; i++) {
        assert(crux_file_dir_close(&dirs[i]) == CRUX_FILE_OK);
    }
    for (size_t i = 0; i < CRUX_FILE_POOL_SIZE; i++) {
        assert(crux_file_close(&files[i]) == CRUX_FILE_OK);
        assert(crux_file_remove(name[i]) == CRUX_FILE_OK);
    }
    assert(rmdir(root) == 0);
    printf("pool: %d handles, %d listings\n", CRUX_FILE_POOL_SIZE, CRUX_FILE_DIR_POOL_SIZE);
    return 0;
}
