#ifndef CRUX_FILE_RELIANCE_EDGE_ZEPHYR_H
#define CRUX_FILE_RELIANCE_EDGE_ZEPHYR_H

/**
 * @file
 * @brief The Reliance Edge file system type of the Zephyr VFS. A composition interface.
 *
 * Status: Experimental (ADR-0001 decision 4). It has no physical-board result yet, and a change
 * is listed in the release notes.
 *
 * This is a composition interface, not a portable one (rules of docs/composition-interfaces.md).
 * It publishes one constant, CRUX_FS_RELIANCE_EDGE, the value that a product's platform
 * composition sets as `type` of its `fs_mount_t`, so that the composition names the file system
 * without a path into the Crux source tree. Zephyr's own FS_FATFS plays that part for FatFs. The
 * header declares no function: the composition mounts with Zephyr's fs_mount() and binds the
 * mounted directory with crux_file_zephyr_bind() of <crux/file_zephyr.h>. It includes only
 * <zephyr/fs/fs.h>, which the composition needs for fs_mount_t anyway.
 *
 * A product reaches it by linking the CMake target crux::file_zephyr, which adds this include
 * root. The file system itself is the optional Reliance Edge adapter that
 * CONFIG_CRUX_FS_RELIANCE_EDGE selects (west group crux-reliance); this header neither selects nor
 * links it.
 *
 * How to use the type (the adapter's rules):
 * - Mount: set `type` to CRUX_FS_RELIANCE_EDGE, `storage_dev` to the disk_access name (for example
 *   "MMC") and leave `fs_data` unused. A mount never formats.
 * - Format: only with CONFIG_CRUX_FS_RELIANCE_EDGE_FORMAT, which is off by default, as
 *   fs_mkfs(CRUX_FS_RELIANCE_EDGE, (uintptr_t)"MMC", NULL, 0). When formatting is allowed is set
 *   by docs/emmc-reliance-physical-gate.md and docs/porting-to-a-new-board.md, not by this header.
 * - Execution context and thread safety are those of the Zephyr VFS calls above.
 *
 * The value is FS_TYPE_EXTERNAL_BASE, the first type that Zephyr leaves to out-of-tree file
 * systems. A build that registers another external file system under the same value is not
 * supported.
 */

#include <zephyr/fs/fs.h>

#define CRUX_FS_RELIANCE_EDGE FS_TYPE_EXTERNAL_BASE

#endif /* CRUX_FILE_RELIANCE_EDGE_ZEPHYR_H */
