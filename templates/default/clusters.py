from sovereign.utils import eds


def _is_wildcard(value):
    """Check if a value is a wildcard matcher."""
    return value in [["*"], "*", ("*",)]


# noinspection PyUnusedLocal
def call(backends, dynamic_backends, discovery_request, **kwargs):
    all_backends = backends + dynamic_backends

    filtered_backends = []
    node_value = discovery_request.node.cluster
    for backend in all_backends:
        backend_value = backend.get("service_clusters", [])
        node_is_wildcard = _is_wildcard(node_value)
        backend_is_wildcard = _is_wildcard(backend_value)
        if node_value in backend_value or node_is_wildcard or backend_is_wildcard:
            filtered_backends.append(backend)

    for backend in filtered_backends:
        yield {
            "name": backend["name"],
            "type": "STRICT_DNS",
            "connect_timeout": "5.000s",
            "transport_socket": {
                "name": "envoy.transport_sockets.tls",
                "typed_config": {
                    "@type": "type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext",
                },
            },
            "load_assignment": {
                "cluster_name": f"{backend['name']}_cluster",
                "endpoints": eds.locality_lb_endpoints(
                    upstreams=backend["endpoints"],
                    request=discovery_request,
                    resolve_dns=False,
                ),
            },
        }
