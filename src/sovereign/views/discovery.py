from quart import Blueprint, request, jsonify, g
from sovereign import discovery, statsd, config
from sovereign.dataclasses import DiscoveryRequest
from sovereign.utils.auth import authenticate

blueprint = Blueprint('discovery', __name__)


@blueprint.route('/v2/discovery:<xds_type>', methods=['POST'])
async def discovery_endpoint(xds_type):
    discovery_request = await request.get_json(force=True)
    req = DiscoveryRequest(**discovery_request)
    del discovery_request

    g.log = g.log.bind(
        resource_names=req.resource_names,
        envoy_ver=req.envoy_version
    )

    authenticate(req)
    response = await discovery.response(req, xds_type)

    if response['version_info'] == req.version_info:
        ret = 'No changes'
        code = config.no_changes_response_code
    elif not response['resources']:
        ret = 'No resources found'
        code = 404
    elif response['version_info'] != req.version_info:
        ret = response
        code = 200
    else:
        ret = 'Unknown Error'
        code = 500

    try:
        client_ip = req.node.metadata.get('ipv4')
    except KeyError:
        client_ip = '-'

    metrics_tags = [
        f"client_ip:{client_ip}",
        f"client_version:{req.envoy_version}",
        f"response_code:{code}",
        f"xds_type:{xds_type}"
    ]
    metrics_tags += [f"resource:{resource}" for resource in req.resource_names]
    statsd.increment('discovery.rq_total', tags=metrics_tags)
    return jsonify(ret), code
