#include "file_port.h"
#include <stdbool.h>
#include <string.h>

_Static_assert(CRUX_FILE_POOL_SIZE >= 4, "File profile requires at least four handles");
_Static_assert(CRUX_FILE_NAME_MAX >= 63, "File profile requires at least 63 name bytes");
_Static_assert(CRUX_FILE_DIR_POOL_SIZE >= 1, "File listing requires a listing handle");
_Static_assert(CRUX_FILE_ROOTS_MAX >= 1 && CRUX_FILE_ROOTS_MAX <= 255,
               "File roots use a uint8_t index, with one value left over as never bound");
/* Widest field first, so that a larger CRUX_FILE_POOL_SIZE does not multiply padding. */
struct crux_file {
    /* A writer on a limited root only: the file's size as counted, and the position when it is
     * known. A failed call leaves the position unknown until a seek, and a write then counts as if
     * it started at the end. */
    uint64_t size;
    uint64_t position;
    crux_file_mode_t mode;
    bool live;
    bool limited;
    bool position_known;
    crux_file_root_t root;
    char name[CRUX_FILE_NAME_MAX + 1];
};

struct crux_file_dir {
    bool live;
    bool ended;
};

/* The byte limit of a root, 0 for none, and what its File files count against it. The count lives
 * only here and is made again at each binding. */
struct root_limit {
    uint64_t max;
    uint64_t used;
    uint64_t unit;
};

static struct crux_file files[CRUX_FILE_POOL_SIZE];
static struct crux_file_dir dirs[CRUX_FILE_DIR_POOL_SIZE];
static struct root_limit limits[CRUX_FILE_ROOTS_MAX];

