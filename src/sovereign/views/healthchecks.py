import random
from quart import Blueprint
from sovereign import XDS_TEMPLATES
from sovereign import discovery
from sovereign.sources import load_sources
from sovereign.utils.mock import mock_discovery_request


blueprint = Blueprint('healthchecks', __name__)

xds_version = list(XDS_TEMPLATES.keys())[-1]


@blueprint.route('/healthcheck')
def health_check():
    return 'OK'


@blueprint.route('/deepcheck')
def deep_check():
    template = random.choice(
        list(XDS_TEMPLATES[xds_version].keys())
    )
    discovery.response(
        mock_discovery_request(),
        xds=template,
        version=xds_version,
        debug=True
    )
    load_sources(service_cluster='', debug=True)
    return 'OK'
