/* SPDX-License-Identifier: Apache-2.0 */
/* The composition of the management services of this image, in the boot order of
 * docs/management-in-a-product.md. main.c calls the steps and decides what a failure means; every
 * step prints its own name when it fails. */
#ifndef COMPOSITION_H
#define COMPOSITION_H

#include <crux/credential_store.h>
#include <crux/tls_certificate.h>

#include <stdbool.h>
#include <stddef.h>

/* The static address of the interface, from CONFIG_CRUX_MBED_MGMT_IPV4_ADDRESS and _NETMASK: set
 * before any listener starts. The interface has that address and no other IPv4 address afterwards,
 * which this function checks. */
bool composition_address_up(void);

/* Events, time, the file medium and the credential store, Access, the Configuration service with
 * the network settings entries, status and the event thread. Nothing that needs the first account
 * or a key. */
bool composition_core_start(void);

/* The state the credential store was in when it started: EMPTY means no account exists yet. */
crux_credential_state_t composition_store_state_at_start(void);

/* The services that need the store, Access and the events: the TLS certificate (the device key is
 * made here), network settings, the file service, reboot, the web session and management cores, the
 * certificate's registration with Zephyr's TLS credentials, and the HTTPS listener last. */
bool composition_services_start(void);

/* Whether the certificate was generated at this boot (always, on a RAM disk), and its SHA-256
 * fingerprint text. */
bool composition_certificate_generated(void);
bool composition_certificate_fingerprint(char text[CRUX_TLS_CERTIFICATE_FINGERPRINT_TEXT_SIZE]);

#if defined(CONFIG_CRUX_MBED_MGMT_TEST_FIRST_ACCOUNT)
/* TEST ONLY (first_account_test.c): creates the first account `admin` from the embedded password.
 */
bool composition_first_account_test(void);
#endif

#endif
