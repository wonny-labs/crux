/* SPDX-License-Identifier: Apache-2.0
 *
 * What Zephyr's TCP stack does when it cannot make an RFC 6528 initial sequence number, in a
 * default Crux image (patches/zephyr/tcp-isn-fail-closed.patch).
 *
 * tcp_init_isn() (subsys/net/ip/tcp.c of Zephyr v4.5.0) hashes a 16-byte key, read from
 * sys_csrand_get() until a read works, with the connection's addresses and ports. Upstream falls
 * back to sys_rand32_get(), which is not cryptographically secure, when the read or the hash fails.
 * With the patch both ways to make a sequence number refuse instead:
 *   - passive: a SYN to a listening port gets a RST, and no connection is created,
 *   - active:  net_context_connect() returns the error, and no SYN is sent,
 * and the next attempt tries again, so a read or a hash that works again gives a keyed number.
 *
 * The test is one scenario, in order, because the key is kept once a read works:
 *   (A) the key read fails; (B) it works; (C) the hash fails; (D) it works again.
 * Each phase sends a SYN to a listening port and makes a connect. It runs on a dummy interface: the
 * test injects the peer's SYN with net_recv_data() and reads what the stack sends in the device's
 * send function. It uses expectations, not assertions, so that the negative control on upstream
 * tcp.c reports everything it sees.
 *
 * sys_csrand_get() is Zephyr's own, over a test entropy device (src/test_entropy.c) whose reads
 * fail on request. The hash fails through a link-time wrap of psa_hash_compute() (CMakeLists.txt).
 *
 * The packet building follows tests/net/tcp of Zephyr (Apache-2.0, Intel Corporation).
 */
#include <errno.h>
#include <stdio.h>
#include <string.h>

#include <psa/crypto.h>
#include <zephyr/kernel.h>
#include <zephyr/net/dummy.h>
#include <zephyr/net/net_context.h>
#include <zephyr/net/net_if.h>
#include <zephyr/net/net_pkt.h>
#include <zephyr/random/random.h>
#include <zephyr/ztest.h>

#include "ipv4.h"
#include "test_entropy.h"

#define TCP_SYN 0x02
#define TCP_RST 0x04
#define TCP_ACK 0x10

#define LISTEN_PORT 4242

/* Longer than the stack keeps a half-open connection with this configuration (prj.conf: 100 ms and
 * 2 retries, so 350 ms). */
#define HALF_OPEN_EXPIRY K_SECONDS(1)

static struct net_in_addr my_addr = {{{192, 0, 2, 1}}};
static struct net_in_addr peer_addr = {{{192, 0, 2, 2}}};

/* ---- the injected hash failure ------------------------------------------------------------- */

psa_status_t __real_psa_hash_compute(psa_algorithm_t alg, const uint8_t *input, size_t input_length,
                                     uint8_t *hash, size_t hash_size, size_t *hash_length);
psa_status_t __wrap_psa_hash_compute(psa_algorithm_t alg, const uint8_t *input, size_t input_length,
                                     uint8_t *hash, size_t hash_size, size_t *hash_length);

static volatile bool fail_hash;
static unsigned int failed_hashes;

psa_status_t __wrap_psa_hash_compute(psa_algorithm_t alg, const uint8_t *input, size_t input_length,
                                     uint8_t *hash, size_t hash_size, size_t *hash_length)
{
    if (fail_hash) {
        failed_hashes++;
        *hash_length = 0;
        return PSA_ERROR_HARDWARE_FAILURE;
    }
    return __real_psa_hash_compute(alg, input, input_length, hash, hash_size, hash_length);
}

/* ---- the dummy interface and the capture of what the stack sends --------------------------- */

struct seen {
    uint8_t flags;
    uint32_t seq;
    uint16_t sport; /* as in the packet */
    uint16_t dport;
};

static struct net_if *iface;
static struct seen last_sent;
static volatile uint16_t want_dport; /* network order */
static K_SEM_DEFINE(sent_sem, 0, 16);

