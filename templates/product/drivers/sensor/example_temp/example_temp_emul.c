/*
 * Emulator of the fictional example temperature sensor: a model of its registers behind Zephyr's
 * I2C emulator, with the common sensor backend so that tests can set a temperature in SI units.
 * It runs on native_sim and answers only what the driver needs. Any other transfer is refused, so
 * that a driver change that adds a transfer shows up in the tests.
 *
 * Modelled on drivers/sensor/f75303/f75303_emul.c of Zephyr (Copyright (c) 2023 Google LLC).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#define DT_DRV_COMPAT vnd_example_temp

#include "example_temp_emul.h"
#include "example_temp.h"

#include <errno.h>
#include <string.h>
#include <zephyr/device.h>
#include <zephyr/drivers/emul.h>
#include <zephyr/drivers/emul_sensor.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/i2c_emul.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>

LOG_MODULE_DECLARE(example_temp, CONFIG_EXAMPLE_TEMP_LOG_LEVEL);

#define EXAMPLE_TEMP_EMUL_NUM_REGS 16

struct example_temp_emul_data {
    uint8_t reg[EXAMPLE_TEMP_EMUL_NUM_REGS];
};

void example_temp_emul_set_reg(const struct emul *target, uint8_t reg, uint8_t val)
{
    struct example_temp_emul_data *data = target->data;

    __ASSERT_NO_MSG(reg < EXAMPLE_TEMP_EMUL_NUM_REGS);
    data->reg[reg] = val;
}

uint8_t example_temp_emul_get_reg(const struct emul *target, uint8_t reg)
{
    struct example_temp_emul_data *data = target->data;

    __ASSERT_NO_MSG(reg < EXAMPLE_TEMP_EMUL_NUM_REGS);
    return data->reg[reg];
}

void example_temp_emul_reset(const struct emul *target)
{
    struct example_temp_emul_data *data = target->data;

    memset(data->reg, 0, sizeof(data->reg));
    data->reg[EXAMPLE_TEMP_REG_ID] = EXAMPLE_TEMP_ID;
}

/* The device keeps a register pointer, as many parts do: a write of one byte sets it, a read
 * starts there and the pointer moves on with each byte. The driver always sets the pointer and
 * reads in two messages (a write, then a read), or writes the pointer and one value in one. */
static int example_temp_emul_transfer_i2c(const struct emul *target, struct i2c_msg *msgs,
                                          int num_msgs, int addr)
{
    unsigned int reg;

    __ASSERT_NO_MSG(msgs && num_msgs);

    i2c_dump_msgs_rw(target->dev, msgs, num_msgs, addr, false);

    if (num_msgs == 1 && (msgs[0].flags & I2C_MSG_READ) == 0 && msgs[0].len >= 2) {
        reg = msgs[0].buf[0];
        for (uint32_t i = 1; i < msgs[0].len; i++, reg++) {
            if (reg >= EXAMPLE_TEMP_EMUL_NUM_REGS) {
                LOG_ERR("write past the last register");
                return -EIO;
            }
            if (reg == EXAMPLE_TEMP_REG_CONFIG) {
                example_temp_emul_set_reg(target, reg, msgs[0].buf[i]);
            } else {
                LOG_ERR("write to read-only register 0x%02x", reg);
                return -EIO;
            }
        }
        return 0;
    }

    if (num_msgs == 2 && (msgs[0].flags & I2C_MSG_READ) == 0 && msgs[0].len == 1 &&
        (msgs[1].flags & I2C_MSG_READ) != 0) {
        reg = msgs[0].buf[0];
        for (uint32_t i = 0; i < msgs[1].len; i++, reg++) {
            if (reg >= EXAMPLE_TEMP_EMUL_NUM_REGS) {
                LOG_ERR("read past the last register");
                return -EIO;
            }
            msgs[1].buf[i] = example_temp_emul_get_reg(target, reg);
        }
        return 0;
    }

    LOG_ERR("unexpected transfer of %d messages", num_msgs);
    return -EIO;
}

static int example_temp_emul_init(const struct emul *target, const struct device *parent)
{
    ARG_UNUSED(parent);

    example_temp_emul_reset(target);
    return 0;
}

static int example_temp_emul_set_channel(const struct emul *target, struct sensor_chan_spec ch,
                                         const q31_t *value, int8_t shift)
{
    int64_t scaled;
    int64_t microcelsius;
    int32_t sample;
    uint16_t word;

    if (ch.chan_type != SENSOR_CHAN_AMBIENT_TEMP) {
        return -ENOTSUP;
    }

    /* The value is a fraction of 2^shift degrees Celsius: value / 2^31 * 2^shift. */
    scaled = (int64_t)*value * ((int64_t)1 << shift);
    microcelsius = scaled * 1000000 / ((int64_t)INT32_MAX + 1);
    sample = microcelsius / EXAMPLE_TEMP_MICROCELSIUS_PER_LSB;
    if (sample < -2048 || sample > 2047) {
        return -ERANGE;
    }

    word = (uint16_t)(sample * (1 << EXAMPLE_TEMP_TEMP_SHIFT));
    example_temp_emul_set_reg(target, EXAMPLE_TEMP_REG_TEMP, word >> 8);
    example_temp_emul_set_reg(target, EXAMPLE_TEMP_REG_TEMP + 1, word & 0xff);
    example_temp_emul_set_reg(target, EXAMPLE_TEMP_REG_STATUS, EXAMPLE_TEMP_STATUS_DRDY);

    return 0;
}

static int example_temp_emul_get_sample_range(const struct emul *target, struct sensor_chan_spec ch,
                                              q31_t *lower, q31_t *upper, q31_t *epsilon,
                                              int8_t *shift)
{
    ARG_UNUSED(target);

    if (ch.chan_type != SENSOR_CHAN_AMBIENT_TEMP) {
        return -ENOTSUP;
    }

    /* A 12-bit two's complement number in steps of 0.0625 degrees: -128 up to 127.9375. */
    *shift = 8;
    *lower = (int64_t)(-128.0 * ((int64_t)INT32_MAX + 1)) >> *shift;
    *upper = (int64_t)(127.9375 * ((int64_t)INT32_MAX + 1)) >> *shift;
    *epsilon = (int64_t)(0.0625 * ((int64_t)INT32_MAX + 1)) >> *shift;

    return 0;
}

static const struct i2c_emul_api example_temp_emul_api_i2c = {
    .transfer = example_temp_emul_transfer_i2c,
};

static const struct emul_sensor_driver_api example_temp_emul_api_sensor = {
    .set_channel = example_temp_emul_set_channel,
    .get_sample_range = example_temp_emul_get_sample_range,
};

#define EXAMPLE_TEMP_EMUL(inst)                                                                    \
    static struct example_temp_emul_data example_temp_emul_data_##inst;                            \
    EMUL_DT_INST_DEFINE(inst, example_temp_emul_init, &example_temp_emul_data_##inst, NULL,        \
                        &example_temp_emul_api_i2c, &example_temp_emul_api_sensor)

DT_INST_FOREACH_STATUS_OKAY(EXAMPLE_TEMP_EMUL)
