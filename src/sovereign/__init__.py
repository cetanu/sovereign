import os
from pkg_resources import get_distribution, resource_filename
from starlette.templating import Jinja2Templates
from sovereign import config_loader
from sovereign.utils.dictupdate import merge
from sovereign.schemas import SovereignConfig, SovereignAsgiConfig, XdsTemplate


def parse_raw_configuration(path: str):
    if path is None:
        raise RuntimeError('No configuration specified via environment variable SOVEREIGN_CONFIG')
    ret = dict()
    for p in path.split(','):
        ret = merge(
            obj_a=ret,
            obj_b=config_loader.load(p),
            merge_lists=True
        )
    return ret


__versionstr__ = get_distribution('sovereign').version
__version__ = tuple(int(i) for i in __versionstr__.split('.'))
config_path = os.getenv('SOVEREIGN_CONFIG', None)
html_templates = Jinja2Templates(resource_filename('sovereign', 'templates'))
config = SovereignConfig(**parse_raw_configuration(config_path))
asgi_config = SovereignAsgiConfig()
XDS_TEMPLATES = config.xds_templates
