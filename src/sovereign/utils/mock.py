from typing import Optional, Dict, List
from random import randint
from sovereign.schemas import DiscoveryRequest, Node, Locality, Resources, Status


def mock_discovery_request(
    service_cluster: Optional[str] = None,
    resource_names: Optional[List[str]] = None,
    region: str = "none",
    version: str = "1.11.1",
    metadata: Optional[Dict[str, str]] = None,
    error_message: Optional[str] = None,
) -> DiscoveryRequest:
    if resource_names is None:
        resource_names = Resources()
    else:
        resource_names = Resources(resource_names)
    request = DiscoveryRequest(
        type_url=None,
        node=Node(
            id="mock",
            cluster=service_cluster or "",
            build_version=f"e5f864a82d4f27110359daa2fbdcb12d99e415b9/{version}/Clean/RELEASE",
            locality=Locality(zone=region, region="example", sub_zone="a"),
        ),
        version_info=str(randint(100000, 1000000000)),
        resource_names=resource_names,
        hide_private_keys=True,
        desired_controlplane="controlplane",
        error_detail=Status(code=200, message="None", details=["None"]),
    )
    if isinstance(metadata, dict):
        request.node.metadata = metadata
    if error_message:
        request.error_detail = Status(code=666, message=error_message, details=["foo"])
    return request