static int tester_send(const struct device *dev, struct net_pkt *pkt)
{
    struct net_tcp_hdr th;

    ARG_UNUSED(dev);
    if (net_pkt_family(pkt) != NET_AF_INET || NET_IPV4_HDR(pkt)->proto != NET_IPPROTO_TCP) {
        return 0;
    }
    net_pkt_cursor_init(pkt);
    net_pkt_set_overwrite(pkt, true);
    if (net_pkt_skip(pkt, net_pkt_ip_hdr_len(pkt) + net_pkt_ip_opts_len(pkt)) < 0 ||
        net_pkt_read(pkt, &th, sizeof(th)) < 0) {
        return -EINVAL;
    }
    net_pkt_cursor_init(pkt);

    /* Only the packet of the attempt under test counts: a half-open connection of an earlier
     * phase retransmits its SYN|ACK or SYN to another peer port. */
    if (th.dst_port != want_dport) {
        return 0;
    }
    last_sent.flags = th.flags;
    last_sent.seq = sys_get_be32(th.seq);
    last_sent.sport = th.src_port;
    last_sent.dport = th.dst_port;
    k_sem_give(&sent_sem);
    return 0;
}

static int dev_init(const struct device *dev)
{
    ARG_UNUSED(dev);
    return 0;
}

static void iface_init(struct net_if *net_if)
{
    static uint8_t mac[6] = {0x00, 0x00, 0x5E, 0x00, 0x53, 0x01};

    net_if_set_link_addr(net_if, mac, sizeof(mac), NET_LINK_ETHERNET);
}

static struct dummy_api tester_api = {
    .iface_api.init = iface_init,
    .send = tester_send,
};

NET_DEVICE_INIT(crux_tcp_isn_test, "crux_tcp_isn_test", dev_init, NULL, NULL, NULL,
                CONFIG_KERNEL_INIT_PRIORITY_DEFAULT, &tester_api, DUMMY_L2,
                NET_L2_GET_CTX_TYPE(DUMMY_L2), 127);

/* A SYN from the peer to the listening port. */
static int inject_syn(uint16_t peer_port)
{
    NET_PKT_DATA_ACCESS_DEFINE(access, struct net_tcp_hdr);
    struct net_tcp_hdr *th;
    struct net_pkt *pkt;
    int ret;

    pkt = net_pkt_alloc_with_buffer(iface, sizeof(struct net_tcp_hdr), NET_AF_INET, NET_IPPROTO_TCP,
                                    K_NO_WAIT);
    if (pkt == NULL) {
        return -ENOMEM;
    }
    ret = net_ipv4_create(pkt, &peer_addr, &my_addr);
    th = ret < 0 ? NULL : (struct net_tcp_hdr *)net_pkt_get_data(pkt, &access);
    if (th == NULL) {
        net_pkt_unref(pkt);
        return -EINVAL;
    }
    memset(th, 0, sizeof(*th));
    th->src_port = net_htons(peer_port);
    th->dst_port = net_htons(LISTEN_PORT);
    th->offset = 5U << 4;
    th->flags = TCP_SYN;
    sys_put_be32(1000U, th->seq);
    sys_put_be16(1280U, th->wnd);
    if (net_pkt_set_data(pkt, &access) < 0) {
        net_pkt_unref(pkt);
        return -EINVAL;
    }
    net_pkt_cursor_init(pkt);
    if (net_ipv4_finalize(pkt, NET_IPPROTO_TCP) < 0) {
        net_pkt_unref(pkt);
        return -EINVAL;
    }
    ret = net_recv_data(iface, pkt);
    if (ret < 0) {
        net_pkt_unref(pkt);
    }
    return ret;
}

/* ---- what a key would give ------------------------------------------------------------------ */

/* The key that the test entropy device gives to a read of 16 bytes (src/test_entropy.c). */
static void device_key(uint8_t key[16])
{
    for (unsigned int index = 0; index < 16U; ++index) {
        key[index] = (uint8_t)(0xA5U ^ (index * 37U));
    }
}

/* The hash of tcpv4_isn_hash() (subsys/net/ip/tcp.c) for this key, these addresses and these ports
 * (as the stack stores them: the ports in network order). The stack then adds the uptime, in 64 ns
 * steps, in seq_scale().
 */
