#ifndef CRUX_CONFIGURATION_ZEPHYR_H
#define CRUX_CONFIGURATION_ZEPHYR_H

/**
 * @file
 * @brief Start of the Configuration provider on the Zephyr Settings File backend. A composition
 * interface.
 *
 * Status: Experimental (ADR-0001 decision 4). A change is listed in the release notes.
 *
 * This is a composition interface, not a portable one (rules of docs/composition-interfaces.md).
 * Only the platform composition of a product calls it, after it has made the storage ready, and a
 * native-free consumer check rejects the target that publishes it (crux::configuration_zephyr).
 * The header includes no Zephyr, vendor, board or private header.
 *
 * A product reaches it by linking the CMake target crux::configuration_zephyr, which adds this
 * include root and crux::configuration. The target exists only when a Settings File selection is
 * on (CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE or CONFIG_CRUX_CONFIGURATION_SETTINGS_FILE_ANY_FS),
 * which builds the provider. It does not link the provider: the module registers that with the
 * Zephyr link.
 */

#include <crux/configuration.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Initialise the Zephyr Settings subsystem and its file backend, and make the provider ready.
 * Until it returns CRUX_CONFIG_OK, crux_config_load() and crux_config_save() return
 * CRUX_CONFIG_ERR_NOT_READY.
 *
 * Call it only after the volume that holds CONFIG_SETTINGS_FILE_PATH is mounted and the
 * composition has checked its layout: the backend creates the missing directories of that path
 * when it initialises, so calling it earlier lets it create them on the wrong medium or before a
 * layout check that should have refused the medium.
 *
 * Thread context. Call it before any other thread loads or saves a parameter and before
 * crux_config_service_start(), because the provider's ready flag is not guarded by a lock. After
 * success a further call returns CRUX_CONFIG_OK and does nothing, because the Settings subsystem
 * initialises once. After a failure the provider stays not ready and the composition may call it
 * again, for example after repairing the medium; Crux never retries on its own.
 *
 * @retval CRUX_CONFIG_OK Ready, now or already.
 * @retval CRUX_CONFIG_ERR_NO_SPACE The backend returned -ENOSPC.
 * @retval CRUX_CONFIG_ERR_NOT_READY The backend returned -ENODEV or -EAGAIN.
 * @retval CRUX_CONFIG_ERR_NOT_SUPPORTED The backend returned -ENOTSUP.
 * @retval CRUX_CONFIG_ERR_IO The backend returned any other error.
 */
crux_config_result_t crux_config_zephyr_init(void);

#ifdef __cplusplus
}
#endif

#endif /* CRUX_CONFIGURATION_ZEPHYR_H */
