/*
 * Register map of the fictional example temperature sensor, shared by the driver and its emulator.
 * The part does not exist. The layout follows the usual shape of a small I2C temperature sensor.
 *
 * Modelled on drivers/sensor/f75303/f75303.h of Zephyr (Copyright (c) 2023 Google LLC).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef PRODUCT_DRIVERS_SENSOR_EXAMPLE_TEMP_H_
#define PRODUCT_DRIVERS_SENSOR_EXAMPLE_TEMP_H_

#include <stdint.h>
#include <zephyr/drivers/i2c.h>

/* Temperature, two bytes read in one transfer: the most significant byte comes first. The value
 * is a 12-bit two's complement number, left-justified in the 16 bits. */
#define EXAMPLE_TEMP_REG_TEMP 0x00
/* Status. */
#define EXAMPLE_TEMP_REG_STATUS 0x02
/* Configuration. */
#define EXAMPLE_TEMP_REG_CONFIG 0x03
/* Part identifier. */
#define EXAMPLE_TEMP_REG_ID 0x0f

#define EXAMPLE_TEMP_ID 0x5c

#define EXAMPLE_TEMP_STATUS_DRDY 0x01
#define EXAMPLE_TEMP_CONFIG_CONTINUOUS 0x01

#define EXAMPLE_TEMP_TEMP_SHIFT 4
#define EXAMPLE_TEMP_MICROCELSIUS_PER_LSB 62500

struct example_temp_config {
    struct i2c_dt_spec i2c;
};

struct example_temp_data {
    /* Last sample, in units of 1/16 degree Celsius. */
    int16_t sample;
};

#endif /* PRODUCT_DRIVERS_SENSOR_EXAMPLE_TEMP_H_ */