static uint32_t key_hash(const uint8_t key[16], const struct net_in_addr *saddr,
                         const struct net_in_addr *daddr, uint16_t sport, uint16_t dport)
{
    struct {
        uint8_t key[16];
        struct net_in_addr saddr;
        struct net_in_addr daddr;
        uint16_t sport;
        uint16_t dport;
    } buf = {.saddr = *saddr, .daddr = *daddr, .sport = sport, .dport = dport};
    uint8_t hash[PSA_HASH_LENGTH(PSA_ALG_SHA_256)];
    size_t length = 0;
    uint32_t word;
    psa_status_t status;

    memcpy(buf.key, key, sizeof(buf.key));
    status = psa_hash_compute(PSA_ALG_SHA_256, (const uint8_t *)&buf, sizeof(buf), hash,
                              sizeof(hash), &length);
    zassert_equal(status, PSA_SUCCESS, "psa_hash_compute: %d", (int)status);
    memcpy(&word, hash, sizeof(word));
    return word;
}

/* seq_scale() of Zephyr v4.5.0: the uptime in 64 ns steps, in 32 bits. */
static uint32_t uptime_scale(void)
{
    return (uint32_t)(k_ticks_to_ns_floor64(k_uptime_ticks()) >> 6);
}

/* Whether isn is the hash plus an uptime between the two readings. */
static bool is_hash_plus_uptime(uint32_t isn, uint32_t hash, uint32_t before, uint32_t after)
{
    uint32_t delta = isn - hash;

    /* The counter wraps after about 275 s: a window that wraps is accepted on either side. */
    return before <= after ? (delta >= before && delta <= after)
                           : (delta >= before || delta <= after);
}

/* ---- the scenario --------------------------------------------------------------------------- */

enum isn_kind {
    ISN_NONE,    /* nothing was sent, or no SYN */
    ISN_KEYED,   /* hash of the key that the device gave, plus the uptime */
    ISN_UNKEYED, /* not made from that key: the sys_rand32_get() fallback */
};

struct outcome {
    bool replied;
    uint8_t flags;
    enum isn_kind kind;
};

/* For a connection that a SYN opened, tcp_conn_new() hashes with the port that net_context_bind()
 * chose for the new context: the test cannot know it, so any_sport tries every port.
 */
static bool made_from_key(uint32_t isn, uint16_t sport, bool any_sport, uint16_t dport,
                          uint32_t before, uint32_t after)
{
    uint8_t key[16];

    device_key(key);
    if (!any_sport) {
        return is_hash_plus_uptime(isn, key_hash(key, &my_addr, &peer_addr, sport, dport), before,
                                   after);
    }
    for (uint32_t port = 0; port <= UINT16_MAX; ++port) {
        if (is_hash_plus_uptime(isn, key_hash(key, &my_addr, &peer_addr, (uint16_t)port, dport),
                                before, after)) {
            return true;
        }
    }
    return false;
}

static const char *flag_name(uint8_t flags)
{
    if ((flags & (TCP_SYN | TCP_ACK)) == (TCP_SYN | TCP_ACK)) {
        return "SYN|ACK";
    } else if ((flags & TCP_SYN) != 0) {
        return "SYN";
    } else if ((flags & TCP_RST) != 0) {
        return (flags & TCP_ACK) != 0 ? "RST|ACK" : "RST";
    }
    return "other";
}

static const char *kind_name(const struct outcome *out)
{
    switch (out->kind) {
    case ISN_KEYED:
        return "keyed";
    case ISN_UNKEYED:
        return "unkeyed";
    default:
        return "-";
    }
}

static unsigned int accepted;

static void accept_cb(struct net_context *context, struct net_sockaddr *addr, net_socklen_t addrlen,
                      int status, void *user_data)
{
    ARG_UNUSED(addr);
    ARG_UNUSED(addrlen);
    ARG_UNUSED(status);
    ARG_UNUSED(user_data);
    accepted++;
    net_context_put(context);
}

