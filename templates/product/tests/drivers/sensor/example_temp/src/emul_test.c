/*
 * Unit tests of the example temperature sensor driver against its emulator, on native_sim.
 *
 * What each test uses, so that a team can copy the pattern:
 *  - the emulator's sensor backend sets a temperature in SI units, as a fixed-point fraction
 *    (emul_sensor_backend_set_channel), without knowing the part's registers;
 *  - the emulator's test controls poke one register (example_temp_emul_set_reg);
 *  - the bus emulator's mock_api injects a bus error for one register. The mock answers -ENOSYS
 *    for every other transfer, and then the bus emulator hands the transfer to the model;
 *  - dev->ops.init() runs the driver's init again, to test the failures that only init can have.
 *
 * Modelled on tests/drivers/sensor/bmi160 and tests/drivers/sensor/akm09918c of Zephyr
 * (Copyright (c) 2020 Nordic Semiconductor ASA; Copyright (c) 2023 Google LLC).
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "example_temp.h"
#include "example_temp_emul.h"

#include <errno.h>
#include <inttypes.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/emul.h>
#include <zephyr/drivers/emul_sensor.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/i2c_emul.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/ztest.h>

#define EXAMPLE_TEMP_NODE DT_NODELABEL(example_temp0)

#define NO_FAILURE (-1)
#define ANY_REGISTER (-2)

/* The register whose access fails, and the error that the mock returns for it. */
static int mock_fail_reg = NO_FAILURE;
static int mock_error = -EIO;

/* Every transfer of the driver starts with a write of the register number, in a message of its
 * own, so the first byte of the first message names the register. */
static int mock_transfer(const struct emul *target, struct i2c_msg *msgs, int num_msgs, int addr)
{
    ARG_UNUSED(target);
    ARG_UNUSED(num_msgs);
    ARG_UNUSED(addr);

    if (mock_fail_reg == ANY_REGISTER ||
        (mock_fail_reg >= 0 && msgs[0].len >= 1 && msgs[0].buf[0] == (uint8_t)mock_fail_reg)) {
        return mock_error;
    }

    return -ENOSYS;
}

struct example_temp_fixture {
    const struct device *dev;
    const struct emul *emul;
    struct i2c_emul_api mock_api;
};

static void *suite_setup(void)
{
    static struct example_temp_fixture fixture = {
        .dev = DEVICE_DT_GET(EXAMPLE_TEMP_NODE),
        .emul = EMUL_DT_GET(EXAMPLE_TEMP_NODE),
        .mock_api = {.transfer = mock_transfer},
    };

    zassert_not_null(fixture.emul);
    zassert_true(emul_sensor_backend_is_supported(fixture.emul));
    return &fixture;
}

static void before_each(void *data)
{
    struct example_temp_fixture *fixture = data;

    example_temp_emul_reset(fixture->emul);
    mock_fail_reg = NO_FAILURE;
    mock_error = -EIO;
    fixture->emul->bus.i2c->mock_api = &fixture->mock_api;
}

static void after_each(void *data)
{
    struct example_temp_fixture *fixture = data;

    /* A mock that stayed installed would fail the next test of this suite or another one. */
    fixture->emul->bus.i2c->mock_api = NULL;
}

ZTEST_SUITE(example_temp, NULL, suite_setup, before_each, after_each, NULL);

/* A temperature in millidegrees Celsius as the fixed-point fraction that the emulator takes: the
 * value is q31 / 2^31 * 2^shift degrees. */
static q31_t millicelsius_to_q31(int32_t millicelsius, int8_t shift)
{
    return (q31_t)(((int64_t)millicelsius * ((int64_t)INT32_MAX + 1)) /
                   (1000 * ((int64_t)1 << shift)));
}

static void set_temperature(const struct emul *emul, int32_t millicelsius)
{
    struct sensor_chan_spec chan = {.chan_type = SENSOR_CHAN_AMBIENT_TEMP, .chan_idx = 0};
    q31_t lower;
    q31_t upper;
    q31_t epsilon;
    int8_t shift;
    q31_t value;

    zassert_ok(emul_sensor_backend_get_sample_range(emul, chan, &lower, &upper, &epsilon, &shift));
    value = millicelsius_to_q31(millicelsius, shift);
    zassert_ok(emul_sensor_backend_set_channel(emul, chan, &value, shift));
}

static int64_t read_microcelsius(const struct device *dev)
{
    struct sensor_value value;

    zassert_ok(sensor_sample_fetch(dev));
    zassert_ok(sensor_channel_get(dev, SENSOR_CHAN_AMBIENT_TEMP, &value));
    return sensor_value_to_micro(&value);
}

