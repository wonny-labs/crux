/*
 * Test controls of the emulator of the example temperature sensor. A test reaches the registers
 * of the model through these functions. They are not part of the driver and no firmware image
 * contains them.
 *
 * Modelled on drivers/sensor/asahi_kasei/akm09918c/akm09918c_emul.h of Zephyr
 * (Copyright (c) 2023 Google LLC).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PRODUCT_DRIVERS_SENSOR_EXAMPLE_TEMP_EMUL_H_
#define PRODUCT_DRIVERS_SENSOR_EXAMPLE_TEMP_EMUL_H_

#include <stdint.h>
#include <zephyr/drivers/emul.h>

/* Set one register of the model. */
void example_temp_emul_set_reg(const struct emul *target, uint8_t reg, uint8_t val);

/* Read one register of the model. */
uint8_t example_temp_emul_get_reg(const struct emul *target, uint8_t reg);

/* Put the model back in its state at power-on: the right identifier, no conversion ready. */
void example_temp_emul_reset(const struct emul *target);

#endif /* PRODUCT_DRIVERS_SENSOR_EXAMPLE_TEMP_EMUL_H_ */
