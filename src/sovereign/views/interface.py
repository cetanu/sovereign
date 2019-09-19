from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import UJSONResponse

from sovereign import html_templates

router = APIRouter()


@router.get('/hello', summary='just a test?', response_class=UJSONResponse)
def main_page(request: Request):
    return html_templates.TemplateResponse('test.json.jinja2', context={'things': [1, 2, 3], 'request': request})