ZTEST_F(example_temp, test_the_device_is_ready_after_boot)
{
    zassert_true(device_is_ready(fixture->dev));
}

ZTEST_F(example_temp, test_a_fetch_before_the_first_conversion_is_busy)
{
    zassert_equal(-EBUSY, sensor_sample_fetch(fixture->dev));
}

ZTEST_F(example_temp, test_the_temperature_comes_out_in_si_units)
{
    /* The part resolves 0.0625 degrees, and every value here is a multiple of it, so the
     * conversion in both directions is exact and the tolerance below is a safety margin. */
    static const int32_t millicelsius[] = {25000, 0, -40000, 100000, -125000, 127875, 1125, -1125};

    for (size_t i = 0; i < ARRAY_SIZE(millicelsius); i++) {
        int64_t microcelsius;

        set_temperature(fixture->emul, millicelsius[i]);
        microcelsius = read_microcelsius(fixture->dev);
        /* One step of the part is the largest error that the conversion may add. */
        zassert_within(microcelsius, (int64_t)millicelsius[i] * 1000,
                       EXAMPLE_TEMP_MICROCELSIUS_PER_LSB, "%d mC read as %" PRId64 " uC",
                       millicelsius[i], microcelsius);
    }
}

ZTEST_F(example_temp, test_a_value_outside_the_range_of_the_part_is_refused)
{
    struct sensor_chan_spec chan = {.chan_type = SENSOR_CHAN_AMBIENT_TEMP, .chan_idx = 0};
    q31_t value = millicelsius_to_q31(130000, 8);

    zassert_equal(-ERANGE, emul_sensor_backend_set_channel(fixture->emul, chan, &value, 8));
}

ZTEST_F(example_temp, test_a_channel_that_the_part_does_not_have_is_not_supported)
{
    zassert_equal(-ENOTSUP, sensor_sample_fetch_chan(fixture->dev, SENSOR_CHAN_HUMIDITY));
    zassert_equal(-ENOTSUP, sensor_channel_get(fixture->dev, SENSOR_CHAN_HUMIDITY,
                                               &(struct sensor_value){0}));
}

ZTEST_F(example_temp, test_a_bus_error_on_the_status_register_fails_the_fetch)
{
    set_temperature(fixture->emul, 20000);
    mock_fail_reg = EXAMPLE_TEMP_REG_STATUS;

    zassert_equal(-EIO, sensor_sample_fetch(fixture->dev));
}

ZTEST_F(example_temp, test_a_bus_error_on_the_temperature_register_keeps_the_last_sample)
{
    struct sensor_value value;

    set_temperature(fixture->emul, 20000);
    zassert_equal(20000000, read_microcelsius(fixture->dev));

    set_temperature(fixture->emul, 30000);
    mock_fail_reg = EXAMPLE_TEMP_REG_TEMP;
    mock_error = -ETIMEDOUT;
    zassert_equal(-ETIMEDOUT, sensor_sample_fetch(fixture->dev));

    /* The failed fetch did not touch the stored sample. */
    zassert_ok(sensor_channel_get(fixture->dev, SENSOR_CHAN_AMBIENT_TEMP, &value));
    zassert_equal(20000000, sensor_value_to_micro(&value));
}

ZTEST_F(example_temp, test_init_checks_the_part_identifier)
{
    example_temp_emul_set_reg(fixture->emul, EXAMPLE_TEMP_REG_ID, 0x00);

    zassert_equal(-ENODEV, fixture->dev->ops.init(fixture->dev));

    example_temp_emul_set_reg(fixture->emul, EXAMPLE_TEMP_REG_ID, EXAMPLE_TEMP_ID);
    zassert_ok(fixture->dev->ops.init(fixture->dev));
}

ZTEST_F(example_temp, test_init_fails_on_a_bus_error_when_it_reads_the_identifier)
{
    mock_fail_reg = EXAMPLE_TEMP_REG_ID;

    zassert_equal(-EIO, fixture->dev->ops.init(fixture->dev));
}

ZTEST_F(example_temp, test_init_fails_on_a_bus_error_when_it_writes_the_configuration)
{
    mock_fail_reg = EXAMPLE_TEMP_REG_CONFIG;

    zassert_equal(-EIO, fixture->dev->ops.init(fixture->dev));
}

ZTEST_F(example_temp, test_init_writes_the_configuration_the_driver_needs)
{
    example_temp_emul_set_reg(fixture->emul, EXAMPLE_TEMP_REG_CONFIG, 0x00);

    zassert_ok(fixture->dev->ops.init(fixture->dev));
    zassert_equal(EXAMPLE_TEMP_CONFIG_CONTINUOUS,
                  example_temp_emul_get_reg(fixture->emul, EXAMPLE_TEMP_REG_CONFIG));
}
