import re
import structlog
from structlog import DropEvent

ignored_messages = '|'.join((
    '/healthcheck',
    '/deepcheck',
))


# pylint: disable=too-few-public-methods

class IgnoreRecordsStructlog:
    def __call__(self, logger, method_name, event_dict):
        logline = str(event_dict)
        if re.search(ignored_messages, logline):
            raise DropEvent
        return event_dict


structlog.configure(
    processors=[
        # IgnoreRecordsStructlog(),
        structlog.processors.JSONRenderer()
    ]
)

LOG = structlog.getLogger()
