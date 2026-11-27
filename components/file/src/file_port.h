#ifndef CRUX_FILE_PORT_H
#define CRUX_FILE_PORT_H
#include <crux/file.h>
#ifndef CRUX_FILE_POOL_SIZE
#define CRUX_FILE_POOL_SIZE 4
#endif
#ifndef CRUX_FILE_DIR_POOL_SIZE
#define CRUX_FILE_DIR_POOL_SIZE 2
#endif
#ifndef CRUX_FILE_ROOTS_MAX
#define CRUX_FILE_ROOTS_MAX 8
#endif
#ifndef CRUX_FILE_NAME_MAX
#define CRUX_FILE_NAME_MAX 63
#endif
/* Sleepable, task-context serialization. An internal lock/ownership failure is
 * fatal: never return with inconsistent pool/native-handle ownership. */
void crux_file_lock(void);
void crux_file_unlock(void);
/* Private provider contract. Counts must not exceed the requested length;
 * valid accepted counts survive errors. Native handles stay
 * in provider slots; close retires exactly once, even on error.
 * The common layer checks arguments, handles and that a root index is in range. A provider returns
 * CRUX_FILE_ERR_NOT_READY for an index that is in range but not bound. */
crux_file_result_t crux_file_impl_open(crux_file_root_t root, size_t slot, const char *name,
                                       crux_file_mode_t mode);
crux_file_result_t crux_file_impl_truncate(size_t slot);
crux_file_result_t crux_file_impl_read(size_t slot, void *buffer, size_t length, size_t *count);
crux_file_result_t crux_file_impl_write(size_t slot, const void *buffer, size_t length,
                                        size_t *count);
crux_file_result_t crux_file_impl_seek(size_t slot, uint64_t offset);
crux_file_result_t crux_file_impl_sync(size_t slot);
crux_file_result_t crux_file_impl_close(size_t slot);
crux_file_result_t crux_file_impl_remove(crux_file_root_t root, const char *name);
/* Regular files only; anything else is CRUX_FILE_ERR_NOT_FOUND. */
crux_file_result_t crux_file_impl_stat(crux_file_root_t root, const char *name,
                                       crux_file_info_t *out);
/* The handle's current size, with its position preserved. */
crux_file_result_t crux_file_impl_size(size_t slot, uint64_t *size);
/* Missing or non-regular source: NOT_FOUND. Any existing destination: EXISTS, never replaced. */
crux_file_result_t crux_file_impl_rename(crux_file_root_t root, const char *from, const char *to);
crux_file_result_t crux_file_impl_dir_open(size_t dir_slot, crux_file_root_t root);
/* The next regular file whose name fits capacity, NUL-terminated, or *end set at the finish. The
 * common layer applies the name rule, and it remembers the end. */
crux_file_result_t crux_file_impl_dir_read(size_t dir_slot, char *name, size_t capacity,
                                           crux_file_info_t *info, bool *end);
/* Close retires exactly once, even on error. */
crux_file_result_t crux_file_impl_dir_close(size_t dir_slot);
/* Record secondary cleanup failure without replacing primary truncate error. */
void crux_file_record_cleanup_error(crux_file_result_t error);
/* Whether two bound paths are equal or one holds the other, comparing text only. */
bool crux_file_paths_overlap(const char *a, const char *b);
/*
 * Root byte limits (docs/file-contract.md#root-byte-limits), enforced by the common layer.
 * A provider's limited binding binds the root first, then calls crux_file_limit_root with the unit
 * of its volume, and unbinds the root again when that fails. The call lists the root through the
 * provider under the File lock and needs a free listing slot. A max_bytes of 0 removes a limit,
 * for a provider whose binding can start again, such as the test fake.
 */
crux_file_result_t crux_file_limit_root(crux_file_root_t root, uint64_t max_bytes, uint64_t unit);
/* What a file of this size counts against a limit: its size rounded up to the unit, at least one
 * unit, saturating at UINT64_MAX. A unit of 0 counts as 1. */
uint64_t crux_file_limit_charge(uint64_t size, uint64_t unit);
#endif
