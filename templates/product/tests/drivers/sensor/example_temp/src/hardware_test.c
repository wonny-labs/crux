/*
 * The hardware scenario of the example temperature sensor: the same driver with the part wired on
 * a board. The part is fictional, so in this template the scenario is a stub that is built and
 * never run. It shows the shape that a product copies for a real part.
 *
 * The scenario is gated on the Twister fixture "example_temp_wired" (see testcase.yaml). Without
 * that fixture on the command line, Twister builds the image and does not run it, and CI does not
 * run it either. With it, a run is a hardware operation: it needs authorisation for the task, a
 * verified board, probe and flash configuration, and a safe setup. In this repository the route
 * is the device-control tool, which gates every flash and reset, and not a Twister launch of the
 * hardware type, which flashes on every launch. The guide docs/writing-a-product-driver.md says
 * more.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <errno.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/ztest.h>

/* The node comes from the board (example_rt1062) or from the overlay of the vendor board. */
static const struct device *const sensor = DEVICE_DT_GET_ANY(vnd_example_temp);

/* A room-temperature bench. A real scenario takes the limits from the setup that it describes. */
#define BENCH_MIN_MICROCELSIUS (-10LL * 1000000)
#define BENCH_MAX_MICROCELSIUS (60LL * 1000000)
#define CONVERSION_TRIES 10

ZTEST_SUITE(example_temp_hardware, NULL, NULL, NULL, NULL, NULL);

ZTEST(example_temp_hardware, test_the_wired_part_reports_a_plausible_temperature)
{
    struct sensor_value value;
    int ret = -EBUSY;

    zassert_not_null(sensor, "no enabled vnd,example-temp node");
    zassert_true(device_is_ready(sensor), "the part did not answer at init: is it wired?");

    /* The first conversion takes a moment after power-on. */
    for (int i = 0; i < CONVERSION_TRIES && ret == -EBUSY; i++) {
        ret = sensor_sample_fetch(sensor);
        if (ret == -EBUSY) {
            k_msleep(100);
        }
    }
    zassert_ok(ret);
    zassert_ok(sensor_channel_get(sensor, SENSOR_CHAN_AMBIENT_TEMP, &value));
    zassert_between_inclusive(sensor_value_to_micro(&value), BENCH_MIN_MICROCELSIUS,
                              BENCH_MAX_MICROCELSIUS);
}
