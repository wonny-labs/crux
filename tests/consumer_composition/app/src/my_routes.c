/* The product's own route. It uses the public header <crux/web.h> only. */
#include <crux/web.h>

static crux_web_result_t on_ping(crux_web_request_t *request, crux_access_session_t session,
                                 void *context)
{
    (void)session;
    (void)context;
    return crux_web_respond(request, 200, "text/plain", "pong", 4u);
}

/* A permission as the access class: the route is not on the reviewed list of public and
 * session-only routes. */
CRUX_WEB_ROUTE(product_ping, "/api/v1/product/ping", CRUX_WEB_GET, "product.demo", on_ping, NULL);
