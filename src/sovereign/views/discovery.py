from quart import Blueprint, request, jsonify, g
from sovereign import discovery, statsd, NO_CHANGE_CODE

blueprint = Blueprint('discovery', __name__)


@blueprint.route('/v2/discovery:<xds_type>', methods=['POST'])
async def discovery_endpoint(xds_type):
    discovery_request = await request.get_json(force=True)

    build_version = discovery_request['node']['build_version']
    revision, version, *other_metadata = build_version.split('/')
    resource_names = discovery_request.get('resource_names', [])

    g.log = g.log.bind(
        resource_names=resource_names,
        envoy_ver=version
    )

    response = discovery.response(discovery_request, xds_type, version)

    if not response['resources']:
        ret = 'No resources found'
        code = 404
    elif response['version_info'] == discovery_request.get('version_info'):
        ret = 'No changes'
        code = NO_CHANGE_CODE
    elif response['version_info'] != discovery_request.get('version_info', '0'):
        ret = response
        code = 200
    else:
        ret = 'Unknown Error'
        code = 500

    try:
        client_ip = discovery_request['node']['metadata']['ipv4']
    except KeyError:
        client_ip = '-'

    metrics_tags = [
        f"client_ip:{client_ip}",
        f"client_version:{version}",
        f"response_code:{code}",
        f"xds_type:{xds_type}"
    ]
    metrics_tags += [f"resource:{resource}" for resource in resource_names]
    statsd.increment('discovery.rq_total', tags=metrics_tags)
    return jsonify(ret), code
