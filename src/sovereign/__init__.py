from contextvars import ContextVar
from importlib.metadata import version

from sovereign.configuration import EncryptionConfig, config
from sovereign.logging.bootstrapper import LoggerBootstrapper
from sovereign.statistics import configure_statsd
from sovereign.utils.crypto.crypto import CipherContainer
from sovereign.utils.crypto.suites import EncryptionType

_request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _request_id_ctx_var.get()


WORKER_URL = "http://localhost:9080"
DIST_NAME = "sovereign"
__version__ = version(DIST_NAME)

stats = configure_statsd()
logs = LoggerBootstrapper(config)
application_logger = logs.application_logger.logger

encryption_configs = config.authentication.encryption_configs
server_cipher_container = CipherContainer.from_encryption_configs(
    encryption_configs, logger=application_logger
)
disabled_ciphersuite = CipherContainer.from_encryption_configs(
    encryption_configs=[EncryptionConfig("", EncryptionType.DISABLED)],
    logger=application_logger,
)
