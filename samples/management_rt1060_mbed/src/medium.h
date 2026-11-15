/* SPDX-License-Identifier: Apache-2.0 */
/* The file medium of the image: a FatFs volume on a RAM disk. The rule is one sentence: THE RAM
 * DISK MAY BE FORMATTED AND NOTHING ELSE EVER IS. A RAM disk is memory that every boot finds blank,
 * so a failed first mount is answered with one format and a second mount. The image has no card
 * driver, so there is no other medium to reach: this file names the RAM disk and no other disk. */
#ifndef MEDIUM_H
#define MEDIUM_H

#include <stdbool.h>

/* The mount point of the RAM disk's volume. */
#define MEDIUM_MOUNT_POINT "/RAM:"

/* Mounts the RAM disk, formatting it once if it is blank, and prints one line that says what was
 * done. Returns true if the volume is mounted. */
bool medium_mount(void);

#endif
