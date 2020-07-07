def call(instances, discovery_request, **kwargs):
    for instance in instances:
        yield {
            'name': instance['name'],
            'connect_timeout': '5s',
            'tls_context': {},
            'type': 'strict_dns',
            'load_assignment': {
                'cluster_name': f'{ instance["name"] }_cluster',
                'endpoints': kwargs['eds'].locality_lb_endpoints(
                    upstreams=instance['endpoints'],
                    request=discovery_request,
                    resolve_dns=False
                )
            }
        }
