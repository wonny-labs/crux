/* Two things this test image does at the socket call that the server makes.
 *
 * The server's inactivity timer closes a client with zsock_shutdown(), and the native socket
 * offload at v4.5.0 has no shutdown operation, so there the call fails and the timer does nothing.
 * This gives the timer the effect it has on Zephyr's own TCP stack, so that the measurements mean
 * something.
 *
 * The offload's send waits out a timeout and then sends anyway, so the server rarely sees -EAGAIN,
 * which it swallows and which leaves a client held. A probe route can make one chosen send return
 * it, and can shrink a socket's send buffer, as on a small target.
 *
 * Over TLS the server's descriptor is a TLS socket, which holds the offloaded one, and the TLS
 * layer calls these again for it. A shutdown goes on to that socket, a send counts and fails only
 * at the outermost call, which is the server's, and a send buffer applies to the offloaded socket.
 *
 * It is here and not in the adapter because a product does not use the offload.
 */
#include "web_probe.h"

#include <errno.h>
#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>
#include <zephyr/sys/fdtable.h>

#if defined(CONFIG_NET_SOCKETS_SOCKOPT_TLS)
bool net_socket_is_tls(void *obj);
#else
#define net_socket_is_tls(obj) false
#endif

int web_host_shutdown(int host_fd, int how);
int web_host_set_send_buffer(int host_fd, int size);
int __real_z_impl_zsock_shutdown(int sock, int how);
int __wrap_z_impl_zsock_shutdown(int sock, int how);
ssize_t __real_z_impl_zsock_sendto(int sock, const void *buf, size_t len, int flags,
                                   const struct net_sockaddr *dest_addr, net_socklen_t addrlen);
ssize_t __wrap_z_impl_zsock_sendto(int sock, const void *buf, size_t len, int flags,
                                   const struct net_sockaddr *dest_addr, net_socklen_t addrlen);
ssize_t __real_z_impl_zsock_sendmsg(int sock, const struct net_msghdr *msg, int flags);
ssize_t __wrap_z_impl_zsock_sendmsg(int sock, const struct net_msghdr *msg, int flags);

/* The start of the driver's private struct nsos_socket at v4.5.0, up to the host descriptor. A
 * wrong layout makes the host call fail, and the driver's inactivity cases then fail. */
struct nsos_socket_start {
    int fd;
    k_timeout_t recv_timeout;
    k_timeout_t send_timeout;
    struct {
        int fd;
        short events;
        short revents;
        void (*cb)(void *pollfd_mid);
    } poll_mid;
};

static bool fail_armed;
static unsigned fail_skip;
static int shrink_size;
static unsigned eagain_count;
static unsigned send_depth;
static unsigned outer_sends;
static unsigned inner_sends;
static unsigned real_eagain;

int __wrap_z_impl_zsock_shutdown(int sock, int how)
{
    const struct nsos_socket_start *socket = zvfs_get_fd_obj(sock, NULL, EBADF);

    if (socket == NULL) {
        return -1;
    }
    if (net_socket_is_tls((void *)socket)) {
        return __real_z_impl_zsock_shutdown(sock, how);
    }
    return web_host_shutdown(socket->poll_mid.fd, how);
}

/* Counts one send. A piece (one sendmsg() of a response, from Zephyr v4.5.0) may be made to fail
 * with -EAGAIN; a header block flushed with sendto() is counted but never failed. Returns false
 * when it failed the send. */
static bool send_enter(int sock, bool piece)
{
    const struct nsos_socket_start *socket = zvfs_get_fd_obj(sock, NULL, EBADF);

    if (shrink_size != 0 && socket != NULL && !net_socket_is_tls((void *)socket)) {
        (void)web_host_set_send_buffer(socket->poll_mid.fd, shrink_size);
        shrink_size = 0;
    }
    if (send_depth == 0u) {
        ++outer_sends;
        if (fail_armed && piece) {
            if (fail_skip == 0u) {
                fail_armed = false;
                ++eagain_count;
                errno = EAGAIN;
                return false;
            }
            --fail_skip;
        }
    } else {
        ++inner_sends;
    }
    ++send_depth;
    return true;
}

static void send_leave(ssize_t sent)
{
    --send_depth;
    if (send_depth == 0u && sent < 0 && errno == EAGAIN) {
        ++real_eagain;
    }
}

/* From Zephyr v4.5.0 the server passes the rest of a response's header block, a chunk and the
 * terminator to the socket in one sendmsg(), one call for each piece of the body. */
ssize_t __wrap_z_impl_zsock_sendmsg(int sock, const struct net_msghdr *msg, int flags)
{
    ssize_t sent;

    if (!send_enter(sock, true)) {
        return -1;
    }
    sent = __real_z_impl_zsock_sendmsg(sock, msg, flags);
    send_leave(sent);
    return sent;
}

ssize_t __wrap_z_impl_zsock_sendto(int sock, const void *buf, size_t len, int flags,
                                   const struct net_sockaddr *dest_addr, net_socklen_t addrlen)
{
    ssize_t sent;

    if (!send_enter(sock, false)) {
        return -1;
    }
    sent = __real_z_impl_zsock_sendto(sock, buf, len, flags, dest_addr, addrlen);
    send_leave(sent);
    return sent;
}

void web_probe_fail_send_after(unsigned skip)
{
    fail_skip = skip;
    fail_armed = true;
}

void web_probe_set_next_send_buffer(int size)
{
    shrink_size = size;
}

unsigned web_probe_eagain_count(void)
{
    return eagain_count;
}

unsigned web_probe_outer_sends(void)
{
    return outer_sends;
}

unsigned web_probe_inner_sends(void)
{
    return inner_sends;
}

unsigned web_probe_real_eagain(void)
{
    return real_eagain;
}
