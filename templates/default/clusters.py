import envoy_data_plane.envoy.api.v2 as envoy
from betterproto import Casing
from datetime import timedelta


def call(instances, discovery_request, **kwargs):
    eds = kwargs['eds']

    for instance in instances:
        yield envoy.Cluster(
            name=instance['name'],
            type=envoy.ClusterDiscoveryType.STRICT_DNS,
            connect_timeout=timedelta(seconds=5),
            # A bug requires some value inside tls_context for it to be in the resulting json
            tls_context=envoy.auth.UpstreamTlsContext(
                common_tls_context=envoy.auth.CommonTlsContext()
            ),
            load_assignment=envoy.ClusterLoadAssignment(
                cluster_name=f'{instance["name"]}_cluster',
                endpoints=[
                    envoy.endpoint.LocalityLbEndpoints().from_dict(endpoint)
                    for endpoint in eds.locality_lb_endpoints(
                        upstreams=instance['endpoints'],
                        request=discovery_request,
                        resolve_dns=False
                    )
                ]
            ),
        ).to_dict(casing=Casing.SNAKE)
