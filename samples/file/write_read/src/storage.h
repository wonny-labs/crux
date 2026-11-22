#ifndef FILE_WRITE_READ_STORAGE_H
#define FILE_WRITE_READ_STORAGE_H

/*
 * The platform composition of the sample: it mounts a file system and binds it as the default
 * File root. The build compiles exactly one implementation, chosen by the selected File
 * provider (CMakeLists.txt). Application code never calls Zephyr's file system API itself.
 */

/** Short name of the selected provider, printed in the result line. */
extern const char *const storage_provider_name;

/**
 * Mount the volume and bind it as File root 0. Prints one "Storage: ..." line.
 *
 * @return 0 on success, otherwise a negative value.
 */
int storage_init(void);

#endif
