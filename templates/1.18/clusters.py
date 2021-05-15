from envoy_data_plane.envoy.api.v2.auth import CommonTlsContext, UpstreamTlsContext
from envoy_data_plane.envoy.config.cluster.v3 import (
    Cluster,
    ClusterDiscoveryType,
)
from envoy_data_plane.envoy.config.endpoint.v3 import (
    ClusterLoadAssignment,
    LocalityLbEndpoints,
)
from envoy_data_plane.envoy.config.core.v3 import TransportSocket
from betterproto import Casing
from datetime import timedelta


def call(instances, discovery_request, **kwargs):
    eds = kwargs["eds"]

    for instance in instances:
        yield Cluster(
            name=instance["name"],
            type=ClusterDiscoveryType.STRICT_DNS,
            connect_timeout=timedelta(seconds=5),
            transport_socket=TransportSocket(
                name="envoy.transport_sockets.tls",
                typed_config=UpstreamTlsContext(common_tls_context=CommonTlsContext()),
            ),
            load_assignment=ClusterLoadAssignment(
                cluster_name=f'{instance["name"]}_cluster',
                endpoints=[
                    LocalityLbEndpoints().from_dict(endpoint)
                    for endpoint in eds.locality_lb_endpoints(
                        upstreams=instance["endpoints"],
                        request=discovery_request,
                        resolve_dns=False,
                    )
                ],
            ),
        ).to_dict(casing=Casing.SNAKE)
