/* The product's access policy: which roles exist and what each may do. Plain C data with no
 * operating system in it, so the Host can build it. It names public Crux types only. */
#ifndef CONSUMER_PRODUCT_POLICY_H
#define CONSUMER_PRODUCT_POLICY_H

#include <crux/access.h>

#define PRODUCT_ROLE_ADMINISTRATOR "administrator"
#define PRODUCT_ROLE_GUEST "guest"
/* A permission that the product names and no Crux service does. */
#define PRODUCT_PERMISSION_DEMO "product.demo"

const crux_access_policy_t *product_policy(void);

#endif
