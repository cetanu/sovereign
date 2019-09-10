from random import randint
from sovereign.dataclasses import DiscoveryRequest, Node, Locality


def mock_discovery_request(service_cluster=None, resource_names=None, region='none', version='1.11.1'):
    # noinspection PyArgumentList
    return DiscoveryRequest(
        node=Node(
            id='mock',
            cluster=service_cluster or '',
            build_version=f'e5f864a82d4f27110359daa2fbdcb12d99e415b9/{version}/Clean/RELEASE',
            locality=Locality(
                zone=region
            ),
            metadata={
                'hide_private_keys': True
            }
        ),
        version_info=str(randint(100000, 1000000000)),
        resource_names=resource_names or [],
    )
