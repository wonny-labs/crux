#ifndef CT_TEST_FAULT_GPIO_H
#define CT_TEST_FAULT_GPIO_H

#include <stdbool.h>
void controller_test_gpio_value(int raw);
void controller_test_gpio_fail_read(bool fail);

#endif
