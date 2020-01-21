import random
from fastapi.routing import APIRouter
from starlette.responses import PlainTextResponse
from sovereign import XDS_TEMPLATES, __versionstr__
from sovereign import discovery
from sovereign.sources import match_node
from sovereign.utils.mock import mock_discovery_request


router = APIRouter()


@router.get('/healthcheck', summary='Healthcheck (Does the server respond to HTTP?)')
async def health_check():
    return PlainTextResponse('OK')


@router.get('/deepcheck', summary='Deepcheck (Can the server render a random template?)')
async def deep_check():
    template = random.choice(
        list(XDS_TEMPLATES['default'].keys())
    )
    await discovery.response(
        mock_discovery_request(),
        xds_type=template
    )
    match_node(request=mock_discovery_request())
    return PlainTextResponse(f'Rendered {template} OK')


@router.get('/version', summary='Display the current version of Sovereign')
async def version_check():
    return PlainTextResponse(f'Sovereign {__versionstr__}')
