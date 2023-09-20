from contextvars import ContextVar
from importlib.metadata import version
from starlette.templating import Jinja2Templates

from sovereign.utils.resources import get_package_file


_request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _request_id_ctx_var.get()


DIST_NAME = "sovereign"

__version__ = version(DIST_NAME)

html_templates = Jinja2Templates(get_package_file(DIST_NAME, "templates"))  # type: ignore[arg-type]