static bool name_valid(const char *name)
{
    if (!name || !*name || strcmp(name, ".") == 0 || strcmp(name, "..") == 0) {
        return false;
    }
    for (size_t i = 0;; i++) {
        unsigned char c = (unsigned char)name[i];
        if (c == 0) {
            return true;
        }
        if (i >= CRUX_FILE_NAME_MAX ||
            !((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
              c == '_' || c == '-' || c == '.')) {
            return false;
        }
    }
}

static size_t slot_of(const crux_file_t *f)
{
    for (size_t i = 0; i < CRUX_FILE_POOL_SIZE; i++) {
        if (f == &files[i] && files[i].live) {
            return i;
        }
    }
    return CRUX_FILE_POOL_SIZE;
}

static size_t dir_slot_of(const crux_file_dir_t *d)
{
    for (size_t i = 0; i < CRUX_FILE_DIR_POOL_SIZE; i++) {
        if (d == &dirs[i] && dirs[i].live) {
            return i;
        }
    }
    return CRUX_FILE_DIR_POOL_SIZE;
}

/* Any live handle on this file; the caller holds the File lock. */
static bool name_is_open(crux_file_root_t r, const char *n)
{
    for (size_t i = 0; i < CRUX_FILE_POOL_SIZE; i++) {
        if (files[i].live && files[i].root == r && strcmp(files[i].name, n) == 0) {
            return true;
        }
    }
    return false;
}

uint64_t crux_file_limit_charge(uint64_t size, uint64_t unit)
{
    if (unit == 0) {
        unit = 1;
    }
    uint64_t blocks = size / unit + (size % unit != 0 ? 1u : 0u);
    if (blocks == 0) {
        blocks = 1;
    }
    return blocks > UINT64_MAX / unit ? UINT64_MAX : blocks * unit;
}

static uint64_t saturating_add(uint64_t a, uint64_t b)
{
    return a > UINT64_MAX - b ? UINT64_MAX : a + b;
}

static uint64_t charge(crux_file_root_t r, uint64_t size)
{
    return crux_file_limit_charge(size, limits[r].unit);
}

/* Whether a root may go from counting before to counting after for one file. Nothing that grows
 * passes a root that is already above its limit, as a binding can find it. */
static bool limit_allows(crux_file_root_t r, uint64_t before, uint64_t after)
{
    const struct root_limit *l = &limits[r];
    return l->max == 0 || after <= before ||
           (l->used <= l->max && after - before <= l->max - l->used);
}

/* One file of the root went from counting before to counting after. */
static void limit_move(crux_file_root_t r, uint64_t before, uint64_t after)
{
    struct root_limit *l = &limits[r];
    l->used = saturating_add(l->used > before ? l->used - before : 0, after);
}

crux_file_result_t crux_file_limit_root(crux_file_root_t r, uint64_t max_bytes, uint64_t unit)
{
    if (r >= CRUX_FILE_ROOTS_MAX) {
        return CRUX_FILE_ERR_INVALID_ARGUMENT;
    }

    crux_file_lock();
    limits[r] = (struct root_limit){0};
    if (max_bytes == 0) {
        crux_file_unlock();
        return CRUX_FILE_OK;
    }
    size_t d = 0;
    while (d < CRUX_FILE_DIR_POOL_SIZE && dirs[d].live) {
        d++;
    }
    if (d == CRUX_FILE_DIR_POOL_SIZE) {
        crux_file_unlock();
        return CRUX_FILE_ERR_NO_RESOURCES;
    }

    /* The files that File can reach are the ones it counts: the listing's name rule applies. */
    uint64_t used = 0;
    crux_file_result_t result = crux_file_impl_dir_open(d, r);
    if (result == CRUX_FILE_OK) {
        for (;;) {
            char name[CRUX_FILE_NAME_MAX + 1] = {0};
            crux_file_info_t info = {0};
            bool end = false;
            result = crux_file_impl_dir_read(d, name, sizeof(name), &info, &end);
            if (result != CRUX_FILE_OK || end) {
                break;
            }
            if (name_valid(name)) {
                used = saturating_add(used, crux_file_limit_charge(info.size, unit));
            }
        }
        crux_file_result_t closed = crux_file_impl_dir_close(d);
        if (result == CRUX_FILE_OK) {
            result = closed;
        }
    }
    if (result == CRUX_FILE_OK) {
        limits[r] = (struct root_limit){.max = max_bytes, .used = used, .unit = unit ? unit : 1};
    }
    crux_file_unlock();
    return result;
}

crux_file_result_t crux_file_open_at(crux_file_root_t r, const char *n, crux_file_mode_t m,
                                     crux_file_t **out)
{
    if (!out || *out || !name_valid(n) ||
        (m != CRUX_FILE_READ && m != CRUX_FILE_READ_WRITE && m != CRUX_FILE_CREATE_REPLACE)) {
        return CRUX_FILE_ERR_INVALID_ARGUMENT;
    }
    if (r >= CRUX_FILE_ROOTS_MAX) {
        return CRUX_FILE_ERR_NOT_READY;
    }

    crux_file_lock();
    /* A file open for writing excludes every other handle; several readers may share it. A second
     * handle can hold stale provider state (for example a cached cluster chain) after a write. */
    for (size_t i = 0; i < CRUX_FILE_POOL_SIZE; i++) {
        if (files[i].live && files[i].root == r && strcmp(files[i].name, n) == 0 &&
            (files[i].mode != CRUX_FILE_READ || m != CRUX_FILE_READ)) {
            crux_file_unlock();
            return CRUX_FILE_ERR_INVALID_STATE;
        }
    }
    size_t s = 0;
    while (s < CRUX_FILE_POOL_SIZE && files[s].live) {
        s++;
    }
    if (s == CRUX_FILE_POOL_SIZE) {
        crux_file_unlock();
        return CRUX_FILE_ERR_NO_RESOURCES;
    }

    /* A writer on a limited root learns what the file counts first. No writer can be open on the
     * name, so the size that stat reports is current. */
    bool limited = limits[r].max != 0 && m != CRUX_FILE_READ;
    crux_file_info_t found = {0};
    uint64_t before = 0;
    if (limited) {
        crux_file_result_t looked = crux_file_impl_stat(r, n, &found);
        if (looked == CRUX_FILE_OK) {
            before = charge(r, found.size);
        } else if (looked != CRUX_FILE_ERR_NOT_FOUND) {
            crux_file_unlock();
            return looked;
        }
        if (m == CRUX_FILE_CREATE_REPLACE && !limit_allows(r, before, charge(r, 0))) {
            crux_file_unlock();
            return CRUX_FILE_ERR_NO_SPACE;
        }
    }

    crux_file_result_t result = crux_file_impl_open(r, s, n, m);
    if (result == CRUX_FILE_OK && m == CRUX_FILE_CREATE_REPLACE) {
        result = crux_file_impl_truncate(s);
        if (result != CRUX_FILE_OK) {
            crux_file_result_t cleanup = crux_file_impl_close(s);
            if (cleanup != CRUX_FILE_OK) {
                crux_file_record_cleanup_error(cleanup);
            }
        }
    }
    if (result == CRUX_FILE_OK) {
        files[s].live = true;
        files[s].mode = m;
        files[s].root = r;
        files[s].limited = limited;
        files[s].position = 0;
        files[s].position_known = true;
        files[s].size = m == CRUX_FILE_CREATE_REPLACE ? 0 : found.size;
        if (limited && m == CRUX_FILE_READ_WRITE && before == 0 &&
            crux_file_impl_size(s, &files[s].size) != CRUX_FILE_OK) {
            /* Created by a native client after the stat, and its size cannot be read: it counts
             * as empty, and the next write measures it. */
            files[s].size = 0;
            files[s].position_known = false;
        }
        if (limited) {
            limit_move(r, before, charge(r, files[s].size));
        }
        memcpy(files[s].name, n, strlen(n) + 1);
        *out = &files[s];
    } else if (limited && m == CRUX_FILE_CREATE_REPLACE) {
        /* A failed create or truncate may still have changed the file. Count what is there, or
         * keep the larger figure when that cannot be read. */
        crux_file_info_t now = {0};
        crux_file_result_t looked = crux_file_impl_stat(r, n, &now);
        uint64_t after = looked == CRUX_FILE_OK              ? charge(r, now.size)
                         : looked == CRUX_FILE_ERR_NOT_FOUND ? 0
                         : before > charge(r, 0)             ? before
                                                             : charge(r, 0);
        limit_move(r, before, after);
    }
    crux_file_unlock();
    return result;
}

crux_file_result_t crux_file_open(const char *n, crux_file_mode_t m, crux_file_t **out)
{
    return crux_file_open_at(CRUX_FILE_ROOT_DEFAULT, n, m, out);
}

/* Where a write of l bytes on a limited handle can end: from the position, or from the end when
 * the position is unknown, which is the furthest it can reach. */
static uint64_t write_end(const struct crux_file *f, size_t l)
{
    uint64_t from = f->position_known ? f->position : f->size;
    uint64_t end = from > UINT64_MAX - l ? UINT64_MAX : from + l;
    return end > f->size ? end : f->size;
}

/* Count a limited handle's transfer. A provider count is exact only after OK with a known position;
 * otherwise the size is read again, and when that fails the furthest end counts. */
static void limit_after_transfer(size_t s, size_t l, size_t c, crux_file_result_t result,
                                 bool write)
{
    struct crux_file *f = &files[s];
    uint64_t was = f->size;
    if (result == CRUX_FILE_OK && f->position_known) {
        f->position += c;
        if (write && f->position > f->size) {
            f->size = f->position;
        }
    } else if (write) {
        uint64_t furthest = write_end(f, l);
        if (crux_file_impl_size(s, &f->size) != CRUX_FILE_OK) {
            f->size = furthest;
        }
    }
    if (result != CRUX_FILE_OK) {
        f->position_known = false;
    }
    if (write) {
        limit_move(f->root, charge(f->root, was), charge(f->root, f->size));
    }
}

static crux_file_result_t transfer(crux_file_t *f, void *b, size_t l, size_t *c, bool write)
{
    if (!c) {
        return CRUX_FILE_ERR_INVALID_ARGUMENT;
    }

    *c = 0;
    if (l && !b) {
        return CRUX_FILE_ERR_INVALID_ARGUMENT;
    }

    crux_file_lock();
    size_t s = slot_of(f);
    crux_file_result_t result;
    if (s == CRUX_FILE_POOL_SIZE) {
        result = CRUX_FILE_ERR_INVALID_STATE;
    }
#if SIZE_MAX > INT64_MAX
    else if (l > INT64_MAX) {
        result = CRUX_FILE_ERR_OUT_OF_RANGE;
    }
#endif
    else if (write && files[s].mode == CRUX_FILE_READ) {
        result = CRUX_FILE_ERR_ACCESS;
    } else if (!l) {
        result = CRUX_FILE_OK;
    } else if (write && files[s].limited &&
               !limit_allows(files[s].root, charge(files[s].root, files[s].size),
                             charge(files[s].root, write_end(&files[s], l)))) {
        /* The whole write is refused before the provider sees it, so nothing passes the limit. */
        result = CRUX_FILE_ERR_NO_SPACE;
    } else {
        result = write ? crux_file_impl_write(s, b, l, c) : crux_file_impl_read(s, b, l, c);
        if (*c > l) {
            /* A contradictory provider result cannot acknowledge any count.
             * This does not undo possible buffer or storage changes. */
            *c = 0;
            result = CRUX_FILE_ERR_IO;
        }
        if (files[s].limited) {
            limit_after_transfer(s, l, *c, result, write);
        }
        if (result == CRUX_FILE_OK && write && *c < l) {
            result = CRUX_FILE_PARTIAL;
        }
    }
    crux_file_unlock();
    return result;
}

crux_file_result_t crux_file_read(crux_file_t *f, void *b, size_t l, size_t *c)
{
    return transfer(f, b, l, c, false);
}

crux_file_result_t crux_file_write(crux_file_t *f, const void *b, size_t l, size_t *c)
{
    return transfer(f, (void *)b, l, c, true);
}

crux_file_result_t crux_file_seek(crux_file_t *f, uint64_t o)
{
    crux_file_lock();
    size_t s = slot_of(f);
    crux_file_result_t result = s == CRUX_FILE_POOL_SIZE ? CRUX_FILE_ERR_INVALID_STATE
                                : o > INT64_MAX          ? CRUX_FILE_ERR_OUT_OF_RANGE
                                                         : crux_file_impl_seek(s, o);
    /* A refused offset leaves the position where it was, as the providers check it first. */
    if (s != CRUX_FILE_POOL_SIZE && files[s].limited && result != CRUX_FILE_ERR_OUT_OF_RANGE) {
        files[s].position = o;
        files[s].position_known = result == CRUX_FILE_OK;
    }
    crux_file_unlock();
    return result;
}

crux_file_result_t crux_file_sync(crux_file_t *f)
{
    crux_file_lock();
    size_t s = slot_of(f);
    crux_file_result_t result =
        s == CRUX_FILE_POOL_SIZE ? CRUX_FILE_ERR_INVALID_STATE : crux_file_impl_sync(s);
    crux_file_unlock();
    return result;
}

crux_file_result_t crux_file_close(crux_file_t **f)
{
    if (!f) {
        return CRUX_FILE_ERR_INVALID_ARGUMENT;
    }

    crux_file_lock();
    size_t s = slot_of(*f);
    if (s == CRUX_FILE_POOL_SIZE) {
        crux_file_unlock();
        return CRUX_FILE_ERR_INVALID_STATE;
    }
    *f = NULL;
    crux_file_result_t result = crux_file_impl_close(s);
    files[s].live = false;
    crux_file_unlock();
    return result;
}

crux_file_result_t crux_file_remove_at(crux_file_root_t r, const char *n)
{
    if (!name_valid(n)) {
        return CRUX_FILE_ERR_INVALID_ARGUMENT;
    }
    if (r >= CRUX_FILE_ROOTS_MAX) {
        return CRUX_FILE_ERR_NOT_READY;
    }

    crux_file_lock();
    if (name_is_open(r, n)) {
        crux_file_unlock();
        return CRUX_FILE_ERR_INVALID_STATE;
    }

    /* On a limited root the file's size is read first, and the space comes back once the file is
     * gone, which a failed remove can also leave. A size that cannot be read keeps its count. */
    crux_file_info_t found = {0};
    bool counted = limits[r].max != 0 && crux_file_impl_stat(r, n, &found) == CRUX_FILE_OK;
    crux_file_result_t result = crux_file_impl_remove(r, n);
    if (counted) {
        crux_file_info_t now;
        if (result == CRUX_FILE_OK || crux_file_impl_stat(r, n, &now) == CRUX_FILE_ERR_NOT_FOUND) {
            limit_move(r, charge(r, found.size), 0);
        }
    }
    crux_file_unlock();
    return result;
}

crux_file_result_t crux_file_remove(const char *n)
{
    return crux_file_remove_at(CRUX_FILE_ROOT_DEFAULT, n);
}

crux_file_result_t crux_file_stat(crux_file_root_t r, const char *n, crux_file_info_t *out)
{
    if (!out || !name_valid(n)) {
        return CRUX_FILE_ERR_INVALID_ARGUMENT;
    }
    if (r >= CRUX_FILE_ROOTS_MAX) {
        return CRUX_FILE_ERR_NOT_READY;
    }

    crux_file_lock();
    crux_file_result_t result = crux_file_impl_stat(r, n, out);
    crux_file_unlock();
    return result;
}

crux_file_result_t crux_file_size(crux_file_t *f, uint64_t *size)
{
    crux_file_lock();
    size_t s = slot_of(f);
    crux_file_result_t result = s == CRUX_FILE_POOL_SIZE ? CRUX_FILE_ERR_INVALID_STATE
                                : !size                  ? CRUX_FILE_ERR_INVALID_ARGUMENT
                                                         : crux_file_impl_size(s, size);
    if (result == CRUX_FILE_OK && files[s].limited) {
        limit_move(files[s].root, charge(files[s].root, files[s].size),
                   charge(files[s].root, *size));
        files[s].size = *size;
    }
    crux_file_unlock();
    return result;
}

crux_file_result_t crux_file_rename(crux_file_root_t r, const char *from, const char *to)
{
    if (!name_valid(from) || !name_valid(to)) {
        return CRUX_FILE_ERR_INVALID_ARGUMENT;
    }
    if (r >= CRUX_FILE_ROOTS_MAX) {
        return CRUX_FILE_ERR_NOT_READY;
    }

    crux_file_lock();
    crux_file_result_t result = name_is_open(r, from) || name_is_open(r, to)
                                    ? CRUX_FILE_ERR_INVALID_STATE
                                    : crux_file_impl_rename(r, from, to);
    crux_file_unlock();
    return result;
}

crux_file_result_t crux_file_dir_open(crux_file_root_t r, crux_file_dir_t **out)
{
    if (!out || *out) {
        return CRUX_FILE_ERR_INVALID_ARGUMENT;
    }
    if (r >= CRUX_FILE_ROOTS_MAX) {
        return CRUX_FILE_ERR_NOT_READY;
    }

    crux_file_lock();
    size_t s = 0;
    while (s < CRUX_FILE_DIR_POOL_SIZE && dirs[s].live) {
        s++;
    }
    crux_file_result_t result =
        s == CRUX_FILE_DIR_POOL_SIZE ? CRUX_FILE_ERR_NO_RESOURCES : crux_file_impl_dir_open(s, r);
    if (result == CRUX_FILE_OK) {
        dirs[s].live = true;
        dirs[s].ended = false;
        *out = &dirs[s];
    }
    crux_file_unlock();
    return result;
}

crux_file_result_t crux_file_dir_read(crux_file_dir_t *d, char *name, size_t capacity,
                                      crux_file_info_t *info, bool *end)
{
    if (!name || !capacity || !info || !end) {
        return CRUX_FILE_ERR_INVALID_ARGUMENT;
    }

    name[0] = '\0';
    *end = false;
    crux_file_lock();
    size_t s = dir_slot_of(d);
    crux_file_result_t result = CRUX_FILE_OK;
    if (s == CRUX_FILE_DIR_POOL_SIZE) {
        result = CRUX_FILE_ERR_INVALID_STATE;
    } else if (capacity < CRUX_FILE_NAME_MAX + 1) {
        result = CRUX_FILE_ERR_OUT_OF_RANGE;
    } else if (dirs[s].ended) {
        *end = true;
    } else {
        /* Foreign names are skipped here, so that the name rule has one definition. */
        do {
            name[0] = '\0';
            result = crux_file_impl_dir_read(s, name, capacity, info, end);
        } while (result == CRUX_FILE_OK && !*end && !name_valid(name));
        if (result != CRUX_FILE_OK || *end) {
            name[0] = '\0';
            *end = result == CRUX_FILE_OK;
            dirs[s].ended = *end;
        }
    }
    crux_file_unlock();
    return result;
}

crux_file_result_t crux_file_dir_close(crux_file_dir_t **d)
{
    if (!d) {
        return CRUX_FILE_ERR_INVALID_ARGUMENT;
    }

    crux_file_lock();
    size_t s = dir_slot_of(*d);
    if (s == CRUX_FILE_DIR_POOL_SIZE) {
        crux_file_unlock();
        return CRUX_FILE_ERR_INVALID_STATE;
    }
    *d = NULL;
    crux_file_result_t result = crux_file_impl_dir_close(s);
    dirs[s].live = false;
    crux_file_unlock();
    return result;
}

static size_t path_length(const char *p)
{
    size_t length = strlen(p);
    while (length > 1 && p[length - 1] == '/') {
        length--;
    }
    return length;
}

bool crux_file_paths_overlap(const char *a, const char *b)
{
    size_t la = path_length(a);
    size_t lb = path_length(b);
    const char *longer = la > lb ? a : b;
    size_t shorter = la > lb ? lb : la;
    /* A shorter path that keeps its final separator is the top of the tree, which holds any path.
     */
    return strncmp(a, b, shorter) == 0 &&
           (la == lb || longer[shorter] == '/' || (shorter > 0 && longer[shorter - 1] == '/'));
}
