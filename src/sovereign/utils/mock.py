def mock_discovery_request(service_cluster=None, resource_names=None, region='none'):
    return {
        'node': {
            # A blank string will select any cluster when debugging
            'cluster': service_cluster or '',
            'build_version': 'e5f864a82d4f27110359daa2fbdcb12d99e415b9/1.8.0/Clean/RELEASE',
            "locality": {
                "zone": region
            },
        },
        'version_info': '0',
        'resource_names': resource_names or []
    }
