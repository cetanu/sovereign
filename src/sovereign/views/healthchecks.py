from quart import Blueprint
from sovereign import XDS_TEMPLATES
from sovereign import discovery
from sovereign.sources import load_sources
from sovereign.utils.mock import mock_discovery_request


blueprint = Blueprint('healthchecks', __name__)

healthcheck_template = '''
<h2>XDS Rendering health:</h1>
<ul>
{% for t, r in result.items() %}
    <li><strong>{{ t }}</strong>: {{ r }}</li>
{% endfor %}
</ul>
'''

xds_version = list(XDS_TEMPLATES.keys())[-1]


@blueprint.route('/healthcheck')
def health_check():
    """ I am still rendering stuff as expected """
    for template in XDS_TEMPLATES[xds_version].keys():
        discovery.response(
            mock_discovery_request(),
            xds=template,
            version=xds_version,
            debug=True
        )
    return 'OK'


@blueprint.route('/deepcheck')
def deepcheck():
    """ I can reach the configured sources """
    load_sources(service_cluster='', debug=True)
    return 'OK'
