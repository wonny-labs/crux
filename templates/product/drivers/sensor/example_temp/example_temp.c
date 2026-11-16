/*
 * Driver of the fictional example temperature sensor, behind Zephyr's sensor API. It is a plain
 * Zephyr driver: it names no Crux header and offers no Crux interface.
 *
 * Modelled on drivers/sensor/f75303/f75303.c of Zephyr (Copyright (c) 2023 Google LLC).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/* The compatible of the binding, as the preprocessor sees it: "vnd,example-temp" with every
 * non-alphanumeric character turned into an underscore. DT_INST_* macros need it. */
#define DT_DRV_COMPAT vnd_example_temp

#include "example_temp.h"

#include <errno.h>
#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/byteorder.h>

LOG_MODULE_REGISTER(example_temp, CONFIG_EXAMPLE_TEMP_LOG_LEVEL);

static int example_temp_sample_fetch(const struct device *dev, enum sensor_channel chan)
{
    const struct example_temp_config *config = dev->config;
    struct example_temp_data *data = dev->data;
    uint8_t status;
    uint8_t raw[2];
    int ret;

    /* The temperature is the only quantity of the part. A caller that asks for another channel
     * gets -ENOTSUP, as with any Zephyr sensor, so that it can tell "not supported" from a fault.
     */
    if (chan != SENSOR_CHAN_ALL && chan != SENSOR_CHAN_AMBIENT_TEMP) {
        return -ENOTSUP;
    }

    ret = i2c_reg_read_byte_dt(&config->i2c, EXAMPLE_TEMP_REG_STATUS, &status);
    if (ret < 0) {
        LOG_ERR("status read failed: %d", ret);
        return ret;
    }
    if ((status & EXAMPLE_TEMP_STATUS_DRDY) == 0) {
        /* No new conversion yet. The caller may try again, so this is not a fault. */
        return -EBUSY;
    }

    ret = i2c_burst_read_dt(&config->i2c, EXAMPLE_TEMP_REG_TEMP, raw, sizeof(raw));
    if (ret < 0) {
        LOG_ERR("temperature read failed: %d", ret);
        return ret;
    }
    data->sample = (int16_t)sys_get_be16(raw) >> EXAMPLE_TEMP_TEMP_SHIFT;

    return 0;
}

static int example_temp_channel_get(const struct device *dev, enum sensor_channel chan,
                                    struct sensor_value *val)
{
    const struct example_temp_data *data = dev->data;

    if (chan != SENSOR_CHAN_AMBIENT_TEMP) {
        return -ENOTSUP;
    }

    return sensor_value_from_micro(val, (int64_t)data->sample * EXAMPLE_TEMP_MICROCELSIUS_PER_LSB);
}

/* DEVICE_API declares a const struct sensor_driver_api in an iterable section, which lets Zephyr
 * check the class of a device at run time. Zephyr asks for it in out-of-tree drivers since 4.1. */
static DEVICE_API(sensor, example_temp_api) = {
    .sample_fetch = example_temp_sample_fetch,
    .channel_get = example_temp_channel_get,
};

static int example_temp_init(const struct device *dev)
{
    const struct example_temp_config *config = dev->config;
    uint8_t id;
    int ret;

    /* The bus controller initialises first, because the devicetree says the part is on it. It
     * can still have failed, and init must say so rather than touch a bus that is not there. */
    if (!i2c_is_ready_dt(&config->i2c)) {
        LOG_ERR("I2C bus not ready");
        return -ENODEV;
    }

    ret = i2c_reg_read_byte_dt(&config->i2c, EXAMPLE_TEMP_REG_ID, &id);
    if (ret < 0) {
        LOG_ERR("identifier read failed: %d", ret);
        return ret;
    }
    if (id != EXAMPLE_TEMP_ID) {
        LOG_ERR("unexpected identifier 0x%02x, expected 0x%02x", id, EXAMPLE_TEMP_ID);
        return -ENODEV;
    }

    ret = i2c_reg_write_byte_dt(&config->i2c, EXAMPLE_TEMP_REG_CONFIG,
                                EXAMPLE_TEMP_CONFIG_CONTINUOUS);
    if (ret < 0) {
        LOG_ERR("configuration write failed: %d", ret);
    }

    return ret;
}

/* One data block and one config block for each enabled node. The init level and the priority
 * order this device after the bus controller. POST_KERNEL is the level of sensors that talk to
 * a bus, and CONFIG_SENSOR_INIT_PRIORITY is the priority that Zephyr's sensor drivers use. */
#define EXAMPLE_TEMP_INST(inst)                                                                    \
    static struct example_temp_data example_temp_data_##inst;                                      \
    static const struct example_temp_config example_temp_config_##inst = {                         \
        .i2c = I2C_DT_SPEC_INST_GET(inst),                                                         \
    };                                                                                             \
    SENSOR_DEVICE_DT_INST_DEFINE(inst, example_temp_init, NULL, &example_temp_data_##inst,         \
                                 &example_temp_config_##inst, POST_KERNEL,                         \
                                 CONFIG_SENSOR_INIT_PRIORITY, &example_temp_api);

DT_INST_FOREACH_STATUS_OKAY(EXAMPLE_TEMP_INST)
