def call(instances, discovery_request, **kwargs):
    eds = kwargs["eds"]

    for instance in instances:
        yield {
            "name": instance["name"],
            "type": "STRICT_DNS",
            "connect_timeout": "5.000s",
            "transport_socket": {
                "name": "envoy.transport_sockets.tls",
                "typed_config": {
                    "@type": "type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext",
                },
            },
            "load_assignment": {
                "cluster_name": f"{instance['name']}_cluster",
                "endpoints": eds.locality_lb_endpoints(
                    upstreams=instance["endpoints"],
                    request=discovery_request,
                    resolve_dns=False,
                ),
            },
        }