/* A SYN to the listening port: what did the stack send back? The hash failure, when asked for,
 * lasts until the stack has answered, so that the test's own hash below is not refused.
 */
static struct outcome passive(uint16_t peer_port, bool hash_fails)
{
    struct outcome out = {0};
    uint32_t before;
    uint32_t after;
    bool replied;

    /* A half-open connection of an earlier phase holds a place in the listener's backlog until it
     * times out, and with the backlog full the stack drops a SYN without an answer. Upstream tcp.c
     * opens one in every phase, so wait for the earlier ones to end. */
    k_sleep(HALF_OPEN_EXPIRY);
    want_dport = net_htons(peer_port);
    k_sem_reset(&sent_sem);
    before = uptime_scale();
    fail_hash = hash_fails;
    zassert_ok(inject_syn(peer_port), "inject the SYN");
    replied = k_sem_take(&sent_sem, K_MSEC(300)) == 0;
    fail_hash = false;
    if (replied) {
        after = uptime_scale();
        out.replied = true;
        out.flags = last_sent.flags;
        if ((out.flags & TCP_SYN) != 0) {
            out.kind = made_from_key(last_sent.seq, 0, true, net_htons(peer_port), before, after)
                           ? ISN_KEYED
                           : ISN_UNKEYED;
        }
    }
    return out;
}

/* A connect to the peer: did the stack send a SYN, and what did connect return? */
static struct outcome active(uint16_t port, bool hash_fails, int *connect_result)
{
    struct net_sockaddr_in peer = {
        .sin_family = NET_AF_INET, .sin_port = net_htons(port), .sin_addr = peer_addr};
    struct outcome out = {0};
    struct net_context *context;
    uint32_t before;
    uint32_t after;

    zassert_ok(net_context_get(NET_AF_INET, NET_SOCK_STREAM, NET_IPPROTO_TCP, &context),
               "net_context_get");
    want_dport = net_htons(port);
    k_sem_reset(&sent_sem);
    before = uptime_scale();
    fail_hash = hash_fails;
    *connect_result = net_context_connect(context, (struct net_sockaddr *)&peer, sizeof(peer), NULL,
                                          K_NO_WAIT, NULL);
    fail_hash = false;
    if (k_sem_take(&sent_sem, K_MSEC(300)) == 0) {
        after = uptime_scale();
        out.replied = true;
        out.flags = last_sent.flags;
        if ((out.flags & TCP_SYN) != 0) {
            out.kind =
                made_from_key(last_sent.seq, last_sent.sport, false, last_sent.dport, before, after)
                    ? ISN_KEYED
                    : ISN_UNKEYED;
        }
    }
    net_context_put(context);
    k_sleep(K_MSEC(50));
    return out;
}

static void report(const char *phase, const char *path, const struct outcome *out,
                   const int *connect_result)
{
    printf("ISN-REPORT phase=%s path=%s sent=%s isn=%s connect=", phase, path,
           out->replied ? flag_name(out->flags) : "nothing", kind_name(out));
    if (connect_result != NULL) {
        printf("%d\n", *connect_result);
    } else {
        printf("-\n");
    }
}

/* A phase that cannot make a sequence number: the SYN must get a RST and the connect must fail
 * without a SYN.
 */
static void expect_refused(const char *phase, uint16_t peer_port, uint16_t port, bool hash_fails)
{
    unsigned int accepted_before = accepted;
    struct outcome out;
    int connect_result;

    out = passive(peer_port, hash_fails);
    report(phase, "passive", &out, NULL);
    zexpect_true(out.replied && (out.flags & TCP_RST) != 0 && (out.flags & TCP_SYN) == 0,
                 "%s passive: the SYN must get a RST, not a SYN|ACK (sent %s, isn %s)", phase,
                 out.replied ? flag_name(out.flags) : "nothing", kind_name(&out));
    zexpect_equal(accepted, accepted_before, "%s passive: no connection must be accepted", phase);

    out = active(port, hash_fails, &connect_result);
    report(phase, "active", &out, &connect_result);
    zexpect_equal(connect_result, -EIO, "%s active: net_context_connect() must return -EIO, not %d",
                  phase, connect_result);
    zexpect_false(out.replied, "%s active: no SYN must be sent (sent %s, isn %s)", phase,
                  out.replied ? flag_name(out.flags) : "nothing", kind_name(&out));
}

