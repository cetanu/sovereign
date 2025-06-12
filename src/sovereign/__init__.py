import sys
from contextvars import ContextVar
from importlib.metadata import version
from sovereign.context import TemplateContext

from sovereign.utils.crypto.suites import EncryptionType
from starlette.templating import Jinja2Templates

from sovereign.logging.bootstrapper import LoggerBootstrapper
from sovereign.schemas import (
    config,
    EncryptionConfig,
    migrate_configs,
)
from sovereign.statistics import configure_statsd
from sovereign.utils.crypto.crypto import CipherContainer
from sovereign.utils.resources import get_package_file

_request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _request_id_ctx_var.get()


DIST_NAME = "sovereign"

__version__ = version(DIST_NAME)

html_templates = Jinja2Templates(
    directory=str(get_package_file(DIST_NAME, "templates"))
)

if sys.argv[0].endswith("sovereign"):
    migrate_configs()

stats = configure_statsd()
logs = LoggerBootstrapper(config)
application_logger = logs.application_logger.logger

template_context = TemplateContext.from_config()

encryption_configs = config.authentication.encryption_configs
server_cipher_container = CipherContainer.from_encryption_configs(
    encryption_configs, logger=application_logger
)
disabled_ciphersuite = CipherContainer.from_encryption_configs(
    encryption_configs=[EncryptionConfig("", EncryptionType.DISABLED)],
    logger=application_logger,
)
