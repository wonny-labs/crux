#ifndef CRUX_VERSION_H
#define CRUX_VERSION_H

/**
 * @file
 * The Crux release version, as compile-time macros (Semantic Versioning 2.0.0).
 *
 * This header is the one place the number is kept; the root CMake project reads it. On the
 * main branch the numeric parts name the next planned release and CRUX_VERSION_PRERELEASE is
 * "dev", so a snapshot of main and that release have the same numbers. Before 1.0, code must not
 * test features by version number. The rules are in ADR-0008 (docs/decisions/).
 */

/** Major version. */
#define CRUX_VERSION_MAJOR 0

/** Minor version. Before 1.0, every release from the main branch raises it. */
#define CRUX_VERSION_MINOR 1

/** Patch version. */
#define CRUX_VERSION_PATCH 0

/** Pre-release identifier: "dev" on the main branch, "rc.N" for a candidate, "" in a release. */
#define CRUX_VERSION_PRERELEASE "dev"

/** The full version without a leading "v", such as "0.1.0-dev" or "0.1.0". */
#define CRUX_VERSION_STRING "0.1.0-dev"

#endif