/* A phase that can make a sequence number: both paths must work, with a keyed number. */
static void expect_keyed(const char *phase, uint16_t peer_port, uint16_t port)
{
    struct outcome out;
    int connect_result;

    out = passive(peer_port, false);
    report(phase, "passive", &out, NULL);
    zexpect_true(out.replied && (out.flags & (TCP_SYN | TCP_ACK)) == (TCP_SYN | TCP_ACK),
                 "%s passive: the SYN must get a SYN|ACK (sent %s)", phase,
                 out.replied ? flag_name(out.flags) : "nothing");
    zexpect_equal(out.kind, ISN_KEYED, "%s passive: the number must be made from the key (got %s)",
                  phase, kind_name(&out));

    out = active(port, false, &connect_result);
    report(phase, "active", &out, &connect_result);
    zexpect_true(connect_result == -EINPROGRESS || connect_result == 0,
                 "%s active: connect gave %d", phase, connect_result);
    zexpect_true(out.replied && (out.flags & TCP_SYN) != 0, "%s active: a SYN must be sent", phase);
    zexpect_equal(out.kind, ISN_KEYED, "%s active: the number must be made from the key (got %s)",
                  phase, kind_name(&out));
}

ZTEST(tcp_isn, test_scenario)
{
    struct net_sockaddr_in listen_addr = {
        .sin_family = NET_AF_INET, .sin_port = net_htons(LISTEN_PORT), .sin_addr = my_addr};
    struct net_context *listener;
    unsigned int reads_before;

    zassert_ok(net_context_get(NET_AF_INET, NET_SOCK_STREAM, NET_IPPROTO_TCP, &listener),
               "listener");
    zassert_ok(net_context_bind(listener, (struct net_sockaddr *)&listen_addr, sizeof(listen_addr)),
               "bind");
    zassert_ok(net_context_listen(listener, 2), "listen");
    zassert_ok(net_context_accept(listener, accept_cb, K_NO_WAIT, NULL), "accept");

    /* (A) The key read fails. */
    crux_test_entropy_result = -EIO;
    reads_before = crux_test_entropy_reads();
    expect_refused("A-read-fails", 50001, 8001, false);
    printf("ISN-REPORT phase=A-read-fails entropy-reads=%u\n",
           crux_test_entropy_reads() - reads_before);
    zexpect_true(crux_test_entropy_reads() > reads_before, "A: the key read was not attempted");

    /* (B) The read works again: the next attempt reads the key and uses it. */
    crux_test_entropy_result = 0;
    expect_keyed("B-read-works", 50002, 8002);

    /* (C) The key is kept, and the hash fails. */
    expect_refused("C-hash-fails", 50003, 8003, true);
    printf("ISN-REPORT phase=C-hash-fails hash-failures=%u\n", failed_hashes);
    zexpect_true(failed_hashes >= 2U, "C: the hash failure did not reach tcp.c (%u)",
                 failed_hashes);

    /* (D) The hash works again. */
    expect_keyed("D-hash-works", 50004, 8004);

    printf("ISN-REPORT accepted=%u\n", accepted);
}

static void *suite_setup(void)
{
    static struct net_in_addr addr_copy;

    /* The boot-time initialisation may have run before the entropy device was ready. The device
     * works here. */
    zassert_equal(psa_crypto_init(), PSA_SUCCESS, "psa_crypto_init");
    iface = net_if_get_first_by_type(&NET_L2_GET_NAME(DUMMY));
    zassert_not_null(iface, "interface");
    addr_copy = my_addr;
    zassert_not_null(net_if_ipv4_addr_add(iface, &addr_copy, NET_ADDR_MANUAL, 0), "address");
    return NULL;
}

ZTEST_SUITE(tcp_isn, NULL, suite_setup, NULL, NULL, NULL);
