def mock_discovery_request(service_cluster=None, resource_names=None, region='none', version='1.11.1'):
    return {
        'node': {
            # A blank string will select any cluster when debugging
            'cluster': service_cluster or '',
            'build_version': f'e5f864a82d4f27110359daa2fbdcb12d99e415b9/{version}/Clean/RELEASE',
            "locality": {
                "zone": region
            },
        },
        'version_info': '0',
        'resource_names': resource_names or []
    }
