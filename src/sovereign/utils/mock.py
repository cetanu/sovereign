from typing import Optional, Dict, List
from random import randint
from sovereign.schemas import DiscoveryRequest, Node, Locality


def mock_discovery_request(
    service_cluster: Optional[str] = None,
    resource_names: Optional[List[str]] = None,
    region: str = "none",
    version: str = "1.11.1",
    metadata: Optional[Dict[str, str]] = None,
) -> DiscoveryRequest:
    request = DiscoveryRequest(
        node=Node(
            id="mock",
            cluster=service_cluster or "",
            build_version=f"e5f864a82d4f27110359daa2fbdcb12d99e415b9/{version}/Clean/RELEASE",
            locality=Locality(zone=region),
        ),
        version_info=str(randint(100000, 1000000000)),
        resource_names=resource_names or [],
        hide_private_keys=True,
    )
    if isinstance(metadata, dict):
        request.node.metadata = metadata
    return request
