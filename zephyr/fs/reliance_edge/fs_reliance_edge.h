/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Private composition header for the Reliance Edge file system in the Zephyr VFS. It is not a
 * crux/ API. The type CRUX_FS_RELIANCE_EDGE is defined once, in the public header
 * <crux/file_reliance_edge_zephyr.h> (target crux::file_zephyr), and this header only includes it,
 * so code that names this header by its path keeps working. A composition outside this module
 * includes the public header instead. Mount with this type, `storage_dev` set to the disk_access
 * name (for example "MMC") and `fs_data` unused. A mount never formats. With
 * CONFIG_CRUX_FS_RELIANCE_EDGE_FORMAT, fs_mkfs(CRUX_FS_RELIANCE_EDGE, (uintptr_t)"MMC", NULL, 0)
 * formats that disk.
 */
#ifndef CRUX_FS_RELIANCE_EDGE_H
#define CRUX_FS_RELIANCE_EDGE_H

#include "../../../components/file/ports/zephyr/include/crux/file_reliance_edge_zephyr.h"

#endif /* CRUX_FS_RELIANCE_EDGE_H */
