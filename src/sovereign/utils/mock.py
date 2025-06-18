import re
import ast
from typing import Optional, Dict, List
from random import randint
from sovereign.schemas import DiscoveryRequest, Node, Locality, Status

scrub = re.compile(r"[^a-zA-Z_\.]")


def mock_discovery_request(
    api_version: Optional[str] = "V3",
    resource_type: Optional[str] = None,
    resource_names: Optional[List[str] | str] = None,
    region: Optional[str] = "none",
    version: Optional[str] = "1.11.1",
    metadata: Optional[Dict[str, str]] = None,
    error_message: Optional[str] = None,
    expressions: Optional[list[str]] = None,
) -> DiscoveryRequest:
    if resource_names is None:
        resource_names = []
    if isinstance(resource_names, str):
        resource_names = [resource_names]
    if expressions is None:
        expressions = []
    base_node = Node(
        id="sovereign-interface",
        cluster="*",
        build_version=f"<randomHash>/{version}/Clean/RELEASE",
        locality=Locality(zone=region),
    ).model_dump()
    set_node_expressions(base_node, expressions)
    request = DiscoveryRequest(
        type_url=None,
        node=Node.model_validate(base_node),
        version_info=str(randint(100000, 1000000000)),
        resource_names=resource_names,
        is_internal_request=True,
        desired_controlplane="__sovereign__",
        error_detail=Status(code=200, message="None", details=["None"]),
        api_version=api_version,
        resource_type=resource_type,
    )
    if isinstance(metadata, dict):
        request.node.metadata = metadata
    if error_message:
        request.error_detail = Status(code=666, message=error_message, details=["foo"])
    return request


def set_node_expressions(node, expressions):
    for expr in expressions:
        try:
            field, value = re.split(r"\s*=\s*", expr, maxsplit=1)
            value = f'"{value}"'
        except ValueError:
            raise ValueError(f"Invalid expression format: {expr}")

        field = scrub.sub("", field)
        parts = field.split(".")

        try:
            value = ast.literal_eval(value)
        except Exception as e:
            raise ValueError(f"invalid value: {value}") from e

        current = node
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
