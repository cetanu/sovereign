import yaml
from collections import defaultdict
from quart import Blueprint, request, g
from quart.json import jsonify
from sovereign import XDS_TEMPLATES
from sovereign.utils.mock import mock_discovery_request
from sovereign.utils.templates import remove_tls_certificates
from sovereign import discovery
from sovereign.sources import load_sources
from sovereign.decorators import cache

blueprint = Blueprint('admin', __name__)

latest_version = list(XDS_TEMPLATES)[-1]
discovery_types = XDS_TEMPLATES[latest_version].keys()


@blueprint.route('/admin/xds_dump')
def display_config():
    xds_type = request.args.get('type')
    service_cluster = request.args.get('partition', '')
    resource_names = request.args.get('resource_names')
    region = request.args.get('region')
    version = request.args.get('envoy_version', '1.9.0')
    ret = defaultdict(list)
    code = 200

    if xds_type in discovery_types:
        selected_types = [xds_type]
    else:
        selected_types = []
        ret = {
            'message': 'Query parameter "type" must be one of ["clusters", "listeners", "routes", "endpoints"]'
        }
        code = 400

    for discovery_type in selected_types:
        mock_request = mock_discovery_request(
            service_cluster=service_cluster,
            resource_names=resource_names,
            region=region
        )
        response = discovery.response(
            request=mock_request,
            xds=discovery_type,
            version=version,
            debug=True
        )
        if isinstance(response, dict):
            ret['resources'] += response.get('resources') or []

    # Hide private keys
    for resource in ret.get('resources', []):
        if not isinstance(resource, dict):
            continue
        if 'Listener' not in resource['@type']:
            continue
        remove_tls_certificates(resource)

    return jsonify(ret), code


@blueprint.route('/admin/source_dump')
def instances():
    debug = yaml.safe_load(request.args.get('debug', 'no'))
    cluster = request.args.get('partition', '')
    modified = yaml.safe_load(request.args.get('modified', 'yes'))
    args = {
        'debug': debug,
        'modify': modified,
        'service_cluster': cluster
    }
    ret = load_sources(**args)
    g.log = g.log.bind(args=args)
    return jsonify(ret)


@blueprint.route('/admin/cache_dump')
def show_cached_keys():
    return jsonify(list(sorted(cache._cache.keys())))


@blueprint.route('/admin/cache_purge')
def purge_cache():
    cache.clear()
    return 'Cache cleared'
