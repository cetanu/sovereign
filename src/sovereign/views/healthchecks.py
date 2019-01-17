from quart import Blueprint, render_template_string
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
async def health_check():
    """ I am still rendering stuff as expected """
    ret = dict()
    ret['exceptions'] = list()
    for template in XDS_TEMPLATES[xds_version].keys():
        try:
            discovery.response(mock_discovery_request(), xds=template, version=xds_version, debug=True)
            ret[template] = True
        except Exception as e:
            ret[template] = False
            ret['exceptions'].append(f'({template}): {e}')
    if ret['exceptions']:
        code = 500
    else:
        code = 200
    return await render_template_string(healthcheck_template, result=ret), code


@blueprint.route('/deepcheck')
def deepcheck():
    """ I can reach the configured sources """
    load_sources(service_cluster='', debug=True)
    return 'OK'
