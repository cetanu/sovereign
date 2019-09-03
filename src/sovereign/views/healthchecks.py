import random
from quart import Blueprint
from sovereign import XDS_TEMPLATES, __versionstr__
from sovereign import discovery
from sovereign.sources import match_node
from sovereign.utils.mock import mock_discovery_request


blueprint = Blueprint('healthchecks', __name__)


@blueprint.route('/healthcheck')
def health_check():
    return 'OK'


@blueprint.route('/deepcheck')
def deep_check():
    template = random.choice(
        list(XDS_TEMPLATES['default'].keys())
    )
    discovery.response(
        mock_discovery_request(),
        xds=template,
        debug=True
    )
    match_node(request=mock_discovery_request())
    return 'OK'


@blueprint.route('/version')
def version_check():
    return f'Sovereign {__versionstr__}'
