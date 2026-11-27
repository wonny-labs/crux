/* Another writer creates the destination of a rename after the provider looked at the names and
 * before the rename itself. The link wraps fstatat, the provider's last look at the names, so the
 * wrapper can play that writer. The rename must report EXISTS and leave the writer's file as it
 * is. On a kernel or file system without RENAME_NOREPLACE the provider falls back to a check and a
 * replacing rename, and this test then fails: it shows the fallback's window. */
#include "file_linux.h"
#include <assert.h>
#include <crux/file.h>
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

// NOLINTNEXTLINE(bugprone-reserved-identifier): linker --wrap name, fixed by the linker
int __real_fstatat(int dirfd, const char *path, struct stat *st, int flags);

static bool armed;
static int intrusions;
static char destination[128];

static void intrude(void)
{
    int fd = open(destination, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (fd < 0) {
        assert(errno == EEXIST);
        return;
    }
    assert(write(fd, "theirs", 6) == 6);
    assert(close(fd) == 0);
    intrusions++;
}

// NOLINTNEXTLINE(bugprone-reserved-identifier): linker --wrap name, fixed by the linker
int __wrap_fstatat(int dirfd, const char *path, struct stat *st, int flags)
{
    if (!armed) {
        return __real_fstatat(dirfd, path, st, flags);
    }
    if (strcmp(path, "to") == 0) {
        /* A check of the destination: it is missing now and exists a moment later. */
        intrude();
        errno = ENOENT;
        return -1;
    }
    int result = __real_fstatat(dirfd, path, st, flags);
    int saved = errno;
    intrude();
    errno = saved;
    return result;
}

int main(void)
{
    char root[] = "/tmp/crux-file-race-XXXXXX";
    assert(mkdtemp(root));
    assert(crux_file_linux_bind(root) == CRUX_FILE_OK);
    assert(snprintf(destination, sizeof(destination), "%s/to", root) > 0);

    crux_file_t *f = NULL;
    size_t n = 0;
    assert(crux_file_open("from", CRUX_FILE_CREATE_REPLACE, &f) == CRUX_FILE_OK);
    assert(crux_file_write(f, "mine", 4, &n) == CRUX_FILE_OK && n == 4);
    assert(crux_file_close(&f) == CRUX_FILE_OK);

    armed = true;
    crux_file_result_t result = crux_file_rename(0, "from", "to");
    armed = false;
    assert(intrusions == 1);
    assert(result == CRUX_FILE_ERR_EXISTS);

    /* The writer's file is unchanged and the source is still there. */
    char b[8] = {0};
    assert(crux_file_open("to", CRUX_FILE_READ, &f) == CRUX_FILE_OK);
    assert(crux_file_read(f, b, sizeof(b), &n) == CRUX_FILE_OK && n == 6);
    assert(memcmp(b, "theirs", 6) == 0);
    assert(crux_file_close(&f) == CRUX_FILE_OK);
    assert(crux_file_open("from", CRUX_FILE_READ, &f) == CRUX_FILE_OK);
    assert(crux_file_read(f, b, sizeof(b), &n) == CRUX_FILE_OK && n == 4);
    assert(memcmp(b, "mine", 4) == 0);
    assert(crux_file_close(&f) == CRUX_FILE_OK);

    /* Without an intruder the rename still works. */
    assert(crux_file_remove("to") == CRUX_FILE_OK);
    assert(crux_file_rename(0, "from", "to") == CRUX_FILE_OK);
    assert(crux_file_remove("to") == CRUX_FILE_OK);
    assert(rmdir(root) == 0);
    puts("rename race: EXISTS, destination unchanged");
    return 0;
}
